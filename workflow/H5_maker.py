# Read nanoAOD with PF constituents (aka pancakes), apply a pre-selection and output to an H5 file format
import ROOT
from ROOT import TLorentzVector, TFile
import numpy as np
import h5py
from optparse import OptionParser
import sys, os
import math

from PhysicsTools.NanoAODTools.postprocessing.framework.datamodel import *
from PhysicsTools.NanoAODTools.postprocessing.framework.postprocessor import PostProcessor
from PhysicsTools.NanoAODTools.postprocessing.tools import *
from PhysicsTools.NanoAODTools.postprocessing.modules.jme.JetSysColl import JetSysColl, JetSysObj
from PhysicsTools.NanoAODTools.postprocessing.framework.eventloop import eventLoop
from PhysicsTools.NanoAODTools.postprocessing.framework.preskimming import preSkim

from Utils import *

from norms import lumi, samples


def deltaR(o1, o2):
    return ((o1.eta - o2.eta)**2 + ang_dist(o1.phi, o2.phi)**2)**(0.5)


def delta_phi(phi1, phi2):
    dphi = phi1 - phi2
    while dphi > math.pi:
        dphi -= 2.0 * math.pi
    while dphi <= -math.pi:
        dphi += 2.0 * math.pi
    return dphi


def get_softdrop_z_theta_btag(fatjet, subjets, R0=0.8):
    idx1 = fatjet.subJetIdx1
    idx2 = fatjet.subJetIdx2

    if idx1 < 0 or idx2 < 0:
        return -1, -1, -1

    sj1 = subjets[idx1]
    sj2 = subjets[idx2]

    pt1, pt2 = sj1.pt, sj2.pt

    z = min(pt1, pt2) / (pt1 + pt2)

    dr = deltaR(sj1,sj2)

    theta = dr / R0
    btag = max(sj1.btagDeepB,sj2.btagDeepB)
    return z, theta,btag




def match_ak4jet(event,ak8jet, sel_muon = None):
    #https://cms-opendata-workshop.github.io/workshop2024-lesson-physics-objects/instructor/05-btagging.html
    jets = Collection(event, "Jet")
    nb = 0
    for jet in jets:
        if(jet.pt_nom > 40 and (jet.jetId == 6) and abs(jet.eta) < 2.4 and jet.btagDeepFlavB >  0.0480):
            dr_jet = deltaR(jet,ak8jet)
            if sel_muon is not None:
                dr_muon = deltaR(jet,sel_muon)
            else:
                dr_muon = 100
            if dr_jet > 0.8 and dr_muon < 0.8:
                nb +=1
    return nb

def nPFCounter(index, event):
    count = 0
    jet_indices = event.FatJetPFCands_jetIdx
    length = len(event.FatJetPFCands_jetIdx)
    for i in range(length):
        if jet_indices[i] == index:
            count += 1
    
    return count

def append_h5(f, name, data):
    prev_size = f[name].shape[0]
    f[name].resize(( prev_size + data.shape[0]), axis=0)
    f[name][prev_size:] = data


def get_branch_mean(inTree, branch_name):

    inTree.Draw(branch_name)
    temp = ROOT.gPad.GetPrimitive("htemp")
    return temp.GetMean()



