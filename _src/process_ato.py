from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

os.environ.setdefault("USE_PYGEOS", "0")

import duckdb
import geopandas as gpd
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_ROOT = REPO_ROOT / "_data" / "raw"
PROCESSED_DIR = REPO_ROOT / "_data" / "processed" / "ato"
WEB_DATA_DIR = REPO_ROOT / "_site" / "public" / "data" / "ato"
SCRATCH_DIR = PROCESSED_DIR / "_scratch"

TAZ_PATH = RAW_ROOT / "statewide TAZ" / "USTM_TAZ_2021_09_22.shp"

MODEL_AREA_CONFIGS = [
    {
        "name": "Statewide",
        "folder": "0 - USTM",
        "years": [2019, 2023, 2028],
    },
    {
        "name": "Wasatch Front",
        "folder": "1 - WF",
        "years": [2019, 2023, 2028],
    },
    {
        "name": "Cache",
        "folder": "2 - CA",
        "years": [2023, 2028],
    },
    {
        "name": "Dixie",
        "folder": "3 - DX",
        "years": [2019, 2023, 2028],
    },
    {
        "name": "Summit Wasatch",
        "folder": "4 - WB",
        "years": [2019, 2023, 2028],
    },
    {
        "name": "Iron",
        "folder": "5 - IR",
        "years": [2019, 2023, 2028],
    },
]

MODEL_AREA_ORDER = [config["name"] for config in MODEL_AREA_CONFIGS]

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

PMTILES_LAYER_NAME = "ato_taz"
BOUNDARY_PMTILES_LAYER_NAME = "ato_taz_boundary"
PMTILES_MINZOOM = 0
PMTILES_MAXZOOM = 11
BOUNDARY_PMTILES_MAXZOOM = 12
TAZ_FILL_SIMPLIFY_TOLERANCE = 0.0005
TAZ_BOUNDARY_SIMPLIFY_TOLERANCE = 0.00015
METRICS_FILENAME = "ato_metrics.parquet"
FILL_PMTILES_FILENAME = "ato_taz.pmtiles"
BOUNDARY_PMTILES_FILENAME = "ato_taz_boundaries.pmtiles"


def safe_unlink(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except PermissionError:
        print(f"Warning: could not delete locked file: {path}")


def write_parquet(df: pd.DataFrame, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = output_path.with_name(f".tmp_{uuid4().hex}_{output_path.name}")
    output_sql = str(temp_path).replace("\\", "/").replace("'", "''")
    con = duckdb.connect()
    con.register("df_view", df)
    con.execute(
        f"COPY df_view TO '{output_sql}' (FORMAT PARQUET, COMPRESSION ZSTD)"
    )
    con.close()

    try:
        temp_path.replace(output_path)
    except PermissionError as error:
        try:
            shutil.copy2(temp_path, output_path)
        except PermissionError:
            if not output_path.exists():
                raise error
            print(f"Warning: kept existing locked file: {output_path}")
        else:
            safe_unlink(temp_path)


def get_ato_path(config: dict, scenario_year: int) -> Path:
    return RAW_ROOT / config["folder"] / str(scenario_year) / "Access_to_Opportunity.csv"


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
                "size_mb": round(path.stat().st_size / 1_000_000, 2) if exists else None,
            }
        )

    if missing_paths:
        missing_list = "\n".join(f"  - {path.relative_to(REPO_ROOT)}" for path in missing_paths)
        raise FileNotFoundError(f"Missing required raw input files:\n{missing_list}")

    return pd.DataFrame(records)


def read_ato_metrics() -> pd.DataFrame:
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
    metrics["SA_TAZID"] = metrics["SA_TAZID"].astype("int32")
    metrics["CO_TAZID"] = metrics["CO_TAZID"].astype("int32")

    for column in METRIC_COLUMNS:
        metrics[column] = pd.to_numeric(metrics[column], errors="coerce").fillna(0)

    return metrics


def read_taz_geometries(simplify_tolerance: float) -> gpd.GeoDataFrame:
    if not TAZ_PATH.exists():
        raise FileNotFoundError(TAZ_PATH)

    gdf = gpd.read_file(TAZ_PATH)
    gdf = gdf[["CO_TAZID", "geometry"]].copy()
    gdf = gdf.dropna(subset=["CO_TAZID", "geometry"])
    gdf = gdf[~gdf.geometry.is_empty].copy()
    gdf["CO_TAZID"] = gdf["CO_TAZID"].astype("int32")

    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:26912")
    gdf = gdf.to_crs("EPSG:4326")

    # The web map is thematic, so simplified TAZ edges are much faster while
    # still preserving the recognizable statewide TAZ pattern.
    gdf["geometry"] = gdf.geometry.simplify(
        simplify_tolerance,
        preserve_topology=True,
    )

    return gdf[["CO_TAZID", "geometry"]].copy()


