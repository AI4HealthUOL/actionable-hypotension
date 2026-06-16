-- Active: 1756194958052@@127.0.0.1@5432@mimic
-- 1) List of vasopressors and inotropes
SELECT 
    itemid,
    label,
    dbsource,
    linksto
FROM mimiciii.d_items
WHERE label ILIKE 'Levosimendan%'
    OR label ILIKE 'Adenosine%'
   OR label ILIKE 'Dopamine%'
   OR label ILIKE 'Epinephrine%'
   OR label ILIKE 'Norepinephrine%'
   OR label ILIKE 'Vasopressin%'
   OR label ILIKE 'Phenylephrine%'
   OR label ILIKE 'Dobutamine%'
   OR label ILIKE 'Milrinone%';

-- Check out the statuses of our linkorder treatment events (doesnt work yet)
SELECT
  t.icustay_id,
  t.itemid,
  t.treatment_starttime,
  t.treatment_endtime,
  i.starttime,
  i.endtime,
  i.statusdescription,
  i.linkorderid,
  i.rate,
  i.amount
FROM ce_approach.linkorder_treatment_events t
JOIN mimiciii.inputevents_mv i
  ON t.icustay_id = i.icustay_id
  AND t.itemid = i.itemid
  AND t.treatment_starttime = i.starttime
  AND t.linkorderid = i.linkorderid;


SELECT
  t.*,
  i.statusdescription
FROM ce_approach.linkorder_treatment_events t
LEFT JOIN mimiciii.inputevents_mv i
  ON t.icustay_id = i.icustay_id
  AND t.itemid = i.itemid
  AND ABS(EXTRACT(EPOCH FROM (t.treatment_starttime - i.starttime))) < 1;