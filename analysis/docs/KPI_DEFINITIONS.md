# KPI definitions

Written before the analysis, so the numbers mean the same thing every time.

| Term | Definition |
|---|---|
| **Current ship** | Heard from in the last 15 minutes. All traffic and congestion numbers use current ships only, so ships that left hours ago are not counted as waiting. |
| **Hub** | A major port with a centre point and a radius (`config/hubs.csv`). A ship belongs to the nearest hub whose radius it is inside. |
| **Under way / idle** | Under way = speed 0.5 kn or more. Idle = the status says under way but the ship is stationary (status is typed by hand and often stale). |
| **Waiting ship** | A ship with status "anchored at sea" (`at_anchor`) inside a hub's radius. Ships moored at a berth (`at_berth`) are *not* waiting. A broader definition that also counts idle ships is reported as a sensitivity check. |
| **Congestion (snapshot)** | Number of waiting ships at a hub, and the share of ships in its radius that are waiting. |
| **Congestion level** | Relative, not absolute. Hubs (or days) are split into thirds: lowest third **green**, middle third **yellow**, top third **red**. |
| **Traffic** | Number of ships inside a hub's radius (any status), or fleet-wide ships heard from in the last 15 minutes (collector). |
| **Usable day** | A day with at least 50% of the expected collector polls. Only usable days enter daily levels, weekly and monthly counts. |
| **Silent ship (dark-flagged)** | No AIS message for 20+ minutes (rule in `backend/dark_fleet.py`). Rates are computed on ships heard from in the last 60 minutes, because the backend keeps silent ships longer in the interior than near the edge and an unrestricted rate would be biased. It cannot distinguish a coverage gap from a switched-off transponder; on live data most flagged ships were stationary harbour traffic. |
| **Near the edge** | Within 0.5 degrees of the tracked box. Ships there may simply have left receiver coverage. |
| **Estimate** | Any number built from `config/assumptions.csv` instead of measured from AIS (fuel, CO2, cost). Always shown as low / central / high. |
| **Excess waiting (time analysis)** | Waiting ships on yellow and red days above the average of green days: the baseline-adjusted figure that can honestly be linked to congestion. |
