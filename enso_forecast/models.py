"""Forecast models for the Nino 3.4 peak, simplest first.

Every model has
  fit(fold)                   uses only fold.training() (NaN outside the training mask)
  predict(fold, rng) -> dict  uses only fold.visible() (nothing after init)
returning
  peak     samples of the peak 3-month mean (N,)
  timing   samples of the peak window position (N,), 0 = ASO
  leads    point forecast for leads 1..4 (or None)

Path models simulate monthly trajectories, so their spread comes from the model noise.
Direct models produce one point forecast; their spread comes from the leave-one-year-out
residuals over the training years ("nested" residuals: no year predicts itself).
"""

import warnings

import numpy as np
import pandas as pd

from .targets import HORIZON, LEADS, PEAK_CENTRES, known_path, path_with_known, peak_from_path

N_ENS = 1000
EL_NINO = 0.5


# ---------------------------------------------------------------- training table

def training_years(fold):
    """One row per training year: state at init and observed target, from training data only."""
    a = fold.training()
    init_m = fold.init.month
    rows = []
    for y in sorted(set(a.index.year)):
        init = pd.Period(year=y, month=init_m, freq="M")
        if fold.smooth3:
            win = a.loc[pd.Period(f"{y}-01", "M"): pd.Period(f"{y + 1}-04", "M")]
            nwin, k0 = 16, 7               # Jan(y)..Apr(y+1); Aug is position 7
        else:
            win = a.loc[pd.Period(f"{y}-01", "M"): pd.Period(f"{y + 1}-03", "M")]
            nwin, k0 = 15, 8               # centres Jan(y)..Mar(y+1); Sep is position 8
        if len(win) < nwin or win["T"].isna().any():
            continue
        T = win["T"].values
        peak, k = peak_from_path(T[k0:], fold.smooth3)
        t_init = win["T"].loc[init]
        rows.append({
            "year": y, "T0": t_init,
            "H0": win["H"].loc[init] if "H" in win else np.nan,
            "U0": win["U_C"].loc[init] if "U_C" in win else np.nan,
            "peak": float(peak), "timing": int(k),
            "path": T,                              # Jan(y) .. end of window
            "leads": T[init_m: init_m + LEADS],     # months after init
            "known": T[k0:init_m],                  # peak-path months observed at init
        })
    return pd.DataFrame(rows)


def climatological_timing(table):
    """Most common peak season among training El Nino years (for direct models)."""
    t = table.loc[table.peak >= EL_NINO, "timing"]
    return int(t.mode().iloc[0]) if len(t) else 3


def _state(fold):
    v = fold.visible()
    return {"T0": v["T"].iloc[-1],
            "H0": v["H"].iloc[-1] if "H" in v else np.nan,
            "U0": v["U_C"].iloc[-1] if "U_C" in v else np.nan,
            "Tyear": v["T"].loc[pd.Period(f"{fold.year}-01", "M"):].values,
            "known": known_path(fold)}


# ---------------------------------------------------------------- direct models

class DirectModel:
    """Point forecast + nested leave-one-year-out residual quantiles for spread."""
    kind = "direct"
    min_years = 8

    def point(self, table, state):
        raise NotImplementedError

    def fit(self, fold):
        self.table = training_years(fold)
        self.table = self.table.dropna(subset=self.required())
        if len(self.table) < self.min_years:
            raise ValueError("not enough training years")
        self.timing = climatological_timing(self.table)
        res = []
        for i in range(len(self.table)):
            y = self.table.year.iloc[i]
            inner = self.table[(self.table.year - y).abs() > 1]   # also drop neighbours
            row = self.table.iloc[i]
            p, _ = self.point(inner, row)
            res.append(row.peak - p)
        self.residuals = np.asarray(res)
        return self

    def required(self):
        return ["T0"]

    def predict(self, fold, rng):
        state = _state(fold)
        p, leads = self.point(self.table, state)
        peak = p + rng.choice(self.residuals, N_ENS)
        return {"peak": peak, "timing": np.full(N_ENS, self.timing), "leads": leads}


