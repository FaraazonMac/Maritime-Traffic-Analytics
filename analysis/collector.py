"""Lean history collector. Every N minutes it summarises the live fleet per port hub into SQLite.

Run it in its own terminal while the backend is running:
    caffeinate -i python analysis/collector.py            # every 30 minutes
    python analysis/collector.py --once                   # a single poll (test)

It stores a few dozen small rows per poll (not every ship), so a month of data is a few megabytes.
"""
import argparse
import datetime as dt
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd  # noqa: E402
import requests  # noqa: E402

from ais import clean, geo, load  # noqa: E402
from ais.config import API_URL, FRESH_MINUTES, HISTORY_DB, HUBS_CSV  # noqa: E402

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_ts TEXT PRIMARY KEY, ok INTEGER, note TEXT,
    total_ships INTEGER, fresh_ships INTEGER, moving INTEGER, at_anchor INTEGER, at_berth INTEGER, dark INTEGER, unknown_type INTEGER, idle INTEGER);
CREATE TABLE IF NOT EXISTS hub_summary (
    run_ts TEXT, hub TEXT, zone TEXT, region TEXT, ships_in_radius INTEGER, at_anchor INTEGER, at_berth INTEGER,
    moving INTEGER, avg_speed_moving REAL, idle INTEGER);
CREATE TABLE IF NOT EXISTS hub_size_summary (
    run_ts TEXT, hub TEXT, size_class TEXT, ships INTEGER, at_anchor INTEGER, moving INTEGER);
CREATE TABLE IF NOT EXISTS type_summary (
    run_ts TEXT, vessel_type TEXT, ships INTEGER, moving INTEGER, at_anchor INTEGER, near_hub_at_anchor INTEGER, avg_speed_moving REAL);
CREATE INDEX IF NOT EXISTS ix_hub_run ON hub_summary(run_ts, hub);
CREATE INDEX IF NOT EXISTS ix_hsz_run ON hub_size_summary(run_ts, hub);
"""


def migrate(conn):
    """Upgrade a history file created by an earlier version (adds the 'idle' columns). Safe to run every time."""
    for table in ("runs", "hub_summary"):
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
        if "idle" not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN idle INTEGER")
    conn.commit()


def summarise(df, hubs):
    """Return (runs_row_dict, hub_summary_df, hub_size_df, type_df) for one poll."""
    fresh = df[df["minutes_since_update"].fillna(0) <= FRESH_MINUTES].copy()
    fresh = geo.assign_hubs(fresh, hubs)
    runs_row = {
        "total_ships": int(len(df)), "fresh_ships": int(len(fresh)),
        "moving": int((fresh["status_group"] == "moving").sum()), "at_anchor": int((fresh["status_group"] == "at_anchor").sum()),
        "at_berth": int((fresh["status_group"] == "at_berth").sum()), "idle": int((fresh["status_group"] == "idle").sum()),
        "dark": int(df["is_dark_flagged"].sum()),
        "unknown_type": int((fresh["vessel_type"] == "unknown").sum()),
    }
    near = fresh[fresh["hub"].notna()]
    hub_rows = []
    for _, h in hubs.iterrows():
        s = near[near["hub"] == h["name"]]
        mv = s[(s["status_group"] == "moving") & s["speed"].notna()]
        hub_rows.append({"hub": h["name"], "zone": h["zone"], "region": h["region"], "ships_in_radius": int(len(s)),
                         "at_anchor": int((s["status_group"] == "at_anchor").sum()), "at_berth": int((s["status_group"] == "at_berth").sum()),
                         "moving": int((s["status_group"] == "moving").sum()), "idle": int((s["status_group"] == "idle").sum()),
                         "avg_speed_moving": float(mv["speed"].mean()) if len(mv) else None})
    hsz = (near.groupby(["hub", "size_class"])
           .agg(ships=("mmsi", "size"), at_anchor=("status_group", lambda x: int((x == "at_anchor").sum())),
                moving=("status_group", lambda x: int((x == "moving").sum())))
           .reset_index())
    mv = fresh[(fresh["status_group"] == "moving") & fresh["speed"].notna()].groupby("vessel_type")["speed"].mean()
    near_anchor = near[near["status_group"] == "at_anchor"].groupby("vessel_type").size()
    tp = (fresh.groupby("vessel_type")
          .agg(ships=("mmsi", "size"), moving=("status_group", lambda x: int((x == "moving").sum())),
               at_anchor=("status_group", lambda x: int((x == "at_anchor").sum())))
          .reset_index())
    tp["near_hub_at_anchor"] = tp["vessel_type"].map(near_anchor).fillna(0).astype(int)
    tp["avg_speed_moving"] = tp["vessel_type"].map(mv)
    return runs_row, pd.DataFrame(hub_rows), hsz, tp


def collect(conn, hubs, url):
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        raw = load.from_records(resp.json())
        df = clean.light_clean(raw)
        runs_row, hub_df, hsz_df, tp_df = summarise(df, hubs)
    except Exception as e:  # noqa: BLE001
        conn.execute("INSERT OR IGNORE INTO runs (run_ts, ok, note) VALUES (?,?,?)", (ts, 0, str(e)[:200]))
        conn.commit()
        print(f"{ts}  FAILED: {e}")
        return False
    conn.execute("INSERT OR REPLACE INTO runs (run_ts, ok, note, total_ships, fresh_ships, moving, at_anchor, at_berth, dark, unknown_type, idle) "
                 "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                 (ts, 1, None, runs_row["total_ships"], runs_row["fresh_ships"], runs_row["moving"], runs_row["at_anchor"],
                  runs_row["at_berth"], runs_row["dark"], runs_row["unknown_type"], runs_row["idle"]))
    hub_df.insert(0, "run_ts", ts)
    hub_df.to_sql("hub_summary", conn, if_exists="append", index=False)
    if len(hsz_df):
        hsz_df.insert(0, "run_ts", ts)
        hsz_df.to_sql("hub_size_summary", conn, if_exists="append", index=False)
    if len(tp_df):
        tp_df.insert(0, "run_ts", ts)
        tp_df.to_sql("type_summary", conn, if_exists="append", index=False)
    conn.commit()
    print(f"{ts}  saved: {runs_row['fresh_ships']} fresh ships, {runs_row['at_anchor']} at anchor, {runs_row['idle']} idle, {len(hub_df)} hubs")
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--interval", type=float, default=30, help="minutes between polls (default 30)")
    ap.add_argument("--once", action="store_true", help="collect one snapshot and exit")
    ap.add_argument("--url", default=API_URL)
    args = ap.parse_args()
    HISTORY_DB.parent.mkdir(parents=True, exist_ok=True)
    hubs = geo.load_hubs(HUBS_CSV)
    conn = sqlite3.connect(HISTORY_DB)
    conn.executescript(SCHEMA)
    migrate(conn)
    print(f"Collecting into {HISTORY_DB} every {args.interval:g} minutes. Ctrl+C to stop. Keep the backend running.")
    try:
        while True:
            collect(conn, hubs, args.url)
            if args.once:
                break
            time.sleep(args.interval * 60)
    except KeyboardInterrupt:
        print("Stopped.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
