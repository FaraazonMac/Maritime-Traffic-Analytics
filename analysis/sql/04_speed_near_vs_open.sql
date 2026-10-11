-- 04 Do ships move more slowly near port hubs than in open water? (moving ships only)
-- Groups with fewer than 5 ships are dropped so a handful of vessels cannot drive an average.
SELECT vessel_type,
       CASE WHEN hub IS NULL THEN 'open water' ELSE 'near a hub' END AS location,
       COUNT(*)                 AS moving_ships,
       ROUND(AVG(speed), 1)     AS avg_speed_kn
FROM ships
WHERE status_group = 'moving' AND speed IS NOT NULL
GROUP BY vessel_type, location
HAVING COUNT(*) >= 5
ORDER BY vessel_type, location;
