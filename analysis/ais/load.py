"""Getting the data in: live from the backend, or from a saved CSV snapshot."""
import datetime as dt

import pandas as pd
import requests

from .config import API_URL, RAW_DIR, DATA_DIR

EXPECTED_COLS = [
    "mmsi", "name", "flag", "vessel_type", "imo", "call_sign", "lat", "lng", "status", "speed", "heading",
    "minutes_since_update", "is_dark_flagged", "destination", "eta", "destination_port", "departure_port",
    "departure_time", "length_m", "beam_m",
]


def _port_name(value):
    if isinstance(value, dict):
        return value.get("name")
    return value if isinstance(value, str) else None


def _ensure_cols(df):
    for c in EXPECTED_COLS:
        if c not in df.columns:
            df[c] = pd.NA
    return df


def from_records(records):
    """Turn the backend's /ships JSON (list of dicts) into a flat DataFrame."""
    df = pd.DataFrame(records)
    for col in ("destination_port", "departure_port"):
        if col in df.columns:
            df[col] = df[col].map(_port_name)
    return _ensure_cols(df)


def fetch_snapshot(url=API_URL, save=True):
    """Download the current fleet from the running backend. Returns (df, timestamp, saved_path)."""
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    df = from_records(resp.json())
    stamp = dt.datetime.now(dt.timezone.utc)
    path = None
    if save:
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        path = RAW_DIR / f"ships_{stamp:%Y%m%d_%H%M}.csv"
        df.to_csv(path, index=False)
    return df, stamp, path


def latest_csv():
    files = list(RAW_DIR.glob("ships_*.csv")) + list(DATA_DIR.glob("ships_snapshot_*.csv"))
    return max(files, key=lambda p: p.stat().st_mtime) if files else None


def read_csv(path):
    df = pd.read_csv(path)
    stamp = dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc)
    return _ensure_cols(df), stamp
