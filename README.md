# MAP-Statewide-ATO-VMT

This repo creates a simple [web map](https://wfrcanalytics.github.io/MAP-Statewide-ATO-VMT/) to view the ATO and VMT data from all the models in the state.

The web application itself can be found in the `docs` folder. The ViteJS App can be found in the `_site` folder.

## Project structure

- `scripts/00_download_raw_data.py` downloads and extracts the raw data archive into `data/raw/`.
- `scripts/01_prepare_data_layers.py` checks and documents the raw inputs needed to rebuild the ATO and VMT data.
- `scripts/02_process_ato_layers.py` creates the canonical processed ATO artifacts in `data/processed/ato/`.
- `scripts/03_process_vmt_layers.py` creates the canonical processed VMT artifacts in `data/processed/vmt/`.
- `scripts/04_build_web_artifacts.py` copies the processed artifacts into `_site/public/data/ato/` and `_site/public/data/vmt/` so the browser can load them.
- `pipeline/` stores reusable data-processing code shared by the numbered scripts (`config.py` for repo paths/model areas/PMTiles settings, `io_utils.py` for parquet/PMTiles/geometry helpers, `ato.py` and `vmt.py` for the dataset-specific logic - these two don't import from each other).
- `data/raw/` stores raw model outputs and shapefiles. Large/raw files are gitignored, so a new clone needs `scripts/00_download_raw_data.py` run before processing.
- `data/processed/ato/` and `data/processed/vmt/` store canonical generated web-ready data.
- `_site/` is the Vite/Vue web app.
- `_site/public/data/ato/` and `_site/public/data/vmt/` store the browser-serving copies used by the Vite app.
- `_site/VITE_GUIDE.md` has the quick file-by-file guide for the Vite/Vue app.

## Rebuilding the data

Install [uv](https://docs.astral.sh/uv/), then set up the environment:

```bash
uv sync
```

You'll also need the `pmtiles` CLI and `ogr2ogr` (from GDAL) on your `PATH` - these aren't managed by `uv`. (`pmtiles` can instead be pointed to via a `PMTILES_EXE` env variable.)

Run the numbered scripts from the repo root, in order:

```bash
uv run scripts/00_download_raw_data.py     # downloads + extracts raw data into data/raw/
uv run scripts/01_prepare_data_layers.py   # checks raw inputs are present
uv run scripts/02_process_ato_layers.py    # builds data/processed/ato/
uv run scripts/03_process_vmt_layers.py    # builds data/processed/vmt/
uv run scripts/04_build_web_artifacts.py   # publishes both into _site/public/data/
```

The current web map uses simplified TAZ polygons in PMTiles for speed, with one vector feature per `ModelArea` + `CO_TAZID` and year-prefixed metric fields. ATO fields are built from the Access to Opportunity CSVs. VMT fields are built from the TAZ-based produced/attracted VMT CSVs for Statewide (`TAZ-Based-VMT.csv`) and Wasatch Front (`TAZ-Based Metrics.csv`), filtered to `Metric = VMT`, then summarized by produced/attracted direction, period, and purpose with Daily rollups plus Person, Truck, and Other purpose-group totals. TAZ outlines are stored in separate, lightly simplified boundary PMTiles files so the fill layers can stay faster without losing readable outlines.

## Running the web app

```bash
cd _site
npm install
npm run dev
```

`npm run dev` starts the local Vite preview server for editing. When changes are ready for GitHub Pages, build the app from `_site`:

```bash
npm run build
```

That command creates the production Vite bundle and overwrites `../docs/`, which is the branch folder GitHub Pages serves. Commit the updated `docs/` files along with the source changes.
