#!/usr/bin/env python3
"""Track feed reliability and optionally quarantine chronic failures."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_FEEDS = "skills/rss-fetch/templates/feeds.txt"
DEFAULT_QUARANTINE = "skills/rss-fetch/templates/feeds.quarantine.txt"
DEFAULT_ERRORS = "skills/rss-fetch/data/errors.json"
DEFAULT_STATE = "skills/rss-fetch/data/state.json"
DEFAULT_HEALTH_STATE = "skills/rss-fetch/data/feed_health_state.json"
DEFAULT_REPORT = "skills/rss-fetch/data/feed_health_report.json"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manage RSS feed health and quarantine chronic failures")
    parser.add_argument("--feeds", default=DEFAULT_FEEDS, help="Active feeds list")
    parser.add_argument("--quarantine", default=DEFAULT_QUARANTINE, help="Quarantined feeds list")
    parser.add_argument("--errors", default=DEFAULT_ERRORS, help="Path to latest errors.json")
    parser.add_argument("--state", default=DEFAULT_STATE, help="Path to rss state.json")
    parser.add_argument("--health-state", default=DEFAULT_HEALTH_STATE, help="Path to feed health state JSON")
    parser.add_argument("--report", default=DEFAULT_REPORT, help="Path to report JSON")
    parser.add_argument("--failure-threshold", type=int, default=5, help="Consecutive failures before quarantine")
    parser.add_argument("--min-active-feeds", type=int, default=20, help="Minimum active feeds to keep")
    parser.add_argument("--apply", action="store_true", help="Apply quarantine updates to feed files")
    return parser.parse_args()


def read_feed_list(path: Path) -> list[str]:
    if not path.exists():
        return []
    feeds: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        feeds.append(s)
    return feeds


def write_feed_list(path: Path, feeds: list[str], header: str) -> None:
    unique = []
    seen = set()
    for feed in feeds:
        if feed in seen:
            continue
        seen.add(feed)
        unique.append(feed)

    path.parent.mkdir(parents=True, exist_ok=True)
    body = [header, "# One URL per line", ""]
    body.extend(unique)
    path.write_text("\n".join(body).rstrip() + "\n", encoding="utf-8")


def load_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    args = parse_args()

    feeds_path = Path(args.feeds)
    quarantine_path = Path(args.quarantine)
    errors_path = Path(args.errors)
    state_path = Path(args.state)
    health_state_path = Path(args.health_state)
    report_path = Path(args.report)

    if args.failure_threshold < 1:
        raise SystemExit("--failure-threshold must be >= 1")
    if args.min_active_feeds < 0:
        raise SystemExit("--min-active-feeds must be >= 0")

    active_feeds = read_feed_list(feeds_path)
    quarantine_feeds = read_feed_list(quarantine_path)

    errors = load_json(errors_path, [])
    rss_state = load_json(state_path, {"feeds": {}})
    health_state = load_json(health_state_path, {"version": 1, "feeds": {}})

    if not isinstance(errors, list):
        raise SystemExit(f"Invalid errors file format: {errors_path}")
    if not isinstance(rss_state, dict):
        raise SystemExit(f"Invalid state file format: {state_path}")
    if not isinstance(health_state, dict):
        raise SystemExit(f"Invalid health state file format: {health_state_path}")

    error_map: dict[str, str] = {}
    for item in errors:
        if not isinstance(item, dict):
            continue
        feed = str(item.get("feed_url", "")).strip()
        if not feed:
            continue
        err = str(item.get("error", "")).strip() or "unknown"
        error_map[feed] = err

    tracked = set(active_feeds) | set(quarantine_feeds) | set(health_state.get("feeds", {}).keys())

    feeds_health = health_state.setdefault("feeds", {})
    if not isinstance(feeds_health, dict):
        feeds_health = {}
        health_state["feeds"] = feeds_health

    for feed in sorted(tracked):
        prev = feeds_health.get(feed, {})
        if not isinstance(prev, dict):
            prev = {}

        prev_failures = int(prev.get("consecutive_failures", 0) or 0)
        status = str(prev.get("last_status", "unknown"))
        last_error = prev.get("last_error")

        checked_this_run = feed in active_feeds
        failed_this_run = feed in error_map

        if checked_this_run and failed_this_run:
            failures = prev_failures + 1
            status = "error"
            last_error = error_map[feed]
        elif checked_this_run and not failed_this_run:
            failures = 0
            status = "ok"
            last_error = None
        else:
            failures = prev_failures

        feed_state = rss_state.get("feeds", {}).get(feed, {}) if isinstance(rss_state.get("feeds", {}), dict) else {}
        feeds_health[feed] = {
            "consecutive_failures": failures,
            "last_status": status,
            "last_error": last_error,
            "last_checked_at": now_iso() if checked_this_run else prev.get("last_checked_at"),
            "last_success_at": feed_state.get("last_success_at") if isinstance(feed_state, dict) else None,
            "last_error_at": feed_state.get("last_error_at") if isinstance(feed_state, dict) else None,
            "quarantined": feed in quarantine_feeds,
        }

    candidates = []
    for feed in active_feeds:
        meta = feeds_health.get(feed, {})
        if int(meta.get("consecutive_failures", 0) or 0) >= args.failure_threshold:
            candidates.append(feed)

    candidates.sort(key=lambda f: int(feeds_health.get(f, {}).get("consecutive_failures", 0)), reverse=True)

    quarantined_now: list[str] = []
    blocked_by_floor: list[str] = []

    new_active = list(active_feeds)
    new_quarantine = list(quarantine_feeds)

    for feed in candidates:
        if len(new_active) <= args.min_active_feeds:
            blocked_by_floor.append(feed)
            continue
        if args.apply and feed in new_active:
            new_active.remove(feed)
            if feed not in new_quarantine:
                new_quarantine.append(feed)
            quarantined_now.append(feed)

    for feed in new_quarantine:
        meta = feeds_health.get(feed)
        if isinstance(meta, dict):
            meta["quarantined"] = True

    summary = {
        "checked_at": now_iso(),
        "active_count": len(active_feeds),
        "quarantine_count": len(quarantine_feeds),
        "error_count": len(error_map),
        "failure_threshold": args.failure_threshold,
        "min_active_feeds": args.min_active_feeds,
        "candidates": [
            {
                "feed_url": feed,
                "consecutive_failures": int(feeds_health.get(feed, {}).get("consecutive_failures", 0) or 0),
                "last_error": feeds_health.get(feed, {}).get("last_error"),
            }
            for feed in candidates
        ],
        "blocked_by_floor": blocked_by_floor,
        "apply": args.apply,
        "quarantined_now": quarantined_now,
        "active_after": len(new_active) if args.apply else len(active_feeds),
        "quarantine_after": len(new_quarantine) if args.apply else len(quarantine_feeds),
    }

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    health_state["version"] = 1
    health_state_path.parent.mkdir(parents=True, exist_ok=True)
    health_state_path.write_text(json.dumps(health_state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if args.apply:
        write_feed_list(feeds_path, new_active, "# Active feeds")
        write_feed_list(quarantine_path, new_quarantine, "# Quarantined feeds")

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
