
from pathlib import Path
import ee
import requests

# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

PROJECT_ID = "study-ai-partner"

ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "Data" / "Raw" / "CHIRPS"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_FILE = OUTPUT_DIR / "chirps_daily_1981_2025.csv"

# --------------------------------------------------
# INITIALIZE EARTH ENGINE
# --------------------------------------------------

ee.Initialize(project=PROJECT_ID)

print("Earth Engine connected.")

# --------------------------------------------------
# DEFINE STUDY REGIONS
# --------------------------------------------------

regions = ee.FeatureCollection([
    ee.Feature(
        ee.Geometry.Point([39.20, 7.50]).buffer(25000),
        {"region_name": "Arsi"}
    ),
    ee.Feature(
        ee.Geometry.Point([40.50, 7.00]).buffer(25000),
        {"region_name": "Bale"}
    ),
    ee.Feature(
        ee.Geometry.Point([36.83, 7.67]).buffer(25000),
        {"region_name": "Jimma"}
    )
])

# --------------------------------------------------
# LOAD CHIRPS
# --------------------------------------------------

rainfall = (
    ee.ImageCollection("UCSB-CHG/CHIRPS/DAILY")
    .filterDate("1981-01-01", "2026-01-01")
    .select("precipitation")
)

print("CHIRPS collection loaded.")

# --------------------------------------------------
# EXTRACT DAILY REGIONAL MEANS
# --------------------------------------------------

def extract_daily(image):

    daily_regions = image.reduceRegions(
        collection=regions,
        reducer=ee.Reducer.mean(),
        scale=5566
    )

    date = image.date().format("YYYY-MM-dd")

    return daily_regions.map(
        lambda feature: feature.set("date", date)
    )

table = rainfall.map(extract_daily).flatten()

# Remove geometry and retain only required columns.
table = table.select(
    ["region_name", "date", "mean"],
    None,
    False
)

print("Preparing direct CSV download...")

# --------------------------------------------------
# GENERATE DOWNLOAD URL
# --------------------------------------------------

download_url = table.getDownloadURL(
    filetype="csv",
    selectors=["region_name", "date", "mean"],
    filename="chirps_daily_1981_2025"
)

# --------------------------------------------------
# DOWNLOAD DIRECTLY TO LOCAL STORAGE
# --------------------------------------------------

print("Downloading CHIRPS data...")

response = requests.get(download_url, stream=True, timeout=300)
response.raise_for_status()

with open(OUTPUT_FILE, "wb") as file:
    for chunk in response.iter_content(chunk_size=1024 * 1024):
        if chunk:
            file.write(chunk)

print("\nDownload completed!")
print(f"Saved to: {OUTPUT_FILE}")
print(f"File size: {OUTPUT_FILE.stat().st_size / 1024 / 1024:.2f} MB")