class Persistence(DirectModel):
    name = "Persistence"

    def point(self, table, s):
        return s["T0"], np.full(LEADS, s["T0"])

    def fit(self, fold):
        super().fit(fold)
        # pure persistence has no bias correction: use symmetric |residual| spread
        r = np.abs(self.residuals)
        self.residuals = np.concatenate([r, -r])
        return self


class DampedPersistence(DirectModel):
    """x(init+L) = c_L * x(init), c_L by least squares through the origin, per lead."""
    name = "Damped persistence"

    def fit(self, fold):
        self.smooth3 = fold.smooth3
        self.init_pos = fold.init.month - 1          # position of init month in table paths
        return super().fit(fold)

    def point(self, table, s):
        x0 = table.T0.values
        known = np.asarray(s["known"], float)
        n_f = (9 if self.smooth3 else PEAK_CENTRES) - len(known)
        fut = np.stack(table.path.values)[:, self.init_pos + 1:self.init_pos + 1 + n_f]
        c = (x0[:, None] * fut).sum(0) / (x0 ** 2).sum()
        f = c * s["T0"]
        full = np.concatenate([known, f])
        peak, _ = peak_from_path(full, self.smooth3)
        return float(peak), f[:LEADS]


class AnalogComposite(DirectModel):
    """Current value + mean rise from init to peak in past El Nino years with similar start."""
    name = "Analog composite"

    def point(self, table, s):
        an = table[table.T0 > EL_NINO]
        if len(an) < 3:
            an = table[table.T0 > 0]
        rise = (an.peak - an.T0).mean()
        lead_rise = (np.stack(an.leads.values) - an.T0.values[:, None]).mean(0)
        return s["T0"] + rise, s["T0"] + lead_rise


class Regression(DirectModel):
    """peak ~ b0 + b1*T0 (+ b2*H0) (+ b3*U0); same predictors for each lead."""

    def __init__(self, predictors):
        self.predictors = predictors
        self.name = "Regression (" + ", ".join(p[0] for p in predictors) + ")"

    def required(self):
        return self.predictors

    def _design(self, d):
        return np.column_stack([np.ones(len(d))] + [np.asarray(d[p], float) for p in self.predictors])

    def point(self, table, s):
        X = self._design(table)
        x = self._design(pd.DataFrame({p: [s[p]] for p in self.predictors}))
        beta = np.linalg.lstsq(X, table.peak.values, rcond=None)[0]
        L = np.stack(table.leads.values)
        bl = np.linalg.lstsq(X, L, rcond=None)[0]
        return float((x @ beta)[0]), (x @ bl)[0]


class BellCurve(DirectModel):
    """Gaussian-in-time event shape (centre, width from training El Nino composite);
    only the amplitude is fitted to the target year's months up to init. A baseline."""
    name = "Bell curve"

    def fit(self, fold):
        self.smooth3 = fold.smooth3
        self.n_known = fold.init.month                  # Jan .. init observed
        table = training_years(fold).dropna(subset=["T0"])
        self.mu, self.sigma = self._shape(table)
        return super().fit(fold)

    @staticmethod
    def _shape(table):
        from scipy.optimize import curve_fit
        ev = table[table.peak >= 1.0]
        if len(ev) < 2:
            ev = table.nlargest(3, "peak")
        n = min(len(p) for p in ev.path)
        comp = np.mean([p[:n] / pk for p, pk in zip(ev.path, ev.peak)], axis=0)
        t = np.arange(n)
        f = lambda t, mu, sig: np.exp(-0.5 * ((t - mu) / sig) ** 2)
        (mu, sig), _ = curve_fit(f, t, comp, p0=[11, 4], bounds=([6, 1.5], [16, 12]))
        return mu, sig

    def point(self, table, s):
        if table is not self.table:          # inner fold: refit shape without this year
            mu, sig = self._shape(table)
        else:
            mu, sig = self.mu, self.sigma
        n_known = self.n_known
        y = np.asarray(s["Tyear"] if "Tyear" in s else s["path"], float)[:n_known]
        t = np.arange(16)
        g = np.exp(-0.5 * ((t - mu) / sig) ** 2)
        A = (g[:n_known] @ y) / (g[:n_known] @ g[:n_known])
        curve = A * g
        if self.smooth3:
            peak, _ = peak_from_path(curve[7:16], True)
        else:
            peak, _ = peak_from_path(curve[8:15], False)
        leads = curve[n_known:n_known + LEADS]
        return float(peak), leads

    def predict(self, fold, rng):
        out = super().predict(fold, rng)
        # timing from the fitted shape
        start = 8                                   # window position 0 = ASO centre (Sep)
        out["timing"] = np.full(N_ENS, int(np.clip(round(self.mu) - start, 0, PEAK_CENTRES - 1)))
        return out


