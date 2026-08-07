"""Vehicle Miles Traveled (VMT) processing.

Builds the VMT dataset from TAZ-based produced/attracted CSV outputs. The
processed web artifacts expose VMT by TAZ, scenario year, model area, period,
purpose, and P/A direction instead of network-wide VMT occurring inside a TAZ.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import geopandas as gpd
import pandas as pd

from pipeline.config import (
    BOUNDARY_PMTILES_MAXZOOM,
    MODEL_AREA_CONFIGS,
    PMTILES_MAXZOOM,
    PMTILES_MINZOOM,
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

VMT_MODEL_AREAS = {"Statewide", "Wasatch Front"}
VMT_SOURCE_FILENAMES = {
    "Statewide": "TAZ-Based-VMT.csv",
    "Wasatch Front": "TAZ-Based Metrics.csv",
}
VMT_INPUT_COLUMNS = ["TAZID", "Metric", "Purpose", "Period", "PA", "Total"]
PA_OPTIONS = [
    {"value": "P", "label": "Produced"},
    {"value": "A", "label": "Attracted"},
]
PERIOD_ORDER = ["DY"]
PERIOD_LABELS = {
    "AM": "AM",
    "MD": "MD",
    "PM": "PM",
    "EV": "EV",
    "DY": "DY",
}
PERIOD_TITLES = {
    "AM": "AM",
    "MD": "Midday",
    "PM": "PM",
    "EV": "Evening",
    "DY": "Daily",
}
PERIOD_ICONS = {
    "AM": "fa-sun",
    "MD": "fa-cloud-sun",
    "PM": "fa-city",
    "EV": "fa-moon",
    "DY": "fa-calendar-day",
}
ALL_PURPOSE_VALUE = "ALL"
ALL_PURPOSE_LABEL = "All Purposes"
PURPOSE_GROUPS = [
    {
        "value": "PERSON",
        "label": "Household",
        "all_value": "PERSON_ALL",
        "purposes": ["HBC", "HBS_Pr", "HBS_Sc", "HBS", "HBW", "NHB", "HBO"],
    },
    {
        "value": "TRUCK",
        "label": "Truck",
        "all_value": "TRUCK_ALL",
        "purposes": ["LT", "MD", "HV"],
    },
    {
        "value": "OTHER",
        "label": "Other",
        "all_value": "OTHER_ALL",
        "purposes": [],
    },
]
PURPOSE_GROUP_BY_VALUE = {
    purpose: group["value"] for group in PURPOSE_GROUPS for purpose in group["purposes"]
}
PURPOSE_GROUP_TOTAL_VALUES = {group["all_value"] for group in PURPOSE_GROUPS}

PMTILES_LAYER_NAME = "vmt_taz"
BOUNDARY_PMTILES_LAYER_NAME = "vmt_taz_boundary"
METRICS_FILENAME = "vmt_metrics.parquet"
FILL_PMTILES_FILENAME = "vmt_taz.pmtiles"
BOUNDARY_PMTILES_FILENAME = "vmt_taz_boundaries.pmtiles"
METRICS_BUILD_VERSION = 4
TILES_BUILD_VERSION = 6
_MODEL_AREA_TAZ_IDS: dict[str, list[int]] = {}


def get_vmt_configs() -> list[dict]:
    return [
        config for config in MODEL_AREA_CONFIGS if config["name"] in VMT_MODEL_AREAS
    ]


def get_vmt_path(config: dict, scenario_year: int) -> Path:
    return (
        REPO_ROOT
        / "data"
        / "raw"
        / config["folder"]
        / str(scenario_year)
        / VMT_SOURCE_FILENAMES[config["name"]]
    )


def get_taz_crosswalk_path(config: dict, scenario_year: int) -> Path:
    return (
        REPO_ROOT
        / "data"
        / "raw"
        / config["folder"]
        / str(scenario_year)
        / "Access_to_Opportunity.csv"
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

    for config in get_vmt_configs():
        for scenario_year in config["years"]:
            files.append(
                {
                    "kind": "TAZ-based VMT CSV",
                    "model_area": config["name"],
                    "scenario_year": scenario_year,
                    "path": get_vmt_path(config, scenario_year),
                }
            )
            files.append(
                {
                    "kind": "TAZID to CO_TAZID crosswalk",
                    "model_area": config["name"],
                    "scenario_year": scenario_year,
                    "path": get_taz_crosswalk_path(config, scenario_year),
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


def relative_path(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT)).replace("\\", "/")


def file_signature(path: Path) -> dict:
    stat = path.stat()
    return {
        "path": relative_path(path),
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }


def json_fingerprint(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()


def purpose_group_metric_signature() -> list[dict]:
    return [
        {
            "value": group["value"],
            "all_value": group["all_value"],
            "purposes": group["purposes"],
        }
        for group in PURPOSE_GROUPS
    ]


def metrics_input_files() -> list[Path]:
    return [
        item["path"]
        for item in required_raw_files()
        if item["kind"] != "TAZ geometry"
    ]


def build_metrics_fingerprint() -> str:
    return json_fingerprint(
        {
            "version": METRICS_BUILD_VERSION,
            "model_areas": [
                {
                    "name": config["name"],
                    "folder": config["folder"],
                    "years": config["years"],
                    "source_filename": VMT_SOURCE_FILENAMES[config["name"]],
                }
                for config in get_vmt_configs()
            ],
            "input_columns": VMT_INPUT_COLUMNS,
            "all_purpose_value": ALL_PURPOSE_VALUE,
            "purpose_groups": purpose_group_metric_signature(),
            "geometry": file_signature(TAZ_PATH),
            "files": [file_signature(path) for path in metrics_input_files()],
        }
    )


def build_tiles_fingerprint(metrics_fingerprint: str) -> str:
    return json_fingerprint(
        {
            "version": TILES_BUILD_VERSION,
            "metrics_fingerprint": metrics_fingerprint,
            "geometry": file_signature(TAZ_PATH),
            "fill_simplify_tolerance": TAZ_FILL_SIMPLIFY_TOLERANCE,
            "boundary_simplify_tolerance": TAZ_BOUNDARY_SIMPLIFY_TOLERANCE,
            "minzoom": PMTILES_MINZOOM,
            "fill_maxzoom": PMTILES_MAXZOOM,
            "boundary_maxzoom": BOUNDARY_PMTILES_MAXZOOM,
            "fill_layer": PMTILES_LAYER_NAME,
            "boundary_layer": BOUNDARY_PMTILES_LAYER_NAME,
        }
    )


def read_existing_manifest() -> dict | None:
    manifest_path = PROCESSED_DIR / "manifest.json"
    if not manifest_path.exists():
        return None

    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def read_processed_metrics() -> pd.DataFrame:
    metrics_path = PROCESSED_DIR / METRICS_FILENAME
    metrics_sql = str(metrics_path).replace("\\", "/").replace("'", "''")
    con = duckdb.connect()
    try:
        return con.execute(f"SELECT * FROM read_parquet('{metrics_sql}')").df()
    finally:
        con.close()


def get_model_area_taz_ids(config: dict) -> list[int]:
    model_area = config["name"]
    if model_area in _MODEL_AREA_TAZ_IDS:
        return _MODEL_AREA_TAZ_IDS[model_area]

    if model_area == "Statewide":
        ids = (
            gpd.read_file(TAZ_PATH)[["CO_TAZID"]]
            .dropna(subset=["CO_TAZID"])["CO_TAZID"]
            .astype("int32")
            .drop_duplicates()
            .sort_values()
            .tolist()
        )
    else:
        ids = sorted(
            {
                int(value)
                for scenario_year in config["years"]
                for value in read_taz_crosswalk(
                    get_taz_crosswalk_path(config, scenario_year)
                )["CO_TAZID"]
            }
        )

    _MODEL_AREA_TAZ_IDS[model_area] = ids
    return ids


def existing_metrics_are_current(
    manifest: dict | None, metrics_fingerprint: str
) -> bool:
    return (
        bool(manifest)
        and (PROCESSED_DIR / METRICS_FILENAME).exists()
        and manifest.get("build", {}).get("metrics_fingerprint")
        == metrics_fingerprint
    )


def existing_tiles_are_current(manifest: dict | None, tiles_fingerprint: str) -> bool:
    return (
        bool(manifest)
        and (PROCESSED_DIR / FILL_PMTILES_FILENAME).exists()
        and (PROCESSED_DIR / BOUNDARY_PMTILES_FILENAME).exists()
        and manifest.get("build", {}).get("tiles_fingerprint") == tiles_fingerprint
    )


def tile_metadata_from_manifest(manifest: dict | None) -> dict | None:
    if not manifest:
        return None

    pmtiles = manifest.get("pmtiles", {})
    boundary_pmtiles = manifest.get("boundary_pmtiles", {})
    required_keys = ["bounds", "model_area_bounds", "model_area_feature_counts"]
    if any(key not in manifest for key in required_keys):
        return None
    if pmtiles.get("feature_count") is None:
        return None
    if boundary_pmtiles.get("feature_count") is None:
        return None

    return {
        "bounds": manifest["bounds"],
        "model_area_bounds": manifest["model_area_bounds"],
        "model_area_feature_counts": manifest["model_area_feature_counts"],
        "tile_features": int(pmtiles["feature_count"]),
        "boundary_features": int(boundary_pmtiles["feature_count"]),
    }


def tile_metadata_from_gdfs(
    tile_gdf: gpd.GeoDataFrame, boundary_gdf: gpd.GeoDataFrame
) -> dict:
    model_area_bounds = {}
    model_area_feature_counts = {}
    for model_area in [config["name"] for config in get_vmt_configs()]:
        group = tile_gdf.loc[tile_gdf["ModelArea"] == model_area]
        if group.empty:
            continue
        model_area_bounds[model_area] = [float(value) for value in group.total_bounds]
        model_area_feature_counts[model_area] = int(len(group))

    return {
        "bounds": [float(value) for value in tile_gdf.total_bounds],
        "model_area_bounds": model_area_bounds,
        "model_area_feature_counts": model_area_feature_counts,
        "tile_features": int(len(tile_gdf)),
        "boundary_features": int(len(boundary_gdf)),
    }


def sanitize_dimension(value: str) -> str:
    text = str(value).strip()
    text = re.sub(r"[^A-Za-z0-9_]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "UNKNOWN"


def metric_column(pa: str, period: str, purpose_value: str) -> str:
    return f"{pa}_{period}_{purpose_value}"


def purpose_group_for_value(purpose_value: str) -> str:
    return PURPOSE_GROUP_BY_VALUE.get(purpose_value, "OTHER")


def purpose_group_total_value(group_value: str) -> str:
    return f"{group_value}_ALL"


def read_taz_crosswalk(path: Path) -> pd.DataFrame:
    crosswalk = pd.read_csv(path, usecols=["TAZID", "CO_TAZID"], skipinitialspace=True)
    crosswalk["SourceTAZID"] = (
        pd.to_numeric(crosswalk["TAZID"], errors="coerce").round().astype("Int64")
    )
    crosswalk["CO_TAZID"] = (
        pd.to_numeric(crosswalk["CO_TAZID"], errors="coerce").round().astype("Int64")
    )
    crosswalk = crosswalk.dropna(subset=["SourceTAZID", "CO_TAZID"])
    crosswalk = crosswalk.loc[
        (crosswalk["SourceTAZID"] > 0) & (crosswalk["CO_TAZID"] > 0)
    ]
    crosswalk = crosswalk[["SourceTAZID", "CO_TAZID"]].drop_duplicates()
    if crosswalk["SourceTAZID"].duplicated().any():
        duplicates = crosswalk.loc[
            crosswalk["SourceTAZID"].duplicated(), "SourceTAZID"
        ].head(6)
        sample = ", ".join(str(int(value)) for value in duplicates)
        raise ValueError(f"{path} has duplicate TAZID crosswalk rows ({sample})")

    return crosswalk.astype({"SourceTAZID": "int32", "CO_TAZID": "int32"})


def read_vmt_base_rows(path: Path) -> pd.DataFrame:
    frames = []
    for chunk in pd.read_csv(
        path,
        usecols=VMT_INPUT_COLUMNS,
        chunksize=250_000,
        skipinitialspace=True,
    ):
        chunk.columns = [column.strip() for column in chunk.columns]
        chunk["Metric"] = chunk["Metric"].astype("string").str.strip().str.upper()
        chunk = chunk.loc[
            chunk["Metric"] == "VMT",
            ["TAZID", "Purpose", "Period", "PA", "Total"],
        ].copy()
        if chunk.empty:
            continue

        chunk["SourceTAZID"] = (
            pd.to_numeric(chunk["TAZID"], errors="coerce").round().astype("Int64")
        )
        chunk["Purpose"] = chunk["Purpose"].astype("string").str.strip()
        chunk["Period"] = chunk["Period"].astype("string").str.strip().str.upper()
        chunk["PA"] = chunk["PA"].astype("string").str.strip().str.upper()
        chunk["Total"] = pd.to_numeric(chunk["Total"], errors="coerce").fillna(0)
        chunk = chunk.dropna(subset=["SourceTAZID", "Purpose", "Period", "PA"])
        chunk = chunk.loc[chunk["SourceTAZID"] > 0]
        chunk = chunk.loc[chunk["PA"].isin(["P", "A"])]
        frames.append(chunk[["SourceTAZID", "Purpose", "Period", "PA", "Total"]])

    if not frames:
        return pd.DataFrame(columns=["SourceTAZID", "Purpose", "Period", "PA", "Total"])

    base = pd.concat(frames, ignore_index=True)
    grouped = base.groupby(
        ["SourceTAZID", "Purpose", "Period", "PA"],
        as_index=False,
        dropna=False,
    )["Total"].sum()
    grouped["SourceTAZID"] = grouped["SourceTAZID"].astype("int32")
    return grouped


def add_summary_rows(base: pd.DataFrame) -> pd.DataFrame:
    daily_by_purpose = (
        base.groupby(["CO_TAZID", "Purpose", "PurposeValue", "PA"], as_index=False)[
            "Total"
        ]
        .sum()
        .assign(Period="DY")
    )
    daily_all_purposes = (
        base.groupby(["CO_TAZID", "PA"], as_index=False)["Total"]
        .sum()
        .assign(Purpose=ALL_PURPOSE_LABEL, PurposeValue=ALL_PURPOSE_VALUE, Period="DY")
    )

    group_base = base.copy()
    group_base["PurposeGroup"] = group_base["PurposeValue"].map(purpose_group_for_value)
    group_base["PurposeValue"] = group_base["PurposeGroup"].map(
        purpose_group_total_value
    )
    group_base["Purpose"] = group_base["PurposeGroup"].map(
        {group["value"]: group["label"] for group in PURPOSE_GROUPS}
    )
    daily_by_group = (
        group_base.groupby(
            ["CO_TAZID", "PA", "Purpose", "PurposeValue"],
            as_index=False,
        )["Total"]
        .sum()
        .assign(Period="DY")
    )

    return pd.concat(
        [
            daily_by_purpose,
            daily_all_purposes,
            daily_by_group,
        ],
        ignore_index=True,
    )


def read_vmt_metrics_for_file(
    path: Path, crosswalk_path: Path, scenario_year: int, model_area: str
) -> pd.DataFrame:
    base = read_vmt_base_rows(path)
    crosswalk = read_taz_crosswalk(crosswalk_path)
    base = base.merge(crosswalk, on="SourceTAZID", how="inner", validate="m:1")
    base = base.groupby(["CO_TAZID", "Purpose", "Period", "PA"], as_index=False)[
        "Total"
    ].sum()
    base["PurposeValue"] = base["Purpose"].map(sanitize_dimension)
    long_metrics = add_summary_rows(base)
    long_metrics["ScenarioYear"] = scenario_year
    long_metrics["ModelArea"] = model_area
    long_metrics["MetricColumn"] = long_metrics.apply(
        lambda row: metric_column(row["PA"], row["Period"], row["PurposeValue"]),
        axis=1,
    )

    wide = long_metrics.pivot_table(
        index=["ScenarioYear", "ModelArea", "CO_TAZID"],
        columns="MetricColumn",
        values="Total",
        aggfunc="sum",
        fill_value=0,
    ).reset_index()
    wide.columns.name = None
    wide["ScenarioYear"] = wide["ScenarioYear"].astype("int16")
    wide["CO_TAZID"] = wide["CO_TAZID"].astype("int32")

    for column in wide.columns:
        if column not in {"ScenarioYear", "ModelArea", "CO_TAZID"}:
            wide[column] = pd.to_numeric(wide[column], errors="coerce").fillna(0)

    return wide


def read_vmt_metrics() -> pd.DataFrame:
    frames = []

    for config in get_vmt_configs():
        model_area = config["name"]
        for scenario_year in config["years"]:
            path = get_vmt_path(config, scenario_year)
            if not path.exists():
                raise FileNotFoundError(path)

            frames.append(
                read_vmt_metrics_for_file(
                    path,
                    get_taz_crosswalk_path(config, scenario_year),
                    scenario_year,
                    model_area,
                )
            )

    metrics = pd.concat(frames, ignore_index=True).fillna(0)
    metric_columns = get_metric_columns(metrics)
    first_columns = ["ScenarioYear", "ModelArea", "CO_TAZID"]
    complete_frames = []

    for config in get_vmt_configs():
        model_area = config["name"]
        model_area_ids = get_model_area_taz_ids(config)
        for scenario_year in config["years"]:
            existing = metrics.loc[
                (metrics["ModelArea"] == model_area)
                & (metrics["ScenarioYear"] == scenario_year),
                first_columns + metric_columns,
            ]
            scaffold = pd.DataFrame(
                {
                    "ScenarioYear": scenario_year,
                    "ModelArea": model_area,
                    "CO_TAZID": model_area_ids,
                }
            )
            complete = scaffold.merge(
                existing,
                on=first_columns,
                how="left",
                validate="1:1",
            )
            complete[metric_columns] = complete[metric_columns].fillna(0)
            complete_frames.append(complete)

    metrics = pd.concat(complete_frames, ignore_index=True)
    metrics["ScenarioYear"] = metrics["ScenarioYear"].astype("int16")
    metrics["CO_TAZID"] = metrics["CO_TAZID"].astype("int32")
    return metrics[first_columns + metric_columns].copy()


def get_metric_columns(metrics: pd.DataFrame) -> list[str]:
    return [
        column
        for column in metrics.columns
        if column not in {"ScenarioYear", "ModelArea", "CO_TAZID"}
    ]


def add_normalized_metric_columns(metrics: pd.DataFrame) -> pd.DataFrame:
    metrics = metrics.copy()
    group_columns = ["ScenarioYear", "ModelArea"]
    grouped = metrics.groupby(group_columns, sort=False)
    normalized_columns = {}

    for column in get_metric_columns(metrics):
        normal_column = f"{column}_norm"
        group_min = grouped[column].transform("min")
        group_max = grouped[column].transform("max")
        spread = group_max - group_min
        normalized_columns[normal_column] = (
            ((metrics[column] - group_min) / spread)
            .where(spread > 0, 0)
            .fillna(0)
            .astype("float32")
        )

    if normalized_columns:
        metrics = pd.concat(
            [metrics, pd.DataFrame(normalized_columns, index=metrics.index)],
            axis=1,
        )

    return metrics


def build_tile_features(
    metrics: pd.DataFrame,
    geometries: gpd.GeoDataFrame,
    warn_missing: bool = True,
) -> gpd.GeoDataFrame:
    metrics = add_normalized_metric_columns(metrics)
    metric_columns = [
        column for column in get_metric_columns(metrics) if not column.endswith("_norm")
    ]
    geometry_ids = set(geometries["CO_TAZID"].astype("int32"))
    area_frames = []

    for model_area in [config["name"] for config in get_vmt_configs()]:
        area_metrics = metrics.loc[metrics["ModelArea"] == model_area].copy()
        if area_metrics.empty:
            continue

        area_ids = (
            area_metrics[["CO_TAZID"]]
            .drop_duplicates()
            .set_index("CO_TAZID")
            .sort_index()
            .index
        )
        wide_columns = {
            "ModelArea": pd.Series(model_area, index=area_ids, dtype="object")
        }

        for scenario_year in sorted(area_metrics["ScenarioYear"].dropna().unique()):
            year_metrics = (
                area_metrics.loc[area_metrics["ScenarioYear"] == scenario_year]
                .set_index("CO_TAZID")
                .sort_index()
                .reindex(area_ids)
            )
            year_has = (
                year_metrics[metric_columns[0]].notna().astype("int8")
                if metric_columns
                else pd.Series(0, index=area_ids, dtype="int8")
            )
            for column in metric_columns:
                value_column = f"y{int(scenario_year)}_{column}"
                normal_column = f"{value_column}_norm"
                available_column = f"{value_column}_has"
                wide_columns[normal_column] = year_metrics[f"{column}_norm"]
                wide_columns[available_column] = year_has

        wide = pd.DataFrame(wide_columns, index=area_ids)

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

    return tile_gdf


def purpose_options_from_metrics(metrics: pd.DataFrame) -> list[dict]:
    purpose_values = set()
    for column in get_metric_columns(metrics):
        parts = column.split("_", 2)
        if len(parts) == 3:
            purpose_values.add(parts[2])

    raw_values = purpose_values - PURPOSE_GROUP_TOTAL_VALUES - {ALL_PURPOSE_VALUE}
    options = []
    for group in PURPOSE_GROUPS:
        group_value = group["value"]
        all_value = group["all_value"]
        if all_value in purpose_values:
            options.append(
                {
                    "value": all_value,
                    "label": "All",
                    "group": group_value,
                    "is_group_total": True,
                }
            )

        if group_value == "OTHER":
            group_values = sorted(
                value
                for value in raw_values
                if purpose_group_for_value(value) == group_value
            )
        else:
            group_values = [value for value in group["purposes"] if value in raw_values]

        options.extend(
            {
                "value": value,
                "label": value.replace("_", " "),
                "group": group_value,
                "is_group_total": False,
            }
            for value in group_values
        )

    return options


def purpose_group_options_from_metrics(metrics: pd.DataFrame) -> list[dict]:
    purpose_values = set()
    for column in get_metric_columns(metrics):
        parts = column.split("_", 2)
        if len(parts) == 3:
            purpose_values.add(parts[2])

    return [
        {
            "value": group["value"],
            "label": group["label"],
            "all_value": group["all_value"],
        }
        for group in PURPOSE_GROUPS
        if group["all_value"] in purpose_values
    ]


def period_options_from_metrics(metrics: pd.DataFrame) -> list[dict]:
    periods = set()
    for column in get_metric_columns(metrics):
        parts = column.split("_", 2)
        if len(parts) == 3:
            periods.add(parts[1])

    ordered_periods = [period for period in PERIOD_ORDER if period in periods]
    ordered_periods += sorted(
        period for period in periods if period not in PERIOD_ORDER
    )
    return [
        {
            "value": period,
            "label": PERIOD_LABELS.get(period, period),
            "title": PERIOD_TITLES.get(period, period),
            "icon": PERIOD_ICONS.get(period, "fa-clock"),
        }
        for period in ordered_periods
    ]


def build_manifest(
    metrics: pd.DataFrame,
    tile_metadata: dict,
    build_info: dict | None = None,
) -> dict:
    metric_columns = get_metric_columns(metrics)
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
        for column in metric_columns:
            ranges[key][column] = {
                "min": float(group[column].min()),
                "max": float(group[column].max()),
            }

    model_areas = [
        config["name"]
        for config in get_vmt_configs()
        if config["name"] in set(metrics["ModelArea"].dropna().unique())
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
        "metrics": metric_columns,
        "metric_dimensions": {
            "pa": PA_OPTIONS,
            "periods": period_options_from_metrics(metrics),
            "purpose_groups": purpose_group_options_from_metrics(metrics),
            "purposes": purpose_options_from_metrics(metrics),
        },
        "metric_ranges": ranges,
        "record_counts": record_counts,
        "bounds": tile_metadata["bounds"],
        "model_area_bounds": tile_metadata["model_area_bounds"],
        "model_area_feature_counts": tile_metadata["model_area_feature_counts"],
        "files": {
            "metrics": f"vmt/{METRICS_FILENAME}",
            "pmtiles": f"vmt/{FILL_PMTILES_FILENAME}",
            "boundaries_pmtiles": f"vmt/{BOUNDARY_PMTILES_FILENAME}",
        },
        "pmtiles": {
            "source_layer": PMTILES_LAYER_NAME,
            "minzoom": PMTILES_MINZOOM,
            "maxzoom": PMTILES_MAXZOOM,
            "feature_model": "wide_taz_by_model_area_year_pa_daily_purpose_normalized",
            "feature_count": int(tile_metadata["tile_features"]),
            "simplify_tolerance": TAZ_FILL_SIMPLIFY_TOLERANCE,
            "property_template": None,
            "normalized_property_template": "y{ScenarioYear}_{MetricColumn}_norm",
            "availability_property_template": "y{ScenarioYear}_{MetricColumn}_has",
            "metric_value_source": "parquet",
        },
        "boundary_pmtiles": {
            "source_layer": BOUNDARY_PMTILES_LAYER_NAME,
            "minzoom": PMTILES_MINZOOM,
            "maxzoom": BOUNDARY_PMTILES_MAXZOOM,
            "feature_count": int(tile_metadata["boundary_features"]),
            "simplify_tolerance": TAZ_BOUNDARY_SIMPLIFY_TOLERANCE,
            "simplification_method": "per_taz_boundary",
        },
        "build": build_info or {},
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


def build_processed_assets(force: bool = False) -> dict:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    validate_raw_inputs()

    existing_manifest = read_existing_manifest()
    metrics_fingerprint = build_metrics_fingerprint()
    tiles_fingerprint = build_tiles_fingerprint(metrics_fingerprint)

    if not force and existing_metrics_are_current(
        existing_manifest, metrics_fingerprint
    ):
        metrics = read_processed_metrics()
        metrics_status = "reused"
    else:
        metrics = read_vmt_metrics()
        write_parquet(metrics, PROCESSED_DIR / METRICS_FILENAME)
        metrics_status = "rebuilt"

    existing_tile_metadata = tile_metadata_from_manifest(existing_manifest)
    if (
        not force
        and existing_tiles_are_current(existing_manifest, tiles_fingerprint)
        and existing_tile_metadata
    ):
        tile_metadata = existing_tile_metadata
        tiles_status = "reused"
    else:
        fill_geometries = read_taz_geometries(TAZ_FILL_SIMPLIFY_TOLERANCE)
        boundary_geometries = read_taz_geometries(TAZ_BOUNDARY_SIMPLIFY_TOLERANCE)
        tile_gdf = build_tile_features(metrics, fill_geometries)
        boundary_tile_gdf = build_tile_features(
            metrics, boundary_geometries, warn_missing=False
        )
        boundary_gdf = build_boundary_features(boundary_tile_gdf)

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
        tile_metadata = tile_metadata_from_gdfs(tile_gdf, boundary_gdf)
        tiles_status = "rebuilt"

    build_info = {
        "metrics_fingerprint": metrics_fingerprint,
        "tiles_fingerprint": tiles_fingerprint,
        "metrics_build_version": METRICS_BUILD_VERSION,
        "tiles_build_version": TILES_BUILD_VERSION,
        "metrics_status": metrics_status,
        "tiles_status": tiles_status,
    }
    manifest = build_manifest(metrics, tile_metadata, build_info)
    (PROCESSED_DIR / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    return {
        "metric_rows": int(len(metrics)),
        "metric_columns": int(len(get_metric_columns(metrics))),
        "tile_features": int(tile_metadata["tile_features"]),
        "boundary_features": int(tile_metadata["boundary_features"]),
        "metrics_status": metrics_status,
        "tiles_status": tiles_status,
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
