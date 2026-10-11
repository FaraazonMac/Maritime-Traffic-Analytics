-- 09 Ships waiting at anchor near a hub, by size class (feeds the fuel and cost estimates).
SELECT size_class,
       COUNT(*) AS ships_waiting,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS share_pct
FROM ships
WHERE status_group = 'at_anchor' AND hub IS NOT NULL
GROUP BY size_class
ORDER BY ships_waiting DESC;
