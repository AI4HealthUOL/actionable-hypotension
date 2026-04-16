-- Active: 1768480900465@@localhost@5432@mimic
-- Active: 1770284354672@@127.0.0.1@5433@eicu
-- ============================================================================
-- eICU Distribution Analysis
-- ============================================================================

-- 1. Summary Statistics
SELECT 
    'MIMICIII-MV' AS dataset,
    COUNT(*) AS total_samples,
    AVG(mean) AS avg_mean_map,
    STDDEV(mean) AS std_mean_map,
    AVG(std) AS avg_std_map,
    AVG(rate_change) AS avg_rate_change,
    SUM(CASE WHEN positive_event THEN 1 ELSE 0 END) AS n_positive,
    SUM(CASE WHEN positive_event THEN 1 ELSE 0 END) * 100.0 / COUNT(*) AS positive_rate
FROM ce_approach.merged_mix_features;

-- 2. Mean MAP Distribution
SELECT 
    width_bucket(mean, 0, 200, 40) AS bucket,
    COUNT(*) AS count,
    COUNT(*) * 100.0 / SUM(COUNT(*)) OVER () AS percentage
FROM ce_approach.merged_mix_features
GROUP BY bucket
ORDER BY bucket;

-- 3. Age Distribution
SELECT 
    age_bin,
    COUNT(*) AS count,
    COUNT(*) * 100.0 / SUM(COUNT(*)) OVER () AS percentage
FROM ce_approach.merged_mix_features
GROUP BY age_bin
ORDER BY age_bin;

-- 4. Gender Distribution
SELECT 
    gender_bin,
    COUNT(*) AS count,
    COUNT(*) * 100.0 / SUM(COUNT(*)) OVER () AS percentage
FROM ce_approach.merged_mix_features
GROUP BY gender_bin;

-- 5. Comorbidities (Top 3)
SELECT 
    SUM(CASE WHEN hypertension THEN 1 ELSE 0 END) * 100.0 / COUNT(*) AS hypertension_pct,
    SUM(CASE WHEN diabetes THEN 1 ELSE 0 END) * 100.0 / COUNT(*) AS diabetes_pct,
    SUM(CASE WHEN heart_disease THEN 1 ELSE 0 END) * 100.0 / COUNT(*) AS heart_disease_pct
FROM ce_approach.merged_mix_features;

-- 6. Label Distribution (CRITICAL!)
SELECT 
    positive_event,
    COUNT(*) AS count,
    COUNT(*) * 100.0 / SUM(COUNT(*)) OVER () AS percentage
FROM ce_approach.merged_mix_features
GROUP BY positive_event;

SELECT 
    value_count,
    COUNT(*) AS count,
    COUNT(*) * 100.0 / SUM(COUNT(*)) OVER () AS percentage
FROM ce_approach.all_mv_labeled_windows_with_map_values
GROUP BY value_count LIMIT 100