"""v2: time-based analysis on the history collected by collector.py.

Everything is gated on how much data exists, so the pipeline never reports a weekly or monthly pattern it cannot support.
"""
import sqlite3

import numpy as np
import pandas as pd

from .config import HISTORY_DB
from .estimates import lookup, SIZE_ORDER
from .metrics import tercile_levels

# minimum number of usable days (>= 50% of expected polls) before each view is shown
MIN_DAYS = {"daily_levels": 3, "hour_profile": 3, "speed_by_level": 7, "excess": 7, "hub_levels": 6, "weekday": 14,
            "weekly": 14, "monthly": 28, "weather": 14}
LOCAL_TZ = "Europe/Amsterdam"


def load_history(db_path=HISTORY_DB):
    if not db_path.exists():
        return None
    conn = sqlite3.connect(db_path)
    try:
        runs = pd.read_sql_query("SELECT * FROM runs WHERE ok = 1", conn)
        hub = pd.read_sql_query("SELECT * FROM hub_summary", conn)
        hts = pd.read_sql_query("SELECT * FROM hub_size_summary", conn)
        tps = pd.read_sql_query("SELECT * FROM type_summary", conn)
        allruns = pd.read_sql_query("SELECT run_ts, ok FROM runs", conn)
    finally:
        conn.close()
    if runs.empty:
        return None
    return {"runs": runs, "hub": hub, "hts": hts, "types": tps, "all_runs": allruns}


def _local(ts):
    t = pd.to_datetime(ts, utc=True)
    try:
        return t.dt.tz_convert(LOCAL_TZ)
    except Exception:  # noqa: BLE001
        return t


