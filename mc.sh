#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'HELP'
Usage: ./mc.sh GROUP STAGE [run.sh options]

Groups:
  qcd_300to470, qcd_470to600, qcd_600to800, qcd_800to1000
  qcd_1000to1400, qcd_1400to1800, qcd_1800to2400
  qcd_2400to3200, qcd_3200toInf   One QCD pT bin per call
  tt_hadronic, tt_semileptonic, tt_dileptonic   One ttbar channel per call
  single_top  Single top (tW, t-channel, s-channel)
  ttv         ttW and ttZ
  four_top    Four-top production
  higgs       ggH, VBF, VH, ttH and HH
  diboson     WW, WZ and ZZ
  wjets       W -> qq, HT bins
  zjets       Z -> qq, HT bins
  wlnu        W -> lnu, 1-4 jet samples
  cr          All 13 CR samples; requires h5maker, automatically enables --cr

Stages: miniaod, postprocess, h5maker, inputsomni

Examples:
  ./mc.sh diboson postprocess
  ./mc.sh qcd_300to470 h5maker
  ./mc.sh tt_hadronic h5maker --cr --outfolder /path/to/outputs_cr
  ./mc.sh higgs postprocess --dry-run
  ./mc.sh cr h5maker

Extra options are passed to run.sh. Set INFOLDER to the parent containing
inputs for the selected stage. The cr group defaults to ${OUTFOLDER}_cr; --outfolder overrides it.
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
group=$1
stage=$2
shift 2
case "$stage" in
    miniaod|postprocess|h5maker|inputsomni) ;;
    *) echo "Unknown stage: $stage" >&2; usage >&2; exit 2 ;;
esac

# Override these defaults by exporting the variables before calling mc.sh.
export CMSSW_BASE=${CMSSW_BASE:-/pscratch/sd/v/vmikuni/CMSSW_10_6_30}
export INFOLDER=${INFOLDER:-/pscratch/sd/v/vmikuni/CMSSW_10_6_30/AOJProcessing/NP/mc}
export OUTFOLDER=${OUTFOLDER:-/pscratch/sd/v/vmikuni/test_cms/outputs}

