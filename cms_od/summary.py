"""Print this launch's results using completion records and rank logs (Python 3.6)."""
import json
from pathlib import Path
import re

from .distributed import NEXT, paths_for_task


def summarize(manifest, output, ranks, through, elapsed, logs):
    manifest, output, logs = Path(manifest), Path(output).resolve(), Path(logs)
    tasks = json.loads(manifest.read_text())['tasks']
    expected = set()
    samples = {}
    for task in tasks:
        stages = NEXT[task['source']]
        if through not in stages:
            raise ValueError('Stop stage incompatible with input')
        expected.update((task['id'], s) for s in stages[:stages.index(through)+1])
        samples.setdefault(task['sample'], []).append(task)
    actions = {}
    for rank in range(ranks):
        path = logs/('rank_{}.out'.format(rank))
        for line in path.read_text().splitlines():
            match = re.match(r'^\[(OK|SKIP)\] (\S+) (\S+) ', line)
            if match:
                action, task_id, stage = match.groups()
                key = (task_id, stage)
                if key in expected:
                    if key in actions:
                        raise ValueError('Duplicate completion log: {}'.format(key))
                    actions[key] = action
    if set(actions) != expected:
        raise ValueError('Missing stage results: {}'.format(sorted(expected-set(actions))))
    counts = {}
    for task in tasks:
        paths = paths_for_task(task, output)
        for stage in NEXT[task['source']]:
            if (task['id'], stage) not in expected:
                continue
            path = paths[stage]
            record = json.loads(path.with_name(path.name+'.complete.json').read_text())
            stat = path.stat()
            if record.get('task') != task or record.get('stage') != stage:
                raise ValueError('Completion record mismatch: {}'.format(path))
            if record.get('output_stamp') != [str(path), stat.st_size, stat.st_mtime_ns]:
                raise ValueError('Output changed since validation: {}'.format(path))
            counts[(task['id'],stage)] = int(record['events_or_jets'])
    lines = ['', 'SUCCESS: workflow completed',
             'Tasks: {} | Ranks: {} | Elapsed: {} s'.format(len(tasks),ranks,elapsed),
             'Stage results: {} completed, {} skipped (validated existing outputs)'.format(
                 sum(v=='OK' for v in actions.values()),sum(v=='SKIP' for v in actions.values())), '']
    width = max([len('Sample')] + [len(s) for s in samples])
    unit = 'Jets' if through in ('h5','preprocess') else 'Events'
    lines.append('{:<{w}}  {:>5}  {:>5}  {:>7}  {:>12}  {:>5}'.format(
        'Sample','Files','New','Reused',unit,'Empty',w=width))
    for sample, group in samples.items():
        keys = [(t['id'],through) for t in group]
        lines.append('{:<{w}}  {:>5}  {:>5}  {:>7}  {:>12,}  {:>5}'.format(
            sample,len(keys),sum(actions[k]=='OK' for k in keys),
            sum(actions[k]=='SKIP' for k in keys),sum(counts[k] for k in keys),
            sum(counts[k]==0 for k in keys),w=width))
    lines += ['', 'Final stage: {} | Files: {} | Total {}: {:,}'.format(
        through,len(tasks),unit.lower(),sum(counts[(t['id'],through)] for t in tasks)),
        'Output: {}'.format(output), 'Rank logs: {}'.format(logs)]
    report = logs/'summary.txt'
    lines.append('Summary saved: {}'.format(report))
    text = '\n'.join(lines)+'\n'
    report.write_text(text)
    print(text, end='')
    return text
