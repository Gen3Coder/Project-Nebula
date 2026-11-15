"""Shared helpers for the modelling step: paths, data loading, feature sets, validation splits, metrics.

Everything here is import-only (no side effects). Used by model_zoo.py, train_model.py,
findings_report.py and predict.py.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.metrics import (average_precision_score, brier_score_loss, log_loss,
                             precision_recall_curve, roc_auc_score)

# <project>/ML/Src/modeling/training_utils.py  ->  parents[2] = <project>/ML
ML_DIR = Path(__file__).resolve().parents[2]
PROC_DIR = ML_DIR / "Data" / "Processed"
MODELS_DIR = ML_DIR / "Models"
REPORTS_DIR = ML_DIR / "Reports"
FIG_DIR = ML_DIR / "Figures"
for _d in (MODELS_DIR, REPORTS_DIR, FIG_DIR):
    _d.mkdir(parents=True, exist_ok=True)

SEED = 42
TARGET = "false_start"
CAT_FEATURES = ["region", "window"]


# ------------------------------------------------------------------ data
def load_training_table():
    """Returns (df, feature_info). df has one row per labelled onset event."""
    info = json.loads((PROC_DIR / "feature_list.json").read_text(encoding="utf-8"))
    df = pd.read_csv(PROC_DIR / "training_dataset.csv", parse_dates=["trigger_date"])
    df = df.sort_values("trigger_date").reset_index(drop=True)
    return df, info


# Feature sets answer "which DATASET adds value?" (used for the ablation table and for the final model).
# Names are columns of training_dataset.csv. Every set also gets region + window (one-hot).
def feature_sets(info):
    allnum = list(info["numeric_features"])
    rain = ["rain_1d", "rain_3d", "rain_7d", "rain_14d", "rain_30d", "rain_antecedent_30d",
            "wet_days_7d", "wet_days_14d", "max_rain_3d", "intensity_7d",
            "dry_run_before", "max_dry_run_30d_before"]
    timing = ["doy"]
    atmos = ["tmean_3d", "tmax_3d", "rh_3d", "wind_3d", "rad_3d", "vpd_3d", "vpd_7d", "et0_3d", "et0_7d"]
    soil = ["sm_l1", "sm_l2", "sm_l3", "sm_l1_3dmean", "sm_l1_pre", "sm_l2_pre", "sm_l1_chg3", "sm_l2_chg3"]
    static = ["elevation_mean", "slope_mean", "cropland_fraction",
              "clay_0_5cm_mean", "sand_0_5cm_mean", "soc_0_5cm_mean"]
    # compact = a short, physically motivated list (few features is safer with ~200 events)
    compact = ["rain_3d", "rain_antecedent_30d", "dry_run_before", "max_dry_run_30d_before",
               "vpd_7d", "et0_7d", "tmax_3d", "sm_l1_pre", "sm_l2", "sm_l2_chg3", "doy"]
    sets = {
        "rain only": rain + timing,
        "rain + atmosphere (VPD/ET0/temp)": rain + timing + atmos,
        "rain + soil moisture": rain + timing + soil,
        "rain + atmosphere + soil": rain + timing + atmos + soil,
        "all (incl. static soil/terrain)": allnum,
        "compact (11 physical features)": compact,
    }
    for name, cols in sets.items():
        missing = [c for c in cols if c not in allnum]
        if missing:
            raise KeyError(f"feature set '{name}' uses columns not in the table: {missing}")
    return sets


# ------------------------------------------------------------------ simple baseline model
class ClimatologyRate(BaseEstimator, ClassifierMixin):
    """Baseline: predict the training false-start rate of the event's region+window.
    Shrunk toward the overall rate (weight k) so tiny groups do not give 0 or 1."""

    def __init__(self, keys=("region", "window"), k=5.0):
        self.keys = keys
        self.k = k

    def fit(self, X, y):
        X = pd.DataFrame(X).reset_index(drop=True)
        y = pd.Series(np.asarray(y, dtype=float))
        self.global_ = float(y.mean())
        key = X[list(self.keys)].astype(str).agg("|".join, axis=1)
        g = y.groupby(key.values).agg(["sum", "count"])
        self.rate_ = ((g["sum"] + self.k * self.global_) / (g["count"] + self.k)).to_dict()
        self.classes_ = np.array([0, 1])
        return self

    def predict_proba(self, X):
        X = pd.DataFrame(X).reset_index(drop=True)
        key = X[list(self.keys)].astype(str).agg("|".join, axis=1)
        p = key.map(self.rate_).fillna(self.global_).to_numpy(float)
        return np.c_[1 - p, p]

    def predict(self, X):
        return (self.predict_proba(X)[:, 1] >= 0.5).astype(int)


# ------------------------------------------------------------------ validation splits
# Each splitter yields (train_index, test_index) as integer positions into df.
def holdout_split(df):
    tr = np.where(df["split"] == "train")[0]
    te = np.where(df["split"] == "test")[0]
    return tr, te


def leave_one_year_out(df, years=None):
    """Hold out every event of one year at a time (the 5 events of a year share the same weather)."""
    years = sorted(df["year"].unique()) if years is None else years
    for y in years:
        te = np.where(df["year"] == y)[0]
        tr = np.where(df["year"] != y)[0]
        yield tr, te


def forward_chaining(df, first_test_year=1996, block=5):
    """Train only on the past, test on the next `block` years, then roll forward."""
    last = int(df["year"].max())
    start = first_test_year
    while start <= last:
        end = min(start + block - 1, last)
        tr = np.where(df["year"] < start)[0]
        te = np.where((df["year"] >= start) & (df["year"] <= end))[0]
        if len(te):
            yield tr, te
        start += block


def out_of_fold(make_model, df, cols, splits):
    """Fit a fresh model per split; return a Series of probabilities (NaN where never tested)."""
    from sklearn.base import clone
    oof = pd.Series(np.nan, index=df.index)
    for tr, te in splits:
        m = clone(make_model) if hasattr(make_model, "get_params") else make_model()
        m.fit(df.iloc[tr][cols], df.iloc[tr][TARGET].values)
        oof.iloc[te] = m.predict_proba(df.iloc[te][cols])[:, 1]
    return oof


# ------------------------------------------------------------------ metrics
def recall_at_precision(y, p, min_precision=0.6):
    """Best recall reachable while keeping precision >= min_precision (0 if impossible)."""
    prec, rec, _ = precision_recall_curve(y, p)
    ok = prec >= min_precision
    return float(rec[ok].max()) if ok.any() else 0.0


def score(y, p, base_rate=None):
    """All headline metrics for one set of predictions."""
    y = np.asarray(y).astype(int)
    p = np.clip(np.asarray(p, dtype=float), 1e-6, 1 - 1e-6)
    base_rate = float(y.mean()) if base_rate is None else base_rate
    brier = brier_score_loss(y, p)
    brier_ref = brier_score_loss(y, np.full(len(y), base_rate))
    out = {"n": len(y), "positives": int(y.sum()),
           "pr_auc": average_precision_score(y, p) if y.sum() else np.nan,
           "brier": brier,
           "brier_skill": 1 - brier / brier_ref if brier_ref > 0 else np.nan,
           "log_loss": log_loss(y, p, labels=[0, 1]),
           "recall@prec0.6": recall_at_precision(y, p, 0.6)}
    out["roc_auc"] = roc_auc_score(y, p) if 0 < y.sum() < len(y) else np.nan
    return out


def year_bootstrap_ci(df, p, metric="roc_auc", n_boot=500, seed=SEED):
    """95% interval from resampling YEARS (not events), because events in one year are not independent."""
    rng = np.random.default_rng(seed)
    d = pd.DataFrame({"year": df["year"].values, "y": df[TARGET].values, "p": np.asarray(p)})
    groups = {k: v for k, v in d.groupby("year")}
    years = list(groups)
    vals = []
    for _ in range(n_boot):
        pick = rng.choice(years, len(years), replace=True)
        s = pd.concat([groups[y] for y in pick])
        if s["y"].nunique() < 2:
            continue
        vals.append(score(s["y"], s["p"])[metric])
    return tuple(np.nanpercentile(vals, [2.5, 97.5]))


def pick_threshold(y, p):
    """Probability cut-off that maximises balanced accuracy on out-of-fold predictions."""
    best_t, best = 0.5, -1
    for t in np.linspace(0.2, 0.8, 61):
        pred = p >= t
        tpr = (pred & (y == 1)).sum() / max((y == 1).sum(), 1)
        tnr = (~pred & (y == 0)).sum() / max((y == 0).sum(), 1)
        if (tpr + tnr) / 2 > best:
            best, best_t = (tpr + tnr) / 2, float(t)
    return round(best_t, 3), round(best, 3)