class Outputer:
    def __init__(self, outputFileName="out.root", batch_size = 5000, sample_type="data", year = 2016, sample_name=None):

        self.batch_size = batch_size
        self.output_name = outputFileName
        self.sample_name = sample_name or os.path.basename(outputFileName).rsplit("_", 1)[0]
        self.sample_type = sample_type
        self.first_write = False
        self.idx = 0
        self.nBatch = 0
        self.n_pf_cands = 150 #how many PF candidates to save (max)
        self.year = year
        self.reset()

    def reset(self):
        self.idx = 0
        self.PFCands = np.zeros((self.batch_size, self.n_pf_cands,11), dtype=np.float32)
        self.jet_kinematics = np.zeros((self.batch_size, 4), dtype=np.float32)
        self.jet_systematics = np.zeros((self.batch_size, 16), dtype=np.float32)
        self.jet_tagging = np.zeros((self.batch_size, 9), dtype=np.float32)
        self.event_info = np.zeros((self.batch_size, 3), dtype=np.int64)
        self.trigger_info = np.zeros((self.batch_size, 2), dtype=np.int64)
        self.part_info = np.zeros((self.batch_size, 2), dtype=np.int64)
        self.match_info = np.zeros((self.batch_size, 1), dtype=np.float32)
        self.weight_info = np.zeros((self.batch_size, 17), dtype=np.float32)


    def sort_pfcands(self, pfcands):
        #Sort by pt
        
        pfcands_pt = np.sqrt(pfcands[:, 0]**2 + pfcands[:, 1]**2)
        sorted_idx = np.flip(np.argsort(pfcands_pt))
        pfcands = pfcands[sorted_idx]
        
        return pfcands
        
    def fill_jet(self, inTree, jet, PFCands, FatJetPFCands,SubJet, passTrigger, passTriggerMuon, nmuon, nelec, top_pt_w,match, isMC):
        
        eventNum = inTree.readBranch('event')
        lumiBlock = inTree.readBranch("luminosityBlock")
        run = inTree.readBranch('run')        

        event_info = [run, lumiBlock, eventNum]

        #Trigger info and weight
        pass_trigger = [passTrigger, passTriggerMuon]
        num_part = [nmuon,nelec]


        jet_kinematics = [jet.pt_nom, jet.eta, jet.phi, jet.msoftdrop_nom]
        if isMC:
            genNorm = lumi*samples[self.sample_name]['xsec']/samples[self.sample_name]['ngen']
            nominal_w = inTree.readBranch('L1PreFiringWeight_Nom')*inTree.readBranch('genWeight')*inTree.readBranch('puWeight')*genNorm
            
            genWeight = [
                nominal_w,
                nominal_w*inTree.readBranch('puWeightUp')/inTree.readBranch('puWeight'),
                nominal_w*inTree.readBranch('puWeightDown')/inTree.readBranch('puWeight'),
                nominal_w*inTree.readBranch('L1PreFiringWeight_Up')/inTree.readBranch('L1PreFiringWeight_Nom'),
                nominal_w*inTree.readBranch('L1PreFiringWeight_Dn')/inTree.readBranch('L1PreFiringWeight_Nom'),
                nominal_w*top_pt_w,
                nominal_w,
                nominal_w*inTree.readBranch('PSWeight')[0],
                nominal_w*inTree.readBranch('PSWeight')[2],
                nominal_w*inTree.readBranch('PSWeight')[1],
                nominal_w*inTree.readBranch('PSWeight')[3],
                ]
            
            try:
                genWeight += [
                    nominal_w*inTree.readBranch('LHEScaleWeight')[0],
                    nominal_w*inTree.readBranch('LHEScaleWeight')[1],
                    nominal_w*inTree.readBranch('LHEScaleWeight')[3],
                    nominal_w*inTree.readBranch('LHEScaleWeight')[5],
                    nominal_w*inTree.readBranch('LHEScaleWeight')[7],
                    nominal_w*inTree.readBranch('LHEScaleWeight')[8],  
                ]
            except:
                #print("INFO:SCALE VARIATIONS MISSING")
                genWeight += 6*[nominal_w]

            jet_systematics = [jet.pt_jesTotalUp,jet.msoftdrop_jesTotalUp,
                               jet.pt_jesTotalDown,jet.msoftdrop_jesTotalDown,
                               jet.pt_jerUp,jet.msoftdrop_jerUp,
                               jet.pt_jerDown,jet.msoftdrop_jerDown,
                               jet.pt_nom,jet.msoftdrop_jmsUp,
                               jet.pt_nom,jet.msoftdrop_jmsDown,
                               jet.pt_nom,jet.msoftdrop_jmrUp,
                               jet.pt_nom,jet.msoftdrop_jmrDown,
                               ]
            
        else:
            genWeight = 17*[1.0]
            jet_systematics = 16*[1.0]
        

        z,theta,btag = get_softdrop_z_theta_btag(jet,SubJet)
        jet_tagging = [jet.nConstituents, jet.tau1, jet.tau2, jet.tau3, jet.tau4, 
                       jet.btagDeepB, jet.particleNetMD_Xbb/(jet.particleNetMD_QCD + jet.particleNetMD_Xbb),
                       z,theta]
                       #jet.particleNetMD_Xqq/(jet.particleNetMD_QCD + jet.particleNetMD_Xqq),
                       #jet.particleNetMD_Xcc/(jet.particleNetMD_QCD + jet.particleNetMD_Xcc)]
        

        cands_idxs = [FJCand.pFCandsIdx for FJCand in FatJetPFCands if FJCand.jetIdx == jet.idx] 

        jet_PFCands = []
        for idx in cands_idxs:
            cand = ROOT.Math.PtEtaPhiMVector(PFCands[idx].pt, PFCands[idx].eta, PFCands[idx].phi, PFCands[idx].mass)
            jet_PFCands.append([cand.Px(), cand.Py(), cand.Pz(), cand.E(), 
                PFCands[idx].d0, PFCands[idx].d0Err, PFCands[idx].dz, PFCands[idx].dzErr, PFCands[idx].charge, PFCands[idx].pdgId, PFCands[idx].puppiWeight])


        self.trigger_info[self.idx] = np.array(pass_trigger, dtype=np.int64)
        self.part_info[self.idx] = np.array(num_part, dtype=np.int64)
        self.weight_info[self.idx] = np.array(genWeight, dtype=np.float32)
        self.match_info[self.idx] = np.array([match], dtype=np.float32)
        self.jet_systematics[self.idx] = np.array(jet_systematics, dtype=np.float32)
        
        self.event_info[self.idx] = np.array(event_info, dtype=np.int64)
        self.jet_kinematics[self.idx] = np.array(jet_kinematics, dtype = np.float32)
        self.jet_tagging[self.idx] = np.array(jet_tagging, dtype = np.float32)
        
        jet_PFCands = self.sort_pfcands(np.array(jet_PFCands, dtype = np.float32).reshape(-1, 11))
        if(len(jet_PFCands) > self.n_pf_cands): jet_PFCands = jet_PFCands[:self.n_pf_cands]
        self.PFCands[self.idx,:len(jet_PFCands)] = jet_PFCands 

        self.idx +=1
        if(self.idx % self.batch_size == 0): self.write_out()


    def write_out(self):
        self.idx = 0
        print("Writing out batch %i \n" % self.nBatch)
        self.nBatch += 1
        write_size = self.event_info.shape[0]

        if(not self.first_write):
            self.first_write = True
            print("First write, creating dataset with name %s \n" % self.output_name)
            with h5py.File(self.output_name, "w") as f:
                f.create_dataset("event_info", data=self.event_info, chunks = True, maxshape=(None, self.event_info.shape[1]))
                f.create_dataset("jet_kinematics", data=self.jet_kinematics, chunks = True, maxshape=(None, self.jet_kinematics.shape[1]), compression = 'gzip')
                f.create_dataset("jet_tagging", data=self.jet_tagging, chunks = True, maxshape=(None, self.jet_tagging.shape[1]), compression = 'gzip')
                f.create_dataset("PFCands", data=self.PFCands, chunks = True, maxshape=(None, self.PFCands.shape[1], self.PFCands.shape[2]), compression='gzip')
                f.create_dataset("trigger_info", data=self.trigger_info, chunks = True, maxshape=(None, self.trigger_info.shape[1]))
                f.create_dataset("lepton_info", data=self.part_info, chunks = True, maxshape=(None, self.part_info.shape[1]))
                f.create_dataset("weight_info", data=self.weight_info, chunks = True, maxshape=(None, self.weight_info.shape[1]))
                f.create_dataset("match_info", data=self.match_info, chunks = True, maxshape=(None, self.match_info.shape[1]))
                f.create_dataset("jet_systematics", data=self.jet_systematics, chunks = True, maxshape=(None, self.jet_systematics.shape[1]))

        else:
            with h5py.File(self.output_name, "a") as f:
                append_h5(f,'event_info',self.event_info)
                append_h5(f,'jet_kinematics',self.jet_kinematics)
                append_h5(f,'jet_tagging',self.jet_tagging)
                append_h5(f,'PFCands',self.PFCands)
                append_h5(f,'trigger_info',self.trigger_info)
                append_h5(f,'lepton_info',self.part_info)
                append_h5(f,'weight_info',self.weight_info)
                append_h5(f,'match_info',self.match_info)
                append_h5(f,'jet_systematics',self.jet_systematics)
        self.reset()

    def final_write_out(self ):
        if self.idx == 0 and self.first_write:
            return
        if(self.idx < self.batch_size):
            print("Last batch only filled %i events, shortening arrays \n" % self.idx)
            self.PFCands = self.PFCands[:self.idx]
            self.jet_kinematics = self.jet_kinematics[:self.idx]
            self.jet_tagging = self.jet_tagging[:self.idx] 
            self.event_info = self.event_info[:self.idx]
            self.trigger_info = self.trigger_info[:self.idx]
            self.part_info = self.part_info[:self.idx]
            self.weight_info = self.weight_info[:self.idx]
            self.match_info = self.match_info[:self.idx]
            self.jet_systematics = self.jet_systematics[:self.idx] 

        self.write_out()




