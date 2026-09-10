# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

NOAA Coral Reef Watch SSTA analysis toolkit. Downloads daily 5km global Sea Surface Temperature Anomaly data (PNG browse images and NetCDF gridded data), assembles timelapse videos, and performs quantitative analysis (El Nino/La Nina assessment, regional ENSO indices, extreme event detection).

## Commands

```bash
# Download SSTA browse images (~515 MB, skips existing files, 10 parallel connections)
bash download_ssta.sh

# Download SSTA NetCDF data (~6 GB, actual C values, 10 parallel connections)
bash download_ssta_nc.sh

# Generate timelapse video (outputs ssta_anomaly_2025_2026.mp4)
python3 create_ssta_video.py

# Analyze SSTA data: El Nino assessment, extremes, regional stats, plots
python3 analyze_ssta.py [--top N] [--no-plot] [--no-csv]
```

## Dependencies

- **curl** — used by download scripts for parallel downloads
- **Python 3** with `opencv-python` (`pip install opencv-python`) — used by `create_ssta_video.py`
- **Python 3** with `xarray netCDF4 numpy pandas matplotlib` — used by `analyze_ssta.py`
- **ffmpeg** — optional, for H.264 re-encoding

## Architecture

- `download_ssta.sh` — Downloads daily SSTA PNG browse images into `ssta_images/{year}/`. Uses macOS `date -j` syntax.
- `download_ssta_nc.sh` — Downloads daily SSTA NetCDF data (~10 MB/file) into `ssta_data/{year}/`. Same macOS `date -j` syntax.
- `create_ssta_video.py` — Assembles PNGs into timelapse MP4 at 15 fps via OpenCV.
- `analyze_ssta.py` — Reads NetCDF files one at a time (memory-efficient), computes global stats, ENSO regional averages (Nino 3.4/3/1+2, North Atlantic), finds extreme days, assesses El Nino/La Nina strength, exports CSV and PNG plot.
- `ssta_images/` — PNG browse images, gitignored.
- `ssta_data/` — NetCDF gridded data (actual C values), gitignored.
- `*.mp4`, `*.csv`, `ssta_analysis.png` — Generated outputs, gitignored.

## Data Sources

NOAA NCEI Coral Reef Watch v3.1:
- Browse images: `https://www.ncei.noaa.gov/data/oceans/crw/5km/v3.1/image_browse/daily/ssta/png/{year}/`
- NetCDF data: `https://www.ncei.noaa.gov/data/oceans/crw/5km/v3.1/nc/v1.0/daily/ssta/{year}/`
