-- This script has the job to create a table with all our positive treatment events for all vasopressors, similar to
-- combined_consecutive_events. After understanding that there are FOR SURE no bolus-information in Metavision I found a standardized approach from 
-- MIT : vaso.sql - and here I adopted their logic but only for metavision, not for carevue. 
-- New setup: 

--1) 
-- For each Icustay id and itemid (those we are interested in) and linkorderid: group together and take earliest starttime and latest endtime. This should be textbook treatment interval, dropping rate information. 

CREATE TABLE ce_approach.linkorder_treatment_events AS
-- Step 1: Extract only relevant itemids
WITH io_mv AS (
  SELECT
    i.subject_id,
    i.icustay_id,
    i.linkorderid,
    i.itemid,
    m.label,
    i.rate,
    i.rateuom,
    i.amount,
    i.amountuom,
    i.starttime,
    i.endtime
  FROM mimiciii.inputevents_mv i
  JOIN public.mv_itemid_mapping m ON i.itemid = m.itemid
  WHERE i.statusdescription != 'Rewritten'
),
-- Step 2: Aggregate by linkorderid (but only as Vorarbeit für Zeitfenster)
vasomv_raw AS (
  SELECT
    subject_id,
    icustay_id,
    linkorderid,
    itemid,
    label,
    AVG(rate) AS avg_rate,
    AVG(amount) AS avg_amount,
    MAX(rate) AS max_rate,
    MAX(amount) AS max_amount,
    rateuom,
    amountuom,
    MIN(starttime) AS starttime,
    MAX(endtime) AS endtime,
    COUNT(*) AS n_merged_entries
  FROM io_mv
  GROUP BY subject_id, icustay_id, linkorderid, itemid, label, rateuom, amountuom
),
-- Step 3: Gruppiere überlappende Episoden zu zusammenhängenden Blöcken
vasomv_grp AS (
  SELECT
    s1.subject_id,
    s1.icustay_id,
    s1.itemid,
    s1.label,
    MIN(s1.starttime) AS starttime,
    MIN(t1.endtime) AS endtime
  FROM vasomv_raw s1
  INNER JOIN vasomv_raw t1
    ON s1.icustay_id = t1.icustay_id
    AND s1.itemid = t1.itemid  -- nur Episoden derselben Substanz verbinden!
    AND s1.starttime <= t1.endtime
    AND NOT EXISTS (
      SELECT 1 FROM vasomv_raw t2
      WHERE t1.icustay_id = t2.icustay_id
        AND t1.itemid = t2.itemid
        AND t1.endtime >= t2.starttime
        AND t1.endtime < t2.endtime
    )
  WHERE NOT EXISTS (
    SELECT 1 FROM vasomv_raw s2
    WHERE s1.icustay_id = s2.icustay_id
      AND s1.itemid = s2.itemid
      AND s1.starttime > s2.starttime
      AND s1.starttime <= s2.endtime
  )
  GROUP BY s1.subject_id,s1.icustay_id, s1.itemid, s1.label, s1.starttime
)
-- Step 4: Baue finale Tabelle mit Metainfos
SELECT
  v.subject_id,
  v.icustay_id,
  v.itemid,
  icu.hadm_id,
  v.label,
  v.starttime AS treatment_starttime,
  v.endtime AS treatment_endtime,
  v.endtime - v.starttime AS treatment_duration,
  icu.intime AS icu_intime,
  icu.outtime AS icu_outtime
FROM vasomv_grp v
JOIN mimiciii.icustays icu ON v.icustay_id = icu.icustay_id
ORDER BY subject_id, icustay_id, itemid, treatment_starttime;