def NanoReader(inputFileNames=["in.root"], outputFileName="out.root", json = '', year = 2016, nEventsMax = -1, 
               sampleType = "data", gen_match = -1,cr = -1,  sort_pfcands=True, sample_name=None):
    
    if not ((sampleType == "MC") or (sampleType=="data")):
        print("Error! sampleType needs to be set to either data or MC! Please set correct option and retry.")
        sys.exit()
    
    #Applying standard data quality filters: https://twiki.cern.ch/twiki/bin/view/CMS/MissingETOptionalFiltersRun2#Analysis_Recommendations_for_ana
    filters = ["Flag_goodVertices",
    "Flag_globalSuperTightHalo2016Filter",
    "Flag_HBHENoiseFilter",
    "Flag_HBHENoiseIsoFilter",
    "Flag_EcalDeadCellTriggerPrimitiveFilter",
    "Flag_BadPFMuonFilter",
    "Flag_eeBadScFilter", 
    "Flag_CSCTightHaloFilter",
        ]

    if year == 2016:
        triggers = [
            # "HLT_AK8DiPFJet250_200_TrimMass30_BTagCSV_p20",
            # "HLT_AK8DiPFJet250_200_TrimMass30",
            # "HLT_AK8DiPFJet280_200_TrimMass30_BTagCSV_p087",
            # "HLT_AK8DiPFJet280_200_TrimMass30_BTagCSV_p20",
            "HLT_AK8DiPFJet280_200_TrimMass30",
            # "HLT_AK8DiPFJet300_200_TrimMass30_BTagCSV_p087",
            # "HLT_AK8DiPFJet300_200_TrimMass30_BTagCSV_p20",
            #"HLT_AK8DiPFJet300_200_TrimMass30",
            # "HLT_AK8PFHT600_TrimR0p1PT0p03Mass50_BTagCSV_p20",
            "HLT_AK8PFHT650_TrimR0p1PT0p03Mass50",
            "HLT_AK8PFHT700_TrimR0p1PT0p03Mass50",
            # "HLT_AK8PFHT750_TrimMass50",
            #"HLT_AK8PFHT800_TrimMass50",
            # "HLT_AK8PFJet140",
            # "HLT_AK8PFJet200",
            # "HLT_AK8PFJet260",
            # "HLT_AK8PFJet320",
            "HLT_AK8PFJet360_TrimMass30",
            # "HLT_AK8PFJet400",
            # "HLT_AK8PFJet40",
            "HLT_AK8PFJet450",
            # "HLT_AK8PFJet500",
            # "HLT_AK8PFJet60",
            # "HLT_AK8PFJet80",
            # "HLT_CaloJet500_NoJetID",
            # "HLT_DiCentralPFJet170_CFMax0p1",
            # "HLT_DiCentralPFJet170",
            # "HLT_DiCentralPFJet220_CFMax0p3",
            # "HLT_DiCentralPFJet330_CFMax0p5",
            # "HLT_DiCentralPFJet430",
            #"HLT_DiJetVBFMu_PassThrough",
            #"HLT_DiJetVBF_PassThrough",
            # "HLT_DiPFJetAve100_HFJEC",
            # "HLT_DiPFJetAve140",
            # "HLT_DiPFJetAve160_HFJEC",
            # "HLT_DiPFJetAve200",
            # "HLT_DiPFJetAve220_HFJEC",
            # "HLT_DiPFJetAve260",
            # "HLT_DiPFJetAve300_HFJEC",
            # "HLT_DiPFJetAve320",
            # "HLT_DiPFJetAve400",
            # "HLT_DiPFJetAve40",
            # "HLT_DiPFJetAve500",
            # "HLT_DiPFJetAve60_HFJEC",
            # "HLT_DiPFJetAve60",
            # "HLT_DiPFJetAve80_HFJEC",
            # "HLT_DiPFJetAve80",
            # "HLT_HT2000",
            # "HLT_HT2500",
            # "HLT_L1_TripleJet_VBF",
            # "HLT_PFHT125",
            # "HLT_PFHT200",
            # "HLT_PFHT250",
            # "HLT_PFHT300",
            # "HLT_PFHT350",
            # "HLT_PFHT400_SixJet30_DoubleBTagCSV_p056",
            # "HLT_PFHT400_SixJet30",
            # "HLT_PFHT400",
            # "HLT_PFHT450_SixJet40_BTagCSV_p056",
            # "HLT_PFHT450_SixJet40",
            # "HLT_PFHT475",
            # "HLT_PFHT550_4JetPt50",
            # "HLT_PFHT600",
            # "HLT_PFHT650_4JetPt50",
            "HLT_PFHT650_WideJetMJJ900DEtaJJ1p5",
            # "HLT_PFHT650_WideJetMJJ950DEtaJJ1p5",
            # "HLT_PFHT650",
            # "HLT_PFHT750_4JetPt50",
            # "HLT_PFHT750_4JetPt70",
            # "HLT_PFHT750_4JetPt80",
            # "HLT_PFHT800_4JetPt50",
            #"HLT_PFHT800",
            # "HLT_PFHT850_4JetPt50",
            "HLT_PFHT900",
            # "HLT_PFJet140",
            # "HLT_PFJet200",
            # "HLT_PFJet260",
            # "HLT_PFJet320",
            # "HLT_PFJet400",
            # "HLT_PFJet40",
            "HLT_PFJet450",
            #"HLT_PFJet500",
            # "HLT_PFJet60",
            # "HLT_PFJet80",
            # "HLT_QuadPFJet_VBF",
            # "HLT_SingleCentralPFJet170_CFMax0p1",
            #muon trigger
        ]
        trigger_muon = ["HLT_IsoMu24", "HLT_IsoTkMu24","HLT_Mu50", "HLT_TkMu50"]
    else:
        triggers = [
            'HLT_AK8PFHT800_TrimMass50',
            "HLT_AK8PFHT750_TrimMass50",
            "HLT_AK8PFJet360_TrimMass30",
            'HLT_AK8PFJet380_TrimMass30',
            "HLT_AK8PFJet450",
            "HLT_PFHT890",
            "HLT_PFJet450",

        ]
        
        trigger_muon = ["HLT_IsoMu24","HLT_Mu50"]
    nFiles = len(inputFileNames)
    print("Will run over %i files and output to %s " % (nFiles, outputFileName))
    count = 0
    saved = 0

