"""Single public launcher. Host-side code uses only Python's standard library."""
import argparse
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import time
import threading

from .distributed import prepare_datasets, run_rank
from .summary import summarize

# Public operation names, mapped to input formats and produced artifacts.
STEPS = ('miniaod', 'postprocess', 'h5maker', 'inputsomni')
INPUTS = dict(zip(STEPS, ('miniaod', 'pfnano', 'corrected', 'h5')))
OUTPUTS = dict(zip(STEPS, ('pfnano', 'corrected', 'h5', 'preprocess')))
REPO = Path(__file__).resolve().parents[1]


def positive(value):
    value = int(value)
    if value < 1:
        raise argparse.ArgumentTypeError('must be a positive integer')
    return value


def parser():
    p = argparse.ArgumentParser(description='Run CMS UL2016 post-VFP samples.', allow_abbrev=False)
    p.add_argument('samples', nargs='+', help='sample subdirectories inside --infolder')
    p.add_argument('--type', choices=('mc','data'), default='mc')
    p.add_argument('--from', dest='start', choices=STEPS, required=True, help='first step to execute')
    p.add_argument('--through', choices=STEPS, default='inputsomni', help='last step (default: inputsomni)')
    p.add_argument('--infolder', default=os.environ.get('INFOLDER'), help='input parent; default $INFOLDER')
    p.add_argument('--outfolder', default=os.environ.get('OUTFOLDER', str(REPO/'outputs')), help='output parent; default $OUTFOLDER or ./outputs')
    p.add_argument('--cmssw', default=os.environ.get('CMSSW_BASE', str(REPO.parent/'CMSSW_10_6_30')), help='CMSSW installation; default $CMSSW_BASE or sibling CMSSW_10_6_30')
    p.add_argument('--ranks', type=positive, help='default: allocated task count, otherwise 1')
    p.add_argument('--cpus-per-task', type=positive, default=int(os.environ.get('SLURM_CPUS_PER_TASK',1)))
    p.add_argument('--files-per-task', type=positive, default=1, help='MiniAOD files per task, within one sample')
    p.add_argument('--period', choices=('F','G','H'), help='data era if not identifiable from sample name')
    p.add_argument('--local', action='store_true', help='one worker without srun, including inside an allocation')
    p.add_argument('--cr', action='store_true', help='apply CR selection')
    p.add_argument('--overwrite', action='store_true', help='recompute existing outputs')
    p.add_argument('--dry-run', action='store_true', help='show tasks and commands without launching')
    return p


def relay_status(logs, ranks, stop):
    """Follow complete status lines only; leave detailed process output in logs."""
    offsets = [0] * ranks
    names = dict(zip(OUTPUTS.values(), STEPS))
    def drain():
        for rank in range(ranks):
            path = logs / ('rank_{}.out'.format(rank))
            if not path.exists():
                continue
            with path.open() as handle:
                handle.seek(offsets[rank])
                while True:
                    line = handle.readline()
                    if not line or not line.endswith('\n'):
                        break
                    offsets[rank] = handle.tell()
                    parts = line.split()
                    if len(parts) >= 3 and parts[0] in ('[RUN]', '[OK]', '[SKIP]', '[FAIL]'):
                        detail = ' '.join(parts[3:]) if parts[0] in ('[OK]', '[FAIL]') else ''
                        print('[rank {}] {} {} {} {}'.format(rank, parts[0], parts[1],
                              names.get(parts[2], parts[2]), detail).rstrip(), flush=True)
                    elif line.startswith('[ENV]'):
                        print('[rank {}] {}'.format(rank, line.rstrip()), flush=True)
    while not stop.is_set():
        drain()
        stop.wait(1)
    drain()


