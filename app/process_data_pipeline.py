#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import html
import json
import os
import re
import xml.etree.ElementTree as ET
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

DEFAULT_CONFIG: dict[str, Any] = {
    "input": {
        "mode": "raw",
        "files": [
            "structured-data/loadData_20307012.json",
            "structured-data/jsonld_20307012_generated.json",
        ],
        "boilerplate_dir": "output/boilerplate/runtime-snapshots",
        "boilerplate_files": [],
    },
    "schema": {
        "enabled": True,
        "file": "",
        "source_boilerplates": {
            "enabled": True,
            "dir": "",
        },
    },
    "preprocessing": {
        "enabled": True,
        "text_fields": [
            "title",
            "description",
            "location_name",
            "category",
            "series",
            "time",
            "start_time",
            "end_time",
            "url",
        ],
        "remove_line_breaks_and_tabs": True,
        "remove_html_tags": True,
        "remove_html_entities": True,
        "trim_whitespace": True,
    },
    "replacements": {
        "enabled": False,
        "rules": [],
    },
    "export": {
        "enabled": True,
        "formats": ["csv", "xml"],
        "output_dir": "output",
        "encoding": "utf-8",
        "line_ending": "\n",
        "rows_per_file": {"enabled": True, "value": 1000},
        "filename_template": "{source}_{format}_{timestamp}{_part{part}}.{ext}",
        "filename_context": {},
        "date_input_formats": ["%Y-%m-%d", "%d.%m.%Y"],
        "date_output_format": "%Y-%m-%d",
        "fields": [],
        "field_mappings": {},
        "csv": {
            "delimiter": ";",
            "quotechar": '"',
            "escapechar": "\\",
            "quoting": "minimal",
            "doublequote": False,
        },
        "xml": {
            "root_tag": "events",
            "item_tag": "event",
            "include_declaration": True,
        },
    },
}

CANONICAL_SCHEMA_ID = "canonical_event_v1"
CANONICAL_SCHEMA_FIELDS: list[dict[str, Any]] = [
    {"name": "id", "label": "ID", "type": "string", "required": False},
    {"name": "title", "label": "Titel", "type": "string", "required": False},
    {"name": "start_date", "label": "Startdatum", "type": "date", "required": False},
    {"name": "end_date", "label": "Enddatum", "type": "date", "required": False},
    {"name": "time", "label": "Uhrzeit", "type": "string", "required": False},
    {"name": "start_time", "label": "Startzeit", "type": "string", "required": False},
    {"name": "end_time", "label": "Endzeit", "type": "string", "required": False},
    {"name": "description", "label": "Beschreibung", "type": "string", "required": False},
    {"name": "location_name", "label": "Ort", "type": "string", "required": False},
    {"name": "location_postal_code", "label": "PLZ", "type": "string", "required": False},
    {"name": "location_city", "label": "Stadt", "type": "string", "required": False},
    {"name": "category", "label": "Kategorie", "type": "string", "required": False},
    {"name": "series", "label": "Sammelbegriff", "type": "string", "required": False},
    {"name": "url", "label": "URL", "type": "string", "required": False},
    {"name": "source_type", "label": "QuelleTyp", "type": "string", "required": False},
    {"name": "source_file", "label": "QuelleDatei", "type": "string", "required": False},
]
CANONICAL_FIELD_ORDER = [field["name"] for field in CANONICAL_SCHEMA_FIELDS]
CANONICAL_FIELD_LABELS = {field["name"]: field["label"] for field in CANONICAL_SCHEMA_FIELDS}
REPLACEMENT_FIELD_ALIASES: dict[str, str] = {
    "location": "location_name",
    "titel": "title",
    "zeit": "time",
}


class SafeFormatDict(dict[str, Any]):
    def __missing__(self, key: str) -> str:
        return ""


