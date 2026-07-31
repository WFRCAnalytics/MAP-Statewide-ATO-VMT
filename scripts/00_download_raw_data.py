# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "gdown",
#     "py7zr",
# ]
# ///

"""0 - Download Raw Data

Downloads and extracts the raw ATO/VMT source archive into `data/raw/`.
This has its own inline dependency block (gdown, py7zr) instead of living in
pyproject.toml, since those packages are only ever needed for this one-time
download step, not for the rest of the pipeline.

Run with:
    uv run scripts/00_download_raw_data.py
"""

import os
import shutil
from pathlib import Path

import gdown
import py7zr

REPO_ROOT = Path(__file__).resolve().parents[1]


def main():
    output_dir = REPO_ROOT / "data" / "raw"
    archive_path = output_dir / "data.7z"
    file_id = "18zbkN9Ph-eW4mTpz_JYveyB1bsbDTFVV"

    # 1. Create the target directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)

    # 2. Check if data already exists
    # We check if there are files other than the archive itself just in case
    if len([f for f in os.listdir(output_dir) if f != "data.7z"]) > 0:
        print(f"Data already exists in {output_dir}. Skipping download and extraction.")
    else:
        # 3. Download the .7z file
        print(f"Downloading file to {archive_path}...")
        gdown.download(id=file_id, output=str(archive_path), quiet=False)

        # 4. Extract the archive
        print("Extracting contents...")
        with py7zr.SevenZipFile(archive_path, mode="r") as z:
            z.extractall(path=output_dir)

        # 5. Clean up by removing the raw .7z file
        archive_path.unlink()

        # 6. Flatten the nested folder if the archive created data/raw/raw
        nested_dir = output_dir / "raw"
        if nested_dir.is_dir():
            print("Flattening nested directory...")
            for item in os.listdir(nested_dir):
                shutil.move(str(nested_dir / item), str(output_dir))
            nested_dir.rmdir()  # Remove the now-empty inner 'raw' folder

        print("Extraction and cleanup complete!")

    # 7. Verify and list the extracted files
    print(f"\nCurrent contents of {output_dir}:")
    for file in os.listdir(output_dir):
        print(f" - {file}")


if __name__ == "__main__":
    main()
