
-- 3) Add label-columns to all context_target_windows (3 columns: 
--        1) Positive Sample? (is there any vasopressor administration at all in the icustay?)
--        2) Positive Event? (is there at least one vasopressor administration in the current target window?)
--        3) Treatment Count (how many active vasopressor treatments are there at the time of the current context window?))


-- EXTENSION: to positive_event 15 min, 30 min and 60 min! 
CREATE TABLE ce_approach.all_mv_labeled_windows_extended AS 
SELECT
  w.*,
  -- Whether the icustay is a positive sample or not
  CASE WHEN EXISTS (
      SELECT 1 FROM ce_approach.linkorder_treatment_events t
      WHERE t.icustay_id = w.icustay_id
  ) THEN TRUE ELSE FALSE END AS positive_sample,
  -- Whether any VP administration starts in the 15 min, 30 min or 60 min target window
  CASE WHEN EXISTS (
      SELECT 1 FROM ce_approach.linkorder_treatment_events t
      WHERE t.icustay_id = w.icustay_id
        AND t.treatment_starttime >= w.target_start
        AND t.treatment_starttime <= w.target_end   
  ) THEN TRUE ELSE FALSE END AS positive_event,
  -- Treatment Counter -- muss im context window schauen 
  (
    SELECT COUNT(*) FROM ce_approach.linkorder_treatment_events t
    WHERE t.icustay_id = w.icustay_id
      AND t.treatment_starttime < w.context_end
      AND t.treatment_endtime >= w.context_start
  ) AS treatment_count,
  -- Treatments that were already ongoing when target starts
  (
    SELECT JSON_AGG(
      JSON_BUILD_OBJECT(
        'label', t.label,
        'starttime', to_char(t.treatment_starttime, 'YYYY-MM-DD HH24:MI:SS')
      )
      ORDER BY t.treatment_starttime
    )
    FROM ce_approach.linkorder_treatment_events t
    WHERE t.icustay_id = w.icustay_id
      AND t.treatment_starttime < w.context_end
      AND t.treatment_endtime >= w.context_start
  ) AS treatments_ongoing,
  -- Treatments that started during the target window
  (
    SELECT JSON_AGG(
      JSON_BUILD_OBJECT(
        'label', t.label,
        'starttime', to_char(t.treatment_starttime, 'YYYY-MM-DD HH24:MI:SS')
      )
      ORDER BY t.treatment_starttime
    )
    FROM ce_approach.linkorder_treatment_events t
    WHERE t.icustay_id = w.icustay_id
      AND t.treatment_starttime >= w.target_start
      AND t.treatment_starttime <= w.target_end
  ) AS treatments_start_in_tw,
  (
    SELECT JSON_AGG(
      JSON_BUILD_OBJECT(
        'label', t.label,
        'starttime', to_char(t.treatment_starttime, 'YYYY-MM-DD HH24:MI:SS')
      )
      ORDER BY t.treatment_starttime
    )
    FROM ce_approach.linkorder_treatment_events t
    WHERE t.icustay_id = w.icustay_id
      AND t.treatment_starttime >= w.context_start
      AND t.treatment_starttime < w.context_end
  ) AS treatments_start_in_cw
FROM ce_approach.all_mv_context_target_windows w;


-- SPEED OPTIMIERUNG -------------------------------------------------------------------------

CREATE INDEX ON ce_approach.linkorder_treatment_events (icustay_id, treatment_starttime);
CREATE INDEX ON ce_approach.linkorder_treatment_events (icustay_id, treatment_endtime);
CREATE INDEX ON ce_approach.linkorder_treatment_events (icustay_id, label);


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
FROM linkorder_treatment_events
WHERE icustay_id = '239034'
ORDER BY treatment_starttime;

