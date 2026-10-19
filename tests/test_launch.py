import json
import os
from pathlib import Path
import subprocess
import pytest
from cms_od import launch
from test_physics import make_input

REPO=Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('step,filename,stage',[
    ('miniaod','raw.root','pfnano'),('postprocess','file_list.root','corrected'),
    ('h5maker','file_list_postprocessed.root','h5'),('inputsomni','input.h5','preprocess')])
def test_steps_and_dry_run(tmp_path,step,filename,stage):
    inp=tmp_path/'inputs'/'ZZ'; inp.mkdir(parents=True); (inp/filename).touch()
    out=tmp_path/'out'
    result=subprocess.run(['bash',str(REPO/'run.sh'),'ZZ','--infolder',str(inp.parent),
        '--outfolder',str(out),'--from',step,'--cr','--dry-run'],
        universal_newlines=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    assert result.returncode==0,result.stderr
    plans=[line for line in result.stdout.splitlines() if '[PLAN]' in line]
    assert plans[0].split()[2]==stage
    assert '--cr' in plans[-1]
    assert not out.exists()


@pytest.mark.parametrize('option,value',[
    ('--from','nanoaod'),('--from','pfnano'),('--from','corrected'),('--from','h5'),
    ('--start','h5maker'),('--input-root','/tmp'),('--output','/tmp'),
    ('--mode','local'),('--jec-year','2016'),('--through','preprocess')])
def test_old_options_rejected(option,value):
    args=['ZZ','--from','h5maker']
    if option=='--from':args=['ZZ']
    with pytest.raises(SystemExit) as exc:
        launch.parser().parse_args(args+[option,value])
    assert exc.value.code==2


def test_local_real_h5_run_and_resume(tmp_path,monkeypatch,capsys):
    # Replace only container entry; exercise the actual worker module and summary.
    inp=tmp_path/'inputs'/'ZZ';inp.mkdir(parents=True);make_input(inp/'chunk.h5')
    cmssw=tmp_path/'CMSSW';(cmssw/'src').mkdir(parents=True)
    repo=tmp_path/'repo';(repo/'cms_od').mkdir(parents=True)
    (repo/'cms_od'/'worker.sh').write_text('''#!/bin/bash
manifest=$1; output=$2; shift 2
exec python3 -m cms_od.distributed --manifest "$manifest" --output-dir "$output" "$@"
''')
    bins=tmp_path/'bin';bins.mkdir()
    shifter=bins/'shifter'
    shifter.write_text('#!/bin/bash\nshift 2\nexec "$@"\n');shifter.chmod(0o755)
    monkeypatch.setenv('PATH',str(bins)+':'+os.environ['PATH'])
    monkeypatch.setenv('PYTHONPATH',str(REPO))
    monkeypatch.setattr(launch,'REPO',repo)
    args=['ZZ','--from','inputsomni','--infolder',str(inp.parent),'--outfolder',str(tmp_path/'out'),
          '--cmssw',str(cmssw),'--local']
    assert launch.main(args)==0
    assert '1 completed, 0 skipped' in capsys.readouterr().out
    assert launch.main(args)==0
    assert '0 completed, 1 skipped' in capsys.readouterr().out
    reports=list((tmp_path/'out'/'logs').glob('*/summary.txt'))
    assert len(reports)==2
    (repo/'cms_od'/'worker.sh').write_text('#!/bin/bash\nexit 7\n')
    assert launch.main(args)==7
    assert 'SUCCESS' not in capsys.readouterr().out


def test_srun_uses_allocation_and_returns_failure(tmp_path,monkeypatch,capsys):
    inp=tmp_path/'inputs'/'ZZ';inp.mkdir(parents=True);(inp/'file_list_postprocessed.root').touch()
    (tmp_path/'CMSSW'/'src').mkdir(parents=True)
    monkeypatch.setenv('SLURM_JOB_ID','123');monkeypatch.setenv('SLURM_NTASKS','64')
    monkeypatch.setenv('SLURM_CPUS_PER_TASK','16')
    seen=[]
    def fail(cmd,**kwargs):
        seen.append((cmd,kwargs))
        return subprocess.CompletedProcess(cmd,3)
    monkeypatch.setattr(launch.subprocess,'run',fail)
    result=launch.main(['ZZ','--from','h5maker','--infolder',str(inp.parent),
        '--outfolder',str(tmp_path/'out'),'--cmssw',str(tmp_path/'CMSSW')])
    assert result==3
    cmd,kw=seen[0]
    assert cmd[:6]==['srun','-u','--cpu-bind=cores','-n','64','--cpus-per-task=16']
    assert kw['env']['OMP_NUM_THREADS']=='16'
    assert 'shifter' in cmd
    assert 'SUCCESS' not in capsys.readouterr().out


def test_live_status_before_worker_exits(tmp_path, monkeypatch, capsys):
    import threading
    logs=tmp_path
    stop=threading.Event()
    printed=threading.Event()
    import builtins
    original=builtins.print
    def capture(*args, **kwargs):
        original(*args, **kwargs)
        if args and '[OK]' in str(args[0]):
            printed.set()
    monkeypatch.setattr(builtins,'print',capture)
    path=logs/'rank_0.out'
    path.write_text('verbose physics output\n[OK] ZZ_00000 corrected entries=12')
    monitor=threading.Thread(target=launch.relay_status,args=(logs,2,stop))
    monitor.start()
    try:
        assert not printed.wait(0.1)
        with path.open('a') as f: f.write('\n')
        assert printed.wait(3)
    finally:
        stop.set(); monitor.join()
    output=capsys.readouterr().out
    assert output.count('[OK]')==1
    assert '[rank 0] [OK] ZZ_00000 postprocess entries=12' in output
    assert 'verbose' not in output


def test_cpu_override_reaches_launcher_environment(tmp_path,monkeypatch):
    inp=tmp_path/'inputs'/'ZZ'; inp.mkdir(parents=True)
    (inp/'file_list.root').touch()
    (tmp_path/'CMSSW'/'src').mkdir(parents=True)
    monkeypatch.setenv('SLURM_JOB_ID','123')
    monkeypatch.setenv('SLURM_CPUS_PER_TASK','16')
    def check(cmd,**kwargs):
        assert '--cpus-per-task=4' in cmd
        assert '--export=ALL' in cmd
        for key in ('CMS_OD_CPUS_PER_TASK','SLURM_CPUS_PER_TASK','OMP_NUM_THREADS'):
            assert kwargs['env'][key]=='4'
        return subprocess.CompletedProcess(cmd,3)
    monkeypatch.setattr(launch.subprocess,'run',check)
    assert launch.main(['ZZ','--from','postprocess','--infolder',str(inp.parent),
        '--outfolder',str(tmp_path/'out'),'--cmssw',str(tmp_path/'CMSSW'),
        '--cpus-per-task','4'])==3


def test_worker_restores_cpu_count_after_cmssw_setup(tmp_path):
    cmssw=tmp_path/'CMSSW'; (cmssw/'src').mkdir(parents=True)
    setup=tmp_path/'cmsset.sh'; setup.write_text('export OMP_NUM_THREADS=99\n')
    bins=tmp_path/'bin'; bins.mkdir()
    (bins/'scram').write_text('#!/bin/bash\necho "export OMP_NUM_THREADS=77"\n')
    (bins/'python3').write_text('#!/bin/bash\necho "THREADS=$OMP_NUM_THREADS SLURM=$SLURM_CPUS_PER_TASK BLAS=$OPENBLAS_NUM_THREADS"\n')
    for path in bins.iterdir():path.chmod(0o755)
    worker=tmp_path/'worker.sh'
    worker.write_text((REPO/'cms_od'/'worker.sh').read_text().replace('/cvmfs/cms.cern.ch/cmsset_default.sh',str(setup)))
    env=dict(os.environ,PATH=str(bins)+':'+os.environ['PATH'],CMSSW_BASE=str(cmssw),
             CMS_OD_CPUS_PER_TASK='4',SLURM_CPUS_PER_TASK='16')
    result=subprocess.run(['bash',str(worker),'manifest','out'],env=env,
                          stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
    assert result.returncode==0,result.stderr
    assert 'CPUs/task=4 OMP_NUM_THREADS=4' in result.stdout
    assert 'THREADS=4 SLURM=4 BLAS=4' in result.stdout
