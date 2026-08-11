LOOP mat_ap=1,2
LOOP mat_period=1,4

if (mat_ap = 1)  mat_ap_str = 'pa'
if (mat_ap = 2)  mat_ap_str = 'ap'

if (mat_period = 1) mat_period_str1 = 'AM'
if (mat_period = 2) mat_period_str1 = 'MD'
if (mat_period = 3) mat_period_str1 = 'PM'
if (mat_period = 4) mat_period_str1 = 'EV'

if (mat_period = 1) mat_period_str2 = 'am3hr'
if (mat_period = 2) mat_period_str2 = 'md6hr'
if (mat_period = 3) mat_period_str2 = 'pm3hr'
if (mat_period = 4) mat_period_str2 = 'ev12hr'



RUN PGM=MATRIX MSG='Reassign WF TAZ to USTM TAZ for @mat_ap_str@-@mat_period_str2@'

FILEI ZDATI[1] = 'inputs/wf-pa-ap-trips/_lookup_ustmtaz_wftaz.dbf'
FILEI MATI[1] = "inputs/wf-pa-ap-trips/@mat_ap_str@_@mat_period_str2@_managed.mtx"
FILEO MATO[1] = "inputs/wf-pa-ap-trips/@mat_ap_str@_@mat_period_str2@_managed_ustm.mtx",
    mo=101-106,111-114,121-125, 
    name=HBW, HBO, NHB, HBS, HBC, REC, 
         Ext_Bus, Ext_Oth, Ext_Rec, Ext_MD,
         SH_LT, SH_MD, SH_HV, LH_MD, LH_HV

ZONES   = 9855

mw[101] = mi.1.HBW_DA_NON + mi.1.HBW_SR_NON + mi.1.HBW_SR_HOV + mi.1.HBW_SR_TOL + mi.1.HBW_DA_TOL
mw[102] = mi.1.HBO_DA_NON + mi.1.HBO_SR_NON + mi.1.HBO_SR_HOV + mi.1.HBO_SR_TOL + mi.1.HBO_DA_TOL
mw[103] = mi.1.NHB_DA_NON + mi.1.NHB_SR_NON + mi.1.NHB_SR_HOV + mi.1.NHB_SR_TOL + mi.1.NHB_DA_TOL
mw[104] = mi.1.HBS_DriveSelf_Pr + mi.1.HBS_DriveSelf_Sc + HBS_DropOff_Pr + HBS_DropOff_Sc + mi.1.SchoolBus_PR + mi.1.SchoolBus_Sc
mw[105] = mi.1.HBC_DA_NON + mi.1.HBC_SR_NON + mi.1.HBC_SR_HOV + mi.1.HBC_SR_TOL + mi.1.HBC_DA_TOL
mw[106] = 0

mw[111] = 0
mw[112] = 0
mw[113] = 0
mw[114] = 0

mw[121] = mi.1.SH_LT
mw[122] = mi.1.SH_MD
mw[123] = mi.1.SH_HV
mw[124] = 0
mw[125] = 0

;reassign to USTM TAZs
RENUMBER ZONEO=zi.1.ZUSTM, missingzi=m, missingzo=w

ENDRUN


RUN PGM=MATRIX MSG='Add WF Trips to USTM Trips for @mat_ap_str@-@mat_period_str2@'

FILEI MATI[1] = "intermediate/temp_@mat_ap_str@_OD_Veh_@mat_period_str1@.mtx"
FILEI MATI[2] = "inputs/wf-pa-ap-trips/@mat_ap_str@_@mat_period_str2@_managed_ustm.mtx"

FILEO MATO[1] = "outputs/@mat_ap_str@_OD_Veh_@mat_period_str1@.mtx", 
    mo=101-106,111-114,121-125, 
    name=HBW, HBO, NHB, HBS, HBC, REC, 
         Ext_Bus, Ext_Oth, Ext_Rec, Ext_MD,
         SH_LT, SH_MD, SH_HV, LH_MD, LH_HV


    ;Cluster: distribute intrastep processings
    DistributeIntrastep MaxProcesses=16
    
    ;set MATRIX parameters
    ZONES   = 9855
    ZONEMSG = 5
    
    ;add together PA matrices to OD matrices by time period =======================================================
    
    mw[101] = mi.1.HBW + mi.2.HBW
    
    mw[102] = mi.1.HBO + mi.2.HBO
    mw[103] = mi.1.NHB + mi.2.NHB
    mw[104] = mi.1.HBS + mi.2.HBS
    mw[105] = mi.1.HBC + mi.2.HBC
    mw[106] = mi.1.REC + mi.2.REC
    
    mw[111] = mi.1.Ext_Bus + mi.2.Ext_Bus
    mw[112] = mi.1.Ext_Oth + mi.2.Ext_Oth
    mw[113] = mi.1.Ext_Rec + mi.2.Ext_Rec
    mw[114] = mi.1.Ext_MD  + mi.2.Ext_MD
    
    mw[121] = mi.1.SH_LT + mi.2.SH_LT
    mw[122] = mi.1.SH_MD + mi.2.SH_MD
    mw[123] = mi.1.SH_HV + mi.2.SH_HV
    mw[124] = mi.1.LH_MD + mi.2.LH_MD
    mw[125] = mi.1.LH_HV + mi.2.LH_HV
    
    
ENDRUN

ENDLOOP
ENDLOOP