import numpy as np
import pandas as pd
import pytest

from enso_forecast import data, folds, models, targets

P = lambda s: pd.Period(s, "M")


@pytest.fixture(scope="module")
def monthly():
    return data.load_monthly()


@pytest.fixture(scope="module")
def oni():
    return data.load_oni()


def test_parsers_known_values(monthly, oni):
    assert monthly.loc[P("2026-09"), "T_cpc"] == pytest.approx(2.84)
    assert monthly.loc[P("2026-09"), "T"] == pytest.approx(29.60)
    assert monthly.loc[P("2026-09"), "U_C"] == pytest.approx(0.1)
    assert monthly.loc[P("1980-01"), "H"] == pytest.approx(26.09619)
    assert oni.loc[P("2026-08"), "T_cpc"] == pytest.approx(2.16)       # JAS 2026
    assert oni.loc[P("2026-08"), "roni"] == pytest.approx(1.69)
    w = data.load_weekly()
    assert w.loc["2026-10-14", "T_cpc"] == pytest.approx(3.3)
    assert w.loc["1981-09-02", "T"] == pytest.approx(26.5)


def test_monthly_has_no_gaps(monthly):
    t = monthly["T"].dropna()
    assert len(t) == (t.index[-1] - t.index[0]).n + 1


def test_cv_climatology_close_to_cpc(monthly):
    # anomalies from all-years climatology should track CPC's 1991-2020 anomalies closely
    df = monthly.loc[:"2025-12"]
    a = folds.anomalies(df["T"], df["T"].notna())
    d = (a - df["T_cpc"]).dropna()
    assert np.corrcoef(a.dropna(), df["T_cpc"].dropna())[0, 1] > 0.99
    assert d.abs().mean() < 0.15


@pytest.mark.parametrize("year", [1982, 1997, 2015, 2025])
def test_cv_fold_has_no_leak(monthly, year):
    f = folds.oisst_fold(monthly.loc[:"2026-04"], year, "cv")
    tm = f.train_mask[f.train_mask].index
    lo, hi = f.holdout
    assert not ((tm >= lo) & (tm <= hi)).any()
    assert tm.max() <= P("2025-12")
    assert f.visible().index[-1] == P(f"{year}-09")


def test_expanding_fold_uses_only_past(monthly):
    f = folds.oisst_fold(monthly.loc[:"2026-04"], 2005, "expanding")
    assert f.train_mask[f.train_mask].index.max() == P("2005-09")
    # climatology must not change if the future is altered
    df2 = monthly.loc[:"2026-04"].copy()
    df2.loc[P("2006-01"):, "T"] += 5
    f2 = folds.oisst_fold(df2, 2005, "expanding")
    pd.testing.assert_series_equal(f.anom["T"].loc[:"2005-09"], f2.anom["T"].loc[:"2005-09"])


def test_oni_fold_trailing(monthly, oni):
    f = folds.oni_fold(oni.loc[:"2026-04"], monthly.loc[:"2026-04"], 1997)
    assert f.train_mask[f.train_mask].index.max() <= P("1997-08")
    # changing data after the init must not change anything the model sees
    oni2 = oni.loc[:"2026-04"].copy()
    oni2.loc[P("1997-09"):, "T"] += 5
    f2 = folds.oni_fold(oni2, monthly.loc[:"2026-04"], 1997)
    pd.testing.assert_frame_equal(f.training(), f2.training())
    pd.testing.assert_frame_equal(f.visible(), f2.visible())


def test_models_cannot_see_future(monthly):
    """Perturbing everything after the init month must not change any forecast."""
    base = monthly.loc[:"2026-04"]
    pert = base.copy()
    pert.loc[P("2009-10"):, ["T", "H", "U_C"]] += 3
    for m in models.all_models():
        outs = []
        for df in (base, pert):
            f = folds.oisst_fold(df, 2009, "expanding")
            out = m.fit(f).predict(f, np.random.default_rng(1))
            outs.append(out["peak"])
        np.testing.assert_allclose(outs[0], outs[1], err_msg=m.name)


def test_peak_from_path():
    path = np.array([0, 1, 2, 3, 2, 1, 0, 0, 0], float)   # Aug..Apr
    peak, k = targets.peak_from_path(path, True)
    assert peak == pytest.approx(7 / 3) and k == 2           # centred on Nov
    assert targets.season_label(k) == "OND"


def test_october_partial_init_hides_full_month(monthly):
    df = monthly.loc[:"2026-04"]
    partial = pd.Series({y: 27.0 for y in range(1982, 2026)} | {1997: 28.7})
    f = folds.oisst_fold(df, 1997, "cv", oct_partial=partial)
    assert f.visible().loc[P("1997-10"), "T"] == pytest.approx(1.7)
    v = f.visible()
    assert v.index[-1] == P("1997-10")
    assert v.loc[P("1997-10"), ["H", "U_C"]].isna().all()
    # the init value is the partial mean, not the observed monthly October anomaly
    assert v.loc[P("1997-10"), "T"] != pytest.approx(f.anom.loc[P("1997-10"), "T"])
