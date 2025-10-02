--Indexing for efficiency
SELECT
  indexname,
  indexdef
FROM
  pg_indexes
WHERE
  tablename = 'inputevents_mv';

CREATE INDEX idx_inputevents_icustay_id
ON mimiciii.inputevents_mv(icustay_id);

CREATE INDEX idx_inputevents_time_range
ON mimiciii.inputevents_mv(icustay_id, starttime, endtime);

CREATE INDEX idx_context_icustay_id
ON ce_approach.all_mv_labeled_windows(icustay_id);

CREATE INDEX idx_context_time_range
ON ce_approach.all_mv_labeled_windows(icustay_id, context_start, context_end);



-- Use the mapping table to create a table that for each context window defines if any of these itemid
-- are given or not 
--Copy all_mv_labeled_windows
--add a column for each drug_class in mv_drug_item_map
-- check for each itemid if documented in inputevents_mv for the icustay_id of the current context window 
-- AND if yes, if treatment end_time > context_start AND treatment_starttime <= context_start 
-- if any is given the column gets a 1, if not the column gets a 0 

-- 1) Join inputevents_mv with relevant item_ids, their label and drug_class (11 categories)
CREATE TABLE ce_approach.additional_meds_in_windows AS   
WITH relevant_inputevents AS (
  SELECT
    ie.icustay_id,
    ie.starttime,
    ie.endtime,
    m.itemid,
    m.label,
    m.drug_class
  FROM mimiciii.inputevents_mv ie
  JOIN public.mv_drug_item_map m
    ON ie.itemid = m.itemid
  WHERE ie.starttime IS NOT NULL
    AND ie.endtime IS NOT NULL
    AND ie.icustay_id IS NOT NULL
),
--2) Join our context_windows (all_mv_labeled_windows) to the relevant inputevents WHERE there is a relevant treatment overlapping with the context window  
-- (distinct entries per drug_class per window)
drug_administrations_per_window AS (
  SELECT
    w.icustay_id,
    w.context_start,
    w.context_end,
    r.drug_class
  FROM ce_approach.all_mv_labeled_windows w
  JOIN relevant_inputevents r
    ON w.icustay_id = r.icustay_id
    AND r.endtime > w.context_start
    AND r.starttime <= w.context_end
  GROUP BY w.icustay_id, w.context_start, w.context_end, r.drug_class
),
-- keep information of labels: Just to inspect what drug_class/label pairs are present
--distinct_drugs_given AS (
--  SELECT DISTINCT 
--   icustay_id,
 --  context_start,
 --  context_end,
 --  drug_class,
 --  label
 --  FROM drug_administrations_per_window
-- ),
-- Left join all context windows with drug_administrations per window 
drug_flags AS (
  SELECT
    w.icustay_id,
    w.context_start,
    w.context_end,
    d.drug_class
  FROM ce_approach.all_mv_labeled_windows w
  LEFT JOIN drug_administrations_per_window d
    ON w.icustay_id = d.icustay_id
    AND w.context_start = d.context_start
    AND w.context_end = d.context_end
)
SELECT
  icustay_id,
  context_start,
  context_end,
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
GROUP BY icustay_id, context_start, context_end

-- Sanity check ( windows in ce_approach.all_mv_labeled_windows die nicht in additional_meds_in_windows sind )
SELECT *
FROM ce_approach.all_mv_labeled_windows w
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







 