-- Check time overlap: 418 from 40373, but given that they are seperated by linkorderid they should be fine to overlap
-- sometimes the overlap is just a minute 
-- sometimes the overlap is a short segment burried inside a very long one 
CREATE TEMP TABLE overlapping_same_drug_events AS
SELECT
  a.subject_id,
  a.icustay_id,
  a.itemid,
  a.label,
  a.linkorderid AS linkorderid_a,
  a.avg_amount AS avg_amount_a,
  a.avg_rate AS avg_rate_a,
  a.treatment_starttime AS treatment_starttime_a,
  a.treatment_endtime AS treatment_endtime_a,
  b.linkorderid AS linkorderid_b,
  b.avg_amount AS avg_amount_b,
  b.avg_rate AS avg_rate_b,
  b.treatment_starttime AS treatment_starttime_b,
  b.treatment_endtime AS treatment_endtime_b
FROM linkorder_treatment_events a
JOIN linkorder_treatment_events b
  ON a.icustay_id = b.icustay_id
  AND a.itemid = b.itemid
  AND a.linkorderid < b.linkorderid  -- eliminate duplicates
  AND a.treatment_endtime > b.treatment_starttime
  AND a.treatment_starttime < b.treatment_endtime
ORDER BY a.icustay_id, a.itemid, a.treatment_starttime;

-- New column same_drug_overlap 
ALTER TABLE linkorder_treatment_events_copy
ADD COLUMN IF NOT EXISTS same_drug_overlap BOOLEAN DEFAULT FALSE;

UPDATE linkorder_treatment_events_copy
SET same_drug_overlap = TRUE
WHERE linkorderid IN (
  SELECT linkorderid_a FROM overlapping_same_drug_events
);

-- Check differences:
(   SELECT icustay_id, itemid, treatment_starttime FROM combined_consecutive_events
    EXCEPT
    SELECT icustay_id, itemid, treatment_starttime FROM linkorder_treatment_events)  
UNION ALL
(   SELECT icustay_id, itemid, treatment_starttime FROM linkorder_treatment_events
    EXCEPT
    SELECT icustay_id, itemid, treatment_starttime FROM combined_consecutive_events) 



-- Setting an is_escalation flag for the 416 same_drug_overlaps 
ALTER TABLE linkorder_treatment_events_copy
ADD COLUMN is_escalation BOOLEAN DEFAULT FALSE;

-- Escalation: later overlapping treatment with significantly higher max_rate -- 74! 
WITH same_drug_overlaps AS (
    SELECT 
        curr.subject_id,
        curr.icustay_id,
        curr.linkorderid AS current_linkorderid,
        curr.itemid,
        curr.treatment_starttime,
        curr.max_rate AS current_rate,
        prev.linkorderid AS previous_linkorderid,
        prev.max_rate AS previous_rate,
        prev.treatment_endtime AS previous_endtime
    FROM linkorder_treatment_events_copy curr
    JOIN linkorder_treatment_events_copy prev
        ON curr.icustay_id = prev.icustay_id
        AND curr.itemid = prev.itemid
        AND curr.treatment_starttime < prev.treatment_endtime
        AND curr.treatment_starttime > prev.treatment_starttime
        AND curr.linkorderid <> prev.linkorderid
    WHERE
        curr.max_rate > 0.5 -- ignore noise
        AND curr.max_rate > 1.2 * prev.max_rate -- significant increase
)
UPDATE linkorder_treatment_events_copy
SET is_escalation = TRUE
FROM same_drug_overlaps
WHERE linkorder_treatment_events_copy.icustay_id = same_drug_overlaps.icustay_id
  AND linkorder_treatment_events_copy.linkorderid = same_drug_overlaps.current_linkorderid
  AND linkorder_treatment_events_copy.itemid = same_drug_overlaps.itemid;

-- another column that flags if rate is too little 

-- Limitations of the link order id approach: 
--Implication:
-- If a nurse reused the same linkorderid for a norepi infusion that was stopped and restarted hours later, Step 2 will merge those into one continuous block, even though clinically there was a gap.
-- That’s a limitation of the GROUP BY linkorderid approach.
