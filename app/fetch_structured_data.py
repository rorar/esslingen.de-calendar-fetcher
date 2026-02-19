#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import ProxyHandler, Request, build_opener

BASE_URL = "https://www.esslingen.de"
JSON_BASE_URL = f"{BASE_URL}/site/Esslingen_Layout_2022/VXC/20307012/loadData/loadData.json"
ICS_URL = f"{BASE_URL}/site/Esslingen_Layout_2022/zmservice/20307012/ical/ical.ics"


def has_curl() -> bool:
    return shutil.which("curl") is not None


def has_stealth_requests() -> bool:
    try:
        import stealth_requests  # type: ignore # noqa: F401
    except Exception:
        return False
    return True


def fetch_text_with_curl(url: str) -> tuple[int, str, str]:
    proc = subprocess.run(
        ["curl", "--noproxy", "*", "-sS", url],
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout, (proc.stderr or "").strip()


def fetch_text_with_urllib(url: str) -> tuple[int, str, str]:
    try:
        req = Request(url, headers={"User-Agent": "esslingen-calendar-fetcher/1.0"})
        opener = build_opener(ProxyHandler({}))
        with opener.open(req, timeout=60) as resp:
            return 0, resp.read().decode("utf-8", "replace"), ""
    except Exception as exc:
        return 1, "", str(exc)


def fetch_text_with_stealth_requests(url: str) -> tuple[int, str, str]:
    try:
        import stealth_requests as stealth  # type: ignore
    except Exception as exc:
        return 1, "", f"stealth-requests import fehlgeschlagen: {exc}"

    try:
        response = stealth.get(url, timeout=60, impersonate="chrome")
        status_code = int(getattr(response, "status_code", 0) or 0)
        text = str(getattr(response, "text", "") or "")
        if 200 <= status_code < 400 and text:
            return 0, text, ""
        if status_code:
            return 1, text, f"HTTP {status_code}"
        return 1, text, "Unbekannter Fehler (keinen HTTP-Status erhalten)"
    except Exception as exc:
        return 1, "", str(exc)


def normalize_backend_arg(value: str) -> str:
    normalized = value.strip().lower()
    if normalized == "stealth":
        return "stealth-requests"
    if normalized in {"auto", "stealth-requests", "curl", "urllib"}:
        return normalized
    raise ValueError(f"Unbekannter Backend-Wert: {value}")


def resolve_backend_order(backend: str) -> list[str]:
    normalized = normalize_backend_arg(backend)
    order: list[str] = []

    # auto: prefer stealth if installed, then curl, finally urllib
    if normalized == "auto":
        if has_stealth_requests():
            order.append("stealth-requests")
        if has_curl():
            order.append("curl")
        order.append("urllib")
        return order

    # explicit stealth: try stealth first, but keep operational fallbacks
    if normalized == "stealth-requests":
        order.append("stealth-requests")
        if has_curl():
            order.append("curl")
        order.append("urllib")
        return order

    # explicit curl: try curl first, then urllib fallback
    if normalized == "curl":
        order.append("curl")
        order.append("urllib")
        return order

    # explicit urllib
    return ["urllib"]


def fetch_with_backend(url: str, backend: str) -> tuple[int, str, str]:
    if backend == "stealth-requests":
        return fetch_text_with_stealth_requests(url)
    if backend == "curl":
        return fetch_text_with_curl(url)
    return fetch_text_with_urllib(url)


def fetch_text(url: str, retries: int = 5, wait_seconds: float = 1.5, backend: str = "auto") -> tuple[str, str]:
    backend_order = resolve_backend_order(backend)
    last_err = ""
    last_backend = ""
    for attempt in range(1, retries + 1):
        for active_backend in backend_order:
            returncode, stdout, stderr = fetch_with_backend(url, active_backend)
            if returncode == 0:
                return stdout, active_backend
            last_backend = active_backend
            last_err = stderr or "Unbekannter Fehler"
        if attempt < retries:
            time.sleep(wait_seconds * attempt)

    backend_note = f" backend={last_backend}" if last_backend else ""
    raise RuntimeError(f"Download fehlgeschlagen: {url} ({last_err}){backend_note}")


def iso_from_de_date(value: object) -> str | None:
    if not value:
        return None
    m = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", str(value))
    if not m:
        return None
    day, month, year = m.groups()
    return f"{year}-{month}-{day}"


def to_jsonld(events: list[object]) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []

    for event in events:
        if not isinstance(event, dict):
            continue

        node_id = event.get("id")
        out: dict[str, object] = {
            "@context": "http://schema.org",
            "@type": "Event",
            "name": event.get("titel"),
            "startDate": iso_from_de_date(event.get("von")),
            "endDate": iso_from_de_date(event.get("bis")) or iso_from_de_date(event.get("von")),
            "url": (
                f"{BASE_URL}/site/Esslingen_Layout_2022/node/20307012/zmdetail/index.html?nodeID={node_id}"
                if node_id is not None
                else None
            ),
        }

        description = "".join(str(p) for p in [event.get("kurzbeschreibung"), event.get("beschreibung")] if p)
        if description:
            out["description"] = description

        location_name = event.get("location")
        if location_name:
            location: dict[str, object] = {"@type": "Place", "name": location_name}

            street = str(event.get("location_strasse") or "").strip()
            house_no = str(event.get("location_hausnr") or "").strip()
            locality = event.get("location_ortsname")
            postal_code = event.get("location_plz")
            country = event.get("location_land")

            street_full = f"{street} {house_no}".strip()
            address: dict[str, object] = {"@type": "PostalAddress"}
            if street_full:
                address["streetAddress"] = street_full
            if locality:
                address["addressLocality"] = locality
            if postal_code:
                address["postalCode"] = postal_code
            if country:
                address["addressCountry"] = country
            if len(address) > 1:
                location["address"] = address

            out["location"] = location

        result.append(out)

    return result


def write_history_snapshot(paths: list[Path], history_dir: Path) -> None:
    history_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    for path in paths:
        history_name = f"{path.stem}__{ts}{path.suffix}"
        shutil.copy2(path, history_dir / history_name)


def build_json_url(series_id: str, anz: str, cat_ids: list[str] | None = None, ldx: str | None = None) -> str:
    if ldx is None:
        ldx = str(int(time.time() * 1000))

    params: list[tuple[str, str]] = [
        ("ldx", ldx),
        ("action", "pre"),
        ("q.z.von", ""),
        ("q.z.bis", ""),
        ("q.sammelbegrif.id", str(series_id)),
        ("q", ""),
        ("rezw", "1200"),
        ("SORT", "2"),
        ("dateformat", "XDATE"),
        ("anz", str(anz)),
        ("loadgruppe", "geg"),
        ("loadgruppe", "dhhd"),
        ("loadgruppe", "kkfjfj"),
        ("xstart", "0"),
    ]

    for cat_id in cat_ids or []:
        cat_id = str(cat_id).strip()
        if cat_id:
            params.append(("q.kat.id", cat_id))

    return f"{JSON_BASE_URL}?{urlencode(params, doseq=True)}"


def unique_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out


def event_dedupe_key(event: dict[str, Any]) -> str:
    event_id = str(event.get("id", "")).strip()
    if event_id:
        return f"id:{event_id}"

    title = str(event.get("titel", "")).strip()
    von = str(event.get("von", "")).strip()
    bis = str(event.get("bis", "")).strip()
    zeit = str(event.get("zeit", "")).strip()
    location = str(event.get("location", "")).strip()
    return f"fallback:{title}|{von}|{bis}|{zeit}|{location}"


def merge_event_lists(event_lists: list[list[object]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen_keys: set[str] = set()

    for events in event_lists:
        for item in events:
            if not isinstance(item, dict):
                continue
            key = event_dedupe_key(item)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            merged.append(item)

    return merged


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch structured Esslingen calendar data into ./structured-data")
    parser.add_argument(
        "--out-dir",
        default="structured-data",
        help="Target directory for downloaded/generated files (default: structured-data)",
    )
    parser.add_argument(
        "--series-id",
        action="append",
        default=[],
        help=(
            "Value for q.sammelbegrif.id (-1 means all series, 330100 = Frauenwochen). "
            "Can be used multiple times."
        ),
    )
    parser.add_argument(
        "--anz",
        default="-1",
        help="Value for anz parameter (-1 means load all available items)",
    )
    parser.add_argument(
        "--cat-id",
        action="append",
        default=[],
        help="Optional q.kat.id filter. Can be used multiple times.",
    )
    parser.add_argument(
        "--backend",
        default="auto",
        choices=["auto", "stealth", "stealth-requests", "curl", "urllib"],
        help="Download backend (default: auto).",
    )
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    history_dir = out_dir / "history"

    series_ids = [str(x).strip() for x in args.series_id if str(x).strip()]
    if not series_ids:
        series_ids = ["-1"]
    if "-1" in series_ids:
        series_ids = ["-1"]
    series_ids = unique_preserve_order(series_ids)

    cat_ids = unique_preserve_order([str(x).strip() for x in args.cat_id if str(x).strip()])

    try:
        all_events: list[list[object]] = []
        used_backends: set[str] = set()
        for series_id in series_ids:
            json_url = build_json_url(series_id, args.anz, cat_ids=cat_ids)
            json_text, backend = fetch_text(json_url, backend=args.backend)
            used_backends.add(backend)
            parsed = json.loads(json_text)
            if not isinstance(parsed, list):
                raise ValueError("Unexpected JSON structure: expected a list")
            all_events.append(parsed)

        merged_events = merge_event_lists(all_events)
        merged_json_text = json.dumps(merged_events, ensure_ascii=False, indent=2)
        ics_text, ics_backend = fetch_text(ICS_URL, backend=args.backend)
        used_backends.add(ics_backend)
    except RuntimeError as exc:
        print(str(exc))
        return 1

    json_path = out_dir / "loadData_20307012.json"
    json_path.write_text(merged_json_text, encoding="utf-8")

    ics_path = out_dir / "ical_20307012.ics"
    ics_path.write_text(ics_text, encoding="utf-8")

    jsonld = to_jsonld(merged_events)
    jsonld_path = out_dir / "jsonld_20307012_generated.json"
    jsonld_path.write_text(json.dumps(jsonld, ensure_ascii=False, indent=2), encoding="utf-8")

    write_history_snapshot([json_path, ics_path, jsonld_path], history_dir)

    ordered_used_backends = [b for b in resolve_backend_order(args.backend) if b in used_backends]
    if not ordered_used_backends:
        ordered_used_backends = sorted(used_backends)
    print(f"Download backend(s): {', '.join(ordered_used_backends)}")
    print(f"Series IDs: {', '.join(series_ids)}")
    if cat_ids:
        print(f"Category IDs: {', '.join(cat_ids)}")
    print(f"Wrote {json_path}")
    print(f"Wrote {ics_path}")
    print(f"Wrote {jsonld_path} ({len(jsonld)} events)")
    print(f"Wrote history snapshot in {history_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
