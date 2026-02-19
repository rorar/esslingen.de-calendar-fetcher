#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Callable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import process_data_pipeline

ValidateFunc = Callable[[dict[str, Any]], Any]


def load_frictionless_validate() -> ValidateFunc:
    try:
        from frictionless import validate  # type: ignore
    except Exception as exc:
        raise RuntimeError(
            "frictionless ist nicht installiert. "
            "Installiere es mit: .venv/bin/python -m pip install frictionless"
        ) from exc
    return validate


def collect_csv_files(output_dir: Path, patterns: list[str], recursive: bool = False) -> list[Path]:
    files: list[Path] = []
    for pattern in patterns:
        if recursive:
            files.extend(path for path in output_dir.rglob(pattern) if path.is_file())
        else:
            files.extend(path for path in output_dir.glob(pattern) if path.is_file())

    deduped: list[Path] = []
    seen: set[Path] = set()
    for path in sorted(files):
        if path not in seen:
            seen.add(path)
            deduped.append(path)
    return deduped


def resolve_expected_headers(config: dict[str, Any], output_dir: Path) -> list[str]:
    fields, field_map = process_data_pipeline.resolve_export_layout(config, output_dir)
    if not fields:
        return []
    return [field_map.get(field, field) for field in fields]


def to_resource_descriptor(
    csv_file: Path,
    dialect: dict[str, Any] | None,
    encoding: str,
    expected_headers: list[str] | None = None,
) -> dict[str, Any]:
    name = csv_file.stem.lower()
    name = "".join(ch if ch.isalnum() or ch in "-._/" else "_" for ch in name).strip("._")
    if not name:
        name = "resource"

    descriptor: dict[str, Any] = {
        "name": name,
        "type": "table",
        "path": str(csv_file),
        "scheme": "file",
        "format": "csv",
        "encoding": encoding,
    }
    if dialect:
        descriptor["dialect"] = dict(dialect)

    if expected_headers:
        descriptor["schema"] = {
            "fields": [{"name": header, "type": "string"} for header in expected_headers],
        }

    return descriptor


def _attr(value: Any, *names: str) -> Any:
    for name in names:
        if isinstance(value, dict) and name in value:
            return value[name]
        if hasattr(value, name):
            return getattr(value, name)
    return None


def report_is_valid(report: Any) -> bool:
    valid = _attr(report, "valid")
    return bool(valid)


def report_errors(report: Any) -> list[str]:
    lines: list[str] = []

    report_level_errors = _attr(report, "errors")
    if isinstance(report_level_errors, list):
        for err in report_level_errors:
            code = str(_attr(err, "code") or "error")
            message = str(_attr(err, "message", "note", "description") or str(err))
            lines.append(f"{code}: {message}")

    tasks = _attr(report, "tasks")
    if not isinstance(tasks, list):
        return lines

    for task in tasks:
        errors = _attr(task, "errors")
        if not isinstance(errors, list):
            continue
        for err in errors:
            code = str(_attr(err, "code") or "error")
            message = str(_attr(err, "message", "note", "description") or str(err))
            row_number = _attr(err, "row_number", "rowNumber")
            field_name = _attr(err, "field_name", "fieldName")

            prefix_parts: list[str] = []
            if row_number not in {None, ""}:
                prefix_parts.append(f"row={row_number}")
            if field_name not in {None, ""}:
                prefix_parts.append(f"field={field_name}")
            prefix = f"[{', '.join(prefix_parts)}] " if prefix_parts else ""
            lines.append(f"{prefix}{code}: {message}")
    return lines


