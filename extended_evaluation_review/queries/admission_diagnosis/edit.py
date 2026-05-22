# just following the script from https://github.com/MIT-LCP/mimic-code/blob/main/mimic-iii/concepts_postgres/diagnosis/README.md

import pandas as pd
df = pd.read_csv('ccs_multi_dx_tool_2015.csv.gz')
# remove apostrophes from header names and relabel
df.rename(columns={"'ICD-9-CM CODE'": "icd9_code", "'CCS LVL 1'": "ccs_level1", "'CCS LVL 1 LABEL'": "ccs_group1", "'CCS LVL 2'": "ccs_level2", "'CCS LVL 2 LABEL'": "ccs_group2", "'CCS LVL 3'": "ccs_level3", "'CCS LVL 3 LABEL'": "ccs_group3", "'CCS LVL 4'": "ccs_level4", "'CCS LVL 4 LABEL'": "ccs_group4", }, inplace=True)

def remove_surrounding_apostrophes(x):
    if x[0] == "'":
        x = x[1:]
    if x[-1] == "'":
        x = x[:-1]
    return x

for c in df.columns:
    df[c] = df[c].map(remove_surrounding_apostrophes)
    idxRemove = df[c].str.strip() == ''
    if idxRemove.any():
        df.loc[idxRemove, c] = None

# write to file
df.to_csv('ccs_multi_dx.csv.gz', index=False, compression='gzip')