"""Paths, constants and shared settings for the Maritime Globe analytics pipeline."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent          # .../analysis
CONFIG_DIR = ROOT / "config"
SQL_DIR = ROOT / "sql"
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
OUT_DIR = ROOT / "outputs"
OUT_DATA = OUT_DIR / "data"
CHART_DIR = OUT_DIR / "charts"
SQL_OUT = OUT_DIR / "sql"
TIME_OUT = OUT_DIR / "time"
HISTORY_DB = DATA_DIR / "history.db"
ANALYSIS_DB = DATA_DIR / "analysis.db"
HUBS_CSV = CONFIG_DIR / "hubs.csv"
ASSUMPTIONS_CSV = CONFIG_DIR / "assumptions.csv"

API_URL = "http://127.0.0.1:8000/ships"

# Must match the AIS subscription box in backend/main.py: lat_min, lng_min, lat_max, lng_max
TRACKED_BOX = (49.0, -2.0, 54.0, 9.0)
EDGE_MARGIN_DEG = 0.5            # ships this close to the box edge are "near the edge"
REGION_NAME = "North Sea & English Channel"

STATIONARY_KN = 0.5              # below this speed a ship is treated as not moving
MAX_PLAUSIBLE_SPEED_KN = 40.0    # above this a merchant-ship speed is treated as an error
FRESH_MINUTES = 15               # collector: only count ships heard from this recently
DARK_WINDOW_MINUTES = 60         # silent-ship comparison uses ships heard within this window (equal-age, fair)

SIZE_BINS = [0, 100, 200, 300, 10_000]
SIZE_LABELS = ["small (<100 m)", "medium (100-200 m)", "large (200-300 m)", "very large (>300 m)"]
UNKNOWN_SIZE = "unknown size"

LEVEL_COLORS = {"green": "#2e9e5b", "yellow": "#e0b020", "red": "#d64541"}
STATUS_COLORS = {"moving": "#1d8f87", "at_anchor": "#e07b3f", "at_berth": "#4a90d9", "idle": "#9b7fd1", "other": "#8895a7"}


def ensure_dirs():
    for d in (RAW_DIR, OUT_DATA, CHART_DIR, SQL_OUT, TIME_OUT):
        d.mkdir(parents=True, exist_ok=True)
