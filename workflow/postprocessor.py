#!/usr/bin/env python
# Python 2 compatible

import os
import sys
import argparse
import tempfile
import shutil

from PhysicsTools.NanoAODTools.postprocessing.framework.postprocessor import PostProcessor
from PhysicsTools.NanoAODTools.postprocessing.modules.jme.jetmetHelperRun2 import createJMECorrector
from PhysicsTools.NanoAODTools.postprocessing.modules.common.puWeightProducer import puWeight_UL2016


def main():

    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input", required=True,
                        help="Input NanoAOD ROOT file (UL2016 MC)")
    parser.add_argument("-o", "--output", required=True,
                        help="Output NanoAOD ROOT file (UL2016 MC)")
    parser.add_argument("-d", "--dir", required=True,
                        help="Directory with root files")
 
    parser.add_argument(
        "--is-mc",
        action="store_true",
        help="Set this flag if running on MC"
    )
    parser.add_argument(
        "--period",
        type=str,
        default="H",
        help="Data-taking period (default: H)"
    )

    args = parser.parse_args()
    print("Postprocessor: CMSSW_BASE=%s CPUs/task=%s OMP_NUM_THREADS=%s; serial event loop" % (
        os.environ.get('CMSSW_BASE', ''), os.environ.get('CMS_OD_CPUS_PER_TASK', '1'),
        os.environ.get('OMP_NUM_THREADS', '1')))
    print("NanoAODTools: %s" % sys.modules[PostProcessor.__module__].__file__)

    in_file = os.path.join(args.dir,args.input)
    out_file =os.path.join(args.dir,args.output)

    if not os.path.exists(in_file):
        print("[ERROR] Input file not found:", in_file)
        sys.exit(1)

    modules = []

    # -------------------------
    # Pileup weights (UL2016)
    # -------------------------
    if args.is_mc:
        modules.append(puWeight_UL2016())

    # -------------------------
    # JEC/JER (AK8 PUPPI)
    # -------------------------
    modules.append(
        createJMECorrector(
            isMC=args.is_mc,
            dataYear="UL2016",
            runPeriod=args.period,
            jesUncert="Total",
            jetType="AK8PFPuppi",   # FatJet collection
            metBranchName="MET",
            applySmearing=True,
            splitJER=False,
            saveMETUncs=[]
        )()
    )

    # CR AK4 selection uses Jet_pt_nom, so correct AK4 CHS as well as AK8 PUPPI.
    modules.append(
        createJMECorrector(
            isMC=args.is_mc,
            dataYear="UL2016",
            runPeriod=args.period,
            jesUncert="Total",
            jetType="AK4PFchs",
            metBranchName="MET",
            applySmearing=True,
            splitJER=False,
            saveMETUncs=[]
        )()
    )

    postfix = "_tmpPost"
    out_file = os.path.abspath(out_file)
    if not os.path.isdir(os.path.dirname(out_file)):
        os.makedirs(os.path.dirname(out_file))
    work = tempfile.mkdtemp(prefix=".postprocess-", dir=os.path.dirname(out_file))

    print "Running NanoAOD postprocessor..."
    p = PostProcessor(
        work,
        [in_file],
        cut=None,
        branchsel=None,
        modules=modules,
        provenance=False,
        noOut=False,
        postfix=postfix,
    )
    p.run()

    produced = os.path.join(work,
                            os.path.basename(in_file).replace(".root", postfix + ".root"))

    if not os.path.exists(produced):
        print "[ERROR] PostProcessor did not produce output."
        sys.exit(2)

    os.rename(produced, out_file)
    shutil.rmtree(work)

    print "[OK] Wrote:", out_file


if __name__ == "__main__":
    main()
