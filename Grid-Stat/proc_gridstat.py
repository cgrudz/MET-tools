##################################################################################
# Description
##################################################################################
# This script reads in arbitrary grid_stat_* output files from a MET analysis
# and creates Pandas dataframes containing a time series for each file type
# versus lead time to a verification period. The dataframes are saved into a
# Pickled dictionary organized by MET file extension as key names, taken
# agnostically from bash wildcard patterns.
#
# Batches of hyper-parameter-dependent data can be processed by constructing
# lists of proc_gridstat arguments which define configurations that will be mapped
# to run in parallel through Python multiprocessing.
#
##################################################################################
# License Statement
##################################################################################
#
# Copyright 2023 Colin Grudzien, cgrudzien@ucsd.edu
# 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#     http://www.apache.org/licenses/LICENSE-2.0
# 
#     Unless required by applicable law or agreed to in writing, software
#     distributed under the License is distributed on an "AS IS" BASIS,
#     WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#     See the License for the specific language governing permissions and
#     limitations under the License.
# 
##################################################################################
# Imports
##################################################################################
import sys
import os
import numpy as np
import pandas as pd
import pickle
import copy
import glob
from datetime import datetime as dt
from datetime import timedelta
import multiprocessing 
from multiprocessing import Pool
import ipdb

##################################################################################
# SET GLOBAL PARAMETERS 
##################################################################################
# define control flow to analyze 
CTR_FLWS = [
            "NAM_lag06_b0.00_v06_h0300",
            "NAM_lag06_b0.20_v06_h0300",
            "NAM_lag06_b0.40_v06_h0300",
            "NAM_lag06_b0.60_v06_h0300",
            "NAM_lag06_b0.80_v06_h0300",
            "NAM_lag06_b1.00_v06_h0300",
            "RAP_lag06_b0.00_v06_h0300",
            "RAP_lag06_b0.20_v06_h0300",
            "RAP_lag06_b0.40_v06_h0300",
            "RAP_lag06_b0.60_v06_h0300",
            "RAP_lag06_b0.80_v06_h0300",
            "RAP_lag06_b1.00_v06_h0300",
           ]

# define the case-wise sub-directory
CSE = 'CC-NAM_v_RAP'

# verification domain for the forecast data                                                                           
GRDS = [
        'd02',
       ]

# starting date and zero hour of forecast cycles (string YYYYMMDDHH)
STRT_DT = '2021012400'

# final date and zero hour of data of forecast cycles (string YYYYMMDDHH)
END_DT = '2021012800'

# number of hours between zero hours for forecast data (string HH)
CYC_INT = '24'

# optionally define output prefix, set as empty string if not needed
PRFXS = [
         '',
        ]

# root directory for gridstat outputs
IN_ROOT = '/cw3e/mead/projects/cwp106/scratch/cgrudzien/' + CSE

# root directory for processed pandas outputs
OUT_ROOT = '/cw3e/mead/projects/cwp106/scratch/cgrudzien/' + CSE

##################################################################################
# Construct hyper-paramter array for batch processing gridstat data
##################################################################################
# standard string indentation
STR_INDT = '    '

# container for map
CNFGS = []

for CTR_FLW in CTR_FLWS:
    for GRD in GRDS:
        for PRFX in PRFXS:
            # storage for configuration settings as arguments of proc_gridstat
            # the function definition and role of these arguments are in the
            # next section directly below
            CNFG = []

            # control flow / directory name
            CNFG.append(CTR_FLW)

            # prefix for gridstat outputs
            CNFG.append(PRFX)

            # grid to be processed
            CNFG.append(GRD)

            # path to cycle directories from IN_ROOT
            CNFG.append('/' + CTR_FLW)
            
            # path to gridstat outputs from cycle directory
            CNFG.append('')

            # path to pandas output directories from OUT_ROOT
            CNFG.append('/' + CTR_FLW)

            # append configuration to be mapped
            CNFGS.append(CNFG)

