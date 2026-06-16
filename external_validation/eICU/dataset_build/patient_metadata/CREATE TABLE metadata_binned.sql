## Learned from the mistake and do not use Ntile(4), instead compute IQR and use Q1 and Q3 as cutoffs 
-- Also include the additional meds already 
-- Step 1: Map gender and ethnicity to integer codes
CREATE TABLE public.metadata_binned AS
WITH base_encoded AS (
  SELECT *,
    CASE
      WHEN gender = 'Male' THEN 0
      WHEN gender = 'Female' THEN 1
      ELSE NULL
    END AS gender_bin,

    CASE
      WHEN ethnicity_group ILIKE '%white%' THEN 0
      WHEN ethnicity_group ILIKE '%black%' THEN 1
      WHEN ethnicity_group ILIKE '%hispanic%' THEN 2
      WHEN ethnicity_group ILIKE '%asian%' THEN 3
      ELSE 4
    END AS ethnicity_bin
  FROM public.metadata
),
iqr_values AS (
  SELECT
    PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY age) AS age_q1,
    PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY age) AS age_q3,
    PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY admissionheight) AS admissionheight_q1,
    PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY admissionheight) AS admissionheight_q3,
    PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY admissionweight) AS admissionweight_q1,
    PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY admissionweight) AS admissionweight_q3,
    PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY bmi) AS bmi_q1,
    PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY bmi) AS bmi_q3
  FROM public.metadata
  WHERE age IS NOT NULL AND admissionheight IS NOT NULL AND admissionweight IS NOT NULL AND bmi IS NOT NULL
  -- Step 2: Create binned versions of continuous variables 
), binned_data AS (
  SELECT 
    m.patientunitstayid,

    CASE 
      WHEN age < i.age_q1 THEN 1
      WHEN age >= i.age_q1 AND age < ((i.age_q1 + i.age_q3)/2) THEN 2
      WHEN age >= ((i.age_q1 + i.age_q3)/2) AND age < i.age_q3 THEN 3
      ELSE 4
    END AS age_bin,

    CASE 
      WHEN admissionheight < i.admissionheight_q1 THEN 1
      WHEN admissionheight >= i.admissionheight_q1 AND admissionheight < ((i.admissionheight_q1 + i.admissionheight_q3)/2) THEN 2
      WHEN admissionheight >= ((i.admissionheight_q1 + i.admissionheight_q3)/2) AND admissionheight < i.admissionheight_q3 THEN 3
      ELSE 4
    END AS admissionheight_bin,

    CASE 
      WHEN admissionweight < i.admissionweight_q1 THEN 1
      WHEN admissionweight >= i.admissionweight_q1 AND admissionweight < ((i.admissionweight_q1 + i.admissionweight_q3)/2) THEN 2
      WHEN admissionweight >= ((i.admissionweight_q1 + i.admissionweight_q3)/2) AND admissionweight < i.admissionweight_q3 THEN 3
      ELSE 4
    END AS admissionweight_bin,

    CASE 
      WHEN bmi < i.bmi_q1 THEN 1
      WHEN bmi >= i.bmi_q1 AND bmi < ((i.bmi_q1 + i.bmi_q3)/2) THEN 2
      WHEN bmi >= ((i.bmi_q1 + i.bmi_q3)/2) AND bmi < i.bmi_q3 THEN 3
      ELSE 4
    END AS bmi_bin

  FROM metadata m CROSS JOIN iqr_values i
)
-- Step 3: Assemble final table
SELECT 
  b.patienthealthsystemstayid,
  b.patientunitstayid,
  b.gender,
  b.gender_bin,
  b.ethnicity_group,
  b.ethnicity_bin,
  b.age,
  bd.age_bin,
  b.admissionheight,
  bd.admissionheight_bin,
  b.admissionweight,
  bd.admissionweight_bin,
  b.bmi,
  bd.bmi_bin,
  b.obesity,
  b.hypertension,
  b.diabetes,
  b.kidney_disease,
  b.lung_disease,
  b.heart_disease,
  b.drug_abuse,
  b.depression
FROM base_encoded b
LEFT JOIN binned_data bd ON b.patientunitstayid = bd.patientunitstayid;