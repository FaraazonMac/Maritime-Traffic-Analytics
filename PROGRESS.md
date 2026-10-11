# Maritime Globe — Progress Log

## Project
A live 3D ship-tracking globe (React + react-globe.gl) backed by a Python FastAPI service consuming real AIS data, with three planned differentiator features: dark-fleet/sanctions detector, port congestion predictor, AI agent chat.

## Milestone log

### Session 1 — Frontend foundations
- Set up Node.js, Vite + React + TypeScript project
- Learned JSX, useState, .map(), git/GitHub basics
- Built first globe (Cesium, later switched to react-globe.gl for better look/less friction)

### Session 2 — Globe styling
- Custom SVG markers for ships (status-based), ports (anchor icon), lighthouses (triangle)
- Click-to-inspect detail panel
- Fixed pointer-events bug blocking clicks

### Session 3 — Backend foundations
- Python virtual environment, FastAPI, first `/ships` endpoint
- Connected frontend to backend via fetch() + CORS

### Session 4 — Real AIS data
- Signed up for AISStream.io, secured API key in `.env`
- Built websocket listener as a FastAPI background task
- Fixed SSL cert issue, Anaconda/venv environment confusion
- Real live ships now flowing end-to-end: AISStream → backend → frontend → globe

### Session 5 — Real-data cleanup (today)
- Added periodic refetch (ships now update every 10s, genuinely live)
- Diagnosed and fixed performance issue: switched ships from DOM-based HTML markers to WebGL `objectsData` sprites (handles hundreds of real ships smoothly)
- Built directional arrow markers using real AIS heading data, uniform sizing across zoom levels (`sizeAttenuation: false`)
- Swapped to higher-res free Earth texture
- Accepted known limitation: map blurs at extreme zoom (fixed-resolution free texture, not a bug)



### Session 6 — Dark-fleet / AIS-gap detector
- Built `dark_fleet.py`: flags any ship with no AIS update for 20+ minutes (`DARK_THRESHOLD_MINUTES`), with an honest reason string ("may have left tracked area or gone dark" — acknowledges the ambiguity)
- New `/ships/dark-fleet` endpoint; `/ships` now runs every ship through the flag check
- Wired into frontend: flagged ships render in alert red, detail panel shows a red-bordered "Dark Fleet Alert" box
- Fixed a real bug along the way: ship clicks weren't registering (`obj.userData` was being read off the wrong object — the click handler receives the ship data directly, not a wrapper)
- Extensively tested threshold behavior by temporarily lowering it to force visible flags, then restoring to 20 min

### Session 7 — Vessel type, live weather, real ports
- Backend now listens for AIS `ShipStaticData` messages (not just `PositionReport`), merging vessel type into each ship's record instead of overwriting it on every position update
- Decided against per-type ship icons on the globe (kept simple arrow/circle); vessel type shown as a "Type" row in the detail panel instead
- Live wave height per selected ship via Open-Meteo Marine API (handles inland/no-data ships gracefully)
- Replaced the 4 hardcoded ports with a live fetch of NGA's World Port Index (~3,630 real global ports) via ArcGIS REST GeoJSON

### Session 8 — Real-world infrastructure layers
- Attempted live shipyard/lighthouse/tank-storage data via OpenStreetMap's Overpass API; hit repeated timeout failures on unscoped worldwide queries across two different Overpass mirrors — concluded this was a genuine free-server capacity limit, not a bug
- Switched to curated real-data lists instead (source of truth for a resume project, matching how ports/bunkering were already handled): 55 shipyards, ~130 lighthouses, 15 ship recycling yards, 30 bunkering stations, 20 dry docks, 10 wet docks
- Built a "Map Layers" sidebar — all categories hidden by default, toggleable
- Clicking any facility marker opens a detail panel with name, country, and a real fact
- Added nearest-facility awareness: clicking a ship computes real distance (haversine) and compass bearing to the nearest port, lighthouse, shipyard, recycling yard, bunkering station, dry dock, and wet dock

