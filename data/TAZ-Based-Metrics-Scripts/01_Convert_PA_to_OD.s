

RUN PGM=MATRIX MSG='Highway Assign: Convert PA to OD'

FILEI MATI[1] = "inputs/pa_MC_motorized.mtx"

FILEO MATO[1] = "intermediate/temp_pa_OD_Veh_AM.mtx",
    mo=101-106,111-114,121-127, 
    name=HBW, HBO, NHB, HBS, HBC, REC, 
         Ext_Bus, Ext_Oth, Ext_Rec, Ext_MD,
         SH_LT, SH_MD, SH_HV, LH_MD, LH_HV, Tot_MD, Tot_HV

FILEO MATO[2] = "intermediate/temp_pa_OD_Veh_MD.mtx",
    mo=201-206,211-214,221-227, 
    name=HBW, HBO, NHB, HBS, HBC, REC, 
         Ext_Bus, Ext_Oth, Ext_Rec, Ext_MD,
         SH_LT, SH_MD, SH_HV, LH_MD, LH_HV, Tot_MD, Tot_HV

FILEO MATO[3] = "intermediate/temp_pa_OD_Veh_PM.mtx",
    mo=301-306,311-314,321-327, 
    name=HBW, HBO, NHB, HBS, HBC, REC, 
         Ext_Bus, Ext_Oth, Ext_Rec, Ext_MD,
         SH_LT, SH_MD, SH_HV, LH_MD, LH_HV, Tot_MD, Tot_HV

FILEO MATO[4] = "intermediate/temp_pa_OD_Veh_EV.mtx",
    mo=401-406,411-414,421-427, 
    name=HBW, HBO, NHB, HBS, HBC, REC, 
         Ext_Bus, Ext_Oth, Ext_Rec, Ext_MD,
         SH_LT, SH_MD, SH_HV, LH_MD, LH_HV, Tot_MD, Tot_HV

FILEO MATO[5] = "intermediate/temp_pa_OD_Veh_PM1hr.mtx",
    mo=501-506,511-514,521-527, 
    name=HBW, HBO, NHB, HBS, HBC, REC, 
         Ext_Bus, Ext_Oth, Ext_Rec, Ext_MD,
         SH_LT, SH_MD, SH_HV, LH_MD, LH_HV, Tot_MD, Tot_HV

FILEO MATO[6] = "intermediate/temp_ap_OD_Veh_AM.mtx",
    mo=151-156,161-164,171-177, 
    name=HBW, HBO, NHB, HBS, HBC, REC, 
         Ext_Bus, Ext_Oth, Ext_Rec, Ext_MD,
         SH_LT, SH_MD, SH_HV, LH_MD, LH_HV, Tot_MD, Tot_HV

FILEO MATO[7] = "intermediate/temp_ap_OD_Veh_MD.mtx",
    mo=251-256,261-264,271-277, 
    name=HBW, HBO, NHB, HBS, HBC, REC, 
         Ext_Bus, Ext_Oth, Ext_Rec, Ext_MD,
         SH_LT, SH_MD, SH_HV, LH_MD, LH_HV, Tot_MD, Tot_HV

FILEO MATO[8] = "intermediate/temp_ap_OD_Veh_PM.mtx",
    mo=351-356,361-364,371-377, 
    name=HBW, HBO, NHB, HBS, HBC, REC, 
         Ext_Bus, Ext_Oth, Ext_Rec, Ext_MD,
         SH_LT, SH_MD, SH_HV, LH_MD, LH_HV, Tot_MD, Tot_HV

FILEO MATO[9] = "intermediate/temp_ap_OD_Veh_EV.mtx",
    mo=451-456,461-464,471-477, 
    name=HBW, HBO, NHB, HBS, HBC, REC, 
         Ext_Bus, Ext_Oth, Ext_Rec, Ext_MD,
         SH_LT, SH_MD, SH_HV, LH_MD, LH_HV, Tot_MD, Tot_HV

