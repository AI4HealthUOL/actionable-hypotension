-- Active: 1770284354672@@127.0.0.1@5432@eicu

-- adapted elixhauser mimic git to eICU 
DROP TABLE if exists public.metadata

CREATE TABLE public.metadata AS
WITH demographics AS (
  SELECT
    patientunitstayid,
    patienthealthsystemstayid,
    hospitalid,
    wardid,
    gender,
    CASE
      WHEN age::text ILIKE '%> 89%' THEN 89 --capped at 89
      WHEN age::text ILIKE '' THEN NULL
      ELSE age::int
    END AS age,
    CASE
      WHEN ethnicity ILIKE '%Caucasian%' THEN 'White'
      WHEN ethnicity ILIKE '%African American%' THEN 'Black'
      WHEN ethnicity ILIKE '%asian%' THEN 'Asian'
      WHEN ethnicity ILIKE '%hispanic%' OR ethnicity ILIKE '%latino%' THEN 'Hispanic'
      ELSE 'Other'
    END AS ethnicity_group
  FROM eicu_crd.patient
),
biometrics AS (
  SELECT
    patientunitstayid,
    admissionheight,
    admissionweight,
    CASE
      WHEN admissionheight IS NOT NULL AND admissionheight <> 0 AND admissionweight IS NOT NULL THEN
        ROUND(CAST(admissionweight / POWER(admissionheight / 100.0, 2) AS numeric), 2)
      ELSE NULL
    END AS bmi
  FROM eicu_crd.patient
),
comorbidity_flags AS (
  SELECT
    pat.patientunitstayid,
    CASE
      WHEN eq.diabetes_uncomplicated = 1 OR eq.diabetes_complicated = 1 THEN 1
      ELSE 0
    END AS diabetes,
    COALESCE(eq.renal_failure, 0) AS kidney_disease,
    CASE
      WHEN eq.congestive_heart_failure = 1 OR eq.valvular_disease = 1 THEN 1
      ELSE 0
    END AS heart_disease,
    COALESCE(eq.chronic_pulmonary, 0) AS lung_disease,
    COALESCE(eq.hypertension, 0) AS hypertension,
    COALESCE(eq.obesity, 0) AS obesity,
    COALESCE(eq.drug_abuse, 0) AS drug_abuse,
    COALESCE(eq.depression, 0) AS depression
  FROM eicu_crd.patient pat
  LEFT JOIN public.elixhauser_quan eq
    ON pat.patientunitstayid = eq.patientunitstayid
),
final_metadata AS (
  SELECT 
    dem.patientunitstayid,
    dem.patienthealthsystemstayid,
    dem.hospitalid,
    dem.wardid,
    dem.gender,
    dem.age,
    dem.ethnicity_group,
    bio.admissionheight,
    bio.admissionweight,
    bio.bmi,
    COALESCE(cm.obesity, 0) AS obesity,
    COALESCE(cm.hypertension, 0) AS hypertension,
    COALESCE(cm.diabetes, 0) AS diabetes,
    COALESCE(cm.kidney_disease, 0) AS kidney_disease,
    COALESCE(cm.lung_disease, 0) AS lung_disease,
    COALESCE(cm.heart_disease, 0) AS heart_disease,
    COALESCE(cm.drug_abuse, 0) AS drug_abuse,
    COALESCE(cm.depression, 0) AS depression
  FROM demographics dem
  LEFT JOIN biometrics bio
    ON dem.patientunitstayid = bio.patientunitstayid
  LEFT JOIN comorbidity_flags cm
    ON dem.patientunitstayid = cm.patientunitstayid
)
SELECT * FROM final_metadata;



