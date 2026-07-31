"""2 - Process ATO Layers

Converts the raw ATO CSVs and statewide TAZ geometry into canonical
web-ready artifacts in `data/processed/ato/`.

This processor:
  - combines Statewide, Wasatch Front, Cache, Dixie, Summit Wasatch, and
    Iron ATO CSVs into one metrics Parquet file
  - normalizes each accessibility metric within ScenarioYear and ModelArea
  - builds simplified PMTiles polygons for the thematic fill layer
  - builds separate boundary PMTiles for readable TAZ outlines
  - writes a manifest with model-area bounds, record counts, metric ranges,
    and file paths used by the web app

Run with:
    uv run scripts/02_process_ato_layers.py

The output of this step is the source-of-truth processed ATO dataset. Pass
--publish to also copy it into the Vite app's static data folder (or run
step 4 afterward to publish both ATO and VMT together).

    uv run scripts/02_process_ato_layers.py --publish
    uv run scripts/02_process_ato_layers.py --publish-only
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pipeline import ato


def print_processed_summary(summary: dict) -> None:
    print(f"Wrote {summary['metric_rows']:,} ATO metric rows")
    print(f"Wrote {summary['tile_features']:,} simplified PMTiles features")
    print(f"Wrote {summary['boundary_features']:,} boundary PMTiles features")
    print(f"Processed output: {summary['processed_dir']}")


def print_publish_summary(summary: dict) -> None:
    print(f"Web output: {summary['webdata_dir']}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build (and optionally publish) ATO data artifacts for the Vite web app."
    )
    parser.add_argument(
        "--publish",
        action="store_true",
        help="Also copy the processed outputs into _site/public/data/ato after building them.",
    )
    parser.add_argument(
        "--publish-only",
        action="store_true",
        help="Copy existing processed outputs into _site/public/data/ato without rebuilding them.",
    )
    args = parser.parse_args()

    if args.publish_only:
        print_publish_summary(ato.publish_web_assets())
        return

    print_processed_summary(ato.build_processed_assets())

    if args.publish:
        print_publish_summary(ato.publish_web_assets())


if __name__ == "__main__":
    main()
