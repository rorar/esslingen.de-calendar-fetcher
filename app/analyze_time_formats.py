#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import process_data_pipeline as pipeline


def collect_load_data_files(structured_dir: Path, history_dir: Path) -> list[Path]:
    candidates: list[Path] = []
    if structured_dir.exists():
        candidates.extend(sorted(structured_dir.glob("loadData_*.json")))
    if history_dir.exists():
        candidates.extend(sorted(history_dir.glob("loadData_*.json")))

    deduped: list[Path] = []
    seen: set[str] = set()
    for path in candidates:
        key = str(path.resolve())
        if key not in seen:
            seen.add(key)
            deduped.append(path)
    return deduped


def safe_title(record: dict[str, Any]) -> str:
    title = str(record.get("titel", "")).strip()
    if title:
        return title
    return str(record.get("title", "")).strip()


def analyze_time_formats(files: list[Path], max_examples: int = 5) -> dict[str, Any]:
    value_stats: dict[str, dict[str, Any]] = {}
    pattern_stats: dict[str, dict[str, Any]] = {}
    total_records = 0
    non_empty_time_records = 0

    for file_path in files:
        try:
            payload = json.loads(file_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(payload, list):
            continue

        for index, item in enumerate(payload):
            if not isinstance(item, dict):
                continue
            total_records += 1
            raw_time = pipeline.normalize_time_source_text(item.get("zeit"))
            if not raw_time:
                continue

            non_empty_time_records += 1
            parsed = pipeline.parse_load_data_time(raw_time)
            format_key = pipeline.build_time_format_key(raw_time)
            recognized = bool(parsed["start_time"] or parsed["end_time"])

            value_entry = value_stats.get(raw_time)
            if value_entry is None:
                value_entry = {
                    "zeit": raw_time,
                    "count": 0,
                    "format_key": format_key,
                    "start_time": parsed["start_time"],
                    "end_time": parsed["end_time"],
                    "zeit_kommentar": parsed["zeit_kommentar"],
                    "recognized": recognized,
                    "examples": [],
                }
                value_stats[raw_time] = value_entry
            value_entry["count"] += 1
            if len(value_entry["examples"]) < max_examples:
                value_entry["examples"].append(
                    {
                        "source_file": file_path.name,
                        "index": index,
                        "id": str(item.get("id", "")).strip(),
                        "title": safe_title(item),
                    }
                )

            pattern_entry = pattern_stats.get(format_key)
            if pattern_entry is None:
                pattern_entry = {
                    "format_key": format_key,
                    "count": 0,
                    "recognized_count": 0,
                    "unrecognized_count": 0,
                    "unique_values": 0,
                    "examples": [],
                }
                pattern_stats[format_key] = pattern_entry
            pattern_entry["count"] += 1
            if recognized:
                pattern_entry["recognized_count"] += 1
            else:
                pattern_entry["unrecognized_count"] += 1
            if len(pattern_entry["examples"]) < max_examples and raw_time not in pattern_entry["examples"]:
                pattern_entry["examples"].append(raw_time)

    values = sorted(
        value_stats.values(),
        key=lambda item: (-int(item["count"]), str(item["zeit"]).casefold()),
    )
    for entry in values:
        pattern_key = str(entry["format_key"])
        if pattern_key in pattern_stats:
            pattern_stats[pattern_key]["unique_values"] += 1

    patterns = sorted(
        pattern_stats.values(),
        key=lambda item: (-int(item["count"]), str(item["format_key"]).casefold()),
    )

    unresolved_values = [entry for entry in values if not entry["recognized"]]
    recognized_values = [entry for entry in values if entry["recognized"]]

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "input_files": [str(path) for path in files],
        "file_count": len(files),
        "record_count": total_records,
        "non_empty_time_record_count": non_empty_time_records,
        "unique_time_values": len(values),
        "recognized_time_values": len(recognized_values),
        "unrecognized_time_values": len(unresolved_values),
        "format_patterns": patterns,
        "values": values,
        "unrecognized_examples": unresolved_values[:max_examples],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Analyze zeit formats from structured-data/loadData*.json and structured-data/history/loadData*.json "
            "and write a report with parser results and edge cases."
        )
    )
    parser.add_argument(
        "--structured-dir",
        default="structured-data",
        help="Structured data directory (default: structured-data)",
    )
    parser.add_argument(
        "--history-dir",
        default="structured-data/history",
        help="History directory (default: structured-data/history)",
    )
    parser.add_argument(
        "--output",
        default="structured-data/history/time_format_history.json",
        help="Output JSON report path (default: structured-data/history/time_format_history.json)",
    )
    parser.add_argument(
        "--max-examples",
        type=int,
        default=5,
        help="Maximum examples per zeit value / pattern (default: 5)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    max_examples = args.max_examples if args.max_examples > 0 else 1

    structured_dir = Path(args.structured_dir)
    history_dir = Path(args.history_dir)
    files = collect_load_data_files(structured_dir, history_dir)
    if not files:
        print("Keine loadData JSON-Dateien gefunden.")
        return 1

    report = analyze_time_formats(files, max_examples=max_examples)
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Input files: {report['file_count']}")
    print(f"Records: {report['record_count']}")
    print(f"Unique time values: {report['unique_time_values']}")
    print(f"Recognized values: {report['recognized_time_values']}")
    print(f"Unrecognized values: {report['unrecognized_time_values']}")
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