# ---------------------------------------------------------------- path models

class SeasonalAR:
    """x_m = sum_k a_{m,k} x_{m-k} + e_m, coefficients per calendar month, no intercept."""
    kind = "path"

    def __init__(self, p=1):
        self.p = p
        self.name = f"Seasonal AR({p})"

    def fit(self, fold):
        T = fold.training()["T"]
        v = T.values
        months = T.index.month.values
        self.coef, self.res = {}, {}
        for m in range(1, 13):
            rows = [i for i in range(self.p, len(v))
                    if months[i] == m and np.isfinite(v[i - self.p: i + 1]).all()]
            X = np.array([[v[i - k] for k in range(1, self.p + 1)] for i in rows])
            y = np.array([v[i] for i in rows])
            if len(rows) < 8:
                raise ValueError("not enough data")
            b = np.linalg.lstsq(X, y, rcond=None)[0]
            self.coef[m], self.res[m] = b, y - X @ b
        return self

    def simulate(self, fold, rng, n=N_ENS, noise=True):
        hist = fold.visible()["T"].values[-self.p:]
        m = fold.init.month
        x = np.tile(hist, (n, 1))
        out = []
        for _ in range(HORIZON):
            m = m % 12 + 1
            nxt = x[:, ::-1][:, :self.p] @ self.coef[m]
            if noise:
                nxt = nxt + rng.choice(self.res[m], n)
            x = np.column_stack([x[:, 1:], nxt]) if self.p > 1 else nxt[:, None]
            out.append(nxt)
        return np.array(out).T

    def predict(self, fold, rng):
        paths = self.simulate(fold, rng)
        peak, k = peak_from_path(path_with_known(fold, paths), fold.smooth3)
        mean_path = self.simulate(fold, rng, n=1, noise=False)[0]
        return {"peak": peak, "timing": k, "leads": mean_path[:LEADS]}


def _harmonics(month):
    w = 2 * np.pi * (np.asarray(month) - 0.5) / 12
    return np.column_stack([np.ones_like(w), np.cos(w), np.sin(w), np.cos(2 * w), np.sin(2 * w)])


class RechargeOscillator:
    """Two-variable recharge oscillator, discrete monthly form:
         z(t+1) - z(t) = L(month) z(t) + noise,   z = [T, H]
    with L built from annual + semi-annual harmonics (10 coefficients per equation),
    fitted by least squares on monthly tendencies. Noise: joint [T, H] residuals
    resampled from the same calendar month."""
    kind = "path"
    name = "Recharge oscillator"

    def fit(self, fold):
        a = fold.training()[["T", "H"]]
        z = a.values
        dz = z[1:] - z[:-1]
        ok = np.isfinite(z[:-1]).all(1) & np.isfinite(dz).all(1)
        mon = a.index.month.values[:-1][ok]
        Hm = _harmonics(mon)
        X = np.column_stack([Hm * z[:-1][ok, 0:1], Hm * z[:-1][ok, 1:2]])
        if ok.sum() < 120:
            raise ValueError("not enough data")
        self.beta = np.linalg.lstsq(X, dz[ok], rcond=None)[0]   # (10, 2)
        res = dz[ok] - X @ self.beta
        self.res = {m: res[mon == m] for m in range(1, 13)}
        self.scale = np.nanstd(a.values, 0)
        return self

    def operator(self, month):
        h = _harmonics([month])[0]
        L = np.empty((2, 2))
        for j in range(2):            # output equation
            L[j, 0] = h @ self.beta[0:5, j]
            L[j, 1] = h @ self.beta[5:10, j]
        return L

    def simulate(self, fold, rng, n=N_ENS, noise=True):
        v = fold.visible()[["T", "H"]].iloc[-1].values
        if not np.isfinite(v).all():
            raise ValueError("missing initial state")
        z = np.tile(v, (n, 1))
        m = fold.init.month
        out = []
        for _ in range(HORIZON):
            L = self.operator(m)
            dz = z @ L.T
            if noise:
                r = self.res[m]
                dz = dz + r[rng.integers(0, len(r), n)]
            z = z + dz
            m = m % 12 + 1
            out.append(z[:, 0])
        return np.array(out).T

    def predict(self, fold, rng):
        paths = self.simulate(fold, rng)
        peak, k = peak_from_path(path_with_known(fold, paths), fold.smooth3)
        mean_path = self.simulate(fold, rng, n=1, noise=False)[0]
        return {"peak": peak, "timing": k, "leads": mean_path[:LEADS]}


