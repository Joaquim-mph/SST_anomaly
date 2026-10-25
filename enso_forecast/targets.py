"""Forecast targets: peak 3-month mean of Nino 3.4 and its season.

The peak window is the seasons ASO(y) .. FMA(y+1), i.e. 3-month means centred on
Sep(y) .. Mar(y+1). Timing is the index of the peak season in that window (0 = ASO).
"""

import numpy as np
import pandas as pd

from .data import SEASONS

PEAK_CENTRES = 7            # Sep .. Mar
LEADS = 4                   # monthly leads scored for correlation
HORIZON = 8                 # months forecast after init (enough for FMA running mean)


def season_label(k):
    """Label of window position k (0 = ASO)."""
    return SEASONS[(8 + k) % 12]


def peak_from_path(path, smooth3):
    """Peak value and timing from a path (array, last axis = months).

    For smooth3=True, `path` holds monthly values Aug(y) .. Apr(y+1) (9 months), and the
    3-month means centred Sep..Mar are taken. For smooth3=False, `path` already holds
    3-month values centred Sep(y) .. Mar(y+1) (7 values).
    """
    path = np.asarray(path, float)
    if smooth3:
        r3 = (path[..., :-2] + path[..., 1:-1] + path[..., 2:]) / 3.0
    else:
        r3 = path
    r3 = r3[..., :PEAK_CENTRES]
    k = np.argmax(r3, axis=-1)
    return np.take_along_axis(r3, k[..., None], -1)[..., 0], k


def observed_target(fold):
    """Observed peak, timing and lead-1..4 values for the fold's year."""
    a = fold.anom["T"]
    y = fold.year
    if fold.smooth3:
        path = a.loc[pd.Period(f"{y}-08", "M"): pd.Period(f"{y + 1}-04", "M")].values
        leads = a.loc[fold.init + 1:].values[:LEADS]
        if len(path) < 9:
            return None
    else:
        path = a.loc[pd.Period(f"{y}-09", "M"): pd.Period(f"{y + 1}-03", "M")].values
        leads = a.loc[fold.init + 1:].values[:LEADS]
        if len(path) < 7:
            return None
    if np.isnan(path).any():
        return None
    peak, k = peak_from_path(path, fold.smooth3)
    return {"peak": float(peak), "timing": int(k), "leads": np.asarray(leads, float)}


def known_path(fold):
    """Values of the peak-path months already observed at init (OISST: from Aug; ONI: from Sep)."""
    start = pd.Period(f"{fold.year}-{'08' if fold.smooth3 else '09'}", "M")
    return fold.visible()["T"].loc[start:].values


def path_with_known(fold, fcst):
    """Prepend months already known at init to forecast trajectories.

    fcst: array (..., HORIZON) of forecasts for the months after init.
    Returns arrays aligned with what peak_from_path expects.
    """
    fcst = np.asarray(fcst, float)
    known = known_path(fold)
    n = (9 if fold.smooth3 else PEAK_CENTRES) - len(known)
    known = np.broadcast_to(known, fcst.shape[:-1] + (len(known),))
    return np.concatenate([known, fcst[..., :n]], axis=-1)
