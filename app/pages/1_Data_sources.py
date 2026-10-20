#!/usr/bin/env python3
"""Data sources used by the FOCAL CVI feature explorer."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from lib.catalog import load_features, load_sources  # noqa: E402
from lib.paths import APP_CACHE, SOURCES_JSON  # noqa: E402
from lib.queries import cache_ready  # noqa: E402

st.set_page_config(page_title="Data sources", layout="wide")


def main():
    st.title("Data sources")
    from lib.bootstrap import ensure_app_cache
    if not cache_ready():
        ensure_app_cache()
    if not cache_ready() or not SOURCES_JSON.exists():
        st.error(
            f"App cache / sources missing under `{APP_CACHE}`.\n\n"
            "Locally: `.venv/bin/python app/build_cache.py features`\n\n"
            "Cloud: set `CVI_HF_DATASET` or `CVI_CACHE_URL` (see `app/DEPLOY.md`)."
        )
        return

    sources = load_sources()
    features = load_features()
    if not sources:
        st.warning("sources.json is empty.")
        return

    st.markdown(
        """
The explorer shows **raw published units** on the FOCAL CVI target grid:

| | |
|---|---|
| **Grid** | 100 m × 100 m INSPIRE / **EPSG:3035** |
| **Join key** | `east_ll`, `north_ll` (SW corner, metres) |
| **Coverage** | Germany matrix cells (~3.14 M) with Zensus themes |
| **Caveat** | Source **years are mixed** (e.g. Tree Cover 2015, Imperviousness 2018, Zensus 2022, LST 2023, AlphaEarth 2024, BA AMK 2024). |

HYRAS hazard indices are shown for exploration; in the modelling framework they
are a **hazard sidecar**, not SAE predictors.
"""
    )

    st.caption(
        f"{len(sources)} sources · {len(features)} features in the explorer cache"
    )

    # Overview table
    overview = pd.DataFrame([{
        "id": s.id,
        "title": s.title,
        "provider": s.provider,
        "inventory_id": s.inventory_id,
        "year": s.year,
        "native_resolution": s.native_resolution,
        "grid_resolution": s.grid_resolution,
        "license": s.license,
        "n_features": s.feature_count,
    } for s in sources])
    st.dataframe(overview, hide_index=True, width="stretch")

    st.markdown("---")
    for s in sources:
        with st.expander(
            f"**{s.title}** · `{s.id}` · {s.feature_count} features",
            expanded=False,
        ):
            meta = {
                "Provider": s.provider,
                "Product": s.product,
                "Inventory ID": s.inventory_id,
                "Year": s.year,
                "Native resolution": s.native_resolution,
                "Grid resolution": s.grid_resolution,
                "CRS": s.crs,
                "License": s.license,
                "Resampling": s.resampling,
                "Coverage": s.coverage,
            }
            st.table(pd.DataFrame(
                {"field": list(meta.keys()), "value": list(meta.values())}
            ))
            if s.description:
                st.markdown(s.description)
            if s.url:
                st.markdown(f"[Primary documentation]({s.url})")
            if s.columns:
                st.markdown("**Features from this source**")
                st.code("\n".join(s.columns), language=None)


main()
