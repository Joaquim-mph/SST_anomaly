#!/usr/bin/env python3
"""Analyze NOAA CRW daily SSTA NetCDF data to quantify SST anomaly conditions.

Reads downloaded NetCDF files and computes:
- Daily global max/mean/min SSTA
- ENSO regional averages (Nino 3.4, Nino 3, etc.)
- Top extreme anomaly days with locations
- El Nino / La Nina strength assessment

Dependencies: pip install xarray netCDF4 numpy pandas matplotlib
"""

import argparse
import glob
import os
import sys
from datetime import datetime

import numpy as np

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "ssta_data")

REGIONS = {
    "Nino 3.4": (-5, 5, -170, -120),
    "Nino 3": (-5, 5, -150, -90),
    "Nino 1+2": (-10, 0, -90, -80),
    "North Atlantic": (0, 60, -80, 0),
}


def find_files():
    files = sorted(
        glob.glob(os.path.join(DATA_DIR, "2025", "ct5km_ssta_v3.1_*.nc"))
        + glob.glob(os.path.join(DATA_DIR, "2026", "ct5km_ssta_v3.1_*.nc"))
    )
    if not files:
        print("No NetCDF files found in ssta_data/. Run download_ssta_nc.sh first.")
        sys.exit(1)
    return files


def date_from_filename(path):
    datestr = os.path.basename(path).split("_")[-1].replace(".nc", "")
    return datetime.strptime(datestr, "%Y%m%d")


def find_ssta_variable(ds):
    for name in ds.data_vars:
        lower = name.lower()
        if "anomal" in lower and "sst" in lower:
            return name
        if lower == "ssta":
            return name
    for name in ds.data_vars:
        if name not in ("lat", "lon", "time", "crs", "mask"):
            return name
    print(f"Could not identify SSTA variable. Available: {list(ds.data_vars)}")
    sys.exit(1)


def build_region_indices(lat, lon):
    """Pre-compute boolean masks and area weights for each region."""
    masks = {}
    weights = {}
    for name, (lat_min, lat_max, lon_min, lon_max) in REGIONS.items():
        lat_mask = (lat >= lat_min) & (lat <= lat_max)
        if lon_min <= lon_max:
            lon_mask = (lon >= lon_min) & (lon <= lon_max)
        else:
            lon_mask = (lon >= lon_min) | (lon <= lon_max)
        masks[name] = (lat_mask, lon_mask)
        w = np.cos(np.deg2rad(lat[lat_mask]))
        weights[name] = w
    return masks, weights


def regional_mean(data, lat_mask, lon_mask, w):
    """Area-weighted mean over a region, ignoring NaN."""
    region = data[np.ix_(lat_mask, lon_mask)]
    w_2d = w[:, np.newaxis] * np.ones(region.shape[1])
    valid = np.isfinite(region)
    if not valid.any():
        return np.nan
    w_masked = np.where(valid, w_2d, 0)
    total_w = w_masked.sum()
    if total_w == 0:
        return np.nan
    return float(np.nansum(region * w_masked) / total_w)


def analyze(files):
    """Process all NetCDF files and return a DataFrame of daily stats."""
    import pandas as pd
    import xarray as xr

    with xr.open_dataset(files[0]) as ds0:
        var_name = find_ssta_variable(ds0)
        lat = ds0.lat.values
        lon = ds0.lon.values
        print(f"Variable: {var_name}")
        print(f"Grid: {len(lat)} lat x {len(lon)} lon")

    masks, weights = build_region_indices(lat, lon)

    records = []
    for i, filepath in enumerate(files):
        date = date_from_filename(filepath)
        with xr.open_dataset(filepath) as ds:
            data = ds[var_name].values.squeeze()

        if not np.isfinite(data).any():
            continue

        global_max = float(np.nanmax(data))
        global_mean = float(np.nanmean(data))
        global_min = float(np.nanmin(data))

        flat_idx = np.nanargmax(data)
        max_lat_idx, max_lon_idx = np.unravel_index(flat_idx, data.shape)

        record = {
            "date": date,
            "global_max": global_max,
            "global_mean": global_mean,
            "global_min": global_min,
            "max_lat": float(lat[max_lat_idx]),
            "max_lon": float(lon[max_lon_idx]),
        }

        for name in REGIONS:
            lat_mask, lon_mask = masks[name]
            record[name] = regional_mean(data, lat_mask, lon_mask, weights[name])

        records.append(record)

        if (i + 1) % 50 == 0 or i == len(files) - 1:
            print(f"  Processed {i + 1}/{len(files)} files")

    df = pd.DataFrame(records)
    df.set_index("date", inplace=True)
    df.sort_index(inplace=True)
    return df


