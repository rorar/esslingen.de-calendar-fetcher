#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path
from typing import Callable

# Download Every Date: --series-id=-1 --anz=-1
DOWNLOAD_EVERY_DATE = {"series_ids": ["-1"], "anz": "-1", "cat_ids": []}

# Download Frauentage: --series-id=330100 --anz=-1
DOWNLOAD_FRAUENTAGE = {"series_ids": ["330100"], "anz": "-1", "cat_ids": []}

HARD_CODED_PROFILES = {
    "every_date": DOWNLOAD_EVERY_DATE,
    "DOWNLOAD_EVERY_DATE": DOWNLOAD_EVERY_DATE,
    "frauentage": DOWNLOAD_FRAUENTAGE,
    "DOWNLOAD_FRAUENTAGE": DOWNLOAD_FRAUENTAGE,
}

ADV_CAT_ID_PREFIX = "DOWNLOAD_CAT_ID="
ADV_CAT_LABEL_PREFIX = "DOWNLOAD_CAT_LABEL="
ADV_SAMMEL_ID_PREFIX = "DOWNLOAD_SAMMEL_ID="
ADV_SAMMEL_LABEL_PREFIX = "DOWNLOAD_SAMMEL_LABEL="

SIMPLE_CAT_PREFIX = "DOWNLOAD_CAT_"
SIMPLE_SAMMEL_PREFIX = "DOWNLOAD_SAMMEL_"


def normalize_label(value: str) -> str:
    value = value.strip().lower()
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_")


def split_multi_values(raw: str) -> list[str]:
    values = [part.strip() for part in re.split(r"[,+;|]", raw) if part.strip()]
    out: list[str] = []
    for value in values:
        if len(value) >= 2 and ((value[0] == value[-1] == '"') or (value[0] == value[-1] == "'")):
            value = value[1:-1].strip()
        if value:
            out.append(value)
    return out


def unique_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out


def is_direct_id_token(token: str) -> bool:
    return bool(re.fullmatch(r"-?\d+", token.strip()))


def parse_direct_ids(tokens: list[str], error_msg: str) -> list[str]:
    ids = [token.strip() for token in tokens if token.strip()]
    if not ids:
        raise ValueError(error_msg)

    invalid = [token for token in ids if not is_direct_id_token(token)]
    if invalid:
        bad = ", ".join(invalid)
        raise ValueError(f"Ungültige ID(s): {bad}")

    ids = unique_preserve_order(ids)
    if "-1" in ids:
        return ["-1"]
    return ids


def run_python_script(script_path: Path, args: list[str]) -> int:
    cmd = [sys.executable, str(script_path), *args]
    completed = subprocess.run(cmd)
    return completed.returncode


def update_filters(filter_dir: Path) -> int:
    script = Path(__file__).resolve().parent / "app" / "fetch_filter_options.py"
    return run_python_script(script, ["--out-dir", str(filter_dir)])


def load_filter_items(file_path: Path) -> list[dict[str, str]]:
    if not file_path.exists():
        raise FileNotFoundError(str(file_path))
    payload = json.loads(file_path.read_text(encoding="utf-8"))
    items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        raise ValueError(f"Unerwartetes Filterformat in {file_path}")
    return [item for item in items if isinstance(item, dict)]


def resolve_token_to_id(token: str, items: list[dict[str, str]]) -> str | None:
    token = token.strip()
    if not token:
        return None

    for item in items:
        item_id = str(item.get("id", "")).strip()
        if item_id == token:
            return item_id

    for item in items:
        label = str(item.get("label", "")).strip()
        if label.casefold() == token.casefold():
            return str(item.get("id", "")).strip()

    token_norm = normalize_label(token)
    for item in items:
        label_norm = normalize_label(str(item.get("label", "")))
        if label_norm == token_norm:
            return str(item.get("id", "")).strip()

    return None


