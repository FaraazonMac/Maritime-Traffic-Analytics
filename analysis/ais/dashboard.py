"""Interactive HTML dashboard (plotly): one self-contained page with tabs, styled like the Maritime Globe app."""
import html

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.io import to_html
from plotly.subplots import make_subplots
import plotly.offline as pyo

from .config import LEVEL_COLORS, STATUS_COLORS, TRACKED_BOX

BG, CARD, TEXT, MUTED = "#0d1620", "#111d2b", "#e8edf2", "#7f95a8"
TEAL, ORANGE, BLUE, RED = "#3fd9c7", "#e07b3f", "#4a90d9", "#d64541"
STATUS_LABEL = {"moving": "Under way", "idle": "Idle (stationary)", "at_anchor": "At anchor", "at_berth": "At berth / moored", "other": "Other"}
DEST_LABEL = {"missing": "Blank", "junk": "Placeholder (e.g. FOR ORDERS)", "locode": "Port code (known hub)", "hub_name": "Hub name",
              "locode_other": "Port code (other port)", "other_text": "Other free text"}
DEST_ORDER = ["Blank", "Placeholder (e.g. FOR ORDERS)", "Other free text", "Port code (other port)", "Port code (known hub)", "Hub name"]


def _short(name):
    return str(name).split(" (")[0]


def _nice(v):
    """Display text: 'cargo' -> 'Cargo', 'ROTTERDAM' -> 'Rotterdam'; mixed case (e.g. IJmuiden) is left alone."""
    v = str(v)
    return v.title() if (v.islower() or v.isupper()) else v


def _label_pos(hubs_df, names):
    if "label_pos" in hubs_df.columns:
        lp = dict(zip(hubs_df["name"], hubs_df["label_pos"]))
        return [lp.get(n, "top right") for n in names]
    return ["top right"] * len(names)


def _geo(fig, title, h=620):
    lat_min, lng_min, lat_max, lng_max = TRACKED_BOX
    fig.update_geos(projection_type="mercator", lonaxis_range=[lng_min - 1.2, lng_max + 1.6], lataxis_range=[lat_min - 0.6, lat_max + 0.6], resolution=50,
                    showland=True, landcolor="#1b2a3a", showocean=True, oceancolor=BG, showcountries=True, countrycolor="#31465c",
                    coastlinecolor=TEAL, bgcolor=CARD)
    return _style(fig, title, h=h)


def _style(fig, title, h=380):
    fig.update_layout(template="plotly_dark", paper_bgcolor=CARD, plot_bgcolor=CARD, height=h,
                      font=dict(color=TEXT, family="IBM Plex Sans, system-ui, sans-serif"),
                      title=dict(text=title, x=0.01, font=dict(size=15)), margin=dict(l=50, r=20, t=55, b=45),
                      legend=dict(bgcolor="rgba(0,0,0,0)"))
    fig.update_xaxes(gridcolor="#1f2e3f")
    fig.update_yaxes(gridcolor="#1f2e3f")
    return fig


# ------------------------------------------------------------------ figures
def fig_map(df, hubs):
    fig = go.Figure()
    for key in ("at_berth", "idle", "at_anchor", "moving"):
        sub = df[df["status_group"] == key]
        fig.add_trace(go.Scattergeo(
            lat=sub["lat"], lon=sub["lng"], mode="markers", name=STATUS_LABEL[key],
            marker=dict(size=5, color=STATUS_COLORS[key], opacity=0.75),
            text=sub["name"].fillna("(unnamed)") + " | " + sub["vessel_type"].map(_nice) + " | " + sub["flag"], hoverinfo="text"))
    fig.add_trace(go.Scattergeo(lat=hubs["lat"], lon=hubs["lng"], mode="markers+text", name="Port hubs",
                                text=hubs["name"].map(_short), textposition=_label_pos(hubs, hubs["name"]), textfont=dict(size=10, color=TEXT),
                                marker=dict(size=8, symbol="diamond", color="white", line=dict(width=1, color="black")), hoverinfo="text"))
    return _geo(fig, "Where the ships are (hover a dot for name, type and flag)", h=640)


