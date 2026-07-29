# MAP-Statewide-ATO-VMT
This repo brings together the ATO and VMT data from all the models in the state and creates a simple web map to view the data.

Pukar recommends the following:
 - ViteJS (dashboard framework for Javascript like Shiny is for R)
 - PMTiles
 - MapLibre

A great example of how to build the map can be found studying the Housing Site Evaluator Map (wfrc.shinyapps.io/housing-site-evaluator/). It should be the reference for the style of how the web map should look, as well as the code framework and how to create the site. A few other things to note about this repo are:
 - ignore the _app folder. This is just the relic of the older version which was hosted via R Shiny
 - reference the _site folder. This is the code for the ViteJS and will give a fantastic reference for this map.

## Project structure

- `1-prepare-data-layers.qmd` checks and documents the raw inputs needed to rebuild the ATO and VMT data.
- `2-process-ato-layers.qmd` creates the canonical processed ATO artifacts in `_data/processed/ato/`.
- `3-process-vmt-layers.qmd` creates the canonical processed VMT artifacts in `_data/processed/vmt/`.
- `4-build-web-artifacts.qmd` copies the processed artifacts into `_site/public/data/ato/` and `_site/public/data/vmt/` so the browser can load them.
- `_src/` stores reusable data-processing code used by the QMD pipeline.
- `_data/raw/` stores raw model outputs and shapefiles. Large/raw files may be gitignored, so a new clone may need these files restored before processing.
- `_data/processed/ato/` and `_data/processed/vmt/` store canonical generated web-ready data.
- `_site/` is the Vite/Vue web app.
- `_site/public/data/ato/` and `_site/public/data/vmt/` store the browser-serving copies used by the Vite app.
- `_site/VITE_GUIDE.md` has the quick file-by-file guide for the Vite/Vue app.

## Rebuilding the data

Create the processing environment:

```bash
conda env create -f environment.yml
conda activate map-statewide-ato-vmt
```

The processor also needs the `pmtiles` command-line tool. It can be available on
`PATH`, pointed to with `PMTILES_EXE`, or placed at
`%TEMP%/map_statewide_ato_tools/pmtiles.exe` on Windows.

Run the numbered Quarto pipeline from the repo root:

```bash
quarto render 1-prepare-data-layers.qmd
quarto render 2-process-ato-layers.qmd
quarto render 3-process-vmt-layers.qmd
quarto render 4-build-web-artifacts.qmd
```

Or run all four in the order defined by `_quarto.yml`:

```bash
quarto render
```

The current web map uses simplified TAZ polygons in PMTiles for speed, with one
vector feature per `ModelArea` + `CO_TAZID` and year-prefixed metric fields.
ATO fields are built from the Access to Opportunity CSVs. VMT fields are summed
from each model area's `assigned_net.dbf` link records to `CO_TAZID`. TAZ
outlines are stored in separate, lightly simplified boundary PMTiles files so
the fill layers can stay faster without losing readable outlines.

## Running the web app

```bash
cd _site
npm install
npm run dev
```
