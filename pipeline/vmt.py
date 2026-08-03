"""Vehicle Miles Traveled (VMT) processing.

Converts the raw per-model-area `assigned_net.dbf` files + statewide TAZ
geometry into the canonical processed artifacts (metrics parquet,
fill/boundary PMTiles, manifest.json) and publishes them into the Vite app's
static data folder.

Depends only on `pipeline.config` and `pipeline.io_utils` - not on
`pipeline.ato`. Previously this module imported constants and geometry
helpers from `process_ato.py`; those have moved to `pipeline/config.py` and
`pipeline/io_utils.py` so the ATO and VMT processors no longer depend on
each other.
"""

from __future__ import annotations

import json
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import pandas as pd
from dbfread import DBF

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
    write_parquet,
)

PROCESSED_DIR = REPO_ROOT / "data" / "processed" / "vmt"
WEB_DATA_DIR = REPO_ROOT / "_site" / "public" / "data" / "vmt"
SCRATCH_DIR = PROCESSED_DIR / "_scratch"

VMT_COLUMNS = [
    "AM_VMT",
    "MD_VMT",
    "PM_VMT",
    "EV_VMT",
    "DY_VMT",
]

VMT_COLUMN_ALIASES = {
    "CO_TAZID": ["CO_TAZID"],
    "AM_VMT": ["AM_VMT", "VMT_AM"],
    "MD_VMT": ["MD_VMT", "VMT_MD"],
    "PM_VMT": ["PM_VMT", "VMT_PM"],
    "EV_VMT": ["EV_VMT", "VMT_EV"],
    "DY_VMT": ["DY_VMT", "VMT_DY"],
}

PMTILES_LAYER_NAME = "vmt_taz"
BOUNDARY_PMTILES_LAYER_NAME = "vmt_taz_boundary"
METRICS_FILENAME = "vmt_metrics.parquet"
FILL_PMTILES_FILENAME = "vmt_taz.pmtiles"
BOUNDARY_PMTILES_FILENAME = "vmt_taz_boundaries.pmtiles"


def get_vmt_path(config: dict, scenario_year: int) -> Path:
    return RAW_ROOT / config["folder"] / str(scenario_year) / "assigned_net.dbf"


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
                    "kind": "VMT assigned_net DBF",
                    "model_area": config["name"],
                    "scenario_year": scenario_year,
                    "path": get_vmt_path(config, scenario_year),
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


def resolve_vmt_columns(field_names: list[str], path: Path) -> dict:
    field_name_set = set(field_names)
    source_columns = {}
    missing_columns = []

    for output_col, candidate_cols in VMT_COLUMN_ALIASES.items():
        source_col = next(
            (
                candidate_col
                for candidate_col in candidate_cols
                if candidate_col in field_name_set
            ),
            None,
        )
        if source_col is None:
            missing_columns.append(output_col)
        else:
            source_columns[output_col] = source_col

    if missing_columns:
        raise ValueError(f"{path} is missing columns: {missing_columns}")

    return source_columns


def as_float(value) -> float:
    if value in (None, ""):
        return 0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0


def as_taz_id(value) -> int | None:
    try:
        taz_id = int(float(value))
    except (TypeError, ValueError):
        return None
    return taz_id if taz_id > 0 else None


def read_vmt_metrics_for_file(path: Path) -> pd.DataFrame:
    table = DBF(
        str(path),
        load=False,
        recfactory=dict,
        char_decode_errors="ignore",
    )
    source_columns = resolve_vmt_columns(table.field_names, path)
    totals = defaultdict(lambda: {column: 0.0 for column in VMT_COLUMNS})

    for record in table:
        taz_id = as_taz_id(record.get(source_columns["CO_TAZID"]))
        if taz_id is None:
            continue

        for column in VMT_COLUMNS:
            totals[taz_id][column] += as_float(record.get(source_columns[column]))

    records = [
        {"CO_TAZID": taz_id, **values} for taz_id, values in sorted(totals.items())
    ]
    return pd.DataFrame.from_records(records)


def read_vmt_metrics() -> pd.DataFrame:
    frames = []

    for config in MODEL_AREA_CONFIGS:
        model_area = config["name"]
        for scenario_year in config["years"]:
            path = get_vmt_path(config, scenario_year)
            if not path.exists():
                raise FileNotFoundError(path)

            df = read_vmt_metrics_for_file(path)
            df["ScenarioYear"] = scenario_year
            df["ModelArea"] = model_area
            frames.append(df)

    metrics = pd.concat(frames, ignore_index=True)
    metrics["ScenarioYear"] = metrics["ScenarioYear"].astype("int16")
    metrics["CO_TAZID"] = metrics["CO_TAZID"].astype("int32")

    for column in VMT_COLUMNS:
        metrics[column] = pd.to_numeric(metrics[column], errors="coerce").fillna(0)

    first_columns = ["ScenarioYear", "ModelArea", "CO_TAZID"]
    return metrics[first_columns + VMT_COLUMNS].copy()


