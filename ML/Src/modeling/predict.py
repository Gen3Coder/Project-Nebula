"""Prediction function for the SE team (SERVER / react app).

    from predict import predict_false_start
    result = predict_false_start(features_dict)

`features_dict` holds the values listed in the model's `numeric_features` (see ML/Models/model_card.json)
plus "region" and "window". These are exactly the columns of training_dataset.csv, computed at the onset
trigger day from data up to and including that day (Src/processing/build_features.py::compute_daily_features).
Missing numeric values are allowed (they are filled with the training median).
"""
from functools import lru_cache
from pathlib import Path

import joblib
import pandas as pd

MODEL_PATH = Path(__file__).resolve().parents[2] / "Models" / "final_model.joblib"


@lru_cache(maxsize=1)
def load_bundle(path=MODEL_PATH):
    return joblib.load(path)


def risk_level(p, bands):
    if p >= bands["high_min"]:
        return "HIGH"
    if p <= bands["low_max"]:
        return "LOW"
    return "MODERATE"


def predict_false_start(features: dict, model_path=MODEL_PATH) -> dict:
    b = load_bundle(model_path)
    key = f"{features.get('region')}|{features.get('window')}"
    if key not in b["valid_region_windows"]:
        raise ValueError(f"Unknown region/window '{key}'. Valid: {b['valid_region_windows']}")
    cols = b["numeric_features"] + b["categorical_features"]
    row = pd.DataFrame([{c: features.get(c) for c in cols}])
    for c in b["numeric_features"]:
        row[c] = pd.to_numeric(row[c], errors="coerce")
    p = float(b["pipeline"].predict_proba(row[cols])[0, 1])
    return {
        "false_start_probability": round(p, 3),
        "risk_level": risk_level(p, b["risk_bands"]),
        "flag": bool(p >= b["threshold"]),
        "typical_rate_for_this_window": round(b["climatology"][key], 3),
        "missing_inputs": [c for c in b["numeric_features"] if pd.isna(row.loc[0, c])],
        "model": b["model_name"],
        "validated_better_than_climatology": b["beats_climatology_on_holdout"],
        "note": "Risk of a >= {DRY_SPELL_DAYS}-day dry spell in the {FOLLOW_DAYS} days after the onset trigger. "
                "Not a prediction of crop death.".format(**b["label_rules"]),
    }


if __name__ == "__main__":      # quick self-test with a real event from the training table
    tab = pd.read_csv(MODEL_PATH.parents[1] / "Data" / "Processed" / "training_dataset.csv")
    ev = tab.iloc[0].to_dict()
    print(ev["event_id"], "actual false_start =", ev["false_start"])
    print(predict_false_start(ev))
