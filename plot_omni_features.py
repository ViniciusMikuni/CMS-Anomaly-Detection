#!/usr/bin/env python3
"""Quick multipage PDF diagnostic for preprocess_aspen_dijet.py HDF5 outputs.

Usage:
    python3 plot_omni_features.py --input-file "$INPUT_DIR/omni_test.h5"

The PDF is written to the current working directory by default.
Requires numpy, h5py, matplotlib (Python 3). No ROOT required.
"""
import argparse
from pathlib import Path

import h5py
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_pdf import PdfPages

PARTICLE_NAMES = [
    r'$\Delta\eta$', r'$\Delta\phi$', r'$\log p_T$', r'$\log E$',
    'Particle ID (encoded)', r'$\tanh(d_0)$', r'$d_0$ error (clipped)',
    r'$\tanh(d_z)$', r'$d_z$ error (clipped)',
]
PID_NAMES = ['pad', 'e+', 'e-', 'mu+', 'mu-', 'h+', 'h-', 'neutral', 'photon']
KIN_NAMES = [r'$\log p_T$ (jet)', r'$\eta$ (jet)', r'$\phi$ (jet)',
             r'$\log m_{SD}$ (jet)', r'$m_{jj}$ (soft-drop mass based)']
TAG_NAMES = ['nConstituents', 'tau1', 'tau2', 'tau3', 'tau4',
             'DeepCSV b tag', 'ParticleNet Xbb', 'soft-drop z', 'soft-drop theta']
TRIGGER_NAMES = ['Jet trigger', 'Muon trigger']
LEPTON_NAMES = ['N selected muons', 'N selected electrons']
SYS_NAMES = [
    'JES up: pt', 'JES up: soft-drop mass', 'JES down: pt', 'JES down: soft-drop mass',
    'JER up: pt', 'JER up: soft-drop mass', 'JER down: pt', 'JER down: soft-drop mass',
    'JMS up: pt', 'JMS up: soft-drop mass', 'JMS down: pt', 'JMS down: soft-drop mass',
    'JMR up: pt', 'JMR up: soft-drop mass', 'JMR down: pt', 'JMR down: soft-drop mass',
]
WEIGHT_NAMES = ['Nominal weight', 'Pileup up', 'Pileup down',
                'Prefiring up', 'Prefiring down', 'Top pt weight', 'Nominal (duplicate)',
                'PS 0', 'PS 2', 'PS 1', 'PS 3',
                'LHE scale 0', 'LHE scale 1', 'LHE scale 3',
                'LHE scale 5', 'LHE scale 7', 'LHE scale 8']
GLOBAL_NAMES = (KIN_NAMES + TAG_NAMES + TRIGGER_NAMES + LEPTON_NAMES
                + SYS_NAMES + WEIGHT_NAMES + ['Generator match'])
assert len(GLOBAL_NAMES) == 52


def hist(ax, values, label, n_bins=45, categorical=False):
    vals = np.asarray(values).ravel()
    vals = vals[np.isfinite(vals)]
    ax.set_title(label, fontsize=10)
    if not len(vals):
        ax.text(.5, .5, 'No finite entries', ha='center', va='center', transform=ax.transAxes)
        return
    if categorical:
        ids, count = np.unique(vals.astype(int), return_counts=True)
        ax.bar(ids, count)
        if len(ids) <= 12:
            ax.set_xticks(ids)
            if label == 'Particle ID (encoded)':
                ax.set_xticklabels([PID_NAMES[i] if 0 <= i < 9 else str(i) for i in ids],
                                   rotation=45, ha='right', fontsize=8)
        ax.set_ylabel('Count')
    else:
        # Clip only visualization range, never change file or original values.
        lo, hi = np.percentile(vals, [0.5, 99.5])
        if lo >= hi:
            lo, hi = float(vals.min()), float(vals.max())
        if lo >= hi:
            lo, hi = lo - .5, hi + .5
        ax.hist(vals, bins=n_bins, range=(lo, hi), histtype='stepfilled', alpha=.75)
        ax.set_ylabel('Count')
    ax.tick_params(labelsize=8)
    ax.grid(alpha=.15)


def draw_pages(pdf, arr, labels, heading, category_cols=(), per_page=12):
    for start in range(0, len(labels), per_page):
        end = min(start + per_page, len(labels))
        fig, axes = plt.subplots(3, 4, figsize=(15, 10))
        for i, ax in enumerate(axes.ravel()):
            col = start + i
            if col < end:
                hist(ax, arr[:, col], '{} [{}]'.format(labels[col], col),
                     categorical=(col in category_cols))
            else:
                ax.axis('off')
        fig.suptitle('{}: features {}–{} ({} entries)'.format(
            heading, start, end - 1, len(arr)), fontsize=14)
        fig.tight_layout(rect=(0, 0, 1, .96))
        pdf.savefig(fig)
        plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-file', required=True, help='AI HDF5 containing data/global/pid')
    parser.add_argument('--output', default='omni_features.pdf',
                        help='PDF output (default: ./omni_features.pdf)')
    args = parser.parse_args()
    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    with h5py.File(args.input_file, 'r') as f:
        for name in ('data', 'global', 'pid'):
            if name not in f:
                raise ValueError('Missing dataset {}'.format(name))
        data = f['data'][:]
        glob = f['global'][:]
        dataset_id = f['pid'][:]

    if data.ndim != 3 or data.shape[2] != 9:
        raise ValueError('Expected data shape (N, P, 9), got {}'.format(data.shape))
    if glob.ndim != 2 or glob.shape[1] != 52:
        raise ValueError('Expected global shape (N, 52), got {}'.format(glob.shape))
    if not (len(data) == len(glob) == len(dataset_id)):
        raise ValueError('Inconsistent number of jets among datasets')

    # Particle ID 0 identifies padded rows; exclude from physics feature histograms.
    active = data[:, :, 4] != 0
    particles = data[active]
    multiplicity = np.count_nonzero(active, axis=1)
    with PdfPages(str(output)) as pdf:
        fig, axes = plt.subplots(2, 2, figsize=(11, 8.5))
        fig.suptitle('Omni dijet diagnostic: {}'.format(Path(args.input_file).name))
        hist(axes[0, 0], multiplicity, 'Non-padded particles per jet')
        hist(axes[0, 1], dataset_id, 'Dataset identifier (pid)', categorical=True)
        hist(axes[1, 0], glob[:, 4], 'Dijet invariant mass (GeV)')
        hist(axes[1, 1], glob[:, 0], 'Jet log(pT)')
        fig.text(.5, .02, '{} jets  |  {} candidate entries  |  {} active particles'.format(
            len(data), data.shape[0] * data.shape[1], len(particles)), ha='center')
        fig.tight_layout(rect=(0, .04, 1, .95))
        pdf.savefig(fig)
        plt.close(fig)

        if len(particles):
            draw_pages(pdf, particles, PARTICLE_NAMES, 'Particle features', category_cols=(4,))
        else:
            print('No non-padded particles; skipping particle feature pages')
        if len(glob):
            draw_pages(pdf, glob, GLOBAL_NAMES, 'Global features',
                       category_cols=(14, 15, 16, 17, 51))
        else:
            print('No jets; skipping global feature pages')

    print('Input: {}'.format(args.input_file))
    print('Jets: {}; active PF candidates: {}'.format(len(data), len(particles)))
    print('Saved PDF: {}'.format(output))


if __name__ == '__main__':
    main()
