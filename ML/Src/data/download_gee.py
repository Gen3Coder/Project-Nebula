"""
NASA Space Apps 2026
Agricultural False-Start Early Warning System

Google Earth Engine data extraction (updated to pull up to END_DATE, e.g. 2026-11-15).

New in this version:
- Every time-series dataset asks Earth Engine for its LATEST available image and
  clips the end date to it. Satellite/reanalysis products lag behind "today", so
  requesting empty future days would create empty chunks and failed downloads.
- Previously downloaded years are reused from the cache, so only the new period
  (2026) is downloaded.

Datasets:
1. ERA5-Land   2. GPM IMERG   3. SMAP L3   4. SMAP L4   5. MODIS
6. Sentinel-2  7. SRTM        8. SoilGrids 9. ESA WorldCover

Raw data is saved under: ML/Data/Raw/
"""

import sys
from pathlib import Path

# Make "ML.Src..." importable no matter where the script is started from
# (this file lives in <project>/ML/Src/data/, so the project root is 3 levels up)
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import argparse
import traceback

import pandas as pd
import ee

import gee_utils as g

from ML.Src.processing.config import START_DATE, END_DATE


# ==========================================================
# HELPER FUNCTIONS
# ==========================================================

def latest_available(collection, sub_daily=False, end=None):
    """Date of the newest image in an Earth Engine collection.

    Only the last ~400 days before `end` are scanned first (scanning a huge archive such as
    Sentinel-2 from the beginning is very slow). If nothing is found there, the whole
    collection is scanned.

    sub_daily=True drops the last day, because a collection of half-hourly or
    3-hourly images may contain only part of that day (a partial daily total
    would look like a dry day).
    """
    ic = ee.ImageCollection(collection) if isinstance(collection, str) else collection

    millis = None

    if end is not None:
        window_end = (pd.Timestamp(end) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        window_start = (pd.Timestamp(end) - pd.Timedelta(days=400)).strftime("%Y-%m-%d")
        recent = ic.filterDate(window_start, window_end)
        millis = g._retry(lambda: recent.aggregate_max("system:time_start").getInfo())

    if millis is None:
        millis = g._retry(lambda: ic.aggregate_max("system:time_start").getInfo())

    if millis is None:
        return None

    latest = pd.Timestamp(millis, unit="ms").normalize()

    if sub_daily:
        latest -= pd.Timedelta(days=1)

    return latest


def valid_date_range(start, end, available_from, dataset_name,
                     collection=None, sub_daily=False):
    """
    Clip a requested date range to a dataset's availability:
    - start is moved forward to the first date the dataset exists
    - end is moved back to the newest image Earth Engine has (if collection given)
    Returns None if there is no overlap.
    """

    effective_start = max(
        pd.Timestamp(start),
        pd.Timestamp(available_from)
    )

    effective_end = pd.Timestamp(end)

    if collection is not None:

        latest = latest_available(collection, sub_daily, end=effective_end)

        if latest is not None and latest < effective_end:
            print(
                f"[info] {dataset_name}: newest data is {latest.date()} "
                f"(requested up to {effective_end.date()}). "
                f"Downloading up to {latest.date()}."
            )
            effective_end = latest

    if effective_start > effective_end:
        print(
            f"[skip] {dataset_name}: "
            f"No data available in the requested period."
        )
        return None

    return (
        effective_start.strftime("%Y-%m-%d"),
        effective_end.strftime("%Y-%m-%d")
    )


# ==========================================================
# 1. ERA5-LAND
# ==========================================================

def era5land(start, end):

    collection_id = "ECMWF/ERA5_LAND/DAILY_AGGR"

    date_range = valid_date_range(
        start,
        end,
        "1981-01-01",
        "ERA5-Land",
        collection=collection_id
    )

    if date_range is None:
        return

    effective_start, effective_end = date_range

    bands = [
        "temperature_2m",
        "dewpoint_temperature_2m",
        "total_precipitation_sum",
        "u_component_of_wind_10m",
        "v_component_of_wind_10m",
        "surface_solar_radiation_downwards_sum",
        "volumetric_soil_water_layer_1",
        "volumetric_soil_water_layer_2",
        "volumetric_soil_water_layer_3",
        "volumetric_soil_water_layer_4",
    ]

    # Units: Kelvin, metres, J/m2, m3/m3, m/s

    g.extract_daily(
        name="ERA5_LAND",
        collection_id=collection_id,
        bands=bands,
        daily_fn=lambda collection: collection.mean(),
        scale=11132,
        start=effective_start,
        end=effective_end,
        chunk="year"
    )


# ==========================================================
# 2. GPM IMERG
# ==========================================================

def imerg(start, end):

    collection_id = "NASA/GPM_L3/IMERG_V07"

    date_range = valid_date_range(
        start,
        end,
        "1998-01-01",
        "GPM IMERG",
        collection=collection_id,
        sub_daily=True
    )

    if date_range is None:
        return

    effective_start, effective_end = date_range

    def daily_precipitation(collection):

        # IMERG precipitation is a rate (mm/hour).
        # Each half-hour image contributes rate * 0.5 hours.

        return collection.map(
            lambda image: image.multiply(0.5)
        ).sum()

    g.extract_daily(
        name="GPM_IMERG",
        collection_id=collection_id,
        bands=["precipitation"],
        daily_fn=daily_precipitation,
        scale=11132,
        start=effective_start,
        end=effective_end,
        chunk="month"
    )


# ==========================================================
# 3. SMAP L3
# ==========================================================

def smap_l3(start, end):

    # The newest data comes from version 006.
    date_range = valid_date_range(
        start,
        end,
        "2015-03-31",
        "SMAP L3",
        collection="NASA/SMAP/SPL3SMP_E/006"
    )

    if date_range is None:
        return

    effective_start, effective_end = date_range

    # Earth Engine filterDate() uses an exclusive end date.
    exclusive_end = (
        pd.Timestamp(effective_end)
        + pd.Timedelta(days=1)
    ).strftime("%Y-%m-%d")

    # Version 005: historical observations.
    old_collection = (
        ee.ImageCollection("NASA/SMAP/SPL3SMP_E/005")
        .filterDate("2015-03-31", "2023-12-04")
    )

    # Version 006: observations from December 4, 2023.
    new_collection = (
        ee.ImageCollection("NASA/SMAP/SPL3SMP_E/006")
        .filterDate("2023-12-04", exclusive_end)
    )

    collection = old_collection.merge(new_collection)

    g.extract_daily(
        name="SMAP_L3",
        collection_id=collection,
        bands=[
            "soil_moisture_am",
            "soil_moisture_pm"
        ],
        daily_fn=lambda c: c.mean(),
        scale=9000,
        start=effective_start,
        end=effective_end,
        chunk="year"
    )


# ==========================================================
# 4. SMAP L4
# ==========================================================

def smap_l4(start, end):

    collection_id = "NASA/SMAP/SPL4SMGP/008"

    date_range = valid_date_range(
        start,
        end,
        "2015-03-31",
        "SMAP L4",
        collection=collection_id,
        sub_daily=True
    )

    if date_range is None:
        return

    effective_start, effective_end = date_range

    g.extract_daily(
        name="SMAP_L4",
        collection_id=collection_id,
        bands=[
            "sm_surface",
            "sm_rootzone"
        ],
        daily_fn=lambda c: c.mean(),
        scale=11000,
        start=effective_start,
        end=effective_end,
        chunk="year"
    )


# ==========================================================
# 5. MODIS VEGETATION INDICES
# ==========================================================

def modis(start, end):

    collection_id = "MODIS/061/MOD13Q1"

    date_range = valid_date_range(
        start,
        end,
        "2000-02-18",
        "MODIS",
        collection=collection_id
    )

    if date_range is None:
        return

    effective_start, effective_end = date_range

    def builder(geom):

        def prepare_image(image):

            # SummaryQA: 0 good, 1 marginal, 2 snow/ice, 3 cloudy
            good_quality = image.select("SummaryQA").lte(1)

            vegetation = (
                image.select(["NDVI", "EVI"])
                .updateMask(good_quality)
                .multiply(0.0001)
            )

            return vegetation.copyProperties(
                image,
                ["system:time_start"]
            )

        return ee.ImageCollection(collection_id).map(prepare_image)

    builder.band_names = ["NDVI", "EVI"]

    g.extract_images(
        name="MODIS",
        builder=builder,
        scale=250,
        start=effective_start,
        end=effective_end,
        chunk="month",
        filter_bounds=False
    )


# ==========================================================
# 6. SENTINEL-2
# ==========================================================

def sentinel2(start, end):

    collection_id = "COPERNICUS/S2_SR_HARMONIZED"

    date_range = valid_date_range(
        start,
        end,
        "2017-01-01",
        "Sentinel-2",
        collection=collection_id
    )

    if date_range is None:
        return

    effective_start, effective_end = date_range

    def builder(geom):

        def prepare_image(image):

            scl = image.select("SCL")

            # Basic mask, not a complete cloud-shadow removal algorithm.
            good_quality = scl.gte(4).And(scl.lte(7))

            ndvi = image.normalizedDifference(["B8", "B4"]).rename("NDVI")
            ndre = image.normalizedDifference(["B8", "B5"]).rename("NDRE")
            ndmi = image.normalizedDifference(["B8", "B11"]).rename("NDMI")

            output = (
                ndvi
                .addBands(ndre)
                .addBands(ndmi)
                .updateMask(good_quality)
            )

            return output.copyProperties(
                image,
                ["system:time_start"]
            )

        return (
            ee.ImageCollection(collection_id)
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 70))
            .map(prepare_image)
        )

    builder.band_names = ["NDVI", "NDRE", "NDMI"]

    # Several tiles can share a date; average them by date in processing.

    g.extract_images(
        name="SENTINEL2",
        builder=builder,
        scale=100,
        start=effective_start,
        end=effective_end,
        chunk="month"
    )