def build_boundary_features(geometries: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    keep_columns = [
        "ModelArea",
        "CO_TAZID",
        *[column for column in geometries.columns if column.endswith("_has")],
        "geometry",
    ]
    boundary_gdf = geometries[keep_columns].copy()
    boundary_gdf["geometry"] = boundary_gdf.geometry.boundary
    boundary_gdf = boundary_gdf[~boundary_gdf.geometry.is_empty].copy()
    return boundary_gdf


def add_normalized_metric_columns(metrics: pd.DataFrame) -> pd.DataFrame:
    metrics = metrics.copy()
    group_columns = ["ScenarioYear", "ModelArea"]

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
            for column in METRIC_COLUMNS:
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
            tile_gdf[column] = tile_gdf[column].fillna(0).astype("float32")
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
        for column in METRIC_COLUMNS:
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
        "model_areas": model_areas,
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
        "files": {
            "metrics": f"ato/{METRICS_FILENAME}",
            "pmtiles": f"ato/{FILL_PMTILES_FILENAME}",
            "boundaries_pmtiles": f"ato/{BOUNDARY_PMTILES_FILENAME}",
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


def resolve_executable(name: str, extra_candidates: list[Path] | None = None) -> str:
    found = shutil.which(name)
    if found:
        return found

    for candidate in extra_candidates or []:
        if candidate.exists():
            return str(candidate)

    raise FileNotFoundError(
        f"Could not find {name}. Add it to PATH or update the script candidates."
    )


def find_pmtiles_exe() -> str:
    candidates = []
    env_value = os.environ.get("PMTILES_EXE")
    if env_value:
        candidates.append(Path(env_value))

    temp_dir = Path(os.environ.get("TEMP", ""))
    if temp_dir:
        candidates.append(temp_dir / "map_statewide_ato_tools" / "pmtiles.exe")

    return resolve_executable("pmtiles", candidates)


def create_pmtiles(
    tile_gdf: gpd.GeoDataFrame,
    output_path: Path,
    layer_name: str,
    maxzoom: int,
    description: str,
) -> None:
    SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
    run_scratch_dir = SCRATCH_DIR / uuid4().hex
    run_scratch_dir.mkdir(parents=True, exist_ok=True)
    geojson_path = run_scratch_dir / f"{layer_name}.geojson"
    mbtiles_path = run_scratch_dir / f"{layer_name}.mbtiles"
    pmtiles_path = run_scratch_dir / f"{layer_name}.pmtiles"

    tile_gdf.to_file(geojson_path, driver="GeoJSON")

    ogr2ogr = resolve_executable("ogr2ogr")
    subprocess.run(
        [
            ogr2ogr,
            "-f",
            "MBTiles",
            str(mbtiles_path),
            str(geojson_path),
            "-nln",
            layer_name,
            "-dsco",
            f"NAME={layer_name}",
            "-dsco",
            f"DESCRIPTION={description}",
            "-dsco",
            f"MINZOOM={PMTILES_MINZOOM}",
            "-dsco",
            f"MAXZOOM={maxzoom}",
            "-dsco",
            "MAX_SIZE=5000000",
            "-lco",
            f"NAME={layer_name}",
            "-lco",
            f"MINZOOM={PMTILES_MINZOOM}",
            "-lco",
            f"MAXZOOM={maxzoom}",
        ],
        check=True,
    )

    pmtiles = find_pmtiles_exe()
    subprocess.run(
        [pmtiles, "convert", str(mbtiles_path), str(pmtiles_path)],
        check=True,
    )

    subprocess.run([pmtiles, "verify", str(pmtiles_path)], check=True)

    try:
        shutil.copy2(pmtiles_path, output_path)
    except PermissionError:
        if not output_path.exists():
            raise
        print(f"Warning: kept existing locked PMTiles file: {output_path}")

    try:
        shutil.rmtree(run_scratch_dir)
    except PermissionError:
        print(f"Warning: could not delete locked scratch folder: {run_scratch_dir}")


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
    fill_geometries = read_taz_geometries(TAZ_FILL_SIMPLIFY_TOLERANCE)
    boundary_geometries = read_taz_geometries(TAZ_BOUNDARY_SIMPLIFY_TOLERANCE)
    tile_gdf = build_tile_features(metrics, fill_geometries)
    boundary_tile_gdf = build_tile_features(metrics, boundary_geometries, warn_missing=False)
    boundary_gdf = build_boundary_features(boundary_tile_gdf)

    write_parquet(metrics, PROCESSED_DIR / METRICS_FILENAME)
    create_pmtiles(
        tile_gdf,
        PROCESSED_DIR / FILL_PMTILES_FILENAME,
        PMTILES_LAYER_NAME,
        PMTILES_MAXZOOM,
        "Access to Opportunity by model area TAZ",
    )
    create_pmtiles(
        boundary_gdf,
        PROCESSED_DIR / BOUNDARY_PMTILES_FILENAME,
        BOUNDARY_PMTILES_LAYER_NAME,
        BOUNDARY_PMTILES_MAXZOOM,
        "Access to Opportunity TAZ boundaries",
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


def print_processed_summary(summary: dict) -> None:
    print(f"Wrote {summary['metric_rows']:,} metric rows")
    print(f"Wrote {summary['tile_features']:,} simplified PMTiles features")
    print(f"Wrote {summary['boundary_features']:,} boundary PMTiles features")
    print(f"Processed output: {summary['processed_dir']}")


def print_publish_summary(summary: dict) -> None:
    print(f"Web output: {summary['web_data_dir']}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Build and publish ATO data artifacts for the Vite web app."
    )
    parser.add_argument(
        "--processed-only",
        action="store_true",
        help=(
            "Build canonical outputs in _data/processed/ato without copying "
            "them to _site/public/data/ato."
        ),
    )
    parser.add_argument(
        "--publish-only",
        action="store_true",
        help="Copy existing processed outputs into _site/public/data/ato without rebuilding them.",
    )
    args = parser.parse_args(argv)

    if args.processed_only and args.publish_only:
        raise ValueError("Use either --processed-only or --publish-only, not both.")

    if args.publish_only:
        print_publish_summary(publish_web_assets())
        return

    processed_summary = build_processed_assets()
    print_processed_summary(processed_summary)

    if not args.processed_only:
        print_publish_summary(publish_web_assets())


if __name__ == "__main__":
    main()
