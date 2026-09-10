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

## Scripts

| Script | Description |
|--------|-------------|
| `download_ssta.sh` | Downloads daily SSTA PNG images from NOAA for 2025 (full year) and 2026 (up to today). Uses 10 parallel connections and skips already-downloaded files, so re-running it fetches only new data. |
| `create_ssta_video.py` | Assembles all downloaded images into an H.264 MP4 timelapse at 15 fps. |

## Requirements

- **bash**, **curl** (macOS/Linux)
- **Python 3** with `opencv-python` (`pip install opencv-python`)
- **ffmpeg** (optional, used for H.264 re-encoding)

## Data Source

- **Dataset:** NOAA Coral Reef Watch Daily Global 5km SST Anomaly (v3.1)
- **URL:** https://www.ncei.noaa.gov/data/oceans/crw/5km/v3.1/image_browse/daily/ssta/png/
- **Resolution:** 5 km
- **Coverage:** Global, daily

Images and generated videos are excluded from the repo via `.gitignore` since they can be reproduced with the download script.

## License

[MIT](LICENSE)
