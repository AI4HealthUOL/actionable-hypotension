"""
CCU: Coronary Care Unit
CSRU: Cardiac Surgery Recovery Unit
MICU: Medical Intensive Care Unit
SICU: Surgical Intensive Care Unit
TSICU: Trauma Surgical Intensive Care Unit
NICU: Neonatal Intensive Care Unit (NICU)
"""

# herzchirurgische patienten
# first care unit CSRU and 
#curr_careunit in transfers table ever CSRU

CREATE TABLE evaluation.heart_surgery_patients as
SELECT DISTINCT
    i.subject_id,
    i.hadm_id,
    i.icustay_id,
    i.first_careunit,
    t.curr_careunit
FROM mimiciii.icustays i
LEFT JOIN mimiciii.transfers t ON i.subject_id = t.subject_id
LEFT JOIN mimiciii.procedures_icd p ON i.subject_id = p.subject_id
WHERE i.first_careunit = 'CSRU' 
   OR t.curr_careunit = 'CSRU'


# icu type ( surgical vs. non-surgical)
CREATE TABLE evaluation.surgery_vs_no_surgery_patients as
SELECT 
    subject_id,
    hadm_id,
    icustay_id,
    first_careunit,
    CASE 
        WHEN first_careunit IN ('CSRU', 'SICU', 'TSICU') THEN 'surgical'
        WHEN first_careunit IN ('MICU', 'CCU') THEN 'non-surgical'
        ELSE 'other'
    END AS patient_type
FROM mimiciii.icustays


SELECT 
    patient_type,
    COUNT(DISTINCT icustay_id) AS n,
    ROUND(100.0 * COUNT(DISTINCT icustay_id) / SUM(COUNT(DISTINCT icustay_id)) OVER (), 1) AS pct
FROM evaluation.surgery_vs_no_surgery_patients
WHERE patient_type IN ('surgical', 'non-surgical')
GROUP BY patient_type

UNION ALL

SELECT
    'cardiac surgery' AS patient_type,
    COUNT(DISTINCT icustay_id) AS n,
    ROUND(100.0 * COUNT(DISTINCT icustay_id) / 
        (SELECT COUNT(DISTINCT icustay_id) FROM evaluation.surgery_vs_no_surgery_patients 
         WHERE patient_type IN ('surgical', 'non-surgical')), 1) AS pct
FROM evaluation.heart_surgery_patients53.9