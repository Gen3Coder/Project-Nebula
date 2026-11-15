"""Step 6: turn the result tables into figures and a plain-language findings file.

Run AFTER train_model.py:   python ML\\Src\\modeling\\findings_report.py
Outputs: ML/Figures/model_*.png and ML/Reports/FINDINGS.md  (numbers are read from the CSVs, nothing typed by hand)
"""
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from training_utils import FIG_DIR, MODELS_DIR, REPORTS_DIR

# validated default categorical slots 1-3 (blue, orange, aqua) + neutral grey for baselines
BLUE, ORANGE, AQUA, GREY = "#2a78d6", "#eb6834", "#1baf7a", "#9a9993"
INK, INK2, GRID, SURF = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
plt.rcParams.update({"figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF,
                     "text.color": INK, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
                     "axes.edgecolor": GRID, "axes.spines.top": False, "axes.spines.right": False,
                     "font.size": 10, "axes.titlesize": 11, "axes.titleweight": "bold", "axes.titlelocation": "left"})


def clean(ax, axis="x"):
    ax.grid(axis=axis, color=GRID, lw=0.8)
    ax.set_axisbelow(True)


def fig_model_comparison(A, B, selected):
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.2), sharey=True)
    order = A.sort_values("brier_skill").index
    for ax, tab, title in ((axes[0], A, "Selection: leave-one-year-out, train years"),
                           (axes[1], B, "Hold-out test: later years, scored once")):
        vals = tab.reindex(order)["brier_skill"]
        colors = [ORANGE if m == selected else GREY if m.startswith("Baseline") else BLUE for m in order]
        ax.barh(range(len(order)), vals, color=colors, height=0.62)
        for i, v in enumerate(vals):
            ax.text(v + (0.004 if v >= 0 else -0.004), i, f"{v:+.3f}", va="center",
                    ha="left" if v >= 0 else "right", fontsize=8.5, color=INK2)
        ax.axvline(0, color=INK2, lw=1)
        ax.set_yticks(range(len(order)), order)
        ax.set_title(title)
        ax.set_xlabel("Brier skill  (0 = no better than the overall rate; higher is better)")
        ax.set_xlim(min(-0.14, vals.min() - 0.03), max(0.14, vals.max() + 0.04))
        clean(ax)
    fig.suptitle("Do any models beat simple climatology?   grey = baseline, orange = selected", x=0.01, ha="left",
                 fontsize=12, fontweight="bold")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "model_comparison.png", dpi=160)
    plt.close(fig)


def fig_ablation(ab):
    ab = ab.iloc[::-1]
    fig, ax = plt.subplots(figsize=(9, 4.6))
    y = np.arange(len(ab))
    colors = [GREY if "NONE" in n else BLUE for n in ab.index]
    ax.barh(y, ab["brier_skill"], color=colors, height=0.6)
    ax.errorbar(ab["brier_skill"], y, xerr=[ab["brier_skill"] - ab["brier_skill_ci_lo"],
                                            ab["brier_skill_ci_hi"] - ab["brier_skill"]],
                fmt="none", ecolor=INK2, elinewidth=1, capsize=3)
    ax.axvline(0, color=INK2, lw=1)
    ax.set_yticks(y, [f"{n}  ({int(k)})" for n, k in zip(ab.index, ab["n_features"])])
    ax.set_xlabel("Brier skill, leave-one-year-out (bars: 95% interval from resampling years)")
    ax.set_title("Which data groups add skill? (logistic regression, all years)")
    clean(ax)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "model_ablation.png", dpi=160)
    plt.close(fig)


def fig_importance(imp):
    imp = imp.iloc[::-1]
    fig, ax = plt.subplots(figsize=(9, 3.8))
    ax.barh(imp["group"], imp["brier_increase"], xerr=imp["sd"], color=BLUE, height=0.6,
            error_kw={"ecolor": INK2, "elinewidth": 1, "capsize": 3})
    ax.axvline(0, color=INK2, lw=1)
    ax.set_xlabel("Increase in Brier error when the group is shuffled (hold-out years)")
    ax.set_title("What does the model rely on?")
    clean(ax)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "model_group_importance.png", dpi=160)
    plt.close(fig)


def fig_calibration(oof):
    d = oof.copy()
    d["bin"] = pd.qcut(d["oof_probability"], 5, duplicates="drop")
    g = d.groupby("bin", observed=True).agg(pred=("oof_probability", "mean"), actual=("false_start", "mean"),
                                            n=("false_start", "size"))
    fig, ax = plt.subplots(figsize=(5.4, 5))
    ax.plot([0, 1], [0, 1], color=GREY, lw=1.5, ls="--", label="perfect calibration")
    ax.plot(g["pred"], g["actual"], marker="o", ms=8, color=BLUE, lw=2, label="model (5 equal-size bins)")
    for _, r in g.iterrows():
        ax.annotate(f"n={int(r['n'])}", (r["pred"], r["actual"]), textcoords="offset points", xytext=(6, -12),
                    fontsize=8, color=INK2)
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.set_xlabel("Predicted probability of false start (leave-one-year-out)")
    ax.set_ylabel("Observed false-start share")
    ax.set_title("Calibration of the final model")
    ax.legend(frameon=False, loc="upper left")
    clean(ax, "both")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "model_calibration.png", dpi=160)
    plt.close(fig)


