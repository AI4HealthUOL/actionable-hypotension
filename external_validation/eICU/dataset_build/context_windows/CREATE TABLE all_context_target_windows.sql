-- get all possible context windows (2hour context window, 15 min target window - hopsize of 15 minutes)
-- use all distinct ICU stay IDS from inputevents_mv (to include also negative samples) as base ( table "all_mv_icu_stays as base")

-- CREATE TABLE ce_approach.all_mv_context_target_windows AS
CREATE TABLE public.all_context_target_windows AS
SELECT
  patientunitstayid,
  patienthealthsystemstayid,
  unitadmittime24,
  unitdischargetime24,
  unitdischargeoffset,
  n * 15 AS context_start_offset_min,
  n * 15 + 120 AS context_end_offset_min,
  n * 15 + 120 AS target_start_offset_min,
  n * 15 + 135 AS target_end_offset_min
FROM eicu_crd.patient,
     generate_series(
       0,
       FLOOR( (unitdischargeoffset - 135) / 15 )::int  -- Anzahl der möglichen Fensterstarts
     ) AS n
WHERE unitdischargeoffset > 135
ORDER BY patientunitstayid, context_start_offset_min;