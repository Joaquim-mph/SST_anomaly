"""Parsers for the raw ENSO index files in data/raw/<snapshot>/.

Every parser returns a pandas Series indexed by a monthly PeriodIndex.
Raw files are only read, never written.
"""

import json
import os

import numpy as np
import pandas as pd

SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_ROOT = os.path.join(SCRIPT_DIR, "data", "raw")

SEASONS = ["DJF", "JFM", "FMA", "MAM", "AMJ", "MJJ",
           "JJA", "JAS", "ASO", "SON", "OND", "NDJ"]


def snapshot_dir(snapshot="latest"):
    path = os.path.realpath(os.path.join(RAW_ROOT, snapshot))
    if not os.path.isdir(path):
        raise FileNotFoundError(f"{path} not found. Run fetch_enso_indices.sh first.")
    return path


def read_manifest(snapshot="latest"):
    with open(os.path.join(snapshot_dir(snapshot), "MANIFEST.json")) as f:
        return json.load(f)


def _month_index(years, months):
    return pd.PeriodIndex.from_fields(year=np.asarray(years), month=np.asarray(months), freq="M")


def read_sstoi(path):
    """CPC monthly OISST Nino indices. Returns Nino 3.4 total SST and CPC anomaly."""
    df = pd.read_csv(path, sep=r"\s+", header=None, skiprows=1,
                     names=["yr", "mon", "n12", "n12a", "n3", "n3a", "n4", "n4a", "n34", "n34a"])
    idx = _month_index(df.yr, df.mon)
    return (pd.Series(df.n34.values, idx, name="oisst_n34"),
            pd.Series(df.n34a.values, idx, name="oisst_n34_cpc_anom"))


def read_weekly(path):
    """CPC weekly OISST. Returns a Series of Nino 3.4 SST total indexed by week-centre date.

    Columns are fixed-width with no space between SST and SSTA (e.g. '20.6-0.1').
    """
    dates, sst, ssta = [], [], []
    with open(path) as f:
        lines = f.readlines()[4:]
    for line in lines:
        if not line.strip():
            continue
        dates.append(pd.to_datetime(line[1:10], format="%d%b%Y"))
        # Nino34 block: "     26.5-0.2" occupying columns 37..49
        sst.append(float(line[41:45]))
        ssta.append(float(line[45:49]))
    idx = pd.DatetimeIndex(dates)
    return (pd.Series(sst, idx, name="weekly_n34"),
            pd.Series(ssta, idx, name="weekly_n34_cpc_anom"))


def read_oni(path):
    """ONI: 3-month ERSSTv5 total and anomaly, indexed by the season's centre month."""
    df = pd.read_csv(path, sep=r"\s+")
    month = df.SEAS.map(lambda s: SEASONS.index(s) + 1)
    idx = _month_index(df.YR, month)
    return (pd.Series(df.TOTAL.values, idx, name="oni_total"),
            pd.Series(df.ANOM.values, idx, name="oni_cpc_anom"))


def read_roni(path):
    df = pd.read_csv(path, sep=r"\s+")
    month = df.SEAS.map(lambda s: SEASONS.index(s) + 1)
    return pd.Series(df.ANOM.values, _month_index(df.YR, month), name="roni")


def read_cpc_wind(path):
    """CPC 850 hPa trade-wind index, ORIGINAL DATA block (m/s, easterly positive)."""
    with open(path) as f:
        lines = f.readlines()
    rows = []
    for line in lines[4:]:
        if not line[:4].isdigit():
            break
        year = int(line[:4])
        vals = [float(line[4 + 6 * i: 10 + 6 * i]) for i in range(12)]
        rows += [(year, m + 1, v) for m, v in enumerate(vals)]
    df = pd.DataFrame(rows, columns=["yr", "mon", "v"])
    s = pd.Series(df.v.values, _month_index(df.yr, df.mon))
    return s.where(s > -999).dropna()


def read_wwv(path):
    """PMEL warm water volume (m^3, 5N-5S 120E-80W): total and PMEL anomaly."""
    df = pd.read_csv(path, sep=r"\s+", skiprows=6, header=None, names=["date", "vol", "anom"],
                     dtype={"date": str})
    idx = _month_index(df.date.str[:4].astype(int), df.date.str[4:].astype(int))
    return (pd.Series(df.vol.values, idx, name="wwv"),
            pd.Series(df.anom.values, idx, name="wwv_pmel_anom"))


def load_monthly(snapshot="latest"):
    """All monthly raw totals in one DataFrame (PeriodIndex, monthly).

    Columns:
      T      OISST Nino 3.4 SST total (degC)
      H      warm water volume (1e14 m^3)
      U_W/U_C/U_E  850 hPa trade wind, west/central/east Pacific (m/s, easterly positive)
      T_cpc  CPC published OISST anomaly (1991-2020 base), for reference only
    """
    d = snapshot_dir(snapshot)
    T, T_cpc = read_sstoi(os.path.join(d, "cpc", "sstoi.indices"))
    H, _ = read_wwv(os.path.join(d, "pmel", "wwv.dat"))
    df = pd.DataFrame({
        "T": T,
        "H": H / 1e14,
        "U_W": read_cpc_wind(os.path.join(d, "cpc", "wpac850")),
        "U_C": read_cpc_wind(os.path.join(d, "cpc", "cpac850")),
        "U_E": read_cpc_wind(os.path.join(d, "cpc", "epac850")),
        "T_cpc": T_cpc,
    })
    return df.loc["1979-01":]


def load_oni(snapshot="latest"):
    d = snapshot_dir(snapshot)
    total, anom = read_oni(os.path.join(d, "cpc", "oni.ascii.txt"))
    roni = read_roni(os.path.join(d, "cpc", "RONI.ascii.txt"))
    return pd.DataFrame({"T": total, "T_cpc": anom, "roni": roni})


def load_weekly(snapshot="latest"):
    d = snapshot_dir(snapshot)
    total, anom = read_weekly(os.path.join(d, "cpc", "wksst9120.for"))
    return pd.DataFrame({"T": total, "T_cpc": anom})
