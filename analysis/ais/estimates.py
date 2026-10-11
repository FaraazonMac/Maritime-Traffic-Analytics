"""Fuel, CO2 and cost estimates for ships waiting at anchor. These are ESTIMATES driven by assumptions.csv."""
import pandas as pd

from .config import SIZE_LABELS, UNKNOWN_SIZE

SIZE_ORDER = SIZE_LABELS + [UNKNOWN_SIZE]
SCENARIOS = ("low", "central", "high")


def load_assumptions(path):
    return pd.read_csv(path)


def lookup(assump, parameter, size_class="all"):
    r = assump[(assump["parameter"] == parameter) & (assump["size_class"] == size_class)]
    if r.empty:
        raise KeyError(f"assumption missing: {parameter} / {size_class}")
    r = r.iloc[0]
    return {"low": float(r["low"]), "central": float(r["central"]), "high": float(r["high"])}


def estimate_waiting(df, assump):
    """Daily fuel, CO2 and cost of ships currently at anchor within a hub radius, as low/central/high ranges.

    Low uses every low assumption together, high uses every high one, so the range is deliberately wide.
    """
    waiting = df[(df["status_group"] == "at_anchor") & df["hub"].notna()]
    counts = waiting.groupby("size_class").size().reindex(SIZE_ORDER, fill_value=0)
    price = lookup(assump, "fuel_price_usd_per_t")
    co2 = lookup(assump, "co2_t_per_t_fuel")
    opex = lookup(assump, "vessel_opex_usd_per_day")
    rows = []
    for sc, n in counts.items():
        fuel = lookup(assump, "fuel_at_anchor_t_per_day", sc)
        row = {"size_class": sc, "ships_waiting": int(n)}
        for s in SCENARIOS:
            f = n * fuel[s]
            row[f"fuel_t_{s}"] = f
            row[f"co2_t_{s}"] = f * co2[s]
            row[f"cost_usd_{s}"] = n * (opex[s] + fuel[s] * price[s])
        rows.append(row)
    t = pd.DataFrame(rows)
    total = t.drop(columns="size_class").sum()
    total_row = pd.DataFrame([{"size_class": "Total", **total.to_dict()}])
    return pd.concat([t, total_row], ignore_index=True)
