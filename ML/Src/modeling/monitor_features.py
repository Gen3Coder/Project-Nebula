"""Daily monitoring after an onset trigger: feature calculation, wording and advice.

Used by BOTH train_monitor.py (training) and predict_monitor.py (live), so the numbers are computed the same way.
Day T = trigger day. "Day d" = d days after T. Only data up to day d is used for the risk on day d.
"""
import numpy as np

FOLLOW_DAYS = 30        # same as label_config.FOLLOW_DAYS
DRY_SPELL_DAYS = 8      # same as label_config.DRY_SPELL_DAYS
DRY_DAY_MM = 1.0        # same as label_config.DRY_DAY_MM

FEATURE_GROUPS = {
    "dry-run only": ["day_after", "dry_run_now", "max_dry_run_so_far"],
    "rain": ["day_after", "dry_run_now", "max_dry_run_so_far", "dry_days_so_far", "rain_since"],
    "atmosphere": ["vpd_3d", "et0_3d", "tmax_3d", "vpd_mean_since", "et0_mean_since"],
    "soil": ["sm_l1_now", "sm_l2_now", "sm_l1_chg_since", "sm_l2_chg_since", "sm_l1_chg3", "sm_l2_chg3"],
}
CAT = ["region", "window"]


def _run_lengths(dry):
    run, out = 0, []
    for f in dry:
        run = run + 1 if f else 0
        out.append(run)
    return np.array(out, dtype=float)


def day_features(rain, vpd, et0, tmax, sm1, sm2, i0, i, doy, trigger_rain_mm):
    """Features on day index i (> i0) for a trigger on day index i0. Arrays are daily series of one region."""
    d = i - i0
    post = rain[i0 + 1: i + 1]
    runs = _run_lengths(post < DRY_DAY_MM)
    j3 = max(i - 3, i0)
    since = slice(i0 + 1, i + 1)
    last3 = slice(max(i - 2, i0 + 1), i + 1)
    return {
        "day_after": d,
        "dry_run_now": runs[-1],
        "max_dry_run_so_far": runs.max(),
        "dry_days_so_far": float((post < DRY_DAY_MM).sum()),
        "rain_since": float(post.sum()),
        "trigger_rain_mm": float(trigger_rain_mm),
        "doy": float(doy),
        "vpd_3d": float(np.nanmean(vpd[last3])), "et0_3d": _nm(et0[last3]), "tmax_3d": float(np.nanmean(tmax[last3])),
        "vpd_mean_since": float(np.nanmean(vpd[since])), "et0_mean_since": _nm(et0[since]),
        "sm_l1_now": float(sm1[i]), "sm_l2_now": float(sm2[i]),
        "sm_l1_chg_since": float(sm1[i] - sm1[i0]), "sm_l2_chg_since": float(sm2[i] - sm2[i0]),
        "sm_l1_chg3": float(sm1[i] - sm1[j3]), "sm_l2_chg3": float(sm2[i] - sm2[j3]),
    }


def _nm(a):
    a = np.asarray(a, dtype=float)
    return float(np.nanmean(a)) if np.isfinite(a).any() else np.nan


def still_undecided(feat):
    """True while a qualifying dry spell has neither happened nor become impossible."""
    if feat["max_dry_run_so_far"] >= DRY_SPELL_DAYS:
        return False
    left = FOLLOW_DAYS - feat["day_after"]
    return bool(left >= DRY_SPELL_DAYS or feat["dry_run_now"] + left >= DRY_SPELL_DAYS)


# ---------------------------------------------------------------- wording
RISK_BANDS = [(0.80, "VERY HIGH"), (0.60, "HIGH"), (0.40, "MODERATE"), (0.0, "LOW")]

ADVICE = {  # DRAFT wording: have an agronomist review before it goes to farmers
    "VERY HIGH": "Hold fertilizer. Prepare to re-sow if no rain in the next 3-4 days.",
    "HIGH": "Hold fertilizer and watch the rain forecast. Check seedling emergence in the field.",
    "MODERATE": "Delay top-dressing and keep monitoring daily.",
    "LOW": "Conditions are holding. Continue normal field work.",
    "CONFIRMED": "A dry spell has been confirmed. Check emergence and re-sow when soil moisture recovers.",
    "RESOLVED": "The risk window has passed without a qualifying dry spell. Seedlings should be establishing.",
}


def risk_label(p):
    return next(name for cut, name in RISK_BANDS if p >= cut)


def soil_trend_label(chg3, cuts):
    q_fast, q_fall, q_rise = cuts
    if chg3 <= q_fast:
        return "falling fast"
    if chg3 <= q_fall:
        return "falling"
    if chg3 >= q_rise:
        return "rising"
    return "stable"
