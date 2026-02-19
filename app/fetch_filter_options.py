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


def has_stealth_requests() -> bool:
    try:
        import stealth_requests  # type: ignore # noqa: F401
    except Exception:
        return False
    return True


def fetch_html_with_curl(url: str) -> tuple[int, str, str]:
    proc = subprocess.run(
        ["curl", "--noproxy", "*", "-sS", url],
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout, (proc.stderr or "").strip()


def fetch_html_with_urllib(url: str) -> tuple[int, str, str]:
    try:
        req = Request(url, headers={"User-Agent": "esslingen-filter-fetcher/1.0"})
        opener = build_opener(ProxyHandler({}))
        with opener.open(req, timeout=60) as resp:
            return 0, resp.read().decode("utf-8", "replace"), ""
    except Exception as exc:
        return 1, "", str(exc)


def fetch_html_with_stealth_requests(url: str) -> tuple[int, str, str]:
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
        return fetch_html_with_stealth_requests(url)
    if backend == "curl":
        return fetch_html_with_curl(url)
    return fetch_html_with_urllib(url)


def fetch_html(
    url: str,
    retries: int = 6,
    wait_seconds: float = 1.5,
    backend: str = "auto",
) -> tuple[str, str]:
    backend_order = resolve_backend_order(backend)
    last_err = ""
    last_backend = ""

    for attempt in range(1, retries + 1):
        for active_backend in backend_order:
            code, out, err = fetch_with_backend(url, active_backend)
            if code == 0 and out:
                return out, active_backend

            last_backend = active_backend
            last_err = err
        if attempt < retries:
            time.sleep(wait_seconds * attempt)

    backend_note = f" backend={last_backend}" if last_backend else ""
    raise RuntimeError(f"Download fehlgeschlagen: {url} ({last_err}){backend_note}")


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
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress success output (useful for internal refresh calls).",
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

    try:
        page_html, backend = fetch_html(args.url, backend=args.backend)
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

    if not args.quiet:
        print(f"Download backend(s): {backend}")
        print(f"Wrote {series_path} ({len(series_options)} items)")
        print(f"Wrote {categories_path} ({len(category_options)} items)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
