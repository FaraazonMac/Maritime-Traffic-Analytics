"""Data cleaning. Every rule is explicit and counted, so the audit trail can go straight into the write-up."""
import re

import numpy as np
import pandas as pd

from .config import (TRACKED_BOX, STATIONARY_KN, MAX_PLAUSIBLE_SPEED_KN, SIZE_BINS, SIZE_LABELS, UNKNOWN_SIZE, FRESH_MINUTES)
from . import geo

JUNK = {"", "N/A", "NA", "?", "??", "???", "TBA", "TBN", "TBC", "UNKNOWN", "AT SEA", "FOR ORDERS", "TO ORDER",
        "ORDERS", "FOR ORDER", "ORDER", "NONE", "NIL", "-", "--", "0", ".", "NOT SET"}
NW_EU = {"NL", "BE", "DE", "FR", "GB", "DK", "NO", "SE", "PL", "ES", "PT", "IE", "IT"}
STATUS_GROUP = {"moving": "moving", "anchored-sea": "at_anchor", "anchored-port": "at_berth"}
NUMERIC = ["mmsi", "lat", "lng", "speed", "heading", "minutes_since_update", "length_m", "beam_m", "imo"]

CLEAN_COLUMNS = [
    "mmsi", "name", "flag", "vessel_type", "imo", "imo_valid", "call_sign", "lat", "lng", "status", "status_group",
    "speed", "heading", "minutes_since_update", "is_stale", "is_dark_flagged", "destination", "dest_clean", "dest_quality",
    "dest_hub", "dest_resolved", "destination_port", "eta", "departure_port", "departure_time", "length_m",
    "beam_m", "size_class", "hub", "zone", "region", "dist_to_hub_km", "is_edge", "stationary_but_moving",
    "moving_but_anchored",
]


# ---------------------------------------------------------------- small helpers
def imo_checksum_ok(value):
    """IMO numbers are 7 digits; the last digit is a checksum of the first six (weights 7..2)."""
    try:
        s = str(int(value))
    except (TypeError, ValueError):
        return False
    if len(s) != 7:
        return False
    total = sum(int(ch) * w for ch, w in zip(s[:6], range(7, 1, -1)))
    return total % 10 == int(s[6])


def _clean_speed(series):
    s = pd.to_numeric(series, errors="coerce")
    s = s.mask(s >= 102.3)                       # AIS "speed not available" is 102.3
    s = s.mask(s < 0)
    s = s.mask(s > MAX_PLAUSIBLE_SPEED_KN)
    return s


def _status_groups(status, speed):
    """moving = under way at 0.5 kn or more; idle = status says under way but the ship is stationary (status is entered by hand and often not updated)."""
    g = status.map(STATUS_GROUP).fillna("other")
    return g.mask((g == "moving") & (speed < STATIONARY_KN), "idle")


def _size_class(length):
    length = pd.to_numeric(length, errors="coerce")
    length = length.mask((length <= 0) | (length > 500))
    cls = pd.cut(length, bins=SIZE_BINS, labels=SIZE_LABELS, right=False)
    return cls.astype(object).where(cls.notna(), UNKNOWN_SIZE)


def _dark_to_int(series):
    return series.map(lambda v: 1 if str(v).strip().lower() in ("true", "1", "1.0") else 0).astype(int)


def _text_or_none(series):
    s = series.astype("object").where(series.notna(), None)
    return s.map(lambda v: (str(v).strip() or None) if v is not None else None)


