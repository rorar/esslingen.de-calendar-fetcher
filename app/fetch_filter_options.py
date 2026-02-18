#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html as html_lib
import json
import re
import shutil
import subprocess
import time
from datetime import datetime, UTC
from pathlib import Path
from urllib.request import ProxyHandler, Request, build_opener

CALENDAR_URL = "https://www.esslingen.de/freizeit-und-engagement/veranstaltungskalender"


def has_curl() -> bool:
    return shutil.which("curl") is not None


def fetch_with_curl(url: str) -> tuple[int, str, str]:
    proc = subprocess.run(
        ["curl", "--noproxy", "*", "-sS", url],
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout, (proc.stderr or "").strip()


def fetch_with_urllib(url: str) -> tuple[int, str, str]:
    try:
        req = Request(url, headers={"User-Agent": "esslingen-filter-fetcher/1.0"})
        opener = build_opener(ProxyHandler({}))
        with opener.open(req, timeout=60) as resp:
            return 0, resp.read().decode("utf-8", "replace"), ""
    except Exception as exc:
        return 1, "", str(exc)


def fetch_html(url: str, retries: int = 6, wait_seconds: float = 1.5) -> tuple[str, str]:
    backend = "curl" if has_curl() else "urllib"
    last_err = ""

    for attempt in range(1, retries + 1):
        if backend == "curl":
            code, out, err = fetch_with_curl(url)
        else:
            code, out, err = fetch_with_urllib(url)

        if code == 0 and out:
            return out, backend

        last_err = err
        if attempt < retries:
            time.sleep(wait_seconds * attempt)

    raise RuntimeError(f"Download fehlgeschlagen: {url} ({last_err})")


def normalize_text(value: str) -> str:
    value = re.sub(r"<[^>]+>", "", value)
    value = html_lib.unescape(value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def extract_series_options(page_html: str) -> list[dict[str, str]]:
    select_match = re.search(
        r'<select[^>]*name="q\.sammelbegrif\.id"[^>]*>(.*?)</select>',
        page_html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not select_match:
        raise ValueError("Konnte select[name='q.sammelbegrif.id'] nicht finden")

    options_block = select_match.group(1)
    options: list[dict[str, str]] = []

    for match in re.finditer(
        r'<option[^>]*value="([^"]*)"[^>]*>(.*?)</option>',
        options_block,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        opt_id = match.group(1).strip()
        label = normalize_text(match.group(2))
        options.append({"id": opt_id, "label": label})

    return options


def extract_category_options(page_html: str) -> list[dict[str, str]]:
    pattern = re.compile(
        r'<li[^>]*class="([^"]*katlevel[0-9][^"]*)"[^>]*>\s*'
        r'<label[^>]*for="q\.kat\.id\.[^"]*"[^>]*>\s*'
        r'(.*?)\s*<input[^>]*name="q\.kat\.id"[^>]*value="([^"]+)"',
        flags=re.IGNORECASE | re.DOTALL,
    )

    items: list[dict[str, str]] = []
    seen_ids: set[str] = set()

    for match in pattern.finditer(page_html):
        classes = match.group(1)
        raw_label = match.group(2)
        cat_id = match.group(3).strip()

        if cat_id in seen_ids:
            continue
        seen_ids.add(cat_id)

        level_match = re.search(r"katlevel[0-9]", classes)
        level = level_match.group(0) if level_match else ""
        label = normalize_text(raw_label)
        items.append({"id": cat_id, "label": label, "level": level})

    if not items:
        raise ValueError("Konnte keine q.kat.id Optionen extrahieren")

    return items


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch current filter options from Esslingen calendar page")
    parser.add_argument("--url", default=CALENDAR_URL, help="Calendar page URL")
    parser.add_argument("--out-dir", default="filter", help="Output directory (default: filter)")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        page_html, backend = fetch_html(args.url)
        series_options = extract_series_options(page_html)
        category_options = extract_category_options(page_html)
    except Exception as exc:
        print(str(exc))
        return 1

    series_path = out_dir / "q.sammelbegrif.id.json"
    categories_path = out_dir / "q.kat.id.json"

    metadata = {
        "source_url": args.url,
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }

    series_payload = {
        **metadata,
        "count": len(series_options),
        "items": series_options,
    }
    categories_payload = {
        **metadata,
        "count": len(category_options),
        "items": category_options,
    }

    series_path.write_text(json.dumps(series_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    categories_path.write_text(json.dumps(categories_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Download backend: {backend}")
    print(f"Wrote {series_path} ({len(series_options)} items)")
    print(f"Wrote {categories_path} ({len(category_options)} items)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
