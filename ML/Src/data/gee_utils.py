
"""Google Earth Engine extraction utilities.

Features:
- Direct Earth Engine CSV downloads to local storage.
- Yearly/monthly chunking.
- Retry handling.
- Range-aware cache filenames.
- Output manifests to prevent incomplete files being reused.
- No FeatureCollection.getInfo() for time-series extraction.
"""

import json
import time
from pathlib import Path

import ee
import pandas as pd
import requests

from ML.Src.processing.config import REGIONS, BUFFER_M, GEE_PROJECT, raw_dir


# --------------------------------------------------
# EARTH ENGINE INITIALIZATION
# --------------------------------------------------

def init_ee():
    ee.Initialize(project=GEE_PROJECT)
    print(f"[connected] Earth Engine project: {GEE_PROJECT}")


# --------------------------------------------------
# GEOGRAPHY
# --------------------------------------------------

def region_geometry(coords):
    return (
        ee.Geometry.Point([
            coords["longitude"],
            coords["latitude"]
        ])
        .buffer(BUFFER_M)
    )


# --------------------------------------------------
# RETRY HANDLING
# --------------------------------------------------

def _retry(fn, tries=4):

    for attempt in range(tries):

        try:
            return fn()

        except Exception as error:

            if attempt == tries - 1:
                raise

            wait = 5 * (2 ** attempt)

            print(
                f"[retry] Attempt {attempt + 1}/{tries}: "
                f"{error}"
            )

            print(f"[retry] Waiting {wait} seconds...")

            time.sleep(wait)


# --------------------------------------------------
# DATE CHUNKING
# --------------------------------------------------

def date_chunks(start, end, freq="year"):
    """Yield inclusive date chunks."""

    cur = pd.Timestamp(start)
    final = pd.Timestamp(end)

    while cur <= final:

        if freq == "year":

            nxt = pd.Timestamp(
                cur.year + 1, 1, 1
            )

        elif freq == "month":

            nxt = (
                cur.replace(day=1)
                + pd.offsets.MonthBegin(1)
            )

        else:
            raise ValueError(
                "freq must be 'year' or 'month'"
            )

        chunk_end = min(
            nxt - pd.Timedelta(days=1),
            final
        )

        yield cur, chunk_end

        cur = chunk_end + pd.Timedelta(days=1)


# --------------------------------------------------
# DIRECT EARTH ENGINE CSV DOWNLOAD
# --------------------------------------------------

def _download_fc_csv(fc, selectors, output_file):

    output_file = Path(output_file)

    temporary_file = output_file.with_suffix(".part")

    def perform_download():

        url = fc.getDownloadURL(
            filetype="csv",
            selectors=selectors,
            filename=output_file.stem
        )

        with requests.get(
            url,
            stream=True,
            timeout=(30, 300)
        ) as response:

            response.raise_for_status()

            with open(temporary_file, "wb") as file:

                for chunk in response.iter_content(
                    chunk_size=1024 * 1024
                ):

                    if chunk:
                        file.write(chunk)

        # Validate the downloaded CSV before accepting it.
        downloaded = pd.read_csv(temporary_file)

        if downloaded.empty:
            raise ValueError(
                f"Earth Engine returned an empty file: "
                f"{output_file.name}"
            )

        missing_columns = [
            col for col in selectors
            if col not in downloaded.columns
        ]

        if missing_columns:
            raise ValueError(
                f"Missing columns: {missing_columns}"
            )

        temporary_file.replace(output_file)

        return len(downloaded)

    try:

        rows = _retry(perform_download)

        print(
            f"[downloaded] {output_file.name} "
            f"| rows={rows} "
            f"| size={output_file.stat().st_size / 1024:.1f} KB"
        )

        return rows

    except Exception:

        if temporary_file.exists():
            temporary_file.unlink()

        raise


# --------------------------------------------------
# MANIFEST / RANGE VALIDATION
# --------------------------------------------------

def _manifest_path(out_file):

    return out_file.with_suffix(".meta.json")


