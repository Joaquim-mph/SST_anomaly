#!/bin/bash
# Fast parallel download of NOAA CRW SSTA daily PNG images for 2025 and 2026
# Re-run anytime to fetch newly available 2026 data — already-downloaded files are skipped.

BASE_URL="https://www.ncei.noaa.gov/data/oceans/crw/5km/v3.1/image_browse/daily/ssta/png"
OUT_DIR="/Users/mphstph/NOAA_coralreef/ssta_images"
PARALLEL=10
TODAY=$(date "+%Y-%m-%d")

generate_urls() {
    local year=$1
    local end_date=$2
    local current="${year}-01-01"

    while [[ "$current" < "$end_date" || "$current" == "$end_date" ]]; do
        local ymd=$(date -j -f "%Y-%m-%d" "$current" "+%Y%m%d" 2>/dev/null)
        local filename="ct5km_ssta_v3.1_global_${ymd}.png"
        local filepath="${OUT_DIR}/${year}/${filename}"
        if [[ ! -f "$filepath" ]]; then
            echo "${BASE_URL}/${year}/${filename} -o ${filepath}"
        fi
        current=$(date -j -v+1d -f "%Y-%m-%d" "$current" "+%Y-%m-%d" 2>/dev/null)
    done
}

echo "=== NOAA Coral Reef Watch SSTA - Fast Parallel Download ==="

mkdir -p "${OUT_DIR}/2025" "${OUT_DIR}/2026"

echo "Today: ${TODAY}"
echo "Generating URL lists..."
URLS_2025=$(generate_urls 2025 "2025-12-31")
URLS_2026=$(generate_urls 2026 "${TODAY}")

COUNT_2025=$(echo "$URLS_2025" | grep -c "http" || true)
COUNT_2026=$(echo "$URLS_2026" | grep -c "http" || true)
echo "  2025: ${COUNT_2025} files to download"
echo "  2026: ${COUNT_2026} files to download"
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
echo "2025: $(ls "${OUT_DIR}/2025"/*.png 2>/dev/null | wc -l | tr -d ' ') files"
echo "2026: $(ls "${OUT_DIR}/2026"/*.png 2>/dev/null | wc -l | tr -d ' ') files"
du -sh "${OUT_DIR}/2025" "${OUT_DIR}/2026" 2>/dev/null
