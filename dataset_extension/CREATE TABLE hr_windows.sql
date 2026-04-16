-- Active: 1761032695395@@localhost@5432
-- Create a new table for 220045 context windows
-- heart rate: 220045
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



