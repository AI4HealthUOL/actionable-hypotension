-- Active: 1756194958052@@127.0.0.1@5432@mimic
-- This is an adoption from CREATE TABLE chartevents_positive/negative_metadata.sql
-- This script is supposed to get the patient demographics, biometrics and comorbidities for all 61532 unique icustays.

 ---------- Get de-duplicated list of ICU STAYS  ---------- 
CREATE TEMP TABLE temp_distinct_stays AS
SELECT DISTINCT 
  i.subject_id, 
  i.icustay_id, 
  i.hadm_id,
  icu.intime AS icu_intime
FROM mimiciii.inputevents_mv i
JOIN mimiciii.icustays icu
ON icu.icustay_id = i.icustay_id


--- 2nd version that uses hadm_id to get only comorbidities that we look for already known beforehand 
-- by using the elixhauser_quan.sql workflow (Only 23386 unique icustays from metavision)

WITH demographics AS (
  SELECT
  patientunitstayid,
  patienthealthsystemsstayid,
  hospitalid,
  wardid,
  gender,
  CASE
        WHEN age ILIKE '%>89%' THEN 89
        ELSE age
      END AS age,
  CASE
        WHEN ethnicity ILIKE '%Caucasian%' THEN 'White'
        WHEN ethnicity ILIKE '%African American%' THEN 'Black'
        WHEN ethnicity ILIKE '%asian%' THEN 'Asian'
        WHEN ethnicity ILIKE '%hispanic%' OR ethnicity ILIKE '%latino%' THEN 'Hispanic'
        ELSE 'Other'  -- For any unclassified ethnicity
      END AS ethnicity_group
    FROM eicu_crd.patient
),
biometrics AS (
admissionheight,
admissionweight,
CASE
      WHEN admissionheight IS NOT NULL AND admissionweight IS NOT NULL THEN
        ROUND(CAST(admissionweight / POWER(admissionheight / 100, 2) AS numeric), 2)
      ELSE NULL
    END AS bmi,
FROM eicu_crd.patient
),
comorbidities AS (
  
)




 ---------- Get de-duplicated list of ICU STAYS connected to _mv  ---------- 
CREATE TEMP TABLE temp_distinct_stays AS
SELECT DISTINCT 
  i.subject_id, 
  i.icustay_id, 
  i.hadm_id,
  icu.intime AS icu_intime
FROM mimiciii.inputevents_mv i
JOIN mimiciii.icustays icu
ON icu.icustay_id = i.icustay_id

CREATE TABLE ce_approach.mv_metadata AS
 ---------- Demographics Section (Age, Gender, Ethnicity)  ---------- 
