#!/usr/bin/env python
# coding: utf-8

import numpy as np
import pandas as pd
import matplotlib as plt
# pd.options.display.max_rows = 4000
pd.set_option('display.max_columns', 500)
pd.set_option('display.max_rows', None)


# In[453]:


date_cols = ['DOB','dateReceivedOriginal','dateReceivedCurrent','latestReleaseDate','paroleHearingDate','maxExpirationDateParole','postReleaseMaxExpiration','paroleBoardDischargeDate']
date_cols_unpure = ['earliestRelaseDate','paroleEligibilityDate','conditionalReleaseDate','maxExpirationDate']
transition_table_cols = ['custodyStatus','dateReceivedOriginal','latestReleaseDate','earliestReleaseDate','conditionalReleaseDate','minSentence','maxSentence','crime1','class1','crime2','class2','crime3','class3','crime4','class4']
THIRTY_YRS = 10950


# In[434]:


df = pd.read_csv("/Users/jpouls/recidiviz/nyrecidiviz/inmates2018.csv",index_col=0,parse_dates=date_cols,na_filter=False)
# df = pd.read_csv("/Users/jpouls/recidiviz/nyrecidiviz/inmates2018.csv",index_col=0,na_filter=False)

# dfs = [pd.read_csv("/Users/jazz/proj/doc-scraper/ny_inmate_data/inmates"+str(year)+".csv",index_col=0,parse_dates=date_cols,na_filter=False) for year in range(2015,2020)]
df.head()


# In[340]:


# ignore reentries
df = df[df.dateReceivedOriginal == df.dateReceivedCurrent]
# ignore no crime records
df = df[df.crime1 != 'NO CRIME RECORD AVAIL']

# trim to essential columns
dftrim = df[transition_table_cols]


# In[368]:


# set conditionalReleaseDate as earliestReleaseDate if 'NONE'
b = dftrim.copy()
mask = b['conditionalReleaseDate'] == 'NONE'
b.loc[mask,'conditionalReleaseDate'] = b['earliestReleaseDate']


# In[458]:


# set conditionalReleaseDate as DATE_FAR_IN_FUTURE if 'LIFE'
c = b.copy()
mask = c['conditionalReleaseDate'] == 'LIFE'
c.loc[mask, 'conditionalReleaseDate'] = '2/22/2222'

# set enddate, with priority to latestReleaseDate, conditionalReleaseDate otherwise
c['enddate'] = c.latestReleaseDate.combine_first(c.conditionalReleaseDate)

# set LOS as timedelta between enddate and entrydate
c['LOS'] = c.enddate - c.dateReceivedOriginal

#remove records with erroneous negative LOS
c = c[c.LOS.dt.days > 0] 


# In[459]:


# get most serious crime by class
def getCrime(df):
#     cls = df[['class1','class2','class3','class4']].to_numpy()
#     index = min(range(4), key=lambda i: cls[i] if cls[i] else 'Z')
#     df['crime'] = df['crime'+str(index+1)]
#     df['crime_class'] = cls[index]
#     return df
    
    df['crime'], df['crime_class'] = df['crime1'],df['class1']
    for i in [2,3,4]:
        cl = df['class'+str(i)]
        if not cl:
            return df
        if cl < df['crime_class']:
            df['crime'], df['crime_class'] = df['crime'+str(i)], cl
    return df

c = c.apply(getCrime,axis=1)
c['crime'] = c.crime + '|' + c.crime_class
c = c[['dateReceivedOriginal','LOS','crime']]
c['LOS'] = c.LOS.dt.days


# In[509]:


d = c.copy()
mask = d['LOS'] > THIRTY_YRS
d.loc[mask,'LOS'] = THIRTY_YRS


# In[555]:


transition_df_by_crime = []

for crime in d.crime.unique():
    by_crime = d[d.crime == crime]
    N = len(by_crime.index)
    LOS_count = d[d.crime == crime].groupby('LOS').count()
#     print(LOS_count)
    minus = lambda x: N-x
    # np.cumsum gets # of inmates released, minus + LOS_count gets # of inmates remaining
    LOS_count['n_left'] = minus(np.cumsum(LOS_count).crime)+LOS_count.crime
    LOS_count['transition'] = LOS_count.crime/(LOS_count.n_left)
    LOS_count['CRIME'] = crime
#     LOS_count['LOSi'] = LOS_count.index
    transition_df_by_crime.append(LOS_count[['transition','CRIME']])
#     print(LOS_count[['LOSi','transition','CRIME']])
#     print(LOS_count.tail())

transitions = pd.concat(transition_df_by_crime)
transitions.to_csv('/Users/jpouls/recidiviz/nyrecidiviz/mm_preprocessing/transitions2018charm.csv')
    
    
#         numLOS['cum'] = cum.crime
#     numLOS['cum_left'] = minus(cum.crime)
#     numLOS['out_of_this_many'] = numLOS.cum_left+nu/mLOS.crime
#     numLOS['transition'] = numLOS.crime/(numLOS.cum_left+numLOS.crime)

#     print(numLOS)
#     print(numLOS.index.to_numpy(),len(numLOS.index.to_numpy()))
#     print(numLOS.to_numpy(),len(numLOS.to_numpy()))
#     print(np.cumsum(numLOS))#,len(np.cumsum(numLOS.to_numpy())))
#     print(square(np.cumsum(numLOS.to_numpy())))

    


# In[259]:


# In[ ]:


# OLD
# diffdates[~diffdates.paroleHearingType.str.contains("VIOLA")]
# merg = pd.merge(diffdates, parole_viol, how='inner', on=['DIN'])
# c['crime_short'] = c.crime.str.extract(r'(.*?\d).*')[0]

# s = d.cc.unique()
# s = [str(x) for x in s]
# s.sort()

# bins = np.arange(0.0, 36500.0, 365.0/12)
# bins = np.append(bins,max(d['LOS'].dt.days))
# count, bins_count = np.histogram(d['LOS'].dt.days, bins=bins)
# pdf = count / sum(count)
# cdf = np.cumsum(pdf) 
# d['LOS'].dt.days.hist(bins=bins)
# los.hist(bins=32)