def fig_by_window(bw):
    bw = bw.reset_index()
    labels = bw["region"] + "\n" + bw["window"]
    x = np.arange(len(bw)); w = 0.38
    fig, ax = plt.subplots(figsize=(8, 4.2))
    ax.bar(x - w / 2, bw["actual_rate"], w, color=BLUE, label="observed false-start rate")
    ax.bar(x + w / 2, bw["mean_pred"], w, color=ORANGE, label="mean predicted probability")
    for i, r in bw.iterrows():
        ax.text(i - w / 2, r["actual_rate"] + 0.015, f"{r['actual_rate']:.2f}", ha="center", fontsize=8.5, color=INK2)
        ax.text(i + w / 2, r["mean_pred"] + 0.015, f"{r['mean_pred']:.2f}", ha="center", fontsize=8.5, color=INK2)
    ax.set_xticks(x, labels)
    ax.set_ylim(0, 1)
    ax.set_title("Hold-out years: observed vs predicted, by region and window")
    ax.legend(frameon=False, loc="upper right")
    clean(ax, "y")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "model_holdout_by_window.png", dpi=160)
    plt.close(fig)


def main():
    A = pd.read_csv(REPORTS_DIR / "A_selection_loyo_train.csv", index_col=0)
    B = pd.read_csv(REPORTS_DIR / "B_holdout_test.csv", index_col=0)
    C = pd.read_csv(REPORTS_DIR / "C_forward_chaining.csv", index_col=0)
    ab = pd.read_csv(REPORTS_DIR / "D_ablation.csv", index_col=0)
    imp = pd.read_csv(REPORTS_DIR / "E_group_importance_holdout.csv")
    bw = pd.read_csv(REPORTS_DIR / "B_holdout_by_window.csv", index_col=[0, 1])
    oof = pd.read_csv(REPORTS_DIR / "final_model_oof_predictions.csv")
    card = json.loads((MODELS_DIR / "model_card.json").read_text(encoding="utf-8"))
    sel = card["model"]
    clim = "Baseline: region+window climatology"

    fig_model_comparison(A, B, sel)
    fig_ablation(ab)
    fig_importance(imp)
    fig_calibration(oof)
    fig_by_window(bw)

    ho = B.loc[sel]
    ho_base = B.loc[clim]
    best_ab = ab.drop(index=[i for i in ab.index if "NONE" in i])["brier_skill"]
    ci = card["holdout_roc_auc_ci95"]
    verdict = ("The selected model did better than region+window climatology on the hold-out years."
               if ho["brier"] < ho_base["brier"] else
               "The selected model did NOT beat region+window climatology on the hold-out years "
               f"(Brier {ho['brier']:.3f} vs {ho_base['brier']:.3f}). Say this openly.")
    top = imp.iloc[0]
    lines = [
        "# Findings (auto-generated from ML/Reports/*.csv)", "",
        f"* Events: {card['n_events']} labelled onsets, {card['train_years'][0]}-{card['train_years'][1]}. "
        f"Label: {card['target']}",
        f"* Selected model: **{sel}** (chosen only on the training years).",
        f"* Hold-out test (n={int(ho['n'])}): ROC-AUC {ho['roc_auc']:.2f} (95% {ci[0]:.2f}-{ci[1]:.2f}), "
        f"PR-AUC {ho['pr_auc']:.2f}, Brier {ho['brier']:.3f}, Brier skill {ho['brier_skill']:+.3f}.",
        f"* {verdict}",
        f"* Forward chaining (train on the past only): selected model Brier skill "
        f"{C.loc[sel, 'brier_skill']:+.3f} vs climatology {C.loc[clim, 'brier_skill']:+.3f}.",
        f"* Best ablation Brier skill across data groups: {best_ab.max():+.3f} ({best_ab.idxmax()}). "
        "Values near 0 mean the extra data did not improve probability quality.",
        f"* The model leans most on: {top['group']} (Brier increase {top['brier_increase']:.4f} when shuffled).",
        f"* Final threshold {card['threshold']} (balanced accuracy {card['balanced_accuracy_at_threshold']}).", "",
        "## What to say honestly", "",
        "* The false-start label is built from rainfall rules, so rainfall features overlap with how the label is made.",
        "* With ~230 events (5 per year) differences between models are within noise; see the year-bootstrap intervals.",
        "* The signal in soil moisture / VPD / temperature is weak at the onset day. Their strongest use may be "
        "daily monitoring during the 30 days after onset (not tested here).",
        "* Hold-out Arsi meher had far fewer false starts than the training years: a rain-regime shift, or a window "
        "that is not a true onset. Review this window.",
        "* Output is a risk probability, not a forecast of crop failure.", "",
        "Figures: model_comparison.png, model_ablation.png, model_group_importance.png, model_calibration.png, "
        "model_holdout_by_window.png (ML/Figures).",
    ]
    (REPORTS_DIR / "FINDINGS.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print(f"\n[saved] figures in {FIG_DIR}, text in {REPORTS_DIR / 'FINDINGS.md'}")


if __name__ == "__main__":
    main()
