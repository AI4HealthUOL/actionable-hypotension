SELECT 
    COUNT(*) FILTER (WHERE last > 65) AS above_65,
    COUNT(*) AS total,
    100.0 * COUNT(*) FILTER (WHERE last > 65) / COUNT(*) AS pct_above_65
FROM ce_approach.merged_mix_features
WHERE positive_event = true;