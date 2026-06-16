-- Active: 1770284354672@@127.0.0.1@5433@eicu

-- Context: What data has to be merged? 
-- One of those tables as base: mix windows_statistical_features | invasive windows_statistical_features | noninvasive_windows_statistical_features (those are on the granularity of context_windows)

-- All matching context_windows from additional_meds_in_windows: (this is on the granularity of all_mv_labeled_windows)

-- All the patient metadata (demographics, biometrics, comorbidities) from mv_metadata_binned:  (this is on the granularity of icustayids)
-- We get three seperate datasets: 
--1) merged_mix_features
--2) merged_inv_features
--3) merged_noninv_features

--Before we start: 
-- Create indices for Efficiency:
CREATE INDEX idx_meds_icustay_context ON ce_approach.additional_meds_in_windows (icustay_id, context_start, context_end);
CREATE INDEX idx_mw_icustay_context ON ce_approach.mix_windows (icustay_id, context_start, context_end);
CREATE INDEX idx_base_icustay_context ON ce_approach.mix_windows_statistical_features (icustay_id, context_start, context_end);

CREATE INDEX idx_mw_icustay_context ON ce_approach.invasive_windows (icustay_id, context_start, context_end);
CREATE INDEX idx_base_icustay_context ON ce_approach.invasive_windows_statistical_features (icustay_id, context_start, context_end);

CREATE INDEX idx_mw_icustay_context ON ce_approach.noninvasive_windows (icustay_id, context_start, context_end);
CREATE INDEX idx_base_icustay_context ON ce_approach.noninvasive_windows_statistical_features (icustay_id, context_start, context_end);

-- Für Meta-Daten (nur icustay_id)
CREATE INDEX idx_meta_icustay ON ce_approach.mv_metadata_binned (icustay_id);

-- Für den split-Join
CREATE INDEX idx_split_subject ON ce_approach.split_all_subjects (subject_id);

-- 1) dataset with base: mix_windows_statistical_features
CREATE Table ce_approach.merged_mix_features AS 
SELECT 
    -- subject_id (not in base, therefore from mix_windows)
    mw.subject_id,
    -- MAP statistical features and flag 'only_2_values'
    base.icustay_id,
    base.context_start,
    base.context_end,
    base.mean,
    base.median,
    base.min,
    base.max,
    base.std,
    base.iqr,
    base.first,
    base.last,
    base.rate_change,
    base.slope,
    base.weighted_mean,
    CAST(base.only_2_values AS INTEGER) AS only_2_values, -- would be true/false otherwise
    -- binned patient metadata
    meta.gender_bin,
    meta.ethnicity_bin,
    meta.age_bin,
    meta.height_bin,
    meta.weight_bin,
    meta.bmi_bin,
    -- comorbidities
    meta.obesity,
    meta.hypertension,
    meta.diabetes,
    meta.kidney_disease,
    meta.lung_disease,
    meta.heart_disease,
    meta.drug_abuse,
    meta.depression,
    -- 11 additional med categories
    meds.sedatives_given,
    meds.blood_products_transfusions_given,
    meds.antibiotics_given,
    meds.anticoagulants_antiplatelets_given,
    meds.neuromuscular_blockers_given,
    meds.analgesics_given,
    meds.crystalloids_given,
    meds.electrolytes_given,
    meds.gi_protection_given,
    meds.parenteral_nutrition_given,
    meds.antiarrhythmics_given,
    -- add: treatment_given and positive sample, positive event from mix_windows 
    -- mw.treatment_count,
    (CASE WHEN mw.treatment_count > 0 THEN 1 ELSE 0 END)::INTEGER AS treatment_given,
    mw.positive_sample,
    mw.positive_event,
    -- add: split column (train,val,test)
    split.split
FROM ce_approach.mix_windows_statistical_features base
LEFT JOIN ce_approach.additional_meds_in_windows meds
  ON base.icustay_id = meds.icustay_id
  AND base.context_start = meds.context_start
  AND base.context_end = meds.context_end
