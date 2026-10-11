"""Static PNG charts (matplotlib) for the README, the findings memo and the notebook."""
import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

from .config import CHART_DIR, LEVEL_COLORS, STATUS_COLORS, TRACKED_BOX

TEAL, ORANGE, BLUE, GREY = "#1d8f87", "#e07b3f", "#4a90d9", "#8895a7"
plt.rcParams.update({
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.alpha": 0.25,
    "axes.titleweight": "bold", "axes.titlesize": 12, "figure.dpi": 110, "savefig.bbox": "tight",
    "axes.axisbelow": True,
})


def _save(fig, name):
    CHART_DIR.mkdir(parents=True, exist_ok=True)
    path = CHART_DIR / f"{name}.png"
    fig.savefig(path, facecolor="white")
    plt.close(fig)
    return path


def _note(ax, text):
    ax.text(0.5, 0.5, text, ha="center", va="center", transform=ax.transAxes, color=GREY)
    ax.set_axis_off()


def chart_fleet_by_type(m, **_):
    t = m["fleet_by_type"]
    fig, ax = plt.subplots(figsize=(8, 4.2))
    ax.bar(t["vessel_type"], t["ships"], color=TEAL)
    for i, v in enumerate(t["ships"]):
        ax.text(i, v, f"{v:,}", ha="center", va="bottom", fontsize=8)
    ax.set_title("Fleet composition by vessel type")
    ax.set_ylabel("ships in the snapshot")
    plt.setp(ax.get_xticklabels(), rotation=30, ha="right")
    ax.grid(axis="x", visible=False)
    return _save(fig, "01_fleet_by_type")


def chart_top_flags(m, **_):
    t = m["flags_top"].head(10).iloc[::-1]
    fig, ax = plt.subplots(figsize=(7, 4.2))
    ax.barh(t["flag"], t["ships"], color=BLUE)
    for i, (v, s) in enumerate(zip(t["ships"], t["share_pct"])):
        ax.text(v, i, f"  {v:,} ({s}%)", va="center", fontsize=8)
    ax.set_title("Top 10 flag states")
    ax.set_xlabel("ships")
    ax.grid(axis="y", visible=False)
    ax.set_xlim(0, t["ships"].max() * 1.2)
    return _save(fig, "02_top_flags")


def chart_hub_status(m, **_):
    t = m["hub_table"].sort_values("ships_in_radius")
    fig, ax = plt.subplots(figsize=(8, 6))
    left = np.zeros(len(t))
    for col, label in (("at_anchor", "waiting at anchor"), ("idle", "idle (stationary, status says under way)"), ("at_berth", "at berth / moored"), ("moving", "under way")):
        key = col
        ax.barh(t["hub"], t[col], left=left, color=STATUS_COLORS[key], label=label)
        left += t[col].to_numpy()
    ax.set_title("Ships inside each hub's radius, by status")
    ax.set_xlabel("ships")
    ax.legend(loc="lower right", frameon=False)
    ax.grid(axis="y", visible=False)
    return _save(fig, "03_hub_status")


def chart_hub_levels(m, **_):
    t = m["hub_table"].sort_values("at_anchor")
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.barh(t["hub"], t["at_anchor"], color=[LEVEL_COLORS[v] for v in t["level_waiting"]])
    for i, v in enumerate(t["at_anchor"]):
        ax.text(v, i, f"  {v}", va="center", fontsize=8)
    ax.set_title("Congestion: ships waiting at anchor near each hub")
    ax.set_xlabel("ships at anchor (colour = relative level: lowest / middle / top third of hubs)")
    ax.legend(handles=[Line2D([0], [0], color=c, lw=6, label=k) for k, c in LEVEL_COLORS.items()], frameon=False, loc="lower right")
    ax.grid(axis="y", visible=False)
    return _save(fig, "04_hub_congestion_levels")


