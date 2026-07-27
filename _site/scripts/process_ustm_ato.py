from __future__ import annotations

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


REPO_ROOT = Path(__file__).resolve().parents[2]
RAW_ROOT = REPO_ROOT / "_data" / "raw"
PROCESSED_DIR = REPO_ROOT / "_data" / "processed" / "ato"
WEB_DATA_DIR = REPO_ROOT / "_site" / "public" / "data" / "ato"
SCRATCH_DIR = PROCESSED_DIR / "_scratch"

TAZ_PATH = RAW_ROOT / "statewide TAZ" / "USTM_TAZ_2021_09_22.shp"

ATO_FILES = {
    2019: RAW_ROOT / "0 - USTM" / "2019" / "Access_to_Opportunity.csv",
    2023: RAW_ROOT / "0 - USTM" / "2023" / "Access_to_Opportunity.csv",
    2028: RAW_ROOT / "0 - USTM" / "2028" / "Access_to_Opportunity.csv",
}

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

USTM_MISSING_COLUMNS = [
    "Job_byTran",
    "HH_byTran",
]

PMTILES_LAYER_NAME = "ato_taz"
BOUNDARY_PMTILES_LAYER_NAME = "ato_taz_boundary"
PMTILES_MINZOOM = 0
PMTILES_MAXZOOM = 11
BOUNDARY_PMTILES_MAXZOOM = 12
TAZ_FILL_SIMPLIFY_TOLERANCE = 0.0005
TAZ_BOUNDARY_SIMPLIFY_TOLERANCE = 0.00015


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
    except PermissionError:
        if not output_path.exists():
            raise
        print(f"Warning: kept existing locked file: {output_path}")
        safe_unlink(temp_path)


def read_ustm_metrics() -> pd.DataFrame:
    frames = []
    for scenario_year, path in ATO_FILES.items():
        if not path.exists():
            raise FileNotFoundError(path)

        df = pd.read_csv(path)
        df = df.rename(columns={"TAZID": "SA_TAZID"})
        df["ScenarioYear"] = scenario_year
        df["ModelArea"] = "Statewide"

        for column in USTM_MISSING_COLUMNS:
            if column not in df.columns:
                df[column] = 0

        keep_columns = ["ScenarioYear", "ModelArea", "CO_TAZID"] + METRIC_COLUMNS
        frames.append(df[keep_columns])

    metrics = pd.concat(frames, ignore_index=True)
    metrics["ScenarioYear"] = metrics["ScenarioYear"].astype("int16")
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
    boundary_gdf = geometries.copy()
    boundary_gdf["geometry"] = boundary_gdf.geometry.boundary
    boundary_gdf = boundary_gdf[~boundary_gdf.geometry.is_empty].copy()
    return boundary_gdf[["CO_TAZID", "geometry"]]


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
) -> gpd.GeoDataFrame:
    model_areas = sorted(metrics["ModelArea"].dropna().unique())
    if model_areas != ["Statewide"]:
        raise ValueError(
            "The current wide PMTiles prototype expects USTM Statewide data only."
        )

    metrics = add_normalized_metric_columns(metrics)
    wide = metrics[["CO_TAZID"]].drop_duplicates().set_index("CO_TAZID").sort_index()

    for scenario_year in sorted(metrics["ScenarioYear"].dropna().unique()):
        year_metrics = (
            metrics.loc[metrics["ScenarioYear"] == scenario_year]
            .set_index("CO_TAZID")
            .sort_index()
        )
        for column in METRIC_COLUMNS:
            wide[f"y{int(scenario_year)}_{column}"] = year_metrics[column]
            wide[f"y{int(scenario_year)}_{column}_norm"] = year_metrics[f"{column}_norm"]

    wide = wide.fillna(0).reset_index()
    tile_gdf = geometries.merge(wide, on="CO_TAZID", how="inner", validate="1:1")

    for column in tile_gdf.columns:
        if column.endswith("_norm"):
            tile_gdf[column] = tile_gdf[column].astype("float32")

    return tile_gdf


def build_manifest(metrics: pd.DataFrame, tile_gdf: gpd.GeoDataFrame) -> dict:
    ranges = {}
    record_counts = {}
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

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model_areas": ["Statewide"],
        "scenario_years": sorted(
            int(year) for year in metrics["ScenarioYear"].dropna().unique()
        ),
        "metrics": METRIC_COLUMNS,
        "metric_ranges": ranges,
        "record_counts": record_counts,
        "bounds": bounds,
        "files": {
            "metrics": "ato/ustm_metrics.parquet",
            "pmtiles": "ato/ustm_ato_taz.pmtiles",
            "boundaries_pmtiles": "ato/ustm_taz_boundaries.pmtiles",
        },
        "pmtiles": {
            "source_layer": PMTILES_LAYER_NAME,
            "minzoom": PMTILES_MINZOOM,
            "maxzoom": PMTILES_MAXZOOM,
            "feature_model": "wide_taz_by_year",
            "feature_count": int(len(tile_gdf)),
            "simplify_tolerance": TAZ_FILL_SIMPLIFY_TOLERANCE,
            "property_template": "y{ScenarioYear}_{MetricColumn}",
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
        "ustm_metrics.parquet",
        "ustm_ato_taz.pmtiles",
        "ustm_taz_boundaries.pmtiles",
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
        PROCESSED_DIR / "ustm_taz_geometries.parquet",
        WEB_DATA_DIR / "ustm_taz_geometries.parquet",
    ]:
        safe_unlink(obsolete)


def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    metrics = read_ustm_metrics()
    fill_geometries = read_taz_geometries(TAZ_FILL_SIMPLIFY_TOLERANCE)
    boundary_geometries = read_taz_geometries(TAZ_BOUNDARY_SIMPLIFY_TOLERANCE)
    tile_gdf = build_tile_features(metrics, fill_geometries)
    boundary_gdf = build_boundary_features(boundary_geometries)

    write_parquet(metrics, PROCESSED_DIR / "ustm_metrics.parquet")
    create_pmtiles(
        tile_gdf,
        PROCESSED_DIR / "ustm_ato_taz.pmtiles",
        PMTILES_LAYER_NAME,
        PMTILES_MAXZOOM,
        "USTM Access to Opportunity by TAZ",
    )
    create_pmtiles(
        boundary_gdf,
        PROCESSED_DIR / "ustm_taz_boundaries.pmtiles",
        BOUNDARY_PMTILES_LAYER_NAME,
        BOUNDARY_PMTILES_MAXZOOM,
        "USTM TAZ boundaries",
    )

    manifest = build_manifest(metrics, tile_gdf)
    manifest["boundary_pmtiles"]["feature_count"] = int(len(boundary_gdf))
    (PROCESSED_DIR / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    copy_web_assets()

    print(f"Wrote {len(metrics):,} metric rows")
    print(f"Wrote {len(tile_gdf):,} simplified PMTiles features")
    print(f"Wrote {len(boundary_gdf):,} boundary PMTiles features")
    print(f"Processed output: {PROCESSED_DIR}")
    print(f"Web output: {WEB_DATA_DIR}")


if __name__ == "__main__":
    main()
