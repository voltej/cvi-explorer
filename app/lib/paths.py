"""Canonical paths for the feature map explorer."""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "data"
EXPERIMENTS = REPO / "experiments"

JOINT_PARQUET = DATA / "cvi_joint_100m.parquet"
HAZARD_PARQUET = DATA / "cvi_hazard_100m.parquet"
FEATURES_CSV = DATA / "cvi_joint_features_v1.csv"
LAYERS_ZARR = REPO / "cvi_layers_100m.zarr"
ADMIN_ON_GRID = EXPERIMENTS / "admin_parquet" / "admin_on_grid.parquet"
VG250_KREIS = EXPERIMENTS / "boundaries_parquet" / "vg250_kreis.parquet"
VG250_GEMEINDE = EXPERIMENTS / "boundaries_parquet" / "vg250_gemeinde.parquet"

APP_CACHE = DATA / "app_cache"
CELLS_100M = APP_CACHE / "cells_100m.parquet"
AGG_KREIS = APP_CACHE / "agg_kreis.parquet"
AGG_GEMEINDE = APP_CACHE / "agg_gemeinde.parquet"
AGG_1KM = APP_CACHE / "agg_1km.parquet"
KREIS_GEOJSON = APP_CACHE / "kreis.geojson"
GEMEINDE_GEOJSON = APP_CACHE / "gemeinde.geojson"
FEATURES_JSON = APP_CACHE / "features.json"
SOURCES_JSON = APP_CACHE / "sources.json"
CVI_OUTPUTS = DATA / "cvi_outputs"

# Bundled into app_cache for cloud deploys (also used locally once copied)
CELL_ADMIN = APP_CACHE / "cell_admin_100m.parquet"
