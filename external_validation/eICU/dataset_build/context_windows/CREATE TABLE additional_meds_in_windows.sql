--Indexing for efficiency
SELECT
  indexname,
  indexdef
FROM
  pg_indexes
WHERE
  tablename = 'inputevents_mv';

CREATE INDEX idx_infusiondrug_patientunitstayid
ON eicu_crd.infusiondrug(patientunitstayid);

CREATE INDEX idx_infusiondrug_time_range
ON eicu_crd.infusiondrug(patientunitstayid, infusionoffset);

CREATE INDEX idx_context_patientunitstayid
ON public.all_labeled_windows(patientunitstayid);

CREATE INDEX idx_context_time_range
ON public.all_labeled_windows(patientunitstayid, context_start_offset_min, context_end_offset_min);

-- Für eicu_crd.infusiondrug
CREATE INDEX idx_infusiondrug_drugname ON eicu_crd.infusiondrug(drugname);
CREATE INDEX idx_infusiondrug_infusionoffset ON eicu_crd.infusiondrug(infusionoffset);

-- Für eicu_crd.medication
CREATE INDEX idx_medication_drugname ON eicu_crd.medication(drugname);
CREATE INDEX idx_medication_drugstartoffset ON eicu_crd.medication(drugstartoffset);
CREATE INDEX idx_medication_drugstopoffset ON eicu_crd.medication(drugstopoffset);

-- Für public.eicu_drug_item_map
CREATE INDEX idx_drug_item_map_label ON public.eicu_drug_item_map(label);



-- Use the mapping table to create a table that for each context window defines if any of these itemid
-- are given or not 
--Copy all_mv_labeled_windows
--add a column for each drug_class in mv_drug_item_map
-- check for each itemid if documented in inputevents_mv for the patientunitstayid of the current context window 
-- AND if yes, if treatment end_time > context_start AND treatment_starttime <= context_start 
-- if any is given the column gets a 1, if not the column gets a 0 

-- Difference in eicu: no itemid, have to use drugname or diffusionid or medicationid ( these are not given per infusiondrug or medication but per event where its given to a patient, distinct)
SELECT COUNT(DISTINCT patientunitstayid) FROM eicu_crd.patient


# Performance:
-- Temporäre Tabellen für die Zwischenergebnisse
DROP TABLE if exists temp_all_medications
DROP TABLE if exists temp_all_infusions

SELECT * FROM temp_all_medications;

CREATE TEMP TABLE temp_all_infusions AS
SELECT
    i.patientunitstayid,
    i.infusiondrugid,
    i.infusionoffset,
    i.infusionrate,
    m.label,
    m.drug_class,
    m.source
  FROM eicu_crd.infusiondrug i
  JOIN public.eicu_drug_item_map m
    ON Lower(i.drugname) = m.label
  WHERE i.patientunitstayid IN (SELECT DISTINCT patientunitstayid FROM public.all_labeled_windows)
    AND i.infusionoffset IS NOT NULL
    AND i.infusionrate != '' 
    And COALESCE(NULLIF(i.infusionrate, '')::float, 0) != 0
    AND i.patientunitstayid IS NOT NULL


CREATE TEMP TABLE temp_all_medications AS
  SELECT
    m.patientunitstayid,
    m.medicationid,
    m.drugstartoffset,
    m.drugstopoffset,
    m.dosage,
    ma.label,
    ma.drug_class,
    ma.source
  FROM eicu_crd.medication m
  JOIN public.eicu_drug_item_map ma
    ON Lower(m.drugname) = ma.label
  WHERE m.patientunitstayid IN (SELECT DISTINCT patientunitstayid FROM public.all_labeled_windows)
    AND m.drugname IS NOT NULL --drugname should be given
    AND (
      CASE
          WHEN REGEXP_REPLACE(m.dosage, '[^0-9]', '', 'g') = '' THEN FALSE
          ELSE REGEXP_REPLACE(m.dosage, '[^0-9]', '', 'g')::numeric != 0
      END
  )
    AND m.drugstartoffset > 0 -- start of drug should be in the icu
    AND m.drugstopoffset > 0 -- stop of drug should be in the icu
    AND NOT m.drugordercancelled = 'No' -- the order shouldnt be cancelled
    AND m.patientunitstayid IS NOT NULL -- should have patientunitstayid


