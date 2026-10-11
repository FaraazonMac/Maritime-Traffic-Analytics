# Data dictionary: `outputs/data/ships_clean.csv`

One row per **current** ship (heard from in the last 15 minutes), after cleaning. `ships_all.csv` has the same columns for every ship, including ones that have gone silent; it is used only for the dark-fleet analysis. Source: AISStream live AIS, via the Maritime Globe backend.

| Column | Type | Meaning |
|---|---|---|
| mmsi | integer | Maritime Mobile Service Identity, the ship's radio ID (unique key). |
| name | text | Ship name; missing if blank or "Unknown". |
| flag | text | Flag state derived from the first 3 digits of the MMSI (ITU country codes). "Unknown" if not recognised. |
| vessel_type | text | cargo, tanker, passenger, tug, fishing, pleasure, official, other or unknown. Comes from AIS static data, which arrives minutes after the first position. |
| imo | integer | IMO ship number (7 digits). Missing for many small vessels. |
| imo_valid | 0/1 | 1 if the IMO passes the checksum (last digit = weighted sum of the first six). |
| call_sign | text | Radio call sign. |
| lat, lng | decimal degrees | Last reported position. |
| status | text | Navigation status as entered by the crew: moving, anchored-sea, anchored-port. |
| status_group | text | moving (under way at 0.5 kn or more), idle (status says under way but speed is under 0.5 kn), at_anchor (anchored-sea), at_berth (anchored-port, i.e. moored), other. Status is typed by hand and often not updated, so speed decides between moving and idle. |
| speed | knots | Speed over ground. The AIS "not available" code (102.3), negatives and values above 40 kn are set to missing. |
| heading | degrees | Course; 360 and above set to missing. |
| minutes_since_update | minutes | Age of the last AIS message when the snapshot was taken. |
| is_stale | 0/1 | 1 if the ship has not been heard from for more than 15 minutes. Stale ships are excluded from traffic metrics. |
| is_dark_flagged | 0/1 | 1 if the ship has been silent for 20+ minutes (the dark-fleet rule in the backend). |
| destination | text | Raw destination typed by the captain. |
| dest_clean | text | Upper-cased, trimmed; for "A > B" only B. |
| dest_quality | text | missing, junk (placeholder like "FOR ORDERS"), locode (UN/LOCODE of a known hub), hub_name, locode_other (a code for another port), other_text. |
| dest_hub | text | The known hub the destination maps to, if any. |
| dest_resolved | text | dest_hub, else the port the backend matched, else empty. |
| destination_port | text | Port the backend matched against the World Port Index. |
| eta | text | Estimated arrival (month-day hour:minute UTC) as broadcast. |
| departure_port | text | Port the ship left, detected live when its status changed from anchored-in-port to moving. Only exists for departures seen while the backend was running. |
| departure_time | text | When that departure was detected (UTC). |
| length_m, beam_m | metres | Ship length and beam from AIS static data. Lengths of 0 or above 500 m are set to missing. |
| size_class | text | small (<100 m), medium (100-200 m), large (200-300 m), very large (>300 m), or "unknown size". |
| hub | text | The port hub whose radius the ship is inside (nearest wins); empty means open water. |
| zone | text | Sub-zone of that hub (Benelux coast, Dover Strait & Channel, UK east coast & Thames, German Bight & Ems). |
| region | text | Study region. |
| dist_to_hub_km | km | Distance to that hub's centre. |
| is_edge | 0/1 | 1 if within 0.5 degrees of the edge of the tracked area. |
| stationary_but_moving | 0/1 | Reported "moving" with speed under 0.5 kn (kept, flagged). |
| moving_but_anchored | 0/1 | Reported anchored or moored with speed above 3 kn (kept, flagged). |
