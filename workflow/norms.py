import numpy as np

lumi = 16.393380531e3

samples = {
    "TTToSemiLeptonic_TuneCP5_13TeV-powheg-pythia8": {
        "xsec": 366.9142888,
        "ngen": 42956934963.88
    },
    "TTToHadronic_TuneCP5_13TeV-powheg-pythia8": {
        "xsec": 377.96006159999996,
        "ngen": 34136217768.18
    },
    "TTTo2L2Nu_TuneCP5_13TeV-powheg-pythia8": {
        "xsec": 89.0482256,
        "ngen": 3146182212.88        
    },
    "ZJetsToQQ_HT-200to400_TuneCP5_13TeV-madgraphMLM-pythia8": {
        "xsec": 1010.2,
        "ngen": 7285673.00
    },
    
    "ZJetsToQQ_HT-400to600_TuneCP5_13TeV-madgraphMLM-pythia8": {
        "xsec": 114.208,
        "ngen": 6942718.00
    },
    "ZJetsToQQ_HT-600to800_TuneCP5_13TeV-madgraphMLM-pythia8": {
        "xsec": 25.35,
        "ngen": 5500386.00 
    },
    "ZJetsToQQ_HT-800toInf_TuneCP5_13TeV-madgraphMLM-pythia8": {
        "xsec": 12.915,
        "ngen": 4388402.00
    },

    "WJetsToQQ_HT-200to400_TuneCP5_13TeV-madgraphMLM-pythia8": {
        "xsec": 2565.302,
        "ngen": 7065076.00
    },
    "WJetsToQQ_HT-400to600_TuneCP5_13TeV-madgraphMLM-pythia8": {
        "xsec": 276.63,
        "ngen": 4455853.00        
    },
    "WJetsToQQ_HT-600to800_TuneCP5_13TeV-madgraphMLM-pythia8": {
        "xsec": 59.078,
        "ngen": 6735353.00
    },
    "WJetsToQQ_HT-800toInf_TuneCP5_13TeV-madgraphMLM-pythia8": {
        "xsec": 28.7614,
        "ngen": 6769101.00  
    },

    "WZZ_TuneCP5_13TeV-amcatnlo-pythia8": {
        "xsec": 5.709e-02,
        "ngen": 395.24
    },




    "TTTT_TuneCP5_13TeV-amcatnlo-pythia8": {
        "xsec": 0.012,
        "ngen": 37355.12
    },


    "TTWJetsToQQ_TuneCP5_13TeV-amcatnloFXFX-madspin-pythia8": {
        "xsec": 0.5297,
        "ngen": 209107.00
    },

    "TTZToBB_TuneCP5_13TeV-amcatnlo-pythia8": {
        "xsec": 0.16366,
        "ngen": 359693.39
    },


    "ST_s-channel_4f_hadronicDecays_TuneCP5_13TeV-amcatnlo-pythia8": {
        "xsec": 6.97632,
        "ngen": 37656391.85
    },


    "ST_t-channel_antitop_4f_InclusiveDecays_TuneCP5_13TeV-powheg-madspin-pythia8": {
        "xsec": 80.95,
        "ngen": 1957283270.76
    },

    "ST_t-channel_top_4f_InclusiveDecays_TuneCP5_13TeV-powheg-madspin-pythia8": {
        "xsec": 136.02,
        "ngen": 4907729562.99
    },


    "ST_tW_antitop_5f_inclusiveDecays_TuneCP5_13TeV-powheg-pythia8": {
        "xsec": 35.85,
        "ngen": 83024149.94,
    },

    

    "ST_tW_top_5f_inclusiveDecays_TuneCP5_13TeV-powheg-pythia8": {
        "xsec": 35.85,
        "ngen": 80821432.59
    },

    "QCD_Pt_300to470_TuneCP5_13TeV_pythia8": {
        "xsec": 6832.,
        "ngen": 55264009.34843346
    },
    "QCD_Pt_470to600_TuneCP5_13TeV_pythia8": {
        "xsec": 551.9,
        "ngen": 52408168.58703071
    },
    "QCD_Pt_600to800_TuneCP5_13TeV_pythia8": {
        "xsec": 156.5,
        "ngen": 65088001.49533641
    },
    "QCD_Pt_800to1000_TuneCP5_13TeV_pythia8": {
        "xsec": 26.5,
        "ngen": 37782000.0
    },
    "QCD_Pt_1000to1400_TuneCP5_13TeV_pythia8": {
        "xsec": 7.475,
        "ngen": 19550000.0
    },
    "QCD_Pt_1400to1800_TuneCP5_13TeV_pythia8": {
        "xsec": 0.6482,
        "ngen": 10722000.0
    },
    "QCD_Pt_1800to2400_TuneCP5_13TeV_pythia8": {
        "xsec": 8.746e-02,
        "ngen": 5236000.0
    },
    "QCD_Pt_2400to3200_TuneCP5_13TeV_pythia8": {
        "xsec": 5.235e-03,
        "ngen":46000.0
    },
    "QCD_Pt_3200toInf_TuneCP5_13TeV_pythia8": {
        "xsec": 1.352e-04,
        "ngen": 996000.0
    },

    "ZH_HToBB_ZToBB_M-125_TuneCP5_13TeV-powheg-pythia8": {
        "xsec": 0.11114172742,
        "ngen": 1240904.25 
        
    },
    
    "ZH_HToBB_ZToQQ_M-125_TuneCP5_13TeV-powheg-pythia8": {
        "xsec": 0.35989019481,
        "ngen": 2575330.87 
        
    },

    "WplusH_HToBB_WToQQ_M-125_TuneCP5_13TeV-powheg-pythia8": {
        "xsec": 0.3297805056,
        "ngen": 2910762.99
        
    },

    "WminusH_HToBB_WToQQ_M-125_TuneCP5_13TeV-powheg-pythia8": {
        "xsec": 0.20925358272,
        "ngen": 1836585.12
        
    },

    "VBFHToBB_M-125_TuneCP5_13TeV-powheg-pythia8": {
        "xsec": 2.233,
        "ngen": 13604905.52
        
    },
    "GluGluHToBB_M-125_TuneCP5_13TeV-powheg-pythia8": {
        "xsec": 28.293,
        "ngen": 62185256.86
        
    },

    "GluGluToHHTo4B_cHHH1_TuneCP5_PSWeights_13TeV-powheg-pythia8": {
        "xsec": 0.010509,
        "ngen": 12347.15
        
    },

    "WW_TuneCP5_13TeV-pythia8": {
        "xsec": 110.8,
        "ngen":15821137.2
    },


    
    "WJetsToLNu_TuneCP5_13TeV-madgraphMLM-pythia8": {
        "xsec": 61526.7,
        "ngen": 1063141589.5887803
    },
    "W1JetsToLNu_TuneCP5_13TeV-madgraphMLM-pythia8": {
        "xsec": 8104.0,
        "ngen": 1263657366489.42
    },
    "W2JetsToLNu_TuneCP5_13TeV-madgraphMLM-pythia8": {
        "xsec": 2793.0,
        "ngen": 35882066.33
    },
    "W3JetsToLNu_TuneCP5_13TeV-madgraphMLM-pythia8": {
        "xsec": 992.5,
        "ngen": 18887529.48
    },
    "W4JetsToLNu_TuneCP5_13TeV-madgraphMLM-pythia8": {
        "xsec": 544.3,
        "ngen": 30810512899.75
    },
    "WZ_TuneCP5_13TeV-pythia8": {
        "xsec": 47.13,
        "ngen": 7889000.0
    },
    "ZZ_TuneCP5_13TeV-pythia8": {
        "xsec": 16.523,
        "ngen": 2708000.0
    },
    "WWW_4F_TuneCP5_13TeV-amcatnlo-pythia8": {
        "xsec": 0.2086,
        "ngen": 36869.1616059
    },
    "WWZ_4F_TuneCP5_13TeV-amcatnlo-pythia8": {
        "xsec": 0.1651,
        "ngen": 30386.291709359997
    },
    "ZZZ_TuneCP5_13TeV-amcatnlo-pythia8": {
        "xsec": 0.01398,
        "ngen": 2628.4716708940005
    },
    "TTHTo2B_TTToHadronic_M-125_TuneCP5_13TeV-powheg-pythia8":{
        "xsec": 0.1391,
        "ngen": 1035137.78
    },
    "ttHJetTobb_M125_TuneCP5_13TeV_amcatnloFXFX_madspin_pythia8": {
        "xsec": 0.5086,
        "ngen": 8656518.879397199
    },
    "TTWJetsToLNu_TuneCP5_13TeV-amcatnloFXFX-madspin-pythia8": {
        "xsec": 0.2043,
        "ngen": 2501696.3683904386
    },
    "tZq_ll_4f_ckm_NLO_TuneCP5_13TeV-amcatnlo-pythia8": {
        "xsec": 0.09418,
        "ngen": 1115742.6830486401
    },
    "TTZToQQ_TuneCP5_13TeV-amcatnlo-pythia8": {
        "xsec": 0.5297,
        "ngen": 6057612.665910002
    },
}