# ---------------------------------------------------------------- destination text
def classify_destination(raw, locodes, aliases):
    """Return (cleaned text, quality category, hub name or None).

    Categories: missing, junk, locode (a known hub's UN/LOCODE), hub_name, locode_other, other_text.
    Captains type destinations by hand, so we see 'NL RTM', 'NLAMS01090DOCKX00018', 'FOR ORDERS', 'NLVLI>DEBRE'...
    """
    if raw is None or (not isinstance(raw, str) and pd.isna(raw)):
        return None, "missing", None
    s = re.sub(r"\s+", " ", str(raw).upper()).strip()
    if not s:
        return None, "missing", None
    parts = [p.strip() for p in re.split(r">|<|=>|->", s) if p.strip()]
    if parts:
        s = parts[-1]                                  # 'A > B' means going to B
    if s in JUNK or not re.search(r"[A-Z]", s):
        return s, "junk", None
    compact = re.sub(r"[^A-Z0-9]", "", s)
    # two codes run together (DEBRVDEBRE): the destination is the second one
    if len(compact) == 10 and compact.isalpha() and compact[:2] in NW_EU and compact[5:7] in NW_EU:
        tail = compact[5:]
        hub = locodes.get(tail)
        return s, ("locode" if hub else "locode_other"), hub
    nospace = s.replace(" ", "")
    if nospace[:5] in locodes and (len(nospace) == 5 or not nospace[5].isalpha()):
        return s, "locode", locodes[nospace[:5]]
    for alias, hub in aliases:
        if alias in s:
            return s, "hub_name", hub
    if re.fullmatch(r"[A-Z]{2} ?[A-Z]{3}", s):
        return s, "locode_other", None
    return s, "other_text", None


