import json
import subprocess
from pathlib import Path
import h5py
import pytest
from cms_od.distributed import run_task
from test_physics import make_input
from cms_od.summary import summarize
REPO=Path(__file__).resolve().parents[1]


def test_summary_new_skipped_empty_and_idle_rank(tmp_path,capsys):
    tasks=[]
    out=tmp_path/'out'; (out/'logs').mkdir(parents=True)
    for sample in ['ZZ','WW']:
        src=tmp_path/(sample+'.h5'); make_input(src)
        if sample=='WW':
            with h5py.File(src,'a') as f:
                f['jet_kinematics'][:,0]=0
        tasks.append({'id':sample+'_00000','sample':sample,'type':'mc','source':'h5','files':[str(src)]})
    run_task(tasks[0],out,REPO)
    capsys.readouterr()
    for rank,task in enumerate(tasks):
        run_task(task,out,REPO)
        (out/'logs'/('rank_{}.out'.format(rank))).write_text(capsys.readouterr().out)
    (out/'logs'/'rank_2.out').write_text('Rank 2/3: 0 tasks\n')
    manifest=tmp_path/'jobs.json'; manifest.write_text(json.dumps({'tasks':tasks}))
    result=summarize(manifest,out,3,'preprocess',42,out/'logs')
    assert 'SUCCESS' in result
    assert '1 completed, 1 skipped' in result
    assert 'Files: 2 | Total jets: 2' in result
    assert (out/'logs'/'summary.txt').read_text()==result
    (out/'logs'/'rank_1.out').write_text('')
    with pytest.raises(ValueError,match='Missing stage results'):
        summarize(manifest,out,3,'preprocess',42,out/'logs')
