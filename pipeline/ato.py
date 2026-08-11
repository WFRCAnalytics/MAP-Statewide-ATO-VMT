"""Access to Opportunity (ATO) processing.

Converts the raw per-model-area ATO CSVs + statewide TAZ geometry into the
canonical processed artifacts (metrics parquet, fill/boundary PMTiles,
manifest.json) and publishes them into the Vite app's static data folder.

Depends only on `pipeline.config` and `pipeline.io_utils` - not on
`pipeline.vmt`.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import pandas as pd

from pipeline.config import (
    BOUNDARY_PMTILES_MAXZOOM,
    MODEL_AREA_CONFIGS,
    MODEL_AREA_ORDER,
    PMTILES_MAXZOOM,
    PMTILES_MINZOOM,
    RAW_ROOT,
    REPO_ROOT,
    TAZ_BOUNDARY_SIMPLIFY_TOLERANCE,
    TAZ_FILL_SIMPLIFY_TOLERANCE,
    TAZ_PATH,
)
from pipeline.io_utils import (
    build_boundary_features,
    create_pmtiles,
    read_taz_geometries,
    safe_unlink,
    write_parquet,
)

PROCESSED_DIR = REPO_ROOT / "data" / "processed" / "ato"
WEB_DATA_DIR = REPO_ROOT / "_site" / "public" / "data" / "ato"
SCRATCH_DIR = PROCESSED_DIR / "_scratch"

METRIC_COLUMNS = [
    "Job_byAuto",
    "Job_byTran",
    "Job_byBike",
    "Job_byWalk",
    "HH_byAuto",
    "HH_byTran",
    "HH_byBike",
    "HH_byWalk",
]
GEOGRAPHY_TYPES = ["TAZ", "CITY"]
GEOGRAPHY_LABELS = {
    "TAZ": "TAZ",
    "CITY": "City",
}
GEOGRAPHY_SOURCE_COLUMNS = {
    "CITY": "CITY_NAME",
}

PMTILES_LAYER_NAME = "ato_taz"
BOUNDARY_PMTILES_LAYER_NAME = "ato_taz_boundary"
METRICS_FILENAME = "ato_metrics.parquet"
FILL_PMTILES_FILENAME = "ato_taz.pmtiles"
BOUNDARY_PMTILES_FILENAME = "ato_taz_boundaries.pmtiles"


def get_ato_path(config: dict, scenario_year: int) -> Path:
    return (
        RAW_ROOT / config["folder"] / str(scenario_year) / "Access_to_Opportunity.csv"
    )


def required_raw_files() -> list[dict]:
    files = [
        {
            "kind": "TAZ geometry",
            "model_area": "Statewide",
            "scenario_year": None,
            "path": TAZ_PATH,
        }
    ]

    for config in MODEL_AREA_CONFIGS:
        for scenario_year in config["years"]:
            files.append(
                {
                    "kind": "ATO CSV",
                    "model_area": config["name"],
                    "scenario_year": scenario_year,
                    "path": get_ato_path(config, scenario_year),
                }
            )

    return files


def validate_raw_inputs() -> pd.DataFrame:
    records = []
    missing_paths = []

    for item in required_raw_files():
        path = item["path"]
        exists = path.exists()
        if not exists:
            missing_paths.append(path)

        records.append(
            {
                "kind": item["kind"],
                "model_area": item["model_area"],
                "scenario_year": item["scenario_year"],
                "path": str(path.relative_to(REPO_ROOT)),
                "exists": exists,
                "size_mb": round(path.stat().st_size / 1_000_000, 2)
                if exists
                else None,
            }
        )

    if missing_paths:
        missing_list = "\n".join(
            f"  - {path.relative_to(REPO_ROOT)}" for path in missing_paths
        )
        raise FileNotFoundError(f"Missing required raw input files:\n{missing_list}")

    return pd.DataFrame(records)


def normalize_geography_name(value: object, geography_type: str) -> str:
    text = str(value or "").strip()
    if not text or text.lower() == "nan":
        return f"Unknown {GEOGRAPHY_LABELS[geography_type]}"
    return re.sub(r"\s+", " ", text)


def geography_id(geography_type: str, geography_name: str) -> str:
    if geography_type == "TAZ":
        return geography_name
    return f"{geography_type}|{geography_name}"


def read_geography_lookup() -> pd.DataFrame:
    lookup = read_taz_geometries(
        0,
        extra_columns=["CITY_NAME"],
    )[["CO_TAZID", "CITY_NAME"]].copy()
    lookup["CO_TAZID"] = lookup["CO_TAZID"].astype("int32")
    lookup["CITY_NAME"] = lookup["CITY_NAME"].map(
        lambda value: normalize_geography_name(value, "CITY")
    )
    return lookup.drop_duplicates(subset=["CO_TAZID"])


def read_ato_taz_metrics() -> pd.DataFrame:
    frames = []
    for config in MODEL_AREA_CONFIGS:
        model_area = config["name"]
        for scenario_year in config["years"]:
            path = get_ato_path(config, scenario_year)
            if not path.exists():
                raise FileNotFoundError(path)

            df = pd.read_csv(path)
            df = df.rename(columns={"TAZID": "SA_TAZID"})
            df["ScenarioYear"] = scenario_year
            df["ModelArea"] = model_area

            if "SA_TAZID" not in df.columns:
                df["SA_TAZID"] = df["CO_TAZID"]

            for column in METRIC_COLUMNS:
                if column not in df.columns:
                    df[column] = 0

            keep_columns = [
                "ScenarioYear",
                "ModelArea",
                "SA_TAZID",
                "CO_TAZID",
            ] + METRIC_COLUMNS
            frames.append(df[keep_columns])

    metrics = pd.concat(frames, ignore_index=True)
    metrics["ScenarioYear"] = metrics["ScenarioYear"].astype("int16")
    metrics["SA_TAZID"] = pd.to_numeric(
        metrics["SA_TAZID"], errors="coerce"
    ).fillna(0).astype("int32")
    metrics["CO_TAZID"] = pd.to_numeric(
        metrics["CO_TAZID"], errors="coerce"
    ).fillna(0).astype("int32")

    for column in METRIC_COLUMNS:
        metrics[column] = pd.to_numeric(metrics[column], errors="coerce").fillna(0)

    metrics["GeographyType"] = "TAZ"
    metrics["GeographyId"] = metrics["CO_TAZID"].astype(str)
    metrics["GeographyName"] = metrics["CO_TAZID"].astype(str)
    return metrics


def aggregate_metrics_by_geography(
    taz_metrics: pd.DataFrame,
    lookup: pd.DataFrame,
    geography_type: str,
) -> pd.DataFrame:
    source_column = GEOGRAPHY_SOURCE_COLUMNS[geography_type]
    merged = taz_metrics.merge(lookup, on="CO_TAZID", how="left", validate="m:1")
    merged["GeographyType"] = geography_type
    merged["GeographyName"] = merged[source_column].map(
        lambda value: normalize_geography_name(value, geography_type)
    )
    merged["GeographyId"] = merged["GeographyName"].map(
        lambda value: geography_id(geography_type, value)
    )

    aggregated = (
        merged.groupby(
            ["ScenarioYear", "ModelArea", "GeographyType", "GeographyId"],
            as_index=False,
        )
        .agg(
            GeographyName=("GeographyName", "first"),
            **{column: (column, "mean") for column in METRIC_COLUMNS},
        )
        .round(3)
    )
    aggregated["SA_TAZID"] = pd.Series(pd.NA, index=aggregated.index, dtype="Int64")
    aggregated["CO_TAZID"] = pd.Series(pd.NA, index=aggregated.index, dtype="Int64")
    return aggregated[
        [
            "ScenarioYear",
            "ModelArea",
            "GeographyType",
            "GeographyId",
            "GeographyName",
            "SA_TAZID",
            "CO_TAZID",
            *METRIC_COLUMNS,
        ]
    ]


def read_ato_metrics() -> pd.DataFrame:
    lookup = read_geography_lookup()
    taz_metrics = read_ato_taz_metrics()
    geography_frames = [taz_metrics]
    for geography_type in ("CITY",):
        geography_frames.append(
            aggregate_metrics_by_geography(taz_metrics, lookup, geography_type)
        )

    metrics = pd.concat(geography_frames, ignore_index=True)
    metrics["ScenarioYear"] = metrics["ScenarioYear"].astype("int16")
    return metrics


def add_normalized_metric_columns(metrics: pd.DataFrame) -> pd.DataFrame:
    metrics = metrics.copy()
    group_columns = ["ScenarioYear", "ModelArea", "GeographyType"]

    for column in METRIC_COLUMNS:
        normal_column = f"{column}_norm"
        group_min = metrics.groupby(group_columns)[column].transform("min")
        group_max = metrics.groupby(group_columns)[column].transform("max")
        spread = group_max - group_min
        metrics[normal_column] = ((metrics[column] - group_min) / spread).where(
            spread > 0,
            0,
        )
        metrics[normal_column] = metrics[normal_column].fillna(0).astype("float32")

    return metrics


def dissolve_geography(
    area_taz: gpd.GeoDataFrame,
    geography_type: str,
) -> gpd.GeoDataFrame:
    if geography_type == "TAZ":
        taz = area_taz[["CO_TAZID", "geometry"]].copy()
        taz["GeographyType"] = "TAZ"
        taz["GeographyId"] = taz["CO_TAZID"].astype(str)
        taz["GeographyName"] = taz["CO_TAZID"].astype(str)
        return taz[["GeographyType", "GeographyId", "GeographyName", "CO_TAZID", "geometry"]]

    source_column = GEOGRAPHY_SOURCE_COLUMNS[geography_type]
    dissolved = area_taz[[source_column, "geometry"]].copy()
    dissolved["GeographyName"] = dissolved[source_column].map(
        lambda value: normalize_geography_name(value, geography_type)
    )
    dissolved["GeographyId"] = dissolved["GeographyName"].map(
        lambda value: geography_id(geography_type, value)
    )
    dissolved = dissolved.dissolve(by="GeographyId", as_index=False, aggfunc="first")
    dissolved["GeographyType"] = geography_type
    dissolved["CO_TAZID"] = pd.Series(pd.NA, index=dissolved.index, dtype="Int64")
    return dissolved[
        ["GeographyType", "GeographyId", "GeographyName", "CO_TAZID", "geometry"]
    ]


def build_geography_geometries(
    simplify_tolerance: float,
    metrics: pd.DataFrame,
) -> gpd.GeoDataFrame:
    base = read_taz_geometries(
        0,
        extra_columns=["CITY_NAME"],
    )
    base["CITY_NAME"] = base["CITY_NAME"].map(
        lambda value: normalize_geography_name(value, "CITY")
    )

    taz_rows = metrics.loc[metrics["GeographyType"] == "TAZ", ["ModelArea", "CO_TAZID"]]
    area_frames = []
    for model_area in MODEL_AREA_ORDER:
        area_ids = sorted(
            {
                int(value)
                for value in taz_rows.loc[taz_rows["ModelArea"] == model_area, "CO_TAZID"]
                .dropna()
                .astype(int)
                .tolist()
            }
        )
        if not area_ids:
            continue

        area_taz = base.loc[base["CO_TAZID"].isin(area_ids)].copy()
        for geography_type in GEOGRAPHY_TYPES:
            geography_gdf = dissolve_geography(area_taz, geography_type)
            geography_gdf["geometry"] = geography_gdf.geometry.simplify(
                simplify_tolerance,
                preserve_topology=True,
            )
            geography_gdf["ModelArea"] = model_area
            area_frames.append(geography_gdf)

    return gpd.GeoDataFrame(
        pd.concat(area_frames, ignore_index=True),
        geometry="geometry",
        crs=base.crs,
    )


def build_tile_features(
    metrics: pd.DataFrame,
    geometries: gpd.GeoDataFrame,
    warn_missing: bool = True,
) -> gpd.GeoDataFrame:
    metrics = add_normalized_metric_columns(metrics)
    area_frames = []
    join_columns = ["ModelArea", "GeographyType", "GeographyId"]

    for model_area in MODEL_AREA_ORDER:
        for geography_type in GEOGRAPHY_TYPES:
            area_metrics = metrics.loc[
                (metrics["ModelArea"] == model_area)
                & (metrics["GeographyType"] == geography_type)
            ].copy()
            if area_metrics.empty:
                continue

            wide = (
                area_metrics[join_columns]
                .drop_duplicates(subset=join_columns)
                .set_index(join_columns)
                .sort_index()
            )

            for scenario_year in sorted(area_metrics["ScenarioYear"].dropna().unique()):
                year_metrics = (
                    area_metrics.loc[area_metrics["ScenarioYear"] == scenario_year]
                    .set_index(join_columns)
                    .sort_index()
                )
                for column in METRIC_COLUMNS:
                    value_column = f"y{int(scenario_year)}_{column}"
                    normal_column = f"{value_column}_norm"
                    available_column = f"{value_column}_has"
                    wide[value_column] = year_metrics[column]
                    wide[normal_column] = year_metrics[f"{column}_norm"]
                    wide[available_column] = year_metrics[column].notna().astype("int8")

            area_geometry = geometries.loc[
                (geometries["ModelArea"] == model_area)
                & (geometries["GeographyType"] == geography_type)
            ].copy()

            missing_ids = sorted(
                set(wide.reset_index()["GeographyId"]) - set(area_geometry["GeographyId"])
            )
            if warn_missing and missing_ids:
                sample = ", ".join(str(value) for value in missing_ids[:6])
                print(
                    f"Warning: {model_area} {geography_type} has "
                    f"{len(missing_ids):,} geography values without geometry ({sample})"
                )

            area_gdf = area_geometry.merge(
                wide.reset_index(),
                on=join_columns,
                how="inner",
                validate="1:1",
            )
            area_frames.append(area_gdf)

    if not area_frames:
        raise ValueError("No ATO tile features could be built.")

    tile_gdf = gpd.GeoDataFrame(
        pd.concat(area_frames, ignore_index=True),
        geometry="geometry",
        crs=geometries.crs,
    )

    for column in tile_gdf.columns:
        if column.endswith("_has"):
            tile_gdf[column] = tile_gdf[column].fillna(0).astype("int8")
        elif column.endswith("_norm"):
            tile_gdf[column] = tile_gdf[column].fillna(0).astype("float32").round(3)
        elif column.startswith("y"):
            tile_gdf[column] = pd.to_numeric(
                tile_gdf[column],
                errors="coerce",
            ).fillna(0)

    return tile_gdf


def build_manifest(metrics: pd.DataFrame, tile_gdf: gpd.GeoDataFrame) -> dict:
    ranges = {}
    record_counts = {}
    scenario_years_by_model_area = {}

    for model_area, group in metrics.groupby("ModelArea", sort=False):
        scenario_years_by_model_area[model_area] = sorted(
            int(year) for year in group["ScenarioYear"].dropna().unique()
        )

    for (scenario_year, model_area, geography_type), group in metrics.groupby(
        ["ScenarioYear", "ModelArea", "GeographyType"],
        sort=True,
    ):
        key = f"{int(scenario_year)}|{model_area}|{geography_type}"
        record_counts[key] = int(group["GeographyId"].nunique())
        ranges[key] = {}
        for column in METRIC_COLUMNS:
            ranges[key][column] = {
                "min": float(group[column].min()),
                "max": float(group[column].max()),
            }

    bounds = [float(value) for value in tile_gdf.total_bounds]
    model_area_bounds = {}
    model_area_feature_counts = {}
    model_area_geography_bounds = {}
    model_area_geography_feature_counts = {}
    for model_area in MODEL_AREA_ORDER:
        group = tile_gdf.loc[tile_gdf["ModelArea"] == model_area]
        if group.empty:
            continue
        model_area_bounds[model_area] = [float(value) for value in group.total_bounds]
        model_area_feature_counts[model_area] = int(len(group))

        for geography_type in GEOGRAPHY_TYPES:
            area_geo = group.loc[group["GeographyType"] == geography_type]
            if area_geo.empty:
                continue
            geo_key = f"{model_area}|{geography_type}"
            model_area_geography_bounds[geo_key] = [
                float(value) for value in area_geo.total_bounds
            ]
            model_area_geography_feature_counts[geo_key] = int(len(area_geo))

    model_areas = [
        model_area
        for model_area in MODEL_AREA_ORDER
        if model_area in set(metrics["ModelArea"].dropna().unique())
    ]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset": "ato",
        "dataset_label": "ATO",
        "dataset_title": "Access to Opportunity",
        "model_areas": model_areas,
        "geography_types": GEOGRAPHY_TYPES,
        "scenario_years": sorted(
            int(year) for year in metrics["ScenarioYear"].dropna().unique()
        ),
        "scenario_years_by_model_area": scenario_years_by_model_area,
        "metrics": METRIC_COLUMNS,
        "metric_ranges": ranges,
        "record_counts": record_counts,
        "bounds": bounds,
        "model_area_bounds": model_area_bounds,
        "model_area_feature_counts": model_area_feature_counts,
        "model_area_geography_bounds": model_area_geography_bounds,
        "model_area_geography_feature_counts": model_area_geography_feature_counts,
        "files": {
            "metrics": f"ato/{METRICS_FILENAME}",
            "pmtiles": f"ato/{FILL_PMTILES_FILENAME}",
            "boundaries_pmtiles": f"ato/{BOUNDARY_PMTILES_FILENAME}",
        },
        "pmtiles": {
            "source_layer": PMTILES_LAYER_NAME,
            "minzoom": PMTILES_MINZOOM,
            "maxzoom": PMTILES_MAXZOOM,
            "feature_model": "wide_geography_by_model_area_year",
            "feature_count": int(len(tile_gdf)),
            "simplify_tolerance": TAZ_FILL_SIMPLIFY_TOLERANCE,
            "property_template": "y{ScenarioYear}_{MetricColumn}",
            "availability_property_template": "y{ScenarioYear}_{MetricColumn}_has",
        },
        "boundary_pmtiles": {
            "source_layer": BOUNDARY_PMTILES_LAYER_NAME,
            "minzoom": PMTILES_MINZOOM,
            "maxzoom": BOUNDARY_PMTILES_MAXZOOM,
            "feature_count": None,
            "simplify_tolerance": TAZ_BOUNDARY_SIMPLIFY_TOLERANCE,
            "simplification_method": "per_geography_boundary",
        },
    }


def copy_web_assets() -> None:
    import shutil

    WEB_DATA_DIR.mkdir(parents=True, exist_ok=True)

    for filename in [
        "manifest.json",
        METRICS_FILENAME,
        FILL_PMTILES_FILENAME,
        BOUNDARY_PMTILES_FILENAME,
    ]:
        source_path = PROCESSED_DIR / filename
        target_path = WEB_DATA_DIR / filename
        try:
            shutil.copy2(source_path, target_path)
        except PermissionError:
            if not target_path.exists():
                raise
            print(f"Warning: kept existing locked web file: {target_path}")

    for obsolete in [
        PROCESSED_DIR / "ustm_metrics.parquet",
        PROCESSED_DIR / "ustm_ato_taz.pmtiles",
        PROCESSED_DIR / "ustm_taz_boundaries.pmtiles",
        PROCESSED_DIR / "ustm_taz_geometries.parquet",
        WEB_DATA_DIR / "ustm_metrics.parquet",
        WEB_DATA_DIR / "ustm_ato_taz.pmtiles",
        WEB_DATA_DIR / "ustm_taz_boundaries.pmtiles",
        WEB_DATA_DIR / "ustm_taz_geometries.parquet",
    ]:
        safe_unlink(obsolete)


def build_processed_assets() -> dict:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    validate_raw_inputs()

    metrics = read_ato_metrics()
    fill_geometries = build_geography_geometries(TAZ_FILL_SIMPLIFY_TOLERANCE, metrics)
    boundary_geometries = build_geography_geometries(
        TAZ_BOUNDARY_SIMPLIFY_TOLERANCE, metrics
    )
    tile_gdf = build_tile_features(metrics, fill_geometries)
    boundary_tile_gdf = build_tile_features(
        metrics, boundary_geometries, warn_missing=False
    )
    boundary_gdf = build_boundary_features(boundary_tile_gdf)

    write_parquet(metrics, PROCESSED_DIR / METRICS_FILENAME)
    create_pmtiles(
        tile_gdf,
        PROCESSED_DIR / FILL_PMTILES_FILENAME,
        SCRATCH_DIR,
        PMTILES_LAYER_NAME,
        PMTILES_MAXZOOM,
        "Access to Opportunity by model area geography",
    )
    create_pmtiles(
        boundary_gdf,
        PROCESSED_DIR / BOUNDARY_PMTILES_FILENAME,
        SCRATCH_DIR,
        BOUNDARY_PMTILES_LAYER_NAME,
        BOUNDARY_PMTILES_MAXZOOM,
        "Access to Opportunity geography boundaries",
    )

    manifest = build_manifest(metrics, tile_gdf)
    manifest["boundary_pmtiles"]["feature_count"] = int(len(boundary_gdf))
    (PROCESSED_DIR / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    return {
        "metric_rows": int(len(metrics)),
        "tile_features": int(len(tile_gdf)),
        "boundary_features": int(len(boundary_gdf)),
        "processed_dir": str(PROCESSED_DIR),
        "manifest": manifest,
    }


def publish_web_assets() -> dict:
    copy_web_assets()
    return {
        "web_data_dir": str(WEB_DATA_DIR),
        "files": {
            "manifest": str(WEB_DATA_DIR / "manifest.json"),
            "metrics": str(WEB_DATA_DIR / METRICS_FILENAME),
            "pmtiles": str(WEB_DATA_DIR / FILL_PMTILES_FILENAME),
            "boundaries_pmtiles": str(WEB_DATA_DIR / BOUNDARY_PMTILES_FILENAME),
        },
    }
