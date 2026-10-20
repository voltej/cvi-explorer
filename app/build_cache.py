#!/usr/bin/env python3
"""
build_cache.py
==============
One-off cache builder for the FOCAL CVI feature map explorer.

Writes to data/app_cache/:
  cells_100m.parquet   — wide raw-feature table sorted by ags_kreis
  agg_kreis.parquet    — Kreis-level means
  agg_gemeinde.parquet — Gemeinde-level means
  agg_1km.parquet      — 1 km aggregation
  kreis.geojson / gemeinde.geojson — simplified WGS84 boundaries
  features.json        — feature catalogue (with provenance)
  sources.json         — data-source cards + feature lists

Usage
-----
  python app/build_cache.py all
  python app/build_cache.py cells
  python app/build_cache.py aggregates
  python app/build_cache.py boundaries
  python app/build_cache.py features
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "app"))
sys.path.insert(0, str(REPO / "experiments"))

from lib.paths import (  # noqa: E402
    ADMIN_ON_GRID,
    AGG_1KM,
    AGG_GEMEINDE,
    AGG_KREIS,
    APP_CACHE,
    CELL_ADMIN,
    CELLS_100M,
    FEATURES_CSV,
    FEATURES_JSON,
    GEMEINDE_GEOJSON,
    HAZARD_PARQUET,
    JOINT_PARQUET,
    KREIS_GEOJSON,
    LAYERS_ZARR,
    SOURCES_JSON,
    VG250_GEMEINDE,
    VG250_KREIS,
)
from lib.provenance import resolve_feature, source_cards  # noqa: E402
from cvi_grid import HEIGHT, WIDTH, ll_to_rowcol  # noqa: E402

PROVENANCE_KEYS = (
    "source_id", "provider", "product", "year", "native_resolution",
    "grid_resolution", "crs", "license", "resampling", "inventory_id", "url",
)


def _attach_provenance(entry: dict) -> None:
    prov = resolve_feature(entry["column"], entry.get("block", ""))
    for k in PROVENANCE_KEYS:
        entry[k] = prov.get(k, "")

STRIP_H = 1024

# (out_column, zarr_layer, nodata, block, component, indicator, unit, note)
ZARR_FEATURES = [
    ("grid__population_jrc_estat_2021", "population_jrc_estat_2021", -1.0,
     "grid", "Exposure", "Population density", "count",
     "E02 JRC/Eurostat 100 m pop grid 2021"),
    ("grid__a06_health_count", "a06_health_count", None,
     "grid", "Adaptive capacity", "Medical infrastructure", "count",
     "OSM health amenity count (ODbL)"),
    ("grid__a06_health_dist_m", "a06_health_dist_m", None,
     "grid", "Adaptive capacity", "Medical infrastructure", "m",
     "OSM distance to nearest health amenity"),
    ("grid__a07_cooling_count", "a07_cooling_count", None,
     "grid", "Adaptive capacity", "Proximity to cooling", "count",
     "OSM cooling amenity count (ODbL)"),
    ("grid__a07_cooling_dist_m", "a07_cooling_dist_m", None,
     "grid", "Adaptive capacity", "Proximity to cooling", "m",
     "OSM distance to nearest cooling amenity"),
    ("grid__a07_green_presence", "a07_green_presence", None,
     "grid", "Adaptive capacity", "Proximity to green", "0/1",
     "OSM green-space presence"),
    ("grid__a07_water_presence", "a07_water_presence", None,
     "grid", "Adaptive capacity", "Proximity to water", "0/1",
     "OSM water-body presence"),
    ("clms__imperviousness_density", "imperviousness_density", 255.0,
     "clms", "Exposure", "Surface imperviousness", "percent",
     "E03 Copernicus HRL IMD"),
    ("clms__tree_cover_density", "tree_cover_density", 255.0,
     "clms", "Adaptive capacity", "Proximity to green/cooling", "percent",
     "A08 Copernicus HRL TCD"),
    ("lst__summer_p90", "lst_summer_p90", -9999.0,
     "lst", "Exposure", "Surface temperature", "degree_C",
     "E04 Landsat 8/9 C2 L2 LST JJA p90"),
]

HAZARD_META = {
    "hyras__heatwave_days_3d__mean": ("Hazard", "Heatwave days (3d)", "days"),
    "hyras__hot_days__mean": ("Hazard", "Hot days", "days"),
    "hyras__r10mm__mean": ("Hazard", "Heavy precip days ≥10 mm", "days"),
    "hyras__r20mm__mean": ("Hazard", "Heavy precip days ≥20 mm", "days"),
    "hyras__r95ptot__mean": ("Hazard", "R95pTOT", "mm"),
    "hyras__rx1day__mean": ("Hazard", "Rx1day", "mm"),
    "hyras__rx5day__mean": ("Hazard", "Rx5day", "mm"),
    "hyras__summer_days__mean": ("Hazard", "Summer days", "days"),
    "hyras__tasmax_p99__mean": ("Hazard", "Tasmax p99", "degree_C"),
    "hyras__tropical_nights__mean": ("Hazard", "Tropical nights", "days"),
    "hyras__tx90p__mean": ("Hazard", "TX90p", "percent"),
    "hyras__wsdi__mean": ("Hazard", "WSDI", "days"),
}

KEY_COLS = {"east_ll", "north_ll", "x_3035", "y_3035", "lon", "lat",
            "gitter_id", "ags_kreis", "ags_gem"}
SKIP_FROM_JOINT = {"x_3035", "y_3035", "gitter_id"}


def _gather_zarr(layer_names: list[str], row, col):
    import numpy as np
    import zarr

    root = zarr.open_group(str(LAYERS_ZARR), mode="r")
    n = int(row.shape[0])
    out = {name: np.empty(n, dtype=np.float32) for name in layer_names}
    n_strips = (HEIGHT + STRIP_H - 1) // STRIP_H
    for s in range(n_strips):
        y0 = s * STRIP_H
        y1 = min(y0 + STRIP_H, HEIGHT)
        in_strip = (row >= y0) & (row < y1)
        n_in = int(in_strip.sum())
        if n_in == 0:
            continue
        local_row = row[in_strip] - y0
        local_col = col[in_strip]
        for name in layer_names:
            block = np.asarray(root[name][y0:y1, :], dtype=np.float32)
            out[name][in_strip] = block[local_row, local_col]
        print(f"  zarr strip {s + 1:02d}/{n_strips} rows[{y0}:{y1}] cells={n_in:,}")
    return out


def _apply_nodata(raw, nodata):
    import numpy as np

    v = np.asarray(raw, dtype=np.float32)
    if nodata is None:
        m = np.isfinite(v)
    else:
        m = np.isfinite(v) & (v != nodata)
    out = v.copy()
    out[~m] = np.nan
    return out


def cmd_cells() -> None:
    import duckdb
    import numpy as np
    import pandas as pd
    import pyarrow as pa
    import pyarrow.parquet as pq

    assert JOINT_PARQUET.exists(), f"missing {JOINT_PARQUET}"
    assert CELL_ADMIN.exists(), f"missing {CELL_ADMIN}"
    APP_CACHE.mkdir(parents=True, exist_ok=True)

    print("Loading joint keys + census/aef …")
    con = duckdb.connect()
    joint = con.execute(
        f"SELECT * FROM read_parquet('{JOINT_PARQUET.as_posix()}')"
    ).df()
    n = len(joint)
    print(f"  joint rows={n:,}")

    print("Joining cell_admin …")
    admin_map = con.execute(f"""
        SELECT east_ll, north_ll, ags_kreis, ags_gem
        FROM read_parquet('{CELL_ADMIN.as_posix()}')
    """).df()
    joint = joint.merge(admin_map, on=["east_ll", "north_ll"], how="left")
    print(f"  with ags_kreis: {joint['ags_kreis'].notna().mean():.3f}")

    if HAZARD_PARQUET.exists():
        print("Joining hazard …")
        haz = con.execute(
            f"SELECT * FROM read_parquet('{HAZARD_PARQUET.as_posix()}')"
        ).df()
        drop = [c for c in haz.columns if c in joint.columns and c not in
                ("east_ll", "north_ll")]
        haz = haz.drop(columns=drop, errors="ignore")
        joint = joint.merge(haz, on=["east_ll", "north_ll"], how="left")
        print(f"  hazard cols: {[c for c in haz.columns if c.startswith('hyras')]}")
    else:
        print(f"  skip hazard (missing {HAZARD_PARQUET})")

    if ADMIN_ON_GRID.exists():
        print("Joining admin_on_grid …")
        adm = con.execute(
            f"SELECT * FROM read_parquet('{ADMIN_ON_GRID.as_posix()}')"
        ).df()
        value_cols = [c for c in adm.columns
                      if c not in ("east_ll", "north_ll", "gitter_id")]
        rename = {
            c: (c if c.startswith("admin__") else f"admin__{c}")
            for c in value_cols
        }
        adm = adm[["east_ll", "north_ll"] + value_cols].rename(columns=rename)
        joint = joint.merge(adm, on=["east_ll", "north_ll"], how="left")
        print(f"  admin cols: {list(rename.values())}")
    else:
        print(f"  skip admin (missing {ADMIN_ON_GRID})")

    # Drop unused coord helpers from the wide table (keep lon/lat/keys)
    for c in list(SKIP_FROM_JOINT):
        if c in joint.columns:
            joint.drop(columns=[c], inplace=True)

    if LAYERS_ZARR.exists():
        print("Gathering zarr layers …")
        east = joint["east_ll"].to_numpy(np.int32)
        north = joint["north_ll"].to_numpy(np.int32)
        row, col = ll_to_rowcol(east, north)
        ok = (row >= 0) & (row < HEIGHT) & (col >= 0) & (col < WIDTH)
        if not bool(ok.all()):
            print(f"  WARNING: {int((~ok).sum())} keys outside grid — NaN filled")
        present = []
        import zarr
        root = zarr.open_group(str(LAYERS_ZARR), mode="r")
        for out_col, layer, nodata, *_ in ZARR_FEATURES:
            if layer in root:
                present.append((out_col, layer, nodata))
            else:
                print(f"  skip missing zarr layer {layer}")
        if present:
            gathered = _gather_zarr([p[1] for p in present], row, col)
            for out_col, layer, nodata in present:
                vals = _apply_nodata(gathered[layer], nodata)
                vals[~ok] = np.nan
                joint[out_col] = vals
                obs = float(np.isfinite(vals).mean())
                print(f"  {out_col}: observed={obs:.3f}")
    else:
        print(f"  skip zarr (missing {LAYERS_ZARR})")

    print("Sorting by ags_kreis …")
    joint["ags_kreis"] = joint["ags_kreis"].fillna("")
    joint["ags_gem"] = joint["ags_gem"].fillna("")
    joint = joint.sort_values(["ags_kreis", "ags_gem", "east_ll", "north_ll"],
                              kind="mergesort").reset_index(drop=True)

    # Prefer float32 for numeric feature cols to keep file size down
    for c in joint.columns:
        if c in KEY_COLS or c in ("ags_kreis", "ags_gem"):
            continue
        if pd.api.types.is_float_dtype(joint[c]):
            joint[c] = joint[c].astype(np.float32)
        elif pd.api.types.is_integer_dtype(joint[c]) and c not in (
            "east_ll", "north_ll",
        ):
            # keep integers that fit; aef int8 stays
            pass

    print(f"Writing {CELLS_100M} …")
    table = pa.Table.from_pandas(joint, preserve_index=False)
    # Row groups ~100k for Kreis-filtered reads
    pq.write_table(
        table,
        CELLS_100M,
        compression="zstd",
        row_group_size=100_000,
    )
    print(f"  rows={len(joint):,}  cols={len(joint.columns)}  "
          f"size={CELLS_100M.stat().st_size / 1e9:.2f} GB")


def _feature_columns(con) -> list[str]:
    cols = [c[0] for c in con.execute(
        f"DESCRIBE SELECT * FROM read_parquet('{CELLS_100M.as_posix()}')"
    ).fetchall()]
    skip = KEY_COLS | {"ags_kreis", "ags_gem"}
    return [c for c in cols if c not in skip]


def _agg_sql(group_expr: str, group_alias: str, feature_cols: list[str],
             extra_select: str = "") -> str:
    """Build DuckDB aggregation SQL for mean / n_obs / pop_sum."""
    pop_candidates = [
        "grid__population_jrc_estat_2021",
        "censA__bevoelkerung__Einwohner",
    ]
    # Detect which pop col exists later; placeholder resolved by caller
    mean_parts = []
    for c in feature_cols:
        mean_parts.append(
            f"avg({c}) FILTER (WHERE {c} IS NOT NULL) AS \"{c}\""
        )
        mean_parts.append(
            f"count({c}) AS \"{c}__n_obs\""
        )
    pop_expr = "NULL"
    for p in pop_candidates:
        if p in feature_cols:
            pop_expr = f"sum(COALESCE({p}, 0))"
            break
    select_bits = [
        f"{group_expr} AS {group_alias}",
        "count(*) AS n_cells",
        f"{pop_expr} AS pop_sum",
        *mean_parts,
    ]
    if extra_select:
        select_bits.insert(1, extra_select)
    return ",\n      ".join(select_bits)


def cmd_aggregates() -> None:
    import duckdb

    assert CELLS_100M.exists(), f"missing {CELLS_100M} — run cells first"
    APP_CACHE.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    feature_cols = _feature_columns(con)
    print(f"Aggregating {len(feature_cols)} features …")

    # Kreis
    print(f"Writing {AGG_KREIS} …")
    sel = _agg_sql("ags_kreis", "ags_kreis", feature_cols)
    con.execute(f"""
        COPY (
          SELECT {sel}
          FROM read_parquet('{CELLS_100M.as_posix()}')
          WHERE ags_kreis <> ''
          GROUP BY ags_kreis
        ) TO '{AGG_KREIS.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)
    n = con.execute(
        f"SELECT count(*) FROM read_parquet('{AGG_KREIS.as_posix()}')"
    ).fetchone()[0]
    print(f"  kreis units={n:,}")

    # Gemeinde
    print(f"Writing {AGG_GEMEINDE} …")
    sel = _agg_sql(
        "ags_gem", "ags_gem", feature_cols,
        extra_select="any_value(ags_kreis) AS ags_kreis",
    )
    con.execute(f"""
        COPY (
          SELECT {sel}
          FROM read_parquet('{CELLS_100M.as_posix()}')
          WHERE ags_gem <> ''
          GROUP BY ags_gem
        ) TO '{AGG_GEMEINDE.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)
    n = con.execute(
        f"SELECT count(*) FROM read_parquet('{AGG_GEMEINDE.as_posix()}')"
    ).fetchone()[0]
    print(f"  gemeinde units={n:,}")

    # 1 km
    print(f"Writing {AGG_1KM} …")
    # Cell-centre lon/lat for the SW corner of the 1 km block + 500 m
    mean_parts = []
    for c in feature_cols:
        mean_parts.append(
            f"avg({c}) FILTER (WHERE {c} IS NOT NULL) AS \"{c}\""
        )
        mean_parts.append(f"count({c}) AS \"{c}__n_obs\"")
    pop_expr = "NULL"
    for p in ("grid__population_jrc_estat_2021",
              "censA__bevoelkerung__Einwohner"):
        if p in feature_cols:
            pop_expr = f"sum(COALESCE({p}, 0))"
            break
    con.execute(f"""
        COPY (
          SELECT
            (east_ll // 1000) * 1000 AS east_ll,
            (north_ll // 1000) * 1000 AS north_ll,
            avg(lon) AS lon,
            avg(lat) AS lat,
            any_value(ags_kreis) AS ags_kreis,
            count(*) AS n_cells,
            {pop_expr} AS pop_sum,
            {", ".join(mean_parts)}
          FROM read_parquet('{CELLS_100M.as_posix()}')
          GROUP BY 1, 2
        ) TO '{AGG_1KM.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)
    n = con.execute(
        f"SELECT count(*) FROM read_parquet('{AGG_1KM.as_posix()}')"
    ).fetchone()[0]
    print(f"  1km cells={n:,}")


def cmd_boundaries() -> None:
    import geopandas as gpd

    APP_CACHE.mkdir(parents=True, exist_ok=True)

    if VG250_KREIS.exists():
        print(f"Writing {KREIS_GEOJSON} …")
        gdf = gpd.read_parquet(VG250_KREIS)
        # Keep inhabited land (GF=4) if present
        if "GF" in gdf.columns:
            gdf = gdf[gdf["GF"] == 4].copy()
        keep = [c for c in ("AGS", "GEN", "BEZ", "NUTS") if c in gdf.columns]
        gdf = gdf[keep + ["geometry"]].copy()
        gdf = gdf.rename(columns={"AGS": "ags_kreis", "GEN": "name",
                                  "BEZ": "bez", "NUTS": "nuts"})
        gdf["geometry"] = gdf.geometry.simplify(200, preserve_topology=True)
        gdf = gdf.to_crs(epsg=4326)
        gdf.to_file(KREIS_GEOJSON, driver="GeoJSON")
        print(f"  features={len(gdf)}")
    else:
        print(f"  skip kreis (missing {VG250_KREIS})")

    if VG250_GEMEINDE.exists():
        print(f"Writing {GEMEINDE_GEOJSON} …")
        gdf = gpd.read_parquet(VG250_GEMEINDE)
        if "GF" in gdf.columns:
            gdf = gdf[gdf["GF"] == 4].copy()
        keep = [c for c in ("AGS", "GEN", "BEZ", "NUTS") if c in gdf.columns]
        gdf = gdf[keep + ["geometry"]].copy()
        gdf = gdf.rename(columns={"AGS": "ags_gem", "GEN": "name",
                                  "BEZ": "bez", "NUTS": "nuts"})
        # Derive kreis AGS (first 5 digits of gemeinde AGS)
        gdf["ags_kreis"] = gdf["ags_gem"].astype(str).str[:5]
        gdf["geometry"] = gdf.geometry.simplify(50, preserve_topology=True)
        gdf = gdf.to_crs(epsg=4326)
        gdf.to_file(GEMEINDE_GEOJSON, driver="GeoJSON")
        print(f"  features={len(gdf)}")
    else:
        print(f"  skip gemeinde (missing {VG250_GEMEINDE})")


def cmd_features() -> None:
    import duckdb
    import pandas as pd

    APP_CACHE.mkdir(parents=True, exist_ok=True)
    entries: list[dict] = []
    seen: set[str] = set()

    if FEATURES_CSV.exists():
        df = pd.read_csv(FEATURES_CSV)
        for _, r in df.iterrows():
            col = str(r["column"])
            block = str(r.get("block", "") or "")
            if block == "coord":
                continue
            # Skip SAE-transformed grid names; we store raw zarr cols instead
            if col.startswith("grid__") and col.endswith("__log1p"):
                continue
            if col.startswith("admin__"):
                # will be filled from cells if present
                pass
            entry = {
                "column": col,
                "block": block,
                "component": str(r.get("cvi_component", "") or ""),
                "indicator": str(r.get("table4_indicator", "") or ""),
                "unit": str(r.get("unit", "") or ""),
                "source": str(r.get("source_field", "") or ""),
                "note": str(r.get("note", "") or ""),
            }
            entries.append(entry)
            seen.add(col)

    # Zarr raw features (prefer these over SAE-named grid__*__log1p)
    for out_col, layer, _nd, block, component, indicator, unit, note in ZARR_FEATURES:
        if out_col in seen:
            continue
        entries.append({
            "column": out_col,
            "block": block,
            "component": component,
            "indicator": indicator,
            "unit": unit,
            "source": layer,
            "note": note,
        })
        seen.add(out_col)

    # Hazard
    for col, (component, indicator, unit) in HAZARD_META.items():
        if col in seen:
            continue
        entries.append({
            "column": col,
            "block": "hazard",
            "component": component,
            "indicator": indicator,
            "unit": unit,
            "source": col,
            "note": "HYRAS indices (framework slot HAZ)",
        })
        seen.add(col)

    # Admin columns present in cells but missing from CSV
    if CELLS_100M.exists():
        con = duckdb.connect()
        cols = [c[0] for c in con.execute(
            f"DESCRIBE SELECT * FROM read_parquet('{CELLS_100M.as_posix()}')"
        ).fetchall()]
        for c in cols:
            if c in seen or c in KEY_COLS or c in ("ags_kreis", "ags_gem"):
                continue
            if c.startswith("admin__"):
                entries.append({
                    "column": c,
                    "block": "admin",
                    "component": "Sensitivity",
                    "indicator": "Admin indicator",
                    "unit": "mixed",
                    "source": c.replace("admin__", "", 1),
                    "note": "Dasymetric disaggregation; predictor role",
                })
                seen.add(c)
            elif c.startswith("hyras__") and c not in seen:
                entries.append({
                    "column": c,
                    "block": "hazard",
                    "component": "Hazard",
                    "indicator": c,
                    "unit": "",
                    "source": c,
                    "note": "HYRAS",
                })
                seen.add(c)

        # Restrict catalogue to columns that actually exist in cells
        present = set(cols)
        entries = [e for e in entries if e["column"] in present]

        # Coverage stats
        for e in entries:
            col = e["column"]
            row = con.execute(f"""
                SELECT
                  count({col}) AS n_obs,
                  count(*) AS n,
                  avg({col}) AS mean,
                  min({col}) AS min,
                  max({col}) AS max
                FROM read_parquet('{CELLS_100M.as_posix()}')
            """).fetchone()
            e["n_obs"] = int(row[0])
            e["n_cells"] = int(row[1])
            e["observed_frac"] = float(row[0] / row[1]) if row[1] else 0.0
            e["mean"] = float(row[2]) if row[2] is not None else None
            e["min"] = float(row[3]) if row[3] is not None else None
            e["max"] = float(row[4]) if row[4] is not None else None

    for e in entries:
        _attach_provenance(e)

    FEATURES_JSON.write_text(json.dumps(entries, indent=2))
    print(f"Wrote {FEATURES_JSON}  features={len(entries)}")

    # Source cards + which features belong to each source
    by_source: dict[str, list[str]] = {}
    for e in entries:
        sid = e.get("source_id") or "unknown"
        by_source.setdefault(sid, []).append(e["column"])
    cards = []
    for card in source_cards():
        cols = by_source.get(card["id"], [])
        card["feature_count"] = len(cols)
        card["columns"] = cols
        cards.append(card)
    # Any leftover source_ids not in the ordered cards
    known = {c["id"] for c in cards}
    for sid, cols in sorted(by_source.items()):
        if sid in known:
            continue
        cards.append({
            "id": sid,
            "title": sid,
            "provider": "",
            "inventory_id": "",
            "year": "",
            "native_resolution": "",
            "grid_resolution": "100 m",
            "crs": "EPSG:3035",
            "license": "",
            "resampling": "",
            "coverage": "",
            "description": "",
            "url": "",
            "product": sid,
            "feature_count": len(cols),
            "columns": cols,
        })
    SOURCES_JSON.write_text(json.dumps(cards, indent=2))
    print(f"Wrote {SOURCES_JSON}  sources={len(cards)}")


def cmd_all() -> None:
    cmd_cells()
    cmd_aggregates()
    cmd_boundaries()
    cmd_features()
    print("\nCache build complete.")


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "cmd",
        choices=["all", "cells", "aggregates", "boundaries", "features"],
        help="Which cache stage to run",
    )
    a = p.parse_args(argv)
    {
        "all": cmd_all,
        "cells": cmd_cells,
        "aggregates": cmd_aggregates,
        "boundaries": cmd_boundaries,
        "features": cmd_features,
    }[a.cmd]()


if __name__ == "__main__":
    main()
