
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
CREATE INDEX if not exists idx_meds_icustay_context ON public.additional_meds_in_windows (patientunitstayid, context_start_offset_min, context_end_offset_min);
CREATE INDEX if not exists idx_mw_icustay_context ON public.mix_windows (patientunitstayid, context_start_offset_min, context_end_offset_min);
CREATE INDEX if not exists idx_base_icustay_context ON public.mix_windows_statistical_features (patientunitstayid, context_start_offset_min, context_end_offset_min);


-- Für Meta-Daten (nur patientunitstayid)
CREATE INDEX if not exists idx_meta_icustay ON public.metadata_binned (patientunitstayid);

-- Für den split-Join
CREATE INDEX if not exists idx_split_subject ON public.split_all_admissions (patienthealthsystemstayid);

-- 1) dataset with base: mix_windows_statistical_features
CREATE Table if not exists public.merged_mix_features AS 
SELECT 
    -- patienthealthsystemstayid (not in base, therefore from mix_windows)
    mw.patienthealthsystemstayid,
    -- MAP statistical features and flag 'only_2_values'
    base.patientunitstayid,
    base.context_start_offset_min,
    base.context_end_offset_min,
    base.context_end_offset_min AS target_start_offset_min,
    base.context_end_offset_min + 15 AS target_end_offset,
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
    -- CAST(base.only_2_values AS INTEGER) AS only_2_values, -- would be true/false otherwise
    -- binned patient metadata
    meta.gender_bin,
    meta.ethnicity_bin,
    meta.age_bin,
    meta.admissionheight_bin,
    meta.admissionweight_bin,
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
    -- (CASE WHEN mw.treatment_count > 0 THEN 1 ELSE 0 END)::INTEGER AS treatment_given,
    mw.positive_sample,
    mw.positive_event,
    -- add: split column (train,val,test)
    split.split
FROM public.mix_windows_statistical_features base
LEFT JOIN public.additional_meds_in_windows meds
  ON base.patientunitstayid = meds.patientunitstayid
  AND base.context_start_offset_min = meds.context_start_offset_min
  AND base.context_end_offset_min = meds.context_end_offset_min
LEFT JOIN public.metadata_binned meta
  ON base.patientunitstayid = meta.patientunitstayid
JOIN public.mix_windows mw
  ON base.patientunitstayid = mw.patientunitstayid
  AND base.context_start_offset_min = mw.context_start_offset_min
  AND base.context_end_offset_min = mw.context_end_offset_min
LEFT JOIN public.split_all_admissions split
  ON mw.patienthealthsystemstayid = split.patienthealthsystemstayid;