def lint_csv_file(
    csv_file: Path,
    validate_func: ValidateFunc,
    dialect: dict[str, Any] | None,
    encoding: str,
    expected_headers: list[str] | None = None,
    fallback_dialect: dict[str, Any] | None = None,
) -> tuple[bool, list[str]]:
    descriptor = to_resource_descriptor(csv_file, dialect, encoding, expected_headers)
    report = validate_func(descriptor)
    if report_is_valid(report):
        return True, []

    primary_errors = report_errors(report)
    if fallback_dialect:
        fallback_descriptor = to_resource_descriptor(csv_file, fallback_dialect, encoding, expected_headers)
        fallback_report = validate_func(fallback_descriptor)
        if report_is_valid(fallback_report):
            return True, []
        fallback_errors = report_errors(fallback_report)
        if fallback_errors:
            return False, fallback_errors

    return False, primary_errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Lint CSV exports using Frictionless.")
    parser.add_argument(
        "--config",
        default="config/processing_config.json",
        help="Path to processing config (default: config/processing_config.json)",
    )
    parser.add_argument(
        "--output-dir",
        default="",
        help="Directory to scan for CSV files (default: export.output_dir from config)",
    )
    parser.add_argument(
        "--pattern",
        action="append",
        default=[],
        help="Glob pattern for CSV files (can be used multiple times, default: *.csv)",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Search CSV files recursively in --output-dir.",
    )
    parser.add_argument(
        "--csv-file",
        action="append",
        default=[],
        help="Explicit CSV file path (can be used multiple times).",
    )
    parser.add_argument(
        "--no-schema-check",
        action="store_true",
        help="Skip expected-header check derived from config/schema boilerplate.",
    )
    parser.add_argument(
        "--schema-check",
        action="store_true",
        help="Enable expected-header check derived from config/schema boilerplate.",
    )
    parser.add_argument(
        "--strict-config",
        action="store_true",
        help="Use config CSV dialect strictly (delimiter/encoding) and enable schema-check.",
    )
    args = parser.parse_args()

    try:
        validate_func = load_frictionless_validate()
    except RuntimeError as exc:
        print(str(exc))
        return 2

    try:
        config = process_data_pipeline.load_config(Path(args.config))
    except Exception as exc:
        print(str(exc))
        return 2

    output_dir = Path(args.output_dir) if args.output_dir else Path(str(config["export"]["output_dir"]))
    patterns = args.pattern or ["*.csv"]

    csv_files: list[Path]
    if args.csv_file:
        csv_files = [Path(path) for path in args.csv_file]
    else:
        csv_files = collect_csv_files(output_dir, patterns, recursive=args.recursive)

    if not csv_files:
        print(f"Keine CSV-Dateien gefunden (output_dir={output_dir}, pattern={patterns})")
        return 1

    for csv_file in csv_files:
        if not csv_file.exists():
            print(f"CSV-Datei nicht gefunden: {csv_file}")
            return 1

    schema_check = bool(args.schema_check or args.strict_config)
    if args.no_schema_check:
        schema_check = False

    expected_headers: list[str] | None = None
    if schema_check:
        expected_headers = resolve_expected_headers(config, output_dir)

    export_cfg = config.get("export", {})
    csv_cfg = export_cfg.get("csv", {})
    config_dialect: dict[str, Any] = {
        "delimiter": str(csv_cfg.get("delimiter", ";")),
        "quoteChar": str(csv_cfg.get("quotechar", '"')),
        "doubleQuote": bool(csv_cfg.get("doublequote", False)),
    }
    escape_char = csv_cfg.get("escapechar")
    if escape_char not in {None, ""}:
        config_dialect["escapeChar"] = str(escape_char)

    dialect: dict[str, Any] | None
    fallback_dialect: dict[str, Any] | None
    if args.strict_config:
        dialect = config_dialect
        fallback_dialect = None
    else:
        dialect = None
        fallback_dialect = config_dialect
    encoding = str(export_cfg.get("encoding", "utf-8"))

    has_failures = False
    for csv_file in csv_files:
        valid, errors = lint_csv_file(
            csv_file=csv_file,
            validate_func=validate_func,
            dialect=dialect,
            encoding=encoding,
            expected_headers=expected_headers,
            fallback_dialect=fallback_dialect,
        )
        if valid:
            print(f"OK   {csv_file}")
            continue

        has_failures = True
        print(f"FAIL {csv_file}")
        if errors:
            for line in errors:
                print(f"  - {line}")
        else:
            print("  - Frictionless reportete Fehler ohne Detailtext.")

    if has_failures:
        return 1

    print(f"CSV lint erfolgreich: {len(csv_files)} Datei(en) geprüft")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
