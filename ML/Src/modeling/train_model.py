"""Step 5: compare models, test them honestly, and save the final model.

Run (from anywhere):   python ML\\Src\\modeling\\train_model.py

Protocol (so the result is not fooled by luck or by the future):
  A. SELECTION     leave-one-YEAR-out CV inside the training years only (<= TRAIN_END_YEAR).
                   Candidates are ranked here by Brier score. The test years are never touched.
  B. HOLD-OUT TEST the chosen model is fitted on the training years and scored ONCE on the later years.
                   (Other models are shown too, for transparency, but were not used to choose.)
  C. FORWARD CHAIN train on the past only, test the next 5 years, roll forward (does it work in practice?).
  D. ABLATION      same logistic model with different data groups: does soil moisture / VPD add anything?
  E. FINAL MODEL   refit on ALL events, threshold set from out-of-fold predictions, saved to ML/Models/.

Outputs: ML/Models/final_model.joblib + model_card.json, ML/Reports/*.csv, ML/Reports/results.json
"""
import json
import platform
import warnings

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.base import clone

from model_zoo import baselines, with_prep, zoo
from training_utils import (CAT_FEATURES, MODELS_DIR, REPORTS_DIR, SEED, TARGET, feature_sets, forward_chaining,
                            holdout_split, leave_one_year_out, load_training_table, out_of_fold, pick_threshold,
                            score, year_bootstrap_ci)

warnings.filterwarnings("ignore")
np.random.seed(SEED)

RISK_LOW_MAX, RISK_HIGH_MIN = 0.40, 0.60      # editable probability bands for the app (LOW / MODERATE / HIGH)


def run_candidates(df, sets, splits_fn, label):
    """Out-of-fold probabilities for every candidate. Returns (table, dict name -> oof Series)."""
    cands = {}
    base_cols = sets["compact (11 physical features)"]
    for n, m in baselines().items():
        cands[n] = (m, base_cols + CAT_FEATURES)
    for set_name in ("compact (11 physical features)", "all (incl. static soil/terrain)"):
        short = "compact" if set_name.startswith("compact") else "all"
        for n, m in zoo(sets[set_name]).items():
            cands[f"{n} [{short}]"] = (m, sets[set_name] + CAT_FEATURES)
    rows, oofs = [], {}
    for name, (model, cols) in cands.items():
        oof = out_of_fold(model, df, cols, list(splits_fn(df)))
        mask = oof.notna()
        oofs[name] = oof
        r = score(df.loc[mask, TARGET], oof[mask])
        r.update(model=name, evaluation=label)
        rows.append(r)
    tab = pd.DataFrame(rows).set_index("model")
    return tab.drop(columns="evaluation"), oofs, cands


