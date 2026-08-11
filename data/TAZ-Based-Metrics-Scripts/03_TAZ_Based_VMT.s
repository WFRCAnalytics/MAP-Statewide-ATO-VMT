;========================================================================================================================
;    create taz based metrics output csv for vizTool
;========================================================================================================================

;System
    ;In case TP+ crashes during batch, this will halt process & help identify error.
    *(ECHO model crashed > 09_TAZ_Based_Metrics.txt)



;create header files ---------------------------------------------------------------------------------------------------
;get start time
ScriptStartTime = currenttime()

;print taz based metrics header
RUN PGM=MATRIX  MSG='TAZ Based Metrics: print header file'
    
    ZONES = 1
    
    PRINT FILE='outputs/TAZ-Based-VMT.csv',
        CSV=T,
        LIST='TAZID'             ,
             'Metric'            ,
             'Purpose'           ,
             'Period'            ,
             'PA'                ,
             'Total'             ,
             'Drive'             ,
             'Truck'             ,
             'External'          
    
ENDRUN

;AM --------------------------------------------------------------
;assign Cluster multi-step processing group
DistributeMultiStep Alias='TAZMet_VMT_AM'
    
    PeriodLp1     = 'AM'
    
    RUN PGM=MATRIX   MSG='TAZ Based Metrics: Calculate Metrics - VMT @PeriodLp1@'
        
        READ FILE = '_vmt_setup.block'
        
    ENDRUN
    
    RUN PGM=MATRIX   MSG='TAZ Based Metrics: Calculate Metrics - VMT @PeriodLp1@'
        
        READ FILE = '_vmt_calculation.block'
        
    ENDRUN
    
EndDistributeMULTISTEP


;MD --------------------------------------------------------------
;assign Cluster multi-step processing group
DistributeMultiStep Alias='TAZMet_VMT_MD'
    
    PeriodLp1     = 'MD'
    
    RUN PGM=MATRIX   MSG='TAZ Based Metrics: Calculate Metrics - VMT @PeriodLp1@'
        
        READ FILE = '_vmt_setup.block'
        
    ENDRUN
    
    RUN PGM=MATRIX   MSG='TAZ Based Metrics: Calculate Metrics - VMT @PeriodLp1@'
        
        READ FILE = '_vmt_calculation.block'
        
    ENDRUN
    
EndDistributeMULTISTEP


;PM --------------------------------------------------------------
;assign Cluster multi-step processing group
DistributeMultiStep Alias='TAZMet_VMT_PM'
    
    PeriodLp1     = 'PM'
    
    RUN PGM=MATRIX   MSG='TAZ Based Metrics: Calculate Metrics - VMT @PeriodLp1@'
        
        READ FILE = '_vmt_setup.block'
        
    ENDRUN
    
    RUN PGM=MATRIX   MSG='TAZ Based Metrics: Calculate Metrics - VMT @PeriodLp1@'
        
        READ FILE = '_vmt_calculation.block'
        
    ENDRUN
    
EndDistributeMULTISTEP


;EV --------------------------------------------------------------
;assign Cluster multi-step processing group
DistributeMultiStep Alias='TAZMet_VMT_EV'
    
    PeriodLp1     = 'EV'
    
    RUN PGM=MATRIX   MSG='TAZ Based Metrics: Calculate Metrics - VMT @PeriodLp1@'
        
        READ FILE = '_vmt_setup.block'
        
    ENDRUN
    
    RUN PGM=MATRIX   MSG='TAZ Based Metrics: Calculate Metrics - VMT @PeriodLp1@'
        
        READ FILE = '_vmt_calculation.block'
        
    ENDRUN
    
EndDistributeMULTISTEP

;Cluster: wait for all multi-step processing to finish before continuing
BARRIER IDLIST='TAZMet_VMT_AM', 'TAZMet_VMT_MD', 'TAZMet_VMT_PM', 'TAZMet_VMT_EV', CheckReturnCode=T, PrintFiles=Merge



;loop through different periods
LOOP numprd=1,4

    if (numprd=1)  PeriodLp1 = 'AM'
    if (numprd=2)  PeriodLp1 = 'MD'
    if (numprd=3)  PeriodLp1 = 'PM'
    if (numprd=4)  PeriodLp1 = 'EV'
    
    RUN PGM=MATRIX  MSG='TAZ Based Metrics: Create Final Metric File - appending @Metric@-@PeriodLp1@'
        
        FILEI DBI[1] = 'intermediate/temp-TAZ-Based-VMT-@PeriodLp1@.csv',
            DELIMITER =',',
            TAZID       = #01,
            Metric(C)   =  02,
            Purpose(C)  =  03,
            Period(C)   =  04,
            PA(C)       =  05,
            Total       =  06,
            Drive       =  07,
            Truck       =  08,
            External    =  09,
            AUTOARRAY=ALLFIELDS,
            SORT=Metric
        
        ZONES = 1
        
        LOOP numrec=1, dbi.1.NUMRECORDS
            
            PRINT FILE='outputs/TAZ-Based-VMT.csv',
                APPEND=T,
                CSV=T,
                LIST=dba.1.TAZID[numrec]      ,
                     dba.1.Metric[numrec]     ,
                     dba.1.Purpose[numrec]    ,
                     dba.1.Period[numrec]     ,
                     dba.1.PA[numrec]         ,
                     dba.1.Total[numrec]      ,
                     dba.1.Drive[numrec]      ,
                     dba.1.Truck[numrec]      ,
                     dba.1.External[numrec]   
            
        ENDLOOP  ;numrec=1, dbi.1.NUMRECORDS
        
    ENDRUN
    
ENDLOOP ;numprd=1,4