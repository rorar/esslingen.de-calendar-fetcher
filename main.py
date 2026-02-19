#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import socket
import subprocess
import sys
import unicodedata
from pathlib import Path
from typing import Callable
from urllib.request import ProxyHandler, Request, build_opener

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
    delimiters = {",", "+", ";", "|"}
    values: list[str] = []
    buf: list[str] = []
    quote_char: str | None = None
    has_nonspace = False

    i = 0
    while i < len(raw):
        ch = raw[i]
        next_ch = raw[i + 1] if i + 1 < len(raw) else ""

        if quote_char is not None:
            if ch == "\\" and next_ch and (next_ch == quote_char or next_ch in delimiters or next_ch == "\\"):
                buf.append(next_ch)
                if not next_ch.isspace():
                    has_nonspace = True
                i += 2
                continue
            if ch == quote_char:
                quote_char = None
                i += 1
                continue
            buf.append(ch)
            if not ch.isspace():
                has_nonspace = True
            i += 1
            continue

        if ch in {"'", '"'}:
            # Treat quote chars as grouping only at token start.
            # Apostrophes inside tokens (e.g. L'art) remain literal.
            if not has_nonspace:
                quote_char = ch
            else:
                buf.append(ch)
                if not ch.isspace():
                    has_nonspace = True
            i += 1
            continue

        if ch == "\\":
            if next_ch and (next_ch in delimiters or next_ch in {"'", '"', "\\"}):
                buf.append(next_ch)
                if not next_ch.isspace():
                    has_nonspace = True
                i += 2
                continue
            buf.append(ch)
            if not ch.isspace():
                has_nonspace = True
            i += 1
            continue

        if ch in delimiters:
            token = "".join(buf).strip()
            if token:
                values.append(token)
            buf = []
            has_nonspace = False
            i += 1
            continue

        buf.append(ch)
        if not ch.isspace():
            has_nonspace = True
        i += 1

    if quote_char is not None:
        raise ValueError("Unbalancierte Anführungszeichen in Multi-Wert-Argument")

    token = "".join(buf).strip()
    if token:
        values.append(token)

    return values


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


def update_filters(filter_dir: Path, backend: str = "auto", quiet: bool = False) -> int:
    script = Path(__file__).resolve().parent / "app" / "fetch_filter_options.py"
    args = ["--out-dir", str(filter_dir), "--backend", backend]
    if quiet:
        args.append("--quiet")
    return run_python_script(script, args)


def load_filter_items_with_refresh(
    filter_file: Path,
    filter_dir: Path,
    backend: str,
    updater: Callable[[Path, str, bool], int] = update_filters,
) -> list[dict[str, str]]:
    try:
        items = load_filter_items(filter_file)
        if items:
            return items
    except FileNotFoundError:
        pass

    rc = updater(filter_dir, backend, True)
    if rc != 0:
        raise RuntimeError(f"Filter konnten nicht aktualisiert werden ({filter_file.name})")
    return load_filter_items(filter_file)


def list_filters(
    filter_dir: Path,
    backend: str = "auto",
    updater: Callable[[Path, str, bool], int] = update_filters,
) -> int:
    sammel_file = filter_dir / "q.sammelbegrif.id.json"
    cat_file = filter_dir / "q.kat.id.json"

    try:
        sammel_items = load_filter_items_with_refresh(sammel_file, filter_dir, backend, updater=updater)
        cat_items = load_filter_items_with_refresh(cat_file, filter_dir, backend, updater=updater)
    except Exception as exc:
        print(str(exc))
        return 1

    print(f"Sammelbegriffe (q.sammelbegrif.id): {len(sammel_items)}")
    for item in sammel_items:
        item_id = str(item.get("id", "")).strip()
        label = str(item.get("label", "")).strip()
        if item_id or label:
            print(f"- {item_id}: {label}")

    print("")
    print(f"Kategorien (q.kat.id): {len(cat_items)}")
    for item in cat_items:
        item_id = str(item.get("id", "")).strip()
        label = str(item.get("label", "")).strip()
        level = str(item.get("level", "")).strip()
        suffix = f" ({level})" if level else ""
        if item_id or label:
            print(f"- {item_id}: {label}{suffix}")

    return 0


def has_frictionless() -> bool:
    try:
        import frictionless  # type: ignore # noqa: F401
    except Exception:
        return False
    return True


def has_stealth_requests() -> bool:
    try:
        import stealth_requests  # type: ignore # noqa: F401
    except Exception:
        return False
    return True


def check_dns(hostname: str) -> tuple[bool, str]:
    try:
        socket.getaddrinfo(hostname, 443)
        return True, f"DNS aufloesbar fuer {hostname}"
    except Exception as exc:
        return False, f"DNS-Fehler fuer {hostname}: {exc}"