def resolve_filter_id(
    token: str,
    filter_file: Path,
    filter_dir: Path,
    updater: Callable[[Path], int],
) -> str:
    try:
        items = load_filter_items(filter_file)
    except FileNotFoundError:
        rc = updater(filter_dir)
        if rc != 0:
            raise RuntimeError(f"Filter konnten nicht aktualisiert werden ({filter_file.name})")
        items = load_filter_items(filter_file)

    resolved = resolve_token_to_id(token, items)
    if resolved:
        return resolved

    rc = updater(filter_dir)
    if rc == 0:
        items = load_filter_items(filter_file)
        resolved = resolve_token_to_id(token, items)
        if resolved:
            return resolved

    raise ValueError(f"Konnte '{token}' nicht in {filter_file.name} auflösen")


def resolve_multiple_filter_ids(
    tokens: list[str],
    filter_file: Path,
    filter_dir: Path,
    updater: Callable[[Path], int],
) -> list[str]:
    if not tokens:
        raise ValueError(f"Mindestens ein Wert für {filter_file.name} erforderlich")
    resolved = [resolve_filter_id(token, filter_file, filter_dir, updater) for token in tokens]
    return unique_preserve_order(resolved)


def resolve_profile(
    profile: str,
    filter_dir: Path,
    updater: Callable[[Path], int] = update_filters,
) -> dict[str, object]:
    if profile in HARD_CODED_PROFILES:
        cfg = HARD_CODED_PROFILES[profile]
        return {
            "series_ids": list(cfg["series_ids"]),
            "anz": cfg["anz"],
            "cat_ids": list(cfg.get("cat_ids", [])),
        }

    if profile.startswith(ADV_CAT_ID_PREFIX):
        raw = profile[len(ADV_CAT_ID_PREFIX) :]
        cat_ids = parse_direct_ids(split_multi_values(raw), "DOWNLOAD_CAT_ID benötigt mindestens eine ID")
        return {"series_ids": ["-1"], "anz": "-1", "cat_ids": cat_ids}

    if profile.startswith(ADV_CAT_LABEL_PREFIX):
        raw = profile[len(ADV_CAT_LABEL_PREFIX) :]
        labels = split_multi_values(raw)
        if not labels:
            raise ValueError("DOWNLOAD_CAT_LABEL benötigt mindestens ein Label")
        cat_file = filter_dir / "q.kat.id.json"
        cat_ids = resolve_multiple_filter_ids(labels, cat_file, filter_dir, updater)
        return {"series_ids": ["-1"], "anz": "-1", "cat_ids": cat_ids}

    if profile.startswith(ADV_SAMMEL_ID_PREFIX):
        raw = profile[len(ADV_SAMMEL_ID_PREFIX) :]
        series_ids = parse_direct_ids(split_multi_values(raw), "DOWNLOAD_SAMMEL_ID benötigt mindestens eine ID")
        return {"series_ids": series_ids, "anz": "-1", "cat_ids": []}

    if profile.startswith(ADV_SAMMEL_LABEL_PREFIX):
        raw = profile[len(ADV_SAMMEL_LABEL_PREFIX) :]
        labels = split_multi_values(raw)
        if not labels:
            raise ValueError("DOWNLOAD_SAMMEL_LABEL benötigt mindestens ein Label")
        sammel_file = filter_dir / "q.sammelbegrif.id.json"
        series_ids = resolve_multiple_filter_ids(labels, sammel_file, filter_dir, updater)
        return {"series_ids": series_ids, "anz": "-1", "cat_ids": []}

    if profile.startswith(SIMPLE_CAT_PREFIX):
        token = profile[len(SIMPLE_CAT_PREFIX) :].strip()
        if not token:
            raise ValueError("DOWNLOAD_CAT_ benötigt ein ID- oder Label-Suffix")

        if is_direct_id_token(token):
            cat_id = token
        else:
            cat_file = filter_dir / "q.kat.id.json"
            cat_id = resolve_filter_id(token, cat_file, filter_dir, updater)

        return {"series_ids": ["-1"], "anz": "-1", "cat_ids": [cat_id]}

    if profile.startswith(SIMPLE_SAMMEL_PREFIX):
        token = profile[len(SIMPLE_SAMMEL_PREFIX) :].strip()
        if not token:
            raise ValueError("DOWNLOAD_SAMMEL_ benötigt ein ID- oder Label-Suffix")

        if is_direct_id_token(token):
            sammel_id = token
        else:
            sammel_file = filter_dir / "q.sammelbegrif.id.json"
            sammel_id = resolve_filter_id(token, sammel_file, filter_dir, updater)

        return {"series_ids": [sammel_id], "anz": "-1", "cat_ids": []}

    raise ValueError(
        "Unbekanntes Profil. Erlaubt: every_date, frauentage, "
        "DOWNLOAD_EVERY_DATE, DOWNLOAD_FRAUENTAGE, "
        "DOWNLOAD_CAT_<ID|LABEL>, DOWNLOAD_SAMMEL_<ID|LABEL>, "
        "DOWNLOAD_CAT_ID=<ID[,ID2]>, DOWNLOAD_CAT_LABEL=<LABEL[,LABEL2]>, "
        "DOWNLOAD_SAMMEL_ID=<ID[,ID2]>, DOWNLOAD_SAMMEL_LABEL=<LABEL[,LABEL2]>"
    )


