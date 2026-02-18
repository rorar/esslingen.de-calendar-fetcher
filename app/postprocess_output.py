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
    parser = argparse.ArgumentParser(description="Run post-processing export to output formats.")
    parser.add_argument(
        "--config",
        default="config/processing_config.json",
        help="Path to config file (default: config/processing_config.json)",
    )
    parser.add_argument(
        "--from-boilerplate",
        action="store_true",
        help=(
            "Read records from output/boilerplate/runtime-snapshots/*.json "
            "(or config input.boilerplate_*) instead of raw input files"
        ),
    )
    args = parser.parse_args()

    try:
        config = process_data_pipeline.load_config(Path(args.config))
        if args.from_boilerplate:
            config["input"]["mode"] = "boilerplate"
            config["preprocessing"]["enabled"] = False
        written = process_data_pipeline.run_pipeline(config)
    except Exception as exc:  # pragma: no cover
        print(str(exc))
        return 1

    print("Post-processing completed.")
    print(f"Boilerplate files: {len(written['boilerplate'])}")
    print(f"Schema boilerplate files: {len(written['schema_boilerplate'])}")
    print(f"Source schema boilerplate files: {len(written['source_schema_boilerplate'])}")
    print(f"Boilerplate input files: {len(written['boilerplate_input'])}")
    print(f"CSV files: {len(written['csv'])}")
    print(f"XML files: {len(written['xml'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
