"""Geography helpers: distances, hub assignment and the 'near the edge' test."""
import numpy as np
import pandas as pd

from .config import TRACKED_BOX, EDGE_MARGIN_DEG, REGION_NAME


def haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance in km. Works on scalars or broadcastable numpy arrays."""
    r = 6371.0088
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = p2 - p1
    dlam = np.radians(lon2) - np.radians(lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dlam / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


def load_hubs(path):
    hubs = pd.read_csv(path)
    hubs["aliases"] = hubs["aliases"].fillna("")
    return hubs


def assign_hubs(df, hubs):
    """Tag each ship with the nearest hub whose radius it is inside (else None = open water)."""
    out = df.copy()
    if len(out) == 0:
        for c in ("hub", "zone", "region"):
            out[c] = pd.Series(dtype="object")
        out["dist_to_hub_km"] = pd.Series(dtype="float64")
        return out
    lat = out["lat"].to_numpy(dtype=float)[:, None]
    lng = out["lng"].to_numpy(dtype=float)[:, None]
    dist = haversine_km(lat, lng, hubs["lat"].to_numpy(float)[None, :], hubs["lng"].to_numpy(float)[None, :])
    radius = hubs["radius_km"].to_numpy(float)[None, :]
    masked = np.where(dist <= radius, dist, np.inf)
    idx = masked.argmin(axis=1)
    best = masked[np.arange(len(out)), idx]
    inside = np.isfinite(best)
    names = hubs["name"].to_numpy(dtype=object)[idx]
    zones = hubs["zone"].to_numpy(dtype=object)[idx]
    regions = hubs["region"].to_numpy(dtype=object)[idx]
    out["hub"] = pd.Series(np.where(inside, names, None), index=out.index, dtype="object")
    out["zone"] = pd.Series(np.where(inside, zones, None), index=out.index, dtype="object")
    out["region"] = pd.Series(np.where(inside, regions, REGION_NAME), index=out.index, dtype="object")
    out["dist_to_hub_km"] = pd.Series(np.where(inside, best, np.nan), index=out.index, dtype="float64")
    return out


def is_edge(lat, lng):
    """True for positions within EDGE_MARGIN_DEG of the edge of the tracked box."""
    lat_min, lng_min, lat_max, lng_max = TRACKED_BOX
    m = EDGE_MARGIN_DEG
    return (lat < lat_min + m) | (lat > lat_max - m) | (lng < lng_min + m) | (lng > lng_max - m)
