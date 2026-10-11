-- 03 Congestion by port hub: ships waiting at anchor within each hub's radius.
-- RANK() orders hubs by waiting ships; NTILE(3) splits them into green / yellow / red thirds.
-- (Ties can fall into different thirds in NTILE; the Python/Excel/dashboard levels treat ties consistently.)
WITH h AS (
  SELECT hub, zone,
         COUNT(*) AS ships_in_radius,
         SUM(CASE WHEN status_group = 'at_anchor' THEN 1 ELSE 0 END) AS at_anchor,
         SUM(CASE WHEN status_group = 'at_berth'  THEN 1 ELSE 0 END) AS at_berth,
         SUM(CASE WHEN status_group = 'idle'      THEN 1 ELSE 0 END) AS idle,
         SUM(CASE WHEN status_group = 'moving'    THEN 1 ELSE 0 END) AS moving,
         ROUND(AVG(CASE WHEN status_group = 'moving' THEN speed END), 1) AS avg_speed_moving_kn
  FROM ships
  WHERE hub IS NOT NULL
  GROUP BY hub, zone
)
SELECT hub, zone, ships_in_radius, at_anchor, idle, at_anchor + idle AS waiting_broad, at_berth, moving, avg_speed_moving_kn,
       ROUND(100.0 * at_anchor / ships_in_radius, 1) AS pct_at_anchor,
       RANK() OVER (ORDER BY at_anchor DESC)         AS waiting_rank,
       CASE NTILE(3) OVER (ORDER BY at_anchor)
            WHEN 1 THEN 'green' WHEN 2 THEN 'yellow' ELSE 'red' END AS level
FROM h
ORDER BY at_anchor DESC, ships_in_radius DESC;
