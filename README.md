# nyrecidiviz

Processes NY inmate data for [Recidiviz](https://www.recidiviz.org/policy) policy impact modeling<br>
Calculates tables to input to Recidiviz's policy impact modeling.

### Motivation
Researching the effects of eliminating mandatory minimums in NY

### Raw data
300k incarceration records from 2000-2020 containing:
* date received
* release date if released
* conditional release date if in custody
* mininmum sentence
* maximum sentence
* crimes committed + felony class
* demographic data
* parole data

### Initial calculations
Clean raw data
Filter out inmates whose data is incomplete/unusable
Calculate inmate length-of-stay `LOS`
Determine inmate's most serious offense, if multiple

### Output data
#### outflows_data
Number of inmates admitted to prison each month<br>
Disaggregated by crime description

#### transitions_data
Percentage inmates released after `x` months<br>
Disaggregated by crime description

#### total_population_data
Current inmate population as of Feb. 2021
