import pandas as pd
from pathlib import Path

raw = Path(r"C:\hackaton\ML\Data\Raw\CHIRPS")
df = pd.read_csv(raw / "chirps_daily_1981_2025.csv", parse_dates=["date"])
df = df.rename(columns={"region_name": "region", "precipitation_mm": "precipitation"})

for region, part in df.groupby("region"):
    part = part.sort_values("date")[["date", "region_name", "mean"]]
    part.to_csv(raw / f"chirps_{region.lower()}.csv", index=False)
    print(region, len(part), part["date"].min().date(), part["date"].max().date())