# ---------------------------------------------------------------- full cleaning with audit log
def clean(raw, hubs):
    """Return (clean_df, log_df). log_df lists every rule, how many rows it touched and what was done."""
    log = []

    def note(rule, n, action):
        log.append({"rule": rule, "rows_affected": int(n), "action": action})

    df = raw.copy()
    note("Raw rows received", len(df), "-")
    for c in NUMERIC:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    bad = df["mmsi"].isna()
    note("Missing MMSI (cannot identify the ship)", bad.sum(), "dropped")
    df = df[~bad]

    df = df.sort_values("minutes_since_update", na_position="last", kind="mergesort")
    dup = df.duplicated("mmsi", keep="first")
    note("Duplicate MMSI (same ship twice)", dup.sum(), "dropped, kept the most recent report")
    df = df[~dup].copy()

    lat_min, lng_min, lat_max, lng_max = TRACKED_BOX
    no_pos = df["lat"].isna() | df["lng"].isna() | ~df["lat"].between(-90, 90) | ~df["lng"].between(-180, 180)
    note("Missing or impossible position", no_pos.sum(), "dropped")
    df = df[~no_pos]
    outside = ~(df["lat"].between(lat_min, lat_max) & df["lng"].between(lng_min, lng_max))
    note("Position outside the tracked box", outside.sum(), "dropped")
    df = df[~outside].copy()

    sp = pd.to_numeric(df["speed"], errors="coerce")
    note("Speed = 102.3 kn (AIS 'not available' code)", (sp >= 102.3).sum(), "set to missing")
    note("Negative speed", ((sp < 0) & (sp < 102.3)).sum(), "set to missing")
    note(f"Implausible speed (> {MAX_PLAUSIBLE_SPEED_KN:.0f} kn)", ((sp > MAX_PLAUSIBLE_SPEED_KN) & (sp < 102.3)).sum(), "set to missing")
    df["speed"] = _clean_speed(df["speed"])

    df["heading"] = df["heading"].mask(df["heading"] >= 360)

    df["vessel_type"] = df["vessel_type"].astype("object").where(df["vessel_type"].notna(), "unknown")
    df["vessel_type"] = df["vessel_type"].astype(str).str.strip().str.lower().replace({"": "unknown", "nan": "unknown", "none": "unknown"})
    note("Vessel type missing", (df["vessel_type"] == "unknown").sum(), "labelled 'unknown' (kept)")

    nm = _text_or_none(df["name"])
    unnamed = nm.isna() | (nm.fillna("").str.upper() == "UNKNOWN")
    note("Ship name missing or 'Unknown'", unnamed.sum(), "name set to missing (kept)")
    df["name"] = nm.where(~unnamed, None)

    fl = _text_or_none(df["flag"])
    note("Flag state missing (MMSI country code not recognised)", fl.isna().sum(), "labelled 'Unknown' (kept)")
    df["flag"] = fl.where(fl.notna(), "Unknown")

    imo_bad = df["imo"].notna() & (df["imo"] <= 0)
    df["imo"] = df["imo"].mask(df["imo"] <= 0)
    note("IMO = 0 (placeholder)", imo_bad.sum(), "set to missing")
    df["imo"] = df["imo"].round().astype("Int64")
    df["imo_valid"] = df["imo"].map(imo_checksum_ok).astype(int)
    note("IMO present but fails the checksum", ((df["imo"].notna()) & (df["imo_valid"] == 0)).sum(), "kept, flagged invalid")

    df["status"] = df["status"].astype(str).str.strip().str.lower()
    df["status_group"] = _status_groups(df["status"], df["speed"])
    df["stationary_but_moving"] = (df["status_group"] == "idle").astype(int)
    df["moving_but_anchored"] = ((df["status_group"].isin(["at_anchor", "at_berth"])) & (df["speed"] > 3)).astype(int)
    note("Status says under way but speed is below 0.5 kn", df["stationary_but_moving"].sum(), "kept; reclassified as 'idle' (stationary)")
    note("Reported anchored/moored but speed above 3 kn", df["moving_but_anchored"].sum(), "kept, flagged")

    long_bad = df["length_m"].notna() & ((df["length_m"] <= 0) | (df["length_m"] > 500))
    note("Implausible length (<= 0 or > 500 m)", long_bad.sum(), "set to missing")
    df["length_m"] = df["length_m"].mask((df["length_m"] <= 0) | (df["length_m"] > 500))
    df["size_class"] = _size_class(df["length_m"])

    locodes = dict(zip(hubs["locode"], hubs["name"]))
    aliases = sorted(
        [(a.strip().upper(), h) for h, al in zip(hubs["name"], hubs["aliases"]) for a in str(al).split("|") if a.strip()],
        key=lambda t: -len(t[0]),
    )
    res = [classify_destination(v, locodes, aliases) for v in df["destination"]]
    df["dest_clean"] = [r[0] for r in res]
    df["dest_quality"] = [r[1] for r in res]
    df["dest_hub"] = pd.Series([r[2] for r in res], index=df.index, dtype="object")
    for q, label in (("missing", "Destination missing"), ("junk", "Destination is a placeholder (e.g. 'FOR ORDERS')"),
                     ("locode", "Destination is a UN/LOCODE of a known hub (e.g. 'NL RTM')"),
                     ("hub_name", "Destination names a known hub")):
        note(label, (df["dest_quality"] == q).sum(), "classified" if q in ("missing", "junk") else "classified and mapped to the hub")

    for c in ("destination_port", "departure_port", "departure_time", "eta", "call_sign", "destination"):
        df[c] = _text_or_none(df[c])
    df["dest_resolved"] = df["dest_hub"].where(df["dest_hub"].notna(), df["destination_port"])
    df["dest_resolved"] = df["dest_resolved"].astype("object")

    df["is_dark_flagged"] = _dark_to_int(df["is_dark_flagged"])
    df["is_stale"] = (df["minutes_since_update"] > FRESH_MINUTES).astype(int)
    note(f"Silent for more than {FRESH_MINUTES:g} minutes (stale)", df["is_stale"].sum(),
         "kept; excluded from traffic metrics, used only for the dark-fleet analysis")

    df = geo.assign_hubs(df, hubs)
    df["is_edge"] = geo.is_edge(df["lat"], df["lng"]).astype(int)

    note("Clean rows kept", len(df), "-")
    for c in CLEAN_COLUMNS:
        if c not in df.columns:
            df[c] = None
    return df[CLEAN_COLUMNS].reset_index(drop=True), pd.DataFrame(log)


# ---------------------------------------------------------------- light cleaning for the collector
def light_clean(raw):
    """Minimal, fast cleaning used by the history collector (no audit log)."""
    df = raw.copy()
    for c in NUMERIC:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df[df["mmsi"].notna()].sort_values("minutes_since_update", na_position="last", kind="mergesort").drop_duplicates("mmsi")
    lat_min, lng_min, lat_max, lng_max = TRACKED_BOX
    df = df[df["lat"].between(lat_min, lat_max) & df["lng"].between(lng_min, lng_max)].copy()
    df["speed"] = _clean_speed(df["speed"])
    vt = df["vessel_type"].astype("object").where(df["vessel_type"].notna(), "unknown")
    df["vessel_type"] = vt.astype(str).str.strip().str.lower().replace({"": "unknown", "nan": "unknown", "none": "unknown"})
    df["status"] = df["status"].astype(str).str.strip().str.lower()
    df["status_group"] = _status_groups(df["status"], df["speed"])
    df["size_class"] = _size_class(df["length_m"])
    df["is_dark_flagged"] = _dark_to_int(df["is_dark_flagged"])
    return df.reset_index(drop=True)