def add_normalized_metric_columns(metrics: pd.DataFrame) -> pd.DataFrame:
    metrics = metrics.copy()
    group_columns = ["ScenarioYear", "ModelArea"]

    for column in VMT_COLUMNS:
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


def build_tile_features(
    metrics: pd.DataFrame,
    geometries: gpd.GeoDataFrame,
    warn_missing: bool = True,
) -> gpd.GeoDataFrame:
    metrics = add_normalized_metric_columns(metrics)
    geometry_ids = set(geometries["CO_TAZID"].astype("int32"))
    area_frames = []

    for model_area in MODEL_AREA_ORDER:
        area_metrics = metrics.loc[metrics["ModelArea"] == model_area].copy()
        if area_metrics.empty:
            continue

        wide = (
            area_metrics[["CO_TAZID"]]
            .drop_duplicates()
            .set_index("CO_TAZID")
            .sort_index()
        )
        wide["ModelArea"] = model_area

        for scenario_year in sorted(area_metrics["ScenarioYear"].dropna().unique()):
            year_metrics = (
                area_metrics.loc[area_metrics["ScenarioYear"] == scenario_year]
                .set_index("CO_TAZID")
                .sort_index()
            )
            for column in VMT_COLUMNS:
                value_column = f"y{int(scenario_year)}_{column}"
                normal_column = f"{value_column}_norm"
                available_column = f"{value_column}_has"
                wide[value_column] = year_metrics[column]
                wide[normal_column] = year_metrics[f"{column}_norm"]
                wide[available_column] = year_metrics[column].notna().astype("int8")

        missing_ids = sorted(set(wide.index.astype("int32")) - geometry_ids)
        if warn_missing and missing_ids:
            sample = ", ".join(str(value) for value in missing_ids[:6])
            print(
                f"Warning: {model_area} has {len(missing_ids):,} CO_TAZID values "
                f"without statewide TAZ geometry ({sample})"
            )

        area_gdf = geometries.merge(
            wide.reset_index(),
            on="CO_TAZID",
            how="inner",
            validate="1:1",
        )
        area_frames.append(area_gdf)

    if not area_frames:
        raise ValueError("No VMT tile features could be built.")

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

    for (scenario_year, model_area), group in metrics.groupby(
        ["ScenarioYear", "ModelArea"],
        sort=True,
    ):
        key = f"{int(scenario_year)}|{model_area}"
        record_counts[key] = int(group["CO_TAZID"].nunique())
        ranges[key] = {}
        for column in VMT_COLUMNS:
            ranges[key][column] = {
                "min": float(group[column].min()),
                "max": float(group[column].max()),
            }

    bounds = [float(value) for value in tile_gdf.total_bounds]
    model_area_bounds = {}
    model_area_feature_counts = {}
    for model_area in MODEL_AREA_ORDER:
        group = tile_gdf.loc[tile_gdf["ModelArea"] == model_area]
        if group.empty:
            continue
        model_area_bounds[model_area] = [float(value) for value in group.total_bounds]
        model_area_feature_counts[model_area] = int(len(group))

    model_areas = [
        model_area
        for model_area in MODEL_AREA_ORDER
        if model_area in set(metrics["ModelArea"].dropna().unique())
    ]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset": "vmt",
        "dataset_label": "VMT",
        "dataset_title": "Vehicle Miles Traveled",
        "model_areas": model_areas,
        "scenario_years": sorted(
            int(year) for year in metrics["ScenarioYear"].dropna().unique()
        ),
        "scenario_years_by_model_area": scenario_years_by_model_area,
        "metrics": VMT_COLUMNS,
        "metric_ranges": ranges,
        "record_counts": record_counts,
        "bounds": bounds,
        "model_area_bounds": model_area_bounds,
        "model_area_feature_counts": model_area_feature_counts,
        "files": {
            "metrics": f"vmt/{METRICS_FILENAME}",
            "pmtiles": f"vmt/{FILL_PMTILES_FILENAME}",
            "boundaries_pmtiles": f"vmt/{BOUNDARY_PMTILES_FILENAME}",
        },
        "pmtiles": {
            "source_layer": PMTILES_LAYER_NAME,
            "minzoom": PMTILES_MINZOOM,
            "maxzoom": PMTILES_MAXZOOM,
            "feature_model": "wide_taz_by_model_area_and_year",
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
            "simplification_method": "per_taz_boundary",
        },
    }


def copy_web_assets() -> None:
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


def build_processed_assets() -> dict:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    validate_raw_inputs()

    metrics = read_vmt_metrics()
    fill_geometries = read_taz_geometries(TAZ_FILL_SIMPLIFY_TOLERANCE)
    boundary_geometries = read_taz_geometries(TAZ_BOUNDARY_SIMPLIFY_TOLERANCE)
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
        "Vehicle Miles Traveled by model area TAZ",
    )
    create_pmtiles(
        boundary_gdf,
        PROCESSED_DIR / BOUNDARY_PMTILES_FILENAME,
        SCRATCH_DIR,
        BOUNDARY_PMTILES_LAYER_NAME,
        BOUNDARY_PMTILES_MAXZOOM,
        "Vehicle Miles Traveled TAZ boundaries",
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
