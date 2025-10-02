-- Create a new table for non-invasive context windows
-- Keeps only the MAP values of type 220181 (non-invasive)
-- Adds a filtered MAP array and a corresponding count
CREATE TABLE ce_approach.noninvasive_windows AS
SELECT
  *,
  (
    SELECT ARRAY_AGG(e)
    FROM UNNEST(map_values) AS e
    WHERE (e->>'type')::text = '220181'
  ) AS map_values_filtered,
  (
    SELECT COUNT(*)
    FROM UNNEST(map_values) AS e
    WHERE (e->>'type')::text = '220181'
  ) AS value_count_filtered
FROM ce_approach.all_mv_labeled_windows_with_map_values;

-- Remove all context windows that have fewer than 2 non-invasive values
DELETE FROM ce_approach.noninvasive_windows
WHERE value_count_filtered < 2;

-- Drop unnecessary columns from original or split dataset that are no longer needed
ALTER TABLE ce_approach.noninvasive_windows
DROP COLUMN value_count,
DROP COLUMN map_values;

-- Rename the filtered columns to standard names (as in the original)
ALTER TABLE ce_approach.noninvasive_windows
RENAME COLUMN map_values_filtered TO map_values;

ALTER TABLE ce_approach.noninvasive_windows
RENAME COLUMN value_count_filtered TO value_count;





-- Create a new table for invasive context windows
-- Merges values at the same position from invasive types (220052, 225312)
-- If multiple values exist at a position, the average is taken
-- The type column reflects the contributing types (e.g., '220052x225312')
-- The count reflects number of unique merged positions (independent of type)
CREATE TABLE ce_approach.invasive_windows AS
SELECT
  *,
  (
    -- Merge values on the same position and combine types with 'x'
    SELECT ARRAY_AGG(
      jsonb_build_object(
        'pos', pos,
        'value', val,
        'type', type_label
      )
      ORDER BY pos
    )
    FROM (
      SELECT
        (e->>'pos')::float AS pos,
        AVG((e->>'value')::float) AS val,
        string_agg(DISTINCT (e->>'type'), 'x' ORDER BY (e->>'type')) AS type_label
      FROM UNNEST(map_values) AS e
      WHERE (e->>'type') IN ('220052', '225312')
      GROUP BY (e->>'pos')
    ) merged
  ) AS map_values_filtered,
  (
    -- Count number of unique positions after merging
    SELECT COUNT(*)
    FROM (
      SELECT DISTINCT (e->>'pos')
      FROM UNNEST(map_values) AS e
      WHERE (e->>'type') IN ('220052', '225312')
    ) AS merged_positions
  ) AS value_count_filtered
FROM ce_approach.all_mv_labeled_windows_with_map_values;


-- Remove all context windows that have fewer than 2 invasive values
DELETE FROM ce_approach.invasive_windows
WHERE value_count_filtered < 2;

-- Drop original and intermediate columns that are no longer required
ALTER TABLE ce_approach.invasive_windows
DROP COLUMN value_count,
DROP COLUMN map_values;

-- Rename the filtered columns to standard names (as in the original)
ALTER TABLE ce_approach.invasive_windows
RENAME COLUMN map_values_filtered TO map_values;

ALTER TABLE ce_approach.invasive_windows
RENAME COLUMN value_count_filtered TO value_count;


-- Create a new table for mixed context windows
-- Merges values at the same position from all MAP types (220052, 225312, 220181)
-- If multiple values exist on the same position, the average is taken
-- The type column reflects the contributing types (e.g., '220052x220181')
-- The count reflects number of unique merged positions, regardless of type
CREATE TABLE ce_approach.mix_windows_old AS
SELECT
  *,
  (
    SELECT ARRAY_AGG(
      jsonb_build_object(
        'pos', pos,
        'value', val,
        'type', type_label
      )
      ORDER BY pos
    )
    FROM (
      SELECT
        (e->>'pos')::float AS pos,
        AVG((e->>'value')::float) AS val,
        string_agg(DISTINCT (e->>'type'), 'x' ORDER BY (e->>'type')) AS type_label
      FROM UNNEST(map_values) AS e
      WHERE (e->>'type') IN ('220052', '225312', '220181')
      GROUP BY (e->>'pos')
    ) merged
  ) AS map_values_filtered,
  (
    -- Count number of unique positions regardless of type
    SELECT COUNT(*)
    FROM (
      SELECT DISTINCT (e->>'pos')
      FROM UNNEST(map_values) AS e
    ) AS merged_positions
  ) AS value_count_filtered
FROM ce_approach.all_mv_labeled_windows_with_map_values;





