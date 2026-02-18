#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import process_data_pipeline


def main() -> int:
    parser = argparse.ArgumentParser(description="Run preprocessing plus export to output formats.")
    parser.add_argument(
        "--config",
        default="config/processing_config.json",
        help="Path to config file (default: config/processing_config.json)",
    )
    args = parser.parse_args()

    try:
        config = process_data_pipeline.load_config(Path(args.config))
        written = process_data_pipeline.run_pipeline(config)
    except Exception as exc:  # pragma: no cover
        print(str(exc))
        return 1

    print("Post-processing completed.")
    print(f"Boilerplate files: {len(written['boilerplate'])}")
    print(f"CSV files: {len(written['csv'])}")
    print(f"XML files: {len(written['xml'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
