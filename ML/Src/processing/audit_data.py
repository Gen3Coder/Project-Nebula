
"""Audit raw agricultural satellite and weather datasets.

Checks:
- Missing expected daily dates.
- Duplicate dates.
- Missing measurements.
- Completely empty observation rows.
- Date coverage.
- Missing files.
- Irregular image datasets and static datasets.

Does not modify raw data.
"""

import argparse
from pathlib import Path

import pandas as pd

from config import START_DATE, END_DATE, REGIONS, ROOT


# --------------------------------------------------
# DATASET COVERAGE CONFIGURATION
# --------------------------------------------------

DAILY_DATASETS = {
    "CHIRPS": "1981-01-01",
    "NASA_POWER": "1981-01-01",
    "ERA5_LAND": "1981-01-01",
    "GPM_IMERG": "1998-01-01",
    "SMAP_L3": "2015-03-31",
    "SMAP_L4": "2015-03-31",
}

# Irregular acquisition datasets.
IRREGULAR_DATASETS = [
    "MODIS",
    "SENTINEL2",
    "ECOSTRESS",
]

# Static datasets: one regional record expected.
STATIC_DATASETS = [
    "SRTM",
    "SOILGRIDS",
    "WORLDCOVER",
]

OUTPUT_DIR = ROOT / "Data" / "Processed"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------
# HELPERS
# --------------------------------------------------

def read_csv_safely(path):

    try:
        return pd.read_csv(path)

    except Exception as error:

        print(f"[read error] {path.name}: {error}")
        return None


def get_expected_dates(dataset, start, end):

    dataset_start = DAILY_DATASETS[dataset]

    actual_start = max(
        pd.Timestamp(start),
        pd.Timestamp(dataset_start)
    )

    actual_end = pd.Timestamp(end)

    if actual_start > actual_end:
        return pd.DatetimeIndex([])

    return pd.date_range(
        actual_start,
        actual_end,
        freq="D"
    )


def measurement_columns(df):

    excluded = {
        "date",
        "region",
        "latitude",
        "longitude",
        "system:index",
    }

    return [
        col for col in df.columns
        if col not in excluded
    ]


# --------------------------------------------------
# DAILY DATA AUDIT
# --------------------------------------------------

def audit_daily(dataset, region, start, end):

    folder = ROOT / "Data" / "Raw" / dataset

    filename = (
        f"{dataset.lower()}_{region.lower()}.csv"
    )

    path = folder / filename

    if not path.exists():

        return {
            "dataset": dataset,
            "region": region,
            "status": "MISSING FILE",
            "expected_days": len(
                get_expected_dates(dataset, start, end)
            ),
            "actual_rows": 0,
            "unique_dates": 0,
            "missing_dates": None,
            "missing_date_pct": None,
            "duplicate_dates": None,
            "all_measurements_missing": None,
            "measurement_null_pct": None,
            "first_date": None,
            "last_date": None,
        }

    df = read_csv_safely(path)

    if df is None or "date" not in df.columns:

        return {
            "dataset": dataset,
            "region": region,
            "status": "INVALID FILE",
            "expected_days": 0,
            "actual_rows": 0,
            "unique_dates": 0,
            "missing_dates": None,
            "missing_date_pct": None,
            "duplicate_dates": None,
            "all_measurements_missing": None,
            "measurement_null_pct": None,
            "first_date": None,
            "last_date": None,
        }

    df["date"] = pd.to_datetime(
        df["date"],
        errors="coerce"
    )

    invalid_dates = int(df["date"].isna().sum())

    df = df.dropna(subset=["date"])

    expected = get_expected_dates(
        dataset, start, end
    )

    actual_dates = pd.DatetimeIndex(
        df["date"].dt.normalize().unique()
    )

    missing = expected.difference(actual_dates)

    duplicates = int(
        df.duplicated(subset=["date"]).sum()
    )

    columns = measurement_columns(df)

    if columns:

        numeric = df[columns].apply(
            pd.to_numeric,
            errors="coerce"
        )

        all_missing = int(
            numeric.isna().all(axis=1).sum()
        )

        null_pct = round(
            numeric.isna().sum().sum()
            / max(numeric.size, 1)
            * 100,
            2
        )

    else:

        all_missing = None
        null_pct = None

    expected_count = len(expected)

    missing_pct = (
        round(len(missing) / expected_count * 100, 2)
        if expected_count
        else None
    )

    if len(missing) == 0 and duplicates == 0:
        status = "PASS"
    else:
        status = "CHECK"

    return {
        "dataset": dataset,
        "region": region,
        "status": status,
        "expected_days": expected_count,
        "actual_rows": len(df),
        "unique_dates": len(actual_dates),
        "missing_dates": len(missing),
        "missing_date_pct": missing_pct,
        "duplicate_dates": duplicates,
        "invalid_dates": invalid_dates,
        "all_measurements_missing": all_missing,
        "measurement_null_pct": null_pct,
        "first_date": (
            df["date"].min().date()
            if not df.empty else None
        ),
        "last_date": (
            df["date"].max().date()
            if not df.empty else None
        ),
        "example_missing_dates": "; ".join(
            str(d.date()) for d in missing[:10]
        ),
    }


