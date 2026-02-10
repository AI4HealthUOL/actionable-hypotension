-- Drop the existing table if it exists
DROP TABLE IF EXISTS ce_approach.all_mv_labeled_windows_with_map_values;

-- CREATE indices
-- Für eicu_crd.vitalaperiodic
CREATE INDEX idx_vitalaperiodic_patientunitstayid ON eicu_crd.vitalaperiodic(patientunitstayid);
CREATE INDEX idx_vitalaperiodic_noninvasivemean ON eicu_crd.vitalaperiodic(noninvasivemean) WHERE noninvasivemean IS NOT NULL;

-- Für eicu_crd.vitalperiodic
CREATE INDEX idx_vitalperiodic_patientunitstayid ON eicu_crd.vitalperiodic(patientunitstayid);
CREATE INDEX idx_vitalperiodic_systemicmean ON eicu_crd.vitalperiodic(systemicmean) WHERE systemicmean IS NOT NULL;


-- Create a table of labeled context windows with associated MAP values
-- Only includes values in range 30–200 and of types 220052, 225312, 220181
-- MAP values are stored as JSON objects with relative time ("pos"), value, and type
-- Also counts the number of values per window

--CREATE TABLE public.all_labeled_windows_with_map_values AS
SELECT * FROM temp_filtered_maps Limit 100; 

CREATE TABLE filtered_maps AS
  -- Nicht-invasive Messungen
  SELECT
    patientunitstayid,
    observationoffset AS offset,
    noninvasivemean AS valuenum,
    'noninvasive' AS source
  FROM eicu_crd.vitalaperiodic
  WHERE patientunitstayid IN (SELECT DISTINCT patientunitstayid FROM public.all_labeled_windows)
  AND noninvasivemean IS NOT NULL
    AND noninvasivemean BETWEEN 30 AND 200
  UNION ALL
  -- Invasive Messungen
  SELECT
    patientunitstayid,
    observationoffset AS offset,
    systemicmean AS valuenum,
    'invasive' AS source
  FROM eicu_crd.vitalperiodic
  WHERE patientunitstayid IN (SELECT DISTINCT patientunitstayid FROM public.all_labeled_windows)
    AND systemicmean IS NOT NULL
    AND systemicmean BETWEEN 30 AND 200
    
--CREATE TABLE public.all_labeled_windows_with_map_values AS
WITH map_agg AS (
  SELECT
    w.patienthealthsystemstayid,
    w.patientunitstayid,
    w.context_start_offset_min,
    w.context_end_offset_min,
    w.target_start_offset_min,
    w.target_end_offset_min,
    w.positive_sample,
    w.positive_event,
    COUNT(ma.valuenum) AS value_count,
    STRING_AGG(
      CONCAT(
        'pos:', ma.offset - w.context_start_offset_min, '|',
        'value:', ma.valuenum, '|',
        'type:', ma.source
      ),
      ';'
      ORDER BY ma.offset
    ) AS ma_values_csv
FROM public.all_labeled_windows w
LEFT JOIN public.filtered_maps ma
  ON ma.patientunitstayid = w.patientunitstayid
  AND ma.offset BETWEEN w.context_start_offset_min AND w.context_end_offset_min
GROUP BY
  w.patienthealthsystemstayid, w.patientunitstayid, w.context_start_offset_min, w.context_end_offset_min,
  w.target_start_offset_min, w.target_end_offset_min,
  w.positive_sample, w.positive_event
)
SELECT * FROM map_agg ma LIMIT 100;

Drop table if exists all_labeled_windows_with_map_values

-- Erstelle eine temporäre Tabelle für die Ergebnisse
-- Temporäre Tabelle mit expliziten Datentypen erstellen
-- Dauerhafte Tabelle mit der korrekten Struktur erstellen
CREATE TABLE public.all_labeled_windows_with_map_values (
  patienthealthsystemstayid INT,
  patientunitstayid INT,
  context_start_offset_min INT,
  context_end_offset_min INT,
  target_start_offset_min INT,
  target_end_offset_min INT,
  positive_sample BOOLEAN,
  positive_event BOOLEAN,
  value_count INT,
  -- CSV-String für die MAP-Werte (Format: "pos:value:type;pos:value:type;...")
  ma_values_csv TEXT
);
-- Verarbeite die Daten in Batches (z. B. pro 1000 Patienten)
DO $$
DECLARE
  batch_size INT := 10000;
  offset_val INT := 0;
  total_windows INT;
BEGIN
  -- Ermittle die Gesamtzahl der Patienten
  SELECT COUNT(*) INTO total_windows
  FROM public.all_labeled_windows;

  -- Verarbeite die Daten in Batches
  WHILE offset_val < total_windows LOOP
    INSERT INTO public.all_labeled_windows_with_map_values
    WITH batch_windows AS (
      SELECT * FROM public.all_labeled_windows
      ORDER BY patientunitstayid, context_start_offset_min
      LIMIT batch_size OFFSET offset_val
    ),
    map_agg AS (
      SELECT
        w.patienthealthsystemstayid,
        w.patientunitstayid,
        w.context_start_offset_min,
        w.context_end_offset_min,
        w.target_start_offset_min,
        w.target_end_offset_min,
        w.positive_sample,
        w.positive_event,
        COUNT(ma.valuenum) AS value_count,
        STRING_AGG(
        CONCAT(
          'pos:', ma.offset - w.context_start_offset_min, '|',
          'value:', ma.valuenum, '|',
          'type:', ma.source
        ),
        ';'
      ORDER BY ma.offset
    ) AS ma_values_csv
      FROM batch_windows w
      LEFT JOIN public.filtered_maps ma
        ON ma.patientunitstayid = w.patientunitstayid
        AND ma.offset BETWEEN w.context_start_offset_min AND w.context_end_offset_min
      GROUP BY
        w.patienthealthsystemstayid, w.patientunitstayid, w.context_start_offset_min, w.context_end_offset_min,
        w.target_start_offset_min, w.target_end_offset_min,
        w.positive_sample, w.positive_event
    )
    SELECT * FROM map_agg;

    -- Erhöhe den Offset für den nächsten Batch
    offset_val := offset_val + batch_size;
    RAISE NOTICE 'Verarbeite Batch: % bis %', offset_val - batch_size + 1, offset_val;
  END LOOP;
END $$;
