"""Step 1: clean every raw dataset into one tidy table per theme.

Run:  python ML\\Src\\processing\\clean_data.py

Outputs (Data/Processed/):
  static_context.csv      one row per region (soil, terrain, cropland)
  rainfall_daily.csv      CHIRPS rain + wet-day flag                     (model backbone)
  weather_daily.csv       NASA POWER + calculated VPD and ET0            (model input)
  soil_moisture_daily.csv ERA5-Land layers (1981+), SMAP L3/L4 (2015+)   (ERA5 = model input)
  era5_weather_daily.csv  ERA5-Land weather                              (validation only)
  imerg_daily.csv         GPM IMERG rain                                 (validation only)
  vegetation.csv          MODIS + Sentinel-2 NDVI etc.                   (validation only)
"""
import numpy as np
import pandas as pd

from agro_physics import vpd_and_et0
from label_config import TRIGGER_WET_DAY_MM
from pipeline_common import (RAW_DIR, REGIONS, REGION_NAMES, complete_grid,
                             read_region_files, read_static_file, save_table, standardize)


# ------------------------------------------------------------------ static
def clean_static():
    print("\n[static] SRTM + SoilGrids + WorldCover")
    srtm = read_static_file("SRTM", "srtm")
    soil = read_static_file("SOILGRIDS", "soilgrids")
    wc = read_static_file("WORLDCOVER", "worldcover")

    df = srtm.merge(soil, on="region").merge(wc, on="region")
    df.columns = [c.lower().replace("-", "_") for c in df.columns]
    df = df[[c for c in df.columns if not c.startswith(("system", ".geo"))]]

    # Convert SoilGrids mapped units to conventional units
    for col in df.columns:
        if col.startswith(("clay_", "sand_", "silt_")):
            df[col] = df[col] / 10          # g/kg  -> %
        elif col.startswith("soc_"):
            df[col] = df[col] / 10          # dg/kg -> g/kg
        elif col.startswith("bdod_"):
            df[col] = df[col] / 100         # cg/cm3 -> g/cm3 (kg/dm3)

    for col in [c for c in df.columns if c.startswith(("clay_", "sand_", "silt_"))]:
        if df[col].max() > 100 or df[col].min() < 0:
            print(f"  [warn] {col} outside 0-100 %: check the SoilGrids unit conversion")

    df = df.sort_values("region").reset_index(drop=True)
    save_table(df, "static_context")
    print(df.set_index("region").T.round(2).to_string())
    return df


# ------------------------------------------------------------------ rainfall
def load_chirps():
    """Per-region files if present, otherwise the combined CHIRPS file."""
    rename = {"mean": "precipitation", "precipitation_mm": "precipitation", "region_name": "region"}
    try:
        df = read_region_files("CHIRPS", "chirps").rename(columns=rename)
    except FileNotFoundError:
        path = RAW_DIR / "CHIRPS" / "chirps_daily_1981_2025.csv"
        print(f"  per-region CHIRPS files not found, using {path.name}")
        df = pd.read_csv(path, parse_dates=["date"]).rename(columns=rename)
    return df[["date", "region", "precipitation"]]


def clean_rainfall():
    print("\n[rainfall] CHIRPS")
    df = standardize(load_chirps(), "CHIRPS").rename(columns={"precipitation": "rain_mm"})
    neg = (df["rain_mm"] < 0).sum()
    if neg:
        print(f"  [warn] {neg} negative rain values set to empty (fill codes)")
        df.loc[df["rain_mm"] < 0, "rain_mm"] = np.nan
    df = complete_grid(df, "CHIRPS")
    df["wet_day"] = np.where(df["rain_mm"].isna(), np.nan,
                             (df["rain_mm"] >= TRIGGER_WET_DAY_MM).astype(float))
    save_table(df, "rainfall_daily")
    print(df.groupby("region")["date"].agg(["min", "max", "count"]).to_string())
    return df


# ------------------------------------------------------------------ weather
def clean_weather(static):
    print("\n[weather] NASA POWER + VPD + ET0")
    p = standardize(read_region_files("NASA_POWER", "nasa_power"), "POWER")
    p = p.rename(columns={"T2M": "t2m_c", "T2M_MAX": "tmax_c", "T2M_MIN": "tmin_c",
                          "RH2M": "rh_pct", "WS10M": "wind10_ms", "ALLSKY_SFC_SW_DWN": "rad_raw"})

    # NASA POWER radiation units differ by community: MJ/m2/day (typ. 12-26) or kWh/m2/day (typ. 3-7)
    med = p["rad_raw"].median()
    if med < 10:
        print(f"  radiation median {med:.1f} -> treated as kWh/m2/day, converted to MJ/m2/day")
        p["rad_mj"] = p["rad_raw"] * 3.6
    else:
        print(f"  radiation median {med:.1f} -> treated as MJ/m2/day")
        p["rad_mj"] = p["rad_raw"]
    p = p.drop(columns="rad_raw")

    elev = static.set_index("region")["elevation_mean"]
    parts = []
    for region, g in p.groupby("region"):
        g = g.sort_values("date").copy()
        vpd, et0 = vpd_and_et0(
            g["t2m_c"].values, g["tmax_c"].values, g["tmin_c"].values, g["rh_pct"].values,
            g["wind10_ms"].values, g["rad_mj"].values, g["date"].dt.dayofyear.values,
            REGIONS[region]["latitude"], float(elev[region]))
        g["vpd_kpa"], g["et0_mm"] = vpd, et0
        parts.append(g)
    df = complete_grid(pd.concat(parts), "POWER")

    bad = (df["tmax_c"] < df["tmin_c"]).sum()
    if bad:
        print(f"  [warn] {bad} days with Tmax < Tmin")
    print(df[["t2m_c", "tmax_c", "tmin_c", "rh_pct", "wind10_ms", "rad_mj", "vpd_kpa", "et0_mm"]]
          .describe().loc[["min", "mean", "max"]].round(2).to_string())
    save_table(df, "weather_daily")
    return df