def check_https(url: str) -> tuple[bool, str]:
    try:
        req = Request(url, headers={"User-Agent": "esslingen-calendar-fetcher-doctor/1.0"})
        opener = build_opener(ProxyHandler({}))
        with opener.open(req, timeout=10) as resp:
            status = int(getattr(resp, "status", 200) or 200)
        if 200 <= status < 400:
            return True, f"HTTPS erreichbar ({status})"
        return False, f"HTTPS unerwarteter Status ({status})"
    except Exception as exc:
        return False, f"HTTPS-Check fehlgeschlagen: {exc}"


def doctor(filter_dir: Path, process_config: str) -> int:
    ok = 0
    warn = 0
    fail = 0

    def report(status: str, title: str, detail: str) -> None:
        print(f"[{status}] {title}: {detail}")

    def add_ok(title: str, detail: str) -> None:
        nonlocal ok
        ok += 1
        report("OK", title, detail)

    def add_warn(title: str, detail: str) -> None:
        nonlocal warn
        warn += 1
        report("WARN", title, detail)

    def add_fail(title: str, detail: str) -> None:
        nonlocal fail
        fail += 1
        report("FAIL", title, detail)

    print("Doctor Report")
    print("=============")

    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    if sys.version_info >= (3, 10):
        add_ok("Python", f"{py_ver} (>= 3.10)")
    else:
        add_fail("Python", f"{py_ver} (< 3.10, nicht unterstuetzt)")

    config_path = Path(process_config)
    if config_path.exists():
        add_ok("Config", f"Gefunden: {config_path}")
    else:
        add_warn("Config", f"Nicht gefunden: {config_path}")

    if Path("structured-data").exists():
        add_ok("structured-data", "Verzeichnis vorhanden")
    else:
        add_warn("structured-data", "Verzeichnis fehlt (wird bei Download erzeugt)")

    if Path("output").exists():
        add_ok("output", "Verzeichnis vorhanden")
    else:
        add_warn("output", "Verzeichnis fehlt (wird bei Processing erzeugt)")

    if shutil.which("curl"):
        add_ok("curl", "Systembefehl verfuegbar")
    else:
        add_warn("curl", "Nicht verfuegbar (Fallback: urllib)")

    if has_stealth_requests():
        add_ok("stealth_requests", "Python-Paket verfuegbar")
    else:
        add_warn("stealth_requests", "Nicht installiert (optional)")

    if has_frictionless():
        add_ok("frictionless", "Python-Paket verfuegbar")
    else:
        add_warn("frictionless", "Nicht installiert (nur fuer CSV-Lint noetig)")

    if (filter_dir / "q.sammelbegrif.id.json").exists() and (filter_dir / "q.kat.id.json").exists():
        add_ok("Filter Cache", f"Filterdateien vorhanden in {filter_dir}")
    else:
        add_warn("Filter Cache", f"Unvollstaendig in {filter_dir} (nutze --update-filters)")

    dns_ok, dns_detail = check_dns("www.esslingen.de")
    if dns_ok:
        add_ok("Netzwerk/DNS", dns_detail)
    else:
        add_warn("Netzwerk/DNS", dns_detail)

    https_ok, https_detail = check_https("https://www.esslingen.de")
    if https_ok:
        add_ok("Netzwerk/HTTPS", https_detail)
    else:
        add_warn("Netzwerk/HTTPS", https_detail)

    print("")
    print(f"Summary: OK={ok} WARN={warn} FAIL={fail}")
    if fail:
        print("Empfehlung: FAIL-Punkte zuerst beheben.")
        return 1
    if warn:
        print("Hinweis: WARN-Punkte sind optional/umgebungsabhaengig, aber pruefenswert.")
    return 0


def run_preprocess(config_path: str) -> int:
    script = Path(__file__).resolve().parent / "app" / "preprocess_data.py"
    return run_python_script(script, ["--config", config_path])


def run_postprocess(config_path: str, from_boilerplate: bool = False) -> int:
    script = Path(__file__).resolve().parent / "app" / "postprocess_output.py"
    args = ["--config", config_path]
    if from_boilerplate:
        args.append("--from-boilerplate")
    return run_python_script(script, args)


def run_csv_lint(
    config_path: str,
    output_dir: str | None = None,
    csv_files: list[str] | None = None,
    recursive: bool = False,
    no_schema_check: bool = False,
    schema_check: bool = False,
    strict_config: bool = False,
) -> int:
    script = Path(__file__).resolve().parent / "app" / "lint_csv.py"
    args = ["--config", config_path]
    if output_dir:
        args.extend(["--output-dir", output_dir])
    for csv_file in csv_files or []:
        args.extend(["--csv-file", csv_file])
    if recursive:
        args.append("--recursive")
    if no_schema_check:
        args.append("--no-schema-check")
    if schema_check:
        args.append("--schema-check")
    if strict_config:
        args.append("--strict-config")
    return run_python_script(script, args)


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


