# Statewide ATO Explorer

Starter Vite/Vue app for the statewide Access to Opportunities viewer.

This app intentionally ships with no ATO data yet. The map shell, sidebar controls,
layer toggles, MapLibre setup, and PMTiles protocol are ready for the next phase.

## Run locally

```bash
npm install
npm run dev
```

## Future PMTiles hook

When the ATO vector tiles are ready, set these environment variables before
running or building:

```bash
VITE_ATO_PMTILES_URL=/data/ato_taz.pmtiles
VITE_ATO_PMTILES_LAYER=ato_taz
```

The PMTiles source is registered in `src/composables/useMap.js` and wired in
`src/App.vue`.
