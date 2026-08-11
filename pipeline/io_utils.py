"""Generic mechanics shared by the ATO and VMT processors.

Nothing in this file knows about accessibility metrics or vehicle miles
traveled - it's purely: write a parquet file safely, find/run the pmtiles
and ogr2ogr executables, read+simplify the statewide TAZ geometry, and turn
polygons into boundary lines. `pipeline/ato.py` and `pipeline/vmt.py` both
call into this module instead of importing from each other.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from uuid import uuid4

import duckdb
import geopandas as gpd
import pandas as pd

from pipeline.config import PMTILES_MINZOOM, TAZ_PATH


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


def read_taz_geometries(
    simplify_tolerance: float,
    extra_columns: list[str] | None = None,
) -> gpd.GeoDataFrame:
    if not TAZ_PATH.exists():
        raise FileNotFoundError(TAZ_PATH)

    extra_columns = extra_columns or []
    keep_columns = ["CO_TAZID", *extra_columns, "geometry"]

    gdf = gpd.read_file(TAZ_PATH)
    gdf = gdf[keep_columns].copy()
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

    return gdf[keep_columns].copy()


def build_boundary_features(geometries: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    keep_columns = [
        "ModelArea",
        "GeographyType",
        "GeographyId",
        "GeographyName",
        "CO_TAZID",
        *[column for column in geometries.columns if column.endswith("_has")],
        "geometry",
    ]
    boundary_gdf = geometries[keep_columns].copy()
    boundary_gdf["geometry"] = boundary_gdf.geometry.boundary
    boundary_gdf = boundary_gdf[~boundary_gdf.geometry.is_empty].copy()
    return boundary_gdf


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
    import os

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
    scratch_dir: Path,
    layer_name: str,
    maxzoom: int,
    description: str,
) -> None:
    scratch_dir.mkdir(parents=True, exist_ok=True)
    run_scratch_dir = scratch_dir / uuid4().hex
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
