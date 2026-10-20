"""
Provenance registry for FOCAL CVI explorer features.

Source cards and per-feature resolution are drawn from
``doc/cvi_dataset_description_mpg.md`` and ``doc/focal_cvi_data_inventory.md``.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

# ---------------------------------------------------------------------------
# Source cards (one per product / inventory family)
# ---------------------------------------------------------------------------

SOURCES: dict[str, dict[str, Any]] = {
    "aef": {
        "id": "aef",
        "title": "AlphaEarth Foundations embeddings",
        "provider": "Google DeepMind (Earth Engine)",
        "inventory_id": "P01",
        "year": "2024",
        "native_resolution": "10 m",
        "grid_resolution": "100 m",
        "crs": "EPSG:3035",
        "license": "CC-BY-4.0",
        "resampling": "10×10 mean-pool from 10 m to 100 m INSPIRE grid",
        "coverage": "Germany + Czechia (matrix uses Germany cells only)",
        "description": (
            "64-dimensional annual satellite embeddings (AlphaEarth Foundations / "
            "Satellite Embedding V1). Stored as int8; decode by dividing by 127 "
            "to recover approximately [-1, 1]."
        ),
        "url": "https://deepmind.google/science/alphaearth/",
        "product": "AlphaEarth Foundations 2024",
    },
    "zensus2022": {
        "id": "zensus2022",
        "title": "Zensus 2022 grid themes",
        "provider": "Destatis / zensus2022.de",
        "inventory_id": "S01–S03, A01–A04, E01",
        "year": "2022",
        "native_resolution": "100 m",
        "grid_resolution": "100 m",
        "crs": "EPSG:3035",
        "license": "DL-DE-BY-2.0",
        "resampling": "Native 100 m GITTER_ID join (no resampling)",
        "coverage": "Germany (cells with any Tier A/B Zensus theme)",
        "description": (
            "Census 2022 grid publications: population, age, households, "
            "nationality/birth country, buildings, heating, dwellings, rent, "
            "and related themes. Tier A (censA) = core indicators; "
            "Tier B (censB) = proxy indicators. Disclosure/Cell-Key missingness "
            "applies."
        ),
        "url": "https://www.zensus2022.de/",
        "product": "Zensus 2022 100 m grid",
    },
    "jrc_pop": {
        "id": "jrc_pop",
        "title": "JRC / Eurostat 100 m population grid",
        "provider": "Eurostat GISCO / JRC",
        "inventory_id": "E02",
        "year": "2021",
        "native_resolution": "100 m",
        "grid_resolution": "100 m",
        "crs": "EPSG:3035",
        "license": "Eurostat reuse / CC-BY-4.0",
        "resampling": "Native 100 m raster on INSPIRE grid",
        "coverage": "Germany (matrix cells)",
        "description": (
            "Harmonised EU population grid (Release 11/2024 product family; "
            "reference year 2021). Used as exposure / population density."
        ),
        "url": "https://ec.europa.eu/eurostat/web/gisco/geodata/population-distribution/geostat",
        "product": "GEOSTAT / JRC-ESTAT population grid 2021",
    },
    "osm": {
        "id": "osm",
        "title": "OpenStreetMap amenities (health, cooling, green, water)",
        "provider": "OpenStreetMap contributors (via Geofabrik)",
        "inventory_id": "A06 / A07",
        "year": "snapshot (ingest date)",
        "native_resolution": "vector (point / polygon)",
        "grid_resolution": "100 m",
        "crs": "EPSG:3035",
        "license": "ODbL (share-alike)",
        "resampling": "Count / distance / presence rasterised to 100 m cells",
        "coverage": "Germany (matrix cells)",
        "description": (
            "Health amenities (hospitals, clinics, pharmacies, GPs), cooling "
            "amenities, green space, and water bodies derived from OSM. "
            "ODbL share-alike applies if redistributing OSM-derived layers."
        ),
        "url": "https://www.openstreetmap.org/copyright",
        "product": "OSM amenities → 100 m grid",
    },
    "clms_imd": {
        "id": "clms_imd",
        "title": "Copernicus HRL Imperviousness Density",
        "provider": "Copernicus Land Monitoring Service",
        "inventory_id": "E03",
        "year": "2018",
        "native_resolution": "10 m / 100 m",
        "grid_resolution": "100 m",
        "crs": "EPSG:3035",
        "license": "CLMS free terms",
        "resampling": "Native 100 m HRL product on INSPIRE grid",
        "coverage": "Germany (matrix cells)",
        "description": "Percent sealed / impervious surface (HRL IMD 2018).",
        "url": "https://land.copernicus.eu/en/products/high-resolution-layer-imperviousness",
        "product": "HRL Imperviousness Density 2018",
    },
    "clms_tcd": {
        "id": "clms_tcd",
        "title": "Copernicus HRL Tree Cover Density",
        "provider": "Copernicus Land Monitoring Service",
        "inventory_id": "A08",
        "year": "2015",
        "native_resolution": "10 m / 100 m",
        "grid_resolution": "100 m",
        "crs": "EPSG:3035",
        "license": "CLMS free terms",
        "resampling": "Native 100 m HRL product on INSPIRE grid",
        "coverage": "Germany (matrix cells)",
        "description": (
            "Percent tree cover (HRL TCD 2015). Note: older vintage than "
            "Imperviousness 2018."
        ),
        "url": "https://land.copernicus.eu/en/products/high-resolution-layer-tree-cover-density",
        "product": "HRL Tree Cover Density 2015",
    },
    "lst": {
        "id": "lst",
        "title": "Landsat land surface temperature (summer p90)",
        "provider": "USGS Landsat 8/9 (via Google Earth Engine)",
        "inventory_id": "E04",
        "year": "2023",
        "native_resolution": "~30 m",
        "grid_resolution": "100 m",
        "crs": "EPSG:3035",
        "license": "USGS Landsat (open)",
        "resampling": (
            "Collection 2 Level-2 LST; June–August clear-sky 90th percentile; "
            "aggregated to 100 m"
        ),
        "coverage": "Germany (matrix cells)",
        "description": (
            "Summer (JJA) clear-sky 90th-percentile land surface temperature "
            "in °C — urban heat / surface temperature exposure proxy."
        ),
        "url": "https://www.usgs.gov/landsat-missions/landsat-collection-2-level-2-science-products",
        "product": "Landsat 8/9 C2 L2 LST JJA p90 2023",
    },
    "hyras": {
        "id": "hyras",
        "title": "DWD HYRAS climate hazard indices",
        "provider": "Deutscher Wetterdienst (DWD CDC)",
        "inventory_id": "H01 / H02",
        "year": "multi-year climatology (HYRAS)",
        "native_resolution": "1 km",
        "grid_resolution": "100 m",
        "crs": "EPSG:3035",
        "license": "GeoNutzV (DWD open)",
        "resampling": "1 km indices nearest-/area-assigned onto 100 m cells",
        "coverage": "Germany (aligned to matrix keys)",
        "description": (
            "Heat and rainfall hazard indices derived from HYRAS daily grids "
            "(e.g. hot days, heatwave days, RX1day, tropical nights). Held as a "
            "hazard sidecar in the modelling framework — shown in the explorer "
            "for map exploration, not as SAE predictors."
        ),
        "url": "https://opendata.dwd.de/climate_environment/CDC/",
        "product": "HYRAS indices on 100 m grid",
    },
    "ba_amk": {
        "id": "ba_amk",
        "title": "BA Arbeitsmarkt kommunal (unemployment / SGB II)",
        "provider": "Bundesagentur für Arbeit",
        "inventory_id": "S06 / S07",
        "year": "2024 (product month 202412)",
        "native_resolution": "Gemeinde (AGS)",
        "grid_resolution": "100 m",
        "crs": "EPSG:3035",
        "license": "BA open reuse terms",
        "resampling": "Gemeinde → 100 m via dasymetric population weights",
        "coverage": "Germany (matrix cells with admin join)",
        "description": (
            "S06: unemployment rate (%) = 100 × Arbeitslose / "
            "(sv-Beschäftigte am Wohnort + Arbeitslose). "
            "S07: mean annual unemployed persons in Rechtskreis SGB II "
            "(not Bedarfsgemeinschaften recipient counts)."
        ),
        "url": "https://statistik.arbeitsagentur.de/",
        "product": "Arbeitsmarkt kommunal 202412",
    },
}


def _from_source(source_id: str, **overrides: Any) -> dict[str, Any]:
    base = SOURCES[source_id]
    out = {
        "source_id": source_id,
        "provider": base["provider"],
        "product": base["product"],
        "year": base["year"],
        "native_resolution": base["native_resolution"],
        "grid_resolution": base["grid_resolution"],
        "crs": base["crs"],
        "license": base["license"],
        "resampling": base["resampling"],
        "inventory_id": base["inventory_id"],
        "url": base.get("url", ""),
    }
    out.update(overrides)
    return out


# Exact column overrides (applied after prefix rules)
_COLUMN_OVERRIDES: dict[str, dict[str, Any]] = {
    "grid__population_jrc_estat_2021": _from_source("jrc_pop"),
    "grid__a06_health_count": _from_source(
        "osm", inventory_id="A06", product="OSM health amenity count",
    ),
    "grid__a06_health_dist_m": _from_source(
        "osm", inventory_id="A06", product="OSM distance to nearest health amenity",
    ),
    "grid__a07_cooling_count": _from_source(
        "osm", inventory_id="A07", product="OSM cooling amenity count",
    ),
    "grid__a07_cooling_dist_m": _from_source(
        "osm", inventory_id="A07", product="OSM distance to nearest cooling amenity",
    ),
    "grid__a07_green_presence": _from_source(
        "osm", inventory_id="A07", product="OSM green-space presence",
    ),
    "grid__a07_water_presence": _from_source(
        "osm", inventory_id="A07", product="OSM water-body presence",
    ),
    "clms__imperviousness_density": _from_source("clms_imd"),
    "clms__tree_cover_density": _from_source("clms_tcd"),
    "lst__summer_p90": _from_source("lst"),
    "admin__s06__ba_unemployment_rate": _from_source(
        "ba_amk",
        inventory_id="S06",
        product="BA AMK unemployment rate (%)",
    ),
    "admin__s07__ba_sgb2_recipients": _from_source(
        "ba_amk",
        inventory_id="S07",
        product="BA AMK SGB II unemployed persons (annual mean)",
    ),
}


def resolve_feature(column: str, block: str = "") -> dict[str, Any]:
    """Return provenance fields for one explorer feature column."""
    if column in _COLUMN_OVERRIDES:
        return deepcopy(_COLUMN_OVERRIDES[column])

    if column.startswith("aef__") or block == "aef":
        return _from_source("aef", product=f"AlphaEarth embedding {column}")

    if column.startswith("censA__") or column.startswith("censB__") or block in (
        "censA", "censB",
    ):
        tier = "Tier A" if column.startswith("censA__") or block == "censA" else "Tier B"
        return _from_source(
            "zensus2022",
            product=f"Zensus 2022 ({tier}): {column}",
        )

    if column.startswith("hyras__") or block == "hazard":
        return _from_source("hyras", product=f"HYRAS index: {column}")

    if column.startswith("admin__s06") or column.startswith("s06__"):
        return _from_source("ba_amk", inventory_id="S06")
    if column.startswith("admin__s07") or column.startswith("s07__"):
        return _from_source("ba_amk", inventory_id="S07")
    if column.startswith("admin__") or block == "admin":
        return _from_source("ba_amk")

    if column.startswith("grid__population") or "population_jrc" in column:
        return _from_source("jrc_pop")
    if column.startswith("grid__a06") or "health" in column:
        return _from_source("osm", inventory_id="A06")
    if column.startswith("grid__a07") or column.startswith("grid__"):
        return _from_source("osm", inventory_id="A07")

    if "imperviousness" in column:
        return _from_source("clms_imd")
    if "tree_cover" in column:
        return _from_source("clms_tcd")
    if column.startswith("lst__") or block == "lst":
        return _from_source("lst")
    if column.startswith("clms__") or block == "clms":
        return _from_source("clms_imd")

    # Fallback — still structured so UI never shows empty provenance
    return {
        "source_id": "unknown",
        "provider": "unknown",
        "product": column,
        "year": "unknown",
        "native_resolution": "unknown",
        "grid_resolution": "100 m",
        "crs": "EPSG:3035",
        "license": "unknown",
        "resampling": "aligned to FOCAL 100 m INSPIRE grid",
        "inventory_id": "",
        "url": "",
    }


def provenance_caption(prov: dict[str, Any]) -> str:
    """One-line caption for map / detail headers."""
    native = prov.get("native_resolution") or "?"
    grid = prov.get("grid_resolution") or "100 m"
    parts = [
        prov.get("provider") or "",
        prov.get("product") or "",
        prov.get("year") or "",
        f"native {native} → grid {grid}",
        prov.get("license") or "",
    ]
    return " · ".join(p for p in parts if p)


def source_cards() -> list[dict[str, Any]]:
    """Ordered list of source cards for the Data sources page."""
    order = [
        "aef", "zensus2022", "jrc_pop", "osm",
        "clms_imd", "clms_tcd", "lst", "hyras", "ba_amk",
    ]
    return [deepcopy(SOURCES[k]) for k in order if k in SOURCES]