def main():
    df, info = load_training_table()
    sets = feature_sets(info)
    tr_idx, te_idx = holdout_split(df)
    train, test = df.iloc[tr_idx].reset_index(drop=True), df.iloc[te_idx].reset_index(drop=True)

    print("=" * 72)
    print(f"Events: {len(df)}  (train {len(train)} / test {len(test)}).  "
          f"False-start rate: train {train[TARGET].mean():.1%}, test {test[TARGET].mean():.1%}")
    print("=" * 72)

    # ---------------------------------------------------------------- A. selection (train years only)
    print("\nA. Model selection: leave-one-year-out inside the training years")
    selA, oofA, cands = run_candidates(train, sets, leave_one_year_out, "selection")
    selA = selA.sort_values("brier")
    selA.to_csv(REPORTS_DIR / "A_selection_loyo_train.csv")
    show = ["pr_auc", "roc_auc", "brier", "brier_skill", "recall@prec0.6"]
    print(selA[show].round(3).to_string())

    real = [m for m in selA.index if not m.startswith("Baseline")]
    best_name = real[0]
    clim_brier = selA.loc["Baseline: region+window climatology", "brier"]
    beats = bool(selA.loc[best_name, "brier"] < clim_brier)
    print(f"\n-> Selected (lowest Brier among real models): {best_name}")
    print(f"   Beats region+window climatology in selection? {beats} "
          f"(Brier {selA.loc[best_name, 'brier']:.4f} vs {clim_brier:.4f})")

    # ---------------------------------------------------------------- B. hold-out test
    print("\nB. Hold-out test (fit on train years, score once on later years)")
    rows = []
    fitted = {}
    for name, (model, cols) in cands.items():
        m = clone(model).fit(train[cols], train[TARGET].values)
        p = m.predict_proba(test[cols])[:, 1]
        fitted[name] = (m, cols, p)
        r = score(test[TARGET], p, base_rate=train[TARGET].mean())
        r.update(model=name, selected=(name == best_name))
        rows.append(r)
    selB = pd.DataFrame(rows).set_index("model").sort_values("brier")
    selB.to_csv(REPORTS_DIR / "B_holdout_test.csv")
    print(selB[show + ["selected"]].round(3).to_string())
    p_best = fitted[best_name][2]
    ci_auc = year_bootstrap_ci(test, p_best, "roc_auc")
    print(f"   Selected model hold-out ROC-AUC {selB.loc[best_name, 'roc_auc']:.3f} "
          f"(95% year-bootstrap {ci_auc[0]:.2f}-{ci_auc[1]:.2f}); n={len(test)}")
    by_window = (test.assign(p=p_best).groupby(["region", "window"])
                 .apply(lambda g: pd.Series({"n": len(g), "actual_rate": g[TARGET].mean(), "mean_pred": g["p"].mean()}))
                 .round(3))
    by_window.to_csv(REPORTS_DIR / "B_holdout_by_window.csv")
    print("\n   Hold-out by region/window (actual vs predicted mean):")
    print(by_window.to_string())

    # ---------------------------------------------------------------- C. forward chaining (all years)
    print("\nC. Forward chaining (train on past, test next 5 years, from 1996)")
    chosen_model, chosen_cols = cands[best_name]
    base_model, base_cols = cands["Baseline: region+window climatology"]
    fc_splits = list(forward_chaining(df))
    fc_best = out_of_fold(chosen_model, df, chosen_cols, fc_splits)
    fc_base = out_of_fold(base_model, df, base_cols, fc_splits)
    m = fc_best.notna()
    fc_rows = []
    for n, o in ((best_name, fc_best), ("Baseline: region+window climatology", fc_base)):
        r = score(df.loc[m, TARGET], o[m]); r["model"] = n; fc_rows.append(r)
    fc = pd.DataFrame(fc_rows).set_index("model")
    fc.to_csv(REPORTS_DIR / "C_forward_chaining.csv")
    print(fc[show].round(3).to_string())

    # ---------------------------------------------------------------- D. ablation (which data helps?)
    print("\nD. Ablation: logistic regression with different data groups (leave-one-year-out, all years)")
    ab_rows = []
    lr_template = zoo(sets["compact (11 physical features)"])["Logistic (L2, C=0.1)"].named_steps["model"]
    for set_name, cols in sets.items():
        pipe = with_prep(clone(lr_template), cols)
        oof = out_of_fold(pipe, df, cols + CAT_FEATURES, list(leave_one_year_out(df)))
        r = score(df[TARGET], oof); r["feature_set"] = set_name; r["n_features"] = len(cols)
        r["brier_skill_ci_lo"], r["brier_skill_ci_hi"] = year_bootstrap_ci(df, oof, "brier_skill")
        ab_rows.append(r)
    base_oof = out_of_fold(base_model, df, base_cols, list(leave_one_year_out(df)))
    r = score(df[TARGET], base_oof); r["feature_set"] = "NONE (region+window climatology)"; r["n_features"] = 0
    r["brier_skill_ci_lo"], r["brier_skill_ci_hi"] = year_bootstrap_ci(df, base_oof, "brier_skill")
    ab_rows.insert(0, r)
    ab = pd.DataFrame(ab_rows).set_index("feature_set")
    ab.to_csv(REPORTS_DIR / "D_ablation.csv")
    print(ab[["n_features", "roc_auc", "pr_auc", "brier", "brier_skill"]].round(3).to_string())
    print("   (brier_skill = improvement over always predicting the overall rate; 0 = no skill)")

    # ---------------------------------------------------------------- grouped permutation importance (hold-out)
    groups = {
        "rainfall (CHIRPS)": [c for c in sets["rain only"] if c != "doy"],
        "atmosphere (POWER: VPD/ET0/temp/wind)": [c for c in sets["rain + atmosphere (VPD/ET0/temp)"] if c not in sets["rain only"]],
        "soil moisture (ERA5-Land)": [c for c in sets["rain + soil moisture"] if c not in sets["rain only"]],
        "static soil/terrain": [c for c in sets["all (incl. static soil/terrain)"]
                                if c in ("elevation_mean", "slope_mean", "cropland_fraction",
                                         "clay_0_5cm_mean", "sand_0_5cm_mean", "soc_0_5cm_mean")],
        "season timing (doy, month)": ["doy", "month"],
        "region + window": CAT_FEATURES,
    }
    # importance is measured on the 'all' variant of the chosen model so every group exists
    imp_name = best_name if "[all]" in best_name else best_name.replace("[compact]", "[all]")
    imp_model, imp_cols, _ = fitted[imp_name]
    rng = np.random.default_rng(SEED)
    base_brier = score(test[TARGET], imp_model.predict_proba(test[imp_cols])[:, 1])["brier"]
    imp_rows = []
    for g, cols in groups.items():
        cols = [c for c in cols if c in imp_cols]
        if not cols:
            continue
        inc = []
        for _ in range(100):
            Xp = test[imp_cols].copy()
            perm = rng.permutation(len(Xp))
            Xp[cols] = Xp[cols].iloc[perm].values
            inc.append(score(test[TARGET], imp_model.predict_proba(Xp)[:, 1])["brier"] - base_brier)
        imp_rows.append({"group": g, "n_features": len(cols), "brier_increase": np.mean(inc), "sd": np.std(inc)})
    imp = pd.DataFrame(imp_rows).sort_values("brier_increase", ascending=False)
    imp.to_csv(REPORTS_DIR / "E_group_importance_holdout.csv", index=False)
    print(f"\nGrouped permutation importance on hold-out ({imp_name}; bigger = model relies on it more):")
    print(imp.round(4).to_string(index=False))

    # ---------------------------------------------------------------- E. final model
    print("\nE. Final model: refit on ALL events")
    oof_all = out_of_fold(chosen_model, df, chosen_cols, list(leave_one_year_out(df)))
    thr, bal = pick_threshold(df[TARGET].values, oof_all.values)
    all_scores = score(df[TARGET], oof_all)
    ci = year_bootstrap_ci(df, oof_all, "roc_auc")
    pd.DataFrame({"event_id": df["event_id"], "region": df["region"], "window": df["window"], "year": df["year"],
                  "false_start": df[TARGET], "oof_probability": oof_all}).to_csv(
        REPORTS_DIR / "final_model_oof_predictions.csv", index=False)

    final = clone(chosen_model).fit(df[chosen_cols], df[TARGET].values)
    num_cols = [c for c in chosen_cols if c not in CAT_FEATURES]
    bundle = {
        "pipeline": final,
        "model_name": best_name,
        "numeric_features": num_cols,
        "categorical_features": CAT_FEATURES,
        "threshold": thr,
        "risk_bands": {"low_max": RISK_LOW_MAX, "high_min": RISK_HIGH_MIN},
        "climatology": {f"{r}|{w}": float(g[TARGET].mean()) for (r, w), g in df.groupby(["region", "window"])},
        "label_rules": info["label_rules"],
        "valid_region_windows": sorted({f"{r}|{w}" for r, w in zip(df["region"], df["window"])}),
        "trained_on_years": [int(df["year"].min()), int(df["year"].max())],
        "n_events": int(len(df)),
        "beats_climatology_on_holdout": bool(selB.loc[best_name, "brier"] < selB.loc["Baseline: region+window climatology", "brier"]),
    }
    joblib.dump(bundle, MODELS_DIR / "final_model.joblib")

    card = {
        "target": "false_start = 1 if a dry spell of >= {DRY_SPELL_DAYS} days (< {DRY_DAY_MM} mm/day) occurs within "
                  "{FOLLOW_DAYS} days after an onset trigger ({TRIGGER_MM} mm in {TRIGGER_DAYS} days, >= "
                  "{MIN_WET_DAYS_IN_TRIGGER} wet days).".format(**info["label_rules"]),
        "model": best_name, "n_events": int(len(df)), "train_years": bundle["trained_on_years"],
        "beats_region_window_climatology_in_selection": beats,
        "beats_region_window_climatology_on_holdout": bool(selB.loc[best_name, "brier"] < selB.loc["Baseline: region+window climatology", "brier"]),
        "holdout_test": {k: (None if pd.isna(v) else float(v)) for k, v in selB.loc[best_name, show + ["n"]].items()},
        "holdout_roc_auc_ci95": [float(ci_auc[0]), float(ci_auc[1])],
        "leave_one_year_out_all_events": {k: float(v) for k, v in all_scores.items()},
        "loyo_roc_auc_ci95": [float(ci[0]), float(ci[1])],
        "threshold_rule": "maximises balanced accuracy on leave-one-year-out predictions",
        "threshold": thr, "balanced_accuracy_at_threshold": bal,
        "risk_bands": bundle["risk_bands"],
        "versions": {"python": platform.python_version(), "sklearn": sklearn.__version__},
        "limitations": [
            "Label comes from rainfall rules (CHIRPS), not observed crop failure.",
            "Region points are provisional centroids, not official boundaries.",
            "About 230 events from 46 years: expect wide uncertainty; treat output as risk, not a forecast of crop death.",
        ],
    }
    (MODELS_DIR / "model_card.json").write_text(json.dumps(card, indent=2), encoding="utf-8")

    results = {"selected": best_name, "beats_climatology": beats, "threshold": thr,
               "selection_table": selA[show].round(4).reset_index().to_dict("records"),
               "holdout_table": selB[show + ["selected"]].round(4).reset_index().to_dict("records")}
    (REPORTS_DIR / "results.json").write_text(json.dumps(results, indent=2, default=float), encoding="utf-8")

    print(f"Leave-one-year-out (all {len(df)} events): ROC-AUC {all_scores['roc_auc']:.3f} "
          f"(95% {ci[0]:.2f}-{ci[1]:.2f}), PR-AUC {all_scores['pr_auc']:.3f}, Brier {all_scores['brier']:.3f}, "
          f"Brier skill {all_scores['brier_skill']:.3f}")
    print(f"Threshold {thr} (balanced accuracy {bal})")
    print(f"\n[saved] {MODELS_DIR / 'final_model.joblib'}\n[saved] {MODELS_DIR / 'model_card.json'}\n"
          f"[saved] tables in {REPORTS_DIR}")
    print("\nNext: python ML\\Src\\modeling\\findings_report.py   (makes the figures and the findings text)")


if __name__ == "__main__":
    main()
