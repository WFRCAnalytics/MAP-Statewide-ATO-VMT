"""Shared constants used by both the ATO and VMT processors.

Anything that describes the *geography* of the pipeline (where raw files
live, which model areas exist, which years each model area has, and the
zoom/simplification settings used for every PMTiles layer) lives here so
`pipeline/ato.py` and `pipeline/vmt.py` don't have to agree with each other
by importing from one another.
"""

from __future__ import annotations

import os
from pathlib import Path

# geopandas/shapely warn about PyGEOS if this isn't set before geopandas is
# imported anywhere in the process, so it's set here, at the top of the
# shared config module that everything else imports first.
os.environ.setdefault("USE_PYGEOS", "0")

REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_ROOT = REPO_ROOT / "data" / "raw"

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

# PMTiles zoom levels and simplification tolerances are shared so the ATO and
# VMT layers stay visually/behaviorally consistent in the web map.
PMTILES_MINZOOM = 0
PMTILES_MAXZOOM = 10
BOUNDARY_PMTILES_MAXZOOM = 11
TAZ_FILL_SIMPLIFY_TOLERANCE = 0.00071
TAZ_BOUNDARY_SIMPLIFY_TOLERANCE = 0.00015