def fig_hub_bubbles(m, hubs):
    cols = ["name"] + (["label_pos"] if "label_pos" in hubs.columns else [])
    t = m["hub_table"].merge(hubs[cols], left_on="hub", right_on="name", how="left")
    size = np.clip(np.sqrt(t["ships_in_radius"].astype(float)) * 2.4, 8, 46)
    fig = go.Figure(go.Scattergeo(
        lat=t["lat"], lon=t["lng"], mode="markers+text", text=t["hub"].map(_short), textposition=_label_pos(hubs, t["hub"]),
        textfont=dict(size=10, color=TEXT),
        marker=dict(size=size, color=[LEVEL_COLORS[v] for v in t["level_waiting"]], opacity=0.85, line=dict(width=1, color="white")),
        customdata=np.stack([t["ships_in_radius"], t["at_anchor"], t["pct_at_anchor"].fillna(0), t["level_waiting"]], axis=-1),
        hovertemplate="<b>%{text}</b><br>ships in radius: %{customdata[0]}<br>waiting at anchor: %{customdata[1]} (%{customdata[2]}%)<br>level: %{customdata[3]}<extra></extra>"))
    fig.update_layout(showlegend=False)
    return _geo(fig, "Hub congestion map: bubble size = ships in radius, colour = waiting level", h=600)


def fig_status(m):
    s = m["status"]
    fig = go.Figure(go.Pie(labels=[STATUS_LABEL.get(x, x) for x in s["status"]], values=s["ships"], hole=0.55,
                           marker=dict(colors=[STATUS_COLORS.get(x, "#8895a7") for x in s["status"]]), textinfo="label+percent"))
    return _style(fig, "Fleet by navigation status", h=330)


def fig_hub_levels(m):
    t = m["hub_table"].sort_values("at_anchor")
    fig = go.Figure(go.Bar(y=t["hub"], x=t["at_anchor"], orientation="h", marker_color=[LEVEL_COLORS[v] for v in t["level_waiting"]],
                           text=t["at_anchor"], textposition="outside",
                           customdata=np.stack([t["ships_in_radius"], t["pct_at_anchor"], t["level_waiting"]], axis=-1),
                           hovertemplate="%{y}<br>waiting: %{x}<br>ships in radius: %{customdata[0]}<br>share at anchor: %{customdata[1]}%<br>level: %{customdata[2]}<extra></extra>"))
    fig.update_xaxes(title="Ships waiting at anchor (colour = relative level: lowest / middle / top third of hubs)")
    return _style(fig, "Congestion: ships waiting at anchor near each hub", h=560)


def fig_hub_status(m):
    t = m["hub_table"].sort_values("ships_in_radius")
    fig = go.Figure()
    for col in ("at_anchor", "idle", "at_berth", "moving"):
        fig.add_trace(go.Bar(y=t["hub"], x=t[col], orientation="h", name=STATUS_LABEL[col], marker_color=STATUS_COLORS[col]))
    fig.update_layout(barmode="stack")
    return _style(fig, "Ships inside each hub's radius, by status", h=560)


def fig_zone(m):
    z = m["zone_table"]
    fig = go.Figure(go.Bar(x=z["zone"], y=z["pct_at_anchor"], marker_color=TEAL, text=z["pct_at_anchor"].astype(str) + "%", textposition="outside"))
    fig.update_yaxes(title="% of ships in hub radius at anchor")
    return _style(fig, "Sub-zones of the study region compared", h=360)


def fig_speed_zone(m):
    t = m["speed_zone"]
    fig = go.Figure()
    for loc, color in (("near a hub", ORANGE), ("open water", TEAL)):
        s = t[t["location"] == loc]
        fig.add_trace(go.Bar(x=s["vessel_type"].map(_nice), y=s["avg_speed_kn"], name=loc.capitalize(), marker_color=color))
    fig.update_layout(barmode="group")
    fig.update_yaxes(title="Average speed of moving ships (knots)")
    return _style(fig, "Do ships slow down near port hubs?", h=360)


