#!/bin/bash
# Download ENSO index files (CPC OISST/ONI/RONI, CPC 850 hPa winds, PMEL warm water volume)
# into a dated snapshot directory data/raw/YYYYMMDD/{cpc,pmel}/ with a MANIFEST.json.
# Existing snapshots are never modified; data/raw/latest points to the newest one.

CPC_URL="https://www.cpc.ncep.noaa.gov/data/indices"
PMEL_URL="https://www.pmel.noaa.gov/tao/wwv/data"
ROOT="/Users/mphstph/NOAA_coralreef/data/raw"
STAMP=$(date -u "+%Y%m%d")
OUT_DIR="${ROOT}/${STAMP}"

CPC_FILES="sstoi.indices wksst9120.for oni.ascii.txt RONI.ascii.txt wpac850 cpac850 epac850"
PMEL_FILES="wwv.dat"

if [[ -d "$OUT_DIR" ]]; then
    echo "Snapshot ${OUT_DIR} already exists; not overwriting."
    exit 0
fi

echo "=== ENSO index download -> ${OUT_DIR} ==="
mkdir -p "${OUT_DIR}/cpc" "${OUT_DIR}/pmel"

MANIFEST="${OUT_DIR}/MANIFEST.json"
echo "{" > "$MANIFEST"
echo "  \"snapshot\": \"${STAMP}\"," >> "$MANIFEST"
echo "  \"downloaded_utc\": \"$(date -u "+%Y-%m-%dT%H:%M:%SZ")\"," >> "$MANIFEST"
echo "  \"files\": [" >> "$MANIFEST"

first=1
fetch() {
    local url=$1
    local dest=$2
    local headers
    headers=$(curl -sfSIL "$url" | tr -d '\r')
    if ! curl -sfSL "$url" -o "$dest"; then
        echo "  FAILED: $url"
        exit 1
    fi
    local modified=$(echo "$headers" | grep -i '^last-modified:' | tail -1 | cut -d' ' -f2-)
    local bytes=$(wc -c < "$dest" | tr -d ' ')
    local sha=$(shasum -a 256 "$dest" | cut -d' ' -f1)
    [[ $first -eq 0 ]] && echo "    ," >> "$MANIFEST"
    first=0
    cat >> "$MANIFEST" <<EOF
    {"path": "${dest#${OUT_DIR}/}", "url": "${url}", "last_modified": "${modified}", "bytes": ${bytes}, "sha256": "${sha}"}
EOF
    echo "  ${dest#${OUT_DIR}/}  (${bytes} bytes, Last-Modified: ${modified})"
}

for f in $CPC_FILES; do fetch "${CPC_URL}/${f}" "${OUT_DIR}/cpc/${f}"; done
for f in $PMEL_FILES; do fetch "${PMEL_URL}/${f}" "${OUT_DIR}/pmel/${f}"; done

echo "  ]" >> "$MANIFEST"
echo "}" >> "$MANIFEST"

chmod -R a-w "${OUT_DIR}"
ln -sfn "${STAMP}" "${ROOT}/latest"
echo "=== Done. Files are read-only; data/raw/latest -> ${STAMP} ==="
