#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import process_data_pipeline


def parse_selector_values(raw_values: list[str]) -> list[str]:
    parsed: list[str] = []
    seen: set[str] = set()
    for raw in raw_values:
        for value in next(csv.reader([raw], skipinitialspace=True), []):
            text = str(value).strip()
            if text and text not in seen:
                seen.add(text)
                parsed.append(text)
    return parsed


def main() -> int:
    parser = argparse.ArgumentParser(description="Run only preprocessing and write boilerplate JSON files.")
    parser.add_argument(
        "--config",
        default="config/processing_config.json",
        help="Path to config file (default: config/processing_config.json)",
    )
    parser.add_argument(
        "--event-id",
        action="append",
        default=[],
        help="Filter by event id (repeatable; comma-separated lists supported).",
    )
    parser.add_argument(
        "--event-title",
        action="append",
        default=[],
        help="Filter by event title (repeatable; comma-separated lists supported).",
    )
    parser.add_argument(
        "--event-url",
        action="append",
        default=[],
        help="Filter by event URL/link (repeatable; comma-separated lists supported).",
    )
    args = parser.parse_args()

    try:
        config = process_data_pipeline.load_config(Path(args.config))
        event_ids = parse_selector_values(args.event_id)
        event_titles = parse_selector_values(args.event_title)
        event_urls = parse_selector_values(args.event_url)
        if event_ids or event_titles or event_urls:
            selection_cfg = config.setdefault("selection", {})
            selection_cfg["enabled"] = True
            if event_ids:
                selection_cfg["ids"] = event_ids
            if event_titles:
                selection_cfg["titles"] = event_titles
            if event_urls:
                selection_cfg["urls"] = event_urls
        config["export"]["enabled"] = False
        written = process_data_pipeline.run_pipeline(config)
    except Exception as exc:  # pragma: no cover
        print(str(exc))
        return 1

    print("Preprocessing completed.")
    print(f"Boilerplate files: {len(written['boilerplate'])}")
    print(f"Schema boilerplate files: {len(written['schema_boilerplate'])}")
    print(f"Source schema boilerplate files: {len(written['source_schema_boilerplate'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
