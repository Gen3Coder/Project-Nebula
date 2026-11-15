# Findings (auto-generated from ML/Reports/*.csv)

* Events: 229 labelled onsets, 1981-2026. Label: false_start = 1 if a dry spell of >= 8 days (< 1.0 mm/day) occurs within 30 days after an onset trigger (20.0 mm in 3 days, >= 2 wet days).
* Selected model: **Random Forest [compact]** (chosen only on the training years).
* Hold-out test (n=54): ROC-AUC 0.60 (95% 0.51-0.72), PR-AUC 0.54, Brier 0.248, Brier skill +0.010.
* The selected model did NOT beat region+window climatology on the hold-out years (Brier 0.248 vs 0.227). Say this openly.
* Forward chaining (train on the past only): selected model Brier skill +0.012 vs climatology +0.016.
* Best ablation Brier skill across data groups: +0.008 (rain only). Values near 0 mean the extra data did not improve probability quality.
* The model leans most on: season timing (doy, month) (Brier increase 0.0135 when shuffled).
* Final threshold 0.56 (balanced accuracy 0.624).

## What to say honestly

* The false-start label is built from rainfall rules, so rainfall features overlap with how the label is made.
* With ~230 events (5 per year) differences between models are within noise; see the year-bootstrap intervals.
* The signal in soil moisture / VPD / temperature is weak at the onset day. Their strongest use may be daily monitoring during the 30 days after onset (not tested here).
* Hold-out Arsi meher had far fewer false starts than the training years: a rain-regime shift, or a window that is not a true onset. Review this window.
* Output is a risk probability, not a forecast of crop failure.

Figures: model_comparison.png, model_ablation.png, model_group_importance.png, model_calibration.png, model_holdout_by_window.png (ML/Figures).