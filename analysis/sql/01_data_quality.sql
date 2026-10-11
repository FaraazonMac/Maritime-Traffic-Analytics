-- 01 Data quality: how complete is the AIS data we receive?
-- Each metric is the share of ships (%) that have a usable value.
SELECT
  COUNT(*)                                                                                         AS ships,
  ROUND(100.0 * SUM(CASE WHEN vessel_type <> 'unknown' THEN 1 ELSE 0 END) / COUNT(*), 1)           AS pct_type_known,
  ROUND(100.0 * SUM(CASE WHEN imo IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 1)                    AS pct_with_imo,
  ROUND(100.0 * SUM(imo_valid) / COUNT(*), 1)                                                      AS pct_valid_imo_checksum,
  ROUND(100.0 * SUM(CASE WHEN dest_quality NOT IN ('missing', 'junk') THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_usable_destination,
  ROUND(100.0 * SUM(CASE WHEN destination_port IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 1)       AS pct_destination_matched_by_app,
  ROUND(100.0 * SUM(CASE WHEN dest_hub IS NOT NULL OR destination_port IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_destination_resolved_after_cleaning,
  ROUND(100.0 * SUM(CASE WHEN length_m IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 1)               AS pct_with_length
FROM ships;