#----------------- Begin loop over files ---------------------------------

    isMC = sampleType == "MC"

    if isMC and sample_name not in samples:
        raise ValueError("Unknown MC normalization sample: %s; add it to norms.py" % sample_name)
    out = Outputer(outputFileName, sample_type=sampleType, year = year, sample_name=sample_name)

    for fileName in inputFileNames:

        print("Opening file %s" % fileName)

        inputFile = TFile.Open(fileName)
        if(not inputFile): #check for null pointer
            print("Unable to open file %s, exting \n" % fileName)
            raise IOError("Unable to open ROOT file: " + fileName)

        #get input tree
        TTree = inputFile.Get("Events")

        # pre-skimming to good quality events based on json
        if(json != ''):
            elist,jsonFilter = preSkim(TTree, json)

            #number of events to be processed 
            nTotal = elist.GetN() if elist else TTree.GetEntries()
            
            print('Pre-select %d entries out of %s '%(nTotal,TTree.GetEntries()))


            inTree= InputTree(TTree, elist) 
        else:
            nTotal = TTree.GetEntries()
            inTree= InputTree(TTree) 
            print('Running over %i entries \n' % nTotal)


        # Grab event tree from nanoAOD
        eventBranch = inTree.GetBranch('event')
        treeEntries = eventBranch.GetEntries()