def print_report(df, top_n=10):
    """Print the analysis report."""
    print()
    print("=" * 65)
    print("  NOAA CORAL REEF WATCH - SSTA ANALYSIS REPORT")
    print("=" * 65)

    print(f"\n  Period:  {df.index[0].date()} to {df.index[-1].date()}")
    print(f"  Days:    {len(df)}")

    print("\n-- Global Extremes " + "-" * 46)
    max_row = df.loc[df["global_max"].idxmax()]
    print(
        f"  Highest SSTA:  {max_row['global_max']:+.2f} C"
        f"  on {df['global_max'].idxmax().date()}"
        f"  at ({max_row['max_lat']:.1f}, {max_row['max_lon']:.1f})"
    )
    print(
        f"  Lowest SSTA:   {df['global_min'].min():+.2f} C"
        f"  on {df['global_min'].idxmin().date()}"
    )
    print(f"  Mean SSTA:     {df['global_mean'].mean():+.2f} C")

    print(f"\n-- Top {top_n} Extreme Days (Global Max) " + "-" * 30)
    top = df.nlargest(top_n, "global_max")
    for date, row in top.iterrows():
        print(
            f"  {date.date()}  {row['global_max']:+.2f} C"
            f"  at ({row['max_lat']:.1f}, {row['max_lon']:.1f})"
        )

    region_cols = [c for c in REGIONS if c in df.columns]
    print("\n-- ENSO Regional Averages " + "-" * 40)
    print(f"  {'Region':20s}  {'Mean':>8s}  {'Peak':>8s}  {'Peak Date':>12s}")
    print(f"  {'-' * 20}  {'-' * 8}  {'-' * 8}  {'-' * 12}")
    for col in region_cols:
        mean_val = df[col].mean()
        max_val = df[col].max()
        max_date = df[col].idxmax().date()
        print(f"  {col:20s}  {mean_val:+.2f} C  {max_val:+.2f} C  {max_date}")

    nino34 = df["Nino 3.4"]
    monthly = nino34.resample("ME").mean()
    latest = monthly.iloc[-1]

    print("\n-- El Nino / La Nina Assessment " + "-" * 34)
    print(f"  Latest monthly Nino 3.4 mean: {latest:+.2f} C")

    if latest >= 0.5:
        if latest >= 2.5:
            strength = "SUPER"
        elif latest >= 2.0:
            strength = "VERY STRONG"
        elif latest >= 1.5:
            strength = "STRONG"
        elif latest >= 1.0:
            strength = "MODERATE"
        else:
            strength = "WEAK"
        print(f"  Assessment: {strength} EL NINO")
    elif latest <= -0.5:
        if latest <= -1.5:
            strength = "STRONG"
        elif latest <= -1.0:
            strength = "MODERATE"
        else:
            strength = "WEAK"
        print(f"  Assessment: {strength} LA NINA")
    else:
        print("  Assessment: ENSO-NEUTRAL")

    print("\n-- Monthly Nino 3.4 Index " + "-" * 40)
    for date, val in monthly.items():
        bar_len = int(abs(val) * 15)
        if val >= 0.5:
            bar = "#" * bar_len
        elif val <= -0.5:
            bar = "~" * bar_len
        else:
            bar = "." * bar_len
        print(f"  {date.strftime('%Y-%m')}  {val:+.2f} C  {bar}")

    print()
    print("=" * 65)


def export_csv(df):
    """Export daily and monthly summaries to CSV."""
    import pandas as pd

    daily_path = os.path.join(SCRIPT_DIR, "ssta_daily_analysis.csv")
    df.to_csv(daily_path)
    print(f"\nExported: {daily_path}")

    region_cols = [c for c in REGIONS if c in df.columns]
    stat_cols = ["global_max", "global_mean", "global_min"] + region_cols
    agg = {"global_max": "max", "global_mean": "mean", "global_min": "min"}
    agg.update({c: "mean" for c in region_cols})
    monthly = df[stat_cols].resample("ME").agg(agg)
    monthly_path = os.path.join(SCRIPT_DIR, "ssta_monthly_summary.csv")
    monthly.to_csv(monthly_path)
    print(f"Exported: {monthly_path}")


def plot_timeseries(df):
    """Generate time series plots."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8), sharex=True)

    ax1.fill_between(
        df.index, df["global_min"], df["global_max"],
        alpha=0.15, color="red", label="Daily min-max range",
    )
    ax1.plot(df.index, df["global_mean"], color="darkred", linewidth=0.7, label="Global mean")
    ax1.axhline(0, color="gray", linewidth=0.5, linestyle="--")
    ax1.set_ylabel("SSTA (C)")
    ax1.set_title("Global Sea Surface Temperature Anomaly - 2025-2026")
    ax1.legend(loc="upper left")
    ax1.grid(True, alpha=0.3)

    region_cols = [c for c in REGIONS if c in df.columns]
    colors = ["#e41a1c", "#377eb8", "#4daf4a", "#984ea3"]
    for col, color in zip(region_cols, colors):
        ax2.plot(df.index, df[col], linewidth=0.7, label=col, color=color)
    ax2.axhline(0, color="gray", linewidth=0.5, linestyle="--")
    ax2.axhspan(-0.5, 0.5, alpha=0.05, color="gray", label="ENSO neutral (+/-0.5 C)")
    ax2.set_ylabel("SSTA (C)")
    ax2.set_xlabel("Date")
    ax2.set_title("ENSO Regional SST Anomalies")
    ax2.legend(loc="upper left", fontsize=8)
    ax2.grid(True, alpha=0.3)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax2.xaxis.set_major_locator(mdates.MonthLocator())
    plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45, ha="right")

    plt.tight_layout()
    plot_path = os.path.join(SCRIPT_DIR, "ssta_analysis.png")
    plt.savefig(plot_path, dpi=150)
    print(f"\nSaved plot: {plot_path}")
    plt.close()


def main():
    parser = argparse.ArgumentParser(
        description="Analyze NOAA CRW SSTA NetCDF data for El Nino/La Nina assessment",
    )
    parser.add_argument("--top", type=int, default=10, help="Number of extreme days to show")
    parser.add_argument("--no-plot", action="store_true", help="Skip plot generation")
    parser.add_argument("--no-csv", action="store_true", help="Skip CSV export")
    args = parser.parse_args()

    files = find_files()
    print(f"Found {len(files)} NetCDF files")
    print(f"  First: {os.path.basename(files[0])}")
    print(f"  Last:  {os.path.basename(files[-1])}")
    print()

    df = analyze(files)
    print_report(df, top_n=args.top)

    if not args.no_csv:
        export_csv(df)

    if not args.no_plot:
        try:
            plot_timeseries(df)
        except ImportError:
            print("\nSkipping plot (install matplotlib: pip install matplotlib)")


if __name__ == "__main__":
    main()
