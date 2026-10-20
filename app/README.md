# FOCAL CVI — feature map explorer

Standalone Streamlit app for exploring dataset features (and CVI outputs) on a map.
Kept separate from the modelling code under `experiments/`.

## Setup

```bash
uv venv .venv
uv pip install -r app/requirements.txt
```

## Publish (full 100 m Germany cache)

See **[DEPLOY.md](DEPLOY.md)** — data is packaged to `dist/app_cache.tar.zst` (~470 MB) and must be hosted on Hugging Face (not git). App downloads it on first boot via `CVI_HF_DATASET` / `CVI_CACHE_URL`.

## Build cache (one-off, re-run when inputs change)

```bash
.venv/bin/python app/build_cache.py all
```

Writes to `data/app_cache/`:

- `cells_100m.parquet` — wide table of raw features + admin keys
- `agg_kreis.parquet`, `agg_gemeinde.parquet`, `agg_1km.parquet`
- `kreis.geojson`, `gemeinde.geojson`
- `features.json` — feature catalogue with provenance (provider, year, resolution, license)
- `sources.json` — data-source cards and feature lists

## Run

```bash
.venv/bin/streamlit run app/streamlit_app.py
```

## Adding CVI outputs

Drop a Parquet into `data/cvi_outputs/<name>.parquet` with columns:

- `east_ll`, `north_ll` (int, canonical 100 m SW-corner keys)
- one or more score columns

Optional `<name>.meta.json`:

```json
{
  "label": "My CVI v1",
  "description": "...",
  "model": "topk_sae",
  "matrix_version": "v1",
  "higher_is_worse": true,
  "columns": {
    "cvi_score": {"label": "CVI", "unit": "z", "kind": "continuous"}
  }
}
```

The app discovers new files automatically (no cache rebuild).
