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
RATE_BASE_OPTIONS = [
    {"value": "TOTAL", "label": "Total VMT", "suffix": ""},
    {"value": "PER_HH", "label": "Per Household", "suffix": "__PER_HH"},
    {"value": "PER_JOB", "label": "Per Job", "suffix": "__PER_JOB"},
    {"value": "PER_HHEQ", "label": "Per HH Equivalent", "suffix": "__PER_HHEQ"},
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
GEOGRAPHY_TYPES = ["TAZ", "CITY"]
GEOGRAPHY_LABELS = {
    "TAZ": "TAZ",
    "CITY": "City",
}
GEOGRAPHY_SOURCE_COLUMNS = {
    "CITY": "CITY_NAME",
}
ALL_PURPOSE_VALUE = "ALL"
ALL_PURPOSE_LABEL = "All Purposes"
SOCIO_HH_COLUMN = "TOTHH"
SOCIO_JOB_COLUMN = "TOTEMP"
SOCIO_HHEQ_COLUMN = "HH_EQUIV"
SOCIO_COLUMNS = [SOCIO_HH_COLUMN, SOCIO_JOB_COLUMN, SOCIO_HHEQ_COLUMN]
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
RATE_BASE_SUFFIXES = {
    option["value"]: option["suffix"] for option in RATE_BASE_OPTIONS
}
RATE_BASE_VALUES = [option["value"] for option in RATE_BASE_OPTIONS]

PMTILES_LAYER_NAME = "vmt_taz"
BOUNDARY_PMTILES_LAYER_NAME = "vmt_taz_boundary"
METRICS_FILENAME = "vmt_metrics.parquet"
FILL_PMTILES_FILENAME = "vmt_taz.pmtiles"
BOUNDARY_PMTILES_FILENAME = "vmt_taz_boundaries.pmtiles"
METRICS_BUILD_VERSION = 6
TILES_BUILD_VERSION = 9
VMT_FILL_SIMPLIFY_TOLERANCE = 0.0012
_MODEL_AREA_TAZ_IDS: dict[str, list[int]] = {}
_STATEWIDE_VMT_ALLOWED_IDS: set[int] | None = None


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


def get_statewide_socio_path(scenario_year: int) -> Path:
    return (
        REPO_ROOT
        / "data"
        / "raw"
        / "0 - USTM"
        / str(scenario_year)
        / f"SE_COMBINED_{scenario_year}_NOSUBAREAS.CSV"
    )


def get_wf_socio_path(scenario_year: int) -> Path:
    return (
        REPO_ROOT
        / "data"
        / "raw"
        / "1 - WF"
        / str(scenario_year)
        / "SE_File.dbf"
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
            if config["name"] == "Statewide":
                files.append(
                    {
                        "kind": "Statewide socioeconomic CSV",
                        "model_area": config["name"],
                        "scenario_year": scenario_year,
                        "path": get_statewide_socio_path(scenario_year),
                    }
                )
                files.append(
                    {
                        "kind": "Wasatch Front socioeconomic DBF",
                        "model_area": "Wasatch Front",
                        "scenario_year": scenario_year,
                        "path": get_wf_socio_path(scenario_year),
                    }
                )
            elif config["name"] == "Wasatch Front":
                files.append(
                    {
                        "kind": "Wasatch Front socioeconomic DBF",
                        "model_area": config["name"],
                        "scenario_year": scenario_year,
                        "path": get_wf_socio_path(scenario_year),
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


def rate_base_signature() -> list[dict]:
    return [
        {
            "value": option["value"],
            "suffix": option["suffix"],
        }
        for option in RATE_BASE_OPTIONS
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
            "rate_bases": rate_base_signature(),
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
            "fill_simplify_tolerance": VMT_FILL_SIMPLIFY_TOLERANCE,
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


def get_statewide_vmt_allowed_taz_ids() -> set[int]:
    global _STATEWIDE_VMT_ALLOWED_IDS
    if _STATEWIDE_VMT_ALLOWED_IDS is not None:
        return _STATEWIDE_VMT_ALLOWED_IDS

    statewide_taz = gpd.read_file(TAZ_PATH)[["CO_TAZID", "SUBAREAID"]].copy()
    statewide_taz = statewide_taz.dropna(subset=["CO_TAZID", "SUBAREAID"])
    statewide_taz["CO_TAZID"] = (
        pd.to_numeric(statewide_taz["CO_TAZID"], errors="coerce").round().astype("Int64")
    )
    statewide_taz["SUBAREAID"] = (
        pd.to_numeric(statewide_taz["SUBAREAID"], errors="coerce").round().astype("Int64")
    )
    statewide_taz = statewide_taz.dropna(subset=["CO_TAZID", "SUBAREAID"])
    statewide_taz = statewide_taz.loc[statewide_taz["SUBAREAID"].isin([0, 1])]
    _STATEWIDE_VMT_ALLOWED_IDS = {
        int(value) for value in statewide_taz["CO_TAZID"] if int(value) > 0
    }
    return _STATEWIDE_VMT_ALLOWED_IDS


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
    required_keys = [
        "bounds",
        "model_area_bounds",
        "model_area_feature_counts",
        "model_area_geography_bounds",
        "model_area_geography_feature_counts",
    ]
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
        "model_area_geography_bounds": manifest["model_area_geography_bounds"],
        "model_area_geography_feature_counts": manifest[
            "model_area_geography_feature_counts"
        ],
        "tile_features": int(pmtiles["feature_count"]),
        "boundary_features": int(boundary_pmtiles["feature_count"]),
    }


def tile_metadata_from_gdfs(
    tile_gdf: gpd.GeoDataFrame, boundary_gdf: gpd.GeoDataFrame
) -> dict:
    model_area_bounds = {}
    model_area_feature_counts = {}
    model_area_geography_bounds = {}
    model_area_geography_feature_counts = {}
    for model_area in [config["name"] for config in get_vmt_configs()]:
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

    return {
        "bounds": [float(value) for value in tile_gdf.total_bounds],
        "model_area_bounds": model_area_bounds,
        "model_area_feature_counts": model_area_feature_counts,
        "model_area_geography_bounds": model_area_geography_bounds,
        "model_area_geography_feature_counts": model_area_geography_feature_counts,
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


def metric_column_for_rate(base_column: str, rate_base: str) -> str:
    suffix = RATE_BASE_SUFFIXES.get(rate_base, "")
    return f"{base_column}{suffix}" if suffix else base_column


def split_metric_column(metric_name: str) -> tuple[str, str]:
    if "__" in metric_name:
        base_column, rate_base = metric_name.split("__", 1)
        if rate_base in RATE_BASE_VALUES:
            return base_column, rate_base
    return metric_name, "TOTAL"


def is_rate_metric_column(metric_name: str) -> bool:
    return split_metric_column(metric_name)[1] != "TOTAL"


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


def read_statewide_socio_data(path: Path) -> pd.DataFrame:
    socio = pd.read_csv(
        path,
        usecols=["CO_TAZID", "SUBAREAID", "TOTHH", "TOTEMP"],
        skipinitialspace=True,
    )
    socio["CO_TAZID"] = (
        pd.to_numeric(socio["CO_TAZID"], errors="coerce").round().astype("Int64")
    )
    socio["SUBAREAID"] = (
        pd.to_numeric(socio["SUBAREAID"], errors="coerce").round().astype("Int64")
    )
    socio[SOCIO_HH_COLUMN] = pd.to_numeric(
        socio[SOCIO_HH_COLUMN], errors="coerce"
    ).fillna(0)
    socio[SOCIO_JOB_COLUMN] = pd.to_numeric(
        socio[SOCIO_JOB_COLUMN], errors="coerce"
    ).fillna(0)
    socio = socio.dropna(subset=["CO_TAZID", "SUBAREAID"])
    socio = socio.loc[socio["CO_TAZID"] > 0].copy()
    socio["CO_TAZID"] = socio["CO_TAZID"].astype("int32")
    socio["SUBAREAID"] = socio["SUBAREAID"].astype("int16")
    return socio[["CO_TAZID", "SUBAREAID", SOCIO_HH_COLUMN, SOCIO_JOB_COLUMN]]


def read_wf_socio_data(path: Path) -> pd.DataFrame:
    socio = gpd.read_file(path)[["CO_TAZID", "SUBAREAID", "TOTHH", "TOTEMP"]].copy()
    socio["CO_TAZID"] = (
        pd.to_numeric(socio["CO_TAZID"], errors="coerce").round().astype("Int64")
    )
    socio["SUBAREAID"] = (
        pd.to_numeric(socio["SUBAREAID"], errors="coerce").round().astype("Int64")
    )
    socio[SOCIO_HH_COLUMN] = pd.to_numeric(
        socio[SOCIO_HH_COLUMN], errors="coerce"
    ).fillna(0)
    socio[SOCIO_JOB_COLUMN] = pd.to_numeric(
        socio[SOCIO_JOB_COLUMN], errors="coerce"
    ).fillna(0)
    socio = socio.dropna(subset=["CO_TAZID", "SUBAREAID"])
    socio = socio.loc[socio["CO_TAZID"] > 0].copy()
    socio["CO_TAZID"] = socio["CO_TAZID"].astype("int32")
    socio["SUBAREAID"] = socio["SUBAREAID"].astype("int16")
    return socio[["CO_TAZID", "SUBAREAID", SOCIO_HH_COLUMN, SOCIO_JOB_COLUMN]]


def read_socio_data(model_area: str, scenario_year: int) -> pd.DataFrame:
    if model_area == "Statewide":
        statewide = read_statewide_socio_data(get_statewide_socio_path(scenario_year))
        wf = read_wf_socio_data(get_wf_socio_path(scenario_year))
        wf = wf.drop_duplicates(subset=["CO_TAZID"], keep="last")
        statewide = statewide.merge(
            wf.rename(
                columns={
                    SOCIO_HH_COLUMN: f"{SOCIO_HH_COLUMN}_wf",
                    SOCIO_JOB_COLUMN: f"{SOCIO_JOB_COLUMN}_wf",
                }
            )[["CO_TAZID", f"{SOCIO_HH_COLUMN}_wf", f"{SOCIO_JOB_COLUMN}_wf"]],
            on="CO_TAZID",
            how="left",
            validate="1:1",
        )
        subarea_one = statewide["SUBAREAID"] == 1
        statewide.loc[subarea_one, SOCIO_HH_COLUMN] = statewide.loc[
            subarea_one, f"{SOCIO_HH_COLUMN}_wf"
        ].fillna(statewide.loc[subarea_one, SOCIO_HH_COLUMN])
        statewide.loc[subarea_one, SOCIO_JOB_COLUMN] = statewide.loc[
            subarea_one, f"{SOCIO_JOB_COLUMN}_wf"
        ].fillna(statewide.loc[subarea_one, SOCIO_JOB_COLUMN])
        socio = statewide[["CO_TAZID", SOCIO_HH_COLUMN, SOCIO_JOB_COLUMN]].copy()
    elif model_area == "Wasatch Front":
        socio = read_wf_socio_data(get_wf_socio_path(scenario_year))[
            ["CO_TAZID", SOCIO_HH_COLUMN, SOCIO_JOB_COLUMN]
        ].copy()
    else:
        raise ValueError(f"Unsupported VMT model area for socioeconomic inputs: {model_area}")

    socio[SOCIO_HHEQ_COLUMN] = socio[SOCIO_HH_COLUMN] + (0.55 * socio[SOCIO_JOB_COLUMN])
    return socio.drop_duplicates(subset=["CO_TAZID"], keep="last")


def add_summary_rows(base: pd.DataFrame) -> pd.DataFrame:
    daily_by_purpose = (
        base.groupby(["CO_TAZID", "Purpose", "PurposeValue", "PA"], as_index=False)[
            "Total"
        ]
        .sum()
        .assign(Period="DY")
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

    wide["GeographyType"] = "TAZ"
    wide["GeographyId"] = wide["CO_TAZID"].astype(str)
    wide["GeographyName"] = wide["CO_TAZID"].astype(str)
    return wide


def add_rate_metric_columns(metrics: pd.DataFrame) -> pd.DataFrame:
    metrics = metrics.copy()
    base_metric_columns = get_total_metric_columns(metrics)

    denominators = {
        "PER_HH": SOCIO_HH_COLUMN,
        "PER_JOB": SOCIO_JOB_COLUMN,
        "PER_HHEQ": SOCIO_HHEQ_COLUMN,
    }

    for base_column in base_metric_columns:
        for rate_base, denominator_column in denominators.items():
            derived_column = metric_column_for_rate(base_column, rate_base)
            denominator = pd.to_numeric(
                metrics[denominator_column], errors="coerce"
            ).fillna(0)
            numerator = pd.to_numeric(metrics[base_column], errors="coerce").fillna(0)
            metrics[derived_column] = (
                (numerator / denominator)
                .where(denominator > 0, 0)
                .replace([pd.NA, pd.NaT], 0)
                .fillna(0)
            )

    return metrics


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
    first_columns = [
        "ScenarioYear",
        "ModelArea",
        "GeographyType",
        "GeographyId",
        "GeographyName",
        "CO_TAZID",
    ]
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
                    "GeographyType": "TAZ",
                    "GeographyId": [str(value) for value in model_area_ids],
                    "GeographyName": [str(value) for value in model_area_ids],
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
            socio = read_socio_data(model_area, scenario_year)
            complete = complete.merge(socio, on="CO_TAZID", how="left", validate="1:1")
            complete[SOCIO_COLUMNS] = complete[SOCIO_COLUMNS].fillna(0)
            complete_frames.append(complete)

    metrics = pd.concat(complete_frames, ignore_index=True)
    metrics["ScenarioYear"] = metrics["ScenarioYear"].astype("int16")
    metrics["CO_TAZID"] = metrics["CO_TAZID"].astype("int32")
    apply_statewide_subarea_mask(metrics)
    metrics = add_rate_metric_columns(metrics)
    lookup = read_geography_lookup()
    geography_metric_columns = get_metric_columns(metrics)
    geography_frames = [metrics[first_columns + SOCIO_COLUMNS + geography_metric_columns].copy()]
    for geography_type in ("CITY",):
        geography_frames.append(
            aggregate_vmt_metrics_by_geography(metrics, lookup, geography_type)
        )

    return pd.concat(geography_frames, ignore_index=True)


def get_metric_columns(metrics: pd.DataFrame) -> list[str]:
    return [
        column
        for column in metrics.columns
        if column
        not in {
            "ScenarioYear",
            "ModelArea",
            "GeographyType",
            "GeographyId",
            "GeographyName",
            "CO_TAZID",
            *SOCIO_COLUMNS,
        }
    ]


def get_total_metric_columns(metrics: pd.DataFrame) -> list[str]:
    return [
        column
        for column in get_metric_columns(metrics)
        if split_metric_column(column)[1] == "TOTAL"
    ]


def aggregate_vmt_metrics_by_geography(
    taz_metrics: pd.DataFrame,
    lookup: pd.DataFrame,
    geography_type: str,
) -> pd.DataFrame:
    source_column = GEOGRAPHY_SOURCE_COLUMNS[geography_type]
    total_metric_columns = get_total_metric_columns(taz_metrics)
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
            **{
                column: (column, "sum")
                for column in [*SOCIO_COLUMNS, *total_metric_columns]
            },
        )
    )
    aggregated["CO_TAZID"] = pd.Series(pd.NA, index=aggregated.index, dtype="Int64")
    aggregated = add_rate_metric_columns(aggregated)
    metric_columns = get_metric_columns(aggregated)
    return aggregated[
        [
            "ScenarioYear",
            "ModelArea",
            "GeographyType",
            "GeographyId",
            "GeographyName",
            "CO_TAZID",
            *SOCIO_COLUMNS,
            *metric_columns,
        ]
    ]


def apply_statewide_subarea_mask(metrics: pd.DataFrame) -> None:
    allowed_ids = get_statewide_vmt_allowed_taz_ids()
    statewide_mask = (
        (metrics["ModelArea"] == "Statewide")
        & (~metrics["CO_TAZID"].isin(allowed_ids))
    )
    if not statewide_mask.any():
        return

    metric_columns = get_metric_columns(metrics)
    metrics.loc[statewide_mask, metric_columns] = 0


def add_normalized_metric_columns(metrics: pd.DataFrame) -> pd.DataFrame:
    metrics = metrics.copy()
    group_columns = ["ScenarioYear", "ModelArea", "GeographyType"]
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
    for model_area in [config["name"] for config in get_vmt_configs()]:
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
    metric_columns = [
        column for column in get_metric_columns(metrics) if not column.endswith("_norm")
    ]
    total_metric_columns = get_total_metric_columns(metrics)
    statewide_allowed_ids = get_statewide_vmt_allowed_taz_ids()
    area_frames = []
    join_columns = ["ModelArea", "GeographyType", "GeographyId"]

    for model_area in [config["name"] for config in get_vmt_configs()]:
        for geography_type in GEOGRAPHY_TYPES:
            area_metrics = metrics.loc[
                (metrics["ModelArea"] == model_area)
                & (metrics["GeographyType"] == geography_type)
            ].copy()
            if area_metrics.empty:
                continue

            geography_index = (
                area_metrics[join_columns]
                .drop_duplicates(subset=join_columns)
                .set_index(join_columns)
                .sort_index()
            )
            wide_columns = {}

            for scenario_year in sorted(area_metrics["ScenarioYear"].dropna().unique()):
                year_metrics = (
                    area_metrics.loc[area_metrics["ScenarioYear"] == scenario_year]
                    .set_index(join_columns)
                    .sort_index()
                    .reindex(geography_index.index)
                )
                year_has = (
                    year_metrics[metric_columns[0]].notna().astype("int8")
                    if metric_columns
                    else pd.Series(0, index=geography_index.index, dtype="int8")
                )
                for socio_column in SOCIO_COLUMNS:
                    wide_columns[f"y{int(scenario_year)}_{socio_column}"] = year_metrics[socio_column]
                for column in metric_columns:
                    value_column = f"y{int(scenario_year)}_{column}"
                    normal_column = f"{value_column}_norm"
                    available_column = f"{value_column}_has"
                    wide_columns[value_column] = year_metrics[column]
                    wide_columns[normal_column] = year_metrics[f"{column}_norm"]
                    wide_columns[available_column] = year_has

            wide = pd.concat(
                [geography_index, pd.DataFrame(wide_columns, index=geography_index.index)],
                axis=1,
            ).reset_index()

            area_geometry = geometries.loc[
                (geometries["ModelArea"] == model_area)
                & (geometries["GeographyType"] == geography_type)
            ].copy()
            missing_ids = sorted(
                set(wide["GeographyId"]) - set(area_geometry["GeographyId"])
            )
            if warn_missing and missing_ids:
                sample = ", ".join(str(value) for value in missing_ids[:6])
                print(
                    f"Warning: {model_area} {geography_type} has "
                    f"{len(missing_ids):,} geography values without geometry ({sample})"
                )

            area_gdf = area_geometry.merge(
                wide,
                on=join_columns,
                how="inner",
                validate="1:1",
            )
            area_gdf["StatewideVmtMasked"] = (
                (area_gdf["ModelArea"] == "Statewide")
                & (area_gdf["GeographyType"] == "TAZ")
                & (~area_gdf["CO_TAZID"].isin(statewide_allowed_ids))
            ).astype("int8")
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
            tile_gdf[column] = tile_gdf[column].fillna(0).astype("float32").round(2)
        elif column.startswith("y"):
            metric_name = column.split("_", 1)[1] if "_" in column else column
            numeric = pd.to_numeric(tile_gdf[column], errors="coerce").fillna(0)
            if is_rate_metric_column(metric_name):
                tile_gdf[column] = numeric.astype("float32").round(2)
            else:
                tile_gdf[column] = numeric.round().astype("int32")

    return tile_gdf


def slim_fill_tile_features(tile_gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    keep_columns = [
        "ModelArea",
        "GeographyType",
        "GeographyId",
        "StatewideVmtMasked",
        *[
            column
            for column in tile_gdf.columns
            if column.startswith("y")
            and (
                column.split("_", 1)[1] in SOCIO_COLUMNS
                or split_metric_column(column.split("_", 1)[1])[1] == "TOTAL"
            )
            and not column.endswith("_norm")
            and not column.endswith("_has")
        ],
        "geometry",
    ]
    return tile_gdf[keep_columns].copy()


def purpose_options_from_metrics(metrics: pd.DataFrame) -> list[dict]:
    purpose_values = set()
    for column in get_metric_columns(metrics):
        base_column, _ = split_metric_column(column)
        parts = base_column.split("_", 2)
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
        base_column, _ = split_metric_column(column)
        parts = base_column.split("_", 2)
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
        base_column, _ = split_metric_column(column)
        parts = base_column.split("_", 2)
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

    for (scenario_year, model_area, geography_type), group in metrics.groupby(
        ["ScenarioYear", "ModelArea", "GeographyType"],
        sort=True,
    ):
        key = f"{int(scenario_year)}|{model_area}|{geography_type}"
        record_counts[key] = int(group["GeographyId"].nunique())
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
        "geography_types": GEOGRAPHY_TYPES,
        "scenario_years": sorted(
            int(year) for year in metrics["ScenarioYear"].dropna().unique()
        ),
        "scenario_years_by_model_area": scenario_years_by_model_area,
        "metrics": metric_columns,
        "metric_dimensions": {
            "pa": PA_OPTIONS,
            "rate_bases": RATE_BASE_OPTIONS,
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
            "feature_model": "wide_geography_by_model_area_year_pa_daily_purpose_normalized",
            "feature_count": int(tile_metadata["tile_features"]),
            "simplify_tolerance": VMT_FILL_SIMPLIFY_TOLERANCE,
            "property_template": "y{ScenarioYear}_{MetricColumn}",
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
        fill_geometries = build_geography_geometries(
            VMT_FILL_SIMPLIFY_TOLERANCE, metrics
        )
        boundary_geometries = build_geography_geometries(
            TAZ_BOUNDARY_SIMPLIFY_TOLERANCE, metrics
        )
        tile_gdf = build_tile_features(metrics, fill_geometries)
        fill_tile_gdf = slim_fill_tile_features(tile_gdf)
        boundary_tile_gdf = build_tile_features(
            metrics, boundary_geometries, warn_missing=False
        )
        boundary_gdf = build_boundary_features(boundary_tile_gdf)

        create_pmtiles(
            fill_tile_gdf,
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
