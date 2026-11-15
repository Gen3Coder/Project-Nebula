import time
import requests
import pandas as pd

from ML.Src.processing.config import REGIONS, START_DATE, END_DATE, raw_dir

API_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"

PARAMETERS = [
    "T2M",
    "T2M_MAX",
    "T2M_MIN",
    "RH2M",
    "WS10M",
    "ALLSKY_SFC_SW_DWN",
]

START = START_DATE.replace("-", "")
END = END_DATE.replace("-", "")


def download_region(region, coords):

    output_dir = raw_dir("NASA_POWER")
    output_file = output_dir / f"nasa_power_{region.lower()}.csv"

    if output_file.exists():
        print(f"[skip] {output_file.name} already exists")
        return pd.read_csv(output_file)

    params = {
        "parameters": ",".join(PARAMETERS),
        "community": "AG",
        "longitude": coords["longitude"],
        "latitude": coords["latitude"],
        "start": START,
        "end": END,
        "format": "JSON",
        "time-standard": "UTC",
    }

    print(f"\n[NASA POWER] Downloading {region}...")

    for attempt in range(4):
        try:
            response = requests.get(
                API_URL,
                params=params,
                timeout=180
            )
            response.raise_for_status()

            payload = response.json()

            parameter_data = payload["properties"]["parameter"]

            df = pd.DataFrame(parameter_data)
            df.index.name = "date"
            df = df.reset_index()

            df["date"] = pd.to_datetime(
                df["date"],
                format="%Y%m%d"
            )

            df["region"] = region
            df["latitude"] = coords["latitude"]
            df["longitude"] = coords["longitude"]

            # NASA POWER uses -999 as a missing-data indicator.
            for col in PARAMETERS:
                df[col] = pd.to_numeric(df[col], errors="coerce")
                df[col] = df[col].replace(-999, float("nan"))

            df.to_csv(output_file, index=False)

            print(
                f"[saved] {output_file.name} | "
                f"{len(df)} rows | "
                f"{df['date'].min().date()} to "
                f"{df['date'].max().date()}"
            )

            return df

        except Exception as error:
            wait = 5 * (2 ** attempt)
            print(f"[retry] {error}")

            if attempt == 3:
                raise

            time.sleep(wait)


def main():

    all_data = []

    for region, coords in REGIONS.items():
        df = download_region(region, coords)
        if df is not None:
            all_data.append(df)

        time.sleep(2)

    if all_data:
        combined = pd.concat(all_data, ignore_index=True)

        combined_file = (
            raw_dir("NASA_POWER")
            / "nasa_power_all_regions.csv"
        )

        combined.to_csv(combined_file, index=False)

        print("\nNASA POWER download completed.")
        print(f"Combined file: {combined_file}")


if __name__ == "__main__":
    main()
