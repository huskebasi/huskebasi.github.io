#!/usr/bin/env python3
"""Fetch tides for the configured spots and write a static JSON file.

Usage:
    RAPIDAPI_KEY=... python3 tools/fetch_tides.py spots.json tides.json

The output is consumed by index.html (and can be reused by other clients).
No API key is ever written to the output.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

API_URL = "https://tides.p.rapidapi.com/tides"
API_HOST = "tides.p.rapidapi.com"
DURATION_MINUTES = 7 * 24 * 60  # 7 days
INTERVAL_MINUTES = 60


def normalise_extreme(raw: dict[str, Any]) -> dict[str, Any]:
    state = str(raw.get("state", "")).upper()
    if "HIGH" in state:
        state = "HIGH"
    elif "LOW" in state:
        state = "LOW"
    return {
        "state": state,
        "timestamp": int(raw["timestamp"]),
        "height": round(float(raw["height"]), 3),
    }


def normalise_height(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "state": str(raw.get("state", "")).upper(),
        "timestamp": int(raw["timestamp"]),
        "height": round(float(raw["height"]), 3),
    }


def fetch_spot(spot: dict[str, Any], key: str, timeout: int = 30) -> dict[str, Any]:
    query = urllib.parse.urlencode(
        {
            "latitude": spot["lat"],
            "longitude": spot["lon"],
            "duration": DURATION_MINUTES,
            "interval": INTERVAL_MINUTES,
        }
    )
    request = urllib.request.Request(
        f"{API_URL}?{query}",
        headers={
            "x-rapidapi-key": key,
            "x-rapidapi-host": API_HOST,
            "Accept": "application/json",
            "User-Agent": "huskebasi-tides/1.0",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")[:500]
        raise RuntimeError(f"HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"network error: {exc.reason}") from exc

    if not isinstance(payload, dict):
        raise RuntimeError("unexpected response: not a JSON object")

    extremes = [normalise_extreme(x) for x in payload.get("extremes", [])]
    heights = [normalise_height(x) for x in payload.get("heights", [])]
    extremes.sort(key=lambda x: x["timestamp"])
    heights.sort(key=lambda x: x["timestamp"])

    origin = payload.get("origin") or {}
    return {
        "name": spot["name"],
        "latitude": float(spot["lat"]),
        "longitude": float(spot["lon"]),
        "origin": {
            "latitude": origin.get("latitude"),
            "longitude": origin.get("longitude"),
            "distance": origin.get("distance"),
            "unit": origin.get("unit", "km"),
        },
        "unit": payload.get("unit", "m"),
        "fetchedAt": int(time.time()),
        "extremes": extremes,
        "heights": heights,
        "copyright": payload.get("copyright"),
        "stale": False,
    }


def load_existing(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"warning: cannot read existing {path}: {exc}", file=sys.stderr)
        return {}

    spots = data.get("spots", []) if isinstance(data, dict) else data
    if not isinstance(spots, list):
        return {}
    return {
        str(item.get("name")): item
        for item in spots
        if isinstance(item, dict) and item.get("name")
    }


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("spots", type=Path, help="input spots JSON")
    parser.add_argument("output", type=Path, help="output tides JSON")
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="seconds between API calls (default: 1)",
    )
    args = parser.parse_args()

    key = os.environ.get("RAPIDAPI_KEY") or os.environ.get("TIDES_RAPIDAPI_KEY")
    if not key:
        print("error: RAPIDAPI_KEY is not set", file=sys.stderr)
        return 2

    try:
        spots = json.loads(args.spots.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error: cannot read {args.spots}: {exc}", file=sys.stderr)
        return 2

    if not isinstance(spots, list) or not spots:
        print("error: spots file must contain a non-empty list", file=sys.stderr)
        return 2

    existing = load_existing(args.output)
    results: list[dict[str, Any]] = []
    failures = 0
    successes = 0

    for index, spot in enumerate(spots):
        if not isinstance(spot, dict) or "name" not in spot:
            print(f"warning: skipping invalid spot at index {index}", file=sys.stderr)
            failures += 1
            continue

        name = str(spot["name"])
        try:
            item = fetch_spot(spot, key)
            item["stale"] = False
            results.append(item)
            successes += 1
            print(
                f"ok: {name} ({len(item['extremes'])} extremes, "
                f"{len(item['heights'])} heights)"
            )
        except Exception as exc:  # noqa: BLE001 - report and keep going
            failures += 1
            print(f"error: {name}: {exc}", file=sys.stderr)
            old = existing.get(name)
            if old:
                old = dict(old)
                old["stale"] = True
                results.append(old)
                print(f"kept previous data for {name}", file=sys.stderr)

        if index + 1 < len(spots):
            time.sleep(max(0.0, args.delay))

    if successes == 0:
        print(
            "error: no spot could be fetched; keeping the existing file untouched",
            file=sys.stderr,
        )
        return 1

    if not results:
        print("error: no spot could be fetched and no previous data exists", file=sys.stderr)
        return 1

    output = {
        "generatedAt": int(time.time()),
        "source": "rapidapi:tides",
        "spots": results,
    }
    write_json(args.output, output)
    print(f"wrote {args.output} ({len(results)} spots, {failures} failures)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
