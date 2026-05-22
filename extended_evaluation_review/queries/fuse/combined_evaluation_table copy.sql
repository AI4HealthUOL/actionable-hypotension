-- Active: 1768480900465@@localhost@5434@mimic
#Edit exclusion for the individual characteristics

# age 
# saps
# sofa
# icu type
# heart-surgery (0/1)

DROP TABLE if exists evaluation.fused_subgroups_mv_excluded_unpacked 

CREATE TABLE evaluation.fused_subgroups_mv_excluded_unpacked  as 
SELECT 
    ie.subject_id,
    ie.hadm_id,
    ie.icustay_id,
    ec.transplant,
    ec.stroke,
    ec.brain_injury,
    ec.brain_hemorrhage,
     -- Exclusion flag
    CASE 
        WHEN ec.transplant = 1 
          OR ec.stroke = 1 
          OR ec.brain_injury = 1 
          OR ec.brain_hemorrhage = 1 
        THEN 1 ELSE 0 
    END AS exclusion,
    -- Age
    m.age,
    -- Severity scores
    s.saps AS saps_score,
    sii.sapsii AS sapsii_score,
    so.sofa AS sofa_score,
    -- ICU type
    CASE 
        WHEN ie.first_careunit IN ('CSRU', 'SICU', 'TSICU') THEN 'surgical'
        WHEN ie.first_careunit IN ('MICU', 'CCU') THEN 'non-surgical'
        ELSE 'other'
    END AS icu_type,
    -- Heart surgery flag
    CASE 
        WHEN hs.icustay_id IS NOT NULL THEN 1 ELSE 0 
    END AS heart_surgery_patient

FROM mimiciii.icustays ie
-- Exclusion criteria
LEFT JOIN evaluation.exclusion_criteria ec
    ON ie.subject_id = ec.subject_id 
    AND ie.hadm_id = ec.hadm_id 
    AND ie.icustay_id = ec.icustay_id
-- Age
LEFT JOIN ce_approach.mv_metadata m
    ON ie.subject_id = m.subject_id 
    AND ie.icustay_id = m.icustay_id
-- SAPS II
LEFT JOIN evaluation.sapsii sii
    On ie.icustay_id = sii.icustay_id
-- SAPS
LEFT JOIN evaluation.saps s
    ON ie.icustay_id = s.icustay_id
-- SOFA
LEFT JOIN evaluation.sofa so
    ON ie.icustay_id = so.icustay_id
-- Heart surgery patients
LEFT JOIN (
    SELECT DISTINCT icustay_id 
    FROM evaluation.heart_surgery_patients
) hs ON ie.icustay_id = hs.icustay_id
-- reduce to mv only
WHERE ie.dbsource != 'carevue'
ORDER BY ie.subject_id, ie.hadm_id, ie.icustay_id;