def analyse(history, assump=None):
    out = {"messages": []}
    runs, hub, hts = history["runs"].copy(), history["hub"].copy(), history["hts"].copy()
    runs["ts"] = _local(runs["run_ts"])
    hub["ts"] = _local(hub["run_ts"])
    hub["avg_speed_moving"] = pd.to_numeric(hub["avg_speed_moving"], errors="coerce")

    per_run = hub.groupby("run_ts").agg(near_hubs=("ships_in_radius", "sum"), waiting=("at_anchor", "sum"), moving_near=("moving", "sum"))
    hub["w_speed"] = hub["avg_speed_moving"] * hub["moving"]
    sp = hub.dropna(subset=["avg_speed_moving"]).groupby("run_ts").agg(w=("w_speed", "sum"), n=("moving", "sum"))
    speed_run = (sp["w"] / sp["n"]).where(sp["n"] > 0).rename("speed_near_hubs")
    rd = runs.merge(per_run, on="run_ts", how="left").merge(speed_run, on="run_ts", how="left")
    rd["date"] = rd["ts"].dt.date
    rd["hour"] = rd["ts"].dt.hour
    rd["weekday"] = rd["ts"].dt.dayofweek

    ts_sorted = pd.to_datetime(runs["run_ts"], utc=True).sort_values()
    interval = float(ts_sorted.diff().dt.total_seconds().div(60).median()) if len(ts_sorted) > 1 else 30.0
    interval = interval if interval and interval > 0 else 30.0
    expected = 1440.0 / interval

    daily = rd.groupby("date").agg(polls=("run_ts", "size"), ships=("fresh_ships", "mean"), near_hubs=("near_hubs", "mean"),
                                   waiting=("waiting", "mean"), speed_near_hubs=("speed_near_hubs", "mean")).reset_index()
    daily["coverage"] = (daily["polls"] / expected).clip(upper=1.0).round(2)
    daily["usable"] = daily["coverage"] >= 0.5
    n_use = int(daily["usable"].sum())
    out["status"] = {
        "polls": int(len(runs)), "failed_polls": int((history["all_runs"]["ok"] == 0).sum()), "days_seen": int(len(daily)),
        "usable_days": n_use, "interval_min": round(interval, 1), "first": str(ts_sorted.iloc[0])[:16], "last": str(ts_sorted.iloc[-1])[:16],
        "mean_coverage_pct": round(100 * float(daily["coverage"].mean()), 1),
    }

    def gate(name):
        if n_use >= MIN_DAYS[name]:
            return True
        out["messages"].append(f"{name.replace('_', ' ').capitalize()}: needs {MIN_DAYS[name]} usable days, have {n_use}. Keep the collector running.")
        return False

    tps = history.get("types")
    if tps is not None and len(tps) and n_use >= MIN_DAYS["hour_profile"]:
        g = tps.groupby("vessel_type").agg(avg_ships=("ships", "mean"), avg_waiting_near_hubs=("near_hub_at_anchor", "mean")).reset_index()
        g["share_of_fleet_pct"] = (100 * g["avg_ships"] / g["avg_ships"].sum()).round(1)
        g["share_of_queue_pct"] = (100 * g["avg_waiting_near_hubs"] / g["avg_waiting_near_hubs"].sum()).round(1)
        g["queue_vs_fleet"] = (g["share_of_queue_pct"] / g["share_of_fleet_pct"]).round(2)
        out["type_queue"] = g.sort_values("share_of_queue_pct", ascending=False).reset_index(drop=True)
    daily["traffic_level"] = None
    daily["congestion_level"] = None
    if gate("daily_levels"):
        u = daily["usable"]
        daily.loc[u, "traffic_level"] = tercile_levels(daily.loc[u, "ships"]).values
        daily.loc[u, "congestion_level"] = tercile_levels(daily.loc[u, "waiting"]).values
    out["daily"] = daily

    if gate("hour_profile"):
        out["hour_profile"] = rd.groupby("hour").agg(ships=("fresh_ships", "mean"), near_hubs=("near_hubs", "mean"), waiting=("waiting", "mean")).round(1).reset_index()
    if gate("weekday"):
        wd = daily[daily["usable"]].copy()
        wd["weekday"] = pd.to_datetime(wd["date"]).dt.dayofweek
        out["weekday_profile"] = wd.groupby("weekday").agg(days=("date", "count"), ships=("ships", "mean"), waiting=("waiting", "mean")).round(1).reset_index()
        out["weekday_profile"]["day"] = out["weekday_profile"]["weekday"].map(dict(enumerate(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])))

    lv = daily.dropna(subset=["congestion_level"]).copy()
    if len(lv):
        lv["date_ts"] = pd.to_datetime(lv["date"])
        lv["week"] = lv["date_ts"].dt.strftime("%G-W%V")
        lv["month"] = lv["date_ts"].dt.strftime("%Y-%m")
        if gate("weekly"):
            out["weekly_levels"] = lv.groupby(["week", "congestion_level"]).size().unstack(fill_value=0).reindex(columns=["green", "yellow", "red"], fill_value=0).reset_index()
        if gate("monthly"):
            out["monthly_levels"] = lv.groupby(["month", "congestion_level"]).size().unstack(fill_value=0).reindex(columns=["green", "yellow", "red"], fill_value=0).reset_index()
        if gate("speed_by_level"):
            sp = lv.dropna(subset=["speed_near_hubs"]).groupby("congestion_level")["speed_near_hubs"].agg(["count", "mean"]).round(2).reset_index()
            out["speed_by_level"] = sp

    if gate("hub_levels"):
        hd = hub.copy()
        hd["date"] = hd["ts"].dt.date
        keep = set(daily.loc[daily["usable"], "date"])
        hd = hd[hd["date"].isin(keep)]
        hdaily = hd.groupby(["hub", "date"]).agg(ships=("ships_in_radius", "mean"), waiting=("at_anchor", "mean")).reset_index()
        hdaily["level"] = hdaily.groupby("hub")["waiting"].transform(lambda s: tercile_levels(s))
        out["hub_daily"] = hdaily
        out["hub_red_share"] = (hdaily.assign(red=(hdaily["level"] == "red")).groupby("hub")["red"].mean().mul(100).round(1)
                                .rename("pct_red_days").reset_index().sort_values("pct_red_days", ascending=False))

    if assump is not None and "congestion_level" in daily and gate("excess"):
        g = daily[daily["congestion_level"] == "green"]
        if len(g) >= 2:
            base = float(g["waiting"].mean())
            nongreen = daily[daily["congestion_level"].isin(["yellow", "red"])]
            excess_ship_days = float((nongreen["waiting"] - base).clip(lower=0).sum())
            sizes = hts.groupby("size_class")["at_anchor"].sum()
            mix = (sizes / sizes.sum()) if sizes.sum() > 0 else pd.Series({"unknown size": 1.0})
            price, co2, opex = (lookup(assump, "fuel_price_usd_per_t"), lookup(assump, "co2_t_per_t_fuel"), lookup(assump, "vessel_opex_usd_per_day"))
            rows = []
            for s in ("low", "central", "high"):
                fuel_ps = sum(share * lookup(assump, "fuel_at_anchor_t_per_day", sc if sc in SIZE_ORDER else "unknown size")[s] for sc, share in mix.items())
                rows.append({"scenario": s, "fuel_t": excess_ship_days * fuel_ps, "co2_t": excess_ship_days * fuel_ps * co2[s],
                             "cost_usd": excess_ship_days * (opex[s] + fuel_ps * price[s])})
            out["excess"] = {"baseline_waiting_ships": round(base, 1), "excess_ship_days": round(excess_ship_days, 1),
                             "days_counted": int(len(nongreen)), "table": pd.DataFrame(rows)}
        else:
            out["messages"].append("Excess-waiting estimate needs at least 2 green days as a baseline.")
    return out


