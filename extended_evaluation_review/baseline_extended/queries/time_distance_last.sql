SELECT
    PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY gap_minutes) AS IQ1,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY gap_minutes) AS median_gap,
    PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY gap_minutes) AS IQ3,
    PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY gap_minutes) AS p90_gap,
    MAX(gap_minutes) AS max_gap
FROM (
    SELECT
        EXTRACT(EPOCH FROM (
            mw.context_end - (
                mw.context_start + (((last_map_elem.elem ->> 'pos')::float)::int * INTERVAL '1 second')
            )
        )) / 60.0 AS gap_minutes
    FROM ce_approach.mix_windows mw
    LEFT JOIN LATERAL (
        SELECT elem
        FROM unnest(mw.map_values) AS elem
        ORDER BY ((elem ->> 'pos')::float)::int DESC
        LIMIT 1
    ) last_map_elem ON TRUE
) sub;


SELECT
    AVG(EXTRACT(EPOCH FROM (
        mw.context_end - (
            mw.context_start + (((last_map_elem.elem ->> 'pos')::float)::int * INTERVAL '1 second')
        )
    )) / 60.0) AS avg_gap_minutes
FROM ce_approach.mix_windows mw
LEFT JOIN LATERAL (
    SELECT elem
    FROM unnest(mw.map_values) AS elem
    ORDER BY ((elem ->> 'pos')::float) DESC
    LIMIT 1
) last_map_elem ON TRUE;