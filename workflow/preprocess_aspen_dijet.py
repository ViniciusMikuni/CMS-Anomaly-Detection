"""Convert AK8 HDF5 files to fixed-schema AI datasets for dijet studies."""
import argparse
from pathlib import Path
import h5py
import numpy as np

PID_IDS = np.array([-11, 11, -13, 13, 211, -211, 130, 22, 0], dtype=np.int32)
PID_INDEX = {int(pid): i for i, pid in enumerate(PID_IDS)}


def select_dijet_indices(event, pt, cr=0):
    """Return indices for two highest-pT jets per contiguous event, or all jets in CR."""
    if cr:
        return np.arange(len(event), dtype=np.int64)
    if len(event) != len(pt):
        raise ValueError('Event IDs and jet pT must have equal length')
    if not len(event):
        return np.array([], dtype=np.int64)
    changed = event[1:] != event[:-1]
    if event.ndim == 2:
        changed = np.any(changed, axis=1)
    starts = np.r_[0, np.flatnonzero(changed) + 1]
    ends = np.r_[starts[1:], len(event)]
    # The H5 maker processes a single event at a time; repeated noncontiguous IDs
    # would break this contract and are rejected instead of silently mispairing.
    if len(np.unique(event[starts], axis=0)) != len(starts):
        raise ValueError('Event IDs repeat in noncontiguous blocks; use full event IDs')
    pairs = []
    for start, end in zip(starts, ends):
        if end - start >= 2:
            indices = np.arange(start, end)
            # stable descending order when two jets have identical pT
            pairs.extend(indices[np.argsort(-pt[start:end], kind='mergesort')[:2]])
    return np.asarray(pairs, dtype=np.int64)


def calculate_mass(jets, cr=0):
    """Append invariant mass of jet four-vectors using corrected soft-drop mass."""
    if cr:
        return np.column_stack((jets, np.ones(len(jets))))
    if len(jets) % 2:
        raise ValueError('Dijet input must contain an even number of jets')
    j = jets.astype(np.float64).reshape(-1, 2, jets.shape[-1])
    mass = j[:, :, 3]
    pt, eta, phi = j[:, :, 0], j[:, :, 1], j[:, :, 2]
    px = (pt * np.cos(phi)).sum(axis=1)
    py = (pt * np.sin(phi)).sum(axis=1)
    pz = (pt * np.sinh(eta)).sum(axis=1)
    energy = np.sqrt(np.maximum(mass**2 + (pt * np.cosh(eta))**2, 0)).sum(axis=1)
    m2 = energy**2 - px**2 - py**2 - pz**2
    if np.any(m2 < -1e-6 * np.maximum(energy**2, 1)):
        raise ValueError('Substantially negative dijet mass squared')
    return np.column_stack((jets, np.repeat(np.sqrt(np.maximum(m2, 0)), 2)))


def encode_pid(pid):
    pid = np.asarray(pid).astype(np.int32).copy()
    for original, replacement in {321:211, 2212:211, -321:-211, -2212:-211,
                                  2112:130, -2112:130, 1:130, 2:130}.items():
        pid[pid == original] = replacement
    result = np.zeros(pid.shape, dtype=np.int32)
    for original, label in PID_INDEX.items():
        result[pid == original] = label
    unknown = np.unique(pid[~np.isin(pid, PID_IDS)])
    if unknown.size:
        raise ValueError('Unsupported particle IDs: {}'.format(unknown.tolist()))
    return result


def take_rows(dataset, indices):
    """Read arbitrary HDF5 rows, preserving order across old h5py versions.

    Use scalar row selections rather than fancy indexing, which fails for
    some numpy index arrays under CMSSW's h5py 2.9 build.
    """
    indices = np.asarray(indices, dtype=np.int64)
    if indices.ndim != 1:
        raise ValueError('Expected one-dimensional row indices')
    result = np.empty((len(indices),) + dataset.shape[1:], dtype=dataset.dtype)
    for out_i, source_i in enumerate(indices):
        result[out_i] = dataset[int(source_i)]
    return result