def build_fetch_command(config: dict[str, object], out_dir: str, backend: str = "auto") -> list[str]:
    fetch_script = Path(__file__).resolve().parent / "app" / "fetch_structured_data.py"
    cmd = [
        sys.executable,
        str(fetch_script),
        "--anz",
        str(config["anz"]),
        "--out-dir",
        out_dir,
        "--backend",
        backend,
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


def run_download(config: dict[str, object], out_dir: str, backend: str = "auto") -> int:
    cmd = build_fetch_command(config, out_dir, backend=backend)
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
    parser.add_argument(
        "--list-filters",
        action="store_true",
        help="List cached/current filter options (q.sammelbegrif.id and q.kat.id).",
    )
    parser.add_argument(
        "--doctor",
        action="store_true",
        help="Run local environment checks (Python, tools, optional deps, network, paths).",
    )
    parser.add_argument(
        "--backend",
        default="auto",
        choices=["auto", "stealth", "stealth-requests", "curl", "urllib"],
        help="Download backend for fetch scripts (default: auto).",
    )
    parser.add_argument(
        "--preprocess",
        action="store_true",
        help="Run preprocessing via app/preprocess_data.py",
    )
    parser.add_argument(
        "--postprocess",
        action="store_true",
        help="Run postprocessing via app/postprocess_output.py",
    )
    parser.add_argument(
        "--lint-csv",
        action="store_true",
        help="Run CSV lint via app/lint_csv.py (Frictionless).",
    )
    parser.add_argument(
        "--lint-output-dir",
        default=None,
        help="Override output directory for --lint-csv (default: export.output_dir from processing config).",
    )
    parser.add_argument(
        "--lint-csv-file",
        action="append",
        default=[],
        help="Explicit CSV file for --lint-csv (can be used multiple times).",
    )
    parser.add_argument(
        "--lint-recursive",
        action="store_true",
        help="Recursive CSV file search for --lint-csv.",
    )
    parser.add_argument(
        "--lint-no-schema-check",
        action="store_true",
        help="Disable expected-header check from schema/config for --lint-csv.",
    )
    parser.add_argument(
        "--lint-schema-check",
        action="store_true",
        help="Enable expected-header check from schema/config for --lint-csv.",
    )
    parser.add_argument(
        "--lint-strict-config",
        action="store_true",
        help="Use CSV delimiter/encoding from config strictly and enable schema-check for --lint-csv.",
    )
    parser.add_argument(
        "--from-boilerplate",
        action="store_true",
        help="Use boilerplate JSON files as input for --postprocess",
    )
    parser.add_argument(
        "--process-config",
        default="config/processing_config.json",
        help="Path to processing config for --preprocess/--postprocess/--lint-csv/--doctor",
    )
    args = parser.parse_args()

    filter_dir = Path(args.filter_dir)
    non_download_actions = bool(
        args.update_filters or args.preprocess or args.postprocess or args.lint_csv or args.list_filters or args.doctor
    )

    if args.from_boilerplate and not args.postprocess:
        print("--from-boilerplate kann nur zusammen mit --postprocess verwendet werden")
        return 1

    if args.update_filters:
        rc = update_filters(filter_dir, backend=args.backend, quiet=False)
        if rc != 0:
            return rc

    if args.list_filters:
        rc = list_filters(filter_dir, backend=args.backend)
        if rc != 0:
            return rc

    if args.doctor:
        rc = doctor(filter_dir, args.process_config)
        if rc != 0:
            return rc

    run_download_step = args.profile is not None or (not non_download_actions)
    if run_download_step:
        if args.profile is None:
            args.profile = "frauentage"

        try:
            config = resolve_profile(
                args.profile,
                filter_dir,
                updater=lambda current_filter_dir: update_filters(current_filter_dir, backend=args.backend, quiet=True),
            )
        except Exception as exc:
            print(str(exc))
            return 1

        rc = run_download(config, args.out_dir, backend=args.backend)
        if rc != 0:
            return rc

    if args.preprocess:
        rc = run_preprocess(args.process_config)
        if rc != 0:
            return rc

    if args.postprocess:
        rc = run_postprocess(args.process_config, from_boilerplate=args.from_boilerplate)
        if rc != 0:
            return rc

    if args.lint_csv:
        lint_schema_check = bool(args.lint_schema_check or args.lint_strict_config)
        if args.lint_no_schema_check:
            lint_schema_check = False
        rc = run_csv_lint(
            config_path=args.process_config,
            output_dir=args.lint_output_dir,
            csv_files=args.lint_csv_file,
            recursive=args.lint_recursive,
            no_schema_check=args.lint_no_schema_check,
            schema_check=lint_schema_check,
            strict_config=args.lint_strict_config,
        )
        if rc != 0:
            return rc

    if args.update_filters and args.profile is None and not (args.preprocess or args.postprocess or args.lint_csv):
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
