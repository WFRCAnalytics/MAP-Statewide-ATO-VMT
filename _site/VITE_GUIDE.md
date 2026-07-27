# Quick Vite/Vue Guide

This is the short map of the new `_site` app. The main idea: Vite serves `index.html`, loads `src/main.js`, and Vue renders `src/App.vue` into the page.

- `index.html` -- The required HTML shell for the app. It has the `<div id="app"></div>` mount point where Vue places the whole interface.

- `package.json` -- Lists the app commands and JavaScript dependencies. The big commands are `npm run dev` for previewing and `npm run build` for making production files.

- `package-lock.json` -- Locks exact dependency versions so the app installs the same way next time.

- `vite.config.js` -- Vite settings. This tells Vite to use Vue, where to put built files, and how to split big map libraries into separate chunks.

- `src/main.js` -- JavaScript entry point. It creates the Vue app, imports the global CSS, registers the small tooltip helper, and mounts Vue into `#app`.

- `src/App.vue` -- Main application component. This is the hub that holds app state, connects the sidebar/map controls, initializes MapLibre, and controls map layers.

- `src/style.css` -- Global styling for the whole app. Most layout, sidebar, buttons, map controls, legend, modal, and MapLibre override styles live here.

- `src/composables/useMap.js` -- Map setup helper. It creates the MapLibre map, registers PMTiles support, adds search/zoom/location controls, and exposes small map utility functions.

- `src/composables/useAtoData.js` -- Browser data helper. It reads `manifest.json` for counts and legend ranges during normal map use. DuckDB-WASM is only started when exporting CSV data.

- `src/config/constants.js` -- Shared settings and option lists. This has map center/zoom, colors, scenario years, model areas, Jobs/HH choices, and travel modes.

- `src/config/layers.js` -- Layer toggle definitions. This is where the sidebar and floating layer panel get their labels/help text for map layers.

- `src/components/Sidebar.vue` -- Left-side control panel. It owns the visible selectors for scenario year, model area, Jobs/HH, travel mode, and layer toggles.

- `src/components/MapControls.vue` -- Top bar above the map. It contains download/map buttons, active column label, opacity slider, 3D toggle, and pinned-tooltip toggle.

- `src/components/LayerControl.vue` -- Floating layer widget on the map. It mirrors the layer toggles from the sidebar.

- `src/components/Legend.vue` -- Bottom-right map legend. It shows the current color ramp from least to most accessible.

- `src/components/SplashModal.vue` -- Opening modal. It appears when the app first loads and gives a quick intro.

- `src/components/Tooltip.vue` -- Map hover/pinned tooltip. It is ready to show `CO_TAZID` and the selected accessibility value once real data is wired in.

- `public/logo.png` -- Logo asset copied from the reference app. Files in `public` are served directly by Vite.

- `public/data/` -- Web-serving copy of selected processed data. Vite can only fetch files that are inside `_site/public`, so the processor copies deployable artifacts here from `_data/processed`.

- `public/data/ato/manifest.json` -- Small data index used by the app. It lists available scenario years, model areas, metric names, and data file paths.

- `public/data/ato/ustm_metrics.parquet` -- Processed USTM ATO values by `ScenarioYear`, `ModelArea`, and `CO_TAZID`.

- `public/data/ato/ustm_ato_taz.pmtiles` -- PMTiles vector tile archive used by MapLibre to draw simplified CO_TAZID polygons. Each tile feature is one TAZ with year-prefixed metric fields like `y2023_Job_byAuto_norm`.

- `public/data/ato/ustm_taz_boundaries.pmtiles` -- Separate PMTiles line archive for cleaner TAZ boundaries. It keeps one lightly simplified boundary feature per TAZ, which is much smaller and faster than the shared-linework experiment.

- `scripts/process_ustm_ato.py` -- Repeatable data processor. It reads raw USTM CSVs plus the statewide TAZ shapefile, simplifies TAZ geometry for web display, writes canonical processed files to `_data/processed/ato`, then copies the deployable files into `_site/public/data/ato`.

## Data Folder Roles

- `_data/raw/` -- Source model exports and shapefiles. The processor reads from here.

- `_data/processed/ato/` -- Canonical processed ATO outputs. This is the folder to trust for generated data artifacts: `manifest.json`, `ustm_metrics.parquet`, the simplified polygon PMTiles file `ustm_ato_taz.pmtiles`, and the boundary line PMTiles file `ustm_taz_boundaries.pmtiles`.

- `_site/public/data/ato/` -- Vite-serving copy. The browser fetches files from here while the app runs, but these files are copied from `_data/processed/ato`.

## How To Preview

Run this from the `_site` folder:

```powershell
npm run dev
```

Then open the URL Vite prints, usually:

```text
http://127.0.0.1:5173/
```

Do not open `index.html` with Live Server for this project. Live Server only serves static files; Vite is needed to compile Vue and bundle JavaScript dependencies.

## How To Rebuild The USTM Data

Run this from the repo root:

```powershell
& 'C:\Users\cday\Anaconda3\python.exe' '_site\scripts\process_ustm_ato.py'
```

Then restart or refresh the Vite app.

The PMTiles CLI is required for the tile conversion step. The script looks for `pmtiles` on your `PATH`; it also checks `%TEMP%\map_statewide_ato_tools\pmtiles.exe`, which is where this setup run placed the CLI.