WITH demographics AS (
  SELECT 
    ds.subject_id,
    ds.icustay_id,
    pat.gender,
     -- Simplify ethnicity to 5 groups: White, Black, Asian, Hispanic, Other
    CASE
      WHEN adm.ethnicity ILIKE '%white%' THEN 'White'
      WHEN adm.ethnicity ILIKE '%black%' OR adm.ethnicity ILIKE '%african%' THEN 'Black'
      WHEN adm.ethnicity ILIKE '%asian%' THEN 'Asian'
      WHEN adm.ethnicity ILIKE '%hispanic%' OR adm.ethnicity ILIKE '%latino%' THEN 'Hispanic'
      ELSE 'Other'  -- For any unclassified ethnicity
    END AS ethnicity_group,
    -- Calculate age ( capped at 89)
    LEAST(
  ROUND(
    (CAST(EXTRACT(epoch FROM ds.icu_intime - pat.dob) / (60*60*24*365.242) AS numeric))
  , 0),
  89
) AS age
  FROM temp_distinct_stays ds
  JOIN mimiciii.icustays icu ON ds.icustay_id = icu.icustay_id
  JOIN mimiciii.patients pat ON ds.subject_id = pat.subject_id
  JOIN mimiciii.admissions adm ON icu.hadm_id = adm.hadm_id
  GROUP BY ds.subject_id, ds.icustay_id, pat.gender, adm.ethnicity, ds.icu_intime, pat.dob
),
-- Biometrics Section (Weight, Height, BMI (calculated in the final aggregation step))
-- Step 1: Get Weight information ( either through weight_from_inputevents, admission weight or daily weight directly, or indirectly via other icu_stays of the same subject_id from max 2 years before)
weight_from_inputevents AS (
  SELECT DISTINCT ON (subject_id, icustay_id)
    subject_id,
    icustay_id,
    patientweight AS weight
  FROM mimiciii.inputevents_mv
  WHERE patientweight IS NOT NULL
    AND patientweight BETWEEN 30 AND 250
  ORDER BY subject_id, icustay_id, starttime  -- oder charttime falls vorhanden
),
weight_events_from_chartevents AS (
  SELECT
    ds.subject_id,
    ds.icustay_id,
    ce.charttime,
    ce.valuenum AS weight,
    ce.itemid
  FROM temp_distinct_stays ds
  JOIN mimiciii.chartevents ce
    ON ce.subject_id = ds.subject_id
  WHERE ce.itemid IN (224639, 226512)
    AND ce.valuenum IS NOT NULL
    AND ce.valuenum BETWEEN 30 AND 250  -- sanity filter
    AND ce.charttime BETWEEN ds.icu_intime - INTERVAL '1 years'
                          AND ds.icu_intime + INTERVAL '72 hours'  -- NEW: include 3 days after icuadmission
    
),
-- Match weight to same ICU stay (must be from the past)
direct_weight_candidates AS (
  SELECT 
    ds.subject_id,
    ds.icustay_id,
    ds.icu_intime,
    we.charttime,
    we.weight,
    ROW_NUMBER() OVER (
      PARTITION BY ds.icustay_id
      ORDER BY ds.icu_intime - we.charttime  -- smaller time gap preferred (more recent)
    ) AS rn
  FROM temp_distinct_stays ds
  JOIN weight_events_from_chartevents we
    ON ds.icustay_id = we.icustay_id AND ds.subject_id = we.subject_id
  WHERE ds.icu_intime - we.charttime <= INTERVAL '1 year'  -- Ensure weight is max 1 years before the icu icu_intime
  AND we.weight BETWEEN 30 AND 250

),
-- take the weight from the closest direct weight candidates
closest_direct_weight AS (
  SELECT 
    icustay_id, subject_id, weight
  FROM direct_weight_candidates
  WHERE rn = 1
),
-- Try to fill gaps using weights from *other* ICU stays of same subject within 1 year (must be from the past)
crossstay_weight_candidates AS (
  SELECT 
    ds.subject_id,
    ds.icustay_id,
    ds.icu_intime,
    we.charttime,
    we.weight,
    we.icustay_id AS source_icustay_id,
    ROW_NUMBER() OVER (
      PARTITION BY ds.icustay_id
      ORDER BY ds.icu_intime - we.charttime
    ) AS rn
  FROM temp_distinct_stays ds
  JOIN weight_events_from_chartevents we
    ON ds.subject_id = we.subject_id
    AND ds.icustay_id <> we.icustay_id
    AND ds.icu_intime - we.charttime <= INTERVAL '1 years'
    AND we.weight BETWEEN 30 AND 250
),
--take the weight from the closest crossstay weight candidates
closest_crossstay_weight AS (
  SELECT
    icustay_id,
    subject_id,
    weight
  FROM crossstay_weight_candidates
  WHERE rn = 1
),
--- Combine all: prefer inputevents_mv > direct weight > crossstay
final_weight_per_stay AS (
  SELECT
    ds.icustay_id,
    ds.subject_id,
    COALESCE(wi.weight, dw.weight, cw.weight) AS weight
  FROM temp_distinct_stays ds
  LEFT JOIN weight_from_inputevents wi
    ON ds.icustay_id = wi.icustay_id AND ds.subject_id = wi.subject_id
  LEFT JOIN closest_direct_weight dw
    ON ds.icustay_id = dw.icustay_id AND ds.subject_id = dw.subject_id
  LEFT JOIN closest_crossstay_weight cw
    ON ds.icustay_id = cw.icustay_id AND ds.subject_id = cw.subject_id
    AND dw.weight IS NULL
),
-- Step 2: HEIGHT (only for Metavision patients using itemid 226730), as in git https://github.com/MIT-LCP/mimic-code/tree/main/mimic-iii
height_events AS (
  SELECT 
    c.subject_id, 
    c.icustay_id, 
    c.charttime,
    c.valuenum AS raw_height,
    CASE
      -- plausibility filter for adults (e.g. 120–230 cm)
      WHEN c.valuenum BETWEEN 120 AND 230 THEN c.valuenum
      ELSE NULL
    END AS height
  FROM mimiciii.chartevents c
  INNER JOIN mimiciii.patients pt
    ON c.subject_id = pt.subject_id
  WHERE c.valuenum IS NOT NULL
    AND c.valuenum != 0
    AND COALESCE(c.error, 0) = 0
    AND c.itemid = 226730
),
all_height_values AS (
  SELECT DISTINCT ON (subject_id, icustay_id)
    subject_id,
    icustay_id,
    height
  FROM height_events
  WHERE height IS NOT NULL
  ORDER BY subject_id, icustay_id, charttime
),
-- Step 3: BMI -----
-- calculated in the final aggregation step 
-------- Comorbidities Section ----------
comorbidity_flags AS (
  SELECT
  ds.*,
  CASE
  WHEN eq.diabetes_uncomplicated = 1 OR eq.diabetes_complicated = 1 THEN 1
  ELSE 0
  END AS diabetes,
  eq.renal_failure AS kidney_disease,
  CASE
  WHEN eq.congestive_heart_failure = 1 OR eq.valvular_disease = 1 THEN 1
  ELSE 0
  END AS heart_disease,
  eq.chronic_pulmonary AS lung_disease,
  eq.hypertension,
  eq.obesity,
  eq.drug_abuse,
  eq.depression
FROM temp_distinct_stays ds
LEFT JOIN ce_approach.elixhauser_quan eq
  ON ds.hadm_id = eq.hadm_id
),
-- Final Aggregation Section (Joining Everything Together)
final_metadata AS (
  SELECT 
    ds.icustay_id,
    ds.subject_id,
    -- from demographics
    dem.gender,
    dem.ethnicity_group,
    dem.age,
    -- from height/weight logic
    hd.height,
    wd.weight,
    -- calculated BMI
    CASE
      WHEN hd.height IS NOT NULL AND wd.weight IS NOT NULL THEN
        ROUND(CAST(wd.weight / POWER(hd.height / 100, 2) AS numeric), 2)
      ELSE NULL
    END AS bmi,
    -- comorbidities (one-hot style, NULL turned to 0)
    COALESCE(cm.obesity, 0) AS obesity,
    COALESCE(cm.hypertension, 0) AS hypertension,
    COALESCE(cm.diabetes, 0) AS diabetes,
    COALESCE(cm.kidney_disease, 0) AS kidney_disease,
    COALESCE(cm.lung_disease, 0) AS lung_disease,
    COALESCE(cm.heart_disease, 0) AS heart_disease,
    COALESCE(cm.drug_abuse, 0) AS drug_abuse,
    COALESCE(cm.depression, 0) AS depression

  FROM temp_distinct_stays ds
  LEFT JOIN final_weight_per_stay wd 
    ON ds.subject_id = wd.subject_id AND ds.icustay_id = wd.icustay_id
  LEFT JOIN all_height_values hd 
    ON ds.subject_id = hd.subject_id AND ds.icustay_id = hd.icustay_id
  LEFT JOIN demographics dem 
    ON ds.subject_id = dem.subject_id AND ds.icustay_id = dem.icustay_id
  LEFT JOIN comorbidity_flags cm 
    ON ds.subject_id = cm.subject_id AND ds.icustay_id = cm.icustay_id
)
-- Final Table Output: Merge Everything into the Final Result
SELECT * FROM final_metadata;

