"""pydeck layers, colour scales, and legend helpers."""

from __future__ import annotations

from typing import Any, Sequence

import numpy as np
import pandas as pd
import pydeck as pdk


# Sequential (low→high) and diverging palettes as RGB tuples
PALETTES = {
    "YlOrRd": [
        (255, 255, 204), (255, 237, 160), (254, 217, 118),
        (254, 178, 76), (253, 141, 60), (252, 78, 42),
        (227, 26, 28), (189, 0, 38), (128, 0, 38),
    ],
    "Viridis": [
        (68, 1, 84), (72, 40, 120), (62, 74, 137),
        (49, 104, 142), (38, 130, 142), (31, 158, 137),
        (53, 183, 121), (110, 206, 88), (181, 222, 43), (253, 231, 37),
    ],
    "Blues": [
        (247, 251, 255), (222, 235, 247), (198, 219, 239),
        (158, 202, 225), (107, 174, 214), (66, 146, 198),
        (33, 113, 181), (8, 81, 156), (8, 48, 107),
    ],
    "RdBu": [
        (5, 48, 97), (33, 102, 172), (67, 147, 195),
        (146, 197, 222), (209, 229, 240), (253, 219, 199),
        (244, 165, 130), (214, 96, 77), (178, 24, 43), (103, 0, 31),
    ],
    "Spectral": [
        (158, 1, 66), (213, 62, 79), (244, 109, 67),
        (253, 174, 97), (254, 224, 139), (230, 245, 152),
        (171, 221, 164), (102, 194, 165), (50, 136, 189), (94, 79, 162),
    ],
}

MISSING_RGBA = (180, 180, 180, 80)


def compute_breaks(
    values: Sequence[float],
    mode: str = "quantile",
    n: int = 7,
    clip_pct: tuple[float, float] = (2.0, 98.0),
    log_scale: bool = False,
) -> list[float]:
    """Return ascending break points (n+1 edges for n classes)."""
    arr = np.asarray(values, dtype=np.float64)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return [0.0, 1.0]
    lo, hi = np.nanpercentile(arr, list(clip_pct))
    if not np.isfinite(lo) or not np.isfinite(hi) or lo == hi:
        lo, hi = float(np.nanmin(arr)), float(np.nanmax(arr))
        if lo == hi:
            return [lo - 0.5, lo + 0.5]
    clipped = arr[(arr >= lo) & (arr <= hi)]
    if clipped.size == 0:
        clipped = arr

    work = clipped
    if log_scale:
        if np.nanmin(work) <= 0:
            work = work[work > 0]
            if work.size == 0:
                log_scale = False
                work = clipped
        if log_scale:
            work = np.log1p(work)

    if mode == "quantile":
        qs = np.linspace(0, 100, n + 1)
        breaks = np.unique(np.nanpercentile(work, qs))
        if breaks.size < 2:
            breaks = np.array([float(work.min()), float(work.max())])
    else:
        breaks = np.linspace(float(work.min()), float(work.max()), n + 1)

    if log_scale:
        breaks = np.expm1(breaks)
    return [float(b) for b in breaks]


def value_to_rgba(
    value: float | None,
    breaks: list[float],
    palette: str = "YlOrRd",
    alpha: int = 180,
) -> list[int]:
    colors = PALETTES.get(palette, PALETTES["YlOrRd"])
    if value is None or not np.isfinite(value):
        return list(MISSING_RGBA)
    # Map into n-1 colour bins from n break edges
    n_bins = max(len(breaks) - 1, 1)
    # Sample palette at bin centres
    idxs = np.linspace(0, len(colors) - 1, n_bins).astype(int)
    bin_i = int(np.searchsorted(breaks, value, side="right") - 1)
    bin_i = max(0, min(n_bins - 1, bin_i))
    r, g, b = colors[idxs[bin_i]]
    return [int(r), int(g), int(b), int(alpha)]


def colorize_series(
    series: pd.Series,
    breaks: list[float],
    palette: str = "YlOrRd",
    alpha: int = 180,
) -> list[list[int]]:
    return [
        value_to_rgba(
            float(v) if pd.notna(v) else None,
            breaks, palette, alpha,
        )
        for v in series
    ]


def legend_rows(
    breaks: list[float],
    palette: str = "YlOrRd",
) -> list[dict[str, Any]]:
    colors = PALETTES.get(palette, PALETTES["YlOrRd"])
    n_bins = max(len(breaks) - 1, 1)
    idxs = np.linspace(0, len(colors) - 1, n_bins).astype(int)
    rows = []
    for i in range(n_bins):
        r, g, b = colors[idxs[i]]
        lo, hi = breaks[i], breaks[i + 1]
        rows.append({
            "color": f"rgb({r},{g},{b})",
            "label": f"{lo:.3g} – {hi:.3g}",
        })
    return rows


def make_geojson_layer(
    geojson: dict,
    value_col: str = "value",
    pickable: bool = True,
) -> pdk.Layer:
    return pdk.Layer(
        "GeoJsonLayer",
        data=geojson,
        opacity=0.75,
        stroked=True,
        filled=True,
        get_fill_color="properties.fill_color",
        get_line_color=[80, 80, 80, 160],
        line_width_min_pixels=0.5,
        pickable=pickable,
        auto_highlight=True,
    )


def make_grid_cell_layer(
    df: pd.DataFrame,
    cell_size: float = 100.0,
    elevation_scale: float = 0.0,
) -> pdk.Layer:
    """GridCellLayer at lon/lat centres. cell_size in metres (approx)."""
    return pdk.Layer(
        "GridCellLayer",
        data=df,
        get_position=["lon", "lat"],
        get_fill_color="fill_color",
        get_elevation=elevation_scale,
        cell_size=cell_size,
        elevation_scale=1,
        extruded=False,
        pickable=True,
        auto_highlight=True,
        opacity=0.85,
    )


def make_view(
    lon: float = 10.4,
    lat: float = 51.2,
    zoom: float = 5.5,
    pitch: float = 0,
) -> pdk.ViewState:
    return pdk.ViewState(
        longitude=lon,
        latitude=lat,
        zoom=zoom,
        pitch=pitch,
        bearing=0,
    )


def bounds_center(df: pd.DataFrame) -> tuple[float, float, float]:
    """Return (lon, lat, zoom) fitting lon/lat columns."""
    if df.empty or "lon" not in df.columns:
        return 10.4, 51.2, 5.5
    lon0, lon1 = float(df["lon"].min()), float(df["lon"].max())
    lat0, lat1 = float(df["lat"].min()), float(df["lat"].max())
    lon_c = 0.5 * (lon0 + lon1)
    lat_c = 0.5 * (lat0 + lat1)
    span = max(lon1 - lon0, lat1 - lat0, 0.05)
    # rough zoom from span
    if span > 8:
        zoom = 5.5
    elif span > 3:
        zoom = 7.0
    elif span > 1:
        zoom = 8.5
    elif span > 0.3:
        zoom = 10.0
    else:
        zoom = 11.5
    return lon_c, lat_c, zoom