def chart_speed_zone(m, **_):
    t = m["speed_zone"]
    fig, ax = plt.subplots(figsize=(8, 4.2))
    if t.empty:
        _note(ax, "Not enough moving ships per group")
        return _save(fig, "05_speed_near_vs_open")
    types = list(t["vessel_type"].unique())
    x = np.arange(len(types))
    for k, (loc, color) in enumerate((("near a hub", ORANGE), ("open water", TEAL))):
        vals = [float(t[(t["vessel_type"] == v) & (t["location"] == loc)]["avg_speed_kn"].mean()) for v in types]
        ax.bar(x + (k - 0.5) * 0.38, vals, 0.38, color=color, label=loc)
    ax.set_xticks(x)
    ax.set_xticklabels(types, rotation=20, ha="right")
    ax.set_ylabel("average speed of moving ships (kn)")
    ax.set_title("Do ships slow down near port hubs?")
    ax.legend(frameon=False)
    ax.grid(axis="x", visible=False)
    return _save(fig, "05_speed_near_vs_open")


def chart_dark_edge(m, **_):
    t = m["dark_edge"]
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(t["location"], t["dark_pct"], color=[ORANGE if "edge" in l else TEAL for l in t["location"]])
    for i, (p, d, n) in enumerate(zip(t["dark_pct"], t["dark"], t["ships"])):
        ax.text(i, p, f"{p}%\n({d} of {n:,})", ha="center", va="bottom", fontsize=8)
    ax.set_ylim(0, max(t["dark_pct"].max() * 1.3, 1))
    ax.set_ylabel("% of ships flagged dark")
    ax.set_title("Silent-ship flags: edge vs interior (ships heard in the last hour)")
    ax.grid(axis="x", visible=False)
    return _save(fig, "06_dark_edge_vs_interior")


def chart_data_quality(m, **_):
    t = m["completeness"].iloc[::-1]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.barh(t["field"], t["pct_complete"], color=[TEAL if v >= 80 else (ORANGE if v >= 50 else "#d64541") for v in t["pct_complete"]])
    for i, v in enumerate(t["pct_complete"]):
        ax.text(v, i, f"  {v}%", va="center", fontsize=8)
    ax.set_xlim(0, 110)
    ax.set_title("Data completeness (share of ships with a usable value)")
    ax.grid(axis="y", visible=False)
    return _save(fig, "07_data_quality")


def chart_dest_quality(m, **_):
    t = m["dest_quality"]
    labels = {"missing": "blank", "junk": "placeholder", "locode": "port code (known hub)", "hub_name": "hub name",
              "locode_other": "code, other port", "other_text": "other free text"}
    fig, ax = plt.subplots(figsize=(7.5, 4))
    ax.bar([labels.get(c, c) for c in t["category"]], t["ships"], color=BLUE)
    for i, (v, s) in enumerate(zip(t["ships"], t["share_pct"])):
        ax.text(i, v, f"{s}%", ha="center", va="bottom", fontsize=8)
    ax.set_title("What captains type into the AIS 'destination' field")
    ax.set_ylabel("ships")
    plt.setp(ax.get_xticklabels(), rotation=20, ha="right")
    ax.grid(axis="x", visible=False)
    return _save(fig, "08_destination_quality")


def chart_size_class(m, **_):
    from .config import SIZE_LABELS, UNKNOWN_SIZE
    t = m["size_class"].set_index("size_class").reindex(SIZE_LABELS + [UNKNOWN_SIZE]).dropna().reset_index()
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(t["size_class"], t["ships"], color=TEAL)
    for i, v in enumerate(t["ships"]):
        ax.text(i, v, f"{v:,}", ha="center", va="bottom", fontsize=8)
    ax.set_title("Ships by size class (length from AIS)")
    plt.setp(ax.get_xticklabels(), rotation=20, ha="right")
    ax.grid(axis="x", visible=False)
    return _save(fig, "09_size_classes")


def chart_routes(m, **_):
    t = m["routes"]
    fig, ax = plt.subplots(figsize=(8, 5))
    if t.empty:
        _note(ax, "No ships with both a detected departure and a usable destination yet")
        return _save(fig, "10_top_routes")
    t = t.iloc[::-1]
    ax.barh([f"{a} → {b}" for a, b in zip(t["departure_port"], t["destination"])], t["ships"], color=ORANGE)
    ax.set_title("Most common voyages (departure detected live → declared destination)")
    ax.set_xlabel("ships")
    ax.grid(axis="y", visible=False)
    return _save(fig, "10_top_routes")


