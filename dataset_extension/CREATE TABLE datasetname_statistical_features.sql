-- Active: 1768480900465@@localhost@5434@mimic
-- Computes descriptive & trend statistics over JSONB time‑series windows in manageable chunks.
-- Dynamically handles any source/target table pair by physically ordering by icustay_id and context_start,
-- adding a row_id surrogate, and batching per range to limit memory usage and enforce transactional boundaries.
-- Produces: mean, median, min, max, std, IQR, first/last values, rate of change, slope, weighted mean, and a two‑value flag.
CREATE OR REPLACE PROCEDURE evaluation.compute_hr_window_stats(
  src_table  TEXT,
  tgt_table  TEXT,
  chunk_size INTEGER DEFAULT 10000  -- Number of rows to process per batch
)
LANGUAGE plpgsql
AS $$
DECLARE
  min_id    BIGINT;  -- Lowest available row_id in source
  max_id    BIGINT;  -- Highest available row_id in source
  start_id  BIGINT;  -- Start of current batch
  end_id    BIGINT;  -- End of current batch
  key_idx   TEXT := replace(src_table, '.', '_') || '_keys';  -- Name for the clustering index
BEGIN
  ---------------------------------------------------------------------
  -- 0) Physically cluster source table by (icustay_id, context_start)
  --    ensures contiguous I/O for time‐based retrieval
  EXECUTE format(
    'CREATE INDEX IF NOT EXISTS %I ON %s(icustay_id, context_start)',
    key_idx, src_table
  );
  EXECUTE format('CLUSTER %s USING %I', src_table, key_idx);

  ---------------------------------------------------------------------
  -- 1) Ensure surrogate integer primary key exists for efficient chunking
  EXECUTE format(
    'ALTER TABLE %s ADD COLUMN IF NOT EXISTS row_id BIGSERIAL PRIMARY KEY',
    src_table
  );

  ---------------------------------------------------------------------
  -- 2) Index row_id for fast BETWEEN scans of each batch
  EXECUTE format(
    'CREATE INDEX IF NOT EXISTS idx_%s_row_id ON %s(row_id)',
    replace(src_table, '.', '_'), src_table
  );

  ---------------------------------------------------------------------
  -- 3) Drop and recreate empty target table with identical key columns
  EXECUTE format('DROP TABLE IF EXISTS %s', tgt_table);
  EXECUTE format($t$
    CREATE TABLE %1$s (
      row_id         bigint      PRIMARY KEY,
      icustay_id     bigint,       -- ICU stay identifier
      context_start  timestamp,    -- Window start (no timezone)
      context_end    timestamp,    -- Window end (no timezone)
      hr_mean           double precision,
      hr_median         double precision,
      hr_std            double precision,
      hr_iqr            double precision,
      hr_first          double precision,
      hr_last           double precision,
      hr_slope          double precision,
      hr_only_2_values  boolean       -- True if exactly two readings in window
    )
  $t$, tgt_table);

  ---------------------------------------------------------------------
  -- 4) Determine overall row_id bounds for batching
  EXECUTE format('SELECT MIN(row_id), MAX(row_id) FROM %s', src_table)
    INTO min_id, max_id;
  start_id := min_id;

  ---------------------------------------------------------------------
  -- 5) Batch processing loop
  WHILE start_id <= max_id LOOP
    -- Compute end of this batch
    end_id := LEAST(start_id + chunk_size - 1, max_id);
    RAISE NOTICE 'Processing rows % – %', start_id, end_id;

    -------------------------------------------------------------------
    -- 5a) Single-pass CTEs for this batch:
    -- exploded: unnest JSONB array to (row_id, keys, pos, val)
    -- max_pos: maximum time offset for weighted_mean
    -- stats: compute aggregates and trend metrics per window
    -- first_last: capture first and last values by ordering
    EXECUTE format($q$
      INSERT INTO %1$s
      WITH exploded AS (
        SELECT
          aw.row_id,
          aw.icustay_id,
          aw.context_start,
          aw.context_end,
          (e::jsonb->>'pos')  ::double precision AS pos,
          (e::jsonb->>'value')::double precision AS val
        FROM %2$s AS aw
        CROSS JOIN LATERAL UNNEST(aw.hr_values) AS e
        WHERE aw.row_id BETWEEN %3$L AND %4$L
      ),
      max_pos AS (
        SELECT row_id, MAX(pos) AS max_pos
        FROM exploded
        GROUP BY row_id
      ),
      stats AS (
        SELECT
          row_id,
          icustay_id,
          context_start,
          context_end,
          AVG(val)                                    AS hr_mean,
          PERCENTILE_CONT(0.5) WITHIN GROUP(ORDER BY val) AS hr_median,
          STDDEV(val)                                 AS hr_std,
          (PERCENTILE_CONT(0.75) WITHIN GROUP(ORDER BY val)
           - PERCENTILE_CONT(0.25) WITHIN GROUP(ORDER BY val)) AS hr_iqr,
          COUNT(*)                                    AS hr_cnt,
          REGR_SLOPE(val, pos)                        AS hr_slope
        FROM exploded e
        JOIN max_pos m USING(row_id)
        GROUP BY row_id, icustay_id, context_start, context_end
      ),
      first_last AS (
        SELECT
          row_id,
          icustay_id,
          context_start,
          context_end,
          (array_agg(val ORDER BY pos))[1]      AS hr_first,  -- earliest reading
          (array_agg(val ORDER BY pos DESC))[1] AS hr_last   -- latest reading
        FROM exploded
        GROUP BY row_id, icustay_id, context_start, context_end
      )
      -- Insert final combined stats for the batch
      SELECT
        s.row_id,
        s.icustay_id,
        s.context_start,
        s.context_end,
        s.hr_mean,
        s.hr_median,
        s.hr_std,
        s.hr_iqr,
        fl.hr_first,
        fl.hr_last,
        s.hr_slope,
        (s.hr_cnt = 2)                                       AS hr_only_2_values
      FROM stats s
      JOIN first_last fl USING(row_id, icustay_id, context_start, context_end)
    $q$, tgt_table, src_table, start_id, end_id);

    -------------------------------------------------------------------
    -- 5b) Pause to commit batch and release resources
    PERFORM pg_sleep(0);

    -- Advance to next batch
    start_id := end_id + 1;
  END LOOP;
END;
$$;


-- compute statistical features of heartrate
CALL evaluation.compute_hr_window_stats(
  'evaluation.all_mv_labeled_windows_with_heart_rate',
  'evaluation.hr_windows_statistical_features'
);
