# Maritime Traffic Analytics

A data-analysis layer on top of the Maritime Globe app: it turns live AIS ship data into cleaned data, SQL analysis, charts, an Excel workbook,
an interactive dashboard and a written findings memo, with **one command**.

**Study area:** North Sea and English Channel (19 port hubs). **Source:** live AIS (AISStream) collected by the Maritime Globe backend.

## Quick start

```bash
# 1. once: a separate environment for the analysis
python3 -m venv analysis/.venv
source analysis/.venv/bin/activate
pip install -r analysis/requirements.txt

# 2. with the backend running (uvicorn main:app --reload), from the project root:
python analysis/run_all.py
```

It pulls the live fleet, cleans it, runs the SQL, draws the charts, builds the workbook and dashboard, and writes the findings. About 10 seconds.
Open `analysis/outputs/dashboard.html` (needs internet for the map) and `analysis/outputs/FINDINGS.md`.

Other ways to run it:

| Command | What it does |
|---|---|
| `python analysis/run_all.py --csv FILE` | analyse a saved snapshot instead of the live backend |
| `python analysis/run_all.py --no-fetch` | reuse the newest saved snapshot (`analysis/data/raw/`) |
| `python analysis/run_all.py --types cargo,tanker` | analyse only these vessel types (the feed also holds tugs, ferries, pleasure craft and inland barges) |
| `python analysis/run_all.py --weather` | also test weather vs waiting ships (internet and several weeks of history needed) |
| `streamlit run analysis/app.py` | filterable dashboard (region, zone, vessel type) |
| Open `analysis/notebooks/01_ais_exploration.ipynb` in VS Code | the exploration notebook, with space for your interpretation |

## Building history (v2): the time analysis

A snapshot shows one moment. To see trends, weekly and monthly patterns and a baseline for the cost of congestion, run the collector in its own terminal while the backend runs:

```bash
caffeinate -i python analysis/collector.py        # every 30 minutes; --interval N to change, --once to test
```

It stores about 125 small summary rows per poll (not every ship), roughly 0.5 MB a day, in `analysis/data/history.db` (git-ignored).
Re-run `run_all.py` any time; the time analysis switches on by itself, and each view appears only when there is enough data:

| View | Needs |
|---|---|
| Daily traffic and congestion levels (green / yellow / red), hour-of-day pattern | 3 usable days |
| Speed on green vs red days, excess-waiting estimate | 7 usable days |
| Weekday pattern, weekly summary, weather test | 14 usable days |
| Monthly summary | 28 usable days |

The laptop and backend must be running. Gaps are recorded, reported and excluded from levels, never hidden.

## What is in `outputs/`

| File | Contents |
|---|---|
| `FINDINGS.md` | Written analysis: executive summary, 7 findings, recommendations (draft), method, limitations, assumptions with sources |
| `dashboard.html` | Interactive dashboard: Overview, Congestion, Fleet, Voyages, Cost & fuel, Data quality, Time analysis |
| `MaritimeAnalytics.xlsx` | Summary, hub congestion with green/yellow/red, live pivot, editable Assumptions, Estimates driven by formulas, clean data |
| `charts/`, `time/` | PNG charts (also used in the memo) |
| `sql/` | Result of each query in `sql/*.sql` |
| `data/` | Cleaned dataset, cleaning log, and every table behind the charts |

## How it works

1. **Clean** (`ais/clean.py`): every rule is explicit and counted: duplicates, impossible speeds (including AIS's 102.3 "not available" code), IMO checksum, free-text destinations normalised (`NL RTM`, `NLAMS01090DOCKX00018`, `FOR ORDERS`...).
2. **Assign** each ship to a hub by distance (`config/hubs.csv`).
3. **Analyse** the same numbers twice, in pandas and in SQL (`sql/`), and cross-check them. The run prints whether they agree.
4. **Estimate** fuel, CO2 and cost from `config/assumptions.csv` (published ranges, each with its source).
5. **Report**: every number in the memo is computed from the data; interpretation lines are marked for you to review.

## Read this before presenting it

- **Estimates are not measurements.** AIS has no fuel, operator or cargo data. Fuel, CO2 and cost are low / central / high ranges from published figures, and the fuel-at-anchor-by-size values are analyst assumptions bracketed by those sources. Cost of ships *idling* is an upper bound for cost of *congestion*; the time analysis gives the baseline-adjusted version.
- **Current ships only.** Traffic and congestion use ships heard from in the last 15 minutes; ships that went silent are used only for the dark-fleet analysis (the backend keeps silent ships for up to 24 hours).
- **Status is not trusted on its own.** Navigation status is typed by hand: on the live feed about two thirds of ships whose status said "under way" were actually stationary. Ships are therefore classified by speed too (under way = 0.5 kn or more; idle = stationary but status says under way), and the report shows how sensitive the hub ranking is to that choice.
- **Mixed fleet.** The feed includes tugs, ferries, pleasure craft and inland barges, not only seagoing ships. The report breaks results down by segment, and `--types cargo,tanker` focuses the analysis.
- **Levels are relative.** Green / yellow / red are thirds of the observed data, not an industry standard.
- **One region, land-based coverage.** Open-sea traffic is under-represented, and counts depend on receiver coverage and on when your backend ran.
- **Hub coordinates and UN/LOCODEs** in `config/hubs.csv` are approximate and written from general knowledge. Check them if you rely on a specific hub.
- **No company-level losses.** Nothing in AIS identifies who owns or charters a ship.

## Extending beyond one region

The live ships cover one region (the North Sea and English Channel); the reference data (ports, lighthouses, shipyards and other facilities) is global. The analysis is built to extend, but it is not a switch you flip:

- **Works as is:** the cleaning rules, the speed-versus-status logic, the segment view, the SQL and the Excel structure do not depend on location. Adding a hub to `config/hubs.csv` adds it everywhere.
- **Needs changing:** the cleaning step drops ships outside `TRACKED_BOX` (`ais/config.py`, matching the box in `backend/main.py`); every ship outside a hub is labelled with one region name; the dashboard map is fixed to this box; some assumptions are regional (the fuel price is Rotterdam's, and MGO is the central fuel because the North Sea is a low-sulphur zone).
- **Scale and coverage:** a global feed would outgrow SQLite (DuckDB or PostgreSQL would be next) and the scatter map, and free land-based AIS still leaves the open ocean mostly empty, so regional comparisons would be biased by receiver coverage. Congestion levels would also have to be set per hub or region.

Expect about a day of focused work to support several regions properly.

## Layout

```
analysis/
  run_all.py            one command for everything
  collector.py          history collector (v2)
  app.py                Streamlit dashboard
  ais/                  the pipeline (config, load, clean, geo, metrics, estimates, charts, excel, dashboard, report, sqlrun, timeseries)
  config/               hubs.csv, assumptions.csv
  sql/                  9 analysis queries
  notebooks/            exploration notebook
  docs/                 data dictionary, KPI definitions
  outputs/              generated results
```
