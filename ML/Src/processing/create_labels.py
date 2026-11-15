"""Step 3: find onset events and label them false start (1) or good start (0).

Run:  python ML\\Src\\processing\\create_labels.py

Rules come from label_config.py. Labels use ONLY rainfall (CHIRPS):
  onset trigger = >= TRIGGER_MM mm over TRIGGER_DAYS days with >= MIN_WET_DAYS wet days,
                  inside the region's onset window
  false start   = a run of >= DRY_SPELL_DAYS dry days within the next FOLLOW_DAYS days

Outputs (Data/Processed/):
  onset_events.csv           one row per event (incl. events whose 30-day follow period is incomplete)
  no_onset_found.csv         region-years/windows where no trigger happened
  label_sensitivity.csv      false-start rate for other dry-spell definitions
  yearly_false_start_summary.csv
"""
import numpy as np
import pandas as pd

import label_config as cfg
from pipeline_common import load_table, save_table


def follow_stats(seg, dry_thr, spell_days):
    """Longest dry run in the follow window, and the day (1 = day after trigger) a qualifying spell begins."""
    run = max_run = 0
    first_start = np.nan
    for i, v in enumerate(seg < dry_thr):
        run = run + 1 if v else 0
        max_run = max(max_run, run)
        if run == spell_days and np.isnan(first_start):
            first_start = i - spell_days + 2
    return max_run, first_start


def find_events(region, g):
    rain = g["rain_mm"].reset_index(drop=True)
    dates = g["date"].reset_index(drop=True)
    wet = (rain >= cfg.TRIGGER_WET_DAY_MM).astype(float).where(rain.notna())
    sum3 = rain.rolling(cfg.TRIGGER_DAYS).sum()
    wet3 = wet.rolling(cfg.TRIGGER_DAYS).sum()
    trigger = ((sum3 >= cfg.TRIGGER_MM) & (wet3 >= cfg.MIN_WET_DAYS_IN_TRIGGER)).values
    x = rain.values

    events, no_onset = [], []
    years = range(max(cfg.FIRST_YEAR, dates.dt.year.min()), dates.dt.year.max() + 1)
    for year in years:
        for wname, start_md, end_md in cfg.ONSET_WINDOWS[region]:
            lo, hi = pd.Timestamp(f"{year}-{start_md}"), pd.Timestamp(f"{year}-{end_md}")
            if lo > dates.max():
                continue
            idx = np.where(trigger & (dates >= lo).values & (dates <= hi).values)[0]
            if len(idx) == 0:
                no_onset.append({"region": region, "window": wname, "year": year})
                continue

            chosen, last = [], -10
            for t in idx:
                if cfg.FIRST_TRIGGER_ONLY and chosen:
                    break
                if t - last >= cfg.TRIGGER_DAYS:          # non-overlapping triggers only
                    chosen.append(t)
                    last = t

            for n, t in enumerate(chosen):
                seg = x[t + 1: t + 1 + cfg.FOLLOW_DAYS]
                complete = len(seg) == cfg.FOLLOW_DAYS and not np.isnan(seg).any()
                max_run, first_start = (follow_stats(seg, cfg.DRY_DAY_MM, cfg.DRY_SPELL_DAYS)
                                        if complete else (np.nan, np.nan))
                events.append({
                    "event_id": f"{region}_{wname}_{year}" + (f"_{n + 1}" if n else ""),
                    "region": region, "window": wname, "year": year,
                    "trigger_date": dates[t],
                    "trigger_rain_mm": sum3[t], "trigger_wet_days": wet3[t],
                    "label_complete": complete,
                    "label_max_dry_run": max_run,
                    "label_dry_spell_start_day": first_start,
                    "false_start": (int(max_run >= cfg.DRY_SPELL_DAYS) if complete else np.nan),
                    "_seg": seg,
                })
    return events, no_onset


def sensitivity(events):
    """False-start rate if the dry-day threshold or spell length were different."""
    rows = []
    done = [e for e in events if e["label_complete"]]
    for thr in (0.1, 0.5, 1.0, 2.0):
        for days in (7, 8, 10, 12):
            flags = [follow_stats(e["_seg"], thr, days)[0] >= days for e in done]
            rows.append({"dry_day_mm": thr, "dry_spell_days": days,
                         "events": len(flags), "false_starts": int(sum(flags)),
                         "false_start_rate": round(float(np.mean(flags)), 3)})
    return pd.DataFrame(rows)


def main():
    rain = load_table("rainfall_daily")
    all_events, all_none = [], []
    for region, g in rain.groupby("region"):
        ev, none = find_events(region, g.sort_values("date"))
        all_events += ev
        all_none += none

    events = pd.DataFrame(all_events)
    sens = sensitivity(all_events)
    events = events.drop(columns="_seg").sort_values(["region", "trigger_date"]).reset_index(drop=True)

    save_table(events, "onset_events")
    save_table(pd.DataFrame(all_none, columns=["region", "window", "year"]), "no_onset_found")
    save_table(sens, "label_sensitivity")

    ok = events[events["label_complete"]]
    summary = (ok.groupby(["region", "window"])
                 .agg(events=("false_start", "size"), false_starts=("false_start", "sum"),
                      rate=("false_start", "mean")).round(3))
    print("\nEvents per region/window (complete labels only):")
    print(summary.to_string())
    print(f"\nTOTAL labelled events: {len(ok)}   false starts: {int(ok['false_start'].sum())} "
          f"({ok['false_start'].mean():.1%})")
    print(f"Incomplete (follow period not fully observed, excluded): {int((~events['label_complete']).sum())}")
    print(f"Region-windows with no onset trigger: {len(all_none)}")

    print("\nFalse-start rate under other definitions (rows: dry-day threshold mm, columns: spell days):")
    print(sens.pivot(index="dry_day_mm", columns="dry_spell_days", values="false_start_rate").to_string())

    yearly = (ok.groupby(["region", "year"])
                .agg(onsets=("false_start", "size"), false_starts=("false_start", "sum"))
                .reset_index())
    yearly["false_start_rate"] = (yearly["false_starts"] / yearly["onsets"]).round(3)
    save_table(yearly, "yearly_false_start_summary")


if __name__ == "__main__":
    main()
