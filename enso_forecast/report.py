"""Tables and figures for the hindcast evaluation."""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

TRACK_LABEL = {
    ("oisst", "cv"): "OISST Nino 3.4, leave-one-season-out CV, 1982-2025",
    ("oisst", "expanding"): "OISST Nino 3.4, strict expanding window, 1995-2025",
    ("oisst", "cv+oct2w"): "Sensitivity: OISST CV with the first two October weeks added (SST-only models; leads start in Nov)",
    ("oni", "trailing"): "ONI-like (ERSSTv5, trailing 30-yr base), expanding window, 1982-2025",
}
SUBSET_LABEL = {"all": "All years", "el_nino": "El Nino years (obs peak >= 0.5)",
                "strong": "Strong events (obs peak >= 1.5)"}


def write_skill_markdown(skill, path):
    lines = ["# Hindcast skill: peak 3-month Nino 3.4, October starts", "",
             "Errors in degC; timing error in months (El Nino years only); "
             "cov80 = fraction of years inside the 80% interval (90% binomial CI); "
             "MSE-SS = 1 - MSE/MSE(persistence). Lead correlations are monthly "
             "(OISST: Oct..Jan) or 3-month seasons (ONI: ASO..NDJ).", ""]
    for (track, mode), g in skill.groupby(["track", "mode"], sort=False):
        lines += [f"## {TRACK_LABEL[(track, mode)]}", ""]
        for subset, s in g.groupby("subset", sort=False):
            lines += [f"### {SUBSET_LABEL[subset]} (n = {s.n.iloc[0]})", ""]
            cols = ["model", "peak_MAE", "peak_RMSE", "peak_bias", "MSE_SS_vs_persist",
                    "timing_MAE_mo", "cov80", "cov50", "CRPS"]
            if subset == "all":
                cols += [f"corr_lead{L}" for L in range(1, 5)]
            t = s[cols].copy()
            t["cov80"] = [f"{c:.2f} ({lo:.2f}-{hi:.2f})"
                          for c, lo, hi in zip(s.cov80, s.cov80_lo, s.cov80_hi)]
            lines.append("| " + " | ".join(cols) + " |")
            lines.append("|" + "---|" * len(cols))
            for _, r in t.iterrows():
                cells = [r[c] if isinstance(r[c], str) else f"{r[c]:+.2f}" if c == "peak_bias"
                         else f"{r[c]:.2f}" for c in cols]
                lines.append("| " + " | ".join(cells) + " |")
            lines.append("")
    with open(path, "w") as f:
        f.write("\n".join(lines))


