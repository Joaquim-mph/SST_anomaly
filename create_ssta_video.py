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

def collect_images():
    files = sorted(
        glob.glob(os.path.join(IMAGE_DIR, "2025", "ct5km_ssta_v3.1_global_*.png"))
        + glob.glob(os.path.join(IMAGE_DIR, "2026", "ct5km_ssta_v3.1_global_*.png"))
    )
    return files

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
        if frame.shape[1] != w_out or frame.shape[0] != h_out:
            frame = frame[:h_out, :w_out]
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