# --------------------------------------------------
# IRREGULAR DATASET AUDIT
# --------------------------------------------------

def audit_irregular(dataset, region):

    folder = ROOT / "Data" / "Raw" / dataset

    path = folder / (
        f"{dataset.lower()}_{region.lower()}.csv"
    )

    if not path.exists():

        return {
            "dataset": dataset,
            "region": region,
            "status": "MISSING FILE",
            "actual_rows": 0,
            "duplicate_dates": None,
            "measurement_null_pct": None,
        }

    df = read_csv_safely(path)

    if df is None or "date" not in df.columns:

        return {
            "dataset": dataset,
            "region": region,
            "status": "INVALID FILE",
            "actual_rows": 0,
            "duplicate_dates": None,
            "measurement_null_pct": None,
        }

    df["date"] = pd.to_datetime(
        df["date"],
        errors="coerce"
    )

    columns = measurement_columns(df)

    duplicates = int(
        df.duplicated(subset=["date"]).sum()
    )

    null_pct = None

    if columns and not df.empty:

        numeric = df[columns].apply(
            pd.to_numeric,
            errors="coerce"
        )

        null_pct = round(
            numeric.isna().sum().sum()
            / max(numeric.size, 1)
            * 100,
            2
        )

    return {
        "dataset": dataset,
        "region": region,
        "status": (
            "CHECK" if duplicates else "PASS"
        ),
        "actual_rows": len(df),
        "duplicate_dates": duplicates,
        "measurement_null_pct": null_pct,
        "first_date": (
            df["date"].min().date()
            if df["date"].notna().any()
            else None
        ),
        "last_date": (
            df["date"].max().date()
            if df["date"].notna().any()
            else None
        ),
    }


# --------------------------------------------------
# STATIC DATASET AUDIT
# --------------------------------------------------

def audit_static(dataset):

    folder = ROOT / "Data" / "Raw" / dataset

    path = folder / (
        f"{dataset.lower()}_all_regions.csv"
    )

    if not path.exists():

        return {
            "dataset": dataset,
            "region": "ALL",
            "status": "MISSING FILE",
            "actual_rows": 0,
            "expected_rows": len(REGIONS),
        }

    df = read_csv_safely(path)

    if df is None or "region" not in df.columns:

        return {
            "dataset": dataset,
            "region": "ALL",
            "status": "INVALID FILE",
            "actual_rows": 0,
            "expected_rows": len(REGIONS),
        }

    present = set(df["region"].dropna())

    missing_regions = set(REGIONS) - present

    return {
        "dataset": dataset,
        "region": "ALL",
        "status": (
            "PASS" if not missing_regions else "CHECK"
        ),
        "actual_rows": len(df),
        "expected_rows": len(REGIONS),
        "missing_regions": ", ".join(
            sorted(missing_regions)
        ),
    }


# --------------------------------------------------
# MAIN AUDIT
# --------------------------------------------------

def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--start",
        default=START_DATE
    )

    parser.add_argument(
        "--end",
        default=END_DATE
    )

    args = parser.parse_args()

    if pd.Timestamp(args.start) > pd.Timestamp(args.end):
        parser.error("--start must not be later than --end")

    results = []

    print("\n======================================")
    print(" AGRICULTURAL DATA QUALITY AUDIT")
    print("======================================")

    # Daily datasets.
    for dataset in DAILY_DATASETS:

        for region in REGIONS:

            print(f"[daily] {dataset} | {region}")

            results.append(
                audit_daily(
                    dataset,
                    region,
                    args.start,
                    args.end
                )
            )

    # Irregular satellite datasets.
    for dataset in IRREGULAR_DATASETS:

        for region in REGIONS:

            print(f"[irregular] {dataset} | {region}")

            results.append(
                audit_irregular(dataset, region)
            )

    # Static datasets.
    for dataset in STATIC_DATASETS:

        print(f"[static] {dataset}")

        results.append(
            audit_static(dataset)
        )

    report = pd.DataFrame(results)

    output_file = (
        OUTPUT_DIR / "data_quality_report.csv"
    )

    report.to_csv(output_file, index=False)

    print("\n======================================")
    print(" AUDIT SUMMARY")
    print("======================================")

    print(
        report[
            ["dataset", "region", "status"]
        ].to_string(index=False)
    )

    print("\nReport saved to:")
    print(output_file)

    print("\nDaily missing-date summary:")

    daily = report[
        report["dataset"].isin(DAILY_DATASETS)
    ]

    if not daily.empty:

        print(
            daily[
                [
                    "dataset",
                    "region",
                    "expected_days",
                    "unique_dates",
                    "missing_dates",
                    "missing_date_pct",
                    "measurement_null_pct",
                ]
            ].to_string(index=False)
        )


if __name__ == "__main__":
    main()