def plot_hindcasts(h, path):
    """Forecast vs observed peak with 80% intervals, one panel per model, one figure row per run."""
    h = h.dropna(subset=["pred_peak"])
    runs = list(h.groupby(["track", "mode"], sort=False).groups)
    model_names = list(dict.fromkeys(h.model))
    fig, axes = plt.subplots(len(runs), len(model_names), figsize=(2.1 * len(model_names), 2.4 * len(runs)),
                             sharex=True, sharey=True, squeeze=False)
    for i, run in enumerate(runs):
        for j, name in enumerate(model_names):
            ax = axes[i, j]
            g = h[(h.track == run[0]) & (h["mode"] == run[1]) & (h.model == name)]
            strong = g.obs_peak >= 1.5
            ax.plot([-2.5, 3.5], [-2.5, 3.5], color="0.7", lw=0.8)
            ax.errorbar(g.obs_peak, g.pred_peak, yerr=[g.pred_peak - g.q10, g.q90 - g.pred_peak],
                        fmt="none", ecolor="0.6", lw=0.6)
            ax.scatter(g.obs_peak[~strong], g.pred_peak[~strong], s=8, color="#4a6fa5")
            ax.scatter(g.obs_peak[strong], g.pred_peak[strong], s=14, color="#c0392b")
            for _, r in g[strong].iterrows():
                ax.annotate(str(r.year), (r.obs_peak, r.pred_peak), fontsize=5, xytext=(2, -6),
                            textcoords="offset points")
            if i == 0:
                ax.set_title(name, fontsize=7)
            if j == 0:
                ax.set_ylabel(f"{run[0]}/{run[1]}\nforecast peak (C)", fontsize=7)
            if i == len(runs) - 1:
                ax.set_xlabel("observed peak (C)", fontsize=7)
            ax.tick_params(labelsize=6)
    fig.suptitle("Hindcasts of peak 3-month Nino 3.4 from October starts (bars: 80% intervals; red: strong events)",
                 fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


INK, MUTED, BLUE, ORANGE, GRID = "#0b0b0b", "#8a8984", "#2a78d6", "#eb6834", "#e4e3df"


def plot_forecast(table, combined, monthly, oct_partial_cpc, record, iri, path):
    """Left: observed 2025-26 trajectory and the combined peak forecast.
    Right: each OISST model's peak with its calibrated 80% interval."""
    obs = monthly["T_cpc"].loc["2025-01":]
    x = obs.index.to_timestamp()
    lo, med, hi = np.percentile(combined, [10, 50, 90])

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 5.2), gridspec_kw={"width_ratios": [1.05, 1]})
    for ax in (a1, a2):
        ax.spines[["top", "right"]].set_visible(False)
        ax.tick_params(labelsize=8, colors="#52514e")
        ax.grid(axis="y" if ax is a1 else "x", color=GRID, lw=0.8)
        ax.set_axisbelow(True)

    a1.plot(x, obs.values, color=INK, lw=2, marker="o", ms=4, label="OISST monthly (CPC)")
    oct_x = pd.Timestamp("2026-10-01")
    a1.plot([oct_x], [oct_partial_cpc], marker="o", ms=7, mfc="white", mec=INK, mew=1.5, ls="none",
            label="1-14 Oct (weekly)")
    dec = pd.Timestamp("2026-12-01")
    a1.errorbar([dec], [med], yerr=[[med - lo], [hi - med]], fmt="o", color=BLUE, ms=8, lw=2, capsize=0,
                label="Forecast peak 3-month mean,\nmodel combination (80% range)")
    a1.plot([pd.Timestamp("2026-11-01"), dec], [iri, iri], marker="D", ms=6, color=ORANGE, ls="none",
            label=f"IRI Oct plume mean (~{iri:+.1f})")
    a1.axhline(record, color=MUTED, ls="--", lw=1)
    a1.text(pd.Timestamp("2025-01-15"), record + 0.06, f"2015-16 peak 3-month mean {record:+.2f}",
            fontsize=8, color="#52514e")
    a1.axhline(0, color=MUTED, lw=0.8)
    a1.annotate(f"{med:+.1f}\n({lo:+.1f} to {hi:+.1f})", (dec, hi), xytext=(10, 4),
                textcoords="offset points", fontsize=8, color=INK)
    a1.set_xlim(pd.Timestamp("2024-12-01"), pd.Timestamp("2027-02-15"))
    a1.set_ylim(-1, 4.8)
    a1.set_ylabel("Nino 3.4 anomaly (C), CPC 1991-2020 base", fontsize=9)
    a1.set_title("Observed trajectory and projected peak", fontsize=10, loc="left")
    a1.legend(fontsize=7.5, frameon=False, loc="upper left")
    import matplotlib.dates as mdates
    a1.xaxis.set_major_formatter(mdates.DateFormatter("%b\n%Y"))
    a1.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 4, 7, 10]))

    t = table[table.track == "oisst"].copy()
    t["label"] = t.model + "  [" + t.init.map({"sep": "Sep", "oct2w": "+Oct wks"}) + "]"
    t = t.sort_values(["in_combined", "median"])
    ys = np.arange(len(t))
    for y, (_, r) in zip(ys, t.iterrows()):
        c = INK if r.in_combined else MUTED
        a2.plot([r.cal_q10, r.cal_q90], [y, y], color=c, lw=2, solid_capstyle="round")
        a2.plot([r["median"]], [y], "o", color=c, ms=6, mec="white", mew=1)
    yc = len(t) + 0.8
    a2.plot([lo, hi], [yc, yc], color=BLUE, lw=3, solid_capstyle="round")
    a2.plot([med], [yc], "o", color=BLUE, ms=8, mec="white", mew=1.5)
    a2.axvline(iri, color=ORANGE, lw=1.5)
    a2.text(iri, -1.3, " IRI", color="#52514e", fontsize=8)
    a2.axvline(record, color=MUTED, ls="--", lw=1)
    a2.text(record, -1.3, " 2015-16", color="#52514e", fontsize=8)
    labels = [l + ("" if ic else "  (not combined)" if not l.startswith("XRO nonlinear") else "  (excluded)")
              for l, ic in zip(t.label, t.in_combined)]
    a2.set_yticks(list(ys) + [yc], labels + ["Skill-weighted combination"], fontsize=7.5)
    for lab, ic in zip(a2.get_yticklabels()[:-1], t.in_combined):
        lab.set_color(INK if ic else MUTED)
    a2.get_yticklabels()[-1].set_color(BLUE)
    a2.get_yticklabels()[-1].set_fontweight("bold")
    a2.set_ylim(-1.8, yc + 0.8)
    a2.set_xlabel("Peak 3-month mean Nino 3.4 (C), median and calibrated 80% interval", fontsize=8.5)
    a2.set_title("Peak forecast by model (OISST)", fontsize=10, loc="left")
    fig.suptitle("2026-27 El Nino: projected peak of Nino 3.4 (models fitted on 1982-2025, started from Sep / mid-Oct 2026)",
                 fontsize=10.5, x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def write_forecast_markdown(table, combined, timing, weights, path, record, iri):
    from .targets import season_label
    lo, med, hi = np.percentile(combined, [10, 50, 90])
    lines = ["# 2026-27 peak forecast: tables", "",
             f"Combined (skill-weighted, calibrated): median {med:+.2f} C, 80% interval {lo:+.2f} to {hi:+.2f} C "
             "(OISST Nino 3.4, CPC 1991-2020 base).", "",
             "Weights (1/RMSE^2, El Nino years in the CV hindcast): " +
             ", ".join(f"{k} {v:.2f}" for k, v in weights.items()), "",
             "Season probabilities (combination): " +
             ", ".join(f"{season_label(k)} {p:.0%}" for k, p in
                       enumerate(np.bincount(timing, minlength=7) / len(timing)) if p >= 0.005), "",
             "Exceedance probabilities (combination): " +
             ", ".join(f"P(> {v:+.2f}) = {(combined > v).mean():.0%}" for v in [record, 3.0, iri, 4.0]), ""]
    for track, g in table.groupby("track", sort=False):
        lines += [f"## {'OISST Nino 3.4 (CPC 1991-2020 base)' if track == 'oisst' else 'ONI-like (ERSSTv5 3-month, 1996-2025 base); separate scale, do not compare with OISST'}", "",
                  "| Model | Start | Median | 80% raw | 80% calibrated | Inflation | Modal season | Timing from | In combination |",
                  "|---|---|---|---|---|---|---|---|---|"]
        for _, r in g.iterrows():
            lines.append(f"| {r.model} | {r.init} | {r['median']:+.2f} | {r.q10:+.2f} to {r.q90:+.2f} | "
                         f"{r.cal_q10:+.2f} to {r.cal_q90:+.2f} | x{r.k_inflate:.2f} | {r.modal_season} | "
                         f"{r.timing_from} | {'yes' if r.in_combined else ''} |")
        lines.append("")
    with open(path, "w") as f:
        f.write("\n".join(lines))
