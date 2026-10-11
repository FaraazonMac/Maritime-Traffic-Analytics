"""Streamlit dashboard with filters.   Run:  streamlit run analysis/app.py   (after python analysis/run_all.py)"""
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from ais import config as C, estimates, geo, timeseries  # noqa: E402

st.set_page_config(page_title="Maritime Traffic Analytics", layout="wide")
LEVEL = {"green": C.LEVEL_COLORS["green"], "yellow": C.LEVEL_COLORS["yellow"], "red": C.LEVEL_COLORS["red"]}

if not (C.OUT_DATA / "ships_clean.csv").exists():
    st.error("No analysed data yet. Run `python analysis/run_all.py` first.")
    st.stop()

ships = pd.read_csv(C.OUT_DATA / "ships_clean.csv")
ships_all = pd.read_csv(C.OUT_DATA / "ships_all.csv") if (C.OUT_DATA / "ships_all.csv").exists() else ships
hubs = geo.load_hubs(C.HUBS_CSV)

st.title("Maritime Traffic Analytics")
st.sidebar.header("Filters")
region = st.sidebar.selectbox("Region", sorted(hubs["region"].unique()))
hubs_r = hubs[hubs["region"] == region]
zones = st.sidebar.multiselect("Zone", sorted(hubs_r["zone"].unique()), default=list(sorted(hubs_r["zone"].unique())))
types = st.sidebar.multiselect("Vessel type", sorted(ships["vessel_type"].unique()), default=list(sorted(ships["vessel_type"].unique())))

near_hub_in_zone = ships["zone"].isin(zones)
f = ships[ships["vessel_type"].isin(types) & (near_hub_in_zone | ships["hub"].isna())]
st.caption(f"{len(f):,} ships after filters · region: {region}")

tab_over, tab_cong, tab_fleet, tab_est, tab_time = st.tabs(["Overview", "Congestion", "Fleet", "Cost estimate", "Time analysis"])

with tab_over:
    c = st.columns(4)
    c[0].metric("Ships", f"{len(f):,}")
    c[1].metric("Under way (0.5 kn or more)", f"{100 * (f['status_group'] == 'moving').mean():.1f}%")
    c[2].metric("Waiting near hubs", f"{int(((f['status_group'] == 'at_anchor') & f['hub'].notna()).sum()):,}")
    c[3].metric("Flagged dark (of all ships incl. silent)", f"{100 * ships_all['is_dark_flagged'].mean():.1f}%")
    fig = px.scatter(f, x="lng", y="lat", color="status_group", color_discrete_map=C.STATUS_COLORS, hover_name="name",
                     hover_data=["vessel_type", "flag", "speed"], height=560)
    fig.update_yaxes(scaleanchor="x", scaleratio=1.6)
    fig.add_scatter(x=hubs_r["lng"], y=hubs_r["lat"], mode="markers+text", text=hubs_r["name"], textposition="top right",
                    marker=dict(symbol="diamond", size=9, color="white"), name="hubs")
    st.plotly_chart(fig, width="stretch")

with tab_cong:
    near = f[f["hub"].notna()]
    ct = near.pivot_table(index="hub", columns="status_group", values="mmsi", aggfunc="count", fill_value=0).reset_index()
    for col in ("at_anchor", "at_berth", "moving"):
        if col not in ct:
            ct[col] = 0
    from ais.metrics import tercile_levels
    ct["level"] = tercile_levels(ct["at_anchor"])
    ct = ct.sort_values("at_anchor")
    st.plotly_chart(px.bar(ct, y="hub", x="at_anchor", color="level", color_discrete_map=LEVEL, orientation="h",
                           title="Ships waiting at anchor near each hub (relative levels)", height=560), width="stretch")
    st.dataframe(ct.sort_values("at_anchor", ascending=False), width="stretch")

with tab_fleet:
    a, b = st.columns(2)
    a.plotly_chart(px.bar(f["vessel_type"].value_counts().reset_index(), x="vessel_type", y="count", title="By vessel type"), width="stretch")
    b.plotly_chart(px.bar(f["flag"].value_counts().head(10).reset_index(), x="flag", y="count", title="Top flags"), width="stretch")

with tab_est:
    st.warning("Estimates, not measurements. See config/assumptions.csv for every assumption and its source.")
    assump = estimates.load_assumptions(C.ASSUMPTIONS_CSV)
    st.dataframe(estimates.estimate_waiting(f, assump).round(1), width="stretch")

with tab_time:
    hist = timeseries.load_history(C.HISTORY_DB)
    if hist is None:
        st.info("No history yet. Run `python analysis/collector.py` for a few days.")
    else:
        tr = timeseries.analyse(hist, estimates.load_assumptions(C.ASSUMPTIONS_CSV))
        st.json(tr["status"])
        d = tr["daily"]
        st.plotly_chart(px.line(d[d["usable"]], x="date", y="waiting", markers=True, title="Daily ships waiting near hubs"), width="stretch")
        for msg in tr["messages"]:
            st.caption(msg)
