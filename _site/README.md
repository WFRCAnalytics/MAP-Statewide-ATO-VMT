# Statewide ATO Explorer

Starter Vite/Vue app for the statewide and model-area Access to Opportunities viewer.

The map shell, sidebar controls, layer toggles, MapLibre setup, PMTiles source,
and ATO data loader are wired for the current prototype.

The PMTiles layer uses simplified statewide TAZ polygons for speed. Each vector
feature is one `ModelArea` + `CO_TAZID` with year-prefixed fields such as
`y2023_Job_byAuto_norm` and availability flags such as
`y2023_Job_byAuto_has`. TAZ outlines are served from a separate, lightly
simplified boundary PMTiles file so they can remain readable without slowing
the fill layer as much.

## Run locally

```bash
npm install
npm run dev
```

## Data

The data pipeline lives at the repository root in the numbered Quarto files.
The Vite app only reads static artifacts; it does not run the processing code in
the browser.

Canonical processed data is written by `2-process-ato-layers.qmd` to:

```text
../_data/processed/ato/
```

The browser-serving copy is written by `3-build-web-artifacts.qmd` to:

```text
public/data/ato/
```

Run `quarto render` from the repo root to rebuild the complete data pipeline.
