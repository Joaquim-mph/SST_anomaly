# SST Anomaly Timelapse

Timelapse video of global Sea Surface Temperature (SST) anomalies using daily 5km imagery from [NOAA Coral Reef Watch](https://coralreefwatch.noaa.gov/) (v3.1), covering 2025–2026.

![NOAA CRW SSTA sample](https://www.ncei.noaa.gov/data/oceans/crw/5km/v3.1/image_browse/daily/ssta/png/2025/ct5km_ssta_v3.1_global_20250101.png)

## Quick Start

```bash
# 1. Download daily SSTA images (~515 MB)
bash download_ssta.sh

# 2. Generate the timelapse video
python3 create_ssta_video.py
```

The output video is saved as `ssta_anomaly_2025_2026.mp4`.

## Latest data refresh

Refreshed on **19 November 2026** (20 November UTC):

- Daily SSTA images and NetCDF data: **1 January 2025–18 November 2026**, 687 days with no gaps. Added 29 days since the previous refresh.
- NCEI supplied data through 13 November; the NOAA STAR mirror supplied 14–18 November. Data for 19 November was not available from either source at refresh time.
- ENSO index snapshot: `data/raw/20261120/`, with `data/raw/latest` pointing to it. All eight files passed manifest size, SHA-256 and parser checks. Monthly OISST, wind and warm water volume data extend through October; weekly OISST through 11 November; ONI/RONI through August–October.
- Daily/monthly CSVs, `ssta_analysis.png` and the 687-frame timelapse were regenerated locally. Downloads and generated outputs remain excluded from Git.
- The latest observations are summarized in [the El Niño report](el_nino_2026_report.md). Forecast outputs retain their original October initialization; refreshing inputs alone does not produce a November forecast.

To refresh the quantitative data and ENSO snapshot as well as the images:

```bash
bash download_ssta_nc.sh
bash fetch_enso_indices.sh
.venv/bin/python analyze_ssta.py
```

If recent days are missing from NCEI, rerun the downloaders against the STAR mirror:

```bash
BASE_URL=https://www.star.nesdis.noaa.gov/pub/socd/mecb/crw/data/5km/v3.1_op/image_browse/daily/ssta/png bash download_ssta.sh
BASE_URL=https://www.star.nesdis.noaa.gov/pub/socd/mecb/crw/data/5km/v3.1_op/nc/v1.0/daily/ssta bash download_ssta_nc.sh
```

## Scripts

| Script | Description |
|--------|-------------|
| `download_ssta.sh` | Downloads daily SSTA PNG images from NOAA for 2025 (full year) and 2026 (up to today). Uses 10 parallel connections and skips already-downloaded files, so re-running it fetches only new data. |
| `create_ssta_video.py` | Assembles all downloaded images into an MPEG-4 MP4 timelapse at 15 fps. |
| `download_ssta_nc.sh` | Downloads daily gridded SSTA NetCDF data, skipping existing files. |
| `analyze_ssta.py` | Computes daily and monthly statistics and regional anomalies; exports CSVs and a plot. |
| `fetch_enso_indices.sh` | Downloads an immutable dated ENSO index snapshot with source metadata and checksums. |

## Requirements

- **bash**, **curl** (macOS/Linux)
- **Python 3** with `opencv-python` (`pip install opencv-python`)
- For quantitative analysis: `xarray netCDF4 numpy pandas matplotlib`.
- **ffmpeg** (optional, used for H.264 re-encoding)

## Data Source

- **Dataset:** NOAA Coral Reef Watch Daily Global 5km SST Anomaly (v3.1)
- **URL:** https://www.ncei.noaa.gov/data/oceans/crw/5km/v3.1/image_browse/daily/ssta/png/
- **Resolution:** 5 km
- **Coverage:** Global, daily

Images and generated videos are excluded from the repo via `.gitignore` since they can be reproduced with the download script.

## License

[MIT](LICENSE)
