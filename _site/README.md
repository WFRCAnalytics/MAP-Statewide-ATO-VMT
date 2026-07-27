# Statewide ATO Explorer

Starter Vite/Vue app for the statewide Access to Opportunities viewer.

The map shell, sidebar controls, layer toggles, MapLibre setup, PMTiles source,
and USTM ATO data loader are wired for the current prototype.

The PMTiles layer uses simplified statewide TAZ polygons for speed. Each vector
feature is one `CO_TAZID` with year-prefixed fields such as
`y2023_Job_byAuto_norm`. TAZ outlines are served from a separate, lightly
simplified boundary PMTiles file so they can remain readable without slowing
the fill layer as much.

## Run locally

```bash
npm install
npm run dev
```

## Data

Canonical processed data is written to:

```text
../_data/processed/ato/
```

The browser-serving copy lives in:

```text
public/data/ato/
```

Run `scripts/process_ustm_ato.py` from the repo root to rebuild the PMTiles,
metrics Parquet, and manifest.
