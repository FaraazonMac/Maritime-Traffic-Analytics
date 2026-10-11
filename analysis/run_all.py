"""One command that rebuilds the whole analysis.

    python analysis/run_all.py                 # pull the live fleet from the backend (must be running), then analyse
    python analysis/run_all.py --csv FILE      # analyse a saved snapshot instead
    python analysis/run_all.py --no-fetch      # reuse the newest saved snapshot
    python analysis/run_all.py --weather       # also test weather vs waiting ships (needs internet and several weeks of history)

Outputs go to analysis/outputs/: data/*.csv, charts/*.png, sql/*.csv, MaritimeAnalytics.xlsx, dashboard.html, FINDINGS.md.
"""
import argparse
import datetime as dt
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd  # noqa: E402

from ais import charts, clean, config as C, dashboard, estimates, excel, geo, load, metrics, report, sqlrun, timeseries  # noqa: E402

FAILED = []


def step(label, fn):
    t0 = time.time()
    try:
        out = fn()
        print(f"   ok  {label} ({time.time() - t0:.1f}s)")
        return out
    except Exception as e:  # noqa: BLE001
        FAILED.append(f"{label}: {e}")
        print(f"   FAILED  {label}: {e}")
        if "--debug" in sys.argv:
            traceback.print_exc()
        return None


