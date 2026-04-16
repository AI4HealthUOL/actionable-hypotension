-- Map types and counts
SELECT
  (mv.elem->>'type')::int AS map_type,
  MIN((mv.elem->>'value')::numeric) AS min_value,
  MAX((mv.elem->>'value')::numeric) AS max_value,
  COUNT(*) AS n_values
FROM mix_windows mw
CROSS JOIN LATERAL unnest(mw.map_values) AS mv(elem)
WHERE mv.elem IS NOT NULL
GROUP BY (mv.elem->>'type')::int
ORDER BY map_type LIMIT 100