def permutation_pvalue(x, y, n=2000, seed=7):
    """Two-sided permutation p-value for the Spearman correlation (no scipy needed)."""
    rng = np.random.default_rng(seed)
    x, y = pd.Series(x).rank(), pd.Series(y).rank()
    obs = abs(np.corrcoef(x, y)[0, 1])
    cnt = sum(abs(np.corrcoef(x, rng.permutation(y.to_numpy()))[0, 1]) >= obs for _ in range(n))
    return (cnt + 1) / (n + 1)


def fetch_weather(dates, lat=51.95, lng=4.10):
    """Daily wind gusts, precipitation and wave height near Rotterdam from Open-Meteo (free, no key). Needs internet."""
    import requests
    start, end = str(min(dates)), str(max(dates))
    wx = requests.get("https://archive-api.open-meteo.com/v1/archive", timeout=40, params={
        "latitude": lat, "longitude": lng, "start_date": start, "end_date": end, "timezone": "UTC",
        "daily": "wind_gusts_10m_max,precipitation_sum"}).json()["daily"]
    w = pd.DataFrame(wx).rename(columns={"time": "date"})
    try:
        mr = requests.get("https://marine-api.open-meteo.com/v1/marine", timeout=40, params={
            "latitude": 52.0, "longitude": 3.5, "start_date": start, "end_date": end, "timezone": "UTC",
            "daily": "wave_height_max"}).json()["daily"]
        w = w.merge(pd.DataFrame(mr).rename(columns={"time": "date"}), on="date", how="left")
    except Exception:  # noqa: BLE001
        pass
    w["date"] = pd.to_datetime(w["date"]).dt.date
    return w


def weather_test(daily, weather=None):
    """Does bad weather go with more ships waiting? Spearman correlation + permutation p-value, per weather variable."""
    d = daily[daily["usable"]].dropna(subset=["waiting"])
    if len(d) < MIN_DAYS["weather"]:
        return None, f"Weather test needs {MIN_DAYS['weather']} usable days, have {len(d)}."
    try:
        w = weather if weather is not None else fetch_weather(d["date"])
    except Exception as e:  # noqa: BLE001
        return None, f"Weather data could not be downloaded ({e}). Re-run with internet access."
    m = d.merge(w, on="date", how="inner")
    rows = []
    for col, label in (("wind_gusts_10m_max", "max wind gust (km/h)"), ("precipitation_sum", "rain (mm)"), ("wave_height_max", "max wave height (m)")):
        if col in m and m[col].notna().sum() >= 10:
            x, y = m[col].astype(float), m["waiting"].astype(float)
            ok = x.notna() & y.notna()
            rho = float(x[ok].rank().corr(y[ok].rank()))
            rows.append({"weather_variable": label, "days": int(ok.sum()), "spearman_rho": round(rho, 2),
                         "p_value": round(permutation_pvalue(x[ok], y[ok]), 3)})
    return pd.DataFrame(rows), None
