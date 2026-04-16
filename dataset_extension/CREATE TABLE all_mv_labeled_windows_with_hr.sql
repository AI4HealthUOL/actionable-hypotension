-- Active: 1768480900465@@localhost@5434@mimic
-- Drop the existing table if it exists
DROP TABLE IF EXISTS evaluation.all_mv_labeled_windows_with_heart_rate;

-- Create a table of labeled context windows with associated MAP values
-- Only includes values in range 30–200 and of types 220052, 225312, 220181
-- MAP values are stored as JSON objects with relative time ("pos") and value
-- Also counts the number of values per window
-- already filtered for values >= 2
CREATE TABLE evaluation.all_mv_labeled_windows_with_heart_rate AS
WITH filtered_ce AS (
  SELECT
    icustay_id,
    charttime,
    valuenum,
    itemid
  FROM mimiciii.chartevents
  WHERE valuenum IS NOT NULL
    AND valuenum BETWEEN 0 AND 300
    AND itemid = 220045
),
hr_agg AS (
  SELECT
    w.subject_id,
    w.icustay_id,
    w.context_start,
    w.context_end,
    w.target_start,
    w.target_end,
    w.icu_intime,
    w.icu_outtime,
    w.positive_sample,
    w.positive_event,
    w.treatment_count,
    COUNT(ce.valuenum) AS value_count,
    ARRAY_AGG(
      jsonb_build_object(
        'pos', EXTRACT(EPOCH FROM (ce.charttime - w.context_start)),
        'value', ce.valuenum
      )
      ORDER BY ce.charttime
    ) AS hr_values
  FROM ce_approach.all_mv_labeled_windows w
  LEFT JOIN filtered_ce ce
    ON ce.icustay_id = w.icustay_id
    AND ce.charttime BETWEEN w.context_start AND w.context_end
  GROUP BY
    w.subject_id, w.icustay_id, w.context_start, w.context_end,
    w.target_start, w.target_end, w.icu_intime, w.icu_outtime,
    w.positive_sample, w.positive_event, w.treatment_count
)
SELECT
  hr.*,
  w.treatments_ongoing,
  w.treatments_start_in_tw,
  w.treatments_start_in_cw
FROM hr_agg hr
JOIN ce_approach.all_mv_labeled_windows w
  ON hr.icustay_id = w.icustay_id
  AND hr.context_start = w.context_start
  AND hr.context_end = w.context_end
  Where hr.value_count >= 2;