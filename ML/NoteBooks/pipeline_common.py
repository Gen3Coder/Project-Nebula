"""Shared paths, constants and helper functions for the processing scripts."""
import os
from pathlib import Path

import numpy as np
import pandas as pd

# <project>/ML/Src/processing/pipeline_common.py  ->  parents[2] = <project>/ML
ML_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.environ.get("FS_DATA_DIR", ML_DIR / "Data"))   # FS_DATA_DIR is only for testing
RAW_DIR = DATA_DIR / "Raw"
PROC_DIR = DATA_DIR / "Processed"
PROC_DIR.mkdir(parents=True, exist_ok=True)

# Provisional centroids (NOT official boundaries)
REGIONS = {
    "Arsi":  {"latitude": 7.50, "longitude": 39.20},
    "Bale":  {"latitude": 7.00, "longitude": 40.50},
    "Jimma": {"latitude": 7.67, "longitude": 36.83},
}
REGION_NAMES = list(REGIONS)


# ---------- reading / writing ----------
def read_region_files(folder, prefix):
    """Read Data/Raw/<folder>/<prefix>_<region>.csv for all regions and stack them."""
    frames = []
    for region in REGION_NAMES:
        path = RAW_DIR / folder / f"{prefix}_{region.lower()}.csv"
        if not path.exists():
            raise FileNotFoundError(f"Missing raw file: {path}")
        df = pd.read_csv(path)
        df["date"] = pd.to_datetime(df["date"]).dt.normalize()
        df["region"] = region
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def read_static_file(folder, prefix):
    path = RAW_DIR / folder / f"{prefix}_all_regions.csv"
    if not path.exists():
        raise FileNotFoundError(f"Missing raw file: {path}")
    return pd.read_csv(path)


def save_table(df, name):
    path = PROC_DIR / f"{name}.csv"
    df.to_csv(path, index=False)
    print(f"[saved] {path.name:<32} rows={len(df):>7}  cols={df.shape[1]}")
    return path


def load_table(name, parse_dates=("date",)):
    path = PROC_DIR / f"{name}.csv"
    if not path.exists():
        raise FileNotFoundError(f"{path.name} not found. Run the earlier pipeline steps first.")
    dates = [c for c in parse_dates if c in pd.read_csv(path, nrows=0).columns]
    return pd.read_csv(path, parse_dates=dates)


# ---------- time-grid helpers ----------
def standardize(df, name):
    """Normalize dates, drop duplicate (region, date) rows, sort."""
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    before = len(df)
    df = df.drop_duplicates(["region", "date"]).sort_values(["region", "date"])
    if len(df) != before:
        print(f"  [{name}] dropped {before - len(df)} duplicate rows")
    return df.reset_index(drop=True)


def complete_grid(df, name):
    """One row per region per calendar day. Missing days become empty rows (never filled)."""
    idx = pd.MultiIndex.from_product(
        [REGION_NAMES, pd.date_range(df["date"].min(), df["date"].max())],
        names=["region", "date"],
    )
    out = df.set_index(["region", "date"]).reindex(idx).reset_index()
    missing = len(out) - len(df)
    if missing:
        print(f"  [{name}] {missing} missing region-days added as empty rows")
    cols = ["date", "region"] + [c for c in out.columns if c not in ("date", "region")]
    return out[cols]


# ---------- dry-spell helpers ----------
def run_length_ending(flags):
    """For each position, how many consecutive True values end there (NaN/False resets to 0)."""
    flags = np.asarray(flags, dtype=bool)
    out = np.zeros(len(flags), dtype=float)
    run = 0
    for i, f in enumerate(flags):
        run = run + 1 if f else 0
        out[i] = run
    return out


def longest_run(flags):
    arr = run_length_ending(flags)
    return int(arr.max()) if len(arr) else 0