--compare old and new approach

SELECT 
  'new_approach' AS approach,
  COUNT(*) AS total_rows,
  SUM(CASE WHEN height IS NULL THEN 1 ELSE 0 END) AS missing_height,
  SUM(CASE WHEN weight IS NULL THEN 1 ELSE 0 END) AS missing_weight
FROM ce_approach.mv_metadata_new_approach

UNION ALL

SELECT 
  'old_approach' AS approach,
  COUNT(*) AS total_rows,
  SUM(CASE WHEN height IS NULL THEN 1 ELSE 0 END) AS missing_height,
  SUM(CASE WHEN weight IS NULL THEN 1 ELSE 0 END) AS missing_weight
FROM ce_approach.mv_metadata_old_approach;

-- check height for new approach

SELECT 
    m1.subject_id, 
    m1.icustay_id AS icustay_id_1,
    m1.height AS height_1,
    m2.icustay_id AS icustay_id_2,
    m2.height AS height_2,
    ABS(m1.height - m2.height) AS height_diff,
    EXTRACT(EPOCH FROM (i2.intime - i1.intime)) / (60*60*24*365.242) AS time_diff_years  -- Time difference in years
FROM ce_approach.mv_metadata m1
JOIN ce_approach.mv_metadata m2 
    ON m1.subject_id = m2.subject_id 
    AND m1.icustay_id < m2.icustay_id  -- To avoid comparing the same rows (m1 vs m1)
JOIN icustays i1 
    ON m1.icustay_id = i1.icustay_id
JOIN icustays i2 
    ON m2.icustay_id = i2.icustay_id
WHERE ABS(m1.height - m2.height) > 5;  -- Difference greater than 5 cm