def fig_fleet(m):
    t = m["fleet_by_type"]
    fig = go.Figure(go.Bar(x=t["vessel_type"].map(_nice), y=t["ships"], marker_color=TEAL, text=t["ships"], textposition="outside"))
    fig.update_yaxes(title="Ships")
    return _style(fig, "Fleet composition by vessel type", h=360)


def fig_segments(m):
    t = m["segments"].iloc[::-1]
    fig = go.Figure()
    for col, label, key in (("pct_under_way", "Under way", "moving"), ("pct_idle", "Idle (stationary)", "idle"),
                            ("pct_at_anchor", "At anchor", "at_anchor"), ("pct_at_berth", "At berth / moored", "at_berth")):
        fig.add_trace(go.Bar(y=t["segment"], x=t[col], orientation="h", name=label, marker_color=STATUS_COLORS[key],
                             customdata=t["ships"], hovertemplate="%{y}: %{x}% " + label.lower() + " (%{customdata:,} ships)<extra></extra>"))
    fig.update_layout(barmode="stack")
    fig.update_xaxes(title="% of the segment's ships", range=[0, 100])
    return _style(fig, "What each segment is doing right now", h=380)


def fig_flags(m):
    t = m["flags_top"].head(10).iloc[::-1]
    fig = go.Figure(go.Bar(y=t["flag"], x=t["ships"], orientation="h", marker_color=BLUE, text=t["share_pct"].astype(str) + "%", textposition="outside"))
    fig.update_xaxes(range=[0, float(t["ships"].max()) * 1.22], title="Ships")
    return _style(fig, "Top 10 flag states", h=380)


def fig_size(m):
    from .config import SIZE_LABELS, UNKNOWN_SIZE
    t = m["size_class"].set_index("size_class").reindex(SIZE_LABELS + [UNKNOWN_SIZE]).dropna().reset_index()
    fig = go.Figure(go.Bar(x=t["size_class"], y=t["ships"], marker_color=TEAL, text=t["ships"].astype(int), textposition="outside"))
    fig.update_yaxes(title="Ships", range=[0, float(t["ships"].max()) * 1.18])
    return _style(fig, "Ships by size class (length from AIS)", h=340)


def fig_routes(m):
    t = m["routes"]
    fig = go.Figure()
    if len(t):
        t = t.iloc[::-1]
        fig.add_trace(go.Bar(y=[f"{_nice(a)} → {_nice(b)}" for a, b in zip(t["departure_port"], t["destination"])], x=t["ships"], orientation="h", marker_color=ORANGE))
        fig.update_xaxes(title="Ships")
    return _style(fig, "Most common voyages (detected departure → declared destination)", h=460)


def fig_dest(m):
    t = m["dest_quality"].copy()
    t["label"] = t["category"].map(DEST_LABEL).fillna(t["category"])
    t = t.set_index("label").reindex([c for c in DEST_ORDER if c in set(t["label"])]).reset_index()
    fig = go.Figure(go.Bar(x=t["label"], y=t["ships"], marker_color=BLUE, text=t["share_pct"].astype(str) + "%", textposition="outside"))
    fig.update_yaxes(title="Ships")
    return _style(fig, "What captains type into the AIS destination field", h=380)


def fig_complete(m):
    t = m["completeness"].iloc[::-1]
    fig = go.Figure(go.Bar(y=t["field"], x=t["pct_complete"], orientation="h", text=t["pct_complete"].astype(str) + "%", textposition="outside",
                           marker_color=[TEAL if v >= 80 else (ORANGE if v >= 50 else RED) for v in t["pct_complete"]]))
    fig.update_xaxes(range=[0, 112], title="% of ships with a usable value")
    return _style(fig, "Data completeness", h=420)