##################################################################################
# Process data routine
##################################################################################
#  function for multiprocessing parameter map
def proc_gridstat(cnfg):
    # unpack argument list
    ctr_flw, prfx, grd, in_cyc_dir, in_dt_subdir, out_cyc_dir = cnfg

    # include underscore if prefix is of nonzero length
    if len(prfx) > 0:
        prfx =+ '_'

    # define derived data paths 
    in_data_root = IN_ROOT + in_cyc_dir 

    out_data_root = OUT_ROOT + '/' + out_cyc_dir
    os.system('mkdir -p ' + out_data_root)
    out_path = out_data_root + '/grid_stats_' + prfx + grd + '_' + STRT_DT +\
               '_to_' + END_DT + '.bin'
    
    with open(out_data_root + '/proc_gridstat_' + prfx + ctr_flw + '_' + grd +\
              '_log.txt', 'w') as log_f:
        # check for input root directory
        if not os.path.isdir(in_data_root):
            print('ERROR: input data root directory ' + in_data_root +\
                    ' does not exist.', file=log_f)
            sys.exit(1)
        
        # convert to date times
        if len(STRT_DT) != 10:
            print('ERROR: STRT_DT, ' + STRT_DT +\
                    ', is not in YYYYMMDDHH format.', file=log_f)
            sys.exit(1)
        else:
            s_iso = STRT_DT[:4] + '-' + STRT_DT[4:6] + '-' + STRT_DT[6:8] +\
                    '_' + STRT_DT[8:]
            strt_dt = dt.fromisoformat(s_iso)

        if len(END_DT) != 10:
            print('ERROR: END_DT, ' + END_DT +\
                    ', is not in YYYYMMDDHH format.', file=log_f)
            sys.exit(1)
        else:
            e_iso = END_DT[:4] + '-' + END_DT[4:6] + '-' + END_DT[6:8] +\
                    '_' + END_DT[8:]
            end_dt = dt.fromisoformat(e_iso)

        if len(CYC_INT) != 2:
            print('ERROR: CYC_INT, ' + CYC_INT +\
                    ', is not in HH format.', file=log_f)
            sys.exit(1)
        else:
            cyc_int = CYC_INT + 'H'
        
        # generate the date range for the analyses
        analyses = pd.date_range(start=strt_dt, end=end_dt,
                                 freq=cyc_int).to_pydatetime()
        
        # initiate empty dictionary for storage of dataframes by keyname
        data_dict = {}
        
        print('Processing dates ' + STRT_DT + ' to ' + END_DT, file=log_f)
        for anl_dt in analyses:
            # directory string format
            anl_strng = anl_dt.strftime('%Y%m%d%H')
            
            # define the gridstat files to open based on the analysis date
            in_paths = in_data_root + '/' + anl_strng + in_dt_subdir  +\
                       '/grid_stat_' + prfx + '*.txt'
        
            # loop sorted grid_stat_prfx* files, sorting compares first on the
            # length of lead time for non left-padded values
            in_paths = sorted(glob.glob(in_paths),
                              key=lambda x:(len(x.split('_')[-4]), x))
            for in_path in in_paths:
                print(STR_INDT + 'Opening file ' + in_path, file=log_f)
        
                # cut the diagnostic type from file name
                fname = in_path.split('/')[-1]
                split_name = fname.split('_')
                postfix = split_name[-1].split('.')
                postfix = postfix[0]
        
                # open file, load column names, then loop lines
                with open(in_path) as f:
                    cols = f.readline()
                    cols = cols.split()
                    
                    if len(cols) > 0:
                        fname_df = {} 
                        tmp_dict = {}
                        df_indx = 1
        
                        print(STR_INDT + 'Loading columns:', file=log_f)
                        for col_name in cols:
                            print(STR_INDT * 2 + col_name, file=log_f)
                            fname_df[col_name] = [] 
        
                        fname_df =  pd.DataFrame.from_dict(fname_df,
                                                           orient='columns')
        
                        # parse file by line, concatenating columns
                        for line in f:
                            split_line = line.split()
        
                            for i in range(len(split_line)):
                                val = split_line[i]
        
                                # filter NA vals
                                if val == 'NA':
                                    val = np.nan
                                tmp_dict[cols[i]] = val
        
                            tmp_dict['line'] = [df_indx]
                            tmp_dict = pd.DataFrame.from_dict(tmp_dict,
                                                              orient='columns')
                            fname_df = pd.concat([fname_df, tmp_dict], axis=0)
                            df_indx += 1
        
                        fname_df['line'] = fname_df['line'].astype(int)
                        
                        if postfix in data_dict.keys():
                            last_indx = data_dict[postfix].index[-1]
                            fname_df['line'] = fname_df['line'].add(last_indx)
                            fname_df = fname_df.set_index('line')
                            data_dict[postfix] = pd.concat([data_dict[postfix],
                                                            fname_df], axis=0)
        
                        else:
                            fname_df = fname_df.set_index('line')
                            data_dict[postfix] = fname_df
        
                    else:
                        print('WARNING: file ' + in_path +\
                                ' is empty, skipping this file.', file=log_f)
        
                    print(STR_INDT + 'Closing file ' + in_path, file=log_f)
        
        print('Writing out data to ' + out_path, file=log_f)
        with open(out_path, 'wb') as f:
            pickle.dump(data_dict, f)

        return 'Completed: ' + prfx + ctr_flw + ' ' + grd + '\n'

##################################################################################
# Runs multiprocessing on parameter grid
##################################################################################
# run lines if executed as a script
if __name__ == '__main__':
    # infer available cpus for workers
    n_workers = multiprocessing.cpu_count() - 1
    print('Running proc_gridstat with ' + str(n_workers) + ' total workers.')

    with Pool(n_workers) as pool:
        print(*pool.map(proc_gridstat, CNFGS))

##################################################################################
# end
