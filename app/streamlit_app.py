#!/usr/bin/env python3
"""FOCAL CVI — feature map explorer (main Streamlit page)."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pydeck as pdk
import streamlit as st

APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from lib.catalog import (  # noqa: E402
    CVI_CONTRACT_HELP,
    discover_cvi_outputs,
    feature_blocks,
    feature_components,
    filter_features,
    load_features_from_rows,
)
from lib.layers import (  # noqa: E402
    PALETTES,
    bounds_center,
    colorize_series,
    compute_breaks,
    legend_rows,
    make_geojson_layer,
    make_grid_cell_layer,
    make_view,
)
from lib.paths import APP_CACHE, CELLS_100M  # noqa: E402
from lib.queries import (  # noqa: E402
    cache_ready,
    cells_for_kreis,
    cvi_agg,
    feature_agg,
    feature_histogram,
    feature_stats,
    join_geojson_values,
    list_kreise,
    load_gemeinde_geojson,
    load_kreis_geojson,
    unit_profile,
)

st.set_page_config(
    page_title="CVI Feature Explorer",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_resource
def _bust_stale_feature_cache() -> bool:
    """One-shot clear of pre-provenance Feature pickles in st.cache_data."""
    st.cache_data.clear()
    return True


_bust_stale_feature_cache()


def _ensure_cache() -> bool:
    if cache_ready():
        return True
    # Cloud: download prebuilt 100 m cache if CVI_CACHE_URL / CVI_HF_DATASET set
    from lib.bootstrap import ensure_app_cache
    with st.spinner("Downloading app cache (100 m data)…"):
        ok = ensure_app_cache()
    if ok and cache_ready():
        return True
    st.error(
        f"App cache not found under `{APP_CACHE}`.\n\n"
        "Locally: `.venv/bin/python app/build_cache.py all`\n\n"
        "Cloud: set secret `CVI_HF_DATASET` or `CVI_CACHE_URL` "
        "(see `app/DEPLOY.md`)."
    )
    return False


def _features_mtime() -> float:
    from lib.paths import FEATURES_JSON
    return FEATURES_JSON.stat().st_mtime if FEATURES_JSON.exists() else 0.0


@st.cache_data(show_spinner=False)
def _features_raw(_mtime: float) -> list[dict]:
    """Cache plain dicts (not Feature dataclasses) to avoid stale pickle issues."""
    import json
    from lib.paths import FEATURES_JSON
    if not FEATURES_JSON.exists():
        return []
    return json.loads(FEATURES_JSON.read_text())


def _features():
    """Rebuild Feature objects every run from cached JSON dicts."""
    return load_features_from_rows(_features_raw(_features_mtime()))


@st.cache_data(show_spinner=False)
def _cvis(_folder_mtime: float):
    return discover_cvi_outputs()


def _cvi_folder_mtime() -> float:
    from lib.paths import CVI_OUTPUTS
    if not CVI_OUTPUTS.exists():
        return 0.0
    mt = CVI_OUTPUTS.stat().st_mtime
    for p in CVI_OUTPUTS.iterdir():
        mt = max(mt, p.stat().st_mtime)
    return mt


def sidebar():
    st.sidebar.title("CVI Feature Explorer")
    source = st.sidebar.radio("Source", ["Features", "CVI outputs"], index=0)

    features = _features()
    cvis = _cvis(_cvi_folder_mtime())

    selection: dict = {"source": source}

    if source == "Features":
        blocks = feature_blocks(features)
        sel_blocks = st.sidebar.multiselect("Blocks", blocks, default=blocks)
        comps = feature_components(
            filter_features(features, blocks=sel_blocks or None)
        )
        sel_comps = st.sidebar.multiselect(
            "Component (optional)", comps, default=[],
        )
        filtered = filter_features(
            features,
            blocks=sel_blocks or None,
            components=sel_comps or None,
        )
        if not filtered:
            st.sidebar.warning("No features match the filters.")
            selection["feature"] = None
        else:
            labels = [f.label for f in filtered]
            idx = st.sidebar.selectbox(
                "Feature", range(len(labels)),
                format_func=lambda i: labels[i],
            )
            selection["feature"] = filtered[idx]
            selection["column"] = filtered[idx].column
            selection["kind"] = "continuous"
    else:
        if not cvis:
            st.sidebar.info(
                "No CVI outputs found yet. Drop a Parquet into "
                "`data/cvi_outputs/` (see contract below)."
            )
            selection["feature"] = None
            selection["cvi"] = None
        else:
            cvi_idx = st.sidebar.selectbox(
                "CVI", range(len(cvis)),
                format_func=lambda i: cvis[i].display,
            )
            cvi = cvis[cvi_idx]
            selection["cvi"] = cvi
            col_idx = st.sidebar.selectbox(
                "Column", range(len(cvi.columns)),
                format_func=lambda i: cvi.columns[i].display,
            )
            cc = cvi.columns[col_idx]
            selection["column"] = cc.name
            selection["kind"] = cc.kind
            selection["feature"] = None

    level = st.sidebar.selectbox(
        "Aggregation level",
        ["kreis", "gemeinde", "1km", "100m"],
        format_func=lambda x: {
            "kreis": "Kreis",
            "gemeinde": "Gemeinde",
            "1km": "1 km",
            "100m": "100 m (requires Kreis)",
        }[x],
    )
    selection["level"] = level

    kreise = list_kreise()
    kreis_options = ["(all / none)"] + [
        f"{r['name']} ({r['ags_kreis']})" for _, r in kreise.iterrows()
    ]
    kreis_pick = st.sidebar.selectbox("Focus Kreis", kreis_options)
    if kreis_pick == "(all / none)":
        selection["kreis"] = None
        selection["kreis_name"] = None
    else:
        ags = kreis_pick.rsplit("(", 1)[-1].rstrip(")")
        selection["kreis"] = ags
        selection["kreis_name"] = kreis_pick

    if level == "100m" and not selection["kreis"]:
        st.sidebar.warning("Select a Kreis to view 100 m cells.")

    st.sidebar.markdown("---")
    st.sidebar.subheader("Styling")
    palette = st.sidebar.selectbox(
        "Palette", list(PALETTES.keys()), index=0,
    )
    scale_mode = st.sidebar.radio(
        "Scale", ["quantile", "linear"], horizontal=True,
    )
    clip = st.sidebar.checkbox("Clip to 2nd–98th percentile", value=True)
    log_scale = st.sidebar.checkbox("Log scale (log1p)", value=False)
    selection.update(
        palette=palette,
        scale_mode=scale_mode,
        clip_pct=(2.0, 98.0) if clip else (0.0, 100.0),
        log_scale=log_scale,
    )

    with st.sidebar.expander("CVI drop-in contract"):
        st.markdown(CVI_CONTRACT_HELP)

    return selection


def _load_values(sel: dict) -> pd.DataFrame:
    col = sel.get("column")
    if not col:
        return pd.DataFrame()
    level = sel["level"]
    kreis = sel.get("kreis")
    if level == "100m" and not kreis:
        return pd.DataFrame()

    if sel["source"] == "Features":
        return feature_agg(col, level, kreis=kreis)

    cvi = sel.get("cvi")
    if cvi is None:
        return pd.DataFrame()
    return cvi_agg(cvi.path, col, sel.get("kind", "continuous"), level, kreis=kreis)


def _build_map(sel: dict, df: pd.DataFrame):
    level = sel["level"]
    palette = sel["palette"]
    if df.empty or "value" not in df.columns:
        return None, [], make_view()

    breaks = compute_breaks(
        df["value"].tolist(),
        mode=sel["scale_mode"],
        clip_pct=sel["clip_pct"],
        log_scale=sel["log_scale"],
    )
    colors = colorize_series(df["value"], breaks, palette=palette)
    legend = legend_rows(breaks, palette=palette)

    layers = []
    view = make_view()
    tooltip = {
        "html": "<b>{name}</b><br/>value: {value}<br/>"
                "n_cells: {n_cells}<br/>n_obs: {n_obs}",
        "style": {"backgroundColor": "steelblue", "color": "white"},
    }

    if level in ("kreis", "gemeinde"):
        id_field = "ags_kreis" if level == "kreis" else "ags_gem"
        gj = load_kreis_geojson() if level == "kreis" else load_gemeinde_geojson()
        if sel.get("kreis") and level == "gemeinde":
            # Filter features to selected kreis
            gj = {
                "type": "FeatureCollection",
                "features": [
                    f for f in gj.get("features", [])
                    if str((f.get("properties") or {}).get("ags_kreis", ""))
                    == sel["kreis"]
                ],
            }
        elif sel.get("kreis") and level == "kreis":
            gj = {
                "type": "FeatureCollection",
                "features": [
                    f for f in gj.get("features", [])
                    if str((f.get("properties") or {}).get("ags_kreis", ""))
                    == sel["kreis"]
                ],
            }
        colored = join_geojson_values(gj, df, id_field, fill_colors=colors)
        layers.append(make_geojson_layer(colored))
        # Zoom to selection
        if sel.get("kreis") and colored["features"]:
            # rough centre from first feature bbox via lon/lat of cells
            if CELLS_100M.exists():
                cells = cells_for_kreis(sel["kreis"], columns=[])
                if not cells.empty:
                    lon, lat, zoom = bounds_center(cells)
                    view = make_view(lon, lat, zoom)
        tooltip = {
            "html": "<b>{name}</b> ({ags_kreis})<br/>"
                    "value: {value}<br/>n_cells: {n_cells}<br/>n_obs: {n_obs}",
            "style": {"backgroundColor": "steelblue", "color": "white"},
        }
    else:
        plot = df.copy()
        plot["fill_color"] = colors
        if "lon" not in plot.columns or "lat" not in plot.columns:
            st.warning("Grid view needs lon/lat columns.")
            return None, legend, view
        cell_size = 1000.0 if level == "1km" else 100.0
        # Subsample 1km nationwide if huge
        if level == "1km" and not sel.get("kreis") and len(plot) > 80_000:
            plot = plot.sample(80_000, random_state=0)
            st.caption(f"Showing a random sample of 80 000 / {len(df):,} 1 km cells.")
        layers.append(make_grid_cell_layer(plot, cell_size=cell_size))
        lon, lat, zoom = bounds_center(plot)
        view = make_view(lon, lat, zoom)
        tooltip = {
            "html": "({east_ll}, {north_ll})<br/>value: {value}<br/>"
                    "n_cells: {n_cells}",
            "style": {"backgroundColor": "steelblue", "color": "white"},
        }

    deck = pdk.Deck(
        layers=layers,
        initial_view_state=view,
        tooltip=tooltip,
        map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
    )
    return deck, legend, view


def _render_legend(legend: list[dict]):
    if not legend:
        return
    parts = [
        f'<span style="display:inline-block;width:14px;height:14px;'
        f'background:{r["color"]};margin-right:6px;border:1px solid #666;"></span>'
        f'{r["label"]}'
        for r in legend
    ]
    st.markdown(
        "<div style='font-size:0.85rem;line-height:1.8'>"
        + "<br/>".join(parts)
        + "</div>",
        unsafe_allow_html=True,
    )


def _render_stats_hist(sel: dict):
    col = sel.get("column")
    if not col:
        return
    level = sel["level"]
    kreis = sel.get("kreis")
    if level == "100m" and not kreis:
        return

    if sel["source"] == "Features":
        stats = feature_stats(col, level, kreis=kreis)
        hist = feature_histogram(col, level, kreis=kreis)
    else:
        df = _load_values(sel)
        if df.empty or "value" not in df.columns:
            stats, hist = {}, pd.DataFrame()
        else:
            v = df["value"].dropna()
            stats = {
                "n": int(len(v)),
                "n_missing": int(df["value"].isna().sum()),
                "mean": float(v.mean()) if len(v) else None,
                "std": float(v.std()) if len(v) > 1 else 0.0,
                "min": float(v.min()) if len(v) else None,
                "median": float(v.median()) if len(v) else None,
                "max": float(v.max()) if len(v) else None,
            }
            import numpy as np
            if len(v):
                counts, edges = np.histogram(v.to_numpy(), bins=40)
                hist = pd.DataFrame({
                    "bin_left": edges[:-1],
                    "count": counts,
                })
            else:
                hist = pd.DataFrame()

    c1, c2 = st.columns([1, 2])
    with c1:
        st.subheader("Summary")
        if stats:
            st.json(stats)
        else:
            st.write("No data.")
    with c2:
        st.subheader("Histogram")
        if not hist.empty:
            st.bar_chart(hist.set_index("bin_left")["count"])
        else:
            st.write("No data.")


def _selection_from_event(event, level: str) -> dict | None:
    """Parse st.pydeck_chart selection event into a unit id dict."""
    if event is None:
        return None
    try:
        sel = event.selection
    except Exception:
        return None
    if sel is None:
        return None
    # Streamlit 1.39+: selection.objects or selection["objects"]
    objects = None
    if hasattr(sel, "objects"):
        objects = sel.objects
    elif isinstance(sel, dict):
        objects = sel.get("objects")
    if not objects:
        return None
    # objects may be dict of layer -> list
    first = None
    if isinstance(objects, dict):
        for v in objects.values():
            if v:
                first = v[0]
                break
    elif isinstance(objects, list) and objects:
        first = objects[0]
    if not first:
        return None
    props = first.get("properties") if isinstance(first, dict) else None
    if props is None and isinstance(first, dict):
        props = first
    if not isinstance(props, dict):
        return None
    if level == "kreis" and props.get("ags_kreis"):
        return {"ags_kreis": str(props["ags_kreis"]), "name": props.get("name")}
    if level == "gemeinde" and props.get("ags_gem"):
        return {
            "ags_gem": str(props["ags_gem"]),
            "ags_kreis": str(props.get("ags_kreis", "")),
            "name": props.get("name"),
        }
    if level in ("1km", "100m"):
        if "east_ll" in props and "north_ll" in props:
            return {
                "east_ll": int(props["east_ll"]),
                "north_ll": int(props["north_ll"]),
            }
    return None


def _render_profile(sel: dict, unit: dict):
    st.subheader("Unit profile")
    features = _features()
    cols = [f.column for f in features]
    profile = unit_profile(sel["level"], unit, cols)

    # Also pull CVI values at this unit if possible
    cvis = _cvis(_cvi_folder_mtime())
    cvi_rows = []
    for cvi in cvis:
        for cc in cvi.columns:
            df = cvi_agg(
                cvi.path, cc.name, cc.kind, sel["level"],
                kreis=sel.get("kreis"),
            )
            if df.empty:
                continue
            if sel["level"] == "kreis":
                m = df[df["ags_kreis"].astype(str) == str(unit.get("ags_kreis"))]
            elif sel["level"] == "gemeinde":
                m = df[df["ags_gem"].astype(str) == str(unit.get("ags_gem"))]
            else:
                m = df[
                    (df["east_ll"] == unit.get("east_ll"))
                    & (df["north_ll"] == unit.get("north_ll"))
                ]
            if not m.empty:
                cvi_rows.append({
                    "source": f"CVI:{cvi.name}",
                    "column": cc.name,
                    "component": "CVI",
                    "indicator": cc.label,
                    "value": m.iloc[0]["value"],
                })

    rows = []
    for f in features:
        if f.column not in profile:
            continue
        rows.append({
            "source": "feature",
            "column": f.column,
            "block": f.block,
            "component": f.component,
            "indicator": f.indicator,
            "unit": f.unit,
            "value": profile[f.column],
        })
    rows.extend(cvi_rows)
    if not rows:
        st.write("No values for this unit.")
        return
    pdf = pd.DataFrame(rows)
    # Group display by component
    for comp, grp in pdf.groupby(pdf["component"].fillna(""), sort=True):
        st.markdown(f"**{comp or 'Other'}**")
        st.dataframe(
            grp.drop(columns=["component"], errors="ignore"),
            hide_index=True,
            width="stretch",
        )


def main():
    if not _ensure_cache():
        return

    sel = sidebar()
    st.title("FOCAL CVI — feature map explorer")

    feat = sel.get("feature")
    if sel["source"] == "Features" and feat is not None:
        st.caption(
            f"**{feat.indicator or feat.column}** · block `{feat.block}` · "
            f"{feat.component} · {feat.note}"
        )
        if feat.provider or feat.year or feat.native_resolution:
            st.caption(feat.provenance_line)
            with st.expander("Feature metadata"):
                st.json({
                    **feat.provenance_dict(),
                    "column": feat.column,
                    "block": feat.block,
                    "component": feat.component,
                    "indicator": feat.indicator,
                    "unit": feat.unit,
                    "note": feat.note,
                })
    elif sel.get("cvi") is not None:
        cvi = sel["cvi"]
        st.caption(
            f"**{cvi.display}** · `{sel.get('column')}` · "
            f"{cvi.description or cvi.model or 'CVI output'}"
        )

    if not sel.get("column"):
        st.info("Select a feature or CVI column in the sidebar.")
        return
    if sel["level"] == "100m" and not sel.get("kreis"):
        st.info("Choose a Kreis to load 100 m cells.")
        return

    with st.spinner("Loading map data…"):
        df = _load_values(sel)

    if df.empty:
        st.warning("No data for this selection.")
        return

    deck, legend, _view = _build_map(sel, df)
    if deck is None:
        return

    col_map, col_leg = st.columns([5, 1])
    with col_map:
        event = st.pydeck_chart(
            deck,
            width="stretch",
            on_select="rerun",
            selection_mode="single-object",
            key="main_map",
        )
    with col_leg:
        st.markdown("**Legend**")
        _render_legend(legend)

    _render_stats_hist(sel)

    unit = _selection_from_event(event, sel["level"])
    if unit:
        label = unit.get("name") or unit.get("ags_kreis") or unit.get("ags_gem")
        if "east_ll" in unit:
            label = f"N{unit['north_ll']} E{unit['east_ll']}"
        st.markdown(f"### Selected: {label}")
        _render_profile(sel, unit)
    else:
        st.caption("Click a region or cell on the map to open its profile.")


if __name__ == "__main__":
    main()
