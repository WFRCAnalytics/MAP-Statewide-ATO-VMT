"""4 - Build Web Artifacts

Publishes the canonical processed ATO and VMT artifacts into the Vite app's
static data folder. Files in `_site/public/data/` are served directly by
the browser at runtime.

This step does not recompute metrics or PMTiles. Run
`scripts/02_process_ato_layers.py` and `scripts/03_process_vmt_layers.py`
first when raw data has changed.

Run with:
    uv run scripts/04_build_web_artifacts.py

After this step, the Vite app can load both ATO and VMT manifests, Parquet
metrics, and PMTiles from `_site/public/data/`.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pipeline import ato, vmt


def main() -> None:
    expected_files = [
        ato.PROCESSED_DIR / "manifest.json",
        ato.PROCESSED_DIR / ato.METRICS_FILENAME,
        ato.PROCESSED_DIR / ato.FILL_PMTILES_FILENAME,
        ato.PROCESSED_DIR / ato.BOUNDARY_PMTILES_FILENAME,
        vmt.PROCESSED_DIR / "manifest.json",
        vmt.PROCESSED_DIR / vmt.METRICS_FILENAME,
        vmt.PROCESSED_DIR / vmt.FILL_PMTILES_FILENAME,
        vmt.PROCESSED_DIR / vmt.BOUNDARY_PMTILES_FILENAME,
    ]

    missing = [path for path in expected_files if not path.exists()]
    if missing:
        missing_text = "\n".join(f"  - {path}" for path in missing)
        raise FileNotFoundError(
            f"Missing processed artifacts. Run steps 2 and 3 first.\n{missing_text}"
        )

    ato_summary = ato.publish_web_assets()
    vmt_summary = vmt.publish_web_assets()

    print(f"ATO web output: {ato_summary['web_data_dir']}")
    print(f"VMT web output: {vmt_summary['web_data_dir']}")


if __name__ == "__main__":
    main()
