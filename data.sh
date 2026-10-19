#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'HELP'
Usage: ./data.sh SAMPLE STAGE [run.sh options]

Samples: JetHTH, JetHTG, SingleMuonH, SingleMuonG
Stages: miniaod, postprocess, h5maker, inputsomni

Examples:
  ./data.sh JetHTH postprocess
  ./data.sh JetHTG h5maker
  ./data.sh SingleMuonH h5maker --cr
  ./data.sh SingleMuonG h5maker --cr

Extra options are passed to run.sh. With --cr, the default output is
${OUTFOLDER}_cr. An explicit --outfolder overrides this default.
HELP
}

if [[ ${1:-} == --help || ${1:-} == -h ]]; then
    usage
    exit 0
fi
if (( $# < 2 )); then
    usage >&2
    exit 2
fi
sample=$1
stage=$2
shift 2
case "$sample" in
    JetHTH|JetHTG|SingleMuonH|SingleMuonG) ;;
    *) echo "Unknown data sample: $sample" >&2; usage >&2; exit 2 ;;
esac
case "$stage" in
    miniaod|postprocess|h5maker|inputsomni) ;;
    *) echo "Unknown stage: $stage" >&2; usage >&2; exit 2 ;;
esac

export CMSSW_BASE=${CMSSW_BASE:-/pscratch/sd/v/vmikuni/CMSSW_10_6_30}
export INFOLDER=/pscratch/sd/v/vmikuni/CMSSW_10_6_30/AOJProcessing/NP/data
#export INFOLDER=${INFOLDER:-/pscratch/sd/v/vmikuni/CMSSW_10_6_30/AOJProcessing/NP/data}
export OUTFOLDER=${OUTFOLDER:-/pscratch/sd/v/vmikuni/test_cms/outputs}

extra=()
for arg in "$@"; do
    if [[ "$arg" == --cr ]]; then
        extra=(--outfolder "${OUTFOLDER}_cr")
        break
    fi
done
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
exec bash "$repo/run.sh" "$sample" --type data --from "$stage" "${extra[@]}" "$@"
