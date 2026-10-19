"""Artifact validation; intentionally independent of CMSSW."""
from pathlib import Path
import subprocess
import json
import warnings

INTERMEDIATE = {'PFCands': (150, 11), 'jet_kinematics': (4,),
                'jet_tagging': (9,), 'jet_systematics': (16,),
                'event_info': (3,), 'trigger_info': (2,),
                'lepton_info': (2,), 'weight_info': (17,), 'match_info': (1,)}
AI = {'data': (150, 9), 'global': (52,), 'pid': ()}


def validate_h5(path, ai=False, require_nonempty=False):
    import numpy as np
    import h5py
    schema = AI if ai else INTERMEDIATE
    with h5py.File(path, 'r') as f:
        missing = set(schema) - set(f)
        if missing:
            raise ValueError('Missing HDF5 keys: {}'.format(sorted(missing)))
        lengths = set()
        clipped_infinities = [0, 0]
        dz_infinities = [0, 0]
        for key, trailing in schema.items():
            ds = f[key]
            if ds.ndim != len(trailing) + 1 or tuple(ds.shape[1:]) != trailing:
                raise ValueError('{}: wrong shape {}'.format(key, ds.shape))
            lengths.add(len(ds))
            # Read chunks rather than allocating the full dataset
            for start in range(0, len(ds), 2048):
                values = ds[start:start+2048]
                bad = ~np.isfinite(values)
                if not ai and key == 'PFCands':
                    # Existing AI clipping maps +inf errors to +1.
                    for i, column in enumerate((5, 7)):
                        allowed = np.isposinf(values[:, :, column])
                        clipped_infinities[i] += int(allowed.sum())
                        bad[:, :, column] &= ~allowed
                    # dz is signed; existing tanh maps either infinity to +/-1.
                    dz = values[:, :, 6]
                    dz_infinities[0] += int(np.isposinf(dz).sum())
                    dz_infinities[1] += int(np.isneginf(dz).sum())
                    bad[:, :, 6] &= ~np.isinf(dz)
                if bad.any():
                    index = tuple(int(i) for i in np.argwhere(bad)[0])
                    location = (start + index[0],) + index[1:]
                    raise ValueError('Nonfinite values in {}: index={}, value={} '
                                     '(outside allowed tracking infinities)'.format(
                                         key, location, values[index]))
        if any(clipped_infinities):
            warnings.warn('{}: +inf tracking uncertainties: d0Err={}, dzErr={}; '
                          'existing AI clipping maps these to +1'.format(
                              path, *clipped_infinities), RuntimeWarning)
        if any(dz_infinities):
            warnings.warn('{}: infinite dz: +inf={}, -inf={}; existing AI tanh '
                          'maps these to +1/-1'.format(path, *dz_infinities), RuntimeWarning)
        if len(lengths) != 1:
            raise ValueError('Dataset first-dimension mismatch')
        n = lengths.pop()
        if require_nonempty and not n:
            raise ValueError('Empty output')
        if ai:
            if (f['pid'][:] != 200).any():
                raise ValueError('Unexpected dataset pid')
            for start in range(0, n, 2048):
                ids = f['data'][start:start+2048, :, 4]
                if ((ids < 0) | (ids > 8) | (ids != np.floor(ids))).any():
                    raise ValueError('Invalid particle IDs')
    return n


def validate_root(path, stage):
    required = {'FatJet_pt', 'FatJet_eta', 'FatJet_phi', 'FatJet_msoftdrop',
                'PFCands_pt', 'FatJetPFCands_jetIdx'}
    if stage == 'corrected':
        required |= {'FatJet_pt_nom', 'FatJet_msoftdrop_nom'}
    try:
        import uproot
    except ImportError:
        # ROOT may only be available in the CMSSW Python 2 environment.
        script = ("import ROOT,json,sys;f=ROOT.TFile.Open(sys.argv[1]);"
                  "assert f and not f.IsZombie();t=f.Get('Events');assert t;"
                  "print(json.dumps({'n':int(t.GetEntries()),"
                  "'branches':[b.GetName() for b in t.GetListOfBranches()]}))")
        result = subprocess.check_output(['python', '-c', script, str(path)],
                                         universal_newlines=True)
        info = json.loads(result.strip().splitlines()[-1])
        keys, n = set(info['branches']), info['n']
    else:
        with uproot.open(path) as f:
            if 'Events' not in f:
                raise ValueError('Missing Events tree')
            keys = set(f['Events'].keys())
            n = f['Events'].num_entries
    missing = required - keys
    if missing:
        raise ValueError('Missing {} branches: {}'.format(stage, sorted(missing)))
    return n


def validate(path, stage, nonempty=False):
    p = Path(path)
    if not p.is_file() or p.stat().st_size == 0:
        raise ValueError('Missing/empty file: {}'.format(p))
    if stage in ('pfnano', 'corrected'):
        n = validate_root(p, stage)
        if nonempty and not n:
            raise ValueError('Empty Events tree')
        return n
    return validate_h5(p, ai=(stage == 'preprocess'), require_nonempty=nonempty)
