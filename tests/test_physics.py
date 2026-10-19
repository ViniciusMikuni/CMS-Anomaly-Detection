import sys
from pathlib import Path
import h5py
import numpy as np
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'workflow'))
from preprocess_aspen_dijet import (select_dijet_indices, calculate_mass, encode_pid, clustering)


def test_pairing():
    event = np.array([10, 20, 20, 30, 30, 30, 40, 40, 40, 40])
    pt = np.array([800, 310, 510, 310, 700, 400, 600, 900, 450, 300])
    np.testing.assert_array_equal(select_dijet_indices(event, pt), [2, 1, 4, 5, 7, 6])
    np.testing.assert_array_equal(select_dijet_indices(event, pt, cr=1), np.arange(10))
    with pytest.raises(ValueError):
        select_dijet_indices(np.array([1, 2, 1]), np.array([400, 400, 400]))


def test_mass():
    # Back-to-back jets with zero soft-drop mass give invariant mass 1000.
    jets = np.array([[500., 0., 0., 0.], [500., 0., np.pi, 0.]])
    np.testing.assert_allclose(calculate_mass(jets)[:, -1], [1000, 1000], rtol=1e-6)
    assert np.all(calculate_mass(np.column_stack((jets[:, :3], [100., 100.])))[:, -1] > 1000)


def test_pid_fixed():
    expected = np.arange(9)
    np.testing.assert_array_equal(encode_pid(np.array([-11,11,-13,13,211,-211,130,22,0])), expected)
    np.testing.assert_array_equal(encode_pid(np.array([321,-2212,2112])), [4,5,6])
    with pytest.raises(ValueError):
        encode_pid(np.array([999]))


def make_input(path):
    # Event 1 has one jet (dropped); event 2 has three jets (keep pT 700, 500)
    # event 3 has exactly two jets, one below threshold (dropped).
    pts = [500, 400, 700, 500, 600, 250]
    n = len(pts)
    with h5py.File(path, 'w') as f:
        f['event_info'] = np.array([[1, 1, e] for e in [1, 2, 2, 2, 3, 3]])
        f['jet_kinematics'] = np.array([[pt, 0., i*np.pi/3, 80.] for i, pt in enumerate(pts)], dtype='f4')
        pc = np.zeros((n, 150, 11), dtype='f4')
        pc[:, 0, :] = np.array([10, 0, 0, 10, 0, 0, 0, 0, 1, 211, 1])
        f['PFCands'] = pc
        for name, width in [('jet_tagging',9),('trigger_info',2),('lepton_info',2),('jet_systematics',16),('weight_info',17),('match_info',1)]:
            f[name] = np.ones((n, width), dtype='f4')


def test_pipeline(tmp_path):
    inp = tmp_path / 'chunk.h5'
    make_input(inp)
    with h5py.File(inp, 'r') as f:
        n = clustering(f, tmp_path/'outputs'/('omni_'+inp.name), 'ZZ')
    assert n == 2
    with h5py.File(tmp_path / 'outputs' / 'omni_chunk.h5', 'r') as f:
        assert f['data'].shape == (2, 150, 9)
        assert f['global'].shape == (2, 52)
        assert f['pid'].shape == (2,)
        assert np.all(f['pid'][:] == 200)
        assert np.all(f['data'][:, 0, 4] == 4)
        assert np.all(f['data'][:, 1:, :] == 0)
        assert np.all(np.isfinite(f['global'][:]))
        np.testing.assert_allclose(f['global'][:2, 4], f['global'][0, 4])


def test_softdrop_mass_from_kinematics(tmp_path):
    inp = tmp_path / 'legacy.h5'
    make_input(inp)
    with h5py.File(inp, 'r') as f:
        assert 'jet_mass' not in f
        assert clustering(f, tmp_path/'outputs'/('omni_'+inp.name), 'ZZ') == 2
    with h5py.File(tmp_path / 'outputs' / 'omni_legacy.h5', 'r') as f:
        assert np.all(np.isfinite(f['global'][:, 4]))
