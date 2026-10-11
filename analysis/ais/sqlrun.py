"""Run the SQL files in sql/ against the cleaned data (SQLite) and cross-check them against the Python results."""
import sqlite3

import pandas as pd


def run_sql(df, hubs, sql_dir, out_dir, db_path, df_all=None):
    """Load the clean ships + hubs into SQLite, run every .sql file, save each result as CSV.

    Returns (results: dict name -> DataFrame, errors: list[str]).
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    def prep(frame):
        s = frame.copy()
        s["imo"] = pd.to_numeric(s["imo"], errors="coerce").astype("float64")
        for c in s.columns:                                  # NaN -> NULL for every text column
            if s[c].dtype == object or str(s[c].dtype).startswith("str"):
                s[c] = s[c].astype(object).where(s[c].notna(), None)
        return s

    ships = prep(df)
    conn = sqlite3.connect(db_path)
    try:
        ships.to_sql("ships", conn, if_exists="replace", index=False)
        prep(df_all if df_all is not None else df).to_sql("ships_all", conn, if_exists="replace", index=False)
        hubs.to_sql("hubs", conn, if_exists="replace", index=False)
        conn.execute("CREATE INDEX IF NOT EXISTS ix_ships_hub ON ships(hub)")
        results, errors = {}, []
        for f in sorted(sql_dir.glob("*.sql")):
            try:
                res = pd.read_sql_query(f.read_text(), conn)
                res.to_csv(out_dir / f"{f.stem}.csv", index=False)
                results[f.stem] = res
            except Exception as e:  # noqa: BLE001
                errors.append(f"{f.name}: {e}")
    finally:
        conn.close()
    return results, errors


def crosscheck(results, m):
    """Compare SQL answers with the pandas answers. Two independent routes to the same numbers."""
    checks = []

    def add(name, ok):
        checks.append((name, bool(ok)))

    try:
        s = results["03_hub_congestion"].set_index("hub")
        p = m["hub_table"].set_index("hub")
        p = p[p["ships_in_radius"] > 0]
        add("hub congestion: ships in radius agree", (s["ships_in_radius"].sort_index() == p["ships_in_radius"].sort_index()).all())
        add("hub congestion: ships at anchor agree", (s["at_anchor"].sort_index() == p["at_anchor"].sort_index()).all())
    except Exception:  # noqa: BLE001
        add("hub congestion cross-check could run", False)
    try:
        s = results["02_fleet_mix"].set_index("vessel_type")["ships"].sort_index()
        p = m["fleet_by_type"].set_index("vessel_type")["ships"].sort_index()
        add("fleet mix: ships per vessel type agree", s.equals(p) or (s.values == p.values).all())
    except Exception:  # noqa: BLE001
        add("fleet mix cross-check could run", False)
    try:
        add("dark fleet: flagged count agrees", int(results["05_dark_fleet"]["dark_flagged"].sum()) == int(m["kpis"]["dark_flagged"]))
    except Exception:  # noqa: BLE001
        add("dark fleet cross-check could run", False)
    try:
        add("waiting by size: total agrees", int(results["09_waiting_by_size"]["ships_waiting"].sum()) == int(m["kpis"]["waiting_near_hubs"]))
    except Exception:  # noqa: BLE001
        add("waiting-by-size cross-check could run", False)
    return checks