def build_fetch_command(config: dict[str, object], out_dir: str) -> list[str]:
    fetch_script = Path(__file__).resolve().parent / "app" / "fetch_structured_data.py"
    cmd = [
        sys.executable,
        str(fetch_script),
        "--anz",
        str(config["anz"]),
        "--out-dir",
        out_dir,
    ]

    series_ids = config.get("series_ids", [])
    if isinstance(series_ids, list):
        for series_id in series_ids:
            cmd.extend(["--series-id", str(series_id)])

    cat_ids = config.get("cat_ids", [])
    if isinstance(cat_ids, list):
        for cat_id in cat_ids:
            cmd.extend(["--cat-id", str(cat_id)])

    return cmd


def run_download(config: dict[str, object], out_dir: str) -> int:
    cmd = build_fetch_command(config, out_dir)
    completed = subprocess.run(cmd)
    return completed.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Download structured Esslingen calendar data.")
    parser.add_argument(
        "--profile",
        default=None,
        help=(
            "Profile: frauentage | every_date | DOWNLOAD_EVERY_DATE | DOWNLOAD_FRAUENTAGE | "
            "DOWNLOAD_CAT_<ID|LABEL> | DOWNLOAD_SAMMEL_<ID|LABEL> | "
            "DOWNLOAD_CAT_ID=<...> | DOWNLOAD_CAT_LABEL=<...> | "
            "DOWNLOAD_SAMMEL_ID=<...> | DOWNLOAD_SAMMEL_LABEL=<...> "
            "(Multi delimiter: , ; | +)"
        ),
    )
    parser.add_argument(
        "--out-dir",
        default="structured-data",
        help="Output directory for calendar data (default: structured-data)",
    )
    parser.add_argument(
        "--filter-dir",
        default="filter",
        help="Directory for cached filter mappings (default: filter)",
    )
    parser.add_argument(
        "--update-filters",
        action="store_true",
        help="Refresh filter mappings via app/fetch_filter_options.py",
    )
    args = parser.parse_args()

    filter_dir = Path(args.filter_dir)

    if args.update_filters:
        rc = update_filters(filter_dir)
        if rc != 0:
            return rc

    if args.profile is None:
        if args.update_filters:
            return 0
        args.profile = "frauentage"

    try:
        config = resolve_profile(args.profile, filter_dir)
    except Exception as exc:
        print(str(exc))
        return 1

    return run_download(config, args.out_dir)


if __name__ == "__main__":
    raise SystemExit(main())
