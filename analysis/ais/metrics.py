"""Metrics: every table and number the dashboard, Excel workbook, SQL cross-checks and report need."""
import numpy as np
import pandas as pd

from .config import FRESH_MINUTES, DARK_WINDOW_MINUTES

STATUS_COLS = ["at_anchor", "at_berth", "idle", "moving", "other"]


def tercile_levels(series):
    """Relative traffic level: lowest third green, middle third yellow, top third red. Ties get the same level."""
    s = pd.to_numeric(series, errors="coerce")
    if s.notna().sum() == 0:
        return pd.Series("green", index=series.index)
    if s.nunique() == 1:
        return pd.Series("yellow" if float(s.iloc[0]) > 0 else "green", index=series.index)
    pct = s.rank(pct=True, method="average")
    return pd.Series(np.where(pct <= 1 / 3, "green", np.where(pct <= 2 / 3, "yellow", "red")), index=series.index)


def _pct(num, den, nd=1):
    return round(100.0 * num / den, nd) if den else float("nan")


SEGMENTS = {"cargo": "Cargo & tanker", "tanker": "Cargo & tanker", "passenger": "Passenger", "tug": "Tug",
            "pleasure": "Pleasure & fishing", "fishing": "Pleasure & fishing"}


def segment_of(vessel_type):
    return SEGMENTS.get(vessel_type, "Other & unknown")


def segment_table(df):
    """Who is in the data? Ship counts and behaviour by broad segment, so a mixed fleet cannot hide inside one average."""
    d = df.copy()
    d["segment"] = d["vessel_type"].map(segment_of)
    g = d.groupby("segment")
    t = pd.DataFrame({"ships": g.size()})
    for key, label in (("moving", "pct_under_way"), ("idle", "pct_idle"), ("at_berth", "pct_at_berth"), ("at_anchor", "pct_at_anchor")):
        t[label] = g["status_group"].apply(lambda s, k=key: round(100.0 * (s == k).mean(), 1))
    near = d[d["hub"].notna() & (d["status_group"] == "at_anchor")].groupby("segment").size()
    t["waiting_near_hubs"] = near.reindex(t.index).fillna(0).astype(int)
    sp = d[(d["status_group"] == "moving") & d["speed"].notna()].groupby("segment")["speed"].mean().round(1)
    t["avg_speed_under_way_kn"] = sp
    t["share_pct"] = (100.0 * t["ships"] / t["ships"].sum()).round(1)
    return t.sort_values("ships", ascending=False).reset_index()


def definition_sensitivity(ht):
    """Do the busiest hubs change if 'waiting' also counts idle ships? Strict = anchored at sea; broad = anchored + idle."""
    t = ht[ht["ships_in_radius"] > 0]
    if len(t) < 5:
        return None
    strict_top = set(t.sort_values("at_anchor", ascending=False).head(5)["hub"])
    broad_top = set(t.sort_values("waiting_broad", ascending=False).head(5)["hub"])
    rho = float(t["at_anchor"].rank().corr(t["waiting_broad"].rank()))
    return {"top5_overlap": len(strict_top & broad_top), "rank_correlation": round(rho, 2),
            "strict_top5": sorted(strict_top), "broad_top5": sorted(broad_top)}


def hub_table(df, hubs):
    near = df[df["hub"].notna()]
    ct = pd.crosstab(near["hub"], near["status_group"]).reindex(columns=STATUS_COLS, fill_value=0)
    t = hubs[["name", "zone", "lat", "lng", "radius_km"]].rename(columns={"name": "hub"}).set_index("hub").join(ct)
    for c in STATUS_COLS:
        t[c] = t[c].fillna(0).astype(int)
    t["ships_in_radius"] = t[STATUS_COLS].sum(axis=1)
    t["waiting_broad"] = t["at_anchor"] + t["idle"]
    spd = near[(near["status_group"] == "moving") & near["speed"].notna()].groupby("hub")["speed"].mean().round(1)
    t["avg_speed_moving_kn"] = spd
    t["pct_at_anchor"] = (100.0 * t["at_anchor"] / t["ships_in_radius"]).where(t["ships_in_radius"] > 0).round(1)
    t["level_waiting"] = tercile_levels(t["at_anchor"])
    t["level_traffic"] = tercile_levels(t["ships_in_radius"])
    t["level_waiting_broad"] = tercile_levels(t["waiting_broad"])
    t["waiting_rank"] = t["at_anchor"].rank(ascending=False, method="min").astype(int)
    cols = ["zone", "ships_in_radius", "at_anchor", "at_berth", "idle", "moving", "other", "waiting_broad", "avg_speed_moving_kn",
            "pct_at_anchor", "waiting_rank", "level_waiting", "level_waiting_broad", "level_traffic", "radius_km", "lat", "lng"]
    return t[cols].reset_index().sort_values(["at_anchor", "ships_in_radius"], ascending=False).reset_index(drop=True)


