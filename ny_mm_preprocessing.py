#!/usr/bin/env python
# coding: utf-8

import numpy as np
import pandas as pd
import matplotlib as plt
import time
from recidiviz.calculator.modeling.population_projection.spark_bq_utils import upload_spark_model_inputs
pd.set_option('display.max_columns', 500)
pd.set_option('display.max_rows', None)

date_cols = ['DOB','dateReceivedOriginal','dateReceivedCurrent','latestReleaseDate','paroleHearingDate','maxExpirationDateParole','postReleaseMaxExpiration','paroleBoardDischargeDate']
transition_table_cols = ['custodyStatus','dateReceivedOriginal','latestReleaseDate','earliestReleaseDate','conditionalReleaseDate','minSentence','maxSentence','crime1','class1','crime2','class2','crime3','class3','crime4','class4']
THIRTY_YRS = 360
SAVE_TO_CSV = False

dfs = {year: pd.read_csv("recidiviz/calculator/modeling/population_projection/state/NY/sentencing_data/inmates"+str(year)+".csv",index_col=0,parse_dates=date_cols,na_filter=False) for year in range(2000,2021)}
df_full = pd.concat(dfs.values())

################### SETUP
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
pop_valid = c.copy()
c = c[['dateReceivedOriginal','LOS','crime']]
c['LOS'] = np.ceil(c.LOS.dt.days*12/365)

##################### OUTFLOWS
p = c.copy()
p['dateIn'] = p.dateReceivedOriginal
p = p[['dateIn','crime']]
p['moBin'] = p['dateIn'].apply(lambda x: "%d/%d" % (x.month, x.year))
p['moNo'] = p['dateIn'].apply(lambda x: x.month + 12*(x.year-2000))

outflows = p.groupby(['moNo','crime'])['moBin'].count().reset_index()
outflows = outflows.rename({'moNo': 'time_step', 'crime': 'crime_type', 'moBin': 'total_population'}, axis=1)
outflows['compartment'] = 'pre-trial'
outflows['outflow_to'] = 'prison'

# fill in missing data
missing_ts = \
    [i for i in range(outflows.time_step.min(), outflows.time_step.max()) if i not in outflows.time_step.unique()]
outflows = \
    pd.concat([outflows, pd.DataFrame({'time_step': missing_ts, 'total_population': [0 for _ in missing_ts]})]).ffill()

if SAVE_TO_CSV:
    csv_file = '/Users/jpouls/recidiviz/nyrecidiviz/mm_preprocessing/outflowfull/outflowfull'+str(int(time.time()))+'.csv'
    outflows[['compartment', 'outflow_to', 'total_population', 'time_step', 'crime_type']].to_csv(csv_file)

######################## TRANISITIONS
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
    LOS_count['n_left'] = minus(np.cumsum(LOS_count).crime) + LOS_count.crime

    # calculate proportion of inmates released, of those remaining
    LOS_count['transition'] = LOS_count.crime / (LOS_count.n_left)

    # add crime for disaggregation and save df to list
    LOS_count['CRIME'] = crime
    transition_df_by_crime.append(LOS_count[['transition', 'CRIME']])

t = pd.concat(transition_df_by_crime)

t['compartment'] = 'prison'
t['outflow_to'] = 'release'
t['total_population'] = t.transition
t['compartment_duration'] = t.index
t['crime_type'] = t.CRIME
t = t[['compartment','outflow_to','total_population','compartment_duration','crime_type']]

transitions = t.reset_index(drop=True)

# taken from here: https://doccs.ny.gov/system/files/documents/2021/03/inmate-releases-three-year-out-post-release-follow-up-2014.pdf
recidivism_transitions = pd.DataFrame({
    'compartment': ['release'] * 4 + ['release_full'],
    'outflow_to': ['prison'] * 3 + ['release_full'] * 2,
    'compartment_duration': [12, 24, 36, 36, 36],
    'total_population': [0.43 * 0.5, 0.43 * 0.34, 0.43 * (1 - 0.83), 1 - 0.43, 1]
})

for crime in d.crime.unique():
    recidivism_transitions['crime_type'] = crime
    transitions = pd.concat([transitions, recidivism_transitions])

# shrink outflows so we don't overcount recidivism
outflows.total_population *= (1 - 0.43)

if SAVE_TO_CSV:
    transitions.to_csv('/Users/jpouls/recidiviz/nyrecidiviz/mm_preprocessing/transitionfull/transitionfull'+str(int(time.time()))+'.csv')


########### TOTAL POPULATION
pop = pop_valid.copy()
pop = pop[['custodyStatus','crime']]
pop_in_custody = pop[pop.custodyStatus == 'IN CUSTODY']

total_pop = pop_in_custody.groupby('crime').count()
total_pop.reset_index(inplace=True)

total_pop['compartment'] = 'prison'
total_pop['total_population'] = total_pop.custodyStatus
# population as of Feb 2021 == 254 months since 2000
total_pop['time_step'] = 254
total_pop['crime_type'] = total_pop.crime
pop_out = total_pop[['compartment','total_population','time_step','crime_type']]

if SAVE_TO_CSV:
    pop_out.to_csv('/Users/jpouls/recidiviz/nyrecidiviz/mm_preprocessing/total_population/total_population'+str(int(time.time()))+'.csv')


############ SPARK MODEL UPLOAD
upload_spark_model_inputs('recidiviz-staging', 'NY_CTC', outflows, transitions, pop_out)