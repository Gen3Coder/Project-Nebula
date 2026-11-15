"""Day-by-day monitoring after an onset trigger (the "Risk now" card).

    from predict_monitor import monitor_status, monitor_history
    monitor_status("Bale", "main", "1997-02-08", daily_rows)      # status for the LAST row (= today)

`daily_rows` = list of dicts, one per day, from the trigger day (included) up to today, with keys
    date (YYYY-MM-DD), rain_mm, and optionally sm_l1, sm_l2 (soil moisture), vpd_kpa, et0_mm, tmax_c.
Only rain_mm drives the risk; soil moisture is used for the "Soil moisture" line (see model_card / findings).
"""
import warnings
from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from monitor_features import (ADVICE, DRY_SPELL_DAYS, FOLLOW_DAYS, day_features, risk_label, soil_trend_label,
                              still_undecided)

MODEL_PATH = Path(__file__).resolve().parents[2] / "Models" / "monitor_model.joblib"


@lru_cache(maxsize=1)
def load_monitor(path=MODEL_PATH):
    return joblib.load(path)


def _col(df, name):
    return df[name].to_numpy(float) if name in df else np.full(len(df), np.nan)


def monitor_status(region, window, trigger_date, daily_rows, model_path=MODEL_PATH):
    b = load_monitor(model_path)
    key = f"{region}|{window}"
    if key not in b["valid_region_windows"]:
        raise ValueError(f"Unknown region/window '{key}'. Valid: {b['valid_region_windows']}")
    df = pd.DataFrame(daily_rows)
    if df.empty or "date" not in df or "rain_mm" not in df:
        raise ValueError("daily_rows needs at least 'date' and 'rain_mm'")
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    t = pd.to_datetime(trigger_date)
    if df["date"].iloc[0] != t:
        raise ValueError("daily_rows must start on the trigger date")
    if (df["date"].diff().dropna() != pd.Timedelta(days=1)).any():
        raise ValueError("daily_rows must have one row per day with no gaps")
    if df["rain_mm"].isna().any():
        raise ValueError("rain_mm has missing values")
    i = len(df) - 1
    out = {"date": df["date"].iloc[i].strftime("%Y-%m-%d"), "day_after_trigger": i, "region": region, "window": window}
    if i == 0:
        out.update(status="TRIGGER_DAY", risk_probability=None, risk_level=None, dry_days_so_far=0,
                   soil_moisture="n/a", advice="Onset trigger today. Daily monitoring starts tomorrow.")
        return _finish(out)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        f = day_features(_col(df, "rain_mm"), _col(df, "vpd_kpa"), _col(df, "et0_mm"), _col(df, "tmax_c"),
                         _col(df, "sm_l1"), _col(df, "sm_l2"), 0, i, df["date"].iloc[i].dayofyear, np.nan)
    out["dry_days_so_far"] = int(f["dry_run_now"])
    chg3 = f["sm_l1_chg3"]
    out["soil_moisture"] = "unknown" if np.isnan(chg3) else soil_trend_label(chg3, b["soil_trend_cuts"])

    if f["max_dry_run_so_far"] >= DRY_SPELL_DAYS:
        out.update(status="CONFIRMED", risk_probability=1.0, risk_level="CONFIRMED")
    elif i >= FOLLOW_DAYS or not still_undecided(f):
        out.update(status="RESOLVED", risk_probability=0.0, risk_level="RESOLVED")
    else:
        p = float(b["pipeline"].predict_proba(pd.DataFrame([{c: f[c] for c in b["features"]}]))[0, 1])
        p = min(round(p * 20) / 20, 0.95)        # shown in steps of 5 %, never above 95 % (honest precision)
        out.update(status="MONITORING", risk_probability=p, risk_level=risk_label(p))
    out["advice"] = ADVICE[out["risk_level"]]
    return _finish(out)


def _finish(out):
    p = out.get("risk_probability")
    risk = "n/a" if p is None else f"{p:.0%} ({out['risk_level']})" if out["status"] == "MONITORING" else out["risk_level"]
    out["text"] = (f"Date: {out['date']} (Day {out['day_after_trigger']} after trigger)\n"
                   f"Dry days so far: {out['dry_days_so_far']}\n"
                   f"Soil moisture: {out['soil_moisture']}\n"
                   f"Risk now: {risk}\n"
                   f"Advice: {out['advice']}")
    out["advice_is_draft"] = True
    return out


def monitor_history(region, window, trigger_date, daily_rows, model_path=MODEL_PATH):
    """Status for every day since the trigger (for a chart / timeline)."""
    return [monitor_status(region, window, trigger_date, daily_rows[: k + 1], model_path)
            for k in range(len(daily_rows))]


if __name__ == "__main__":   # demo on a real past event from the processed data
    import sys
    root = Path(__file__).resolve().parents[2] / "Data" / "Processed"
    ev = pd.read_csv(root / "onset_events.csv", parse_dates=["trigger_date"])
    daily = pd.read_csv(root / "integrated_daily.csv", parse_dates=["date"])
    eid = sys.argv[1] if len(sys.argv) > 1 else "Bale_main_1997"
    e = ev[ev["event_id"] == eid].iloc[0]
    g = daily[(daily["region"] == e["region"]) & (daily["date"] >= e["trigger_date"])].head(14)
    rows = g[["date", "rain_mm", "sm_l1", "sm_l2", "vpd_kpa", "et0_mm", "tmax_c"]].assign(
        date=lambda d: d["date"].dt.strftime("%Y-%m-%d")).to_dict("records")
    print(f"{eid}: actual false_start = {e['false_start']}\n")
    for s in monitor_history(e["region"], e["window"], e["trigger_date"].strftime("%Y-%m-%d"), rows)[1:11]:
        print(s["text"], "\n")
