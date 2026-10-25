#!/usr/bin/env python3
"""Skill-tested forecast of the peak 3-month Nino 3.4 anomaly (2026-27 El Nino).

Stage 1 (hindcast): runs every model on 1982-2025 October starts and writes skill tables.
Stage 2 (forecast): runs the skilful models from current (2026) conditions; needs Stage 1 outputs.

Inputs:  data/raw/<snapshot>/ (from fetch_enso_indices.sh), read only
Outputs: outputs/forecast/

Dependencies: pip install numpy pandas scipy matplotlib xarray XRO
"""

import argparse
import importlib.metadata
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from enso_forecast import data, hindcast

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(SCRIPT_DIR, "outputs", "forecast")

RUNS = [  # (track, mode, years)
    ("oisst", "cv", range(1982, 2026)),
    ("oisst", "expanding", range(1995, 2026)),
    ("oisst", "cv+oct2w", range(1982, 2026)),        # sensitivity: + first two October weeks
    ("oni", "trailing", range(1982, 2026)),
]


def write_manifest(snapshot, extra=None, name="manifest.json"):
    try:
        commit = subprocess.check_output(["git", "-C", SCRIPT_DIR, "rev-parse", "HEAD"],
                                         text=True).strip()
        dirty = bool(subprocess.check_output(["git", "-C", SCRIPT_DIR, "status", "--porcelain"],
                                             text=True).strip())
    except (OSError, subprocess.CalledProcessError):
        commit, dirty = None, None
    pkgs = {p: importlib.metadata.version(p)
            for p in ["numpy", "pandas", "scipy", "xarray", "matplotlib", "xro"]}
    manifest = {
        "run_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "snapshot": os.path.basename(data.snapshot_dir(snapshot)),
        "data_files": data.read_manifest(snapshot)["files"],
        "python": sys.version.split()[0],
        "packages": pkgs,
        "git_commit": commit, "git_dirty": dirty,
        "seed": hindcast.SEED,
        **(extra or {}),
    }
    with open(os.path.join(OUT_DIR, name), "w") as f:
        json.dump(manifest, f, indent=2)


def stage_hindcast(snapshot, workers):
    parts = []
    for track, mode, years in RUNS:
        print(f"Hindcast {track}/{mode} {years.start}-{years.stop - 1} ...", flush=True)
        parts.append(hindcast.run(track, mode, years, snapshot, workers))
    h = pd.concat(parts, ignore_index=True)
    h.to_csv(os.path.join(OUT_DIR, "hindcast_raw.csv"), index=False, float_format="%.4f")
    skill = hindcast.skill_table(h)
    skill.to_csv(os.path.join(OUT_DIR, "skill_table.csv"), index=False, float_format="%.3f")
    from enso_forecast import report
    report.write_skill_markdown(skill, os.path.join(OUT_DIR, "skill_table.md"))
    report.plot_hindcasts(h, os.path.join(OUT_DIR, "hindcast_scatter.png"))
    write_manifest(snapshot, {"stage": "hindcast",
                              "runs": [[t, m, years.start, years.stop - 1] for t, m, years in RUNS]})
    print(f"Wrote {OUT_DIR}/hindcast_raw.csv, skill_table.csv/.md, hindcast_scatter.png, manifest.json")
    return h, skill


RECORD_OISST = 2.53   # 2015-16 peak 3-month mean, OISST Nino 3.4, CPC base (NDJ)
IRI_PLUME = 3.5       # IRI October 2026 plume, multi-model mean, OND/NDJ (as given in the brief)


def stage_forecast(snapshot):
    from enso_forecast import forecast, report
    if not os.path.exists(os.path.join(OUT_DIR, "hindcast_raw.csv")):
        sys.exit("Run --stage hindcast first: the forecast uses its skill and calibration.")
    h = pd.read_csv(os.path.join(OUT_DIR, "hindcast_raw.csv"))
    skill = pd.read_csv(os.path.join(OUT_DIR, "skill_table.csv"))
    rows, fold_list, offsets = forecast.run_live(snapshot)
    table, combined, timing, weights = forecast.summarise(rows, h, skill)
    table.to_csv(os.path.join(OUT_DIR, "forecast_table.csv"), index=False, float_format="%.3f")
    report.write_forecast_markdown(table, combined, timing, weights,
                                   os.path.join(OUT_DIR, "forecast_table.md"), RECORD_OISST, IRI_PLUME)
    monthly = data.load_monthly(snapshot)
    oct_cpc = data.load_weekly(snapshot)["T_cpc"].loc["2026-10-01":"2026-10-14"].mean()
    report.plot_forecast(table, combined, monthly, oct_cpc, RECORD_OISST, IRI_PLUME,
                         os.path.join(OUT_DIR, "forecast_2026.png"))
    lo, med, hi = np.percentile(combined, [10, 50, 90])
    summary = {"combined_median": med, "combined_q10": lo, "combined_q90": hi,
               "season_probs": dict(zip(["ASO", "SON", "OND", "NDJ", "DJF", "JFM", "FMA"],
                                        (np.bincount(timing, minlength=7) / len(timing)).tolist())),
               "P_exceed": {str(v): float((combined > v).mean()) for v in [RECORD_OISST, 3.0, IRI_PLUME, 4.0]},
               "weights": weights.to_dict(), "cpc_base_offsets_by_season": offsets.tolist()}
    write_manifest(snapshot, {"stage": "forecast", "forecast_year": forecast.YEAR,
                              "init_state": {f"{t}/{i}": float(f.visible()["T"].iloc[-1])
                                             for (t, i), f in fold_list.items()},
                              "summary": summary}, name="manifest_forecast.json")
    print(f"Combined peak: {med:+.2f} C (80%: {lo:+.2f} to {hi:+.2f}), OISST CPC base")
    print(f"Wrote {OUT_DIR}/forecast_table.csv/.md, forecast_2026.png, manifest_forecast.json")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--stage", choices=["hindcast", "forecast"], default="hindcast")
    parser.add_argument("--snapshot", default="latest", help="data/raw/<snapshot> to read")
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    os.makedirs(OUT_DIR, exist_ok=True)
    if args.stage == "hindcast":
        stage_hindcast(args.snapshot, args.workers)
    else:
        stage_forecast(args.snapshot)


if __name__ == "__main__":
    main()
