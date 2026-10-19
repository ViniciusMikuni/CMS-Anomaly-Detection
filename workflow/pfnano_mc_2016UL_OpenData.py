import os
# Auto generated configuration file
# using: 
# Revision: 1.19 
# Source: /local/reps/CMSSW/CMSSW/Configuration/Applications/python/ConfigBuilder.py,v 
# with command line options: nano_mc_2016_ULPostVFP --mc --eventcontent NANOAODSIM --datatier NANOAODSIM --step NANO --conditions 106X_mcRun2_asymptotic_v17 --era Run2_2016,run2_nanoAOD_106Xv2 --customise_commands=process.add_(cms.Service('InitRootHandlers', EnableIMT = cms.untracked.bool(False))) --nThreads 4 --fileout file:nano_mc2016post.root --filein /store/mc/RunIISummer20UL16MiniAODv2/QCD_HT1000to1500_TuneCP5_PSWeights_13TeV-madgraph-pythia8/MINIAODSIM/106X_mcRun2_asymptotic_v17-v1/2520000/302EA76A-383E-9A44-88A4-B5832C5BB88E.root -n 100  
import FWCore.ParameterSet.Config as cms

from Configuration.Eras.Era_Run2_2016_cff import Run2_2016
from Configuration.Eras.Modifier_run2_nanoAOD_106Xv2_cff import run2_nanoAOD_106Xv2
import FWCore.ParameterSet.VarParsing as VarParsing

process = cms.Process('NANO',Run2_2016,run2_nanoAOD_106Xv2)

# import of standard configurations
process.load('Configuration.StandardSequences.Services_cff')
process.load('SimGeneral.HepPDTESSource.pythiapdt_cfi')
process.load('FWCore.MessageService.MessageLogger_cfi')
process.load('Configuration.EventContent.EventContent_cff')
process.load('SimGeneral.MixingModule.mixNoPU_cfi')
process.load('Configuration.StandardSequences.GeometryRecoDB_cff')
process.load('Configuration.StandardSequences.MagneticField_cff')
process.load('PhysicsTools.NanoAOD.nano_cff')
process.load('Configuration.StandardSequences.EndOfProcess_cff')
process.load('Configuration.StandardSequences.FrontierConditions_GlobalTag_cff')

process.MessageLogger = cms.Service("MessageLogger",
    destinations = cms.untracked.vstring('cerr'),
    cerr = cms.untracked.PSet(
        threshold = cms.untracked.string('ERROR'),
        ERROR   = cms.untracked.PSet(limit = cms.untracked.int32(-1)),
        WARNING = cms.untracked.PSet(limit = cms.untracked.int32(0)),
        INFO    = cms.untracked.PSet(limit = cms.untracked.int32(0)),
        DEBUG   = cms.untracked.PSet(limit = cms.untracked.int32(0))
    ),
)


options = VarParsing.VarParsing ('analysis')
#options.inputFiles = "test.root"
options.maxEvents = -1
options.parseArguments()


print(options)

with open(options.inputFiles[0], 'r') as f:
    # Strip whitespace and backslash line continuations
    file_list = [line.strip().rstrip('\\') for line in f if line.strip()]
print(file_list)

process.maxEvents = cms.untracked.PSet(
    input = cms.untracked.int32(options.maxEvents)
)

# Input source
process.source = cms.Source("PoolSource",
    #fileNames = cms.untracked.vstring('file:QCD_Pt_600to800_TuneCP5_13TeV_pythia8/003CC255-3EB5-4846-AA90-3A2316904C5C.root'),
    #fileNames = cms.untracked.vstring('root://eospublic.cern.ch//eos/opendata/cms/mc/RunIISummer20UL16MiniAODv2/ZprimeToTT_M1400_W14_TuneCP2_PSweights_13TeV-madgraph-pythiaMLM-pythia8/MINIAODSIM/106X_mcRun2_asymptotic_v17-v1/280000/1566E899-1621-574A-9ABB-70BFB25BC2AC.root'),
    #fileNames = cms.untracked.vstring("QCD/QCD_Pt300/9DB532F2-E4B1-7949-8782-241ADA37B8F6.root"),
    fileNames = cms.untracked.vstring(file_list),
    secondaryFileNames = cms.untracked.vstring()
)

process.options = cms.untracked.PSet(

)

# Production Info
process.configurationMetadata = cms.untracked.PSet(
    annotation = cms.untracked.string('nano_mc_2016_ULPostVFP nevts:100'),
    name = cms.untracked.string('Applications'),
    version = cms.untracked.string('$Revision: 1.19 $')
)

# Output definition
output_name = 'file:' + (options.outputFile if options.outputFile else __import__('os').path.splitext(options.inputFiles[0])[0] + '.root')

process.NANOAODSIMoutput = cms.OutputModule("NanoAODOutputModule",
    compressionAlgorithm = cms.untracked.string('LZMA'),
    compressionLevel = cms.untracked.int32(9),
    dataset = cms.untracked.PSet(
        dataTier = cms.untracked.string('NANOAODSIM'),
        filterName = cms.untracked.string('')
    ),
    fileName = cms.untracked.string(output_name),
    outputCommands = process.NANOAODSIMEventContent.outputCommands
)

# Additional output definition

# Other statements
from Configuration.AlCa.GlobalTag import GlobalTag
process.GlobalTag = GlobalTag(process.GlobalTag, '106X_mcRun2_asymptotic_v17', '')

# Path and EndPath definitions
process.nanoAOD_step = cms.Path(process.nanoSequenceMC)
process.endjob_step = cms.EndPath(process.endOfProcess)
process.NANOAODSIMoutput_step = cms.EndPath(process.NANOAODSIMoutput)

# Schedule definition
process.schedule = cms.Schedule(process.nanoAOD_step,process.endjob_step,process.NANOAODSIMoutput_step)
from PhysicsTools.PatAlgos.tools.helpers import associatePatAlgosToolsTask
associatePatAlgosToolsTask(process)

process.options.numberOfThreads=cms.untracked.uint32(int(os.environ.get('CMS_OD_CPUS_PER_TASK', os.environ.get('SLURM_CPUS_PER_TASK', '1'))))
process.options.numberOfStreams=cms.untracked.uint32(0)
process.options.numberOfConcurrentLuminosityBlocks=cms.untracked.uint32(1)

# customisation of the process.

# Automatic addition of the customisation function from PhysicsTools.NanoAOD.nano_cff
from PhysicsTools.NanoAOD.nano_cff import nanoAOD_customizeMC 

#call to customisation function nanoAOD_customizeMC imported from PhysicsTools.NanoAOD.nano_cff
process = nanoAOD_customizeMC(process)


from PhysicsTools.PFNano.pfnano_cff import PFnano_customizeMC_AK8JetsOnly
process = PFnano_customizeMC_AK8JetsOnly(process)

# End of customisation functions

# Customisation from command line

process.add_(cms.Service('InitRootHandlers', EnableIMT = cms.untracked.bool(False)))
# Add early deletion of temporary data products to reduce peak memory need
from Configuration.StandardSequences.earlyDeleteSettings_cff import customiseEarlyDelete
process = customiseEarlyDelete(process)
# End adding early deletion