FILEO MATO[10] = "intermediate/temp_ap_OD_Veh_PM1hr.mtx",
    mo=551-556,561-564,571-577, 
    name=HBW, HBO, NHB, HBS, HBC, REC, 
         Ext_Bus, Ext_Oth, Ext_Rec, Ext_MD,
         SH_LT, SH_MD, SH_HV, LH_MD, LH_HV, Tot_MD, Tot_HV
 
    ;Cluster: distribute intrastep processing
    DistributeIntrastep MaxProcesses=16
    
    
    ;set MATRIX parameters
    ZONEMSG = 5
    
    READ FILE = "inputs/GeneralParameters.block"
    
    ;calculate diunal PA & AP factors (% in Period * % in Direction) =========================================
    if (I=FIRSTZONE)
        ;PA factors ----------------------------------------------------------------
        Fac_AM_PA_HBW = HBW_AM_Pct * HBW_AM_PA
        Fac_MD_PA_HBW = HBW_MD_Pct * HBW_MD_PA
        Fac_PM_PA_HBW = HBW_PM_Pct * HBW_PM_PA
        Fac_EV_PA_HBW = HBW_EV_Pct * HBW_EV_PA
        
        Fac_AM_PA_HBO = HBO_AM_Pct * HBO_AM_PA
        Fac_MD_PA_HBO = HBO_MD_Pct * HBO_MD_PA
        Fac_PM_PA_HBO = HBO_PM_Pct * HBO_PM_PA
        Fac_EV_PA_HBO = HBO_EV_Pct * HBO_EV_PA
        
        Fac_AM_PA_NHB = NHB_AM_Pct * NHB_AM_PA
        Fac_MD_PA_NHB = NHB_MD_Pct * NHB_MD_PA
        Fac_PM_PA_NHB = NHB_PM_Pct * NHB_PM_PA
        Fac_EV_PA_NHB = NHB_EV_Pct * NHB_EV_PA
        
        Fac_AM_PA_HBS = HBS_AM_Pct * HBS_AM_PA
        Fac_MD_PA_HBS = HBS_MD_Pct * HBS_MD_PA
        Fac_PM_PA_HBS = HBS_PM_Pct * HBS_PM_PA
        Fac_EV_PA_HBS = HBS_EV_Pct * HBS_EV_PA
        
        Fac_AM_PA_HBC = HBC_AM_Pct * HBC_AM_PA
        Fac_MD_PA_HBC = HBC_MD_Pct * HBC_MD_PA
        Fac_PM_PA_HBC = HBC_PM_Pct * HBC_PM_PA
        Fac_EV_PA_HBC = HBC_EV_Pct * HBC_EV_PA
        
        Fac_AM_PA_Rec = Rec_AM_Pct * Rec_AM_PA
        Fac_MD_PA_Rec = Rec_MD_Pct * Rec_MD_PA
        Fac_PM_PA_Rec = Rec_PM_Pct * Rec_PM_PA
        Fac_EV_PA_Rec = Rec_EV_Pct * Rec_EV_PA
        
        Fac_AM_PA_Ext = Ext_AM_Pct * Ext_AM_PA
        Fac_MD_PA_Ext = Ext_MD_Pct * Ext_MD_PA
        Fac_PM_PA_Ext = Ext_PM_Pct * Ext_PM_PA
        Fac_EV_PA_Ext = Ext_EV_Pct * Ext_EV_PA
        
        Fac_AM_PA_TR  = TR_AM_Pct  * TR_AM_PA
        Fac_MD_PA_TR  = TR_MD_Pct  * TR_MD_PA
        Fac_PM_PA_TR  = TR_PM_Pct  * TR_PM_PA
        Fac_EV_PA_TR  = TR_EV_Pct  * TR_EV_PA
        
        
        ;AP factors ----------------------------------------------------------------
        Fac_AM_AP_HBW = HBW_AM_Pct * (1 - HBW_AM_PA)
        Fac_MD_AP_HBW = HBW_MD_Pct * (1 - HBW_MD_PA)
        Fac_PM_AP_HBW = HBW_PM_Pct * (1 - HBW_PM_PA)
        Fac_EV_AP_HBW = HBW_EV_Pct * (1 - HBW_EV_PA)
        
        Fac_AM_AP_HBO = HBO_AM_Pct * (1 - HBO_AM_PA)
        Fac_MD_AP_HBO = HBO_MD_Pct * (1 - HBO_MD_PA)
        Fac_PM_AP_HBO = HBO_PM_Pct * (1 - HBO_PM_PA)
        Fac_EV_AP_HBO = HBO_EV_Pct * (1 - HBO_EV_PA)
        
        Fac_AM_AP_NHB = NHB_AM_Pct * (1 - NHB_AM_PA)
        Fac_MD_AP_NHB = NHB_MD_Pct * (1 - NHB_MD_PA)
        Fac_PM_AP_NHB = NHB_PM_Pct * (1 - NHB_PM_PA)
        Fac_EV_AP_NHB = NHB_EV_Pct * (1 - NHB_EV_PA)
        
        Fac_AM_AP_HBS = HBS_AM_Pct * (1 - HBS_AM_PA)
        Fac_MD_AP_HBS = HBS_MD_Pct * (1 - HBS_MD_PA)
        Fac_PM_AP_HBS = HBS_PM_Pct * (1 - HBS_PM_PA)
        Fac_EV_AP_HBS = HBS_EV_Pct * (1 - HBS_EV_PA)
        
        Fac_AM_AP_HBC = HBC_AM_Pct * (1 - HBC_AM_PA)
        Fac_MD_AP_HBC = HBC_MD_Pct * (1 - HBC_MD_PA)
        Fac_PM_AP_HBC = HBC_PM_Pct * (1 - HBC_PM_PA)
        Fac_EV_AP_HBC = HBC_EV_Pct * (1 - HBC_EV_PA)
        
        Fac_AM_AP_Rec = Rec_AM_Pct * (1 - Rec_AM_PA)
        Fac_MD_AP_Rec = Rec_MD_Pct * (1 - Rec_MD_PA)
        Fac_PM_AP_Rec = Rec_PM_Pct * (1 - Rec_PM_PA)
        Fac_EV_AP_Rec = Rec_EV_Pct * (1 - Rec_EV_PA)
        
        Fac_AM_AP_Ext = Ext_AM_Pct * (1 - Ext_AM_PA)
        Fac_MD_AP_Ext = Ext_MD_Pct * (1 - Ext_MD_PA)
        Fac_PM_AP_Ext = Ext_PM_Pct * (1 - Ext_PM_PA)
        Fac_EV_AP_Ext = Ext_EV_Pct * (1 - Ext_EV_PA)
        
        Fac_AM_AP_TR  = TR_AM_Pct  * (1 - TR_AM_PA )
        Fac_MD_AP_TR  = TR_MD_Pct  * (1 - TR_MD_PA )
        Fac_PM_AP_TR  = TR_PM_Pct  * (1 - TR_PM_PA )
        Fac_EV_AP_TR  = TR_EV_Pct  * (1 - TR_EV_PA )  
    
    endif  ;i=FIRSTZONE
    
    
    ;read in trips ===========================================================================================
    ;read in mode choice person trips & convert person trips to vehicle trips
    mw[01] = mi.1.HBW          / VEH_OCCUPANCY_HBW
    mw[02] = mi.1.HBO          / VEH_OCCUPANCY_HBO
    mw[03] = mi.1.NHB          / VEH_OCCUPANCY_NHB
    
    mw[05] = mi.1.HBC          / VEH_OCCUPANCY_HBC
    mw[06] = mi.1.Rec          / VEH_OCCUPANCY_Rec 
    
    mw[07] = mi.1.HBSch_Drv    / VEH_OCCUPANCY_HBSch    ;drive
    mw[08] = mi.1.HBSch_Drp    / VEH_OCCUPANCY_HBSch    ;drop off / pick up
    mw[09] = mi.1.HBSch_Bus    / Schoolbus_VO           ;schoolbus
    
    ;read in external vehicle trips
    mw[11] = mi.1.Ext_Bus
    mw[12] = mi.1.Ext_Oth
    mw[13] = mi.1.Ext_Rec
    mw[14] = mi.1.Ext_MD
    
    ;read in short and long haul CV and truck trips
    mw[21] = mi.1.SH_LT
    mw[22] = mi.1.SH_MD
    mw[23] = mi.1.SH_HV
    
    mw[24] = mi.1.LH_MD
    mw[25] = mi.1.LH_HV
    
    
    ;read in TRANSPOSE of mode choice person trips & convert person trips to vehicle trips
    mw[51] = mi.1.HBW.T        / VEH_OCCUPANCY_HBW
    mw[52] = mi.1.HBO.T        / VEH_OCCUPANCY_HBO
    mw[53] = mi.1.NHB.T        / VEH_OCCUPANCY_NHB
    
    mw[55] = mi.1.HBC.T        / VEH_OCCUPANCY_HBC
    mw[56] = mi.1.Rec.T        / VEH_OCCUPANCY_Rec 
    
    mw[57] = mi.1.HBSch_Drv.T  / VEH_OCCUPANCY_HBSch    ;drive
    mw[58] = mi.1.HBSch_Drp.T  / VEH_OCCUPANCY_HBSch    ;drop off / pick up
    mw[59] = mi.1.HBSch_Bus.T  / Schoolbus_VO           ;schoolbus
    
    ;read in TRANSPOSE of external vehicle trips
    mw[61] = mi.1.Ext_Bus.T
    mw[62] = mi.1.Ext_Oth.T
    mw[63] = mi.1.Ext_Rec.T
    mw[64] = mi.1.Ext_MD.T
    
    ;read in TRANSPOSE o short haul CV and truck trips (note: long haul already in OD format)
    mw[71] = mi.1.SH_LT.T
    mw[72] = mi.1.SH_MD.T
    mw[73] = mi.1.SH_HV.T
    
    ;mw[74] = mi.1.LH_MD.T
    ;mw[75] = mi.1.LH_HV.T
    
    
    ;convert PA matrices to OD matrices by time period =======================================================
    ;AM Peak -----------------------------------------------------------------------------
    ;person trips
    mw[101] = mw[01] * Fac_AM_PA_HBW    
    mw[151] = mw[51] * Fac_AM_AP_HBW                          ;HBW

    mw[102] = mw[02] * Fac_AM_PA_HBO
    mw[152] = mw[52] * Fac_AM_AP_HBO                          ;HBO

    mw[103] = mw[03] * Fac_AM_PA_NHB
    mw[153] = mw[53] * Fac_AM_AP_NHB                          ;NHB
                                        
    mw[104] = mw[07] * Fac_AM_PA_HBS + (mw[08] * HBS_AM_Pct)
    mw[154] = mw[57] * Fac_AM_AP_HBS + (mw[58] * HBS_AM_Pct) ;HBSch drive + HBSch drop off

    mw[105] = mw[05] * Fac_AM_PA_HBC
    mw[155] = mw[55] * Fac_AM_AP_HBC                         ;HBC

    mw[106] = mw[06] * Fac_AM_PA_Rec
    mw[156] = mw[56] * Fac_AM_AP_Rec                         ;Rec
     
    ;external trips
    mw[111] = mw[11] * Fac_AM_PA_Ext    
    mw[161] = mw[61] * Fac_AM_AP_Ext                         ;Ext_Bus

    mw[112] = mw[12] * Fac_AM_PA_Ext
    mw[162] = mw[62] * Fac_AM_AP_Ext                         ;Ext_Oth

    mw[113] = mw[13] * Fac_AM_PA_Ext
    mw[163] = mw[63] * Fac_AM_AP_Ext                         ;Ext_Rec

    mw[114] = mw[14] * Fac_AM_PA_Ext
    mw[164] = mw[64] * Fac_AM_AP_Ext                         ;Ext_MD 
    
    ;short and long haul CV and truck trips
    mw[121] = mw[21] * Fac_AM_PA_TR
    mw[171] = mw[71] * Fac_AM_AP_TR                          ;SH_LT

    mw[122] = mw[22] * Fac_AM_PA_TR
    mw[172] = mw[72] * Fac_AM_AP_TR                          ;SH_MD

    mw[123] = mw[23] * Fac_AM_PA_TR
    mw[173] = mw[73] * Fac_AM_AP_TR                          ;SH_HV
    
    mw[124] = mw[24] * TR_AM_Pct * .5
    mw[174] = mw[24] * TR_AM_Pct * .5                        ;LH_MD

    mw[125] = mw[25] * TR_AM_Pct * .5
    mw[175] = mw[25] * TR_AM_Pct * .5                        ;LH_HV
    
    ;add schoolbus trips to SH_MD trip purpose
    mw[109] = mw[09] * Fac_AM_PA_HBS
    mw[159] = mw[59] * Fac_AM_PA_HBS                         ;schoolbus (add to SH_MD)

    mw[122] = mw[122] + mw[109]
    mw[172] = mw[172] + mw[159]
    
    ;sum total MD and HV
    mw[126] = mw[114] +                                      ;Ext_MD  
              mw[122] +                                      ;SH_MD
              mw[124]                                        ;SH_MD
    mw[176] = mw[164] +                                      ;Ext_MD  
              mw[172] +                                      ;SH_MD
              mw[174]                                        ;SH_MD
    
    mw[127] = mw[123] +                                      ;LH_MD
              mw[125]                                        ;LH_MD
    mw[177] = mw[173] +                                      ;LH_MD
              mw[175]                                        ;LH_MD
    
    
    ;MD Peak -----------------------------------------------------------------------------
    ;person trips
    mw[201] = mw[01] * Fac_MD_PA_HBW    
    mw[251] = mw[51] * Fac_MD_AP_HBW                         ;HBW

    mw[202] = mw[02] * Fac_MD_PA_HBO
    mw[252] = mw[52] * Fac_MD_AP_HBO                         ;HBO

    mw[203] = mw[03] * Fac_MD_PA_NHB
    mw[253] = mw[53] * Fac_MD_AP_NHB                         ;NHB

    mw[204] = mw[07] * Fac_MD_PA_HBS + (mw[08] * HBS_MD_Pct)
    mw[254] = mw[57] * Fac_MD_AP_HBS + (mw[58] * HBS_MD_Pct) ;HBSch drive + HBSch drop off

    mw[205] = mw[05] * Fac_MD_PA_HBC
    mw[255] = mw[55] * Fac_MD_AP_HBC                         ;HBC

    mw[206] = mw[06] * Fac_MD_PA_Rec
    mw[256] = mw[56] * Fac_MD_AP_Rec                         ;Rec
     
    ;external trips
    mw[211] = mw[11] * Fac_MD_PA_Ext    
    mw[261] = mw[61] * Fac_MD_AP_Ext                         ;Ext_Bus

    mw[212] = mw[12] * Fac_MD_PA_Ext
    mw[262] = mw[62] * Fac_MD_AP_Ext                         ;Ext_Oth

    mw[213] = mw[13] * Fac_MD_PA_Ext
    mw[263] = mw[63] * Fac_MD_AP_Ext                         ;Ext_Rec

    mw[214] = mw[14] * Fac_MD_PA_Ext
    mw[264] = mw[64] * Fac_MD_AP_Ext                         ;Ext_MD 
    
    ;short and long haul CV and truck trips
    mw[221] = mw[21] * Fac_MD_PA_TR
    mw[271] = mw[71] * Fac_MD_AP_TR                          ;SH_LT

    mw[222] = mw[22] * Fac_MD_PA_TR
    mw[272] = mw[72] * Fac_MD_AP_TR                          ;SH_MD

    mw[223] = mw[23] * Fac_MD_PA_TR
    mw[273] = mw[73] * Fac_MD_AP_TR                          ;SH_HV
    
    mw[224] = mw[24] * TR_MD_Pct * .5
    mw[274] = mw[24] * TR_MD_Pct * .5                        ;LH_MD

    mw[225] = mw[25] * TR_MD_Pct * .5
    mw[275] = mw[25] * TR_MD_Pct * .5                        ;LH_HV
    
    ;add schoolbus trips to SH_MD trip purpose
    mw[209] = mw[09] * Fac_MD_PA_HBS
    mw[259] = mw[59] * Fac_MD_PA_HBS                         ;schoolbus (add to SH_MD)

    mw[222] = mw[222] + mw[209]
    mw[272] = mw[272] + mw[259]
    
    ;sum total MD and HV
    mw[226] = mw[214] +                                      ;Ext_MD  
              mw[222] +                                      ;SH_MD
              mw[224]                                        ;SH_MD
    mw[276] = mw[264] +                                      ;Ext_MD  
              mw[272] +                                      ;SH_MD
              mw[274]                                        ;SH_MD
    
    mw[227] = mw[223] +                                      ;LH_MD
              mw[225]                                        ;LH_MD
    mw[277] = mw[273] +                                      ;LH_MD
              mw[275]                                        ;LH_MD
    

    ;PM Peak -----------------------------------------------------------------------------
    ;person trips
    mw[301] = mw[01] * Fac_PM_PA_HBW    
    mw[351] = mw[51] * Fac_PM_AP_HBW                         ;HBW

    mw[302] = mw[02] * Fac_PM_PA_HBO
    mw[352] = mw[52] * Fac_PM_AP_HBO                         ;HBO

    mw[303] = mw[03] * Fac_PM_PA_NHB
    mw[353] = mw[53] * Fac_PM_AP_NHB                         ;NHB

    mw[304] = mw[07] * Fac_PM_PA_HBS + (mw[08] * HBS_PM_Pct)
    mw[354] = mw[57] * Fac_PM_AP_HBS + (mw[58] * HBS_PM_Pct) ;HBSch drive + HBSch drop off

    mw[305] = mw[05] * Fac_PM_PA_HBC
    mw[355] = mw[55] * Fac_PM_AP_HBC                         ;HBC

    mw[306] = mw[06] * Fac_PM_PA_Rec
    mw[356] = mw[56] * Fac_PM_AP_Rec                         ;Rec
     
    ;external trips
    mw[311] = mw[11] * Fac_PM_PA_Ext    
    mw[361] = mw[61] * Fac_PM_AP_Ext                         ;Ext_Bus

    mw[312] = mw[12] * Fac_PM_PA_Ext
    mw[362] = mw[62] * Fac_PM_AP_Ext                         ;Ext_Oth

    mw[313] = mw[13] * Fac_PM_PA_Ext
    mw[363] = mw[63] * Fac_PM_AP_Ext                         ;Ext_Rec

    mw[314] = mw[14] * Fac_PM_PA_Ext
    mw[364] = mw[64] * Fac_PM_AP_Ext                         ;Ext_PM 
    
    ;short and long haul CV and truck trips
    mw[321] = mw[21] * Fac_PM_PA_TR
    mw[371] = mw[71] * Fac_PM_AP_TR                          ;SH_LT

    mw[322] = mw[22] * Fac_PM_PA_TR
    mw[372] = mw[72] * Fac_PM_AP_TR                          ;SH_PM

    mw[323] = mw[23] * Fac_PM_PA_TR
    mw[373] = mw[73] * Fac_PM_AP_TR                          ;SH_HV
    
    mw[324] = mw[24] * TR_PM_Pct * .5
    mw[374] = mw[24] * TR_PM_Pct * .5                        ;LH_PM

    mw[325] = mw[25] * TR_PM_Pct * .5
    mw[375] = mw[25] * TR_PM_Pct * .5                        ;LH_HV
    
    ;add schoolbus trips to SH_PM trip purpose
    mw[309] = mw[09] * Fac_PM_PA_HBS
    mw[359] = mw[59] * Fac_PM_PA_HBS                         ;schoolbus (add to SH_PM)

    mw[322] = mw[322] + mw[309]
    mw[372] = mw[372] + mw[359]
    
    ;sum total PM and HV
    mw[326] = mw[314] +                                      ;Ext_PM
              mw[322] +                                      ;SH_PM
              mw[324]                                        ;SH_PM
    mw[376] = mw[364] +                                      ;Ext_PM
              mw[372] +                                      ;SH_PM
              mw[374]                                        ;SH_PM
    
    mw[327] = mw[323] +                                      ;LH_PM
              mw[325]                                        ;LH_PM
    mw[377] = mw[373] +                                      ;LH_PM
              mw[375]                                        ;LH_PM
    
    
    ;EV Peak -----------------------------------------------------------------------------
    ;person trips
    mw[401] = mw[01] * Fac_EV_PA_HBW    
    mw[451] = mw[51] * Fac_EV_AP_HBW                         ;HBW

    mw[402] = mw[02] * Fac_EV_PA_HBO
    mw[452] = mw[52] * Fac_EV_AP_HBO                         ;HBO

    mw[403] = mw[03] * Fac_EV_PA_NHB
    mw[453] = mw[53] * Fac_EV_AP_NHB                         ;NHB

    mw[404] = mw[07] * Fac_EV_PA_HBS + (mw[08] * HBS_EV_Pct)
    mw[454] = mw[57] * Fac_EV_AP_HBS + (mw[58] * HBS_EV_Pct) ;HBSch drive + HBSch drop off

    mw[405] = mw[05] * Fac_EV_PA_HBC
    mw[455] = mw[55] * Fac_EV_AP_HBC                         ;HBC

    mw[406] = mw[06] * Fac_EV_PA_Rec
    mw[456] = mw[56] * Fac_EV_AP_Rec                         ;Rec
     
    ;external trips
    mw[411] = mw[11] * Fac_EV_PA_Ext    
    mw[461] = mw[61] * Fac_EV_AP_Ext                         ;Ext_Bus

    mw[412] = mw[12] * Fac_EV_PA_Ext
    mw[462] = mw[62] * Fac_EV_AP_Ext                         ;Ext_Oth

    mw[413] = mw[13] * Fac_EV_PA_Ext
    mw[463] = mw[63] * Fac_EV_AP_Ext                         ;Ext_Rec

    mw[414] = mw[14] * Fac_EV_PA_Ext
    mw[464] = mw[64] * Fac_EV_AP_Ext                         ;Ext_EV 
    
    ;short and long haul CV and truck trips
    mw[421] = mw[21] * Fac_EV_PA_TR
    mw[471] = mw[71] * Fac_EV_AP_TR                          ;SH_LT

    mw[422] = mw[22] * Fac_EV_PA_TR
    mw[472] = mw[72] * Fac_EV_AP_TR                          ;SH_EV

    mw[423] = mw[23] * Fac_EV_PA_TR
    mw[473] = mw[73] * Fac_EV_AP_TR                          ;SH_HV
    
    mw[424] = mw[24] * TR_EV_Pct * .5
    mw[474] = mw[24] * TR_EV_Pct * .5                        ;LH_EV

    mw[425] = mw[25] * TR_EV_Pct * .5
    mw[475] = mw[25] * TR_EV_Pct * .5                        ;LH_HV
    
    ;add schoolbus trips to SH_EV trip purpose
    mw[409] = mw[09] * Fac_EV_PA_HBS
    mw[459] = mw[59] * Fac_EV_PA_HBS                         ;schoolbus (add to SH_EV)

    mw[422] = mw[422] + mw[409]
    mw[472] = mw[472] + mw[459]
    
    ;sum total EV and HV
    mw[426] = mw[414] +                                      ;Ext_EV  
              mw[422] +                                      ;SH_EV
              mw[424]                                        ;SH_EV
    mw[476] = mw[464] +                                      ;Ext_EV  
              mw[472] +                                      ;SH_EV
              mw[474]                                        ;SH_EV
    
    mw[427] = mw[423] +                                      ;LH_EV
              mw[425]                                        ;LH_EV
    mw[477] = mw[473] +                                      ;LH_EV
              mw[475]                                        ;LH_EV
    
    
    ;PM 1 Hour ---------------------------------------------------------------------------
    ;person trips
    mw[501] = mw[301] * PM_1hr     ;HBW
    mw[502] = mw[302] * PM_1hr     ;HBO
    mw[503] = mw[303] * PM_1hr     ;NHB
    mw[504] = mw[304] * PM_1hr     ;HBSch
    mw[505] = mw[305] * PM_1hr     ;HBC
    mw[506] = mw[306] * PM_1hr     ;Rec
    mw[511] = mw[311] * PM_1hr     ;Ext_Bus
    mw[512] = mw[312] * PM_1hr     ;Ext_Oth
    mw[513] = mw[313] * PM_1hr     ;Ext_Rec
    mw[514] = mw[314] * PM_1hr     ;Ext_MD 
    mw[521] = mw[321] * PM_1hr     ;SH_LT
    mw[522] = mw[322] * PM_1hr     ;SH_MD
    mw[523] = mw[323] * PM_1hr     ;SH_HV
    mw[524] = mw[324] * PM_1hr     ;LH_MD
    mw[525] = mw[325] * PM_1hr     ;LH_HV
    
    ;sum total MD and HV
    mw[526] = mw[514] +            ;Ext_MD  
              mw[522] +            ;SH_MD
              mw[524]              ;SH_MD
    
    mw[527] = mw[523] +            ;LH_MD
              mw[525]              ;LH_MD

    mw[551] = mw[351] * PM_1hr     ;HBW
    mw[552] = mw[352] * PM_1hr     ;HBO
    mw[553] = mw[353] * PM_1hr     ;NHB
    mw[554] = mw[354] * PM_1hr     ;HBSch
    mw[555] = mw[355] * PM_1hr     ;HBC
    mw[556] = mw[356] * PM_1hr     ;Rec
    mw[561] = mw[361] * PM_1hr     ;Ext_Bus
    mw[562] = mw[362] * PM_1hr     ;Ext_Oth
    mw[563] = mw[363] * PM_1hr     ;Ext_Rec
    mw[564] = mw[364] * PM_1hr     ;Ext_MD 
    mw[571] = mw[371] * PM_1hr     ;SH_LT
    mw[572] = mw[372] * PM_1hr     ;SH_MD
    mw[573] = mw[373] * PM_1hr     ;SH_HV
    mw[574] = mw[374] * PM_1hr     ;LH_MD
    mw[575] = mw[375] * PM_1hr     ;LH_HV

    ;sum total MD and HV
    mw[576] = mw[564] +            ;Ext_MD  
              mw[572] +            ;SH_MD
              mw[574]              ;SH_MD
    
    mw[577] = mw[573] +            ;LH_MD
              mw[575]              ;LH_MD
    
ENDRUN