def fig_dark_edge(m):
    t = m["dark_edge"]
    fig = go.Figure(go.Bar(x=t["location"].str.capitalize(), y=t["dark_pct"], marker_color=[ORANGE if "edge" in l else TEAL for l in t["location"]],
                           text=[f"{p}% ({d}/{n})" for p, d, n in zip(t["dark_pct"], t["dark"], t["ships"])], textposition="outside"))
    fig.update_yaxes(title="% silent for 20+ minutes")
    return _style(fig, "Silent-ship flags: edge vs interior (ships heard in the last hour)", h=340)


def fig_dark_type(m):
    t = m["dark_type"]
    fig = go.Figure(go.Bar(x=t["vessel_type"].map(_nice), y=t["dark_pct"], marker_color=ORANGE))
    fig.update_yaxes(title="% silent for 20+ minutes")
    return _style(fig, "Silent-ship flags by vessel type (ships heard in the last hour, types with 20+ ships)", h=340)


def fig_estimates(est):
    tot = est[est["size_class"] == "Total"].iloc[0]
    fig = make_subplots(rows=1, cols=3, subplot_titles=("Fuel burned (t/day)", "CO2 emitted (t/day)", "Cost of idling (USD m/day)"))
    for i, (key, div) in enumerate((("fuel_t", 1), ("co2_t", 1), ("cost_usd", 1e6)), start=1):
        lo, ce, hi = tot[f"{key}_low"] / div, tot[f"{key}_central"] / div, tot[f"{key}_high"] / div
        fig.add_trace(go.Bar(x=["central"], y=[ce], error_y=dict(type="data", symmetric=False, array=[hi - ce], arrayminus=[ce - lo]),
                             marker_color=TEAL, showlegend=False, hovertemplate=f"low {lo:,.1f} | central {ce:,.1f} | high {hi:,.1f}<extra></extra>"), row=1, col=i)
    fig = _style(fig, "ESTIMATE: ships waiting at anchor near hubs (bar = central case, whisker = low to high)", h=420)
    fig.update_layout(margin=dict(l=50, r=20, t=110, b=45))
    return fig


# ------------------------------------------------------------------ time (v2) figures
def _time_figs(tr):
    figs = []
    d = tr["daily"]
    u = d[d["usable"]]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=u["date"], y=u["waiting"], mode="lines+markers", name="ships waiting near hubs", line=dict(color=TEAL),
                             marker=dict(size=9, color=[LEVEL_COLORS.get(l, "#8895a7") for l in u["congestion_level"]], line=dict(width=1, color="black"))))
    fig.update_yaxes(title="average ships waiting at anchor")
    figs.append(("Daily congestion (marker colour = relative level)", _style(fig, "Daily congestion near the hubs", h=360)))
    if "hour_profile" in tr:
        h = tr["hour_profile"]
        fig = go.Figure(go.Bar(x=h["hour"], y=h["waiting"], marker_color=TEAL))
        fig.update_xaxes(title="hour of day (Europe/Amsterdam)")
        fig.update_yaxes(title="average ships waiting")
        figs.append(("Hour of day", _style(fig, "Waiting ships by hour of day", h=340)))
    if "weekday_profile" in tr:
        w = tr["weekday_profile"]
        fig = go.Figure(go.Bar(x=w["day"], y=w["waiting"], marker_color=BLUE))
        figs.append(("Weekday", _style(fig, "Waiting ships by weekday", h=340)))
    for key, label in (("weekly_levels", "Weekly: number of green / yellow / red days"), ("monthly_levels", "Monthly: number of green / yellow / red days")):
        if key in tr:
            t = tr[key]
            fig = go.Figure()
            for lvl in ("green", "yellow", "red"):
                fig.add_trace(go.Bar(x=t.iloc[:, 0], y=t[lvl], name=lvl, marker_color=LEVEL_COLORS[lvl]))
            fig.update_layout(barmode="stack")
            figs.append((label, _style(fig, label, h=340)))
    return figs