def _already_complete(out_file, start, end):

    manifest = _manifest_path(out_file)

    if not out_file.exists() or not manifest.exists():
        return False

    try:

        metadata = json.loads(
            manifest.read_text(encoding="utf-8")
        )

        return (
            metadata.get("start") == str(start)
            and metadata.get("end") == str(end)
            and out_file.stat().st_size > 0
        )

    except Exception:
        return False


def _write_manifest(out_file, start, end, rows):

    metadata = {
        "start": str(start),
        "end": str(end),
        "rows": int(rows),
        "file": out_file.name,
        "download_method": "Earth Engine direct CSV"
    }

    _manifest_path(out_file).write_text(
        json.dumps(metadata, indent=4),
        encoding="utf-8"
    )


# --------------------------------------------------
# FINALIZE REGION DATA
# --------------------------------------------------

def _finish(parts, region, out_file, start, end):

    df = (
        pd.concat(parts, ignore_index=True)
        if parts
        else pd.DataFrame()
    )

    if df.empty:

        print(f"[warning] No data for {region}")
        return

    if "date" not in df.columns:

        raise ValueError(
            f"Date column missing for {region}"
        )

    df["date"] = pd.to_datetime(
        df["date"],
        errors="coerce"
    )

    df = df.dropna(subset=["date"])

    df = df.sort_values("date")

    df = df.drop_duplicates()

    df.insert(1, "region", region)

    df.to_csv(out_file, index=False)

    _write_manifest(
        out_file,
        start,
        end,
        len(df)
    )

    print(
        f"[saved] {out_file.name} "
        f"| rows={len(df)} "
        f"| {df['date'].min().date()} "
        f"to {df['date'].max().date()}"
    )


# --------------------------------------------------
# DAILY DATASETS
# --------------------------------------------------

def extract_daily(
    name,
    collection_id,
    bands,
    daily_fn,
    scale,
    start,
    end,
    chunk="year"
):

    """Extract one regional observation per calendar day."""

    if pd.Timestamp(start) > pd.Timestamp(end):
        raise ValueError("Start date must not exceed end date")

    if isinstance(collection_id, str):

        ic = ee.ImageCollection(
            collection_id
        )

    else:

        ic = ee.ImageCollection(collection_id)

    ic = ic.select(bands)

    out_dir = raw_dir(name)

    cache = out_dir / "_cache"

    cache.mkdir(parents=True, exist_ok=True)

    selectors = ["date"] + list(bands)

    for region, coords in REGIONS.items():

        out_file = (
            out_dir
            / f"{name.lower()}_{region.lower()}.csv"
        )

        if _already_complete(
            out_file, start, end
        ):

            print(f"[skip] Complete file: {out_file.name}")
            continue

        geom = region_geometry(coords)

        parts = []

        for s, e in date_chunks(start, end, chunk):

            # Both dates are included in the cache key.
            cache_file = cache / (
                f"{region}_{s:%Y%m%d}_{e:%Y%m%d}.csv"
            )

            if cache_file.exists():

                try:

                    cached = pd.read_csv(cache_file)

                    if (
                        not cached.empty
                        and set(selectors).issubset(cached.columns)
                    ):

                        parts.append(cached)

                        print(
                            f"[cache] {region} "
                            f"{s.date()} -> {e.date()}"
                        )

                        continue

                except Exception:
                    cache_file.unlink(missing_ok=True)

            print(
                f"[{name}] {region}: "
                f"{s.date()} -> {e.date()}"
            )

            n_days = (e - s).days + 1

            start_string = s.strftime("%Y-%m-%d")

            def per_day(i):

                d0 = (
                    ee.Date(start_string)
                    .advance(ee.Number(i), "day")
                )

                daily_collection = ic.filterDate(
                    d0,
                    d0.advance(1, "day")
                )

                img = daily_fn(daily_collection)

                stats = img.reduceRegion(
                    reducer=ee.Reducer.mean(),
                    geometry=geom,
                    scale=scale,
                    maxPixels=1e9,
                    tileScale=4
                )

                return (
                    ee.Feature(None, stats)
                    .set(
                        "date",
                        d0.format("YYYY-MM-dd")
                    )
                )

            fc = ee.FeatureCollection(
                ee.List.sequence(
                    0, n_days - 1
                ).map(per_day)
            )

            # Keep only selected properties.
            fc = fc.select(
                selectors,
                None,
                False
            )

            _download_fc_csv(
                fc,
                selectors,
                cache_file
            )

            parts.append(
                pd.read_csv(cache_file)
            )

        _finish(
            parts,
            region,
            out_file,
            start,
            end
        )


