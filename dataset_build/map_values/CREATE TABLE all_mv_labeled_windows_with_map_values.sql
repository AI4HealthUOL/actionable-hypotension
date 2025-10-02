-- Drop the existing table if it exists
DROP TABLE IF EXISTS ce_approach.all_mv_labeled_windows_with_map_values;

-- Create a table of labeled context windows with associated MAP values
-- Only includes values in range 30–200 and of types 220052, 225312, 220181
-- MAP values are stored as JSON objects with relative time ("pos"), value, and type
-- Also counts the number of values per window
CREATE TABLE ce_approach.all_mv_labeled_windows_with_map_values AS
WITH filtered_ce AS (
  SELECT
    icustay_id,
    charttime,
    valuenum,
    itemid
  FROM mimiciii.chartevents
  WHERE valuenum IS NOT NULL
    AND valuenum BETWEEN 30 AND 200
    AND itemid IN (225312, 220052, 220181)
),
map_agg AS (
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
        'value', ce.valuenum,
        'type', ce.itemid
      )
      ORDER BY ce.charttime
    ) AS map_values
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
  ma.*,
  w.treatments_ongoing,
  w.treatments_start_in_tw,
  w.treatments_start_in_cw
FROM map_agg ma
JOIN ce_approach.all_mv_labeled_windows w
  ON ma.icustay_id = w.icustay_id
  AND ma.context_start = w.context_start
  AND ma.context_end = w.context_end;