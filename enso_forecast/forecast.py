"""Stage 2: live forecast of the 2026-27 peak from current conditions.

Models are fitted on 1982-2025 exactly as in the hindcasts; 2026 enters only as the
initial state. OISST results are converted to CPC's 1991-2020 base for reporting.
"""

import numpy as np
import pandas as pd

from . import data, folds, hindcast, models
from .targets import PEAK_CENTRES, season_label

YEAR = 2026
SEED = 20261022

# Models with real skill in Stage 1, and the start each one is run from.
# (Sep = state through September; oct2w = plus the first two October weeks.)
COMBINED = [("Recharge oscillator", "sep"), ("Regression (T, H)", "sep"),
            ("Seasonal AR(1)", "oct2w"), ("Damped persistence", "oct2w")]
HINDCAST_MODE = {"sep": "cv", "oct2w": "cv+oct2w", "jas": "trailing"}


def cpc_offsets(monthly):
    """Per peak-window position: (1982-2025 climatology) - (CPC 1991-2020 climatology),
    averaged over the 3 months of that season. Adding it converts our anomalies to CPC's base."""
    T, Tc = monthly["T"], monthly["T_cpc"]
    cpc = (T - Tc).loc["1991-01":"2020-12"]
    ours = T.loc["1982-01":"2025-12"]
    off = ours.groupby(ours.index.month).mean() - cpc.groupby(cpc.index.month).mean()
    out = []
    for k in range(PEAK_CENTRES):
        centre = (8 + k) % 12 + 1                           # Sep .. Mar
        months = [(centre - 2) % 12 + 1, centre, centre % 12 + 1]
        out.append(off.loc[months].mean())
    return np.array(out)


def calibration_factors(h):
    """Spread inflation per (model, mode): the factor that makes the 80% interval
    cover 80% of El Nino years (obs peak >= 0.5) in the hindcasts; never below 1."""
    h = h.dropna(subset=["pred_peak"])
    h = h[h.obs_peak >= 0.5]
    half = (h.q90 - h.q10) / 2
    ratio = (h.obs_peak - h.pred_peak).abs() / half
    k = ratio.groupby([h.model, h["mode"]]).quantile(0.8)
    return k.clip(lower=1.0)


def run_live(snapshot="latest"):
    monthly = data.load_monthly(snapshot)
    weekly = data.load_weekly(snapshot)
    oni = data.load_oni(snapshot)
    partial = pd.Series({y: hindcast.october_partial(weekly, y)
                         for y in sorted(set(weekly.index.year)) if y >= 1982})
    fold_list = {
        ("oisst", "sep"): folds.oisst_fold(monthly, YEAR, "live"),
        ("oisst", "oct2w"): folds.oisst_fold(monthly, YEAR, "live", partial),
        ("oni", "jas"): folds.oni_fold(oni, monthly, YEAR, "live"),
    }
    offsets = cpc_offsets(monthly)
    rows = []
    for (track, init), fold in fold_list.items():
        has_h = np.isfinite(fold.visible()["H"].iloc[-1])
        for m in models.all_models():
            if not has_h and m.name.startswith(("Recharge", "XRO", "Regression")):
                continue
            rng = np.random.default_rng([SEED, sum(map(ord, m.name + init))])
            m.fit(fold)
            out = m.predict(fold, rng)
            peak = np.asarray(out["peak"], float)
            timing = np.asarray(out["timing"], int)
            if track == "oisst":
                peak = peak + offsets[timing]
            rows.append({"track": track, "init": init, "model": m.name, "kind": m.kind,
                         "peak": peak, "timing": timing,
                         "T0": float(fold.visible()["T"].iloc[-1])})
    return rows, fold_list, offsets


def summarise(rows, h, skill):
    """Per-model table with raw and calibrated intervals, plus the skill-weighted mixture."""
    kfac = calibration_factors(h)
    el = skill[skill.subset == "el_nino"].set_index(["model", "mode"])
    rng = np.random.default_rng(SEED)
    out, mix = [], {}
    for r in rows:
        mode = HINDCAST_MODE[r["init"]]
        p = r["peak"]
        med = np.median(p)
        k = float(kfac.get((r["model"], mode), np.nan))
        cal = med + (k if np.isfinite(k) else 1.0) * (p - med)
        season_p = np.bincount(r["timing"], minlength=PEAK_CENTRES) / len(r["timing"])
        row = {"track": r["track"], "init": r["init"], "model": r["model"],
               "median": med, "q10": np.percentile(p, 10), "q90": np.percentile(p, 90),
               "k_inflate": k, "cal_q10": np.percentile(cal, 10), "cal_q90": np.percentile(cal, 90),
               "modal_season": season_label(int(season_p.argmax())),
               "timing_from": "model" if r["kind"] == "path" else "climatology",
               "hindcast_RMSE_elnino": el.peak_RMSE.get((r["model"], mode), np.nan),
               "in_combined": (r["model"], r["init"]) in COMBINED and r["track"] == "oisst"}
        for j in range(PEAK_CENTRES):
            row[f"P_{season_label(j)}"] = season_p[j]
        out.append(row)
        if row["in_combined"]:
            mix[(r["model"], r["init"])] = (cal, r["timing"], row["hindcast_RMSE_elnino"])
    table = pd.DataFrame(out)

    w = np.array([1 / v[2] ** 2 for v in mix.values()])
    w = w / w.sum()
    n = 20000
    pick = rng.choice(len(mix), n, p=w)
    vals = list(mix.values())
    peak = np.empty(n)
    timing = np.empty(n, int)
    for i, (cal, tim, _) in enumerate(vals):
        sel = pick == i
        j = rng.integers(0, len(cal), sel.sum())
        peak[sel], timing[sel] = cal[j], tim[j]
    weights = pd.Series(w, index=[f"{m} [{i}]" for m, i in mix.keys()])
    return table, peak, timing, weights
