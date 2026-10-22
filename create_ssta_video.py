#!/usr/bin/env python3
"""Create a timelapse video from NOAA Coral Reef Watch daily SSTA images (2025–2026)."""

import glob
import os
import sys
import cv2
import numpy as np

IMAGE_DIR = os.path.join(os.path.dirname(__file__), "ssta_images")
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "ssta_anomaly_2025_2026.mp4")
FPS = 15

# Layout of the NCEI browse images (1787x1054) and of the taller variant served
# by the NOAA STAR mirror (1787x1085), measured from the images.
NCEI_MAP_BOX = (98, 109, 1689, 904)  # x0, y0, x1, y1
STAR_SIZE = (1787, 1085)
STAR_MAP_BOX = (67, 110, 1720, 937)
TITLE_BOTTOM = 60
# STAR row bands copied below the map: (src_start, src_end, dst_start).
# The colour bar sits 36 px lower in STAR images, its tick labels 31 px lower.
STAR_BOTTOM_BANDS = [(996, 1051, 960), (1051, 1085, 1020)]
NCEI_BOTTOM_START = 960

def collect_images():
    files = sorted(
        glob.glob(os.path.join(IMAGE_DIR, "2025", "ct5km_ssta_v3.1_global_*.png"))
        + glob.glob(os.path.join(IMAGE_DIR, "2026", "ct5km_ssta_v3.1_global_*.png"))
    )
    return files

def star_to_ncei_layout(frame, w_out, h_out):
    """Re-lay a STAR-mirror frame onto the NCEI layout so the map doesn't jump."""
    (ax0, ay0, ax1, ay1), (bx0, by0, bx1, by1) = NCEI_MAP_BOX, STAR_MAP_BOX
    sx, sy = (ax1 - ax0) / (bx1 - bx0), (ay1 - ay0) / (by1 - by0)
    m = np.float32([[sx, 0, ax0 - bx0 * sx], [0, sy, ay0 - by0 * sy]])
    out = cv2.warpAffine(frame, m, (w_out, h_out), flags=cv2.INTER_AREA,
                         borderValue=(255, 255, 255))
    out[:TITLE_BOTTOM] = frame[:TITLE_BOTTOM, :w_out]
    out[NCEI_BOTTOM_START:] = 255
    for src0, src1, dst0 in STAR_BOTTOM_BANDS:
        rows = min(src1 - src0, h_out - dst0)
        out[dst0:dst0 + rows] = frame[src0:src0 + rows, :w_out]
    return out


def main():
    files = collect_images()
    if not files:
        print("No images found. Run download_ssta.sh first.")
        sys.exit(1)

    print(f"Found {len(files)} images")
    print(f"  First: {os.path.basename(files[0])}")
    print(f"  Last:  {os.path.basename(files[-1])}")
    print(f"  FPS:   {FPS}  →  video duration: {len(files) / FPS:.1f}s")

    sample = cv2.imread(files[0])
    h, w = sample.shape[:2]

    # Ensure dimensions are even (required by H.264)
    w_out = w if w % 2 == 0 else w - 1
    h_out = h if h % 2 == 0 else h - 1

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(OUTPUT_FILE, fourcc, FPS, (w_out, h_out))

    for i, path in enumerate(files):
        frame = cv2.imread(path)
        if frame is None:
            print(f"  Skipping unreadable: {os.path.basename(path)}")
            continue
        if (frame.shape[1], frame.shape[0]) == STAR_SIZE:
            frame = star_to_ncei_layout(frame, w_out, h_out)
        elif frame.shape[1] != w_out or frame.shape[0] != h_out:
            frame = cv2.resize(frame, (w_out, h_out), interpolation=cv2.INTER_AREA)
        writer.write(frame)
        if (i + 1) % 50 == 0 or i == len(files) - 1:
            print(f"  Processed {i + 1}/{len(files)}")

    writer.release()
    size_mb = os.path.getsize(OUTPUT_FILE) / (1024 * 1024)
    print(f"\nDone! Video saved to: {OUTPUT_FILE}")
    print(f"  Resolution: {w_out}x{h_out}")
    print(f"  Size: {size_mb:.1f} MB")

if __name__ == "__main__":
    main()
