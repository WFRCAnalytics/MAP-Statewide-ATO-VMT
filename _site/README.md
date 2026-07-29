# Statewide ATO and VMT Explorer

Starter Vite/Vue app for the statewide and model-area Access to Opportunities
and Vehicle Miles Traveled viewer.

The map shell, sidebar controls, layer toggles, MapLibre setup, PMTiles source,
and ATO/VMT data loader are wired for the current prototype.

The PMTiles layer uses simplified statewide TAZ polygons for speed. Each vector
feature is one `ModelArea` + `CO_TAZID` with year-prefixed fields such as
`y2023_Job_byAuto_norm` or `y2023_DY_VMT_norm` and availability flags such as
`y2023_Job_byAuto_has`. TAZ outlines are served from separate, lightly
simplified boundary PMTiles files so they can remain readable without slowing
the fill layers as much.

## Run locally

```bash
npm install
npm run dev
```

## Data

The data pipeline lives at the repository root in the numbered Quarto files.
The Vite app only reads static artifacts; it does not run the processing code in
the browser.

Canonical processed ATO data is written by `2-process-ato-layers.qmd` to:

```text
../_data/processed/ato/
```

Canonical processed VMT data is written by `3-process-vmt-layers.qmd` to:

```text
../_data/processed/vmt/
```

The browser-serving copies are written by `4-build-web-artifacts.qmd` to:

```text
public/data/ato/
public/data/vmt/
```

Run `quarto render` from the repo root to rebuild the complete data pipeline.