# ==========================================================
# 7. SRTM TERRAIN (static)
# ==========================================================

def srtm(start, end):

    terrain = ee.Terrain.products(
        ee.Image("USGS/SRTMGL1_003")
    ).select(["elevation", "slope", "aspect"])

    reducer = (
        ee.Reducer.mean()
        .combine(ee.Reducer.minMax(), sharedInputs=True)
        .combine(ee.Reducer.stdDev(), sharedInputs=True)
    )

    g.extract_static(
        name="SRTM",
        image=terrain,
        scale=90,
        reducer=reducer
    )


# ==========================================================
# 8. SOILGRIDS (static)
# ==========================================================

def soilgrids(start, end):

    depths = ["0-5cm", "5-15cm", "15-30cm"]
    properties = ["clay", "sand", "silt", "soc", "bdod"]

    image = None

    for prop in properties:

        band_names = [f"{prop}_{depth}_mean" for depth in depths]

        layer = (
            ee.Image(f"projects/soilgrids-isric/{prop}_mean")
            .select(band_names)
        )

        image = layer if image is None else image.addBands(layer)

    g.extract_static(
        name="SOILGRIDS",
        image=image,
        scale=250
    )


# ==========================================================
# 9. ESA WORLDCOVER (static)
# ==========================================================

def worldcover(start, end):

    world_cover = (
        ee.ImageCollection("ESA/WorldCover/v200")
        .first()
        .select("Map")
    )

    cropland_fraction = world_cover.eq(40).rename("cropland_fraction")

    g.extract_static(
        name="WORLDCOVER",
        image=cropland_fraction,
        scale=30
    )