def zone_table(ht):
    z = ht.groupby("zone").agg(hubs=("hub", "count"), ships_in_hub_radius=("ships_in_radius", "sum"),
                               at_anchor=("at_anchor", "sum"), idle=("idle", "sum"), moving=("moving", "sum")).reset_index()
    z["pct_at_anchor"] = (100.0 * z["at_anchor"] / z["ships_in_hub_radius"]).where(z["ships_in_hub_radius"] > 0).round(1)
    return z.sort_values("at_anchor", ascending=False).reset_index(drop=True)


def speed_zone(df):
    mv = df[(df["status_group"] == "moving") & df["speed"].notna()].copy()
    mv["location"] = np.where(mv["hub"].notna(), "near a hub", "open water")
    overall = mv.groupby("location")["speed"].agg(["count", "mean"]).round(2)
    top = mv["vessel_type"].value_counts().head(6).index
    t = mv[mv["vessel_type"].isin(top)].groupby(["vessel_type", "location"])["speed"].agg(["count", "mean"]).reset_index()
    t = t[t["count"] >= 5].rename(columns={"count": "moving_ships", "mean": "avg_speed_kn"})
    t["avg_speed_kn"] = t["avg_speed_kn"].round(2)
    return t, overall


def fleet_by_type(df):
    g = df.groupby("vessel_type")
    t = pd.DataFrame({
        "ships": g.size(),
        "moving": g["status_group"].apply(lambda s: int((s == "moving").sum())),
        "at_anchor": g["status_group"].apply(lambda s: int((s == "at_anchor").sum())),
        "idle": g["status_group"].apply(lambda s: int((s == "idle").sum())),
        "dark": g["is_dark_flagged"].sum(),
    })
    t["share_pct"] = (100.0 * t["ships"] / t["ships"].sum()).round(1)
    t["pct_moving"] = (100.0 * t["moving"] / t["ships"]).round(1)
    t["pct_dark"] = (100.0 * t["dark"] / t["ships"]).round(2)
    mv = df[(df["status_group"] == "moving") & df["speed"].notna()].groupby("vessel_type")["speed"].mean().round(1)
    t["avg_speed_moving_kn"] = mv
    return t.sort_values("ships", ascending=False).reset_index()


def flags_top(df, n=15):
    t = df["flag"].value_counts().head(n).rename_axis("flag").reset_index(name="ships")
    t["share_pct"] = (100.0 * t["ships"] / len(df)).round(1)
    return t


def dark_tables(win):
    """Silent-ship flags by location and vessel type. win = ships heard from within DARK_WINDOW_MINUTES (a fair, equal-age comparison)."""
    g = win.groupby("is_edge").agg(ships=("mmsi", "size"), dark=("is_dark_flagged", "sum")).reset_index()
    g["location"] = g["is_edge"].map({1: "near edge of tracked area", 0: "interior"})
    g["dark_pct"] = (100.0 * g["dark"] / g["ships"]).round(2)
    bt = win.groupby("vessel_type").agg(ships=("mmsi", "size"), dark=("is_dark_flagged", "sum")).reset_index()
    bt = bt[bt["ships"] >= 20].copy()
    bt["dark_pct"] = (100.0 * bt["dark"] / bt["ships"]).round(2)
    return g[["location", "ships", "dark", "dark_pct"]], bt.sort_values("dark_pct", ascending=False)


def dark_profile(win, current):
    """What were the flagged ships doing when they went quiet, and how do they differ from current ships?"""
    flagged = win[win["is_dark_flagged"] == 1]
    if flagged.empty:
        return None
    stationary = flagged["status_group"].isin(["at_berth", "at_anchor", "idle"])
    return {
        "flagged": int(len(flagged)),
        "pct_stationary": round(100.0 * stationary.mean(), 1),
        "pct_under_way": round(100.0 * (flagged["status_group"] == "moving").mean(), 1),
        "pct_in_hub": round(100.0 * flagged["hub"].notna().mean(), 1),
        "median_silent_min": round(float(flagged["minutes_since_update"].median())),
        "pct_type_unknown_flagged": round(100.0 * (flagged["vessel_type"] == "unknown").mean(), 1),
        "pct_type_unknown_current": round(100.0 * (current["vessel_type"] == "unknown").mean(), 1),
    }


def routes_table(df, n=15):
    r = df[df["departure_port"].notna() & ~df["dest_quality"].isin(["missing", "junk"])].copy()
    if r.empty:
        return pd.DataFrame(columns=["departure_port", "destination", "ships", "avg_speed_kn"])
    r["destination"] = r["dest_resolved"].fillna(r["dest_clean"])
    # the same port arrives as 'AMSTERDAM' (port database) and 'Amsterdam' (our hub list): unify before counting routes
    tidy = lambda v: v.title() if isinstance(v, str) and v.isupper() else v   # noqa: E731
    r["departure_port"] = r["departure_port"].map(tidy)
    r["destination"] = r["destination"].map(tidy)
    t = r.groupby(["departure_port", "destination"]).agg(ships=("mmsi", "size"), avg_speed_kn=("speed", "mean")).reset_index()
    t["avg_speed_kn"] = t["avg_speed_kn"].round(1)
    return t.sort_values(["ships", "departure_port"], ascending=[False, True]).head(n).reset_index(drop=True)


