"""Step 7: daily monitoring model ("Risk now" on each day after an onset trigger).

Run:   python ML\\Src\\modeling\\train_monitor.py
Needs: Data/Processed/integrated_daily.csv and onset_events.csv (from run_processing.py).
Outputs: Data/Processed/monitoring_dataset.csv, Models/monitor_model.joblib, Reports/M_*.csv, Figures/monitor_*.png

Question answered: on day d after the trigger (no 8-day dry spell yet), what is the chance one still happens
before day 30?  Compared across data groups to see whether soil moisture / VPD / temperature add anything
beyond simply counting dry days.
"""
import warnings

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from monitor_features import (CAT, DRY_SPELL_DAYS, FEATURE_GROUPS, FOLLOW_DAYS, day_features, still_undecided)
from training_utils import FIG_DIR, MODELS_DIR, PROC_DIR, REPORTS_DIR, SEED

warnings.filterwarnings("ignore")
TRAIN_END_YEAR = 2015
ALERT = 0.70            # probability at which we call it an alert (for lead-time analysis)

# Event-level features (trigger rain, day of year, region/window) are NOT used: every day of one event shares
# them, so a flexible model memorises events instead of learning how drying proceeds (first version overfitted).
SETS = {
    "dry-run only": FEATURE_GROUPS["dry-run only"],
    "rain": FEATURE_GROUPS["rain"],
    "rain + atmosphere": FEATURE_GROUPS["rain"] + FEATURE_GROUPS["atmosphere"],
    "rain + soil": FEATURE_GROUPS["rain"] + FEATURE_GROUPS["soil"],
    "rain + atmosphere + soil": FEATURE_GROUPS["rain"] + FEATURE_GROUPS["atmosphere"] + FEATURE_GROUPS["soil"],
}
BLUE, ORANGE, GREY, INK, INK2, GRID, SURF = "#2a78d6", "#eb6834", "#9a9993", "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"


# ------------------------------------------------------------------ build the day-by-day table
def build_table():
    daily = pd.read_csv(PROC_DIR / "integrated_daily.csv", parse_dates=["date"])
    ev = pd.read_csv(PROC_DIR / "onset_events.csv", parse_dates=["trigger_date"])
    ev = ev[ev["label_complete"]]
    series = {r: g.sort_values("date").reset_index(drop=True) for r, g in daily.groupby("region")}
    rows = []
    for _, e in ev.iterrows():
        g = series[e["region"]]
        i0 = int(np.where(g["date"].values == np.datetime64(e["trigger_date"]))[0][0])
        arr = {k: g[c].to_numpy(float) for k, c in
               (("rain", "rain_mm"), ("vpd", "vpd_kpa"), ("et0", "et0_mm"), ("tmax", "tmax_c"),
                ("sm1", "sm_l1"), ("sm2", "sm_l2"))}
        fail_day = (e["label_dry_spell_start_day"] + DRY_SPELL_DAYS - 1) if e["false_start"] == 1 else np.nan
        for d in range(1, FOLLOW_DAYS):
            i = i0 + d
            f = day_features(arr["rain"], arr["vpd"], arr["et0"], arr["tmax"], arr["sm1"], arr["sm2"],
                             i0, i, g["doy"].iloc[i], e["trigger_rain_mm"])
            if not still_undecided(f):
                continue
            f.update(event_id=e["event_id"], region=e["region"], window=e["window"], year=int(e["year"]),
                     date=g["date"].iloc[i], fail_day=fail_day, false_start=int(e["false_start"]))
            rows.append(f)
    return pd.DataFrame(rows)


def make_model(cols):
    # large leaves (~6 events' worth of rows) + strong L2 keep the probabilities honest
    hgb = HistGradientBoostingClassifier(max_iter=100, max_depth=3, learning_rate=0.05, min_samples_leaf=120,
                                         l2_regularization=5.0, random_state=SEED)
    return Pipeline([("model", hgb)])


def loyo_oof(df, cols, years):
    oof = pd.Series(np.nan, index=df.index)
    for y in years:
        te = df["year"] == y
        tr = ~te & df["year"].isin(years)
        m = make_model(cols).fit(df.loc[tr, cols], df.loc[tr, "false_start"])
        oof[te] = m.predict_proba(df.loc[te, cols])[:, 1]
    return oof


def row_scores(df, p):
    y = df["false_start"].values
    base = y.mean()
    return {"rows": len(df), "brier": brier_score_loss(y, p), "brier_skill": 1 - brier_score_loss(y, p) / brier_score_loss(y, np.full(len(y), base)),
            "roc_auc": roc_auc_score(y, p)}


def lead_time(df, p, alert=ALERT):
    """Per event: first day risk >= alert. Failing events: days before the 8th dry day. Good events: false alarms."""
    d = df.assign(p=p)
    rows = []
    for eid, g in d.groupby("event_id"):
        hit = g[g["p"] >= alert]
        first = int(hit["day_after"].iloc[0]) if len(hit) else np.nan
        rows.append({"event_id": eid, "false_start": int(g["false_start"].iloc[0]), "first_alert_day": first,
                     "fail_day": g["fail_day"].iloc[0]})
    r = pd.DataFrame(rows)
    f, ok = r[r["false_start"] == 1], r[r["false_start"] == 0]
    warned = f[f["first_alert_day"] < f["fail_day"]]
    return {"false_starts": len(f), "warned_before_8th_dry_day": len(warned),
            "share_warned": len(warned) / max(len(f), 1),
            "median_lead_days": float((warned["fail_day"] - warned["first_alert_day"]).median()) if len(warned) else np.nan,
            "good_starts": len(ok), "false_alarm_share": float(ok["first_alert_day"].notna().mean())}


