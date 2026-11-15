"""Shows (1) the END_DATE your scripts use, (2) where your local files end,
(3) the newest date Earth Engine has for each dataset.

Run:  python ML\\Src\\data\\check_latest.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import ee
import pandas as pd

from ML.Src.processing.config import END_DATE, GEE_PROJECT, raw_dir

print("=" * 55)
print("1. END_DATE in config:", END_DATE)

print("\n2. Where your LOCAL files end")
local = {
    "CHIRPS":     raw_dir("CHIRPS") / "chirps_arsi.csv",
    "NASA_POWER": raw_dir("NASA_POWER") / "nasa_power_arsi.csv",
    "ERA5_LAND":  raw_dir("ERA5_LAND") / "era5_land_arsi.csv",
    "GPM_IMERG":  raw_dir("GPM_IMERG") / "gpm_imerg_arsi.csv",
    "SMAP_L4":    raw_dir("SMAP_L4") / "smap_l4_arsi.csv",
    "MODIS":      raw_dir("MODIS") / "modis_arsi.csv",
}
for name, path in local.items():
    if path.exists():
        d = pd.read_csv(path, usecols=["date"], parse_dates=["date"])["date"]
        print(f"  {name:<11} {d.min().date()} -> {d.max().date()}  ({len(d)} rows)")
    else:
        print(f"  {name:<11} file not found: {path.name}")

print("\n3. Newest date Earth Engine HAS")
ee.Initialize(project=GEE_PROJECT)
sources = {
    "CHIRPS":    "UCSB-CHG/CHIRPS/DAILY",
    "ERA5_LAND": "ECMWF/ERA5_LAND/DAILY_AGGR",
    "GPM_IMERG": "NASA/GPM_L3/IMERG_V07",
    "SMAP_L3":   "NASA/SMAP/SPL3SMP_E/006",
    "SMAP_L4":   "NASA/SMAP/SPL4SMGP/008",
    "MODIS":     "MODIS/061/MOD13Q1",
    "SENTINEL2": "COPERNICUS/S2_SR_HARMONIZED",
}
for name, cid in sources.items():
    try:
        ms = ee.ImageCollection(cid).aggregate_max("system:time_start").getInfo()
        print(f"  {name:<11} {pd.Timestamp(ms, unit='ms').date()}")
    except Exception as e:
        print(f"  {name:<11} error: {str(e)[:80]}")
print("=" * 55)