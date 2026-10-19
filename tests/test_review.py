import os
import subprocess
from pathlib import Path
import h5py
import numpy as np
import pytest
from cms_od.distributed import run_task, paths_for_task, prepare_datasets
from test_physics import make_input
from preprocess_aspen_dijet import select_dijet_indices
REPO = Path(__file__).resolve().parents[1]


def test_full_event_identity():
    event = np.array([[1,1,10], [1,1,10], [2,1,10], [2,1,10]])
    assert select_dijet_indices(event, np.array([500,600,700,800])).tolist() == [1,0,3,2]


def test_cr_restart_and_identity(tmp_path):
    src=tmp_path/'input.h5'; make_input(src)
    task={'id':'ZZ_00000','sample':'ZZ','type':'mc','source':'h5','files':[str(src)]}
    out=tmp_path/'out'
    run_task(task,out,REPO)
    dst=paths_for_task(task,out)['preprocess']; before=dst.stat().st_mtime_ns
    run_task(task,out,REPO)
    assert dst.stat().st_mtime_ns == before
    run_task(task,out,REPO,cr=True)
    with h5py.File(dst) as f:
        assert len(f['data']) == 5
        assert f['event_info'].shape == (5,3)
        assert f.attrs['cr'] == 1
        assert np.all(f['global'][:,4] == 1)
    dst.with_name(dst.name+'.complete.json').unlink()
    before=dst.stat().st_mtime_ns
    run_task(task,out,REPO,cr=True)
    assert dst.stat().st_mtime_ns != before


def test_sample_cut_independent_of_chunk_name(tmp_path):
    src=tmp_path/'input.h5'; make_input(src)
    with h5py.File(src,'r+') as f:
        f['jet_kinematics'][3,0]=350
        f['jet_kinematics'][1,0]=350
    task={'id':'chunk','sample':'JetHTH','type':'data','source':'h5','files':[str(src)]}
    run_task(task,tmp_path/'out',REPO)
    with h5py.File(paths_for_task(task,tmp_path/'out')['preprocess']) as f:
        assert len(f['data']) == 0


def test_era_and_cr_forwarding(tmp_path):
    task={'id':'data','sample':'JetHTG','type':'data','source':'pfnano','files':[str(tmp_path/'file_list.root')]}
    commands=run_task(task,tmp_path/'out',REPO,dry_run=True,cr=True)
    assert commands[0][1][-2:] == ['--period','G']
    assert commands[1][1][-2:] == ['--cr','1']
    assert commands[2][1][-1] == '--cr'
    task['sample']='JetHTE'
    with pytest.raises(ValueError,match='post-VFP'):
        run_task(task,tmp_path/'out',REPO,dry_run=True)


def test_discover_own_outputs(tmp_path):
    inp=tmp_path/'ZZ'; (inp/'corrected').mkdir(parents=True)
    (inp/'corrected'/'ZZ_00000.root').touch()
    _,tasks=prepare_datasets(['ZZ,mc,corrected,'+str(inp)],tmp_path/'jobs.json')
    assert len(tasks)==1


def test_conflicting_h5_cr_metadata(tmp_path):
    src=tmp_path/'input.h5'; make_input(src)
    with h5py.File(src,'a') as f:
        f.attrs['cr']=0
    task={'id':'chunk','sample':'ZZ','type':'mc','source':'h5','files':[str(src)]}
    with pytest.raises(subprocess.CalledProcessError):
        run_task(task,tmp_path/'out',REPO,cr=True)
    assert not paths_for_task(task,tmp_path/'out')['preprocess'].with_suffix('.h5.complete.json').exists()


def test_nominal_pt_threshold_migrations():
    # Exercise the actual production selection expressions without requiring ROOT.
    import ast
    from types import SimpleNamespace
    source=ast.parse((REPO/'workflow'/'H5_maker.py').read_text())
    ak4=next(n for n in source.body if isinstance(n,ast.FunctionDef) and n.name=='match_ak4jet')
    ak8=next(n for n in source.body if isinstance(n,ast.FunctionDef) and n.name=='NanoReader')
    for func,threshold in [(ak4,40),(ak8,300)]:
        condition=next(n.test for n in ast.walk(func) if isinstance(n,ast.If)
                       and isinstance(n.test,ast.BoolOp)
                       and any(isinstance(x,ast.Attribute) and x.attr=='jetId' for x in ast.walk(n.test)))
        code=compile(ast.Expression(condition),'<jet-selection>','eval')
        jet=SimpleNamespace(pt=threshold-1,pt_nom=threshold+1,jetId=6,eta=0,btagDeepFlavB=1)
        assert eval(code,{'jet':jet,'jet_min_pt':300})
        jet.pt,jet.pt_nom=threshold+1,threshold-1
        assert not eval(code,{'jet':jet,'jet_min_pt':300})


def test_infinite_uncertainty_converts_to_finite_ai(tmp_path):
    from cms_od.validation import validate_h5
    src=tmp_path/'input.h5'; make_input(src)
    with h5py.File(src,'a') as f:
        f['PFCands'][2,0,5]=np.inf
        f['PFCands'][2,0,7]=np.inf
    with pytest.warns(RuntimeWarning, match='d0Err=1, dzErr=1'):
        assert validate_h5(src)==6
    task={'id':'ZZ_00000','sample':'ZZ','type':'mc','source':'h5','files':[str(src)]}
    run_task(task,tmp_path/'out',REPO)
    dst=paths_for_task(task,tmp_path/'out')['preprocess']
    assert validate_h5(dst,ai=True)==2
    with h5py.File(dst) as f:
        assert f['data'][0,0,6]==1
        assert f['data'][0,0,8]==1


@pytest.mark.parametrize('column,value',[(0,np.inf),(7,np.nan),(7,-np.inf),(4,np.inf)])
def test_other_nonfinite_values_still_fail(tmp_path,column,value):
    from cms_od.validation import validate_h5
    src=tmp_path/'input.h5'; make_input(src)
    with h5py.File(src,'a') as f:
        f['PFCands'][2,0,column]=value
    with pytest.raises(ValueError,match='Nonfinite'):
        validate_h5(src)