def deep_merge_dict(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = deep_merge_dict(merged[key], value)
        else:
            merged[key] = value
    return merged


def parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Ungueltiger boolescher Wert: {value}")


def normalize_input_mode(input_cfg: dict[str, Any]) -> None:
    mode = str(input_cfg.get("mode", "raw")).strip().lower()
    if mode not in {"raw", "boilerplate"}:
        raise ValueError("input.mode muss 'raw' oder 'boilerplate' sein")
    input_cfg["mode"] = mode


def ensure_schema_config(config: dict[str, Any]) -> None:
    schema_cfg = config.get("schema")
    if not isinstance(schema_cfg, dict):
        schema_cfg = {}

    enabled_raw = schema_cfg.get("enabled", True)
    if isinstance(enabled_raw, str):
        enabled = parse_bool(enabled_raw)
    else:
        enabled = bool(enabled_raw)

    schema_file = str(schema_cfg.get("file", "")).strip()

    source_cfg = schema_cfg.get("source_boilerplates")
    if not isinstance(source_cfg, dict):
        source_cfg = {}

    source_enabled_raw = source_cfg.get("enabled", True)
    if isinstance(source_enabled_raw, str):
        source_enabled = parse_bool(source_enabled_raw)
    else:
        source_enabled = bool(source_enabled_raw)

    source_dir = str(source_cfg.get("dir", "")).strip()

    schema_cfg["enabled"] = enabled
    schema_cfg["file"] = schema_file
    schema_cfg["source_boilerplates"] = {
        "enabled": source_enabled,
        "dir": source_dir,
    }
    config["schema"] = schema_cfg


def ensure_rows_per_file_config(export_cfg: dict[str, Any]) -> None:
    rows_cfg = export_cfg.get("rows_per_file")

    if isinstance(rows_cfg, dict):
        enabled_raw = rows_cfg.get("enabled", True)
        value_raw = rows_cfg.get("value", 1000)
    else:
        enabled_raw = True
        value_raw = rows_cfg if rows_cfg is not None else 1000

    if isinstance(enabled_raw, str):
        enabled = parse_bool(enabled_raw)
    else:
        enabled = bool(enabled_raw)

    value = int(value_raw)
    if enabled and value <= 0:
        raise ValueError("rows_per_file.value muss > 0 sein, wenn rows_per_file.enabled=true")

    export_cfg["rows_per_file"] = {"enabled": enabled, "value": value}


def ensure_replacements_config(config: dict[str, Any]) -> None:
    replacements_cfg = config.get("replacements")
    if not isinstance(replacements_cfg, dict):
        replacements_cfg = {}

    enabled_raw = replacements_cfg.get("enabled", False)
    if isinstance(enabled_raw, str):
        enabled = parse_bool(enabled_raw)
    else:
        enabled = bool(enabled_raw)

    raw_rules = replacements_cfg.get("rules", [])
    if not isinstance(raw_rules, list):
        raise ValueError("replacements.rules muss eine Liste sein")

    normalized_rules: list[dict[str, Any]] = []
    for idx, raw_rule in enumerate(raw_rules, start=1):
        if not isinstance(raw_rule, dict):
            raise ValueError(f"replacements.rules[{idx}] muss ein Objekt sein")

        field = str(raw_rule.get("field", "")).strip()
        search = str(raw_rule.get("search", ""))
        replace = str(raw_rule.get("replace", ""))
        mode = str(raw_rule.get("mode", "exact")).strip().lower()
        case_sensitive_raw = raw_rule.get("case_sensitive", True)

        if isinstance(case_sensitive_raw, str):
            case_sensitive = parse_bool(case_sensitive_raw)
        else:
            case_sensitive = bool(case_sensitive_raw)

        if not field:
            raise ValueError(f"replacements.rules[{idx}].field darf nicht leer sein")
        if search == "":
            raise ValueError(f"replacements.rules[{idx}].search darf nicht leer sein")
        if mode not in {"exact", "contains", "regex"}:
            raise ValueError(f"replacements.rules[{idx}].mode muss exact, contains oder regex sein")
        if mode == "regex":
            try:
                re.compile(search)
            except re.error as exc:
                raise ValueError(f"Ungültiger Regex in replacements.rules[{idx}].search: {exc}") from exc

        normalized_rules.append(
            {
                "field": field,
                "search": search,
                "replace": replace,
                "mode": mode,
                "case_sensitive": case_sensitive,
            }
        )

    replacements_cfg["enabled"] = enabled
    replacements_cfg["rules"] = normalized_rules
    config["replacements"] = replacements_cfg


def parse_list(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def parse_mapping(value: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for part in parse_list(value):
        if ":" not in part:
            raise ValueError(f"Mapping ohne ':' gefunden: {part}")
        key, mapped = part.split(":", 1)
        result[key.strip()] = mapped.strip()
    return result


def decode_escapes(value: str) -> str:
    return (
        value.replace("\\r\\n", "\r\n")
        .replace("\\n", "\n")
        .replace("\\r", "\r")
        .replace("\\t", "\t")
    )


def normalize_csv_options(config: dict[str, Any]) -> None:
    csv_cfg = config["export"]["csv"]
    delimiter = str(csv_cfg.get("delimiter", ";"))
    quotechar = str(csv_cfg.get("quotechar", '"'))
    escapechar_raw = csv_cfg.get("escapechar")
    doublequote = bool(csv_cfg.get("doublequote", False))

    delimiter = decode_escapes(delimiter)
    quotechar = decode_escapes(quotechar)
    if len(delimiter) != 1:
        raise ValueError("CSV delimiter muss genau ein Zeichen sein")
    if len(quotechar) != 1:
        raise ValueError("CSV quotechar muss genau ein Zeichen sein")

    escapechar: str | None
    if escapechar_raw is None:
        escapechar = None
    else:
        escape_text = decode_escapes(str(escapechar_raw))
        if escape_text in {"", "none", "null", '""', "double"}:
            escapechar = None
            doublequote = True
        else:
            if len(escape_text) != 1:
                raise ValueError("CSV escapechar muss genau ein Zeichen sein")
            escapechar = escape_text

    csv_cfg["delimiter"] = delimiter
    csv_cfg["quotechar"] = quotechar
    csv_cfg["escapechar"] = escapechar
    csv_cfg["doublequote"] = doublequote


def apply_env_overrides(config: dict[str, Any]) -> dict[str, Any]:
    updated = deepcopy(config)
    env = os.environ
    ensure_rows_per_file_config(updated["export"])
    ensure_schema_config(updated)
    ensure_replacements_config(updated)

    if value := env.get("PROCESS_INPUT_MODE"):
        updated["input"]["mode"] = value.strip().lower()
    if value := env.get("PROCESS_INPUT_FILES"):
        updated["input"]["files"] = parse_list(value)
    if value := env.get("PROCESS_BOILERPLATE_DIR"):
        updated["input"]["boilerplate_dir"] = value
    if value := env.get("PROCESS_BOILERPLATE_FILES"):
        updated["input"]["boilerplate_files"] = parse_list(value)
    if value := env.get("PROCESS_SCHEMA_ENABLED"):
        updated["schema"]["enabled"] = parse_bool(value)
    if value := env.get("PROCESS_SCHEMA_FILE"):
        updated["schema"]["file"] = value
    if value := env.get("PROCESS_SCHEMA_SOURCE_BOILERPLATES_ENABLED"):
        updated["schema"]["source_boilerplates"]["enabled"] = parse_bool(value)
    if value := env.get("PROCESS_SCHEMA_SOURCE_BOILERPLATES_DIR"):
        updated["schema"]["source_boilerplates"]["dir"] = value

    if value := env.get("PROCESS_TEXT_FIELDS"):
        updated["preprocessing"]["text_fields"] = parse_list(value)
    if value := env.get("PROCESS_CLEAN_REMOVE_LINE_BREAKS"):
        updated["preprocessing"]["remove_line_breaks_and_tabs"] = parse_bool(value)
    if value := env.get("PROCESS_CLEAN_REMOVE_HTML_TAGS"):
        updated["preprocessing"]["remove_html_tags"] = parse_bool(value)
    if value := env.get("PROCESS_CLEAN_REMOVE_HTML_ENTITIES"):
        updated["preprocessing"]["remove_html_entities"] = parse_bool(value)
    if value := env.get("PROCESS_CLEAN_TRIM_WHITESPACE"):
        updated["preprocessing"]["trim_whitespace"] = parse_bool(value)
    if value := env.get("PROCESS_REPLACEMENTS_ENABLED"):
        updated["replacements"]["enabled"] = parse_bool(value)
    if value := env.get("PROCESS_REPLACEMENTS_RULES"):
        loaded_rules = json.loads(value)
        if not isinstance(loaded_rules, list):
            raise ValueError("PROCESS_REPLACEMENTS_RULES muss ein JSON-Array sein")
        updated["replacements"]["rules"] = loaded_rules

    if value := env.get("PROCESS_EXPORT_FORMATS"):
        updated["export"]["formats"] = [fmt.lower() for fmt in parse_list(value)]
    if value := env.get("PROCESS_EXPORT_FIELDS"):
        updated["export"]["fields"] = parse_list(value)
    if value := env.get("PROCESS_EXPORT_FIELD_MAPPINGS"):
        updated["export"]["field_mappings"] = parse_mapping(value)
    if value := env.get("PROCESS_CSV_DELIMITER"):
        updated["export"]["csv"]["delimiter"] = value
    if value := env.get("PROCESS_CSV_QUOTECHAR"):
        updated["export"]["csv"]["quotechar"] = value
    if value := env.get("PROCESS_CSV_ESCAPECHAR"):
        updated["export"]["csv"]["escapechar"] = value
    if value := env.get("PROCESS_CSV_DOUBLEQUOTE"):
        updated["export"]["csv"]["doublequote"] = parse_bool(value)
    if value := env.get("PROCESS_CSV_QUOTING"):
        updated["export"]["csv"]["quoting"] = value
    if value := env.get("PROCESS_EXPORT_ENCODING"):
        updated["export"]["encoding"] = value
    if value := env.get("PROCESS_DATE_OUTPUT_FORMAT"):
        updated["export"]["date_output_format"] = value
    if value := env.get("PROCESS_LINE_ENDING"):
        updated["export"]["line_ending"] = value
    if value := env.get("PROCESS_ROWS_PER_FILE"):
        updated["export"]["rows_per_file"]["value"] = int(value)
    if value := env.get("PROCESS_ROWS_PER_FILE_ENABLED"):
        updated["export"]["rows_per_file"]["enabled"] = parse_bool(value)
    if value := env.get("PROCESS_FILENAME_TEMPLATE"):
        updated["export"]["filename_template"] = value
    if value := env.get("PROCESS_OUTPUT_DIR"):
        updated["export"]["output_dir"] = value
    if value := env.get("PROCESS_XML_ROOT_TAG"):
        updated["export"]["xml"]["root_tag"] = value
    if value := env.get("PROCESS_XML_ITEM_TAG"):
        updated["export"]["xml"]["item_tag"] = value
    if value := env.get("PROCESS_XML_DECLARATION"):
        updated["export"]["xml"]["include_declaration"] = parse_bool(value)
    if value := env.get("PROCESS_FILENAME_CATEGORY"):
        updated["export"]["filename_context"]["category"] = value

    ensure_rows_per_file_config(updated["export"])
    ensure_schema_config(updated)
    ensure_replacements_config(updated)
    normalize_input_mode(updated["input"])
    updated["export"]["line_ending"] = decode_escapes(str(updated["export"]["line_ending"]))
    normalize_csv_options(updated)
    return updated


def load_config(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        raise FileNotFoundError(f"Konfigurationsdatei nicht gefunden: {config_path}")
    user_config = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(user_config, dict):
        raise ValueError("Konfiguration muss ein JSON-Objekt sein")

    merged = deep_merge_dict(DEFAULT_CONFIG, user_config)
    ensure_rows_per_file_config(merged["export"])
    ensure_schema_config(merged)
    ensure_replacements_config(merged)
    normalize_input_mode(merged["input"])
    return apply_env_overrides(merged)


def join_values(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        items: list[str] = []
        for entry in value:
            if isinstance(entry, dict):
                if entry.get("name"):
                    items.append(str(entry["name"]))
                elif entry.get("id"):
                    items.append(str(entry["id"]))
                else:
                    items.append(str(entry))
            else:
                items.append(str(entry))
        return " | ".join(item for item in items if item)
    return str(value)


def build_date_candidates(text: str) -> list[str]:
    raw = text.strip().replace("\xa0", " ")
    if not raw:
        return []

    out: list[str] = [raw]

    german_match = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", raw)
    if german_match:
        day, month, year = german_match.groups()
        out.append(f"{int(day):02d}.{int(month):02d}.{year}")

    iso_match = re.search(r"(\d{4}-\d{2}-\d{2})", raw)
    if iso_match:
        out.append(iso_match.group(1))

    deduped: list[str] = []
    seen: set[str] = set()
    for item in out:
        if item not in seen:
            seen.add(item)
            deduped.append(item)
    return deduped


def format_date(value: Any, input_formats: list[str], output_format: str) -> str:
    text = join_values(value).strip()
    if not text:
        return ""

    candidates = build_date_candidates(text)
    for candidate in candidates:
        for fmt in input_formats:
            try:
                dt = datetime.strptime(candidate, fmt)
                return dt.strftime(output_format)
            except ValueError:
                continue

    for candidate in candidates:
        try:
            dt = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
            return dt.strftime(output_format)
        except ValueError:
            continue

    return text


def parse_time_fragment(value: str) -> str | None:
    text = value.strip()
    match = re.fullmatch(r"(\d{1,2})(?::(\d{1,2}))?", text)
    if not match:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2) or "0")
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        return None
    return f"{hour:02d}:{minute:02d}"


def normalize_time_text(value: Any) -> str:
    text = join_values(value).strip()
    if not text:
        return ""

    text = text.replace("–", "-").replace("—", "-")
    text = re.sub(r"\s*uhr\b", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"\s+", " ", text)

    range_parts = re.split(r"\s*-\s*|\s+bis\s+", text, maxsplit=1, flags=re.IGNORECASE)
    if len(range_parts) == 2:
        start = parse_time_fragment(range_parts[0])
        end = parse_time_fragment(range_parts[1])
        if start and end:
            return f"{start}-{end}"

    normalized = parse_time_fragment(text)
    return normalized if normalized else text


def extract_time_from_datetime(value: Any) -> str:
    text = join_values(value).strip()
    if not text:
        return ""

    # Date-only values (e.g. 2026-03-08) must stay time-empty.
    if not re.search(r"[T ]\d{1,2}:\d{2}", text):
        return ""

    time_match = re.search(r"[T ](\d{1,2}):(\d{2})", text)
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return dt.strftime("%H:%M")
    except ValueError:
        if time_match:
            return f"{int(time_match.group(1)):02d}:{time_match.group(2)}"
        return ""


def split_time_range(value: str) -> tuple[str, str]:
    text = str(value).strip()
    if not text:
        return "", ""

    exact_range = re.fullmatch(r"(\d{2}:\d{2})-(\d{2}:\d{2})", text)
    if exact_range:
        return exact_range.group(1), exact_range.group(2)

    single = parse_time_fragment(text)
    if single:
        return single, ""

    # Fallback: extract first 1-2 time-like fragments from free text.
    # Example: "ab 18:00 bis 20:00" -> 18:00 / 20:00
    matches = re.findall(r"\b(\d{1,2}):(\d{2})\b", text)
    parsed: list[str] = []
    for hour, minute in matches:
        fragment = parse_time_fragment(f"{hour}:{minute}")
        if fragment:
            parsed.append(fragment)

    if len(parsed) >= 2:
        return parsed[0], parsed[1]
    if len(parsed) == 1:
        return parsed[0], ""
    return "", ""


def compose_time_value(start_time: str, end_time: str) -> str:
    if start_time and end_time:
        if start_time == end_time:
            return start_time
        return f"{start_time}-{end_time}"
    if start_time:
        return start_time
    if end_time:
        return end_time
    return ""


def detect_source_type(record: dict[str, Any]) -> str:
    if "@type" in record or "@context" in record or ("startDate" in record and "name" in record):
        return "jsonld"
    return "loadData"


def normalize_record(record: dict[str, Any], source_file: str, config: dict[str, Any]) -> dict[str, str]:
    source_type = detect_source_type(record)
    date_input_formats = config["export"]["date_input_formats"]
    date_output_format = config["export"]["date_output_format"]

    if source_type == "jsonld":
        location = record.get("location")
        address = location.get("address", {}) if isinstance(location, dict) else {}
        start_time = extract_time_from_datetime(record.get("startDate"))
        end_time = extract_time_from_datetime(record.get("endDate"))
        return {
            "id": join_values(record.get("identifier") or record.get("@id")),
            "title": join_values(record.get("name")),
            "start_date": format_date(record.get("startDate"), date_input_formats, date_output_format),
            "end_date": format_date(record.get("endDate"), date_input_formats, date_output_format),
            "time": compose_time_value(start_time, end_time),
            "start_time": start_time,
            "end_time": end_time,
            "description": join_values(record.get("description")),
            "location_name": join_values(location.get("name") if isinstance(location, dict) else location),
            "location_postal_code": join_values(address.get("postalCode") if isinstance(address, dict) else ""),
            "location_city": join_values(address.get("addressLocality") if isinstance(address, dict) else ""),
            "category": join_values(record.get("eventType")),
            "series": "",
            "url": join_values(record.get("url")),
            "source_type": source_type,
            "source_file": source_file,
        }

    normalized_time = normalize_time_text(record.get("zeit"))
    start_time, end_time = split_time_range(normalized_time)

    return {
        "id": join_values(record.get("id")),
        "title": join_values(record.get("titel")),
        "start_date": format_date(record.get("von"), date_input_formats, date_output_format),
        "end_date": format_date(record.get("bis") or record.get("von"), date_input_formats, date_output_format),
        "time": normalized_time,
        "start_time": start_time,
        "end_time": end_time,
        "description": join_values(record.get("beschreibung") or record.get("kurzbeschreibung")),
        "location_name": join_values(record.get("location")),
        "location_postal_code": join_values(record.get("location_plz")),
        "location_city": join_values(record.get("location_ortsname")),
        "category": join_values(record.get("kategorie") or record.get("kat")),
        "series": join_values(record.get("sammel")),
        "url": join_values(record.get("link_url")),
        "source_type": source_type,
        "source_file": source_file,
    }


def clean_text(value: str, config: dict[str, Any]) -> str:
    out = value
    if config.get("remove_html_entities", True):
        out = html.unescape(out)
    if config.get("remove_html_tags", True):
        out = re.sub(r"<[^>]+>", " ", out)
    if config.get("remove_line_breaks_and_tabs", True):
        out = re.sub(r"[\r\n\t]+", " ", out)
    out = re.sub(r"[ ]{2,}", " ", out)
    if config.get("trim_whitespace", True):
        out = out.strip()
    return out


def apply_replacement_to_text(
    value: str,
    search: str,
    replace: str,
    mode: str,
    case_sensitive: bool,
) -> tuple[str, int]:
    if mode == "exact":
        if case_sensitive:
            if value == search:
                return replace, 1
            return value, 0
        if value.casefold() == search.casefold():
            return replace, 1
        return value, 0

    if mode == "contains":
        if case_sensitive:
            hits = value.count(search)
            if hits == 0:
                return value, 0
            return value.replace(search, replace), hits
        pattern = re.compile(re.escape(search), flags=re.IGNORECASE)
        return pattern.subn(replace, value)

    flags = 0 if case_sensitive else re.IGNORECASE
    return re.subn(search, replace, value, flags=flags)


def apply_replacements(records: list[dict[str, str]], replacements_cfg: dict[str, Any]) -> list[dict[str, str]]:
    if not replacements_cfg.get("enabled", False):
        return records

    rules = replacements_cfg.get("rules", [])
    if not isinstance(rules, list) or not rules:
        return records

    updated_records: list[dict[str, str]] = []
    for record in records:
        updated = dict(record)

        for rule in rules:
            if not isinstance(rule, dict):
                continue

            field = str(rule.get("field", "")).strip()
            search = str(rule.get("search", ""))
            replace = str(rule.get("replace", ""))
            mode = str(rule.get("mode", "exact")).strip().lower()
            case_sensitive = bool(rule.get("case_sensitive", True))
            if not field or search == "":
                continue

            candidate_fields = [field]
            alias = REPLACEMENT_FIELD_ALIASES.get(field)
            if alias and alias not in candidate_fields:
                candidate_fields.append(alias)

            for candidate in candidate_fields:
                value = updated.get(candidate)
                if not isinstance(value, str):
                    continue
                new_value, hits = apply_replacement_to_text(value, search, replace, mode, case_sensitive)
                if hits > 0:
                    updated[candidate] = new_value
                break

        updated_records.append(updated)

    return updated_records


def preprocess_records(records: list[dict[str, str]], preprocess_cfg: dict[str, Any]) -> list[dict[str, str]]:
    if not preprocess_cfg.get("enabled", True):
        return records

    fields = [str(field).strip() for field in preprocess_cfg.get("text_fields", []) if str(field).strip()]
    process_all = "*" in fields
    cleaned_records: list[dict[str, str]] = []

    for record in records:
        cleaned = dict(record)
        target_fields = list(cleaned.keys()) if process_all else fields
        for field in target_fields:
            value = cleaned.get(field)
            if isinstance(value, str):
                cleaned[field] = clean_text(value, preprocess_cfg)
        cleaned_records.append(cleaned)

    return cleaned_records


def read_json_record_list(input_file: Path) -> list[dict[str, Any]]:
    payload = json.loads(input_file.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"Unerwartete JSON-Struktur (Liste erwartet): {input_file}")
    return [item for item in payload if isinstance(item, dict)]


def normalize_source_records(
    raw_records: list[dict[str, Any]], source_file: str, config: dict[str, Any]
) -> list[dict[str, str]]:
    normalized = [normalize_record(item, source_file, config) for item in raw_records]
    preprocessed = preprocess_records(normalized, config["preprocessing"])
    return apply_replacements(preprocessed, config.get("replacements", {}))


def read_source_records(input_file: Path, config: dict[str, Any]) -> list[dict[str, str]]:
    raw_records = read_json_record_list(input_file)
    return normalize_source_records(raw_records, input_file.name, config)


def read_boilerplate_records(boilerplate_file: Path) -> tuple[str, list[dict[str, Any]]]:
    payload = json.loads(boilerplate_file.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Unerwartete Boilerplate-Struktur (Objekt erwartet): {boilerplate_file}")

    records = payload.get("records")
    if not isinstance(records, list):
        raise ValueError(f"Unerwartete Boilerplate-Struktur ('records' Liste erwartet): {boilerplate_file}")

    source_name = str(payload.get("source", "")).strip()
    if not source_name:
        source_name = boilerplate_file.stem.removeprefix("boilerplate_")

    safe_records = [dict(item) for item in records if isinstance(item, dict)]
    return source_name, safe_records


def runtime_snapshot_dir(output_dir: Path) -> Path:
    return output_dir / "boilerplate" / "runtime-snapshots"


def resolve_schema_boilerplate_file(config: dict[str, Any], output_dir: Path) -> Path:
    schema_cfg = config.get("schema", {})
    file_value = str(schema_cfg.get("file", "")).strip()
    if file_value:
        return Path(file_value)
    return output_dir / "boilerplate" / "schema-boilerplates" / f"{CANONICAL_SCHEMA_ID}.json"


def build_schema_boilerplate_payload() -> dict[str, Any]:
    return {
        "schema_id": CANONICAL_SCHEMA_ID,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "description": "Canonical schema boilerplate for event records. This file is the field source of truth.",
        "fields": CANONICAL_SCHEMA_FIELDS,
        "template_record": {name: "" for name in CANONICAL_FIELD_ORDER},
    }


def infer_json_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return "unknown"


def default_template_value(types: list[str]) -> Any:
    type_set = set(types)
    if type_set == {"array"}:
        return []
    if type_set == {"object"}:
        return {}
    if type_set == {"boolean"}:
        return False
    if type_set <= {"integer", "number"} and type_set:
        return 0
    return ""


def resolve_source_schema_boilerplate_dir(config: dict[str, Any], output_dir: Path) -> Path:
    source_cfg = config.get("schema", {}).get("source_boilerplates", {})
    dir_value = str(source_cfg.get("dir", "")).strip() if isinstance(source_cfg, dict) else ""
    if dir_value:
        return Path(dir_value)
    return output_dir / "boilerplate" / "schema-boilerplates"


def build_source_schema_boilerplate_payload(source_name: str, raw_records: list[dict[str, Any]]) -> dict[str, Any]:
    field_order: list[str] = []
    stats: dict[str, dict[str, Any]] = {}
    total_records = len(raw_records)

    for record in raw_records:
        for key, value in record.items():
            key_text = str(key)
            if key_text not in stats:
                stats[key_text] = {"count": 0, "types": set()}
                field_order.append(key_text)
            stats[key_text]["count"] += 1
            stats[key_text]["types"].add(infer_json_type(value))

    fields: list[dict[str, Any]] = []
    template_record: dict[str, Any] = {}
    for name in field_order:
        stat = stats[name]
        types = sorted(str(item) for item in stat["types"])
        required = bool(total_records) and stat["count"] == total_records
        fields.append(
            {
                "name": name,
                "label": name,
                "types": types,
                "required": required,
            }
        )
        template_record[name] = default_template_value(types)

    return {
        "schema_id": f"source_{source_name}_v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source": source_name,
        "record_count": total_records,
        "description": "Input-source schema boilerplate generated from raw source file.",
        "fields": fields,
        "template_record": template_record,
    }


def write_source_schema_boilerplate(
    config: dict[str, Any],
    output_dir: Path,
    source_name: str,
    raw_records: list[dict[str, Any]],
    encoding: str,
    line_ending: str,
) -> Path | None:
    source_cfg = config.get("schema", {}).get("source_boilerplates", {})
    source_enabled = bool(source_cfg.get("enabled", True)) if isinstance(source_cfg, dict) else True
    if not source_enabled:
        return None

    out_dir = resolve_source_schema_boilerplate_dir(config, output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"source_{source_name}.json"

    payload = build_source_schema_boilerplate_payload(source_name, raw_records)
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if line_ending != "\n":
        text = text.replace("\n", line_ending)
    with out_path.open("w", encoding=encoding, newline="") as fp:
        fp.write(text)
    return out_path


def write_schema_boilerplate(config: dict[str, Any], output_dir: Path, encoding: str, line_ending: str) -> Path | None:
    if not config.get("schema", {}).get("enabled", True):
        return None

    schema_path = resolve_schema_boilerplate_file(config, output_dir)
    if schema_path.exists():
        return schema_path
    schema_path.parent.mkdir(parents=True, exist_ok=True)
    payload = build_schema_boilerplate_payload()
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if line_ending != "\n":
        text = text.replace("\n", line_ending)
    with schema_path.open("w", encoding=encoding, newline="") as fp:
        fp.write(text)
    return schema_path


def load_schema_field_layout(config: dict[str, Any], output_dir: Path) -> tuple[list[str], dict[str, str]]:
    if not config.get("schema", {}).get("enabled", True):
        return [], {}

    schema_path = resolve_schema_boilerplate_file(config, output_dir)
    if not schema_path.exists():
        return [], {}

    payload = json.loads(schema_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Unerwartete Schema-Boilerplate-Struktur (Objekt erwartet): {schema_path}")

    raw_fields = payload.get("fields")
    if not isinstance(raw_fields, list):
        raise ValueError(f"Unerwartete Schema-Boilerplate-Struktur ('fields' Liste erwartet): {schema_path}")

    fields: list[str] = []
    field_map: dict[str, str] = {}
    for item in raw_fields:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        fields.append(name)
        label = str(item.get("label", "")).strip()
        if label:
            field_map[name] = label

    dedup_fields: list[str] = []
    seen: set[str] = set()
    for name in fields:
        if name not in seen:
            seen.add(name)
            dedup_fields.append(name)

    return dedup_fields, field_map


def resolve_export_layout(config: dict[str, Any], output_dir: Path) -> tuple[list[str], dict[str, str]]:
    schema_fields, schema_map = load_schema_field_layout(config, output_dir)

    configured_fields = [str(field).strip() for field in config["export"].get("fields", []) if str(field).strip()]
    if configured_fields:
        fields = configured_fields
    elif schema_fields:
        fields = schema_fields
    else:
        fields = list(CANONICAL_FIELD_ORDER)

    raw_mapping = config["export"].get("field_mappings", {})
    mapping_dict = raw_mapping if isinstance(raw_mapping, dict) else {}
    configured_map = {str(key).strip(): str(value) for key, value in mapping_dict.items() if str(key).strip()}
    field_map = dict(CANONICAL_FIELD_LABELS)
    field_map.update(schema_map)
    field_map.update(configured_map)
    return fields, field_map


def collect_boilerplate_input_files(config: dict[str, Any], output_dir: Path) -> list[Path]:
    input_cfg = config["input"]
    explicit_files = [str(path).strip() for path in input_cfg.get("boilerplate_files", []) if str(path).strip()]
    if explicit_files:
        return [Path(path) for path in explicit_files]

    boilerplate_dir_raw = str(input_cfg.get("boilerplate_dir", "")).strip()
    boilerplate_dir = Path(boilerplate_dir_raw) if boilerplate_dir_raw else runtime_snapshot_dir(output_dir)
    if not boilerplate_dir.exists():
        raise FileNotFoundError(f"Runtime-Snapshot-Verzeichnis nicht gefunden: {boilerplate_dir}")

    files = sorted(boilerplate_dir.glob("boilerplate_*.json"))
    if files:
        return files

    legacy_dir = output_dir / "boilerplate"
    legacy_files = sorted(legacy_dir.glob("boilerplate_*.json")) if legacy_dir.exists() else []
    if legacy_files and boilerplate_dir == runtime_snapshot_dir(output_dir):
        return legacy_files

    raise FileNotFoundError(f"Keine Runtime-Snapshot-Dateien gefunden in: {boilerplate_dir}")


def write_boilerplate(
    output_dir: Path,
    source_name: str,
    records: list[dict[str, str]],
    encoding: str,
    line_ending: str,
) -> Path:
    snapshot_dir = runtime_snapshot_dir(output_dir)
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "source": source_name,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "record_count": len(records),
        "records": records,
    }
    out_path = snapshot_dir / f"boilerplate_{source_name}.json"
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if line_ending != "\n":
        text = text.replace("\n", line_ending)
    with out_path.open("w", encoding=encoding, newline="") as fp:
        fp.write(text)
    return out_path


def chunk_rows(rows: list[list[str]], rows_per_file: int) -> list[list[list[str]]]:
    if rows_per_file <= 0:
        rows_per_file = len(rows) if rows else 1
    if not rows:
        return [[]]
    return [rows[idx : idx + rows_per_file] for idx in range(0, len(rows), rows_per_file)]


def make_filename(
    source: str,
    fmt: str,
    part: int,
    config: dict[str, Any],
    timestamp: str,
    include_part: bool,
) -> str:
    template = str(config["export"]["filename_template"])
    template = template.replace("{_part{part}}", "_part{part}" if include_part else "")
    context = SafeFormatDict(
        {
            **config["export"].get("filename_context", {}),
            "source": source,
            "format": fmt,
            "part": part if include_part else "",
            "timestamp": timestamp,
            "ext": fmt,
        }
    )
    return template.format_map(context)


def normalize_xml_tag(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    if not text:
        return "field"
    if text[0].isdigit():
        return f"f_{text}"
    return text


def csv_quoting_mode(mode: str) -> int:
    mapping = {
        "minimal": csv.QUOTE_MINIMAL,
        "all": csv.QUOTE_ALL,
        "nonnumeric": csv.QUOTE_NONNUMERIC,
        "none": csv.QUOTE_NONE,
    }
    try:
        return mapping[mode.lower()]
    except KeyError as exc:
        raise ValueError(f"Ungueltiger CSV quoting mode: {mode}") from exc


def build_export_rows(
    records: list[dict[str, Any]], fields: list[str], field_map: dict[str, str]
) -> tuple[list[str], list[list[str]]]:
    headers = [field_map.get(field, field) for field in fields]
    rows: list[list[str]] = []
    for record in records:
        rows.append([join_values(record.get(field, "")) for field in fields])
    return headers, rows


def export_csv(
    out_path: Path,
    headers: list[str],
    rows: list[list[str]],
    csv_cfg: dict[str, Any],
    encoding: str,
    line_ending: str,
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding=encoding, newline="") as fp:
        writer = csv.writer(
            fp,
            delimiter=csv_cfg["delimiter"],
            quotechar=csv_cfg["quotechar"],
            escapechar=csv_cfg["escapechar"],
            doublequote=bool(csv_cfg.get("doublequote", False)),
            quoting=csv_quoting_mode(str(csv_cfg.get("quoting", "minimal"))),
            lineterminator=line_ending,
        )
        writer.writerow(headers)
        writer.writerows(rows)


def export_xml(
    out_path: Path,
    headers: list[str],
    rows: list[list[str]],
    xml_cfg: dict[str, Any],
    encoding: str,
    line_ending: str,
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    root = ET.Element(normalize_xml_tag(str(xml_cfg.get("root_tag", "events"))))
    item_tag = normalize_xml_tag(str(xml_cfg.get("item_tag", "event")))

    for row in rows:
        item = ET.SubElement(root, item_tag)
        for header, value in zip(headers, row):
            tag = normalize_xml_tag(header)
            node = ET.SubElement(item, tag)
            node.text = value

    ET.indent(root, space="  ")
    xml_text = ET.tostring(
        root,
        encoding=encoding,
        xml_declaration=bool(xml_cfg.get("include_declaration", True)),
    ).decode(encoding)
    if line_ending != "\n":
        xml_text = xml_text.replace("\n", line_ending)
    with out_path.open("w", encoding=encoding, newline="") as fp:
        fp.write(xml_text)


def run_pipeline(config: dict[str, Any], timestamp: str | None = None) -> dict[str, list[Path]]:
    normalize_input_mode(config["input"])
    ensure_schema_config(config)
    ensure_replacements_config(config)
    output_dir = Path(str(config["export"]["output_dir"]))
    output_dir.mkdir(parents=True, exist_ok=True)
    encoding = str(config["export"]["encoding"])
    line_ending = str(config["export"]["line_ending"])
    ensure_rows_per_file_config(config["export"])
    rows_cfg: dict[str, Any] = config["export"]["rows_per_file"]
    rows_split_enabled = bool(rows_cfg.get("enabled", True))
    rows_per_file = int(rows_cfg.get("value", 1000))
    timestamp = timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")

    written: dict[str, list[Path]] = {
        "boilerplate": [],
        "schema_boilerplate": [],
        "source_schema_boilerplate": [],
        "boilerplate_input": [],
        "csv": [],
        "xml": [],
    }
    schema_path = write_schema_boilerplate(config, output_dir, encoding, line_ending)
    if schema_path is not None:
        written["schema_boilerplate"].append(schema_path)

    export_fields, export_field_map = resolve_export_layout(config, output_dir)

    def export_source_records(source_name: str, records: list[dict[str, Any]]) -> None:
        if not config["export"].get("enabled", True):
            return

        formats = [str(fmt).lower() for fmt in config["export"]["formats"]]
        headers, raw_rows = build_export_rows(records, export_fields, export_field_map)
        chunks = chunk_rows(raw_rows, rows_per_file) if rows_split_enabled else [raw_rows]

        for part_idx, chunk in enumerate(chunks, start=1):
            for fmt in formats:
                filename = make_filename(
                    source_name,
                    fmt,
                    part_idx,
                    config,
                    timestamp,
                    include_part=rows_split_enabled,
                )
                out_path = output_dir / filename
                if fmt == "csv":
                    export_csv(
                        out_path,
                        headers,
                        chunk,
                        config["export"]["csv"],
                        encoding,
                        line_ending,
                    )
                    written["csv"].append(out_path)
                elif fmt == "xml":
                    export_xml(
                        out_path,
                        headers,
                        chunk,
                        config["export"]["xml"],
                        encoding,
                        line_ending,
                    )
                    written["xml"].append(out_path)
                else:
                    raise ValueError(f"Nicht unterstuetztes Export-Format: {fmt}")

    input_mode = str(config["input"].get("mode", "raw"))
    if input_mode == "raw":
        input_files = [Path(path) for path in config["input"].get("files", [])]
        if not input_files:
            raise ValueError("Keine input.files konfiguriert")

        for input_file in input_files:
            if not input_file.exists():
                raise FileNotFoundError(f"Input-Datei nicht gefunden: {input_file}")

            source_name = input_file.stem
            raw_records = read_json_record_list(input_file)
            source_schema_path = write_source_schema_boilerplate(
                config,
                output_dir,
                source_name,
                raw_records,
                encoding,
                line_ending,
            )
            if source_schema_path is not None:
                written["source_schema_boilerplate"].append(source_schema_path)
            records = normalize_source_records(raw_records, input_file.name, config)
            written["boilerplate"].append(write_boilerplate(output_dir, source_name, records, encoding, line_ending))
            export_source_records(source_name, records)
    else:
        boilerplate_files = collect_boilerplate_input_files(config, output_dir)
        for boilerplate_file in boilerplate_files:
            if not boilerplate_file.exists():
                raise FileNotFoundError(f"Boilerplate-Datei nicht gefunden: {boilerplate_file}")

            source_name, records = read_boilerplate_records(boilerplate_file)
            records = apply_replacements(records, config.get("replacements", {}))
            written["boilerplate_input"].append(boilerplate_file)
            export_source_records(source_name, records)

    return written


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Pre- und Post-Processing fuer strukturierte Kalenderdaten mit Config und ENV Overrides."
    )
    parser.add_argument(
        "--config",
        default="config/processing_config.json",
        help="Pfad zur Konfigurationsdatei (default: config/processing_config.json)",
    )
    args = parser.parse_args()

    try:
        config = load_config(Path(args.config))
        written = run_pipeline(config)
    except Exception as exc:  # pragma: no cover
        print(str(exc))
        return 1

    print("Processing completed.")
    print(f"Boilerplate files: {len(written['boilerplate'])}")
    print(f"Schema boilerplate files: {len(written['schema_boilerplate'])}")
    print(f"Source schema boilerplate files: {len(written['source_schema_boilerplate'])}")
    print(f"Boilerplate input files: {len(written['boilerplate_input'])}")
    print(f"CSV files: {len(written['csv'])}")
    print(f"XML files: {len(written['xml'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
