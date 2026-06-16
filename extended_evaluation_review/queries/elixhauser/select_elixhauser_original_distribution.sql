-- Active: 1768480900465@@localhost@5434@mimic
SELECT
  COUNT(*) AS n,
  SUM(eq.diabetes_uncomplicated) AS diabetes_uncomplicated_count,
  100.0 * AVG(eq.diabetes_uncomplicated) AS diabetes_uncomplicated_pct,
  SUM(eq.diabetes_complicated) AS diabetes_complicated_count,
  100.0 * AVG(eq.diabetes_complicated) AS diabetes_complicated_pct,

  SUM(eq.renal_failure) AS renal_failure_count,
  100.0 * AVG(eq.renal_failure) AS renal_failure_pct,

  SUM(eq.congestive_heart_failure) AS congestive_heart_failure_count,
  100.0 * AVG(eq.congestive_heart_failure) AS congestive_heart_failure_pct,

  SUM(eq.valvular_disease) AS valvular_disease_count,
  100.0 * AVG(eq.valvular_disease) AS valvular_disease_pct,

  SUM(eq.chronic_pulmonary) AS chronic_pulmonary_count,
  100.0 * AVG(eq.chronic_pulmonary) AS chronic_pulmonary_pct,

  SUM(eq.hypertension) AS hypertension_count,
  100.0 * AVG(eq.hypertension) AS hypertension_pct,

  SUM(eq.obesity) AS obesity_count,
  100.0 * AVG(eq.obesity) AS obesity_pct,

  SUM(eq.drug_abuse) AS drug_abuse_count,
  100.0 * AVG(eq.drug_abuse) AS drug_abuse_pct,

  SUM(eq.depression) AS depression_count,
  100.0 * AVG(eq.depression) AS depression_pct

FROM ce_approach.elixhauser_quan eq;

-- 
SELECT COUNT(*) FROM ce_approach.merged_mix_features WHERE hypertension = 1 and positive_event = 1