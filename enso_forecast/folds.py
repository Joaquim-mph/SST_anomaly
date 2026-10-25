"""Leak-free anomalies and hindcast folds.

A Fold holds everything one hindcast (or the live forecast) may see:
  anom        monthly anomalies computed with a climatology that uses only allowed months
  train_mask  months a model may be fitted on
  init        last month whose value is known at the start date (early October)

Fold modes
  cv         OISST leave-one-season-out: Jul(y-1)..Jun(y+2) is removed from the fit
             and from the climatology. Because this window spans the whole event, it is
             leave-one-event-out for strong events.
  expanding  OISST strict real time: only months <= Sep(y) for fit and climatology.
  trailing   ONI-like track: anomalies from a trailing 30-year climatology,
             fit on months <= init only.
"""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

# Hindcast stage: nothing after this month is ever used for fitting or climatology.
LAST_TRAIN_MONTH = pd.Period("2025-12", "M")
VARS = ["T", "H", "U_W", "U_C", "U_E"]


@dataclass
class Fold:
    year: int
    mode: str
    init: pd.Period
    anom: pd.DataFrame
    train_mask: pd.Series
    smooth3: bool              # True: target is the 3-month running mean of a monthly series
    holdout: tuple = field(default=None)
    init_override: dict = field(default=None)   # partial-month values replacing anom at init

    def visible(self):
        """Anomalies a forecast may use as initial state (nothing after init)."""
        v = self.anom.loc[:self.init]
        if self.init_override:
            v = v.copy()
            for k, val in self.init_override.items():
                v.loc[self.init, k] = val
        return v

    def training(self):
        """Anomalies a model may be fitted on (NaN outside the training mask)."""
        return self.anom.where(self.train_mask, np.nan)

    def check_no_leak(self):
        tm = self.train_mask[self.train_mask].index
        assert tm.max() <= LAST_TRAIN_MONTH, "2026 data in training"
        if self.mode in ("expanding", "trailing"):
            assert tm.max() <= self.init, f"{self.year}: training month after init"
        if self.holdout is not None:
            lo, hi = self.holdout
            assert not ((tm >= lo) & (tm <= hi)).any(), f"{self.year}: training month in holdout"


def monthly_climatology(total, mask):
    """Per-calendar-month mean of `total` over months where mask is True."""
    sel = total[mask & total.notna()]
    clim = sel.groupby(sel.index.month).mean()
    if len(clim) < 12:
        raise ValueError("climatology missing calendar months")
    return clim


def anomalies(total, mask):
    clim = monthly_climatology(total, mask)
    return total - clim.reindex(total.index.month).values


def _frame_anomalies(df, mask):
    return pd.DataFrame({v: anomalies(df[v], mask) for v in VARS if v in df})


def oisst_fold(df, year, mode, oct_partial=None):
    """oct_partial: Series by year of OISST Nino 3.4 totals averaged over the first two
    October weeks (weekly file). If given, the init moves to October, T(Oct) = this year's
    partial value minus the mean partial value of the climatology years; H, U unknown."""
    init = pd.Period(f"{year}-09", "M")
    idx = df.index
    if mode == "cv":
        lo, hi = pd.Period(f"{year - 1}-07", "M"), pd.Period(f"{year + 2}-06", "M")
        mask = pd.Series(((idx < lo) | (idx > hi)) & (idx <= LAST_TRAIN_MONTH), idx)
        holdout = (lo, hi)
    elif mode == "expanding":
        mask = pd.Series(idx <= init, idx)
        holdout = None
    elif mode == "live":
        # live forecast: fit and climatology on 1982-2025, exactly as in the hindcasts;
        # 2026 enters only as the initial state
        mask = pd.Series(idx <= LAST_TRAIN_MONTH, idx)
        holdout = None
    else:
        raise ValueError(mode)
    mask &= df["T"].notna()
    fold = Fold(year, mode, init, _frame_anomalies(df, mask), mask, smooth3=True, holdout=holdout)
    if oct_partial is not None:
        oct_ok = mask[mask.index.month == 10]
        clim_years = oct_ok.index[oct_ok.values].year
        clim_oct = oct_partial[oct_partial.index.isin(clim_years)].mean()
        fold.init = init + 1
        fold.init_override = {v: np.nan for v in VARS if v != "T"}
        fold.init_override["T"] = oct_partial.loc[year] - clim_oct
    fold.check_no_leak()
    return fold


def _three_month(s):
    return s.rolling(3, center=True).mean()


def oni_fold(oni, monthly, year, mode="trailing"):
    """ONI-like track. T is the ERSSTv5 3-month total; anomaly base = 30 years before `year`.

    Each earlier year y' (used for training) gets its own trailing base y'-30..y'-1,
    or 1950-1979 for y' < 1980; none of these bases reaches past the init.
    H and U are 3-month means of monthly anomalies from an expanding climatology (<= Sep y).
    """
    init = pd.Period(f"{year}-08", "M")   # JAS season, published early October
    T = oni["T"]
    years = T.index.year
    anomT = pd.Series(np.nan, T.index)
    base_years = sorted(set(years[years <= year + 1]))
    for yy in base_years:
        ref = min(yy, year)          # target-year months (y and y+1) use the y-30..y-1 base
        b0, b1 = (ref - 30, ref - 1) if ref >= 1980 else (1950, 1979)
        mask = pd.Series((years >= b0) & (years <= b1), T.index)
        clim = monthly_climatology(T, mask)
        sel = years == yy
        anomT[sel] = T[sel] - clim.reindex(T.index[sel].month).values

    mon_mask = pd.Series((monthly.index <= pd.Period(f"{year}-09", "M"))
                         & (monthly.index <= LAST_TRAIN_MONTH), monthly.index)
    other = {v: _three_month(anomalies(monthly[v], mon_mask & monthly[v].notna()))
             for v in VARS if v != "T"}
    anom = pd.DataFrame({"T": anomT, **other})
    mask = pd.Series((anom.index <= init) & (anom.index <= LAST_TRAIN_MONTH)
                     & anom["T"].notna(), anom.index)
    fold = Fold(year, mode, init, anom, mask, smooth3=False)
    fold.check_no_leak()
    return fold