-- CREATE TABLE public.additional_meds_in_windows AS   
-- WITH all_infusions AS (
--   SELECT
--     i.patientunitstayid,
--     i.infusiondrugid,
--     i.infusionoffset,
--     i.infusionrate,
--     m.label,
--     m.drug_class,
--     m.source
--   FROM eicu_crd.infusiondrug i
--   JOIN public.eicu_drug_item_map m
--     ON i.drugname = m.label
--   WHERE i.infusionoffset IS NOT NULL
--     AND i.infusionrate != '' 
--     And COALESCE(NULLIF(i.infusionrate, '')::float, 0) != 0
--     AND i.patientunitstayid IS NOT NULL
-- ),
-- all_medications AS (
--   SELECT
--     m.patientunitstayid,
--     m.medicationid,
--     m.drugstartoffset,
--     m.drugstopoffset,
--     m.dosage,
--     ma.label,
--     ma.drug_class,
--     ma.source
--   FROM eicu_crd.medication m
--   JOIN public.eicu_drug_item_map ma
--     ON m.drugname = ma.label
--   WHERE m.drugname IS NOT NULL --drugname should be given
--     AND (
--       CASE
--           WHEN REGEXP_REPLACE(m.dosage, '[^0-9]', '', 'g') = '' THEN FALSE
--           ELSE REGEXP_REPLACE(m.dosage, '[^0-9]', '', 'g')::numeric != 0
--       END
--   )
--     AND m.drugstartoffset > 0 -- start of drug should be in the icu
--     AND m.drugstopoffset > 0 -- stop of drug should be in the icu
--     AND NOT m.drugordercancelled = 'No' -- the order shouldnt be cancelled
--     AND m.patientunitstayid IS NOT NULL -- should have patientunitstayid
-- ),
-- 3. Medikamentenverabreichungen pro Fenster (Infusionen + Medikamente)
CREATE TABLE public.additional_meds_in_windows AS   
WITH drug_administrations_per_window AS (
  -- Infusionen
  SELECT
    w.patientunitstayid,
    w.context_start_offset_min,
    w.context_end_offset_min,
    i.drug_class
  FROM public.all_labeled_windows w
  JOIN temp_all_infusions i
    ON w.patientunitstayid = i.patientunitstayid
    AND i.infusionoffset > w.context_start_offset_min
    AND i.infusionoffset <= w.context_end_offset_min

  UNION ALL
  -- Medikamente
  SELECT
    w.patientunitstayid,
    w.context_start_offset_min,
    w.context_end_offset_min,
    m.drug_class
  FROM public.all_labeled_windows w
  JOIN temp_all_medications m
    ON w.patientunitstayid = m.patientunitstayid
    AND m.drugstopoffset > w.context_start_offset_min
    AND m.drugstartoffset <= w.context_end_offset_min
),
drug_flags AS (
  SELECT
    w.patientunitstayid,
    w.context_start_offset_min,
    w.context_end_offset_min,
    d.drug_class
  FROM public.all_labeled_windows w
  LEFT JOIN drug_administrations_per_window d
    ON w.patientunitstayid = d.patientunitstayid
    AND w.context_start_offset_min = d.context_start_offset_min
    AND w.context_end_offset_min = d.context_end_offset_min
)
-- 5. Ergebnis: Flags pro Fenster
SELECT
  patientunitstayid,
  context_start_offset_min,
  context_end_offset_min,
  MAX(CASE WHEN drug_class = 'sedatives' THEN 1 ELSE 0 END) AS sedatives_given,
  MAX(CASE WHEN drug_class = 'blood_products_transfusions' THEN 1 ELSE 0 END) AS blood_products_transfusions_given,
  MAX(CASE WHEN drug_class = 'antibiotics' THEN 1 ELSE 0 END) AS antibiotics_given,
  MAX(CASE WHEN drug_class = 'anticoagulants_antiplatelets' THEN 1 ELSE 0 END) AS anticoagulants_antiplatelets_given,
  MAX(CASE WHEN drug_class = 'neuromuscular_blockers' THEN 1 ELSE 0 END) AS neuromuscular_blockers_given,
  MAX(CASE WHEN drug_class = 'analgesics' THEN 1 ELSE 0 END) AS analgesics_given,
  MAX(CASE WHEN drug_class = 'crystalloids' THEN 1 ELSE 0 END) AS crystalloids_given,
  MAX(CASE WHEN drug_class = 'electrolytes' THEN 1 ELSE 0 END) AS electrolytes_given,
  MAX(CASE WHEN drug_class = 'gi_protection' THEN 1 ELSE 0 END) AS gi_protection_given,
  MAX(CASE WHEN drug_class = 'parenteral_nutrition' THEN 1 ELSE 0 END) AS parenteral_nutrition_given,
  MAX(CASE WHEN drug_class = 'antiarrhythmics' THEN 1 ELSE 0 END) AS antiarrhythmics_given
FROM drug_flags
GROUP BY patientunitstayid, context_start_offset_min, context_end_offset_min
;






-- Sanity check ( windows in public.all_mv_labeled_windows die nicht in additional_meds_in_windows sind )
SELECT *
FROM public.all_mv_labeled_windows w
LEFT JOIN additional_meds_in_windows a
  ON w.icustay_id = a.icustay_id
  AND w.context_start = a.context_start
  AND w.context_end = a.context_end
WHERE a.icustay_id IS NULL;

-- Sanity check ( duplikate windows in additional_meds_in_windows )
SELECT 
  icustay_id,
  context_start,
  context_end,
  COUNT(*) AS cnt
FROM additional_meds_in_windows
GROUP BY icustay_id, context_start, context_end
HAVING COUNT(*) > 1
ORDER BY cnt DESC;







 