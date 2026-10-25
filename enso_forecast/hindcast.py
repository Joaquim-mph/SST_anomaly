"""Hindcast loops and skill metrics."""

from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd
from scipy import stats

from . import data, folds, models, targets

SEED = 20261022
STRONG = 1.5

# Hindcast years must have their full target (to Apr of y+1) in the record.
DATA_END_HINDCAST = "2026-04"


def crps_samples(x, y):
    x = np.sort(np.asarray(x, float))
    n = len(x)
    e1 = np.abs(x - y).mean()
    # E|X - X'| from sorted samples
    e2 = 2.0 * np.sum((2 * np.arange(1, n + 1) - n - 1) * x) / (n * n)
    return e1 - 0.5 * e2


def october_partial(weekly, year):
    """Mean OISST Nino 3.4 total of the weekly values centred on 1-14 October."""
    w = weekly["T"].loc[f"{year}-10-01":f"{year}-10-14"]
    if len(w) != 2:
        raise ValueError(f"expected 2 October weeks in {year}, got {len(w)}")
    return w.mean()


def _run_fold(args):
    track, mode, year, snapshot = args
    rng = np.random.default_rng([SEED, year, sum(map(ord, mode))])
    if track == "oisst":
        df = data.load_monthly(snapshot).loc[:DATA_END_HINDCAST]
        base, _, extra = mode.partition("+")
        oct_partial = None
        if extra == "oct2w":
            weekly = data.load_weekly(snapshot)
            oct_partial = pd.Series({y: october_partial(weekly, y)
                                     for y in sorted(set(weekly.index.year)) if y >= 1982})
        fold = folds.oisst_fold(df, year, base, oct_partial)
    else:
        oni = data.load_oni(snapshot).loc[:DATA_END_HINDCAST]
        mon = data.load_monthly(snapshot).loc[:DATA_END_HINDCAST]
        fold = folds.oni_fold(oni, mon, year)
    obs = targets.observed_target(fold)
    if obs is None:
        return []
    with_pred = fold.visible()[["H"]].iloc[-1].notna().all()
    rows = []
    for m in models.all_models():
        rec = {"track": track, "mode": mode, "year": year, "model": m.name,
               "obs_peak": obs["peak"], "obs_timing": obs["timing"],
               "T0": fold.visible()["T"].iloc[-1]}
        for L in range(targets.LEADS):
            rec[f"obs_lead{L + 1}"] = obs["leads"][L]
        try:
            if not with_pred and m.name.startswith(("Recharge", "XRO", "Regression")):
                raise ValueError("no H at init")
            m.fit(fold)
            out = m.predict(fold, rng)
        except (ValueError, np.linalg.LinAlgError, RuntimeError) as e:
            rec["error"] = str(e)
            rows.append(rec)
            continue
        p = out["peak"]
        q = np.percentile(p, [10, 25, 50, 75, 90])
        rec.update({"pred_peak": q[2], "q10": q[0], "q25": q[1], "q75": q[3], "q90": q[4],
                    "pred_mean": p.mean(), "crps": crps_samples(p, obs["peak"]),
                    "pred_timing": int(np.bincount(out["timing"], minlength=7).argmax())})
        for L in range(targets.LEADS):
            rec[f"pred_lead{L + 1}"] = (np.nan if out["leads"] is None else out["leads"][L])
        rows.append(rec)
    return rows


def run(track, mode, years, snapshot="latest", workers=8):
    jobs = [(track, mode, y, snapshot) for y in years]
    with ProcessPoolExecutor(workers) as ex:
        rows = [r for chunk in ex.map(_run_fold, jobs) for r in chunk]
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- metrics

def _coverage(hit):
    n, k = len(hit), int(hit.sum())
    if n == 0:
        return np.nan, np.nan, np.nan
    ci = stats.binomtest(k, n).proportion_ci(0.9)
    return k / n, ci.low, ci.high


def skill_table(h):
    """Skill per (track, mode, model, subset)."""
    h = h.dropna(subset=["pred_peak"]).copy()
    h["err"] = h.pred_peak - h.obs_peak
    h["in80"] = (h.obs_peak >= h.q10) & (h.obs_peak <= h.q90)
    h["in50"] = (h.obs_peak >= h.q25) & (h.obs_peak <= h.q75)
    out = []
    for (track, mode, model), g in h.groupby(["track", "mode", "model"], sort=False):
        pers = h[(h.track == track) & (h["mode"] == mode) & (h.model == "Persistence")]
        for subset, sel in [("all", g.index), ("el_nino", g.index[g.obs_peak >= 0.5]),
                            ("strong", g.index[g.obs_peak >= STRONG])]:
            s = g.loc[sel]
            if len(s) == 0:
                continue
            ps = pers[pers.year.isin(s.year)]
            ens = s[s.obs_peak >= 0.5]
            c80, lo80, hi80 = _coverage(s.in80)
            c50, _, _ = _coverage(s.in50)
            row = {"track": track, "mode": mode, "model": model, "subset": subset,
                   "n": len(s), "years": f"{s.year.min()}-{s.year.max()}",
                   "peak_MAE": s.err.abs().mean(), "peak_RMSE": np.sqrt((s.err ** 2).mean()),
                   "peak_bias": s.err.mean(),
                   "MSE_SS_vs_persist": 1 - (s.err ** 2).mean() / ((ps.pred_peak - ps.obs_peak) ** 2).mean(),
                   "timing_MAE_mo": (ens.pred_timing - ens.obs_timing).abs().mean() if len(ens) else np.nan,
                   "timing_exact": (ens.pred_timing == ens.obs_timing).mean() if len(ens) else np.nan,
                   "cov80": c80, "cov80_lo": lo80, "cov80_hi": hi80, "cov50": c50,
                   "CRPS": s.crps.mean()}
            if subset == "all":
                for L in range(1, targets.LEADS + 1):
                    ok = s[[f"pred_lead{L}", f"obs_lead{L}"]].dropna()
                    row[f"corr_lead{L}"] = (np.corrcoef(ok.iloc[:, 0], ok.iloc[:, 1])[0, 1]
                                            if len(ok) > 5 else np.nan)
            out.append(row)
    return pd.DataFrame(out)