# --------------------------------------------------
# IMAGE-BASED DATASETS
# --------------------------------------------------


def extract_images(
    name,
    builder,
    scale,
    start,
    end,
    chunk="month",
    filter_bounds=True
):
    """Extract irregular satellite-image observations.

    filter_bounds=False is needed for MODIS, whose sinusoidal projection
    cannot be intersected with an EPSG:4326 geometry in filterBounds().
    reduceRegion still clips each image to the region.
    """

    out_dir = raw_dir(name)
    cache = out_dir / "_cache"
    cache.mkdir(parents=True, exist_ok=True)

    bands = getattr(builder, "band_names", None)

    if not bands:
        raise ValueError(
            f"{name}: builder.band_names must be defined"
        )

    selectors = ["date"] + list(bands)

    for region, coords in REGIONS.items():

        out_file = (
            out_dir / f"{name.lower()}_{region.lower()}.csv"
        )

        if _already_complete(out_file, start, end):
            print(f"[skip] Complete file: {out_file.name}")
            continue

        geom = region_geometry(coords)
        parts = []

        for s, e in date_chunks(start, end, chunk):

            cache_file = cache / (
                f"{region}_{s:%Y%m%d}_{e:%Y%m%d}.csv"
            )

            if cache_file.exists():
                try:
                    cached = pd.read_csv(cache_file)

                    if set(selectors).issubset(cached.columns):
                        parts.append(cached)
                        print(f"[cache] {cache_file.name}")
                        continue

                except Exception:
                    cache_file.unlink(missing_ok=True)

            print(
                f"[{name}] {region}: "
                f"{s.date()} -> {e.date()}"
            )

            ic = builder(geom)

            if filter_bounds:
                ic = ic.filterBounds(geom)

            ic = ic.filterDate(
                s.strftime("%Y-%m-%d"),
                (e + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
            )

            # This is a small scalar request, not a table download.
            image_count = _retry(lambda: ic.size().getInfo())

            if image_count == 0:
                print(f"[no images] {region} {s.date()}")

                pd.DataFrame(columns=selectors).to_csv(
                    cache_file,
                    index=False
                )

                parts.append(pd.DataFrame(columns=selectors))
                continue

            def per_img(img):

                stats = img.reduceRegion(
                    reducer=ee.Reducer.mean(),
                    geometry=geom,
                    scale=scale,
                    maxPixels=1e9,
                    tileScale=4
                )

                return (
                    ee.Feature(None, stats)
                    .set(
                        "date",
                        img.date().format("YYYY-MM-dd")
                    )
                )

            fc = ee.FeatureCollection(ic.map(per_img))

            fc = fc.select(selectors, None, False)

            _download_fc_csv(
                fc,
                selectors,
                cache_file
            )

            parts.append(pd.read_csv(cache_file))

        _finish(
            parts,
            region,
            out_file,
            start,
            end
        )


# --------------------------------------------------
# STATIC DATASETS
# --------------------------------------------------

def extract_static(
    name,
    image,
    scale,
    reducer=None
):

    """Extract one static row per region."""

    out_dir = raw_dir(name)

    out_file = (
        out_dir
        / f"{name.lower()}_all_regions.csv"
    )

    if out_file.exists():

        print(f"[skip] {out_file.name}")
        return

    reducer = reducer or ee.Reducer.mean()

    rows = []

    for region, coords in REGIONS.items():

        print(f"[{name}] Extracting {region}...")

        stats = _retry(
            lambda: image.reduceRegion(
                reducer=reducer,
                geometry=region_geometry(coords),
                scale=scale,
                maxPixels=1e10,
                tileScale=4
            ).getInfo()
        )

        stats["region"] = region

        rows.append(stats)

    df = pd.DataFrame(rows)

    df.to_csv(out_file, index=False)

    print(f"[saved] {out_file}")
    print(df.T)