def main(argv=None):
    p = parser()
    a = p.parse_args(argv)
    if not a.infolder:
        p.error('provide --infolder or set INFOLDER')
    if STEPS.index(a.start) > STEPS.index(a.through):
        p.error('--through must not precede --from')
    if a.start != 'miniaod' and a.files_per_task != 1:
        p.error('--files-per-task applies only to --from miniaod')
    if a.local and a.ranks not in (None,1):
        p.error('--local requires one rank')
    if len(set(a.samples)) != len(a.samples):
        p.error('sample names must not be repeated')
    if any('/' in s or ',' in s or s in ('.','..') for s in a.samples):
        p.error('pass sample names, not paths; set their parent with --infolder')
    ranks = a.ranks or (1 if a.local else int(os.environ.get('SLURM_NTASKS',1)))
    use_srun = not a.local and bool(os.environ.get('SLURM_JOB_ID'))
    if ranks > 1 and not use_srun and not a.dry_run:
        p.error('multiple ranks require an active SLURM allocation')
    inp, out, cmssw = (Path(x).expanduser().resolve() for x in (a.infolder,a.outfolder,a.cmssw))
    specs = ['{},{},{},{}'.format(s,a.type,INPUTS[a.start],inp/s) for s in a.samples]
    # A dry run leaves no manifests or output directories behind.
    with tempfile.TemporaryDirectory(prefix='cms-plan-') as tmp:
        _, tasks = prepare_datasets(specs,Path(tmp)/'jobs.json',a.files_per_task)
        if a.dry_run:
            print('{} tasks | {} ranks | {} -> {}'.format(len(tasks),ranks,a.start,a.through))
            run_rank(Path(tmp)/'jobs.json',out,0,1,repo=REPO,through=OUTPUTS[a.through],dry_run=True,cr=a.cr,period=a.period)
            return 0
    if not (cmssw/'src').is_dir():
        p.error('CMSSW src directory not found: {}'.format(cmssw/'src'))
    run_parent=out/'.runs'; run_parent.mkdir(parents=True,exist_ok=True)
    run_dir=Path(tempfile.mkdtemp(prefix='run-',dir=str(run_parent)))
    manifest=run_dir/'jobs.json'
    manifest.write_text(json.dumps({'version':1,'tasks':tasks},indent=2)+'\n')
    logs=out/'logs'/run_dir.name; logs.mkdir(parents=True)
    worker=['bash',str(REPO/'cms_od'/'worker.sh'),str(manifest),str(out),'--through',OUTPUTS[a.through]]
    if not use_srun:
        worker += ['--rank','0','--nranks','1']
    for flag, enabled in [('--cr',a.cr),('--overwrite',a.overwrite)]:
        if enabled:
            worker.append(flag)
    if a.period:
        worker += ['--period',a.period]
    os_release=Path('/etc/os-release')
    inside_el7=os_release.is_file() and any(line.strip('"').startswith('7') for line in
        [x.split('=',1)[1] for x in os_release.read_text().splitlines() if x.startswith('VERSION_ID=')])
    if use_srun or not (inside_el7 and Path('/cvmfs/cms.cern.ch/cmsset_default.sh').is_file()):
        worker=['shifter','--image=zlmarshall/atlas-grid-centos7:20211123','--module=cvmfs']+worker
    cmd=worker
    if use_srun:
        cmd=['srun','-u','--cpu-bind=cores','-n',str(ranks),'--cpus-per-task='+str(a.cpus_per_task),
             '--export=ALL','--output='+str(logs/'rank_%t.out'),'--error='+str(logs/'rank_%t.err')]+worker
    env=dict(os.environ,CMSSW_BASE=str(cmssw),SCRAM_ARCH='slc7_amd64_gcc700',
             CMS_OD_CPUS_PER_TASK=str(a.cpus_per_task),
             SLURM_CPUS_PER_TASK=str(a.cpus_per_task),PYTHONUNBUFFERED='1',
             OMP_PROC_BIND='spread',OMP_PLACES='threads',OMP_NUM_THREADS=str(a.cpus_per_task))
    print('Samples: {}\nTasks: {} | Ranks: {} | Steps: {} -> {}'.format(', '.join(a.samples),len(tasks),ranks,a.start,a.through),flush=True)
    print('Logs: {}\nLaunch: {}'.format(logs,' '.join(shlex.quote(x) for x in cmd)),flush=True)
    print('CPUs per rank: {}'.format(a.cpus_per_task), flush=True)
    start=time.monotonic()
    stop=threading.Event()
    monitor=threading.Thread(target=relay_status,args=(logs,ranks,stop),daemon=True)
    monitor.start()
    try:
        if use_srun:
            result=subprocess.run(cmd,env=env)
        else:
            with (logs/'rank_0.out').open('w') as stdout, (logs/'rank_0.err').open('w') as stderr:
                result=subprocess.run(cmd,env=env,stdout=stdout,stderr=stderr)
    finally:
        stop.set()
        monitor.join()
    if result.returncode:
        print('FAILED: worker launch exited with status {}. See {}'.format(result.returncode,logs),file=sys.stderr)
        return result.returncode if result.returncode > 0 else 1
    summarize(manifest,out,ranks,OUTPUTS[a.through],int(time.monotonic()-start),logs)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError,OSError) as exc:
        print('ERROR: {}'.format(exc),file=sys.stderr)
        sys.exit(1)
