#!/usr/bin/env bash
set -euo pipefail
if (( $# < 2 )); then
    echo 'Usage: worker.sh MANIFEST OUTPUT [worker options]' >&2
    exit 2
fi
manifest=$1; output=$2; shift 2
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
: "${CMSSW_BASE:?Set CMSSW_BASE or pass --cmssw}"
cmssw=$CMSSW_BASE
cpus=${CMS_OD_CPUS_PER_TASK:-${SLURM_CPUS_PER_TASK:-1}}
export SCRAM_ARCH=slc7_amd64_gcc700
set +u
source /cvmfs/cms.cern.ch/cmsset_default.sh
cd "$cmssw/src"
eval "$(scram runtime -sh)"
set -u
export CMS_OD_CPUS_PER_TASK="$cpus" SLURM_CPUS_PER_TASK="$cpus"
export OMP_NUM_THREADS="$cpus" OMP_PROC_BIND=spread OMP_PLACES=threads
export OPENBLAS_NUM_THREADS="$cpus" MKL_NUM_THREADS="$cpus" NUMEXPR_NUM_THREADS="$cpus"
export PYTHONUNBUFFERED=1
echo "[ENV] CMSSW_BASE=$CMSSW_BASE CPUs/task=$cpus OMP_NUM_THREADS=$OMP_NUM_THREADS"
cd "$repo"
export PYTHONPATH="$repo${PYTHONPATH:+:$PYTHONPATH}"
python3 -c 'import sys; assert sys.version_info >= (3,6), "Python >=3.6 required inside CMSSW"; import numpy,h5py'
exec python3 -m cms_od.distributed --manifest "$manifest" --output-dir "$output" "$@"