# ------------------------------------------------------------------ soil moisture
def clean_soil_moisture():
    print("\n[soil moisture] ERA5-Land (+ SMAP L3, L4)")
    era = standardize(read_region_files("ERA5_LAND", "era5_land"), "ERA5-Land")

    soil = era[["date", "region"]].copy()
    for i in range(1, 5):
        soil[f"sm_l{i}"] = era[f"volumetric_soil_water_layer_{i}"]   # m3/m3; L1 0-7, L2 7-28, L3 28-100, L4 100-289 cm

    l3 = standardize(read_region_files("SMAP_L3", "smap_l3"), "SMAP L3")
    l3["smap_l3_sm"] = l3[["soil_moisture_am", "soil_moisture_pm"]].mean(axis=1, skipna=True)
    l3 = l3.rename(columns={"soil_moisture_am": "smap_l3_am", "soil_moisture_pm": "smap_l3_pm"})
    l3 = l3[["date", "region", "smap_l3_am", "smap_l3_pm", "smap_l3_sm"]]

    l4 = standardize(read_region_files("SMAP_L4", "smap_l4"), "SMAP L4")
    l4 = l4.rename(columns={"sm_surface": "smap_l4_surface", "sm_rootzone": "smap_l4_rootzone"})
    l4 = l4[["date", "region", "smap_l4_surface", "smap_l4_rootzone"]]

    df = soil.merge(l3, on=["date", "region"], how="outer").merge(l4, on=["date", "region"], how="outer")
    df = complete_grid(standardize(df, "soil moisture"), "soil moisture")

    sm_cols = [c for c in df.columns if c.startswith(("sm_l", "smap_"))]
    for c in sm_cols:
        bad = ((df[c] < 0) | (df[c] > 0.8)).sum()
        if bad:
            print(f"  [warn] {c}: {bad} values outside 0-0.8 m3/m3 set to empty")
            df.loc[(df[c] < 0) | (df[c] > 0.8), c] = np.nan
    print(df[sm_cols].describe().loc[["count", "min", "mean", "max"]].round(3).to_string())
    save_table(df, "soil_moisture_daily")
    return df


# ------------------------------------------------------------------ validation-only tables
def clean_era5_weather():
    print("\n[validation] ERA5-Land weather")
    era = standardize(read_region_files("ERA5_LAND", "era5_land"), "ERA5-Land")
    out = pd.DataFrame({
        "date": era["date"], "region": era["region"],
        "era5_t2m_c": era["temperature_2m"] - 273.15,
        "era5_dewpoint_c": era["dewpoint_temperature_2m"] - 273.15,
        "era5_wind10_ms": np.hypot(era["u_component_of_wind_10m"], era["v_component_of_wind_10m"]),
        "era5_rain_mm": era["total_precipitation_sum"] * 1000,
        "era5_rad_mj": era["surface_solar_radiation_downwards_sum"] / 1e6,
    })
    save_table(complete_grid(out, "ERA5 weather"), "era5_weather_daily")


def clean_imerg():
    print("\n[validation] GPM IMERG")
    im = standardize(read_region_files("GPM_IMERG", "gpm_imerg"), "IMERG")
    im = im.rename(columns={"precipitation": "imerg_mm"})[["date", "region", "imerg_mm"]]
    save_table(complete_grid(im, "IMERG"), "imerg_daily")


def clean_vegetation():
    print("\n[validation] MODIS + Sentinel-2")
    modis = read_region_files("MODIS", "modis").rename(columns={"NDVI": "ndvi", "EVI": "evi"})
    modis = modis.groupby(["date", "region"], as_index=False)[["ndvi", "evi"]].mean()
    modis["source"] = "MODIS"

    s2 = read_region_files("SENTINEL2", "sentinel2").rename(
        columns={"NDVI": "ndvi", "NDRE": "ndre", "NDMI": "ndmi"})
    s2 = s2.groupby(["date", "region"], as_index=False)[["ndvi", "ndre", "ndmi"]].mean()   # average tiles per date
    s2["source"] = "Sentinel-2"

    veg = pd.concat([modis, s2], ignore_index=True).sort_values(["source", "region", "date"])
    cols = ["date", "region", "source", "ndvi", "evi", "ndre", "ndmi"]
    save_table(veg[cols], "vegetation")
    print(veg.groupby("source")["ndvi"].describe()[["count", "min", "mean", "max"]].round(2).to_string())


# ------------------------------------------------------------------ main
def main():
    static = clean_static()
    clean_rainfall()
    clean_weather(static)
    clean_soil_moisture()
    clean_era5_weather()
    clean_imerg()
    clean_vegetation()
    print("\nCleaning finished.")


if __name__ == "__main__":
    main()
