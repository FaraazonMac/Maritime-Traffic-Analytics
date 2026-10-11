-- 07 Flag states ranked by ships, with a running (cumulative) share, to show concentration.
WITH f AS (
  SELECT COALESCE(flag, 'Unknown') AS flag, COUNT(*) AS ships FROM ships GROUP BY COALESCE(flag, 'Unknown')
)
SELECT flag, ships,
       ROUND(100.0 * ships / SUM(ships) OVER (), 1) AS share_pct,
       ROUND(100.0 * SUM(ships) OVER (ORDER BY ships DESC, flag ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
             / SUM(ships) OVER (), 1) AS cumulative_share_pct,
       DENSE_RANK() OVER (ORDER BY ships DESC) AS flag_rank
FROM f
ORDER BY ships DESC, flag
LIMIT 15;
