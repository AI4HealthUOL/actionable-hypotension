
-- 3) Add label-columns to all context_target_windows (3 columns: 
--        1) Positive Sample? (is there any vasopressor administration at all in the icustay?)
--        2) Positive Event? (is there at least one vasopressor administration in the current target window?)
--        3) Treatment Count (how many active vasopressor treatments are there at the time of the current context window?))
DROP TABLE IF EXISTS public.all_labeled_windows

CREATE TABLE public.all_labeled_windows AS 
SELECT
  w.*,
  -- Whether the patientunitstayid a positive sample or not
  CASE WHEN EXISTS (
      SELECT 1 FROM public.catecholamine_events_4h t
      WHERE t.patientunitstayid = w.patientunitstayid
  ) THEN TRUE ELSE FALSE END AS positive_sample,
  -- Whether any VP administration starts in the current target window
  CASE WHEN EXISTS (
      SELECT 1 FROM public.catecholamine_events_4h t
      WHERE t.patientunitstayid = w.patientunitstayid
        AND t.infusionoffset >= w.target_start_offset_min
        AND t.infusionoffset <= w.target_end_offset_min   
  ) THEN TRUE ELSE FALSE END AS positive_event
  -- Treatments that started during the target window
  -- (
  --   SELECT JSON_AGG(
  --     JSON_BUILD_OBJECT(
  --       'label', t.drugname,
  --       'offset', t.infusionoffset
  --     )
  --     ORDER BY t.infusionoffset
  --   )
  --   FROM public.catecholamine_events_4h t
  --   WHERE t.patientunitstayid = w.patientunitstayid
  --     AND t.infusionoffset >= w.target_start_offset_min
  --     AND t.infusionoffset <= w.target_end_offset_min 
  -- ) AS treatments_start_in_tw,
  -- -- Treatments that started during the target window
  -- (
  --   SELECT JSON_AGG(
  --     JSON_BUILD_OBJECT(
  --       'label', t.drugname,
  --       'offset', t.infusionoffset 
  --     )
  --     ORDER BY t.infusionoffset
  --   )
  --   FROM public.catecholamine_events_4h t
  --   WHERE t.patientunitstayid = w.patientunitstayid
  --     AND t.infusionoffset >= w.context_start_offset_min
  --     AND t.infusionoffset <= w.context_end_offset_min 
  -- ) AS treatments_start_in_cw
FROM public.all_context_target_windows w;


-- SPEED OPTIMIERUNG -------------------------------------------------------------------------

CREATE INDEX ON public.catecholamine_events_4h (patientunitstayid, infusionoffset);
CREATE INDEX ON public.catecholamine_events_4h (patientunitstayid, drugname);


SELECT indexname, indexdef
FROM pg_indexes
WHERE schemaname = 'public'
  AND tablename = 'all_context_target_windows';

CREATE INDEX ON public.all_context_target_windows(patientunitstayid)

DROP INDEX if exists all_context_target_windows_patientunitstayid_context_start__idx

CREATE INDEX ON public.all_context_target_windows(patientunitstayid, target_start_offset_min)

CREATE INDEX ON public.all_context_target_windows(patientunitstayid, target_end_offset_min)

CREATE INDEX ON public.all_context_target_windows(patientunitstayid, context_start_offset_min)

CREATE INDEX ON public.all_context_target_windows(patientunitstayid, context_end_offset_min)


--- CHECK RESULTS ----
-- check for duplicate labels inside one target window ( one still ongoing and another one starting)
SELECT *
FROM ce_approach.all_mv_labeled_windows
WHERE EXISTS (
  SELECT 1
  FROM (
    SELECT jsonb_array_elements(treatments_ongoing::jsonb)->>'label' AS label_ongoing
  ) o
  INNER JOIN (
    SELECT jsonb_array_elements(treatments_start_in_tw::jsonb)->>'label' AS label_start
  ) s ON o.label_ongoing = s.label_start
);
-- von 36.131 positive events sind 545 wo es einen overlap gibt zwischen treatment ongoing und treatment start in targetwindow 

SELECT *
FROM catecholamine_events_4h
WHERE icustay_id = '239034'
ORDER BY treatment_starttime;

