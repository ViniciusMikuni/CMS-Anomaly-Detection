#!/usr/bin/env bash
set -euo pipefail
# Execute inside a CERN-compatible el7 container with CVMFS mounted.
RELEASE=CMSSW_10_6_30
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
WORKDIR=${CMSSW_WORKDIR:-$(dirname "$repo")}
export SCRAM_ARCH=slc7_amd64_gcc700
mkdir -p "$WORKDIR"
set +u
source /cvmfs/cms.cern.ch/cmsset_default.sh
set -u
export SCRAM_ARCH=slc7_amd64_gcc700
cd "$WORKDIR"
if [[ ! -d "$RELEASE/src" ]]; then
  cmsrel "$RELEASE"
fi
cd "$RELEASE/src"
set +u
eval "$(scram runtime -sh)"
set -u
mkdir -p PhysicsTools
if [[ ! -d PhysicsTools/PFNano/.git ]]; then
  git clone https://github.com/cms-opendata-analyses/PFNanoProducerTool.git PhysicsTools/PFNano
fi
if [[ ! -d PhysicsTools/NanoAODTools/.git ]]; then
  git clone https://github.com/cms-nanoAOD/nanoAOD-tools.git PhysicsTools/NanoAODTools
fi
if [[ -n "${PFNANO_COMMIT:-}" ]]; then
  git -C PhysicsTools/PFNano checkout "$PFNANO_COMMIT"
fi
if [[ -n "${NANOAODTOOLS_COMMIT:-}" ]]; then
  git -C PhysicsTools/NanoAODTools checkout "$NANOAODTOOLS_COMMIT"
fi
scram b -j "${BUILD_JOBS:-8}"
echo "CMSSW_BASE=$CMSSW_BASE"
git -C PhysicsTools/PFNano rev-parse HEAD
git -C PhysicsTools/NanoAODTools rev-parse HEAD