def get_data(args):
    if args.csv:
        df, stamp = load.read_csv(Path(args.csv))
        print(f"Using {args.csv}")
        return df, stamp
    if not args.no_fetch:
        try:
            df, stamp, path = load.fetch_snapshot(args.url)
            print(f"Fetched {len(df):,} ships from {args.url} and saved {path.name}")
            return df, stamp
        except Exception as e:  # noqa: BLE001
            print(f"Could not reach the backend ({e.__class__.__name__}). Falling back to the newest saved snapshot.")
    path = load.latest_csv()
    if path is None:
        sys.exit("No data. Start the backend (uvicorn main:app --reload) and re-run, or pass --csv FILE.")
    df, stamp = load.read_csv(path)
    print(f"Using saved snapshot {path.name} ({stamp:%Y-%m-%d %H:%M} UTC)")
    return df, stamp


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv")
    ap.add_argument("--url", default=C.API_URL)
    ap.add_argument("--no-fetch", action="store_true")
    ap.add_argument("--region", default=None, help="analyse only the hubs of this region (see config/hubs.csv)")
    ap.add_argument("--types", default=None, help="analyse only these vessel types, e.g. cargo,tanker")
    ap.add_argument("--weather", action="store_true")
    ap.add_argument("--inline-js", action="store_true", help="embed plotly.js in the dashboard (bigger file, works without the CDN)")
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args()

    C.ensure_dirs()
    started = time.time()
    print("== Maritime Traffic Analytics ==")
    raw, stamp = get_data(args)
    hubs = geo.load_hubs(C.HUBS_CSV)
    region = C.REGION_NAME
    if args.region:
        if args.region not in set(hubs["region"]):
            sys.exit(f"Unknown region '{args.region}'. Available: {sorted(set(hubs['region']))}")
        hubs, region = hubs[hubs["region"] == args.region].reset_index(drop=True), args.region
    assump = estimates.load_assumptions(C.ASSUMPTIONS_CSV)

    print("\n[1/8] Cleaning")
    df, log = clean.clean(raw, hubs)
    print(f"   {len(raw):,} raw rows -> {len(df):,} clean rows ({len(raw) - len(df):,} removed); see outputs/data/cleaning_log.csv")
    df_all = df
    df = df_all[df_all["is_stale"] == 0].reset_index(drop=True)
    print(f"   {len(df_all) - len(df):,} stale ships (silent over {C.FRESH_MINUTES:g} min) set aside: traffic metrics use the {len(df):,} current ships; "
          f"the dark-fleet analysis uses all {len(df_all):,}")
    filter_note = None
    if args.types:
        keep = [t.strip().lower() for t in args.types.split(",") if t.strip()]
        filter_note = ", ".join(keep)
        df_all, df = df_all[df_all["vessel_type"].isin(keep)].reset_index(drop=True), df[df["vessel_type"].isin(keep)].reset_index(drop=True)
        print(f"   filtered to vessel types {filter_note}: {len(df):,} current ships, {len(df_all):,} incl. silent")
    df_all.to_csv(C.OUT_DATA / "ships_all.csv", index=False)
    df.to_csv(C.OUT_DATA / "ships_clean.csv", index=False)
    log.to_csv(C.OUT_DATA / "cleaning_log.csv", index=False)

    print("\n[2/8] Metrics and estimates")
    m = metrics.compute_all(df, hubs, log, stamp, df_dark=df_all)
    est = estimates.estimate_waiting(df, assump)
    if m["kpis"]["pct_with_length"] == 0:
        print("   NOTE: no ship lengths received, so every ship is 'unknown size' and fuel estimates use medium-ship values (check length_m capture in backend/main.py).")
    if m["kpis"]["pct_type_unknown"] >= 20:
        print(f"   CAUTION: {m['kpis']['pct_type_unknown']}% of ships have no vessel type yet. The backend probably restarted recently; type, IMO and length shares are understated. Re-run after it has been up for several hours before quoting them.")
    print(f"   {m['kpis']['pct_idle']}% of ships are idle (status says under way, speed under 0.5 kn): they are classified by speed, not status.")
    for name in ("hub_table", "zone_table", "speed_zone", "fleet_by_type", "flags_top", "dark_edge", "dark_type", "routes",
                 "completeness", "dest_quality", "status", "size_class", "segments"):
        m[name].to_csv(C.OUT_DATA / f"{name}.csv", index=False)
    pd.Series(m["kpis"], name="value").rename_axis("kpi").reset_index().to_csv(C.OUT_DATA / "kpis.csv", index=False)
    est.to_csv(C.OUT_DATA / "estimates.csv", index=False)

    print("\n[3/8] SQL queries (and cross-check against pandas)")
    res = step("run sql/*.sql", lambda: sqlrun.run_sql(df, hubs, C.SQL_DIR, C.SQL_OUT, C.ANALYSIS_DB, df_all=df_all))
    checks = None
    if res:
        results, errors = res
        for e in errors:
            FAILED.append(f"sql {e}")
        checks = sqlrun.crosscheck(results, m)
        for name, ok in checks:
            print(f"   {'agree   ' if ok else 'DISAGREE'}  {name}")
        print(f"   {len(results)} queries saved to outputs/sql/")

    print("\n[4/8] Charts")
    out = step("static charts", lambda: charts.make_all(m, df, hubs, est))
    if out:
        print(f"   {len(out[0])} charts saved to outputs/charts/" + (f"; problems: {out[1]}" if out[1] else ""))

    print("\n[5/8] Time analysis (history collector data)")
    tr, weather = None, None
    hist = step("load history", lambda: timeseries.load_history(C.HISTORY_DB))
    if hist is not None:
        tr = step("time analysis", lambda: timeseries.analyse(hist, assump))
        if tr:
            tr["daily"].to_csv(C.TIME_OUT / "daily.csv", index=False)
            for key in ("hour_profile", "weekday_profile", "weekly_levels", "monthly_levels", "speed_by_level", "type_queue", "hub_red_share"):
                if key in tr:
                    tr[key].to_csv(C.TIME_OUT / f"{key}.csv", index=False)
            if "excess" in tr:
                tr["excess"]["table"].to_csv(C.TIME_OUT / "excess_waiting_estimate.csv", index=False)
            tc = step("time charts", lambda: charts.make_time_charts(tr))
            if tc:
                print(f"   {len(tc[0])} time charts saved to outputs/time/")
            if args.weather:
                weather, msg = timeseries.weather_test(tr["daily"])
                print("   weather:", msg or "done")
            st = tr["status"]
            print(f"   history: {st['polls']} polls, {st['usable_days']} usable days")
            for msg in tr["messages"]:
                print("   note:", msg)
    else:
        print("   no history yet. Start analysis/collector.py to build it (the time analysis switches on by itself).")

    print("\n[6/8] Excel workbook")
    step("MaritimeAnalytics.xlsx", lambda: excel.build(C.OUT_DIR / "MaritimeAnalytics.xlsx", m, assump, df, stamp, region))

    print("\n[7/8] Dashboard")
    step("dashboard.html", lambda: dashboard.build(C.OUT_DIR / "dashboard.html", m, df, hubs, est, stamp, region, tr=tr, inline_js=args.inline_js))

    print("\n[8/8] Findings report")
    step("FINDINGS.md", lambda: report.build(C.OUT_DIR / "FINDINGS.md", m, est, df, hubs, stamp, region, assump, tr=tr, weather=weather, sql_checks=checks, filter_note=filter_note))

    print(f"\nDone in {time.time() - started:.0f}s. Open:")
    print(f"   {C.OUT_DIR / 'dashboard.html'}   (interactive dashboard; needs internet for the map)")
    print(f"   {C.OUT_DIR / 'FINDINGS.md'}      (the written analysis)")
    print(f"   {C.OUT_DIR / 'MaritimeAnalytics.xlsx'}")
    if FAILED:
        print("\nSome steps failed (everything else still ran):")
        for f in FAILED:
            print("  -", f)
        sys.exit(1)


if __name__ == "__main__":
    main()