# ==========================================================
# JOB REGISTRY
# ==========================================================

JOBS = {
    "era5land": era5land,
    "imerg": imerg,
    "smap_l3": smap_l3,
    "smap_l4": smap_l4,
    "modis": modis,
    "sentinel2": sentinel2,
    "srtm": srtm,
    "soilgrids": soilgrids,
    "worldcover": worldcover,
}


# ==========================================================
# MAIN
# ==========================================================

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Download agricultural climate and "
            "satellite datasets using Google Earth Engine."
        )
    )

    parser.add_argument(
        "datasets",
        nargs="+",
        choices=list(JOBS.keys()) + ["all"],
        help="Dataset names or 'all'."
    )

    parser.add_argument("--start", default=START_DATE, help="Start date YYYY-MM-DD.")
    parser.add_argument("--end", default=END_DATE, help="End date YYYY-MM-DD.")

    args = parser.parse_args()

    if pd.Timestamp(args.start) > pd.Timestamp(args.end):
        parser.error("Start date must not be later than end date.")

    g.init_ee()

    if "all" in args.datasets:
        names = list(JOBS.keys())
    else:
        names = list(dict.fromkeys(args.datasets))

    successful = []
    failed = []

    print("\n" + "=" * 60)
    print(" AGRICULTURAL DATA EXTRACTION")
    print("=" * 60)
    print(f"Start date: {args.start}")
    print(f"End date:   {args.end}")
    print(f"Datasets:   {', '.join(names)}")

    for name in names:

        print("\n" + "=" * 60)
        print(f" STARTING: {name.upper()}")
        print("=" * 60)

        try:
            JOBS[name](args.start, args.end)
            successful.append(name)
            print(f"\n[SUCCESS] {name.upper()} completed.")

        except Exception as error:
            failed.append({"dataset": name, "error": str(error)})
            print(f"\n[FAILED] {name.upper()}")
            print(f"Reason: {error}")
            traceback.print_exc()
            print("\nContinuing with the next dataset...")

    print("\n" + "=" * 60)
    print(" EXTRACTION SUMMARY")
    print("=" * 60)

    print("\nSuccessful datasets:")
    for name in successful:
        print(f"  [OK] {name}")

    print("\nFailed datasets:")
    for item in failed:
        print(f"  [FAILED] {item['dataset']}")
        print(f"           {item['error']}")

    print("\n" + "=" * 60)
    print(f"Completed: {len(successful)} / {len(names)}")
    print(f"Failed:    {len(failed)} / {len(names)}")
    print("=" * 60)

    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()