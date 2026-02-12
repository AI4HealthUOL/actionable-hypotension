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

