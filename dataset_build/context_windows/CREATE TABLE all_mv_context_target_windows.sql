-- 1) get all possible context windows (2hour context window, 15 min target window - hopsize of 15 minutes)
-- use all distinct ICU stay IDS from inputevents_mv (to include also negative samples) as base ( table "all_mv_icu_stays as base")
CREATE TABLE ce_approach.all_mv_context_target_windows AS
SELECT
  ams.subject_id,
  ams.icustay_id,
  ams.hadm_id,
  ams.icu_intime + n * interval '15 minutes' AS context_start,
  ams.icu_intime + n * interval '15 minutes' + interval '2 hours' AS context_end,
  ams.icu_intime + n * interval '15 minutes' + interval '2 hours' AS target_start,
  ams.icu_intime + n * interval '15 minutes' + interval '2 hours 15 minutes' AS target_end,
  ams.icu_intime,
  ams.icu_outtime
FROM ce_approach.all_mv_icu_stays ams,
     generate_series(0,
    CAST(FLOOR(EXTRACT(EPOCH FROM (icu_outtime - icu_intime - interval '2 hours 15 minutes')) / 900) AS INT)
) AS n -- dynamische Erzeugung von n je nach Länge des ICU Aufenthalts, letzte Stück wird verworfen
WHERE
  ams.icu_intime + n * interval '15 minutes' + interval '2 hours 15 minutes' <= ams.icu_outtime;