def completeness(df):
    n = len(df)
    items = [
        ("Ship name", df["name"].notna()),
        ("Flag state", df["flag"] != "Unknown"),
        ("Vessel type", df["vessel_type"] != "unknown"),
        ("IMO number", df["imo"].notna()),
        ("IMO passes checksum", df["imo_valid"] == 1),
        ("Call sign", df["call_sign"].notna()),
        ("Length", df["length_m"].notna()),
        ("Speed", df["speed"].notna()),
        ("Destination usable (not blank/placeholder)", ~df["dest_quality"].isin(["missing", "junk"])),
        ("Destination resolved to a port", df["dest_resolved"].notna()),
    ]
    return pd.DataFrame({"field": [i[0] for i in items], "pct_complete": [_pct(int(i[1].sum()), n) for i in items],
                         "ships": [int(i[1].sum()) for i in items]})


def compute_all(df, hubs, log, stamp, df_dark=None):
    """df = current ships (traffic metrics). df_dark = all ships incl. silent ones (dark-fleet metrics)."""
    dd = df_dark if df_dark is not None else df
    n = len(df)
    ht = hub_table(df, hubs)
    sz, sz_overall = speed_zone(df)
    win = dd[dd["minutes_since_update"].fillna(0) <= DARK_WINDOW_MINUTES]
    dark_edge, dark_type = dark_tables(win)
    comp = completeness(df)
    dq = df["dest_quality"].value_counts().rename_axis("category").reset_index(name="ships")
    dq["share_pct"] = (100.0 * dq["ships"] / n).round(1)
    status = df["status_group"].value_counts().rename_axis("status").reset_index(name="ships")
    status["share_pct"] = (100.0 * status["ships"] / n).round(1)
    size = df["size_class"].value_counts().rename_axis("size_class").reset_index(name="ships")
    mv = df[(df["status_group"] == "moving") & df["speed"].notna()]
    big = ht[ht["ships_in_radius"] >= 10]
    kpis = {
        "snapshot_utc": stamp.strftime("%Y-%m-%d %H:%M"),
        "total_ships": n,
        "pct_moving": _pct((df["status_group"] == "moving").sum(), n),
        "pct_idle": _pct((df["status_group"] == "idle").sum(), n),
        "pct_at_anchor": _pct((df["status_group"] == "at_anchor").sum(), n),
        "pct_at_berth": _pct((df["status_group"] == "at_berth").sum(), n),
        "ships_near_hubs": int(df["hub"].notna().sum()),
        "waiting_near_hubs": int(((df["status_group"] == "at_anchor") & df["hub"].notna()).sum()),
        "dark_flagged": int(win["is_dark_flagged"].sum()),
        "pct_dark": _pct(win["is_dark_flagged"].sum(), len(win), 2),
        "ships_in_dark_window": int(len(win)),
        "total_ships_incl_silent": int(len(dd)),
        "pct_type_unknown": _pct((df["vessel_type"] == "unknown").sum(), n),
        "pct_with_imo": _pct(df["imo"].notna().sum(), n),
        "pct_valid_imo": _pct((df["imo_valid"] == 1).sum(), n),
        "pct_with_length": _pct(df["length_m"].notna().sum(), n),
        "pct_dest_usable": _pct((~df["dest_quality"].isin(["missing", "junk"])).sum(), n),
        "pct_dest_app_matched": _pct(df["destination_port"].notna().sum(), n),
        "pct_dest_resolved": _pct(df["dest_resolved"].notna().sum(), n),
        "ships_with_departure": int(df["departure_port"].notna().sum()),
        "median_speed_moving_kn": round(float(mv["speed"].median()), 1) if len(mv) else float("nan"),
        "mean_speed_moving_kn": round(float(mv["speed"].mean()), 1) if len(mv) else float("nan"),
        "busiest_hub": ht.sort_values("ships_in_radius", ascending=False).iloc[0]["hub"] if len(ht) else None,
        "most_waiting_hub": ht.iloc[0]["hub"] if len(ht) else None,
        "highest_anchor_share_hub": big.sort_values("pct_at_anchor", ascending=False).iloc[0]["hub"] if len(big) else None,
        "stationary_but_moving": int(df["stationary_but_moving"].sum()),
        "moving_but_anchored": int(df["moving_but_anchored"].sum()),
    }
    return {
        "kpis": kpis, "hub_table": ht, "zone_table": zone_table(ht), "speed_zone": sz, "speed_overall": sz_overall,
        "fleet_by_type": fleet_by_type(df), "flags_top": flags_top(df), "dark_edge": dark_edge, "dark_type": dark_type,
        "routes": routes_table(df), "completeness": comp, "dest_quality": dq, "status": status, "size_class": size,
        "cleaning_log": log, "segments": segment_table(df), "sensitivity": definition_sensitivity(ht), "dark_profile": dark_profile(win, df),
    }