def main():
    tab = build_table()
    tab.to_csv(PROC_DIR / "monitoring_dataset.csv", index=False)
    n_ev = tab["event_id"].nunique()
    print(f"Monitoring table: {len(tab)} event-days from {n_ev} events "
          f"({tab['false_start'].mean():.1%} of rows belong to eventual false starts)")

    years = sorted(tab["year"].unique())
    tr_years = [y for y in years if y <= TRAIN_END_YEAR]
    train, test = tab[tab["year"] <= TRAIN_END_YEAR].reset_index(drop=True), tab[tab["year"] > TRAIN_END_YEAR].reset_index(drop=True)

    # A. ablation, leave-one-year-out inside the training years
    print("\nA. Which data groups help? (leave-one-year-out, training years)")
    res, oofs = [], {}
    for name, cols in SETS.items():
        oof = loyo_oof(train, cols, tr_years)
        oofs[name] = oof
        s = row_scores(train, oof); s.update(feature_set=name, n_features=len(cols)); s.update(
            {f"lead_{k}": v for k, v in lead_time(train, oof).items()})
        res.append(s)
    A = pd.DataFrame(res).set_index("feature_set")
    A.to_csv(REPORTS_DIR / "M_A_ablation_train_loyo.csv")
    print(A[["n_features", "roc_auc", "brier", "brier_skill", "lead_share_warned", "lead_median_lead_days",
             "lead_false_alarm_share"]].round(3).to_string())

    best = A["brier"].idxmin()
    print(f"\n-> Lowest Brier: {best}")

    # B. hold-out test, all sets, scored once
    print("\nB. Hold-out test (later years)")
    rows, test_p = [], {}
    for name, cols in SETS.items():
        m = make_model(cols).fit(train[cols], train["false_start"])
        p = m.predict_proba(test[cols])[:, 1]
        test_p[name] = p
        s = row_scores(test, p); s.update(feature_set=name, selected=(name == best))
        s.update({f"lead_{k}": v for k, v in lead_time(test, p).items()})
        rows.append(s)
    B = pd.DataFrame(rows).set_index("feature_set")
    B.to_csv(REPORTS_DIR / "M_B_holdout.csv")
    print(B[["roc_auc", "brier", "brier_skill", "lead_share_warned", "lead_median_lead_days",
             "lead_false_alarm_share", "selected"]].round(3).to_string())

    # C. calibration of the selected model on the hold-out + by-day behaviour
    p_sel = test_p[best]
    cal = test.assign(p=p_sel)
    cal["bin"] = pd.cut(cal["p"], [0, .2, .4, .6, .8, 1.0], include_lowest=True)
    ctab = cal.groupby("bin", observed=True).agg(rows=("p", "size"), mean_pred=("p", "mean"), observed=("false_start", "mean")).round(3)
    ctab.to_csv(REPORTS_DIR / "M_C_calibration_holdout.csv")
    print("\nC. Calibration on hold-out (do 'risk 85%' rows really fail ~85% of the time?)")
    print(ctab.to_string())

    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.6))
    ax = axes[0]
    ax.plot([0, 1], [0, 1], color=GREY, ls="--", lw=1.5, label="perfect")
    ax.plot(ctab["mean_pred"], ctab["observed"], marker="o", ms=8, lw=2, color=BLUE, label="monitoring model (hold-out)")
    for _, r in ctab.iterrows():
        ax.annotate(f"n={int(r['rows'])}", (r["mean_pred"], r["observed"]), textcoords="offset points", xytext=(6, -12), fontsize=8, color=INK2)
    ax.set(xlim=(0, 1), ylim=(0, 1), xlabel="Risk shown to the farmer", ylabel="Share that really became a false start",
           title="Is '85%' really 85%?")
    ax.legend(frameon=False, loc="upper left")
    ax = axes[1]
    order = list(B.index)
    ax.barh(order[::-1], B.loc[order[::-1], "roc_auc"], color=[ORANGE if n == best else BLUE for n in order[::-1]], height=0.6)
    for k, n in enumerate(order[::-1]):
        ax.text(B.loc[n, "roc_auc"] + 0.005, k, f"{B.loc[n, 'roc_auc']:.3f}", va="center", fontsize=9, color=INK2)
    ax.set(xlim=(0.5, 1.0), xlabel="Hold-out ROC-AUC (0.5 = chance)", title="Does soil / VPD / temperature add anything?")
    for a in axes:
        a.grid(color=GRID, lw=.8); a.set_axisbelow(True)
        for s in ("top", "right"): a.spines[s].set_visible(False)
    fig.tight_layout(); fig.savefig(FIG_DIR / "monitor_results.png", dpi=160, facecolor=SURF); plt.close(fig)

    # D. final model on all events, soil-trend cut-offs
    cols = SETS[best]
    final = make_model(cols).fit(tab[cols], tab["false_start"])
    cuts = tuple(float(tab["sm_l1_chg3"].quantile(q)) for q in (0.10, 0.35, 0.65))
    joblib.dump({"pipeline": final, "features": cols, "categorical": [], "feature_set": best,
                 "soil_trend_cuts": cuts, "valid_region_windows": sorted({f"{r}|{w}" for r, w in zip(tab["region"], tab["window"])}),
                 "sklearn": sklearn.__version__, "n_events": n_ev, "alert_probability": ALERT}, MODELS_DIR / "monitor_model.joblib")
    print(f"\n[saved] {MODELS_DIR / 'monitor_model.joblib'}  (feature set: {best})")
    print(f"[saved] Reports/M_*.csv and Figures/monitor_results.png")


if __name__ == "__main__":
    main()
