"""Interactive SLURM rank processing of independent dataset chunks.

Designed for execution *inside* the CMSSW/Shifter environment. Jobs are
assigned statically, one entry to exactly one SLURM rank.
"""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import traceback
import hashlib
import shlex
import fcntl

STAGES = ('pfnano', 'corrected', 'h5', 'preprocess')
from .validation import validate

KINDS = ('miniaod', 'pfnano', 'corrected', 'h5')
NEXT = {'miniaod': STAGES, 'pfnano': STAGES[1:],
        'corrected': STAGES[2:], 'h5': STAGES[3:]}
PATTERNS = {'pfnano': 'file_list.root', 'corrected': 'file_list_postprocessed.root'}


def _safe(value):
    return re.sub(r'[^A-Za-z0-9_.-]+', '_', value).strip('._')


def discover(folder, kind):
    root = Path(folder).expanduser().resolve()
    if root.is_file():
        if root.suffix == '.txt':
            # Input manifests may contain PFNano, corrected ROOT, HDF5 or MiniAOD paths.
            # Resolve local relative paths from the list's directory.
            lines = [line.strip() for line in root.read_text().splitlines()
                     if line.strip() and not line.lstrip().startswith('#')]
            result = []
            for line in lines:
                if line.startswith(('root://', 'file:')):
                    result.append(line if kind == 'miniaod' else (line[5:] if line.startswith('file:') else line))
                else:
                    item = Path(line).expanduser()
                    result.append(str((root.parent / item).resolve() if not item.is_absolute() else item))
            if kind != 'miniaod':
                for item in result:
                    if not Path(item).is_file():
                        raise ValueError('Input does not exist: {}'.format(item))
            return result
        return [str(root)]
    if not root.is_dir():
        raise ValueError('Missing input: {}'.format(root))
    pattern = PATTERNS.get(kind, '*.h5' if kind == 'h5' else '*.root')
    paths = sorted(root.rglob(pattern))
    stage_dir = {'pfnano': 'pfnano', 'corrected': 'corrected', 'h5': 'h5'}.get(kind)
    if stage_dir and (root / stage_dir).is_dir():
        paths = sorted((root / stage_dir).glob('*.h5' if kind == 'h5' else '*.root'))
    if kind == 'h5':
        paths = [p for p in paths if not p.name.startswith('omni_')]

    if kind == 'miniaod':
        paths = [p for p in paths if p.name not in PATTERNS.values()
                 and 'postprocessed' not in p.name.lower()]
    return [str(p) for p in paths]


