#!/usr/bin/env bash
# Package data/app_cache (incl. 100 m cells + cell_admin) for cloud upload.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

CACHE="data/app_cache"
OUT_DIR="${1:-dist}"
mkdir -p "$OUT_DIR"

if [[ ! -f "$CACHE/cells_100m.parquet" ]]; then
  echo "Missing $CACHE/cells_100m.parquet — run: python app/build_cache.py all" >&2
  exit 1
fi

if [[ ! -f "$CACHE/cell_admin_100m.parquet" ]]; then
  if [[ -f experiments/cell_admin_100m.parquet ]]; then
    cp experiments/cell_admin_100m.parquet "$CACHE/cell_admin_100m.parquet"
  else
    echo "Missing cell_admin_100m.parquet" >&2
    exit 1
  fi
fi

STAMP=$(date +%Y%m%d)
TAR_GZ="$OUT_DIR/app_cache_${STAMP}.tar.gz"
TAR_ZST="$OUT_DIR/app_cache.tar.zst"

echo "Packaging $CACHE → $TAR_GZ …"
# Archive paths relative to repo root so extract lands in data/app_cache/
tar -czf "$TAR_GZ" \
  data/app_cache/cells_100m.parquet \
  data/app_cache/agg_kreis.parquet \
  data/app_cache/agg_gemeinde.parquet \
  data/app_cache/agg_1km.parquet \
  data/app_cache/kreis.geojson \
  data/app_cache/gemeinde.geojson \
  data/app_cache/features.json \
  data/app_cache/sources.json \
  data/app_cache/cell_admin_100m.parquet \
  data/cvi_outputs

ls -lh "$TAR_GZ"

if command -v zstd >/dev/null 2>&1; then
  echo "Also writing $TAR_ZST …"
  tar -cf - \
    data/app_cache/cells_100m.parquet \
    data/app_cache/agg_kreis.parquet \
    data/app_cache/agg_gemeinde.parquet \
    data/app_cache/agg_1km.parquet \
    data/app_cache/kreis.geojson \
    data/app_cache/gemeinde.geojson \
    data/app_cache/features.json \
    data/app_cache/sources.json \
    data/app_cache/cell_admin_100m.parquet \
    data/cvi_outputs \
    | zstd -T0 -19 -o "$TAR_ZST"
  ls -lh "$TAR_ZST"
  # stable name for HF bootstrap default
  cp -f "$TAR_ZST" "$OUT_DIR/app_cache.tar.zst" 2>/dev/null || true
else
  echo "zstd not installed — using .tar.gz only (set CVI_HF_FILENAME=app_cache_*.tar.gz)"
  cp -f "$TAR_GZ" "$OUT_DIR/app_cache.tar.gz"
fi

echo "Done. Upload $OUT_DIR/app_cache.tar.* to Hugging Face (see app/DEPLOY.md)."
