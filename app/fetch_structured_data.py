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
from urllib.parse import urlencode
from urllib.request import ProxyHandler, Request, build_opener

BASE_URL = "https://www.esslingen.de"
JSON_BASE_URL = f"{BASE_URL}/site/Esslingen_Layout_2022/VXC/20307012/loadData/loadData.json"
ICS_URL = f"{BASE_URL}/site/Esslingen_Layout_2022/zmservice/20307012/ical/ical.ics"


def has_curl() -> bool:
    return shutil.which("curl") is not None


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


def fetch_text(url: str, retries: int = 5, wait_seconds: float = 1.5) -> str:
    last_err = ""
    use_curl = has_curl()
    for attempt in range(1, retries + 1):
        if use_curl:
            returncode, stdout, stderr = fetch_text_with_curl(url)
        else:
            returncode, stdout, stderr = fetch_text_with_urllib(url)

        if returncode == 0:
            return stdout

        last_err = stderr
        if attempt < retries:
            time.sleep(wait_seconds * attempt)

    raise RuntimeError(f"Download fehlgeschlagen: {url} ({last_err})")


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


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch structured Esslingen calendar data into ./structured-data")
    parser.add_argument(
        "--out-dir",
        default="structured-data",
        help="Target directory for downloaded/generated files (default: structured-data)",
    )
    parser.add_argument(
        "--series-id",
        default="-1",
        help="Value for q.sammelbegrif.id (-1 means all series, 330100 = Frauenwochen)",
    )
    parser.add_argument(
        "--anz",
        default="-1",
        help="Value for anz parameter (-1 means load all available items)",
    )
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    history_dir = out_dir / "history"

    ldx = str(int(time.time() * 1000))
    json_params = [
        ("ldx", ldx),
        ("action", "pre"),
        ("q.z.von", ""),
        ("q.z.bis", ""),
        ("q.sammelbegrif.id", str(args.series_id)),
        ("q", ""),
        ("rezw", "1200"),
        ("SORT", "2"),
        ("dateformat", "XDATE"),
        ("anz", str(args.anz)),
        ("loadgruppe", "geg"),
        ("loadgruppe", "dhhd"),
        ("loadgruppe", "kkfjfj"),
        ("xstart", "0"),
    ]
    json_url = f"{JSON_BASE_URL}?{urlencode(json_params, doseq=True)}"

    try:
        json_text = fetch_text(json_url)
        ics_text = fetch_text(ICS_URL)
    except RuntimeError as exc:
        print(str(exc))
        return 1

    json_path = out_dir / "loadData_20307012.json"
    json_path.write_text(json_text, encoding="utf-8")

    ics_path = out_dir / "ical_20307012.ics"
    ics_path.write_text(ics_text, encoding="utf-8")

    data = json.loads(json_text)
    if not isinstance(data, list):
        raise ValueError("Unexpected JSON structure: expected a list")

    jsonld = to_jsonld(data)
    jsonld_path = out_dir / "jsonld_20307012_generated.json"
    jsonld_path.write_text(json.dumps(jsonld, ensure_ascii=False, indent=2), encoding="utf-8")

    write_history_snapshot([json_path, ics_path, jsonld_path], history_dir)

    if has_curl():
        print("Download backend: curl")
    else:
        print("Download backend: urllib fallback (curl nicht gefunden)")
    print(f"Wrote {json_path}")
    print(f"Wrote {ics_path}")
    print(f"Wrote {jsonld_path} ({len(jsonld)} events)")
    print(f"Wrote history snapshot in {history_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