### Session 9 — Port congestion predictor
- Scoped honestly as a live congestion score (count of anchored ships within 15km, classified Low/Medium/High), not a historical forecast — no historical port-call data exists to train a real predictor on
- New "Port Congestion (Live)" map layer, color-coded markers
- Built an interactive port-checker on the ship panel: shows nearest port + congestion, "Check another port →" cycles to progressively farther ports (each numbered simultaneously on the globe), "← Previous port" to go back
- Port facility panel (clicking a port directly) shows live docked-ship count, nearby traffic, and congestion level
- Added a full country-code → country-name lookup table for cleaner facility panel display

### Session 10 — AI fleet chat assistant
- New `/chat` backend endpoint using Groq's API with function-calling
- Single tool (`query_ships`) lets the model filter the live fleet by vessel type, status, dark-fleet flag, idle time, and/or proximity to any of the ~3,630 global ports (backend independently fetches the same World Port Index on startup, decoupled from the frontend's copy)
- Debugged through: wrong model name (`llama-3.3-70b-versatile` deprecated on Groq, switched to `openai/gpt-oss-120b`), a route defined before `app = FastAPI(...)` existed, a non-JSON-serializable `datetime` field, and a malformed follow-up message causing 400s
- Frontend: bottom-right toggle "Fleet Assistant" chat widget; matching ships highlight on the globe (dimming others) only when the result set is small enough to show in full — broad queries just show the text answer

### Session 11 — UI polish & bug fixes
- Removed a fixed-width `#root` CSS rule that was leaving empty space on wide screens
- Fixed a stacking-order bug where globe labels rendered on top of overlay panels
- Made the ship dimming effect apply consistently on both direct ship-click and chat highlighting
- Panel background, blur, and text-centering cleanup across all four panel types

### Session 12 — Flag/IMO/call sign, chat reliability, weather depth, UI bugs
- Added real ship identity from AIS: flag derived from the MMSI's Maritime Identification Digits (official ITU country-code table, 290 codes verified against the source list), plus IMO number and call sign captured from `ShipStaticData`
- Made the chat assistant multi-step: it can call its tools several times per question (e.g. one lookup per port when comparing), retries automatically on Groq's rate limit (429), and sends the model a compact summary instead of full ship records to stay under the token budget
- Added chat tools `port_direction` (real distance and bearing between two ports) and `find_ship` (live ship lookup by name). This fixed a bug where the model answered ship-name questions from general knowledge, e.g. treating the ship "RATINGEN" as the German town
- Chat replies now render `**bold**` as bold text and keep line breaks
- Congestion facility panel now matches the clicked marker's colour (red, amber or green)
- Built the full live weather block: wind speed, direction and gusts; sky condition with thunderstorm flag; pressure; visibility; wave height, direction and period; swell; sea temperature; and current. Switched from Open-Meteo's `hourly[0]` (which was reading midnight UTC, not now) to its `current` parameter
- Fixed a page-layout bug: `#root` only had `min-height`, so any overflow made the whole page scrollable. Locking `html`, `body` and `#root` to the viewport also stopped mouse-wheel scrolling over a panel from scrolling the page

### Session 13 — Voyage data, chat upgrades, departure tracking
- Captured Destination and ETA from AIS static data. The destination text is matched to a known port only on an exact or substantial match, with no forced guesses, and both show in the ship panel
- Built departure tracking: when a ship flips from anchored-in-port to moving, the nearest known port (within 15 km) of its previous position is logged as `departure_port` with a timestamp. It is held in memory and resets on restart. At one check, 58 ships had both a departure and a destination
- Chat assistant upgrades:
  - Conversation memory (history is sent with each message)
  - Multi-round tool calls with rate-limit retry
  - New tools: `find_ship` (by name or IMO, returns every match), `find_facility` (ports plus ~150 lighthouses, shipyards, docks and other facilities duplicated server-side), and `port_direction`
  - New filters: `has_destination` and `has_departure`
- Chat highlighting: numbered markers for 2+ facilities, ships dim, the camera frames all results, and a Clear button sits in the chat header. Clicking a ship inside a highlighted group keeps the group visible
- Fixed Groq tool-validation errors by making optional tool parameters nullable
- Built route arcs from departure to current position to destination, then removed them. For short routes they rendered as oversized wedges, and a flat-line replacement was not worth the risk. The same information stays in the panel as text
- Wrap-up: README written, `requirements.txt` generated, dead `test_ais.py` deleted, and confirmed `.env` was never committed to git

### Session 14 — Chat filters, full-set highlighting, persistent departures
- Added chat filters for flag, departure port, and destination text (`flag`, `departed_from`, `destination_contains`), so questions like "Dutch cargo ships heading to Rotterdam" are answered from the data instead of the model guessing from a 5-ship sample
- Highlighting now covers the entire result set (up to 500 ships) rather than the 20-ship sample the model sees. Ships are keyed by MMSI, so two ships with the same name no longer overwrite each other
- Added output formatting rules so replies use plain lines instead of Markdown tables the chat box can't render
- Made the model check both ships and facilities before reporting a name as not found
- Persisted the departure log to `backend/departures.json` (git-ignored). It is written when a departure is detected and reloaded on startup, so departures survive restarts
- Rotated the Groq API key after it was exposed during debugging.

### Session 15 — Ship expiry
- Added a background task that drops ships from the live list when they stop reporting. Ships last seen near the edge of the tracked area (within 0.5°) are dropped after 60 minutes, since they most likely sailed out of coverage. Ships that go silent well inside the area are kept for 24 hours so they stay flagged as dark-fleet candidates
- Effect: the tracked count no longer grows without limit, so fleet counts and chat answers reflect ships that are actually still reporting

### Session 16 — Analytics layer
- Built an analysis pipeline in `analysis/`: one command cleans the live fleet, runs 9 SQL queries (cross-checked against pandas), draws 13 charts, builds an Excel workbook (live pivot, editable assumptions, formula-driven estimates), an interactive dashboard and a findings memo
- Found on real data that navigation status cannot be trusted alone (about two thirds of ships marked "under way" were stationary), so ships are classified by speed too; added a by-segment view because the feed mixes tugs, ferries, pleasure craft, barges and cargo ships
- Caught that the silent-ship rate was biased by how long the backend retains ships (an apparent edge effect vanished when comparing ships of the same age) and that routes were double-counted under two spellings; both fixed
- Captured ship length and beam from AIS static data (about 95% of ships now report a length) so fuel and cost estimates use size classes
- Added a history collector (per-hub summaries every 30 minutes) and a time analysis gated by how many usable days exist
- Moved the analysis Python environment outside the Desktop folder after file reads from it stalled




## Current state
- ✅ Analytics pipeline (cleaning, SQL, dashboard, Excel workbook, findings memo) running on live data
- ⬜ Daily and weekly congestion patterns fill in as the history collector gathers more days
- ✅ Live globe with real ships, ports, lighthouses, shipyards, recycling yards, bunkering stations, dry/wet docks (toggleable layers)
- ✅ Dark-fleet / sanctions-evasion detector
- ✅ Live port congestion score
- ✅ AI fleet chat assistant (Groq function-calling, multi-step, rate-limit-safe, with conversation memory, ship/facility lookup by name, and numbered multi-location highlighting)
- ✅ Nearest-facility distance and compass bearing on every ship
- ✅ Full live weather per ship (wind, sky, pressure, visibility, waves, swell, sea temp, current)
- ✅ Real flag (from MMSI), IMO number, and call sign per ship (where broadcast)
- ✅ Destination and ETA from AIS, plus departure port detected live when a ship leaves a known port
- ✅ Departure log persisted to disk and survives restarts
- ⬜ No operator or build-year data (no legitimate free source; Equasis requires a login and has no public API)
- ⬜ Live ship tracking is scoped to the North Sea / English Channel by choice, because of AIS coverage, render cost and payload size

## Next target
Persist the departure log to a file, add a self-check for overall system health, record the demo video, and decide on the global-ships scope.
## Next target
Build a self-check/monitoring feature that verifies the whole project is actually working (backend up, AIS feed live, ports loaded, chat reachable). Then decide on global ship tracking scope, then wrap-up tasks: `requirements.txt`, README rewrite, dead-code cleanup (test_ais.py, test_groq.py), demo video.