def chart_map(m, df=None, hubs=None, **_):
    lat_min, lng_min, lat_max, lng_max = TRACKED_BOX
    fig, ax = plt.subplots(figsize=(8, 7))
    for key, label in (("at_berth", "at berth"), ("idle", "idle"), ("at_anchor", "at anchor"), ("moving", "under way")):
        s = df[df["status_group"] == key]
        ax.scatter(s["lng"], s["lat"], s=4, color=STATUS_COLORS[key], alpha=0.55, label=label, linewidths=0)
    ax.scatter(hubs["lng"], hubs["lat"], marker="D", s=26, color="black", zorder=5)
    for _, h in hubs.iterrows():
        ax.annotate(h["name"].split(" (")[0], (h["lng"], h["lat"]), fontsize=6.5, xytext=(3, 3), textcoords="offset points")
    ax.set_xlim(lng_min, lng_max)
    ax.set_ylim(lat_min, lat_max)
    ax.set_aspect(1 / np.cos(np.radians((lat_min + lat_max) / 2)))
    ax.set_title("Where the ships are (diamonds = port hubs)")
    ax.set_xlabel("longitude")
    ax.set_ylabel("latitude")
    ax.legend(markerscale=3, frameon=False, loc="upper left")
    return _save(fig, "11_map")


def chart_estimates(m, est=None, **_):
    if est is None:
        return None
    tot = est[est["size_class"] == "Total"].iloc[0]
    fig, axes = plt.subplots(1, 3, figsize=(10, 3.8))
    for ax, (key, title, unit, div) in zip(axes, (("fuel_t", "Fuel burned", "tonnes/day", 1), ("co2_t", "CO2 emitted", "tonnes/day", 1),
                                                   ("cost_usd", "Cost of idling", "USD million/day", 1e6))):
        lo, ce, hi = tot[f"{key}_low"] / div, tot[f"{key}_central"] / div, tot[f"{key}_high"] / div
        ax.bar([0], [ce], color=TEAL, width=0.5)
        ax.errorbar([0], [ce], yerr=[[ce - lo], [hi - ce]], fmt="none", ecolor="black", capsize=8)
        ax.set_xticks([])
        ax.set_title(f"{title}\n{lo:,.1f} to {hi:,.1f} {unit}", fontsize=10)
        ax.set_ylabel(unit)
        ax.grid(axis="x", visible=False)
    fig.suptitle("ESTIMATE: ships waiting at anchor near hubs (bar = central case, whisker = low to high)", fontsize=10, y=1.02)
    return _save(fig, "12_estimates")


def chart_segments(m, **_):
    t = m["segments"].iloc[::-1]
    fig, ax = plt.subplots(figsize=(9, 3.8))
    left = np.zeros(len(t))
    for col, label, key in (("pct_under_way", "under way", "moving"), ("pct_idle", "idle (stationary)", "idle"),
                            ("pct_at_anchor", "at anchor", "at_anchor"), ("pct_at_berth", "at berth / moored", "at_berth")):
        ax.barh(t["segment"], t[col], left=left, color=STATUS_COLORS[key], label=label)
        left += t[col].to_numpy()
    for i, n in enumerate(t["ships"]):
        ax.text(101, i, f"{n:,} ships", va="center", fontsize=8)
    ax.set_xlim(0, 118)
    ax.set_xlabel("% of the segment's ships")
    ax.set_title("What each segment is doing right now")
    ax.legend(ncol=4, frameon=False, loc="upper center", bbox_to_anchor=(0.45, -0.18), fontsize=8)
    ax.grid(axis="y", visible=False)
    return _save(fig, "13_segments")


ALL_CHARTS = [chart_fleet_by_type, chart_top_flags, chart_hub_status, chart_hub_levels, chart_speed_zone, chart_dark_edge,
              chart_data_quality, chart_dest_quality, chart_size_class, chart_routes, chart_map, chart_estimates, chart_segments]


def make_all(m, df, hubs, est):
    """Draw every chart; one failing chart never stops the rest. Returns (paths, errors)."""
    paths, errors = [], []
    for fn in ALL_CHARTS:
        try:
            p = fn(m, df=df, hubs=hubs, est=est)
            if p:
                paths.append(p)
        except Exception as e:  # noqa: BLE001
            errors.append(f"{fn.__name__}: {e}")
    return paths, errors


