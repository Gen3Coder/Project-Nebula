"""Step 4: build the training dataset (one row per labelled onset event).

Run:  python ML\\Src\\processing\\build_features.py

Every feature is computed with TRAILING windows only (today and the past), so it uses nothing that
happens after the trigger day. At the end the script PROVES this: for random events it deletes all
data after the trigger date, rebuilds the features, and checks they are identical.

Outputs (Data/Processed/):
  training_dataset.csv   id columns + features + false_start + split (train/test by year)
  feature_list.json      which columns are features (for training and for the SE team's predict())
"""
import json

import numpy as np
import pandas as pd

import label_config as cfg
from pipeline_common import PROC_DIR, load_table, run_length_ending, save_table

STATIC_FEATURES = ["elevation_mean", "slope_mean", "cropland_fraction",
                   "clay_0_5cm_mean", "sand_0_5cm_mean", "soc_0_5cm_mean"]


def compute_daily_features(df):
    """Features for EVERY day of one region, using only that day and earlier days."""
    df = df.sort_values("date").reset_index(drop=True)
    rain = df["rain_mm"]
    wet = df["wet_day"]
    f = pd.DataFrame(index=df.index)

    # --- rainfall ---
    f["rain_1d"] = rain
    f["rain_3d"] = rain.rolling(3).sum()
    f["rain_7d"] = rain.rolling(7).sum()
    f["rain_14d"] = rain.rolling(14).sum()
    f["rain_30d"] = rain.rolling(30).sum()
    f["rain_antecedent_30d"] = rain.shift(3).rolling(30).sum()      # the 30 days BEFORE the trigger window
    f["wet_days_7d"] = wet.rolling(7).sum()
    f["wet_days_14d"] = wet.rolling(14).sum()
    f["max_rain_3d"] = rain.rolling(3).max()                         # biggest single day = intensity
    f["intensity_7d"] = f["rain_7d"] / f["wet_days_7d"].clip(lower=1)  # mm per wet day

    run = pd.Series(run_length_ending((rain < cfg.DRY_DAY_MM).values), index=df.index)
    f["dry_run_before"] = run.shift(3)                               # dry days right before the trigger window
    f["max_dry_run_30d_before"] = run.shift(3).rolling(30).max()

    # --- atmosphere (how fast water leaves) ---
    f["tmean_3d"] = df["t2m_c"].rolling(3).mean()
    f["tmax_3d"] = df["tmax_c"].rolling(3).mean()
    f["rh_3d"] = df["rh_pct"].rolling(3).mean()
    f["wind_3d"] = df["wind10_ms"].rolling(3).mean()
    f["rad_3d"] = df["rad_mj"].rolling(3).mean()
    f["vpd_3d"] = df["vpd_kpa"].rolling(3).mean()
    f["vpd_7d"] = df["vpd_kpa"].rolling(7).mean()
    f["et0_3d"] = df["et0_mm"].rolling(3).mean()
    f["et0_7d"] = df["et0_mm"].rolling(7).mean()

    # --- soil water (ERA5-Land: covers all years) ---
    for layer in ("sm_l1", "sm_l2", "sm_l3"):
        f[layer] = df[layer]
    f["sm_l1_3dmean"] = df["sm_l1"].rolling(3).mean()
    f["sm_l1_pre"] = df["sm_l1"].shift(3)                            # soil moisture BEFORE the trigger rain
    f["sm_l2_pre"] = df["sm_l2"].shift(3)
    f["sm_l1_chg3"] = df["sm_l1"] - df["sm_l1"].shift(3)
    f["sm_l2_chg3"] = df["sm_l2"] - df["sm_l2"].shift(3)

    # --- timing ---
    f["doy"] = df["date"].dt.dayofyear
    f["month"] = df["date"].dt.month

    f.index = df["date"]
    return f


def main():
    daily = load_table("integrated_daily")
    events = load_table("onset_events", parse_dates=("trigger_date",))
    events = events[events["label_complete"]].copy()
    static_cols = [c for c in STATIC_FEATURES if c in daily.columns]

    feats = {region: compute_daily_features(g) for region, g in daily.groupby("region")}

    rows = []
    for _, e in events.iterrows():
        row = feats[e["region"]].loc[e["trigger_date"]].to_dict()
        row.update({"event_id": e["event_id"], "region": e["region"], "window": e["window"],
                    "year": int(e["year"]), "trigger_date": e["trigger_date"]})
        rows.append(row)
    train = pd.DataFrame(rows)

    static = daily.groupby("region")[static_cols].first().reset_index()
    train = train.merge(static, on="region", how="left")
    train["false_start"] = events["false_start"].astype(int).values
    train["split"] = np.where(train["year"] <= cfg.TRAIN_END_YEAR, "train", "test")

    id_cols = ["event_id", "region", "window", "year", "trigger_date", "split"]
    num_cols = [c for c in feats[next(iter(feats))].columns] + static_cols
    train = train[id_cols + num_cols + ["false_start"]].sort_values("trigger_date").reset_index(drop=True)

    # ---------------- leakage proof ----------------
    rng = np.random.default_rng(0)
    sample = train.sample(min(30, len(train)), random_state=0)
    for _, e in sample.iterrows():
        region_df = daily[daily["region"] == e["region"]]
        truncated = region_df[region_df["date"] <= e["trigger_date"]]            # delete the future
        rebuilt = compute_daily_features(truncated).iloc[-1][num_cols[:len(feats[e["region"]].columns)]]
        stored = e[rebuilt.index]
        if not np.allclose(rebuilt.astype(float).values, stored.astype(float).values, equal_nan=True):
            diff = rebuilt.index[~np.isclose(rebuilt.astype(float).values, stored.astype(float).values, equal_nan=True)]
            raise AssertionError(f"LEAKAGE: features changed when future data was removed: {list(diff)} ({e['event_id']})")
    print(f"\n[leakage check] PASSED for {len(sample)} random events: features are identical "
          f"when all data after the trigger date is deleted.")

    save_table(train, "training_dataset")

    feature_info = {
        "id_columns": id_cols,
        "numeric_features": num_cols,
        "categorical_features": ["region", "window"],
        "target": "false_start",
        "split_rule": f"train: year <= {cfg.TRAIN_END_YEAR}, test: later years",
        "label_rules": {k: getattr(cfg, k) for k in
                        ("TRIGGER_MM", "TRIGGER_DAYS", "MIN_WET_DAYS_IN_TRIGGER", "TRIGGER_WET_DAY_MM",
                         "FOLLOW_DAYS", "DRY_SPELL_DAYS", "DRY_DAY_MM", "FIRST_TRIGGER_ONLY")},
    }
    (PROC_DIR / "feature_list.json").write_text(json.dumps(feature_info, indent=2), encoding="utf-8")
    print("[saved] feature_list.json")

    print("\nTraining table summary")
    print(train.groupby("split")["false_start"].agg(rows="size", false_starts="sum", rate="mean").round(3).to_string())
    print(f"Features: {len(num_cols)} numeric + 2 categorical (region, window)")
    miss = train[num_cols].isna().mean().mul(100).round(1)
    print("Features with empty values (%):", miss[miss > 0].to_dict() or "none")


if __name__ == "__main__":
    main()
