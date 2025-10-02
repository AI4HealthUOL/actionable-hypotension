--1) How many subjects are in each split for each dataset? 
WITH counts AS (
  SELECT
    'mix' AS dataset,
    split,
    COUNT(DISTINCT subject_id) AS n_subjects
  FROM ce_approach.mix_windows mw
  JOIN ce_approach.split_all_subjects ss USING (subject_id)
  GROUP BY split

  UNION ALL

  SELECT
    'noninvasive' AS dataset,
    split,
    COUNT(DISTINCT subject_id) AS n_subjects
  FROM ce_approach.noninvasive_windows nw
  JOIN ce_approach.split_all_subjects ss USING (subject_id)
  GROUP BY split

  UNION ALL

  SELECT
    'invasive' AS dataset,
    split,
    COUNT(DISTINCT subject_id) AS n_subjects
  FROM ce_approach.invasive_windows iw
  JOIN ce_approach.split_all_subjects ss USING (subject_id)
  GROUP BY split
),
total_counts AS (
  SELECT
    dataset,
    SUM(n_subjects) AS total_subjects
  FROM counts
  GROUP BY dataset
)
SELECT
  c.dataset,
  c.split,
  c.n_subjects,
  ROUND(100.0 * c.n_subjects / t.total_subjects, 2) AS percentage
FROM counts c
JOIN total_counts t ON c.dataset = t.dataset
ORDER BY c.dataset, c.split;