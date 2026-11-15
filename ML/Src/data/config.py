import os
from pathlib import Path

# ML/Src/data/config.py -> parents[2] = ML/
ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "Data" / "Raw"

# Provisional centroids (NOT official boundaries)
REGIONS = {
    "Arsi":  {"latitude": 7.50, "longitude": 39.20},
    "Bale":  {"latitude": 7.00, "longitude": 40.50},
    "Jimma": {"latitude": 7.67, "longitude": 36.83},
}

BUFFER_M = 25_000            # 25 km buffer around each point
START_DATE = "1981-01-01"
END_DATE = "2025-12-31"

# Your Google Cloud project that is registered for Earth Engine
GEE_PROJECT = os.environ.get("GEE_PROJECT", "study-ai-partner")


def raw_dir(name: str) -> Path:
    path = RAW_DIR / name
    path.mkdir(parents=True, exist_ok=True)
    return path