def clustering(data, output_file, sample, cr=0):
    if 'cr' in data.attrs and bool(data.attrs['cr']) != bool(cr):
        raise ValueError('Input HDF5 selection differs from --cr; restart at h5maker')
    pt_cut = 400 if 'JetHT' in sample else 300
    kin = data['jet_kinematics'][:]
    pt_indices = np.flatnonzero(kin[:, 0] > pt_cut)
    event = data['event_info'][:][pt_indices]
    idx = pt_indices[select_dijet_indices(event, kin[pt_indices, 0], cr)]
    print('Input jets: {}'.format(len(kin)))
    print('Jets passing pT > {} GeV: {}'.format(pt_cut, len(pt_indices)))
    if cr:
        print('Control-region jets retained: {}'.format(len(idx)))
    else:
        print('Dijet events retained: {}'.format(len(idx) // 2))
    print('Output jets: {}'.format(len(idx)))
    jets = kin[idx].copy()
    particles = take_rows(data['PFCands'], idx)
    jets = calculate_mass(jets, cr)
    components = [take_rows(data[key], idx) for key in ('jet_tagging', 'trigger_info', 'lepton_info',
                                               'jet_systematics', 'weight_info', 'match_info')]
    jets = np.concatenate([jets] + components, axis=-1)
    if jets.shape[1] != 52:
        raise ValueError('Expected 52 global features, got {}'.format(jets.shape[1]))

    px, py, pz, energy = (particles[:, :, i].astype(np.float64) for i in range(4))
    pt = np.hypot(px, py)
    eta = np.arcsinh(np.divide(pz, pt, out=np.zeros_like(pt), where=pt > 0))
    phi = np.arctan2(py, px)
    valid = energy > 0
    points = np.zeros((*pt.shape, 9), dtype=np.float32)
    points[:, :, 0] = eta - jets[:, None, 1]
    points[:, :, 1] = (phi - jets[:, None, 2] + np.pi) % (2 * np.pi) - np.pi
    points[:, :, 2] = np.log(pt, out=np.zeros_like(pt), where=pt > 0)
    points[:, :, 3] = np.log(energy, out=np.zeros_like(energy), where=energy > 0)
    points[:, :, 4] = encode_pid(particles[:, :, 9])
    points[:, :, 5] = np.tanh(particles[:, :, 4])
    points[:, :, 6] = np.clip(particles[:, :, 5], -1., 1.)
    points[:, :, 7] = np.tanh(particles[:, :, 6])
    points[:, :, 8] = np.clip(particles[:, :, 7], -1., 1.)
    points *= valid[:, :, None]
    jets[:, 0] = np.log(jets[:, 0], out=np.zeros(len(jets)), where=jets[:, 0] > 0)
    jets[:, 3] = np.log(jets[:, 3], out=np.zeros(len(jets)), where=jets[:, 3] > 0)
    if not np.isfinite(points).all() or not np.isfinite(jets).all():
        raise ValueError('Nonfinite AI output')
    output_file = Path(output_file)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with h5py.File(output_file, 'w') as f:
        f.create_dataset('data', data=points)
        f.create_dataset('global', data=jets)
        f.create_dataset('pid', data=np.full(len(idx), 200, dtype=np.float32))
        f.create_dataset('event_info', data=take_rows(data['event_info'], idx))
        f.attrs['cr'] = int(bool(cr))
    print('Output saved: {}'.format(output_file))
    return len(idx)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument('--cr', action='store_true')
    parser.add_argument('--sample', required=True)
    parser.add_argument('--input-file', required=True)
    parser.add_argument('--output-file', required=True)
    flags = parser.parse_args()
    with h5py.File(flags.input_file, 'r') as data:
        clustering(data, flags.output_file, flags.sample, cr=flags.cr)
