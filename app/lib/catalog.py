"""
Feature catalogue and CVI drop-in discovery.

CVI drop-in contract
--------------------
Place outputs in ``data/cvi_outputs/<name>.parquet`` with columns:

* ``east_ll``, ``north_ll`` — int, canonical 100 m SW-corner keys (EPSG:3035)
* one or more score columns

Numeric columns are treated as continuous. Integer or string columns with
≤50 distinct values are treated as categorical (e.g. cluster / latent IDs).

Optional ``<name>.meta.json``::

    {
      "label": "My CVI v1",
      "description": "...",
      "model": "topk_sae",
      "matrix_version": "v1",
      "created_at": "2026-10-20",
      "higher_is_worse": true,
      "columns": {
        "cvi_score": {"label": "CVI", "unit": "z", "kind": "continuous"}
      }
    }

The app rescans the folder on each run; no cache rebuild is required.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from lib.paths import CVI_OUTPUTS, FEATURES_JSON, SOURCES_JSON
from lib.provenance import provenance_caption


@dataclass
class Feature:
    column: str
    block: str = ""
    component: str = ""
    indicator: str = ""
    unit: str = ""
    source: str = ""
    note: str = ""
    n_obs: int = 0
    n_cells: int = 0
    observed_frac: float = 0.0
    mean: float | None = None
    min: float | None = None
    max: float | None = None
    # Provenance
    source_id: str = ""
    provider: str = ""
    product: str = ""
    year: str = ""
    native_resolution: str = ""
    grid_resolution: str = "100 m"
    crs: str = "EPSG:3035"
    license: str = ""
    resampling: str = ""
    inventory_id: str = ""
    url: str = ""

    @property
    def label(self) -> str:
        ind = self.indicator or self.column
        unit = f" ({self.unit})" if self.unit else ""
        return f"{ind}: {self.column}{unit}"

    @property
    def provenance_line(self) -> str:
        return provenance_caption({
            "provider": self.provider,
            "product": self.product,
            "year": self.year,
            "native_resolution": self.native_resolution,
            "grid_resolution": self.grid_resolution,
            "license": self.license,
        })

    def provenance_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "provider": self.provider,
            "product": self.product,
            "year": self.year,
            "native_resolution": self.native_resolution,
            "grid_resolution": self.grid_resolution,
            "crs": self.crs,
            "license": self.license,
            "resampling": self.resampling,
            "inventory_id": self.inventory_id,
            "url": self.url,
        }


@dataclass
class DataSource:
    id: str
    title: str = ""
    provider: str = ""
    inventory_id: str = ""
    year: str = ""
    native_resolution: str = ""
    grid_resolution: str = "100 m"
    crs: str = "EPSG:3035"
    license: str = ""
    resampling: str = ""
    coverage: str = ""
    description: str = ""
    url: str = ""
    product: str = ""
    feature_count: int = 0
    columns: list[str] = field(default_factory=list)


@dataclass
class CVIColumn:
    name: str
    label: str = ""
    unit: str = ""
    kind: str = "continuous"  # continuous | categorical

    @property
    def display(self) -> str:
        lab = self.label or self.name
        unit = f" ({self.unit})" if self.unit else ""
        return f"{lab}: {self.name}{unit}"


@dataclass
class CVIOutput:
    name: str
    path: Path
    label: str = ""
    description: str = ""
    model: str = ""
    matrix_version: str = ""
    created_at: str = ""
    higher_is_worse: bool = True
    columns: list[CVIColumn] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def display(self) -> str:
        return self.label or self.name


def load_features_from_rows(raw: list[dict[str, Any]]) -> list[Feature]:
    """Build Feature objects from JSON rows (safe after Streamlit cache)."""
    out: list[Feature] = []
    for r in raw:
        out.append(Feature(
            column=r["column"],
            block=r.get("block", "") or "",
            component=r.get("component", "") or "",
            indicator=r.get("indicator", "") or "",
            unit=r.get("unit", "") or "",
            source=r.get("source", "") or "",
            note=r.get("note", "") or "",
            n_obs=int(r.get("n_obs") or 0),
            n_cells=int(r.get("n_cells") or 0),
            observed_frac=float(r.get("observed_frac") or 0.0),
            mean=r.get("mean"),
            min=r.get("min"),
            max=r.get("max"),
            source_id=str(r.get("source_id") or ""),
            provider=str(r.get("provider") or ""),
            product=str(r.get("product") or ""),
            year=str(r.get("year") or ""),
            native_resolution=str(r.get("native_resolution") or ""),
            grid_resolution=str(r.get("grid_resolution") or "100 m"),
            crs=str(r.get("crs") or "EPSG:3035"),
            license=str(r.get("license") or ""),
            resampling=str(r.get("resampling") or ""),
            inventory_id=str(r.get("inventory_id") or ""),
            url=str(r.get("url") or ""),
        ))
    return out


def load_features(path: Path | None = None) -> list[Feature]:
    p = path or FEATURES_JSON
    if not p.exists():
        return []
    return load_features_from_rows(json.loads(p.read_text()))


def load_sources(path: Path | None = None) -> list[DataSource]:
    p = path or SOURCES_JSON
    if not p.exists():
        return []
    raw = json.loads(p.read_text())
    out: list[DataSource] = []
    for r in raw:
        out.append(DataSource(
            id=str(r.get("id") or ""),
            title=str(r.get("title") or ""),
            provider=str(r.get("provider") or ""),
            inventory_id=str(r.get("inventory_id") or ""),
            year=str(r.get("year") or ""),
            native_resolution=str(r.get("native_resolution") or ""),
            grid_resolution=str(r.get("grid_resolution") or "100 m"),
            crs=str(r.get("crs") or "EPSG:3035"),
            license=str(r.get("license") or ""),
            resampling=str(r.get("resampling") or ""),
            coverage=str(r.get("coverage") or ""),
            description=str(r.get("description") or ""),
            url=str(r.get("url") or ""),
            product=str(r.get("product") or ""),
            feature_count=int(r.get("feature_count") or 0),
            columns=list(r.get("columns") or []),
        ))
    return out


def feature_blocks(features: list[Feature]) -> list[str]:
    order = ["aef", "censA", "censB", "grid", "clms", "lst", "hazard", "admin"]
    present = {f.block for f in features if f.block}
    return [b for b in order if b in present] + sorted(present - set(order))


def feature_components(features: list[Feature]) -> list[str]:
    comps = sorted({f.component for f in features if f.component})
    return comps


def filter_features(
    features: list[Feature],
    blocks: list[str] | None = None,
    components: list[str] | None = None,
) -> list[Feature]:
    out = features
    if blocks:
        out = [f for f in out if f.block in blocks]
    if components:
        out = [f for f in out if f.component in components]
    return out


def _infer_kind(con, path: Path, col: str, declared: str | None) -> str:
    if declared in ("continuous", "categorical"):
        return declared
    import duckdb  # noqa: F401 — con is duckdb connection

    info = con.execute(f"""
        SELECT
          typeof("{col}") AS t,
          count(DISTINCT "{col}") AS nuniq,
          count("{col}") AS nobs
        FROM read_parquet('{path.as_posix()}')
    """).fetchone()
    dtype = str(info[0]).lower()
    nuniq = int(info[1] or 0)
    if "varchar" in dtype or "string" in dtype:
        return "categorical"
    if ("int" in dtype or "utinyint" in dtype or "usmallint" in dtype) and nuniq <= 50:
        return "categorical"
    if nuniq <= 50 and nuniq > 0 and nuniq <= max(2, int(0.01 * (info[2] or 1))):
        # sparse discrete — still prefer continuous for floats
        if "float" in dtype or "double" in dtype or "decimal" in dtype:
            return "continuous"
        return "categorical"
    return "continuous"


def discover_cvi_outputs(folder: Path | None = None) -> list[CVIOutput]:
    """Scan data/cvi_outputs/ for parquet + optional meta.json."""
    import duckdb

    root = folder or CVI_OUTPUTS
    root.mkdir(parents=True, exist_ok=True)
    results: list[CVIOutput] = []
    con = duckdb.connect()

    for pq_path in sorted(root.glob("*.parquet")):
        name = pq_path.stem
        meta_path = pq_path.with_suffix(".meta.json")
        meta: dict[str, Any] = {}
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text())
            except json.JSONDecodeError:
                meta = {}

        try:
            cols = [c[0] for c in con.execute(
                f"DESCRIBE SELECT * FROM read_parquet('{pq_path.as_posix()}')"
            ).fetchall()]
        except Exception:
            continue
        if "east_ll" not in cols or "north_ll" not in cols:
            continue
        score_cols = [c for c in cols if c not in ("east_ll", "north_ll", "gitter_id")]
        if not score_cols:
            continue

        col_meta = meta.get("columns") or {}
        cvi_cols: list[CVIColumn] = []
        for c in score_cols:
            cm = col_meta.get(c) or {}
            kind = _infer_kind(con, pq_path, c, cm.get("kind"))
            cvi_cols.append(CVIColumn(
                name=c,
                label=str(cm.get("label") or c),
                unit=str(cm.get("unit") or ""),
                kind=kind,
            ))

        results.append(CVIOutput(
            name=name,
            path=pq_path,
            label=str(meta.get("label") or name),
            description=str(meta.get("description") or ""),
            model=str(meta.get("model") or ""),
            matrix_version=str(meta.get("matrix_version") or ""),
            created_at=str(meta.get("created_at") or ""),
            higher_is_worse=bool(meta.get("higher_is_worse", True)),
            columns=cvi_cols,
            meta=meta,
        ))
    return results


CVI_CONTRACT_HELP = """
**CVI drop-in contract**

1. Write a Parquet to `data/cvi_outputs/<name>.parquet` with columns:
   - `east_ll`, `north_ll` (int, canonical 100 m SW-corner keys)
   - one or more score columns
2. Optional `data/cvi_outputs/<name>.meta.json` with label, description,
   model, matrix_version, higher_is_worse, and per-column metadata.
3. Restart / refresh the app — new files are discovered automatically.
   No cache rebuild is required.
"""