# -------- Begin Loop over tree-------------------------------------

        entries = inTree.entries
        for entry in xrange(entries):

            if count % 10000 == 0 :
                print('--------- Processing Event ' + str(count) +'   -- percent complete ' + str(100*count/nTotal/nFiles) + '% -- ')

            count +=1
            # Grab the event
            event = Event(inTree, entry)

            passTrigger = False
            for trig in triggers: passTrigger = passTrigger or inTree.readBranch(trig)
            passTriggerMuon = False
            for trig in trigger_muon: passTriggerMuon = passTriggerMuon or inTree.readBranch(trig)
            
            if passTrigger == False and passTriggerMuon == False: continue

            
            passFilter = True
            for fil in filters: passFilter = passFilter and inTree.readBranch(fil)
            if(not passFilter): continue
            

            FatJetPFCands = Collection(event, "FatJetPFCands")
            PFCands = Collection(event, "PFCands")
            SubJet = Collection(event, "SubJet")
            
            
            AK8Jets = Collection(event, "FatJet")

            Muons = Collection(event, "Muon")
            Electrons = Collection(event, "Electron")

            nmuon = 0
            sel_muon = None
            for i,muon in enumerate(Muons):
                #Tight ID
                if cr > 0:
                    muon_pt = 55
                else:
                    muon_pt = 15
                if((muon.pt > muon_pt) and (muon.pfRelIso04_all< 0.15) and abs(muon.eta) < 2.4 and (muon.tightId == True)):
                    nmuon +=1
                    sel_muon = muon
                    
            nelec = 0
            for i,elec in enumerate(Electrons):
                #Tight ID
                if((elec.pt > 15) and (elec.pfRelIso03_all< 0.15) and abs(elec.eta) < 2.4 and (elec.cutBased >= 1)):
                    if (
                            ((np.abs(elec.eta) < 1.4442) and (np.abs(elec.dxy) < 0.05) and (np.abs(elec.dz) < 0.1) )
                            or ((np.abs(elec.eta) > 1.5660) and (np.abs(elec.dxy) < 0.1) and (np.abs(elec.dz) < 0.2) )
                    ):
                        nelec +=1

            top_pt_w = 1.0        
            if(isMC and 'TTTo' in (sample_name or outputFileName)):                
                try:
                    gen_part1, gen_part2, W,antiW, q1a,q1b,b1, q2a,q2b,b2  = get_ttbar_gen_parts(event)
                    top_pt_w = np.sqrt(np.exp(0.0615-0.0005*(gen_part1.pt + gen_part2.pt)))
                    
                    
                except:
                    print("Failed to get top pt weight")
                



            #keep jets with pt > 300, tight id
            jet_min_pt = 300
        
            jet_index = 0

            for i,jet in enumerate(AK8Jets):
                jet.idx = i
                #jetId : bit1 = loose, bit2 = tight, bit3 = tightLepVeto
                #want tight id and tightLepVeto
                if(jet.pt_nom > jet_min_pt and (jet.jetId == 6) and abs(jet.eta) < 2.5):
                    nb = 0
                    if cr > 0:
                        nb = match_ak4jet(event,jet,sel_muon)
                        if nb ==0 : break
                    if(isMC and "TTTo" in (sample_name or outputFileName)):
                        gen_part1, gen_part2, W,antiW, q1a,q1b,b1, q2a,q2b,b2  = get_ttbar_gen_parts(event)
                        match1 = check_matching(jet, q1a, q1b, b1)
                        match2 = check_matching(jet, q2a, q2b, b2)
                        match  = max(match1,match2)

                    else:
                        match = 0
                    if(gen_match > 0):
                        if not (isMC and "TTTo" in (sample_name or outputFileName)):
                            raise ValueError("Generator matching requested for non-ttbar sample")
                        #require gen match
                        if(gen_match == top_ID):
                            match1 = check_matching(jet, q1a, q1b, b1) == 2
                            match2 = check_matching(jet, q2a, q2b, b2) == 2
                        else:
                            match1 = check_matching(jet, q1a, q1b, None)
                            match2 = False

                        if(match1 or match2):
                            out.fill_jet(inTree, jet, PFCands, FatJetPFCands,SubJet, passTrigger, passTriggerMuon, nmuon, nelec, top_pt_w,match, isMC)
                            saved+=1

                    else:
                        out.fill_jet(inTree, jet, PFCands, FatJetPFCands, SubJet, passTrigger, passTriggerMuon, nmuon, nelec, top_pt_w,match,isMC)
                        saved+=1
                    if cr > 0:
                        #take only the leading AK8
                        break


            if(nEventsMax > 0 and saved >= nEventsMax): break

    print("Done. Selected %i jets in %i events \n" % (saved, count))
    out.final_write_out()
    with h5py.File(outputFileName, "a") as metadata:
        metadata.attrs["cr"] = int(cr > 0)

    print("Outputed to %s" % outputFileName)
    return saved

if(__name__ == "__main__"):

    parser = OptionParser()
    parser.add_option("--sample", default=None, help="Explicit MC normalization sample key from norms.py")
    parser.add_option("--sample_type", default = "data", help="MC or data")
    parser.add_option("--gen_match", default =0, type =int, help="Require gen match to specific particle ID")
    parser.add_option("--cr", default =0, type =int, help="Require gen match to specific particle ID")
    parser.add_option("-i", "--input", dest = "fin", default = '', help="Input file name")
    parser.add_option("-o", "--output", dest = "fout", default = 'test.h5', help="Output file name")
    parser.add_option("-j", "--json", default = '', help="Json file name")
    parser.add_option("-y", "--year", type=int, default = 2016, help="Year the sample corresponds to")
    parser.add_option("-n", "--nEvents",  type=int, default = -1, help="Maximum number of events to output (-1 to run over whole file)")

    options, args = parser.parse_args()

    NanoReader(inputFileNames = [options.fin], outputFileName = options.fout, json = options.json, year = options.year, nEventsMax = options.nEvents, 
               sampleType = options.sample_type, gen_match = options.gen_match,
               cr = options.cr, sample_name=options.sample)