-- Create a new table for mixed context windows
-- Merges values at the same position from all MAP item IDs (220052, 225312, 220181)
-- Invasive measurements (220052, 225312) are prioritized; non‑invasive (220181) are only used when no invasive measurement exists at that position.
-- If two invasive measurements exist at the same position, their average is taken.
-- An additional column `non_invasive_discarded` indicates if any non‑invasive measurement was discarded because an invasive one was present.
CREATE TABLE ce_approach.mix_windows AS
SELECT
  *,
  -- 1) Filtered JSONB array with prioritized/aggregated values per position
  (
    SELECT ARRAY_AGG(
      jsonb_build_object(
        'pos',  pos,
        'value', val,
        'type',  type_label
      )
      ORDER BY pos
    )
    FROM (
      SELECT
        (e->>'pos')::float                                AS pos,
        AVG((e->>'value')::float)                         AS val,
        string_agg(DISTINCT e->>'type', 'x' ORDER BY e->>'type') AS type_label
      FROM UNNEST(map_values) AS e
      WHERE e->>'type' IN ('220052','225312','220181')
      GROUP BY (e->>'pos')
    ) AS merged
  ) AS map_values_filtered,
  -- 2) Number of unique positions (regardless of type)
  (
    SELECT COUNT(*)
    FROM (
      SELECT DISTINCT (e->>'pos')
      FROM UNNEST(map_values) AS e
      WHERE e->>'type' IN ('220052','225312','220181')
    ) AS merged_positions
  ) AS value_count_filtered,
  -- 3) Flag indicating whether any non‑invasive (220181) value was discarded due to presence of invasive measurements
  (
    SELECT EXISTS (
      SELECT 1
      FROM UNNEST(map_values) AS e
      WHERE e->>'type' IN ('220052','225312','220181')
      GROUP BY (e->>'pos')
      HAVING
        count(*) FILTER (WHERE e->>'type' IN ('220052','225312')) > 0
        AND
        count(*) FILTER (WHERE e->>'type' = '220181')       > 0
    )
  ) AS non_invasive_discarded
FROM ce_approach.all_mv_labeled_windows_with_map_values;











-- Rebuild mix_windows with a single non‑invasive value per pos
CREATE TABLE ce_approach.mix_windows AS
WITH exploded AS (
  SELECT
    aw.*,
    (e->>'pos')::float        AS pos,
    (e->>'value')::float      AS value,
    e->>'type'                AS type
  FROM ce_approach.all_mv_labeled_windows_with_map_values aw,
       UNNEST(map_values) AS e
  WHERE e->>'type' IN ('220052','225312','220181')
),
per_pos AS (
  SELECT
    icustay_id,
    context_start,
    context_end,
    pos,
    -- invasive summary
    COUNT(*) FILTER (WHERE type IN ('220052','225312'))   AS inv_count,
    AVG(value) FILTER (WHERE type IN ('220052','225312')) AS inv_avg,
    string_agg(DISTINCT type, 'x' ORDER BY type) FILTER (WHERE type IN ('220052','225312')) AS inv_label,
    -- non‑invasive: nur ein Wert, kein AVG nötig
    MAX(value) FILTER (WHERE type = '220181')             AS noninv_val
  FROM exploded
  GROUP BY icustay_id, context_start, context_end, pos
),
map_agg AS (
  SELECT
    icustay_id,
    context_start,
    context_end,
    ARRAY_AGG(
      jsonb_build_object(
        'pos',  pos,
        'value',
          CASE WHEN inv_count>0 THEN inv_avg ELSE noninv_val END,
        'type',
          CASE WHEN inv_count>0 THEN inv_label ELSE '220181' END
      )
      ORDER BY pos
    ) AS map_values_filtered,
    COUNT(*) AS value_count_filtered,
    BOOL_OR(inv_count>0 AND noninv_val IS NOT NULL) AS non_invasive_discarded
  FROM per_pos
  GROUP BY icustay_id, context_start, context_end
)
SELECT
  aw.*,
  m.map_values_filtered,
  m.value_count_filtered,
  m.non_invasive_discarded
FROM ce_approach.all_mv_labeled_windows_with_map_values aw
JOIN map_agg m
  ON aw.icustay_id    = m.icustay_id
 AND aw.context_start = m.context_start
 AND aw.context_end   = m.context_end
WHERE m.value_count_filtered >= 2;


-- Remove context windows with fewer than 2 usable values
DELETE FROM ce_approach.mix_windows
WHERE value_count_filtered < 2;

-- Remove obsolete columns
ALTER TABLE ce_approach.mix_windows
DROP COLUMN value_count,
DROP COLUMN map_values;

-- Rename the filtered columns to standard names (as in the original)
ALTER TABLE ce_approach.mix_windows
RENAME COLUMN map_values_filtered TO map_values;

ALTER TABLE ce_approach.mix_windows
RENAME COLUMN value_count_filtered TO value_count;