# ------------------------------------------------------------------ page
def _div(fig):
    return to_html(fig, full_html=False, include_plotlyjs=False, config={"responsive": True, "displaylogo": False})


def _kpi(label, value):
    return f'<div class="kpi"><div class="v">{html.escape(str(value))}</div><div class="l">{html.escape(label)}</div></div>'


def _table_html(df, max_rows=40):
    return df.head(max_rows).to_html(index=False, border=0, classes="tbl", na_rep="")


def _estimates_table(est):
    def tri(r, key, div=1, nd=0):
        return f"{r[key + '_low'] / div:,.{nd}f} / {r[key + '_central'] / div:,.{nd}f} / {r[key + '_high'] / div:,.{nd}f}"
    rows = [{"Size class": r["size_class"], "Ships waiting": f"{int(r['ships_waiting']):,}",
             "Fuel, t/day (low / central / high)": tri(r, "fuel_t"), "CO2, t/day (low / central / high)": tri(r, "co2_t"),
             "Cost, $ million/day (low / central / high)": tri(r, "cost_usd", 1e6, 2)} for _, r in est.iterrows()]
    return pd.DataFrame(rows)


def _log_table(log):
    return log.rename(columns={"rule": "Cleaning rule", "rows_affected": "Rows affected", "action": "What was done"})


def _insight(text):
    return '<div class="insight">' + text + '</div>'


CSS = f"""
*{{box-sizing:border-box}} body{{margin:0;background:{BG};color:{TEXT};font-family:'IBM Plex Sans',system-ui,sans-serif}}
header{{padding:22px 28px 8px}} h1{{margin:0;font-size:22px;color:{TEAL};letter-spacing:.02em}}
.sub{{color:{MUTED};font-size:13px;margin-top:4px}}
nav{{display:flex;gap:6px;padding:10px 28px;flex-wrap:wrap;border-bottom:1px solid #1f2e3f;position:sticky;top:0;background:{BG};z-index:5}}
nav button{{background:{CARD};color:{MUTED};border:1px solid #1f2e3f;border-radius:6px;padding:8px 14px;cursor:pointer;font-size:13px}}
nav button.on{{color:{BG};background:{TEAL};border-color:{TEAL};font-weight:600}}
.tab{{display:none;padding:18px 28px 40px}} .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(460px,1fr));gap:16px}}
.card{{background:{CARD};border:1px solid #1f2e3f;border-radius:10px;padding:6px;overflow:hidden}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin-bottom:16px}}
.kpi{{background:{CARD};border:1px solid #1f2e3f;border-radius:10px;padding:14px}} .kpi .v{{font-size:24px;color:{TEAL};font-weight:600}} .kpi .l{{font-size:12px;color:{MUTED};margin-top:4px}}
.note{{background:#1a2635;border-left:3px solid {ORANGE};padding:10px 14px;border-radius:6px;margin:0 0 16px;font-size:13px;color:{TEXT}}}
.tbl{{border-collapse:collapse;font-size:12px;width:100%}} .tbl th{{background:#16263a;color:{TEAL};text-align:left;padding:6px 8px}} .tbl td{{padding:5px 8px;border-top:1px solid #1f2e3f}}
.insight{{background:#0f2a2c;border-left:3px solid {TEAL};padding:10px 14px;border-radius:6px;margin:0 0 16px;font-size:14px}} .wide{{grid-column:1/-1}} footer{{color:{MUTED};font-size:12px;padding:0 28px 30px}}
"""
JS = """
function show(id){document.querySelectorAll('.tab').forEach(e=>e.style.display='none');
document.getElementById(id).style.display='block';
document.querySelectorAll('nav button').forEach(b=>b.classList.toggle('on',b.dataset.t===id));
window.dispatchEvent(new Event('resize'));}
show('overview');
"""


