"""DuckDB queries for the feature map explorer (cached via Streamlit)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from lib.paths import (
    AGG_1KM,
    AGG_GEMEINDE,
    AGG_KREIS,
    CELL_ADMIN,
    CELLS_100M,
    GEMEINDE_GEOJSON,
    KREIS_GEOJSON,
)


def _mtime(path: Path) -> float:
    return path.stat().st_mtime if path.exists() else 0.0


def _con() -> duckdb.DuckDBPyConnection:
    return duckdb.connect()


@lru_cache(maxsize=8)
def _load_geojson_cached(path_str: str, mtime: float) -> dict:
    return json.loads(Path(path_str).read_text())


def load_kreis_geojson() -> dict:
    return _load_geojson_cached(str(KREIS_GEOJSON), _mtime(KREIS_GEOJSON))


def load_gemeinde_geojson() -> dict:
    return _load_geojson_cached(str(GEMEINDE_GEOJSON), _mtime(GEMEINDE_GEOJSON))


def list_kreise() -> pd.DataFrame:
    """AGS + name for Kreis picker."""
    if not KREIS_GEOJSON.exists():
        return pd.DataFrame(columns=["ags_kreis", "name"])
    gj = load_kreis_geojson()
    rows = []
    for feat in gj.get("features", []):
        props = feat.get("properties") or {}
        rows.append({
            "ags_kreis": str(props.get("ags_kreis", "")),
            "name": str(props.get("name", "")),
        })
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return df.sort_values("name").reset_index(drop=True)


def feature_agg(
    column: str,
    level: str,
    kreis: str | None = None,
) -> pd.DataFrame:
    """
    Return aggregated values for a feature column.

    level: kreis | gemeinde | 1km | 100m
    For 100m, kreis is required.
    """
    if level == "100m":
        if not kreis:
            raise ValueError("100m level requires a Kreis selection")
        return cells_for_kreis(kreis, columns=[column])

    path = {
        "kreis": AGG_KREIS,
        "gemeinde": AGG_GEMEINDE,
        "1km": AGG_1KM,
    }[level]
    if not path.exists():
        return pd.DataFrame()

    n_obs_col = f"{column}__n_obs"
    con = _con()
    cols = [c[0] for c in con.execute(
        f"DESCRIBE SELECT * FROM read_parquet('{path.as_posix()}')"
    ).fetchall()]
    if column not in cols:
        return pd.DataFrame()

    id_cols = {
        "kreis": ["ags_kreis", "n_cells", "pop_sum"],
        "gemeinde": ["ags_gem", "ags_kreis", "n_cells", "pop_sum"],
        "1km": ["east_ll", "north_ll", "lon", "lat", "ags_kreis",
                "n_cells", "pop_sum"],
    }[level]
    select = [c for c in id_cols if c in cols]
    select.append(f'"{column}" AS value')
    if n_obs_col in cols:
        select.append(f'"{n_obs_col}" AS n_obs')

    where = ""
    if kreis and "ags_kreis" in cols:
        where = f"WHERE ags_kreis = '{kreis}'"

    sql = f"""
        SELECT {", ".join(select)}
        FROM read_parquet('{path.as_posix()}')
        {where}
    """
    return con.execute(sql).df()


def cells_for_kreis(
    kreis: str,
    columns: list[str] | None = None,
) -> pd.DataFrame:
    """Load 100 m cells for one Kreis (uses sorted parquet row groups)."""
    if not CELLS_100M.exists():
        return pd.DataFrame()
    con = _con()
    all_cols = [c[0] for c in con.execute(
        f"DESCRIBE SELECT * FROM read_parquet('{CELLS_100M.as_posix()}')"
    ).fetchall()]
    base = ["east_ll", "north_ll", "lon", "lat", "ags_kreis", "ags_gem"]
    if columns:
        feat = [c for c in columns if c in all_cols]
    else:
        feat = []
    select = base + [c for c in feat if c not in base]
    # Rename single feature to value for map layer convenience
    sql_cols = []
    for c in select:
        if columns and len(columns) == 1 and c == columns[0]:
            sql_cols.append(f'"{c}" AS value')
        else:
            sql_cols.append(f'"{c}"')
    sql = f"""
        SELECT {", ".join(sql_cols)}
        FROM read_parquet('{CELLS_100M.as_posix()}')
        WHERE ags_kreis = '{kreis}'
    """
    df = con.execute(sql).df()
    if "value" in df.columns:
        df["n_cells"] = 1
        df["n_obs"] = df["value"].notna().astype(int)
    return df


def feature_histogram(
    column: str,
    level: str,
    kreis: str | None = None,
    bins: int = 40,
) -> pd.DataFrame:
    df = feature_agg(column, level, kreis=kreis)
    if df.empty or "value" not in df.columns:
        return pd.DataFrame(columns=["bin_left", "bin_right", "count"])
    vals = df["value"].dropna()
    if vals.empty:
        return pd.DataFrame(columns=["bin_left", "bin_right", "count"])
    import numpy as np
    counts, edges = np.histogram(vals.to_numpy(), bins=bins)
    return pd.DataFrame({
        "bin_left": edges[:-1],
        "bin_right": edges[1:],
        "count": counts,
    })


def feature_stats(
    column: str,
    level: str,
    kreis: str | None = None,
) -> dict[str, Any]:
    df = feature_agg(column, level, kreis=kreis)
    if df.empty or "value" not in df.columns:
        return {}
    v = df["value"].dropna()
    if v.empty:
        return {"n": 0, "n_missing": int(df["value"].isna().sum())}
    return {
        "n": int(len(v)),
        "n_missing": int(df["value"].isna().sum()),
        "mean": float(v.mean()),
        "std": float(v.std()) if len(v) > 1 else 0.0,
        "min": float(v.min()),
        "p25": float(v.quantile(0.25)),
        "median": float(v.median()),
        "p75": float(v.quantile(0.75)),
        "max": float(v.max()),
    }


def unit_profile(
    level: str,
    unit_id: dict[str, Any],
    columns: list[str],
) -> dict[str, Any]:
    """Return {column: value} for one administrative / grid unit."""
    if not columns:
        return {}
    con = _con()
    if level == "kreis":
        path = AGG_KREIS
        where = f"ags_kreis = '{unit_id['ags_kreis']}'"
    elif level == "gemeinde":
        path = AGG_GEMEINDE
        where = f"ags_gem = '{unit_id['ags_gem']}'"
    elif level == "1km":
        path = AGG_1KM
        where = (
            f"east_ll = {int(unit_id['east_ll'])} "
            f"AND north_ll = {int(unit_id['north_ll'])}"
        )
    elif level == "100m":
        path = CELLS_100M
        where = (
            f"east_ll = {int(unit_id['east_ll'])} "
            f"AND north_ll = {int(unit_id['north_ll'])}"
        )
    else:
        return {}
    if not path.exists():
        return {}
    avail = [c[0] for c in con.execute(
        f"DESCRIBE SELECT * FROM read_parquet('{path.as_posix()}')"
    ).fetchall()]
    cols = [c for c in columns if c in avail]
    if not cols:
        return {}
    sel = ", ".join(f'"{c}"' for c in cols)
    row = con.execute(
        f"SELECT {sel} FROM read_parquet('{path.as_posix()}') WHERE {where} LIMIT 1"
    ).fetchdf()
    if row.empty:
        return {}
    return {c: (None if pd.isna(row.iloc[0][c]) else row.iloc[0][c]) for c in cols}


def cvi_mtime_key(path: Path) -> tuple[str, float]:
    return (str(path), _mtime(path))


@lru_cache(maxsize=32)
def _cvi_agg_cached(
    path_str: str,
    mtime: float,
    column: str,
    kind: str,
    level: str,
    kreis: str | None,
) -> pd.DataFrame:
    path = Path(path_str)
    if not path.exists() or not CELL_ADMIN.exists():
        return pd.DataFrame()
    con = _con()

    if level == "100m":
        if not kreis:
            return pd.DataFrame()
        sql = f"""
            SELECT c.east_ll, c.north_ll,
                   j.lon, j.lat,
                   c.ags_kreis, c.ags_gem,
                   o."{column}" AS value,
                   1 AS n_cells,
                   CASE WHEN o."{column}" IS NULL THEN 0 ELSE 1 END AS n_obs
            FROM read_parquet('{path.as_posix()}') o
            INNER JOIN read_parquet('{CELL_ADMIN.as_posix()}') c
              USING (east_ll, north_ll)
            INNER JOIN (
              SELECT east_ll, north_ll, lon, lat
              FROM read_parquet('{CELLS_100M.as_posix()}')
              WHERE ags_kreis = '{kreis}'
            ) j USING (east_ll, north_ll)
            WHERE c.ags_kreis = '{kreis}'
        """
        return con.execute(sql).df()

    if kind == "categorical":
        # mode via arg_max(count)
        value_expr = f"""
            arg_max(o."{column}", cnt) AS value
        """
        # DuckDB: compute counts in subquery
        if level == "kreis":
            sql = f"""
                WITH joined AS (
                  SELECT c.ags_kreis AS unit_id, o."{column}" AS v
                  FROM read_parquet('{path.as_posix()}') o
                  INNER JOIN read_parquet('{CELL_ADMIN.as_posix()}') c
                    USING (east_ll, north_ll)
                  WHERE c.ags_kreis <> '' AND o."{column}" IS NOT NULL
                ),
                counts AS (
                  SELECT unit_id, v, count(*) AS cnt
                  FROM joined GROUP BY 1, 2
                )
                SELECT unit_id AS ags_kreis,
                       arg_max(v, cnt) AS value,
                       sum(cnt) AS n_obs,
                       sum(cnt) AS n_cells
                FROM counts GROUP BY unit_id
            """
        elif level == "gemeinde":
            sql = f"""
                WITH joined AS (
                  SELECT c.ags_gem AS unit_id, c.ags_kreis, o."{column}" AS v
                  FROM read_parquet('{path.as_posix()}') o
                  INNER JOIN read_parquet('{CELL_ADMIN.as_posix()}') c
                    USING (east_ll, north_ll)
                  WHERE c.ags_gem <> '' AND o."{column}" IS NOT NULL
                ),
                counts AS (
                  SELECT unit_id, any_value(ags_kreis) AS ags_kreis, v, count(*) AS cnt
                  FROM joined GROUP BY 1, 3
                )
                SELECT unit_id AS ags_gem,
                       any_value(ags_kreis) AS ags_kreis,
                       arg_max(v, cnt) AS value,
                       sum(cnt) AS n_obs,
                       sum(cnt) AS n_cells
                FROM counts GROUP BY unit_id
            """
        else:  # 1km
            sql = f"""
                WITH joined AS (
                  SELECT (o.east_ll // 1000) * 1000 AS east_ll,
                         (o.north_ll // 1000) * 1000 AS north_ll,
                         o."{column}" AS v
                  FROM read_parquet('{path.as_posix()}') o
                  WHERE o."{column}" IS NOT NULL
                ),
                counts AS (
                  SELECT east_ll, north_ll, v, count(*) AS cnt
                  FROM joined GROUP BY 1, 2, 3
                )
                SELECT east_ll, north_ll,
                       arg_max(v, cnt) AS value,
                       sum(cnt) AS n_obs,
                       sum(cnt) AS n_cells
                FROM counts GROUP BY 1, 2
            """
    else:
        # continuous — mean
        if level == "kreis":
            sql = f"""
                SELECT c.ags_kreis,
                       avg(o."{column}") AS value,
                       count(o."{column}") AS n_obs,
                       count(*) AS n_cells
                FROM read_parquet('{path.as_posix()}') o
                INNER JOIN read_parquet('{CELL_ADMIN.as_posix()}') c
                  USING (east_ll, north_ll)
                WHERE c.ags_kreis <> ''
                GROUP BY c.ags_kreis
            """
        elif level == "gemeinde":
            sql = f"""
                SELECT c.ags_gem, any_value(c.ags_kreis) AS ags_kreis,
                       avg(o."{column}") AS value,
                       count(o."{column}") AS n_obs,
                       count(*) AS n_cells
                FROM read_parquet('{path.as_posix()}') o
                INNER JOIN read_parquet('{CELL_ADMIN.as_posix()}') c
                  USING (east_ll, north_ll)
                WHERE c.ags_gem <> ''
                GROUP BY c.ags_gem
            """
        else:  # 1km
            sql = f"""
                SELECT (o.east_ll // 1000) * 1000 AS east_ll,
                       (o.north_ll // 1000) * 1000 AS north_ll,
                       avg(o."{column}") AS value,
                       count(o."{column}") AS n_obs,
                       count(*) AS n_cells
                FROM read_parquet('{path.as_posix()}') o
                GROUP BY 1, 2
            """

    df = con.execute(sql).df()
    if kreis and "ags_kreis" in df.columns:
        df = df[df["ags_kreis"] == kreis].reset_index(drop=True)

    # Attach lon/lat for 1km from agg_1km if available
    if level == "1km" and AGG_1KM.exists() and not df.empty:
        coords = con.execute(f"""
            SELECT east_ll, north_ll, lon, lat, ags_kreis
            FROM read_parquet('{AGG_1KM.as_posix()}')
        """).df()
        df = df.merge(coords, on=["east_ll", "north_ll"], how="left")
    return df


def cvi_agg(
    path: Path,
    column: str,
    kind: str,
    level: str,
    kreis: str | None = None,
) -> pd.DataFrame:
    return _cvi_agg_cached(
        str(path), _mtime(path), column, kind, level, kreis,
    )


def join_geojson_values(
    geojson: dict,
    values: pd.DataFrame,
    id_field: str,
    value_col: str = "value",
    fill_colors: list[list[int]] | None = None,
) -> dict:
    """Attach value + fill_color to GeoJSON features by id_field."""
    lookup: dict[str, Any] = {}
    color_lookup: dict[str, list[int]] = {}
    if not values.empty and id_field in values.columns:
        for i, row in values.iterrows():
            key = str(row[id_field])
            lookup[key] = row[value_col] if value_col in values.columns else None
            if fill_colors is not None:
                color_lookup[key] = fill_colors[i]

    out = {"type": "FeatureCollection", "features": []}
    for feat in geojson.get("features", []):
        props = dict(feat.get("properties") or {})
        key = str(props.get(id_field, ""))
        val = lookup.get(key)
        props["value"] = None if val is None or (isinstance(val, float) and pd.isna(val)) else val
        props["fill_color"] = color_lookup.get(key, [180, 180, 180, 80])
        # also stash n_obs if present
        if not values.empty and id_field in values.columns:
            match = values[values[id_field].astype(str) == key]
            if not match.empty:
                if "n_obs" in match.columns:
                    props["n_obs"] = int(match.iloc[0]["n_obs"])
                if "n_cells" in match.columns:
                    props["n_cells"] = int(match.iloc[0]["n_cells"])
        out["features"].append({
            "type": "Feature",
            "geometry": feat.get("geometry"),
            "properties": props,
        })
    return out


def cache_ready() -> bool:
    from lib.paths import FEATURES_JSON
    return (
        CELLS_100M.exists()
        and AGG_KREIS.exists()
        and FEATURES_JSON.exists()
    )