LEFT JOIN ce_approach.mv_metadata_binned meta
  ON base.icustay_id = meta.icustay_id
JOIN ce_approach.mix_windows mw
  ON base.icustay_id = mw.icustay_id
  AND base.context_start = mw.context_start
  AND base.context_end = mw.context_end
LEFT JOIN ce_approach.split_all_subjects split
  ON mw.subject_id = split.subject_id;


  -- 2) dataset with base: invasive_windows_statistical_features
CREATE Table ce_approach.merged_inv_features AS 
SELECT 
    -- subject_id (not in base, therefore from invasive_windows)
    iw.subject_id,
    -- MAP statistical features and flag 'only_2_values'
    base.icustay_id,
    base.context_start,
    base.context_end,
    base.mean,
    base.median,
    base.min,
    base.max,
    base.std,
    base.iqr,
    base.first,
    base.last,
    base.rate_change,
    base.slope,
    base.weighted_mean,
    CAST(base.only_2_values AS INTEGER) AS only_2_values, -- would be true/false otherwise
    -- binned patient metadata
    meta.gender_bin,
    meta.ethnicity_bin,
    meta.age_bin,
    meta.height_bin,
    meta.weight_bin,
    meta.bmi_bin,
    -- comorbidities
    meta.obesity,
    meta.hypertension,
    meta.diabetes,
    meta.kidney_disease,
    meta.lung_disease,
    meta.heart_disease,
    meta.drug_abuse,
    meta.depression,
    -- 11 additional med categories
    meds.sedatives_given,
    meds.blood_products_transfusions_given,
    meds.antibiotics_given,
    meds.anticoagulants_antiplatelets_given,
    meds.neuromuscular_blockers_given,
    meds.analgesics_given,
    meds.crystalloids_given,
    meds.electrolytes_given,
    meds.gi_protection_given,
    meds.parenteral_nutrition_given,
    meds.antiarrhythmics_given,
    -- add: treatment_given and positive sample, positive event from invasive_windows 
    -- mw.treatment_count,
    (CASE WHEN iw.treatment_count > 0 THEN 1 ELSE 0 END)::INTEGER AS treatment_given,
    iw.positive_sample,
    iw.positive_event,
    -- add: split column (train,val,test)
    split.split
FROM ce_approach.invasive_windows_statistical_features base
LEFT JOIN ce_approach.additional_meds_in_windows meds
  ON base.icustay_id = meds.icustay_id
  AND base.context_start = meds.context_start
  AND base.context_end = meds.context_end
LEFT JOIN ce_approach.mv_metadata_binned meta
  ON base.icustay_id = meta.icustay_id
JOIN ce_approach.invasive_windows iw
  ON base.icustay_id = iw.icustay_id
  AND base.context_start = iw.context_start
  AND base.context_end = iw.context_end
LEFT JOIN ce_approach.split_all_subjects split
  ON iw.subject_id = split.subject_id;

  -- 3) dataset with base: noninvasive_windows_statistical_features
CREATE Table ce_approach.merged_noninv_features AS 
SELECT 
    -- subject_id (not in base, therefore from noninvasive_windows)
    niw.subject_id,
    -- MAP statistical features and flag 'only_2_values'
    base.icustay_id,
    base.context_start,
    base.context_end,
    base.mean,
    base.median,
    base.min,
    base.max,
    base.std,
    base.iqr,
    base.first,
    base.last,
    base.rate_change,
    base.slope,
    base.weighted_mean,
    CAST(base.only_2_values AS INTEGER) AS only_2_values, -- would be true/false otherwise
    -- binned patient metadata
    meta.gender_bin,
    meta.ethnicity_bin,
    meta.age_bin,
    meta.height_bin,
    meta.weight_bin,
    meta.bmi_bin,
    -- comorbidities
    meta.obesity,
    meta.hypertension,
    meta.diabetes,
    meta.kidney_disease,
    meta.lung_disease,
    meta.heart_disease,
    meta.drug_abuse,
    meta.depression,
    -- 11 additional med categories
    meds.sedatives_given,
    meds.blood_products_transfusions_given,
    meds.antibiotics_given,
    meds.anticoagulants_antiplatelets_given,
    meds.neuromuscular_blockers_given,
    meds.analgesics_given,
    meds.crystalloids_given,
    meds.electrolytes_given,
    meds.gi_protection_given,
    meds.parenteral_nutrition_given,
    meds.antiarrhythmics_given,
    -- add: treatment_given and positive sample, positive event from noninvasive_windows 
    -- mw.treatment_count,
    (CASE WHEN niw.treatment_count > 0 THEN 1 ELSE 0 END)::INTEGER AS treatment_given,
    niw.positive_sample,
    niw.positive_event,
    -- add: split column (train,val,test)
    split.split