def build(path, m, df, hubs, est, stamp, region, tr=None, inline_js=False):
    k = m["kpis"]
    kpis = "".join([
        _kpi("current ships", f"{k['total_ships']:,}"), _kpi("under way (0.5 kn or more)", f"{k['pct_moving']}%"), _kpi("idle (stationary)", f"{k['pct_idle']}%"),
        _kpi("waiting at anchor near hubs", f"{k['waiting_near_hubs']:,}"), _kpi("silent 20+ min (ships heard in the last hour)", f"{k['pct_dark']}%"),
        _kpi("destination resolved to a port", f"{k['pct_dest_resolved']}%"), _kpi("with a valid IMO", f"{k['pct_valid_imo']}%"),
    ])
    ht = m["hub_table"]
    top = ht.iloc[0] if len(ht) else None
    reds = ht[ht["level_waiting"] == "red"]["hub"].tolist()
    ft = m["fleet_by_type"]
    ft_known = ft[ft["vessel_type"] != "unknown"]
    fl = m["flags_top"]
    tabs = {}
    ins_over = _insight(f"Of {k['total_ships']:,} current ships, <b>{k['pct_moving']}%</b> are under way, <b>{k['pct_idle']}%</b> are idle (stationary though their status says under way), <b>{k['pct_at_berth']}%</b> are moored and <b>{k['pct_at_anchor']}%</b> are at anchor. "
                        f"<b>{k['waiting_near_hubs']:,}</b> ships are waiting at anchor inside a hub radius.")
    tabs["overview"] = ("Overview", ins_over + f'<div class="kpis">{kpis}</div><div class="grid"><div class="card wide">{_div(fig_map(df, hubs))}</div>'
                                    f'<div class="card">{_div(fig_status(m))}</div><div class="card">{_div(fig_hub_levels(m))}</div></div>')
    ins_cong = _insight((f"<b>{_short(top['hub'])}</b> has the most ships waiting at anchor ({int(top['at_anchor'])}, {top['pct_at_anchor']}% of ships in its radius). "
                         f"Top 3 by waiting ships: {', '.join(_short(r['hub']) + ' (' + str(int(r['at_anchor'])) + ')' for _, r in ht.head(3).iterrows())}.") if top is not None and top["at_anchor"] > 0 else "No ships are waiting at anchor inside a hub radius.")
    tabs["congestion"] = ("Congestion", ins_cong + '<div class="note">Levels are <b>relative</b>: the lowest third of hubs is green, the middle third yellow, the top third red. '
                                        'They are not an industry standard. One snapshot shows a moment, not a trend.</div>'
                                        f'<div class="grid"><div class="card wide">{_div(fig_hub_bubbles(m, hubs))}</div>'
                                        f'<div class="card">{_div(fig_hub_levels(m))}</div><div class="card">{_div(fig_hub_status(m))}</div>'
                                        f'<div class="card">{_div(fig_zone(m))}</div><div class="card">{_div(fig_speed_zone(m))}</div></div>')
    ins_fleet = _insight((f"Among ships with a known type, <b>{_nice(ft_known.iloc[0]['vessel_type'])}</b> is the largest group ({int(ft_known.iloc[0]['ships']):,} ships). "
                          f"<b>{k['pct_type_unknown']}%</b> have no type. The most common flag is <b>{fl.iloc[0]['flag']}</b> ({fl.iloc[0]['share_pct']}%).") if len(ft_known) and len(fl) else "")
    tabs["fleet"] = ("Fleet", ins_fleet + f'<div class="grid"><div class="card">{_div(fig_fleet(m))}</div><div class="card">{_div(fig_flags(m))}</div>'
                              f'<div class="card">{_div(fig_size(m))}</div><div class="card">{_div(fig_dark_edge(m))}</div><div class="card wide">{_div(fig_segments(m))}</div>'
                              f'<div class="card wide">{_div(fig_dark_type(m))}</div></div>')
    ins_voy = _insight(f"<b>{k['ships_with_departure']:,}</b> ships have a detected departure port. Only <b>{k['pct_dest_usable']}%</b> of destinations are usable text, "
                       f"and <b>{k['pct_dest_resolved']}%</b> resolve to a known port after cleaning.")
    tabs["voyages"] = ("Voyages", ins_voy + '<div class="note">Departure ports are detected live when a ship leaves a known port, so only voyages observed while the backend was running appear. '
                                  'Destinations are typed by captains and cleaned here.</div>'
                                  f'<div class="grid"><div class="card">{_div(fig_routes(m))}</div><div class="card">{_div(fig_dest(m))}</div></div>')
    tabs["estimates"] = ("Cost & fuel (estimates)", '<div class="note"><b>These are estimates, not measurements.</b> AIS has no fuel, operator or cargo data. '
                                                    'Figures come from published ranges in config/assumptions.csv. The result is the cost of ships idling at anchor near a hub, '
                                                    'an upper bound for congestion-attributable cost because some waiting is normal.</div>'
                                                    f'<div class="card">{_div(fig_estimates(est))}</div>'
                                                    f'<div class="card" style="margin-top:16px;padding:12px">{_table_html(_estimates_table(est))}</div>')
    tabs["quality"] = ("Data quality", _insight(f"Only <b>{k['pct_valid_imo']}%</b> of ships carry a valid IMO number and <b>{k['pct_with_length']}%</b> report a length; "
                                                f"<b>{k['pct_type_unknown']}%</b> have no vessel type." + (" This is high because the backend restarted recently and static data is still arriving; re-run after several hours." if k["pct_type_unknown"] >= 20 else "")) +
                       f'<div class="grid"><div class="card">{_div(fig_complete(m))}</div>'
                       f'<div class="card" style="padding:12px;max-height:640px;overflow:auto"><h3 style="margin:4px 0 8px;color:{TEAL}">Cleaning log</h3>{_table_html(_log_table(m["cleaning_log"]), 60)}</div></div>')
    if tr is not None:
        body = ""
        st = tr["status"]
        body += (f'<div class="note">History: {st["polls"]} polls over {st["days_seen"]} days ({st["usable_days"]} usable), every {st["interval_min"]:g} min, '
                 f'{st["first"]} to {st["last"]}; {st["failed_polls"]} failed polls. Mean daily coverage {st["mean_coverage_pct"]}%. '
                 f'Gaps are real: the laptop or backend was off.</div>')
        if tr["messages"]:
            body += '<div class="note">' + "<br>".join(html.escape(x) for x in tr["messages"]) + "</div>"
        body += '<div class="grid">' + "".join(f'<div class="card">{_div(f)}</div>' for _, f in _time_figs(tr)) + "</div>"
        tabs["time"] = ("Time analysis (v2)", body)

    nav = "".join(f'<button data-t="{k_}" onclick="show(\'{k_}\')">{html.escape(v[0])}</button>' for k_, v in tabs.items())
    sections = "".join(f'<section class="tab" id="{k_}">{v[1]}</section>' for k_, v in tabs.items())
    js = pyo.get_plotlyjs() if inline_js else None
    script = f"<script>{js}</script>" if js else f'<script src="https://cdn.plot.ly/plotly-{pyo.get_plotlyjs_version()}.min.js"></script>'
    page = (f'<!doctype html><html><head><meta charset="utf-8"><title>Maritime Traffic Analytics</title>'
            f'<meta name="viewport" content="width=device-width,initial-scale=1"><style>{CSS}</style>{script}</head><body>'
            f'<header><h1>Maritime Traffic Analytics</h1><div class="sub">{html.escape(region)} · snapshot {html.escape(k["snapshot_utc"])} UTC · live AIS data</div></header>'
            f'<nav>{nav}</nav>{sections}'
            f'<footer>Coverage comes from land-based AIS receivers and your uptime, so open-sea traffic is under-represented. Generated by run_all.py.</footer>'
            f'<script>{JS}</script></body></html>')
    path.write_text(page, encoding="utf-8")
    return path
