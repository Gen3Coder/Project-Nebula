"""Download / UPDATE NASA POWER daily weather up to END_DATE (or the newest day POWER has).

Run:  python ML\\Src\\data\\download_nasa_power.py
Output: Data/Raw/NASA_POWER/nasa_power_<region>.csv  + nasa_power_all_regions.csv
"""
import sys
from pathlib import Path

# Make "ML.Src..." importable no matter where the script is started from
# (this file lives in <project>/ML/Src/data/, so the project root is 3 levels up)
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import time

import pandas as pd
import requests

from ML.Src.processing.config import REGIONS, START_DATE, END_DATE, raw_dir

URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
PARAMETERS = ["T2M", "T2M_MAX", "T2M_MIN", "RH2M", "WS10M", "ALLSKY_SFC_SW_DWN"]
FILL_VALUE = -999            # POWER's code for "no data"
LAG_DAYS = 5                 # POWER lags real time by a few days; we stay safely behind it

TARGET_END = min(
    pd.Timestamp(END_DATE),
    pd.Timestamp.today().normalize() - pd.Timedelta(days=LAG_DAYS),
)


def download_region(name, coords, out_dir):
    out_file = out_dir / f"nasa_power_{name.lower()}.csv"

    if out_file.exists():
        existing = pd.read_csv(out_file, parse_dates=["date"])
        if existing["date"].max() >= TARGET_END:
            print(f"[skip] {out_file.name} already reaches {existing['date'].max().date()}")
            return existing
        print(f"[update] {out_file.name} ends {existing['date'].max().date()}, "
              f"target {TARGET_END.date()}")

    params = {
        "parameters": ",".join(PARAMETERS),
        "community": "AG",
        "latitude": coords["latitude"],
        "longitude": coords["longitude"],
        "start": START_DATE.replace("-", ""),
        "end": TARGET_END.strftime("%Y%m%d"),
        "format": "JSON",
        "time-standard": "UTC",
    }

    for attempt in range(1, 5):
        try:
            print(f"[download] {name} (attempt {attempt})")
            r = requests.get(URL, params=params, timeout=300)
            r.raise_for_status()
            data = r.json()["properties"]["parameter"]
            break
        except Exception as e:
            print(f"  failed: {e}")
            if attempt == 4:
                raise
            time.sleep(10 * attempt)

    df = pd.DataFrame(data)
    df.index = pd.to_datetime(df.index, format="%Y%m%d")
    df.index.name = "date"
    df = df.astype(float)
    df = df.mask(df == FILL_VALUE)   # -999 -> NaN (real float NaN, not pd.NA)

    # drop trailing days where POWER has no data yet
    valid = df.dropna(how="all")
    df = df.loc[:valid.index.max()].reset_index()
    df.insert(1, "region", name)
    df.to_csv(out_file, index=False)
    print(f"[saved] {out_file.name} rows={len(df)} ends {df['date'].max().date()}")
    return df


def main():
    out_dir = raw_dir("NASA_POWER")
    frames = [download_region(n, c, out_dir) for n, c in REGIONS.items()]
    combined = pd.concat(frames, ignore_index=True)
    combined.to_csv(out_dir / "nasa_power_all_regions.csv", index=False)
    print(combined.groupby("region")["date"].agg(["min", "max", "count"]))
    print("Missing values per column:\n", combined.isna().sum())


if __name__ == "__main__":
    main()