case "$group" in
    qcd_300to470)
        samples=(QCD_Pt_300to470_TuneCP5_13TeV_pythia8)
        ;;
    qcd_470to600)
        samples=(QCD_Pt_470to600_TuneCP5_13TeV_pythia8)
        ;;
    qcd_600to800)
        samples=(QCD_Pt_600to800_TuneCP5_13TeV_pythia8)
        ;;
    qcd_800to1000)
        samples=(QCD_Pt_800to1000_TuneCP5_13TeV_pythia8)
        ;;
    qcd_1000to1400)
        samples=(QCD_Pt_1000to1400_TuneCP5_13TeV_pythia8)
        ;;
    qcd_1400to1800)
        samples=(QCD_Pt_1400to1800_TuneCP5_13TeV_pythia8)
        ;;
    qcd_1800to2400)
        samples=(QCD_Pt_1800to2400_TuneCP5_13TeV_pythia8)
        ;;
    qcd_2400to3200)
        samples=(QCD_Pt_2400to3200_TuneCP5_13TeV_pythia8)
        ;;
    qcd_3200toInf)
        samples=(QCD_Pt_3200toInf_TuneCP5_13TeV_pythia8)
        ;;
    tt_hadronic)
        samples=(TTToHadronic_TuneCP5_13TeV-powheg-pythia8)
        ;;
    tt_semileptonic)
        samples=(TTToSemiLeptonic_TuneCP5_13TeV-powheg-pythia8)
        ;;
    tt_dileptonic)
        samples=(TTTo2L2Nu_TuneCP5_13TeV-powheg-pythia8)
        ;;
    single_top)
        samples=(
            ST_tW_top_5f_inclusiveDecays_TuneCP5_13TeV-powheg-pythia8
            ST_tW_antitop_5f_inclusiveDecays_TuneCP5_13TeV-powheg-pythia8
            ST_t-channel_antitop_4f_InclusiveDecays_TuneCP5_13TeV-powheg-madspin-pythia8
            ST_t-channel_top_4f_InclusiveDecays_TuneCP5_13TeV-powheg-madspin-pythia8
            ST_s-channel_4f_hadronicDecays_TuneCP5_13TeV-amcatnlo-pythia8
        )
        ;;
    ttv)
        samples=(
            TTWJetsToQQ_TuneCP5_13TeV-amcatnloFXFX-madspin-pythia8
            TTWJetsToLNu_TuneCP5_13TeV-amcatnloFXFX-madspin-pythia8
            TTZToQQ_TuneCP5_13TeV-amcatnlo-pythia8
        )
        ;;
    four_top)
        samples=(
            TTTT_TuneCP5_13TeV-amcatnlo-pythia8
        )
        ;;
    higgs)
        samples=(
            GluGluHToBB_M-125_TuneCP5_13TeV-powheg-pythia8
            GluGluToHHTo4B_cHHH1_TuneCP5_PSWeights_13TeV-powheg-pythia8
            TTHTo2B_TTToHadronic_M-125_TuneCP5_13TeV-powheg-pythia8
            VBFHToBB_M-125_TuneCP5_13TeV-powheg-pythia8
            WplusH_HToBB_WToQQ_M-125_TuneCP5_13TeV-powheg-pythia8
            WminusH_HToBB_WToQQ_M-125_TuneCP5_13TeV-powheg-pythia8
            ZH_HToBB_ZToQQ_M-125_TuneCP5_13TeV-powheg-pythia8
        )
        ;;
    diboson)
        samples=(
            WW_TuneCP5_13TeV-pythia8
            WZ_TuneCP5_13TeV-pythia8
            ZZ_TuneCP5_13TeV-pythia8
        )
        ;;
    wjets)
        samples=(
            WJetsToQQ_HT-200to400_TuneCP5_13TeV-madgraphMLM-pythia8
            WJetsToQQ_HT-400to600_TuneCP5_13TeV-madgraphMLM-pythia8
            WJetsToQQ_HT-600to800_TuneCP5_13TeV-madgraphMLM-pythia8
            WJetsToQQ_HT-800toInf_TuneCP5_13TeV-madgraphMLM-pythia8
        )
        ;;
    zjets)
        samples=(
            ZJetsToQQ_HT-200to400_TuneCP5_13TeV-madgraphMLM-pythia8
            ZJetsToQQ_HT-400to600_TuneCP5_13TeV-madgraphMLM-pythia8
            ZJetsToQQ_HT-600to800_TuneCP5_13TeV-madgraphMLM-pythia8
            ZJetsToQQ_HT-800toInf_TuneCP5_13TeV-madgraphMLM-pythia8
        )
        ;;
    wlnu)
        samples=(
            W1JetsToLNu_TuneCP5_13TeV-madgraphMLM-pythia8
            W2JetsToLNu_TuneCP5_13TeV-madgraphMLM-pythia8
            W3JetsToLNu_TuneCP5_13TeV-madgraphMLM-pythia8
            W4JetsToLNu_TuneCP5_13TeV-madgraphMLM-pythia8
        )
        ;;
    cr)
        if [[ "$stage" != h5maker ]]; then
            echo "The cr group must start from h5maker: ./mc.sh cr h5maker" >&2
            exit 2
        fi
        samples=(
            TTToHadronic_TuneCP5_13TeV-powheg-pythia8
            TTToSemiLeptonic_TuneCP5_13TeV-powheg-pythia8
            TTTo2L2Nu_TuneCP5_13TeV-powheg-pythia8
            ST_tW_top_5f_inclusiveDecays_TuneCP5_13TeV-powheg-pythia8
            ST_tW_antitop_5f_inclusiveDecays_TuneCP5_13TeV-powheg-pythia8
            ST_t-channel_antitop_4f_InclusiveDecays_TuneCP5_13TeV-powheg-madspin-pythia8
            ST_t-channel_top_4f_InclusiveDecays_TuneCP5_13TeV-powheg-madspin-pythia8
            TTWJetsToQQ_TuneCP5_13TeV-amcatnloFXFX-madspin-pythia8
            TTWJetsToLNu_TuneCP5_13TeV-amcatnloFXFX-madspin-pythia8
            W1JetsToLNu_TuneCP5_13TeV-madgraphMLM-pythia8
            W2JetsToLNu_TuneCP5_13TeV-madgraphMLM-pythia8
            W3JetsToLNu_TuneCP5_13TeV-madgraphMLM-pythia8
            W4JetsToLNu_TuneCP5_13TeV-madgraphMLM-pythia8
        )
        ;;
    *) echo "Unknown process group: $group" >&2; usage >&2; exit 2 ;;
esac

repo=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
extra=()
if [[ "$group" == cr ]]; then
    extra=(--cr --outfolder "${OUTFOLDER}_cr")
fi
exec bash "$repo/run.sh" "${samples[@]}" --type mc --from "$stage" "${extra[@]}" "$@"