FROM ce_approach.noninvasive_windows_statistical_features base
LEFT JOIN ce_approach.additional_meds_in_windows meds
  ON base.icustay_id = meds.icustay_id
  AND base.context_start = meds.context_start
  AND base.context_end = meds.context_end
LEFT JOIN ce_approach.mv_metadata_binned meta
  ON base.icustay_id = meta.icustay_id
JOIN ce_approach.noninvasive_windows niw
  ON base.icustay_id = niw.icustay_id
  AND base.context_start = niw.context_start
  AND base.context_end = niw.context_end
LEFT JOIN ce_approach.split_all_subjects split
  ON niw.subject_id = split.subject_id;


  ----
  -- 1) dataset with base: mix_windows_statistical_features UPDATED to include target windows
CREATE Table ce_approach.merged_mix_features_updated AS 
SELECT 
    -- subject_id (not in base, therefore from mix_windows)
    mw.subject_id,
    -- MAP statistical features and flag 'only_2_values'
    base.icustay_id,
    base.context_start,
    base.context_end,
    base.context_end AS target_start,
    base.context_end + interval '15 minutes' AS target_end,
    base.mean,
    base.median,
    base.min,
    base.max,
    base.std,
    base.iqr,
    base.first,
    base.last,
    base.rate_change,
    base.slope,
    base.weighted_mean,
    CAST(base.only_2_values AS INTEGER) AS only_2_values, -- would be true/false otherwise
    -- binned patient metadata
    meta.gender_bin,
    meta.ethnicity_bin,
    meta.age_bin,
    meta.height_bin,
    meta.weight_bin,
    meta.bmi_bin,
    -- comorbidities
    meta.obesity,
    meta.hypertension,
    meta.diabetes,
    meta.kidney_disease,
    meta.lung_disease,
    meta.heart_disease,
    meta.drug_abuse,
    meta.depression,
    -- 11 additional med categories
    meds.sedatives_given,
    meds.blood_products_transfusions_given,
    meds.antibiotics_given,
    meds.anticoagulants_antiplatelets_given,
    meds.neuromuscular_blockers_given,
    meds.analgesics_given,
    meds.crystalloids_given,
    meds.electrolytes_given,
    meds.gi_protection_given,
    meds.parenteral_nutrition_given,
    meds.antiarrhythmics_given,
    -- add: treatment_given and positive sample, positive event from mix_windows 
    -- mw.treatment_count,
    (CASE WHEN mw.treatment_count > 0 THEN 1 ELSE 0 END)::INTEGER AS treatment_given,
    mw.positive_sample,
    mw.positive_event,
    -- add: split column (train,val,test)
    split.split
FROM ce_approach.mix_windows_statistical_features base
LEFT JOIN ce_approach.additional_meds_in_windows meds
  ON base.icustay_id = meds.icustay_id
  AND base.context_start = meds.context_start
  AND base.context_end = meds.context_end
LEFT JOIN ce_approach.mv_metadata_binned meta
  ON base.icustay_id = meta.icustay_id
JOIN ce_approach.mix_windows mw
  ON base.icustay_id = mw.icustay_id
  AND base.context_start = mw.context_start
  AND base.context_end = mw.context_end
LEFT JOIN ce_approach.split_all_subjects split
  ON mw.subject_id = split.subject_id;
