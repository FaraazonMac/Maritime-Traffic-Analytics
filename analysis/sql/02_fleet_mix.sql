-- 02 Fleet mix by vessel type, with each type's share of the fleet (window function) and rank.
WITH by_type AS (
  SELECT vessel_type,
         COUNT(*) AS ships,
         SUM(CASE WHEN status_group = 'moving'    THEN 1 ELSE 0 END) AS moving,
         SUM(CASE WHEN status_group = 'at_anchor' THEN 1 ELSE 0 END) AS at_anchor,
         SUM(CASE WHEN status_group = 'at_berth'  THEN 1 ELSE 0 END) AS at_berth,
         SUM(CASE WHEN status_group = 'idle'      THEN 1 ELSE 0 END) AS idle,
         SUM(is_dark_flagged) AS dark
  FROM ships
  GROUP BY vessel_type
)
SELECT vessel_type,
       ships,
       ROUND(100.0 * ships / SUM(ships) OVER (), 1)  AS share_pct,
       ROUND(100.0 * moving / ships, 1)              AS pct_under_way,
       ROUND(100.0 * idle / ships, 1)                AS pct_idle,
       ROUND(100.0 * at_anchor / ships, 1)           AS pct_at_anchor,
       ROUND(100.0 * dark / ships, 2)                AS pct_dark,
       RANK() OVER (ORDER BY ships DESC)             AS size_rank
FROM by_type
ORDER BY ships DESC;