class XROModel:
    """XRO package (Zhao et al. 2024) with T and H only, refitted in every fold.
    nonlinear=True adds the T^2 term to the T equation (fit_matrix, maskNT=['T2'])."""
    kind = "path"

    def __init__(self, nonlinear=False):
        self.nonlinear = nonlinear
        self.name = "XRO nonlinear (T, H, T^2)" if nonlinear else "XRO (T, H)"

    def fit(self, fold):
        from XRO import XRO, gradient
        a = fold.training()[["T", "H"]]
        if a.index[0].month != 1:
            raise ValueError("series must start in January")
        X = a.values.T.copy()
        X[:, ~np.isfinite(X).all(0)] = np.nan   # XRO only checks one row for NaN
        if np.isfinite(X).all(0).sum() < 120:
            raise ValueError("not enough data")
        self.model = XRO(ncycle=12, ac_order=2, is_forward=True)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            if self.nonlinear:
                # trailing NaN month so the last valid month gets no backward-difference tendency
                Xp = np.concatenate([X, np.full((2, 12), np.nan)], axis=1)
                self.fit_ds = self.model.fit_matrix(Xp, maskNT=["T2"])
            else:
                Y = gradient(X, axis=1, is_forward=True, ncycle=12)
                Y[:, -1] = np.nan                   # XRO pads the last step with a backward diff
                bad = ~(np.isfinite(X).all(0) & np.isfinite(Y).all(0))
                X[:, bad] = np.nan
                Y[:, bad] = np.nan
                self.fit_ds = self.model.fit(X, Y, is_remove_nan=True)
        return self

    def _run(self, fold, ncopy, noise_type, seed):
        import xarray as xr
        v = fold.visible()[["T", "H"]].iloc[-1]
        t = np.array([fold.init.to_timestamp()], dtype="datetime64[ns]")
        init = xr.Dataset({k: ("time", [float(v[k])]) for k in ["T", "H"]}, coords={"time": t})
        init = init.rename({"T": "X1", "H": "X2"})
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            f = self.model.reforecast(self.fit_ds, init, n_month=HORIZON, ncopy=ncopy,
                                      noise_type=noise_type, seed=seed)
        T = f["X1"]
        if "init" in T.dims:
            T = T.isel(init=0)
        if "member" in T.dims:
            return T.transpose("member", "lead").values[:, 1:HORIZON + 1]
        return T.values[1:HORIZON + 1]

    def predict(self, fold, rng):
        paths = self._run(fold, N_ENS, "red", int(rng.integers(0, 2**31)))
        if not np.isfinite(paths).all():
            raise ValueError("non-finite forecast")
        peak, k = peak_from_path(path_with_known(fold, paths), fold.smooth3)
        mean_path = self._run(fold, 1, "zero", 0)
        return {"peak": peak, "timing": k, "leads": mean_path[:LEADS]}


def all_models(with_predictors=True):
    models = [Persistence(), DampedPersistence(), AnalogComposite(), BellCurve(),
              SeasonalAR(1), SeasonalAR(2)]
    if with_predictors:
        models += [RechargeOscillator(), XROModel(), XROModel(nonlinear=True),
                   Regression(["T0", "H0"]), Regression(["T0", "H0", "U0"])]
    return models