def prepare_datasets(specifications, manifest_path, files_per_task=1):
    """Each spec: SAMPLE,TYPE,INPUT_STAGE,INPUT_DIR_OR_FILE."""
    if files_per_task < 1:
        raise ValueError('files_per_task must be >= 1')
    target = Path(manifest_path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    tasks = []
    for spec in specifications:
        fields = spec.split(',', 3)
        if len(fields) != 4:
            raise ValueError('Expected SAMPLE,TYPE,STAGE,PATH: {}'.format(spec))
        sample, sample_type, kind, location = fields
        if not sample or sample_type not in ('mc', 'data') or kind not in KINDS:
            raise ValueError('Invalid dataset spec: {}'.format(spec))
        paths = discover(location, kind)
        if len(paths) != len(set(paths)):
            raise ValueError('Duplicate input paths for {}'.format(sample))
        if not paths:
            raise ValueError('No {} files found for {}'.format(kind, sample))
        if kind != 'miniaod':
            batches = [[p] for p in paths]
        else:
            batches = [paths[i:i+files_per_task] for i in range(0,len(paths),files_per_task)]
        for batch in batches:
            name = '{}_{:05d}'.format(_safe(sample), sum(t['sample'] == sample for t in tasks))
            tasks.append({'id': name, 'sample': sample, 'type': sample_type,
                          'source': kind, 'files': batch})
    if len({t['id'] for t in tasks}) != len(tasks):
        raise ValueError('Duplicate task IDs; dataset names must be unique')
    target.write_text(json.dumps({'version': 1, 'tasks': tasks}, indent=2) + '\n')
    return target, tasks


def paths_for_task(task, output_dir):
    root = Path(output_dir).resolve() / _safe(task['sample'])
    base = task['id']
    return {s: root / s / (('omni_' if s == 'preprocess' else '') + base +
            ('.root' if s in ('pfnano','corrected') else '.h5')) for s in STAGES}


def _run_task(task, output_dir, repo, *, through='preprocess', overwrite=False,
             dry_run=False, cr=False, period=None):
    if through not in STAGES:
        raise ValueError('Invalid stop stage: {}'.format(through))
    stages = NEXT[task['source']]
    stages = stages[:stages.index(through) + 1] if through in stages else ()
    if not stages:
        raise ValueError('Cannot stop at {} when starting from {}'.format(through, task['source']))
    if task['type'] == 'data' and 'corrected' in stages:
        if period is None:
            found = re.search(r'(?:Run2016|JetHT|SingleMuon)([B-H])(?:$|[_-])', task['sample'])
            if not found:
                raise ValueError('Cannot infer data era for {}; pass --period F/G/H'.format(task['sample']))
            period = found.group(1)
        if period not in ('F', 'G', 'H'):
            raise ValueError('This workflow targets post-VFP data: {} is not supported'.format(period))
    period = period or 'H'
    paths = paths_for_task(task, output_dir)

    # Only MiniAOD uses a chunk list. Later stages consume their original file.
    first_source = Path(task['files'][0]) if task['source'] != 'miniaod' else None
    list_path = Path(output_dir).resolve() / _safe(task['sample']) / 'inputs' / (task['id'] + '.txt')
    if task['source'] == 'miniaod' and not dry_run:
        list_path.parent.mkdir(parents=True, exist_ok=True)
        list_path.write_text(''.join((p if p.startswith(('file:', 'root:')) else 'file:' + p) + '\n'
                                     for p in task['files']))
    commands = []
    for i, stage in enumerate(stages):
        dst = paths[stage]
        if stage == 'pfnano':
            config = 'pfnano_{}_2016UL_OpenData.py'.format(task['type'])
            cmd = ['cmsRun', str(Path(repo)/'workflow'/config),
                   'inputFiles='+str(list_path), 'outputFile='+str(dst)]
        elif stage == 'corrected':
            src = first_source if i == 0 else paths['pfnano']
            cmd = ['python', str(Path(repo)/'workflow'/'postprocessor.py'),
                   '-d', str(src.parent), '-i', src.name, '-o', str(dst),
                   '--period', period]
            if task['type'] == 'mc':
                cmd += ['--is-mc']
        elif stage == 'h5':
            src = first_source if i == 0 else paths['corrected']
            cmd = ['python', str(Path(repo)/'workflow'/'H5_maker.py'),
                   '-i', str(src), '-o', str(dst), '--sample_type',
                   'MC' if task['type'] == 'mc' else 'data']
            if task['type'] == 'mc':
                cmd += ['--sample', task['sample']]
            else:
                cmd += ['-j', str(Path(repo)/'workflow'/'Cert_271036-284044_13TeV_Legacy2016_Collisions16_JSON.txt')]
            if cr:
                cmd += ['--cr', '1']
        else:
            src = first_source if i == 0 else paths['h5']
            cmd = ['python3', str(Path(repo)/'workflow'/'preprocess_aspen_dijet.py'),
                   '--input-file', str(src), '--output-file', str(dst), '--sample', task['sample']]
            if cr:
                cmd += ['--cr']
        commands.append((stage, cmd))
        if dry_run:
            print('[PLAN] {} {} {}'.format(task['id'], stage, ' '.join(shlex.quote(x) for x in cmd)), flush=True)
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        complete = dst.with_name(dst.name + '.complete.json')
        # Match inputs, options and code before reusing an artifact. A readable
        # partial file alone is never proof of successful completion.
        inputs = task['files'] if i == 0 else [str(paths[stages[i-1]])]
        def stamp(value):
            p = Path(value[5:] if value.startswith('file:') else value)
            if p.is_file():
                st = p.stat()
                return [value, st.st_size, st.st_mtime_ns]
            return [value]
        code = hashlib.sha256()
        for p in sorted((Path(repo)/'workflow').glob('*')) + sorted((Path(repo)/'cms_od').glob('*.py')):
            if p.is_file():
                code.update(p.read_bytes())
        signature = {'task': task, 'command': cmd, 'inputs': [stamp(x) for x in inputs],
                     'code': code.hexdigest(), 'cr': cr}
        if dst.exists() and complete.exists() and not overwrite:
            try:
                record = json.loads(complete.read_text())
                if record.get('signature') == signature and record.get('output_stamp') == stamp(str(dst)):
                    validate(dst, stage, nonempty=(stage == 'pfnano'))
                    print('[SKIP] {} {} {}'.format(task['id'], stage, dst), flush=True)
                    continue
            except Exception:
                pass
        if complete.exists():
            complete.unlink()
        print('[RUN] {} {} {}'.format(task['id'], stage, ' '.join(cmd)), flush=True)
        try:
            work = Path(output_dir).resolve() / '.work' / task['id'] / stage
            work.mkdir(parents=True, exist_ok=True)
            subprocess.run(cmd, check=True, cwd=str(work))
            n = validate(dst, stage)
            if n == 0 and stage == 'pfnano':
                raise ValueError('Unexpected empty PFNano Events tree')
            complete.write_text(json.dumps({'task': task, 'stage': stage, 'events_or_jets': n,
                                            'output': str(dst), 'signature': signature,
                                            'output_stamp': stamp(str(dst))}, indent=2))
            print('[OK] {} {} entries={}'.format(task['id'], stage, n), flush=True)
        except Exception as exc:
            print('[FAIL] {} {} {}'.format(task['id'], stage, str(exc).replace('\n', ' ')), flush=True)
            if complete.exists():
                complete.unlink()
            # Keep files for diagnostics, but never mark as completed.
            raise
    return commands


def run_task(task, output_dir, repo, **kwargs):
    if kwargs.get('dry_run'):
        return _run_task(task, output_dir, repo, **kwargs)
    lock = Path(output_dir) / '.locks' / (task['id'] + '.lock')
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open('a') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise RuntimeError('Task already running: {}'.format(task['id']))
        return _run_task(task, output_dir, repo, **kwargs)


def run_rank(manifest, output_dir, rank, nranks, **kwargs):
    info = json.loads(Path(manifest).read_text())
    if rank < 0 or nranks < 1 or rank >= nranks:
        raise ValueError('Invalid rank configuration')
    assigned = info['tasks'][rank::nranks]
    print('Rank {}/{}: {} tasks'.format(rank, nranks, len(assigned)), flush=True)
    failures = []
    for task in assigned:
        try:
            run_task(task, output_dir, **kwargs)
        except Exception as exc:
            traceback.print_exc()
            failures.append('{}: {}'.format(task['id'], exc))
    if failures:
        raise RuntimeError('Rank {} failed: {}'.format(rank, '; '.join(failures)))
    return [t['id'] for t in assigned]


def main(argv=None):
    p = argparse.ArgumentParser(description='Internal rank worker', allow_abbrev=False)
    p.add_argument('--manifest', required=True)
    p.add_argument('--output-dir', required=True)
    p.add_argument('--through', choices=STAGES, default='preprocess')
    p.add_argument('--rank', type=int, default=int(os.environ.get('SLURM_PROCID',0)))
    p.add_argument('--nranks', type=int, default=int(os.environ.get('SLURM_NTASKS',1)))
    p.add_argument('--overwrite', action='store_true')
    p.add_argument('--cr', action='store_true')
    p.add_argument('--period', choices=('F','G','H'))
    a = p.parse_args(argv)
    run_rank(a.manifest,a.output_dir,a.rank,a.nranks,repo=Path(__file__).resolve().parents[1],
             through=a.through,overwrite=a.overwrite,cr=a.cr,period=a.period)


if __name__ == '__main__':
    main()