# ------------------------------------------------------------------ time-analysis charts (v2)
def _save_time(fig, name):
    from .config import TIME_OUT
    TIME_OUT.mkdir(parents=True, exist_ok=True)
    path = TIME_OUT / f"{name}.png"
    fig.savefig(path, facecolor="white")
    plt.close(fig)
    return path


def make_time_charts(tr):
    """PNG charts for the time analysis. Returns (paths, errors)."""
    from matplotlib.patches import Rectangle
    paths, errors = [], []
    d = tr["daily"]
    u = d[d["usable"]].copy()

    def attempt(fn):
        try:
            p = fn()
            if p:
                paths.append(p)
        except Exception as e:  # noqa: BLE001
            errors.append(f"{fn.__name__}: {e}")

    def daily_line():
        fig, ax = plt.subplots(figsize=(9, 3.8))
        ax.plot(pd_dates(u["date"]), u["waiting"], color=TEAL, lw=1.5)
        ax.scatter(pd_dates(u["date"]), u["waiting"], s=55, zorder=3, edgecolor="black", linewidth=0.5,
                   c=[LEVEL_COLORS.get(l, GREY) for l in u["congestion_level"]])
        ax.set_title("Daily congestion: average ships waiting at anchor near the hubs")
        ax.set_ylabel("ships")
        fig.autofmt_xdate()
        return _save_time(fig, "t1_daily_congestion")

    def calendar():
        import pandas as pd
        dd = u.dropna(subset=["congestion_level"]).copy()
        if dd.empty:
            return None
        dd["ts"] = pd.to_datetime(dd["date"])
        dd["wk"] = dd["ts"].dt.strftime("%G-W%V")
        weeks = sorted(dd["wk"].unique())
        fig, ax = plt.subplots(figsize=(7.5, 0.55 * len(weeks) + 1.4))
        for _, r in dd.iterrows():
            x, y = r["ts"].dayofweek, weeks.index(r["wk"])
            ax.add_patch(Rectangle((x, -y - 1), 0.92, 0.88, color=LEVEL_COLORS[r["congestion_level"]]))
            ax.text(x + 0.46, -y - 0.55, str(r["ts"].day), ha="center", va="center", fontsize=8, color="white")
        ax.set_xlim(0, 7)
        ax.set_ylim(-len(weeks), 0)
        ax.set_xticks([i + 0.46 for i in range(7)])
        ax.set_xticklabels(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])
        ax.set_yticks([-i - 0.55 for i in range(len(weeks))])
        ax.set_yticklabels(weeks)
        ax.grid(False)
        ax.set_title("Calendar of congestion levels (green / yellow / red)")
        return _save_time(fig, "t2_calendar")

    def hours():
        if "hour_profile" not in tr:
            return None
        h = tr["hour_profile"]
        fig, ax = plt.subplots(figsize=(8, 3.6))
        ax.bar(h["hour"], h["waiting"], color=TEAL)
        ax.set_title("Ships waiting by hour of day (Europe/Amsterdam)")
        ax.set_xlabel("hour")
        ax.set_ylabel("average ships waiting")
        return _save_time(fig, "t3_hour_of_day")

    def weekdays():
        if "weekday_profile" not in tr:
            return None
        w = tr["weekday_profile"]
        fig, ax = plt.subplots(figsize=(7, 3.6))
        ax.bar(w["day"], w["waiting"], color=BLUE)
        ax.set_title("Ships waiting by weekday")
        ax.set_ylabel("average ships waiting")
        return _save_time(fig, "t4_weekday")

    def weekly():
        if "weekly_levels" not in tr:
            return None
        t = tr["weekly_levels"]
        fig, ax = plt.subplots(figsize=(8, 3.8))
        bottom = np.zeros(len(t))
        for lvl in ("green", "yellow", "red"):
            ax.bar(t.iloc[:, 0], t[lvl], bottom=bottom, color=LEVEL_COLORS[lvl], label=lvl)
            bottom += t[lvl].to_numpy()
        ax.set_title("Weekly: number of green / yellow / red days")
        ax.legend(frameon=False)
        plt.setp(ax.get_xticklabels(), rotation=30, ha="right")
        return _save_time(fig, "t5_weekly_levels")

    for fn in (daily_line, calendar, hours, weekdays, weekly):
        attempt(fn)
    return paths, errors


def pd_dates(series):
    import pandas as pd
    return pd.to_datetime(series)
