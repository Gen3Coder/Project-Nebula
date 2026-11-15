"""Step 2: merge the clean tables into the integrated tables.

Run:  python ML\\Src\\processing\\merge_daily.py

Outputs (Data/Processed/):
  integrated_daily.csv     one row per region per day (rain + weather + soil moisture + static context)
  integrated_seasonal.csv  one row per region per Ethiopian season (Bega, Belg, Kiremt)
  integrated_yearly.csv    one row per region per year

Missing values stay empty. Nothing is filled with invented numbers.
"""
import pandas as pd

from label_config import DRY_DAY_MM
from pipeline_common import load_table, longest_run, save_table

STATIC_KEEP = ["elevation_mean", "slope_mean", "cropland_fraction",
               "clay_0_5cm_mean", "sand_0_5cm_mean", "silt_0_5cm_mean",
               "soc_0_5cm_mean", "bdod_0_5cm_mean"]

# Ethiopian seasons by month. January belongs to the Bega that started the previous October.
SEASON_OF_MONTH = {10: "bega", 11: "bega", 12: "bega", 1: "bega",
                   2: "belg", 3: "belg", 4: "belg", 5: "belg",
                   6: "kiremt", 7: "kiremt", 8: "kiremt", 9: "kiremt"}
NOMINAL_DAYS = {"bega": 123, "belg": 120, "kiremt": 122}


def summarize(g):
    rain = g["rain_mm"]
    return {
        "days_in_period": len(g),
        "days_observed": int(rain.notna().sum()),
        "rain_total_mm": rain.sum(min_count=1),
        "wet_days": g["wet_day"].sum(min_count=1),
        "max_dry_run_days": longest_run((rain < DRY_DAY_MM).values),
        "t2m_mean_c": g["t2m_c"].mean(),
        "tmax_mean_c": g["tmax_c"].mean(),
        "vpd_mean_kpa": g["vpd_kpa"].mean(),
        "et0_total_mm": g["et0_mm"].sum(min_count=1),
        "sm_l1_mean": g["sm_l1"].mean(),
        "sm_l2_mean": g["sm_l2"].mean(),
    }


def build_integrated_daily(rain, weather, soil, static):
    """Rain is the backbone: every other table is attached to it (left joins)."""
    keep = [c for c in STATIC_KEEP if c in static.columns]
    missing = [c for c in STATIC_KEEP if c not in static.columns]
    if missing:
        print(f"[warn] static columns not found and skipped: {missing}")

    df = (rain.merge(weather, on=["date", "region"], how="left")
              .merge(soil, on=["date", "region"], how="left")
              .merge(static[["region"] + keep], on="region", how="left"))
    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.month
    df["doy"] = df["date"].dt.dayofyear
    df = df.sort_values(["region", "date"]).reset_index(drop=True)
    assert not df.duplicated(["region", "date"]).any(), "duplicate region-days in integrated table"
    return df


def build_seasonal(df):
    df = df.copy()
    df["season"] = df["month"].map(SEASON_OF_MONTH)
    df["season_year"] = df["year"] - (df["month"] == 1).astype(int)
    rows = []
    for (region, sy, season), g in df.groupby(["region", "season_year", "season"]):
        row = {"region": region, "season_year": sy, "season": season, **summarize(g)}
        row["complete"] = bool(row["days_observed"] == row["days_in_period"]
                               and row["days_in_period"] >= NOMINAL_DAYS[season])
        rows.append(row)
    return pd.DataFrame(rows)


def build_yearly(df):
    rows = []
    for (region, year), g in df.groupby(["region", "year"]):
        row = {"region": region, "year": year, **summarize(g)}
        row["complete"] = bool(row["days_observed"] >= 365)
        rows.append(row)
    return pd.DataFrame(rows)


def main():
    rain = load_table("rainfall_daily")
    weather = load_table("weather_daily")
    soil = load_table("soil_moisture_daily")
    static = load_table("static_context", parse_dates=())

    df = build_integrated_daily(rain, weather, soil, static)
    save_table(df, "integrated_daily")
    print(df.groupby("region")["date"].agg(["min", "max", "count"]).to_string())
    print("Share of empty values per column (%):")
    print((df.isna().mean() * 100).round(1)[lambda s: s > 0].to_string())

    save_table(build_seasonal(df), "integrated_seasonal")
    save_table(build_yearly(df), "integrated_yearly")


if __name__ == "__main__":
    main()
