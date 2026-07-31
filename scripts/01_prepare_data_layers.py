"""1 - Prepare ATO and VMT Data Layers

Checks that the raw files needed to rebuild the Access to Opportunity and
Vehicle Miles Traveled web-map data are present. This does not touch the web
app directly - it's a preflight check for the rest of the offline pipeline.

Expected raw inputs live under `data/raw/`:
  - Statewide TAZ polygons in `data/raw/statewide TAZ/`
  - ATO CSVs in `data/raw/0 - USTM/`, `1 - WF/`, `2 - CA/`, `3 - DX/`,
    `4 - WB/`, and `5 - IR/`
  - VMT `assigned_net.dbf` files in the same model-area folders/years

Run with:
    uv run scripts/01_preparedata_layers.py

If this fails, place the missing files at the paths shown in the error and
rerun this script before continuing to step 2.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pandas as pd

from pipeline import ato, vmt
from pipeline.config import RAW_ROOT


def main() -> None:
    print(f"Raw data root: {RAW_ROOT}\n")

    raw_inputs = pd.concat(
        [
            ato.validate_raw_inputs().assign(dataset="ATO"),
            vmt.validate_raw_inputs().assign(dataset="VMT"),
        ],
        ignore_index=True,
    )

    with pd.option_context("display.max_rows", None, "display.width", 120):
        print(raw_inputs)

    print(f"\nAll {len(raw_inputs)} required raw input files are present.")


if __name__ == "__main__":
    main()
