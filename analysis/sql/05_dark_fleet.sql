-- 05 Silent-ship flags: are silent ships concentrated near the edge of the tracked area? (ships heard within the last hour, so the two areas are compared fairly)
-- Uses ships_all: dark-flagged ships are, by definition, ones that have been silent for a while.
-- If yes, many flags are probably ships that sailed out of coverage rather than switched transponders off.
SELECT CASE WHEN is_edge = 1 THEN 'near edge of tracked area' ELSE 'interior' END AS location,
       COUNT(*)                                   AS ships,
       SUM(is_dark_flagged)                       AS dark_flagged,
       ROUND(100.0 * SUM(is_dark_flagged) / COUNT(*), 2) AS dark_pct
FROM ships_all
WHERE COALESCE(minutes_since_update, 0) <= 60   -- same equal-age window as the Python analysis (DARK_WINDOW_MINUTES)
GROUP BY location
ORDER BY location;
