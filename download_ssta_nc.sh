#!/bin/bash
# Download NOAA CRW 5km SSTA daily NetCDF data for 2025 and 2026.
# These contain actual anomaly values (°C) — unlike the PNG browse images.
# Re-run anytime to fetch newly available data; already-downloaded files are skipped.
#
# Each file is ~10 MB. Full 2025–2026 download is ~6 GB.

BASE_URL="https://www.ncei.noaa.gov/data/oceans/crw/5km/v3.1/nc/v1.0/daily/ssta"
OUT_DIR="/Users/mphstph/NOAA_coralreef/ssta_data"
PARALLEL=10
TODAY=$(date "+%Y-%m-%d")

generate_urls() {
    local year=$1
    local end_date=$2
    local current="${year}-01-01"

    while [[ "$current" < "$end_date" || "$current" == "$end_date" ]]; do
        local ymd=$(date -j -f "%Y-%m-%d" "$current" "+%Y%m%d" 2>/dev/null)
        local filename="ct5km_ssta_v3.1_${ymd}.nc"
        local filepath="${OUT_DIR}/${year}/${filename}"
        if [[ ! -f "$filepath" ]]; then
            echo "${BASE_URL}/${year}/${filename} -o ${filepath}"
        fi
        current=$(date -j -v+1d -f "%Y-%m-%d" "$current" "+%Y-%m-%d" 2>/dev/null)
    done
}

echo "=== NOAA Coral Reef Watch SSTA NetCDF - Parallel Download ==="
echo "WARNING: Each file is ~10 MB. Full 2025-2026 download is ~6 GB."
echo ""

mkdir -p "${OUT_DIR}/2025" "${OUT_DIR}/2026"

echo "Today: ${TODAY}"
echo "Generating URL lists..."
URLS_2025=$(generate_urls 2025 "2025-12-31")
URLS_2026=$(generate_urls 2026 "${TODAY}")

COUNT_2025=$(echo "$URLS_2025" | grep -c "http" || true)
COUNT_2026=$(echo "$URLS_2026" | grep -c "http" || true)
TOTAL_SIZE_GB=$(echo "scale=1; (${COUNT_2025} + ${COUNT_2026}) * 10 / 1024" | bc)
echo "  2025: ${COUNT_2025} files to download"
echo "  2026: ${COUNT_2026} files to download"
echo "  Estimated size: ~${TOTAL_SIZE_GB} GB"
echo ""

download_batch() {
    local url_list="$1"
    local label="$2"
    if [[ -z "$url_list" ]]; then
        echo "  ${label}: nothing to download (all files exist)"
        return
    fi
    echo "  Downloading ${label} (${PARALLEL} parallel connections)..."
    echo "$url_list" | xargs -P ${PARALLEL} -I {} sh -c 'curl -sf {} && echo -n "."'
    echo ""
    echo "  ${label} done."
}

download_batch "$URLS_2025" "2025"
download_batch "$URLS_2026" "2026"

echo ""
echo "=== Download complete ==="
echo "2025: $(ls "${OUT_DIR}/2025"/*.nc 2>/dev/null | wc -l | tr -d ' ') files"
echo "2026: $(ls "${OUT_DIR}/2026"/*.nc 2>/dev/null | wc -l | tr -d ' ') files"
du -sh "${OUT_DIR}/2025" "${OUT_DIR}/2026" 2>/dev/null
