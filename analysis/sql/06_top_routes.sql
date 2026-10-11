-- 06 Most common voyages: departure port (detected live) to destination (cleaned).
SELECT MIN(departure_port) AS departure_port,
       MIN(COALESCE(dest_hub, destination_port, dest_clean)) AS destination,
       COUNT(*)                AS ships,
       ROUND(AVG(speed), 1)    AS avg_speed_kn
FROM ships
WHERE departure_port IS NOT NULL
  AND dest_quality NOT IN ('missing', 'junk')
GROUP BY UPPER(departure_port), UPPER(COALESCE(dest_hub, destination_port, dest_clean))   -- 'AMSTERDAM' and 'Amsterdam' are the same port
ORDER BY ships DESC, UPPER(departure_port)
LIMIT 15;
