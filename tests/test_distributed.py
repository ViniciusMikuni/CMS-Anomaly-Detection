import json
import subprocess
from pathlib import Path
import pytest
from cms_od.distributed import prepare_datasets, run_rank, paths_for_task, run_task
from cms_od.validation import validate_h5
from test_physics import make_input


def test_multi_dataset_discovery_and_partition(tmp_path):
    a = tmp_path/'ZZ'; b=tmp_path/'QCD'
    for folder in [a/'part0',a/'part1', b/'part0']:
        folder.mkdir(parents=True)
        (folder/'file_list.root').write_bytes(b'root')
        (folder/'file_list_postprocessed.root').write_bytes(b'corrected')
    manifest, tasks = prepare_datasets([
        'ZZ,mc,pfnano,{}'.format(a), 'QCD,mc,corrected,{}'.format(b)],
        tmp_path/'manifest.json')
    assert len(tasks)==3
    assert len([t for t in tasks if t['sample']=='ZZ'])==2
    assert tasks[-1]['source']=='corrected'
    all_ids=[]
    for rank in range(4):
        assigned=run_rank(manifest,tmp_path/'output',rank,4,
                          repo=Path(__file__).parents[1],dry_run=True)
        all_ids+=assigned
    assert len(all_ids)==len(set(all_ids))==3


def test_existing_h5_to_ai_full_subprocess(tmp_path):
    src = tmp_path/'original'/'intermediate.h5'
    src.parent.mkdir()
    make_input(src)
    manifest, tasks=prepare_datasets(['ZZ,mc,h5,{}'.format(src)],tmp_path/'jobs.json')
    run_rank(manifest,tmp_path/'out',0,1,repo=Path(__file__).parents[1])
    dst=paths_for_task(tasks[0],tmp_path/'out')['preprocess']
    assert validate_h5(dst, ai=True)==2
    marker=dst.with_name(dst.name+'.complete.json')
    assert marker.exists()
    # A second run should skip completed output.
    assert run_rank(manifest,tmp_path/'out',0,1,repo=Path(__file__).parents[1])==[tasks[0]['id']]


def test_miniaod_filelist_and_dry_run(tmp_path):
    inp=tmp_path/'in';inp.mkdir()
    for i in range(5):
        (inp/'file_{}.root'.format(i)).touch()
    manifest,tasks=prepare_datasets(['signal,mc,miniaod,{}'.format(inp)],tmp_path/'manifest.json',2)
    assert [len(t['files']) for t in tasks]==[2,2,1]
    commands=run_task(tasks[0],tmp_path/'out',Path(__file__).parents[1],dry_run=True)
    assert [x[0] for x in commands]==['pfnano','corrected','h5','preprocess']
    assert 'inputFiles=' in ' '.join(commands[0][1])
    assert '--sample' in commands[2][1]


def test_invalid_input_and_failure_reporting(tmp_path,monkeypatch):
    with pytest.raises(ValueError,match='No pfnano'):
        inp=tmp_path/'empty'; inp.mkdir()
        prepare_datasets(['ZZ,mc,pfnano,{}'.format(inp)],tmp_path/'manifest.json')
    src=tmp_path/'input.h5'; make_input(src)
    manifest,tasks=prepare_datasets(['ZZ,mc,h5,{}'.format(src)],tmp_path/'manifest.json')
    def bad(*a,**kw):
        raise subprocess.CalledProcessError(2,['mock'])
    monkeypatch.setattr('cms_od.distributed.subprocess.run',bad)
    with pytest.raises(RuntimeError,match='Rank 0 failed'):
        run_rank(manifest,tmp_path/'out',0,1,repo=Path(__file__).parents[1])

def test_list_of_existing_pfnano_files(tmp_path):
    root=tmp_path/'data';root.mkdir()
    for i in range(2):
        (root/'{}.root'.format(i)).write_bytes(b'data')
    lst=root/'files.txt';lst.write_text('0.root\n1.root\n')
    manifest,tasks=prepare_datasets(['Data,data,pfnano,{}'.format(lst)],tmp_path/'manifest.json')
    assert len(tasks)==2
    assert all(Path(t['files'][0]).exists() for t in tasks)
