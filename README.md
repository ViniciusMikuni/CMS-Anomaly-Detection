# CMS Open Data dijet processing

Process 2016 Ultra Legacy post-VFP data and simulation with one command:

```bash
bash run.sh SAMPLE [SAMPLE ...] --from STEP
```

The runner distributes files across your allocated ranks, enters Shifter,
initializes CMSSW, and runs through final AI inputs. Samples always remain
separate. You do not need to prepare job lists or run `cmsenv` yourself.

## 1. Start an interactive allocation on Perlmutter

```bash
salloc -C cpu -q interactive -A m3246 -t 4:00:00 \
  --cpus-per-task=16 --ntasks=64 \
  --image=zlmarshall/atlas-grid-centos7:20211123 \
  --module=cvmfs
```

Stay in the shell opened by this command. Then enter the extracted directory:

```bash
cd CMSOpenDataDijet
```

## 2. Set your paths

```bash
export CMSSW_BASE=your/CMSSW_10_6_30/installation
export INFOLDER=/pscratch/sd/v/vmikuni/test_cms/outputs
export OUTFOLDER=$SCRATCH/cms_outputs
```

`CMSSW_BASE` is the installation containing your compiled packages.
`INFOLDER` is the parent containing sample directories. `OUTFOLDER` is where
new files are saved. Input and output locations should be separate.

If CMSSW is not installed yet, see **One-time installation** below.

## 3. Run samples

For your existing corrected ROOT files:

```bash
bash run.sh \
  ZZ_TuneCP5_13TeV-pythia8 \
  WW_TuneCP5_13TeV-pythia8 \
  WZ_TuneCP5_13TeV-pythia8 \
  --from h5maker
```

This runs H5 maker and AI preprocessing using all allocated ranks.
Each rank handles its assigned tasks sequentially.
Standard output and errors are saved in the log directory printed
at launch. Step starts, completions, reused outputs and failures also appear
live in the terminal with their rank and task ID. Updates are checked every
second; shared-filesystem visibility can introduce a short delay. A terminal
summary appears when all workers finish successfully.

For data, add `--type data`:

```bash
bash run.sh JetHTG JetHTH --type data --from postprocess \
  --infolder /path/to/data --outfolder /path/to/data_outputs
```

Command-line folder options override the exported defaults. Data periods are
inferred from names such as JetHTG or SingleMuonH. Use `--period G` if your
sample name does not identify its era. MC sample names must match `workflow/norms.py`.

## Choose the first and last steps

| `--from` | Input files | First operation |
|---|---|---|
| `miniaod` | MiniAOD ROOT files | Produce PFNano with particle constituents |
| `postprocess` | `file_list.root` | Apply UL2016 AK8/AK4 corrections |
| `h5maker` | `file_list_postprocessed.root` | Select jets and write intermediate HDF5 |
| `inputsomni` | Intermediate `.h5` files | Write AI inputs |

Each step also runs the following steps. To stop early, specify `--through`
using the same names. For example, produce only intermediate HDF5:

```bash
bash run.sh ZZ_TuneCP5_13TeV-pythia8 --from h5maker --through h5maker
```

Files are discovered recursively beneath `INFOLDER/SAMPLE`. The runner also
recognizes its own `pfnano`, `corrected`, and `h5` output subdirectories. To
preprocess its intermediate outputs later:

```bash
bash run.sh ZZ_TuneCP5_13TeV-pythia8 \
  --from inputsomni --infolder "$OUTFOLDER"
```

Standard NanoAOD without PF constituent tables is not sufficient. Keep raw
MiniAOD files in their own input tree so generated ROOT files are not mistaken
for raw inputs.

## Running on an interactive job

You can also submit runs using slurm jobs or over an interactive job using the command:

```bash
./mc.sh tt_hadronic  postprocess
```

which will in turn use the flags above to run over the sample handle starting from the postprocess step.
The same can be done for data with the ```./data.sh``` command instead. 

## Control region

Add `--cr` and choose an output folder:

```bash
bash run.sh ZZ_TuneCP5_13TeV-pythia8 --from h5maker --cr \
  --outfolder /pscratch/sd/v/vmikuni/test_cms/outputs_cr
```

