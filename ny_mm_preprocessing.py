#!/usr/bin/env python
# coding: utf-8

import numpy as np
import pandas as pd
import matplotlib as plt
import time
pd.set_option('display.max_columns', 500)
pd.set_option('display.max_rows', None)

date_cols = ['DOB','dateReceivedOriginal','dateReceivedCurrent','latestReleaseDate','paroleHearingDate','maxExpirationDateParole','postReleaseMaxExpiration','paroleBoardDischargeDate']
transition_table_cols = ['dateReceivedOriginal','latestReleaseDate','earliestReleaseDate','conditionalReleaseDate','minSentence','maxSentence','crime1','class1','crime2','class2','crime3','class3','crime4','class4']
THIRTY_YRS = 10950

dfs = [pd.read_csv("/Users/jpouls/recidiviz/nyrecidiviz/ny_inmate_data/inmates"+str(year)+".csv",index_col=0,parse_dates=date_cols,na_filter=False) for year in range(2000,2021)]
df_full = pd.concat(dfs)

df = df_full.copy()
print(df.shape[0])

# ignore reentries
df = df[df.dateReceivedOriginal == df.dateReceivedCurrent]
print(df.shape[0])

# ignore no crime records
df = df[df.crime1 != 'NO CRIME RECORD AVAIL']
print(df.shape[0])

# trim to essential columns
a = df[transition_table_cols]

# set conditionalReleaseDate as earliestReleaseDate if 'NONE'
b = a.copy()
mask = b['conditionalReleaseDate'] == 'NONE'
b.loc[mask,'conditionalReleaseDate'] = b['earliestReleaseDate']

# set conditionalReleaseDate as DATE_FAR_IN_FUTURE if 'LIFE'
c = b.copy()
mask = c['conditionalReleaseDate'] == 'LIFE'
c.loc[mask, 'conditionalReleaseDate'] = '2/22/2222'

# set enddate, with priority to latestReleaseDate, conditionalReleaseDate otherwise
c['enddate'] = c.latestReleaseDate.combine_first(c.conditionalReleaseDate)

# set LOS as timedelta between enddate and entrydate
c['LOS'] = c.enddate - c.dateReceivedOriginal

# ignore records with erroneous negative LOS
c = c[c.LOS.dt.days > 0]

# get most serious crime by class
def getCrime(df):
    df['crime'], df['crime_class'] = df['crime1'],df['class1']
    for i in [2,3,4]:
        cl = df['class'+str(i)]
        if not cl:
            return df
        if cl < df['crime_class']:
            df['crime'], df['crime_class'] = df['crime'+str(i)], cl
    return df
c = c.apply(getCrime,axis=1)

# clean up df
c['crime'] = c.crime + '|' + c.crime_class
c = c[['dateReceivedOriginal','LOS','crime']]
c['LOS'] = c.LOS.dt.days

d = c.copy()
d['dateIn'] = d.dateReceivedOriginal
d = d[['dateIn','crime']]
d['moBin'] = d['dateIn'].apply(lambda x: "%d/%d" % (x.month, x.year))
d['moNo'] = d['dateIn'].apply(lambda x: x.month + 12*(x.year-2000))
outflows = d.groupby(['moNo','crime'])['moBin'].count()

outflows.to_csv('/Users/jpouls/recidiviz/nyrecidiviz/mm_preprocessing/outflowfull/outflowfull'+str(int(time.time()))+'.csv')

# cap LOS at 30yr
d = c.copy()
mask = d['LOS'] > THIRTY_YRS
d.loc[mask,'LOS'] = THIRTY_YRS

transition_df_by_crime = []

for crime in d.crime.value_counts().index:
    # get sub-dataframe with specific crime
    by_crime = d[d.crime == crime]
    
    # fn to subtract released inmates from total inmates
    minus = lambda x: len(by_crime.index) - x
    
    # combine inmates with the same LOS
    LOS_count = by_crime.groupby('LOS').count()
    
    # np.cumsum gets num_of_inmates_released_so_far, minus + LOS_count gets num_of_inmates_remaining
    LOS_count['n_left'] = minus(np.cumsum(LOS_count).crime)+LOS_count.crime
    
    # calculate proportion of inmates released, of those remaining
    LOS_count['transition'] = LOS_count.crime/(LOS_count.n_left)
    
    # add crime for disaggregation and save df to list
    LOS_count['CRIME'] = crime
    transition_df_by_crime.append(LOS_count[['transition','CRIME']])

transitions = pd.concat(transition_df_by_crime)

transitions.to_csv('/Users/jpouls/recidiviz/nyrecidiviz/mm_preprocessing/transitionfull/transitionfull'+str(int(time.time()))+'.csv')

