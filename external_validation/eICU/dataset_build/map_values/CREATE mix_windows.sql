

-- Create a new table for mixed context windows
-- Merges values at the same position from all MAP item IDs (220052, 225312, 220181)
-- Invasive measurements (220052, 225312) are prioritized; non‑invasive (220181) are only used when no invasive measurement exists at that position.
-- If two invasive measurements exist at the same position, their average is taken.
-- An additional column `non_invasive_discarded` indicates if any non‑invasive measurement was discarded because an invasive one was present.


-- Created a separate table with the map values per context window 'split_map_values'
-- create indices on this table 
CREATE INDEX idx_split_map_values_1 ON public.split_map_values(patientunitstayid, context_start_offset_min, context_end_offset_min);
CREATE INDEX idx_split_map_values_2 ON public.split_map_values(map_type);
CREATE INDEX idx_split_map_values_3 ON public.split_map_values(pos);




-- Rebuild mix_windows with a single non‑invasive value per pos
CREATE TABLE public.mix_windows AS
WITH per_pos AS (
  SELECT
    patientunitstayid AS icustay_id,
    context_start_offset_min AS context_start,
    context_end_offset_min AS context_end,
    pos,
    -- invasive summary
    COUNT(*) FILTER (WHERE map_type = 'invasive')   AS inv_count,
    AVG(value) FILTER (WHERE map_type = 'invasive') AS inv_avg,
    -- non-invasive summary
    MAX(value) FILTER (WHERE map_type = 'noninvasive') AS noninv_val
  FROM public.split_map_values
  WHERE map_type IN ('invasive', 'noninvasive')
  GROUP BY patientunitstayid, context_start_offset_min, context_end_offset_min, pos
),
map_agg AS (
  SELECT
    icustay_id,
    context_start,
    context_end,
    STRING_AGG(
      CONCAT(
        'pos:', pos, '|',
        'value:', CASE WHEN inv_count > 0 THEN inv_avg ELSE noninv_val END, '|',
        'type:', CASE WHEN inv_count > 0 THEN 'invasive' ELSE 'noninvasive' END
      ),
      ';'
      ORDER BY pos
    ) AS map_values_filtered,
    COUNT(*) AS value_count_filtered,
    BOOL_OR(inv_count > 0 AND noninv_val IS NOT NULL) AS non_invasive_discarded
  FROM per_pos
  GROUP BY icustay_id, context_start, context_end
)
SELECT
  aw.*,
  m.map_values_filtered,
  m.value_count_filtered,
  m.non_invasive_discarded
FROM public.all_labeled_windows_with_map_values aw
JOIN map_agg m
  ON aw.patientunitstayid = m.icustay_id
 AND aw.context_start_offset_min = m.context_start
 AND aw.context_end_offset_min = m.context_end;

# remove 8 rows where we ended up with value count lower than 2 
DELETE FROM public.mix_windows
WHERE value_count_filtered < 2;

-- Remove obsolete columns
ALTER TABLE public.mix_windows
DROP COLUMN value_count,
DROP COLUMN ma_values_csv;

-- Rename the filtered columns to standard names (as in the original)
ALTER TABLE public.mix_windows
RENAME COLUMN map_values_filtered TO map_values;

ALTER TABLE public.mix_windows
RENAME COLUMN value_count_filtered TO value_count;
