#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

# Download Every Date: --series-id=-1 --anz=-1
DOWNLOAD_EVERY_DATE = {"series_id": "-1", "anz": "-1"}

# Download Frauentage: --series-id=330100 --anz=-1
DOWNLOAD_FRAUENTAGE = {"series_id": "330100", "anz": "-1"}

PROFILES = {
    "every_date": DOWNLOAD_EVERY_DATE,
    "frauentage": DOWNLOAD_FRAUENTAGE,
}


def run_profile(profile: str, out_dir: str) -> int:
    config = PROFILES[profile]
    fetch_script = Path(__file__).resolve().parent / "app" / "fetch_structured_data.py"

    cmd = [
        sys.executable,
        str(fetch_script),
        "--series-id",
        config["series_id"],
        "--anz",
        config["anz"],
        "--out-dir",
        out_dir,
    ]
    completed = subprocess.run(cmd)
    return completed.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Download structured Esslingen calendar data.")
    parser.add_argument(
        "--profile",
        choices=sorted(PROFILES.keys()),
        default="frauentage",
        help="Download profile (default: frauentage)",
    )
    parser.add_argument(
        "--out-dir",
        default="structured-data",
        help="Output directory (default: structured-data)",
    )
    args = parser.parse_args()

    return run_profile(args.profile, args.out_dir)


if __name__ == "__main__":
    raise SystemExit(main())
