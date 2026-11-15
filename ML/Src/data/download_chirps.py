import io
import time

import ee
import pandas as pd
import requests

from config import REGIONS, BUFFER_M, GEE_PROJECT, END_DATE, raw_dir

START_YEAR = 1981
END = pd.Timestamp(END_DATE)

OUT_DIR = raw_dir("CHIRPS")
OUT_FILE = OUT_DIR / "chirps_daily_1981_2025.csv"  # name kept so other scripts keep working
CACHE_DIR = OUT_DIR / "_cache"
CACHE_DIR.mkdir(exist_ok=True)

try:
    ee.Initialize(project=GEE_PROJECT)
except Exception:
    ee.Authenticate()
    ee.Initialize(project=GEE_PROJECT)

regions = ee.FeatureCollection([
    ee.Feature(
        ee.Geometry.Point([c["longitude"], c["latitude"]]).buffer(BUFFER_M),
        {"region_name": name},
    )
    for name, c in REGIONS.items()
])

rainfall_all = ee.ImageCollection("UCSB-CHG/CHIRPS/DAILY").select("precipitation")


def extract_daily(image):
    daily_regions = image.reduceRegions(
        collection=regions, reducer=ee.Reducer.mean(), scale=5566
    )
    date = image.date().format("YYYY-MM-dd")
    return daily_regions.map(lambda f: f.set("date", date))


def download_year(year):
    """Download one year (up to END). Only complete past years are cached."""
    cacheable = year < END.year
    cache_file = CACHE_DIR / f"chirps_{year}.csv"

    if cacheable and cache_file.exists():
        return pd.read_csv(cache_file).rename(columns={"precipitation_mm": "mean"})

    start = f"{year}-01-01"
    stop = min(pd.Timestamp(year + 1, 1, 1), END + pd.Timedelta(days=1)).strftime("%Y-%m-%d")

    table = rainfall_all.filterDate(start, stop).map(extract_daily).flatten()

    df = None
    for attempt in range(1, 5):
        try:
            url = table.getDownloadURL(
                filetype="CSV", selectors=["region_name", "date", "mean"]
            )
            r = requests.get(url, timeout=300)
            r.raise_for_status()
            try:
                df = pd.read_csv(io.StringIO(r.text))
            except pd.errors.EmptyDataError:
                df = pd.DataFrame(columns=["region_name", "date", "mean"])
            break
        except Exception as e:
            print(f"  attempt {attempt} failed: {e}")
            if attempt == 4:
                raise
            time.sleep(10 * attempt)

    if cacheable and not df.empty:
        df.to_csv(cache_file, index=False)
    return df


def main():
    existing = None
    first_year = START_YEAR

    if OUT_FILE.exists():
        existing = pd.read_csv(OUT_FILE, parse_dates=["date"]).rename(
            columns={"precipitation_mm": "mean"})
        last = existing["date"].max()
        print(f"[info] existing file ends {last.date()}")

        if last >= END:
            print("[info] already up to date")
        else:
            # re-download the year containing the last date (it may have been incomplete)
            first_year = last.year if last < pd.Timestamp(last.year, 12, 31) else last.year + 1

    need_download = existing is None or existing["date"].max() < END

    if need_download:
        frames = []
        for year in range(first_year, END.year + 1):
            print(f"[CHIRPS] {year}")
            frames.append(download_year(year))
        new = pd.concat(frames, ignore_index=True)
        new["date"] = pd.to_datetime(new["date"])

        if existing is not None:
            keep = existing[existing["date"] < pd.Timestamp(first_year, 1, 1)]
            df = pd.concat([keep, new], ignore_index=True)
        else:
            df = new
    else:
        df = existing

    df = (df.drop_duplicates(["region_name", "date"])
          .sort_values(["region_name", "date"])
          .reset_index(drop=True))
    df = df[df["date"] <= END]

    df[["region_name", "date", "mean"]].to_csv(OUT_FILE, index=False)

    # per-region files (date, region, precipitation)
    for region, part in df.groupby("region_name"):
        out = part.rename(columns={"region_name": "region", "mean": "precipitation"})
        out[["date", "region", "precipitation"]].to_csv(
            OUT_DIR / f"chirps_{region.lower()}.csv", index=False)

    print(f"\n[saved] {OUT_FILE}")
    print(df.groupby("region_name")["date"].agg(["min", "max", "count"]))
    print("Missing values:", int(df["mean"].isna().sum()))
    print("Negative values:", int((df["mean"] < 0).sum()))


if __name__ == "__main__":
    main()