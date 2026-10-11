# Maritime Traffic Analytics

**A live 3D globe of real ships, tracked via AIS, with genuine maritime-intelligence features layered on top — not just dots on a map.**

Most public ship trackers show you *where* ships are. This project treats the live AIS feed as raw data to derive real insight from: which ships have gone dark, how congested a port is right now, and what's actually happening around any given vessel — answered by an AI agent that queries live data instead of guessing.

<!-- ![Maritime Globe screenshot](docs/screenshot.png) -->

---

## Table of Contents

- [Key Features](#key-features)
- [Also Built In](#also-built-in)
- [Scope: Why Not Every Ship Worldwide?](#scope-why-not-every-ship-worldwide)
- [Tech Stack](#tech-stack)
- [Architecture](#architecture)
- [Getting Started](#getting-started)
- [API Reference](#api-reference)
- [Known Limitations](#known-limitations)
- [Roadmap](#roadmap)

---

## 🎯 Problem, solution and approach

**The problem.** Raw ship-tracking (AIS) data looks authoritative but misleads. It is a firehose of position messages with free-text destinations typed by hand, navigation status that crews forget to update (about 30% of ships marked "under way" are actually stationary), missing identifiers (only about 25% of ships carry a valid IMO number), and a mix of cargo ships, tugs, ferries, pleasure craft and inland barges. Raw counts therefore overstate movement, blur seagoing and local traffic, and make ships that simply went quiet look suspicious. Operators and analysts need trustworthy answers to simple questions: where are ships waiting, what does that waiting cost, and which signals are real?

**The solution.** A live maritime intelligence tool for the North Sea and English Channel with two layers:
- **An application:** a 3D globe with ports and maritime infrastructure worldwide, per-ship voyage and weather context, silent-ship ("dark fleet") alerts, port congestion, and an AI assistant that answers questions from the live fleet data.
- **An analytics pipeline:** it cleans the feed, measures congestion per port hub, separates fleet segments, and estimates the fuel and cost of ships waiting at anchor, delivered as an Excel workbook, an interactive dashboard and a findings memo.

**How it works.**
1. **Ingest.** Live AIS from AISStream flows into a FastAPI backend, alongside the World Port Index and curated facility lists for context.
2. **Clean.** Every rule is explicit and counted: impossible speeds, IMO checksums, free-text destinations normalised, and ships classified by speed as well as status.
3. **Model.** Ships are assigned to 19 port hubs; "waiting" means anchored at sea inside a hub's radius; congestion levels are relative (green, yellow, red).
4. **Verify.** Headline numbers are computed twice, in pandas and in SQL, and cross-checked. Silent-ship rates are compared on equal-age windows, which removed a bias found during the analysis.
5. **Answer.** The AI assistant uses function calling over live data, so replies come from the data and not from the model's memory.
6. **Track over time.** A history collector stores per-hub summaries every 30 minutes, and time views (daily levels, weekday patterns) appear as data accumulates.




## Key Features

| Feature | What it does |
|---|---|
| 🔴 **Dark-fleet / AIS-gap detector** | Flags any ship silent for 20+ minutes — a simplified version of a technique maritime intelligence firms sell to governments for sanctions-evasion and illegal-fishing monitoring. Computed live from real AIS timestamps. |
| 🟢 **Live port congestion** | For every port in the tracked region, computes a live congestion score from real ship density (anchored ships within 15km, docked count, traffic). Explicitly scoped as a *live estimate*, not a historical forecast — no historical port-call data exists to train a real predictor on. |
| 💬 **AI fleet chat assistant** | Ask questions in plain English — *"how many tankers are idling near Rotterdam?"*, *"which Belgian port is busiest right now?"* — and get answers grounded in the live fleet. Powered by Groq (`openai/gpt-oss-120b`) with function-calling: the model decides *what* to query, the backend runs the real filter against live data, and the model only writes the final sentence. |

## Also Built In

- **Real vessel identity** — flag (derived from the MMSI's official ITU country code), IMO number, and call sign, from live AIS static data
- **Full live weather per ship** — wind speed/direction/gusts, sky condition with storm flag, pressure, visibility, wave height/period, swell, sea temperature, ocean current
- **Nearest-facility awareness** — real distance and compass bearing from any ship to the nearest port, lighthouse, shipyard, recycling yard, bunkering station, dry dock, and wet dock
- **Global infrastructure data** — ~3,630 real ports (NGA World Port Index) plus curated real shipyards, lighthouses, recycling yards, bunkering stations, and dry/wet docks, all as toggleable map layers
- **Interactive port-checker** — "Check another port →" cycles through progressively farther ports from a selected ship, each numbered live on the globe
- **Voyage data** — destination and ETA from AIS, plus departure ports detected live when a ship leaves a known port. The departure log is saved to disk and survives restarts, but only covers departures observed while the server was running
- **Smarter chat** — remembers the conversation, looks up ships by name or IMO and facilities by name, filters by flag, departure port and destination, and highlights whole result sets on the globe

## Scope: Why Not Every Ship Worldwide?

A deliberate engineering decision, not an oversight.

1. **AIS coverage isn't actually global.** Free feeds like [AISStream.io](https://aisstream.io) rely on a community network of land-based receivers, strong near coastlines, and dropping off sharply in open ocean. Closing that gap needs *satellite* AIS — a paid commercial product (Kpler, Spire, etc.). "All ships worldwide" on a free tier would mean busy coastlines and empty oceans — a worse product than one honestly scoped.
2. **Rendering cost.** Every ship is a live 3D object, rebuilt on every 10-second poll. The current North Sea/English Channel region alone regularly holds 1,000–3,000+ live ships. Global scale would need a different rendering strategy (GPU instancing, clustering) to stay smooth in a browser.
3. **Payload size.** `/ships` returns the full tracked fleet on every poll. At global AIS volume that payload reaches multiple megabytes every 10 seconds — untenable on free-tier infrastructure.

**None of the analysis features are region-limited.** Dark-fleet detection, port congestion, nearest-facility lookups, and the AI chat assistant already operate on the *entire* global port/infrastructure dataset. They'd work identically well the moment ship tracking widened — the AIS subscription's bounding box is a single line of config, not an architectural limitation.

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React, TypeScript, Vite, [react-globe.gl](https://github.com/vasturiano/react-globe.gl) (Three.js) |
| Backend | Python, FastAPI, async WebSocket |
| Live AIS data | [AISStream.io](https://aisstream.io) |
| Port data | [NGA World Port Index](https://msi.nga.mil/Publications/WPI) |
| Weather data | [Open-Meteo](https://open-meteo.com) (marine + atmospheric, free, no key) |
| AI chat | [Groq](https://groq.com) (`openai/gpt-oss-120b`, function-calling) |


## Architecture

AISStream.io (WebSocket)
│
▼
FastAPI backend ──► in-memory live ship store
│ │
│ ├──► dark-fleet flagging
│ ├──► port congestion scoring
│ └──► /chat (Groq function-calling)
▼
REST endpoints (/ships, /ships/dark-fleet, /chat)
│
▼
React frontend ──► react-globe.gl (3D render)
│
├──► Open-Meteo (weather, per selected ship)
└──► NGA World Port Index (global port data)


## Getting Started

### Prerequisites
- Python 3.10+
- Node.js 18+
- A free [AISStream.io](https://aisstream.io) API key
- A free [Groq](https://console.groq.com) API key (for the chat assistant)

### Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install fastapi uvicorn websockets python-dotenv requests
```

Create `backend/.env`:

AISSTREAM_API_KEY=your_key_here
GROQ_API_KEY=your_key_here


Run it:

```bash
uvicorn main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

## API Reference

| Method | Endpoint | Description |

| `GET` | `/ships` | All currently tracked ships, with dark-fleet flags applied |
| `GET` | `/ships/dark-fleet` | Only ships currently flagged as dark |
| `POST` | `/chat` | AI fleet assistant. Send `{ "message": "...", "history": [...] }`, get `{ "reply", "ships", "facilities" }` back |

## Known Limitations

- No operator or build-year data — this doesn't exist in AIS broadcasts. The only real source (Equasis) requires a login with no public API, and this project doesn't build scrapers for authenticated third-party services.
- Some smaller vessels (fishing boats, pleasure craft, Class B AIS transponders) never broadcast an IMO number — a real limitation of the ship's equipment, not a bug.
- Live ship tracking is scoped to the North Sea/English Channel (see [Scope](#scope-why-not-every-ship-worldwide) above).
- Departure ports are only recorded for departures observed while the server is running. Ships that left port before that are unknown, and "departed yesterday"-style questions can't be answered.
- Ships are dropped from the live list after 60 minutes of silence if they were last seen near the edge of the tracked area, and after 24 hours if they went silent well inside it. A ship that really switched off its transponder near the edge cannot be told apart from one that sailed out of coverage.

## Roadmap

- [ ] Self-check/monitoring for overall system health (backend, AIS feed, data freshness)
- [ ] Evaluate widening live tracking beyond the North Sea/English Channel
- [x] `requirements.txt` for one-command backend setup

## 📊 Analytics layer

A reproducible analysis pipeline sits on top of the live feed (`analysis/`). One command, `python analysis/run_all.py`, pulls the current fleet, cleans it, runs SQL and pandas analysis, and builds an Excel workbook, an interactive dashboard and a written findings memo. Setup and details are in [`analysis/README.md`](analysis/README.md).

**What it found** (North Sea & English Channel, snapshot of 11 Oct 2026, about 6,900 current ships):

- **Data quality.** Only about 25% of ships carry a valid IMO number. Destinations are free text typed by hand, and cleaning raised the share resolved to a port from about 28% to about 35%. About 30% of ships whose status says "under way" are actually stationary, so ships are classified by speed as well as status.
- **What the feed contains.** Only about 16% of current ships are under way and about 44% are moored, and about 69% are under 100 m. It is a harbour-dominated feed (tugs, ferries, pleasure craft, inland barges and cargo ships), not open-sea shipping.
- **Congestion.** Rotterdam and Amsterdam have the most ships waiting at anchor (about 70 each), followed by Antwerp (about 30). This is one snapshot; trends need the history collector.
- **Silent ships.** About 8% of ships heard in the last hour had been silent for 20+ minutes. About 86% of them were stationary when last heard, and the rate was similar at the edge of the tracked area and in the interior (about 7-8% in both). A first calculation suggested a large edge effect, but it was an artefact of how long silent ships are retained, and it disappeared when ships of the same age were compared.
- **Cost of waiting (estimate).** Ships at anchor near hubs burn roughly 140-780 t of fuel and cost about $1.5-4 million per day, built from published fuel and operating-cost ranges. This is an upper bound for congestion-attributable cost, not a measured loss.

**Method highlights.** Every cleaning rule is counted and reported. The same headline numbers are computed in pandas and in SQL and cross-checked. A history collector stores per-hub summaries every 30 minutes, and time views (daily levels, weekday and weekly patterns) switch on as data accumulates.

**Limits.** One region only; AIS coverage comes from land-based receivers, so open-sea traffic is under-represented; fuel, CO2 and cost are estimates with explicit assumptions and sources; AIS has no operator or cargo data, so no company-level loss can be computed.



## 📧 Contact & Info

* **Analyst:** Mohammed Faraaz Shaik — [faraazshaik05042005@gmail.com](mailto:faraazshaik05042005@gmail.com)
* **LinkedIn:** [www.linkedin.com/in/mohammed-faraaz-shaik](https://www.linkedin.com/in/mohammed-faraaz-shaik)
* **GitHub:** [FaraazonMac](https://github.com/FaraazonMac)