The flag reaches both H5 maker and AI preprocessing. Both data and MC use the
same option. No automatic region folder suffix is added. Existing corrected
ROOT files used for CR must contain `Jet_pt_nom`; if they do not, start from
`postprocess` to generate the AK4 corrections. An already-selected intermediate
HDF5 cannot recover events removed by a different selection.

## Useful run options

| Option | Use |
|---|---|
| `--ranks 8` | Use eight ranks from your allocation |
| `--local` | Run one worker without srun; Shifter and CMSSW setup still happen |
| `--cpus-per-task 4` | Use four CPUs per rank; otherwise inherit the allocation |
| `--files-per-task 5` | Group up to five MiniAOD files from one sample per task |
| `--dry-run` | Print planned processing commands without running or writing output files |
| `--overwrite` | Recompute outputs instead of reusing validated completions |
| `--cmssw /path/to/CMSSW_10_6_30` | Override the CMSSW installation |
| `--help` | Show all options |

`--files-per-task` applies only to `--from miniaod`. It never groups files from
different samples. Later steps process one existing input file per task.
Without an allocation, the runner uses one local worker. Local execution still
requires the Shifter/CVMFS environment used for this project.

## CPU allocation

The runner inherits `SLURM_CPUS_PER_TASK` or uses `--cpus-per-task` when given.
It passes that count to srun and restores the thread environment after CMSSW
initialization. Each rank prints its CMSSW path and CPU count; the postprocessor
log also records the NanoAODTools module path.

MiniAOD `cmsRun` uses this count for `numberOfThreads`. NanoAODTools postprocessing
has a serial event loop: allocating 16 CPUs to a rank does not make that loop
16-way parallel. Files are processed concurrently across ranks. For a run starting
at `postprocess`, one CPU per task is a reasonable starting allocation; measure
throughput and memory for your samples before increasing concurrency.

## Results and logs

For each sample, outputs are saved under:

| Subdirectory | Contents |
|---|---|
| `pfnano/` | PFNano ROOT |
| `corrected/` | Corrected ROOT |
| `h5/` | Intermediate jet HDF5 |
| `preprocess/` | Final `omni_*.h5` AI files |

Only the steps you run produce outputs. Final AI files contain `data (N,150,9)`,
`global (N,52)`, `pid (N,)`, and `event_info (N,3)` for run/lumi/event identity.

Each run prints its own log directory, for example
`$OUTFOLDER/logs/run-abcdefgh/`. Inside it:

- `rank_0.out`, `rank_0.err`, etc.: worker output and errors.
- `summary.txt`: the same summary printed in your terminal after success.

The summary reports files per sample, newly produced/reused files, final jet
counts, empty files, stage completions, elapsed time and output location.
Jet counts are HDF5 rows, not unique events. A failed run exits nonzero and
points to the logs instead of printing success.

Rerun the same command after an interruption. Matching completed outputs are
validated and reused. Changes to inputs, options or workflow code trigger
reprocessing. Use a fresh outfolder when changing sample membership or
MiniAOD grouping, to avoid retaining obsolete outputs from an earlier layout.

## One-time installation

Skip this section if `CMSSW_10_6_30` is already
installed with PFNano and NanoAODTools.

From an allocation with the image and CVMFS specified above, inside the workflow
directory:

```bash
export CMSSW_WORKDIR=$SCRATCH
shifter bash setup_cmssw.sh
```

This creates `CMSSW_10_6_30` under that parent and builds the required packages.
The launcher uses host Python 3.6+ for file discovery; after CMSSW initialization,
container Python 3.6+ must provide NumPy/h5py and CMSSW Python must provide ROOT.
No pip installation of the workflow is needed.

For reproducible installations, set `PFNANO_COMMIT` and `NANOAODTOOLS_COMMIT`
to your tested revisions before setup. The installer does not apply optional
NanoAODTools patches automatically. Calibration and normalization checks are
listed separately in `ANALYSIS_NOTES.md`.

To run the developer tests in an environment with NumPy, h5py and pytest:

```bash
python3 -m pytest -q tests/
```
