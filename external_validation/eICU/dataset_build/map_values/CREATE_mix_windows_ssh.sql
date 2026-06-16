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

"""
# STEP I 
-- Add a new serial column 'id' to the table
ALTER TABLE public.all_labeled_windows_with_map_values ADD COLUMN if not exists id BIGSERIAL PRIMARY KEY;

CREATE TABLE if not exists public.split_map_values (
    id SERIAL PRIMARY KEY,
    original_row_id BIGINT REFERENCES public.all_labeled_windows_with_map_values(id),
    patientunitstayid BIGINT,
    context_start_offset_min INT,
    context_end_offset_min INT,
    pos FLOAT,
    value FLOAT,
    map_type TEXT
);

CREATE OR REPLACE FUNCTION populate_split_map_values()
RETURNS VOID AS $$
DECLARE
    row_record RECORD;
    measurement TEXT;
BEGIN
    FOR row_record IN SELECT id, patientunitstayid, context_start_offset_min, context_end_offset_min, ma_values_csv FROM public.all_labeled_windows_with_map_values
    LOOP
        FOR measurement IN SELECT regexp_split_to_table(row_record.ma_values_csv, ';') AS measurement
        LOOP
            INSERT INTO public.split_map_values (
                original_row_id,
                patientunitstayid,
                context_start_offset_min,
                context_end_offset_min,
                pos,
                value,
                map_type
            )
            VALUES (
                row_record.id,
                row_record.patientunitstayid,
                row_record.context_start_offset_min,
                row_record.context_end_offset_min,
                SPLIT_PART(SPLIT_PART(measurement, '|', 1), ':', 2)::float,
                SPLIT_PART(SPLIT_PART(measurement, '|', 2), ':', 2)::float,
                SPLIT_PART(SPLIT_PART(measurement, '|', 3), ':', 2)
            )
            ON CONFLICT DO NOTHING;
        END LOOP;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- Execute the function
SELECT populate_split_map_values();
"""