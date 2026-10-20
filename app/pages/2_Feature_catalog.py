#!/usr/bin/env python3
"""Searchable feature catalogue with coverage, provenance, and histograms."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from lib.catalog import (  # noqa: E402
    feature_blocks,
    filter_features,
    load_features,
)
from lib.paths import APP_CACHE  # noqa: E402
from lib.queries import cache_ready, feature_histogram, feature_stats  # noqa: E402

st.set_page_config(page_title="Feature catalogue", layout="wide")


def main():
    st.title("Feature catalogue")
    from lib.bootstrap import ensure_app_cache
    if not cache_ready():
        ensure_app_cache()
    if not cache_ready():
        st.error(
            f"App cache missing under `{APP_CACHE}`. "
            "Locally: `python app/build_cache.py all`. "
            "Cloud: set `CVI_HF_DATASET` / `CVI_CACHE_URL` (see `app/DEPLOY.md`)."
        )
        return

    features = load_features()
    if not features:
        st.warning("features.json is empty.")
        return

    blocks = feature_blocks(features)
    c1, c2, c3 = st.columns(3)
    with c1:
        sel_blocks = st.multiselect("Block", blocks, default=blocks)
    with c2:
        q = st.text_input(
            "Search (column / indicator / provider / product / inventory)",
            "",
        )
    with c3:
        min_cov = st.slider("Min observed fraction", 0.0, 1.0, 0.0, 0.05)

    filtered = filter_features(features, blocks=sel_blocks or None)
    if q:
        ql = q.lower()
        filtered = [
            f for f in filtered
            if ql in f.column.lower()
            or ql in (f.indicator or "").lower()
            or ql in (f.note or "").lower()
            or ql in (f.component or "").lower()
            or ql in (f.provider or "").lower()
            or ql in (f.product or "").lower()
            or ql in (f.inventory_id or "").lower()
            or ql in (f.source_id or "").lower()
            or ql in (f.year or "").lower()
        ]
    filtered = [f for f in filtered if f.observed_frac >= min_cov]

    rows = [{
        "column": f.column,
        "block": f.block,
        "indicator": f.indicator,
        "provider": f.provider,
        "year": f.year,
        "native_resolution": f.native_resolution,
        "license": f.license,
        "observed_frac": round(f.observed_frac, 3),
        "inventory_id": f.inventory_id,
        "component": f.component,
    } for f in filtered]
    table = pd.DataFrame(rows)
    st.dataframe(table, hide_index=True, width="stretch")
    st.caption(f"{len(filtered)} / {len(features)} features")

    st.markdown("---")
    st.subheader("Feature detail")
    if not filtered:
        return
    labels = [f"{f.block} · {f.column}" for f in filtered]
    idx = st.selectbox("Inspect", range(len(labels)), format_func=lambda i: labels[i])
    feat = filtered[idx]

    st.markdown(
        f"**{feat.indicator or feat.column}**  \n"
        f"Block `{feat.block}` · {feat.component} · unit `{feat.unit}`  \n"
        f"{feat.note}"
    )
    st.caption(feat.provenance_line)

    with st.expander("Feature metadata", expanded=True):
        st.json({
            **feat.provenance_dict(),
            "column": feat.column,
            "block": feat.block,
            "component": feat.component,
            "indicator": feat.indicator,
            "unit": feat.unit,
            "note": feat.note,
            "observed_frac": feat.observed_frac,
        })

    stats = feature_stats(feat.column, "kreis")
    hist = feature_histogram(feat.column, "kreis")
    a, b = st.columns([1, 2])
    with a:
        st.subheader("Summary (Kreis means)")
        st.json(stats)
    with b:
        st.subheader("Histogram (Kreis means)")
        if not hist.empty:
            st.bar_chart(hist.set_index("bin_left")["count"])
        else:
            st.write("No histogram data.")


main()
