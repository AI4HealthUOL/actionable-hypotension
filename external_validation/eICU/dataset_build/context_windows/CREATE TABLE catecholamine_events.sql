-- Problem, we have no linkorderid in eICU:
""" A patient can be:

off norepi for 2 hours → restart = same shock episode

off norepi for 2 hours → restart = new shock
In MIMICIII Carevue they did something similar to infer the logic: when previous rate was 0 now <0 then start, stop when rate is either 0, or stop signal.
We do not have these Status signals in eicu so honest limitation is: multiple episodes of the same drug per stay are not defensible, wihtout introducing 
a hardcoded time gap which we didnt have in mimic3. So here we define at most one episode per vasopressor per ICU stay in eICU.
"""
SELECT DISTINCT
  drugname
FROM eicu_crd.infusiondrug
WHERE LOWER(drugname) ~
  '(norepinephrine|epinephrine|phenylephrine|vasopressin|dopamine|dobutamine|milrinone)';



SELECT
    patientunitstayid,
    drugname,
    infusionoffset,
    infusionrate,
    LEAD(infusionoffset) OVER (
      PARTITION BY patientunitstayid, drugname
      ORDER BY infusionoffset
    ) AS next_infusionoffset
  FROM eicu_crd.infusiondrug
  WHERE LOWER(drugname) ~
  '(norepinephrine|epinephrine|phenylephrine|vasopressin|dopamine|dobutamine|milrinone)'
  

SELECT
    patientunitstayid,
    drugname,
    infusionoffset,
    infusionrate,
    LAG(infusionoffset) OVER (
      PARTITION BY patientunitstayid, drugname ORDER BY infusionoffset
    ) AS prev_offset,
    LAG(infusionrate) OVER (
      PARTITION BY patientunitstayid, drugname ORDER BY infusionoffset
    ) AS prev_infusionrate
  FROM eicu_crd.infusiondrug
   WHERE LOWER(drugname) ~
  '(norepinephrine|epinephrine|phenylephrine|vasopressin|dopamine|dobutamine|milrinone)'
  AND infusionrate != ''
  
  
Drop table if exists public.catecholamine_events

CREATE TABLE public.catecholamine_events_pure AS
WITH vaso_events AS (
  -- Select previous infusion offset and previous infusion rate 
  SELECT
    patientunitstayid,
    drugname,
    infusionoffset,
    infusionrate,
    LAG(infusionoffset) OVER (
      PARTITION BY patientunitstayid, drugname ORDER BY infusionoffset
    ) AS prev_offset,
    LAG(infusionrate) OVER (
      PARTITION BY patientunitstayid, drugname ORDER BY infusionoffset
    ) AS prev_infusionrate
  FROM eicu_crd.infusiondrug
  WHERE LOWER(drugname) ~
  '(norepinephrine|epinephrine|phenylephrine|vasopressin|dopamine|dobutamine|milrinone)'
  AND infusionrate != '' 
  And COALESCE(NULLIF(infusionrate, '')::float, 0) != 0
  And infusionoffset > 0 
),
-- Definiere Threshold, z.B. 4 Stunden = 240 Minuten Pause
vaso_with_flags AS (
  SELECT
    *,
    CASE
      WHEN prev_offset IS NULL THEN 1  -- erster Eintrag = neuer Block -- we can only reliably do this one!
      -- WHEN infusionoffset - prev_offset > 240 THEN 1  -- mehr als 4h Pause? 
      -- WHEN (COALESCE(prev_infusionrate::float, 0) = 0) AND infusionrate::float > 0 THEN 1 -- Restart nach Pause oder Dosiserhöhung von 0
      ELSE 0
    END AS new_onset_flag
  FROM vaso_events
),
vaso_onsets AS (
  SELECT DISTINCT 
  patientunitstayid, 
  infusionoffset,
  drugname, 
  infusionrate
  
  FROM vaso_with_flags
  WHERE new_onset_flag = 1 
)
SELECT * FROM vaso_onsets
ORDER BY patientunitstayid, infusionoffset, drugname;








