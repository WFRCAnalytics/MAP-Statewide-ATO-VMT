"""3 - Process VMT Layers

Converts the TAZ-based produced/attracted VMT CSV files into canonical
web-ready Vehicle Miles Traveled artifacts in `data/processed/vmt/`.

This processor:
  - reads Statewide `TAZ-Based-VMT.csv` and Wasatch Front
    `TAZ-Based Metrics.csv` for each available scenario year
  - filters to Metric = VMT
  - summarizes produced and attracted VMT by TAZ, period, and purpose
  - adds Daily and All Purposes rollups
  - normalizes each VMT metric within ScenarioYear and ModelArea
  - builds simplified PMTiles polygons for the thematic fill layer
  - builds separate boundary PMTiles for readable TAZ outlines
  - writes a manifest with model-area bounds, record counts, metric ranges,
    and file paths used by the web app
  - reuses existing parquet/PMTiles artifacts when source inputs and build
    settings have not changed

Run with:
    uv run scripts/03_process_vmt_layers.py

The output of this step is the source-of-truth processed VMT dataset. Pass
--publish to also copy it into the Vite app's static data folder (or run
step 4 afterward to publish both ATO and VMT together).

    uv run scripts/03_process_vmt_layers.py --publish
    uv run scripts/03_process_vmt_layers.py --publish-only
    uv run scripts/03_process_vmt_layers.py --publish --force
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pipeline import vmt


def print_processed_summary(summary: dict) -> None:
    print(
        f"{summary['metrics_status'].title()} {summary['metric_rows']:,} "
        "VMT metric rows"
    )
    print(f"Wrote {summary['metric_columns']:,} VMT metric columns")
    print(
        f"{summary['tiles_status'].title()} {summary['tile_features']:,} "
        "simplified PMTiles features"
    )
    print(
        f"{summary['tiles_status'].title()} {summary['boundary_features']:,} "
        "boundary PMTiles features"
    )
    print(f"Processed output: {summary['processed_dir']}")


def print_publish_summary(summary: dict) -> None:
    print(f"Web output: {summary['web_data_dir']}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build (and optionally publish) VMT data artifacts for the Vite web app."
    )
    parser.add_argument(
        "--publish",
        action="store_true",
        help="Also copy the processed outputs into _site/public/data/vmt after building them.",
    )
    parser.add_argument(
        "--publish-only",
        action="store_true",
        help="Copy existing processed outputs into _site/public/data/vmt without rebuilding them.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Rebuild VMT parquet and PMTiles even when cached artifacts are current.",
    )
    args = parser.parse_args()

    if args.publish_only:
        print_publish_summary(vmt.publish_web_assets())
        return

    print_processed_summary(vmt.build_processed_assets(force=args.force))

    if args.publish:
        print_publish_summary(vmt.publish_web_assets())


if __name__ == "__main__":
    main()
