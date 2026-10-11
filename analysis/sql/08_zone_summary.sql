-- 08 Compare sub-zones of the study region (Benelux coast, Dover Strait, German Bight, ...).
SELECT zone,
       COUNT(DISTINCT hub)  AS hubs,
       COUNT(*)             AS ships_in_hub_radius,
       SUM(CASE WHEN status_group = 'at_anchor' THEN 1 ELSE 0 END) AS at_anchor,
       ROUND(100.0 * SUM(CASE WHEN status_group = 'at_anchor' THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_at_anchor,
       ROUND(AVG(CASE WHEN status_group = 'moving' THEN speed END), 1) AS avg_speed_moving_kn
FROM ships
WHERE hub IS NOT NULL
GROUP BY zone
ORDER BY at_anchor DESC;
