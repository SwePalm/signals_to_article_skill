#!/usr/bin/env python3
"""Fetch RSS/Atom feeds and emit normalized items, digest, state, and errors."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import socket
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

MAX_BYTES = 2 * 1024 * 1024
RETRIES = 3
BACKOFF_BASE_SECONDS = 0.5
DEFAULT_USER_AGENT = "rss-fetch/1.0 (+local-skill)"
NETWORK_CHECK_URL = "https://example.com/"


@dataclass
class FeedErrorRecord:
    feed_url: str
    stage: str
    error: str
    attempts: int
    status_code: int


class FeedProcessingError(Exception):
    def __init__(self, stage: str, message: str, attempts: int = 1, status_code: int = 0) -> None:
        super().__init__(message)
        self.stage = stage
        self.message = message
        self.attempts = attempts
        self.status_code = status_code


class _HTMLToText(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []

    def handle_data(self, data: str) -> None:
        if data:
            self._chunks.append(data)

    def text(self) -> str:
        return " ".join(self._chunks)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def first_text(elem: ET.Element | None, names: list[str]) -> str | None:
    if elem is None:
        return None
    wanted = set(names)
    for child in elem.iter():
        if local_name(child.tag) in wanted:
            text = (child.text or "").strip()
            if text:
                return text
    return None


def first_attr(elem: ET.Element | None, element_name: str, attr_name: str) -> str | None:
    if elem is None:
        return None
    for child in elem.iter():
        if local_name(child.tag) == element_name:
            val = (child.attrib.get(attr_name) or "").strip()
            if val:
                return val
    return None


def html_to_text(value: str | None, limit: int | None = 300) -> str:
    if not value:
        return ""
    parser = _HTMLToText()
    parser.feed(value)
    txt = parser.text()
    txt = re.sub(r"\s+", " ", txt).strip()
    if limit is not None and len(txt) > limit:
        return txt[: limit - 1].rstrip() + "..."
    return txt


def word_count(text: str) -> int:
    if not text:
        return 0
    return len(re.findall(r"\b\w+\b", text))


def parse_date_to_iso(value: str | None) -> str | None:
    if not value:
        return None
    raw = value.strip()
    if not raw:
        return None

    try:
        dt = parsedate_to_datetime(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except (TypeError, ValueError):
        pass

    iso_candidate = raw.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(iso_candidate)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except ValueError:
        return None


def read_feeds_file(path: Path) -> list[str]:
    if not path.exists():
        raise FeedProcessingError("input", f"Feeds file not found: {path}")

    lines = path.read_text(encoding="utf-8").splitlines()
    feeds: list[str] = []
    for line in lines:
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        feeds.append(s)

    if not feeds:
        raise FeedProcessingError("input", f"No feed URLs found in {path}")
    return feeds


def is_http_url(value: str) -> bool:
    scheme = urlparse(value).scheme.lower()
    return scheme in {"http", "https"}


def resolve_local_path(feed_url: str) -> Path:
    parsed = urlparse(feed_url)
    if parsed.scheme == "file":
        decoded_path = unquote(parsed.path)
        return Path(os.path.abspath(os.path.expanduser(os.path.join(parsed.netloc, decoded_path))))
    return Path(feed_url).expanduser().resolve()


def fetch_feed_bytes(feed_url: str, timeout: float, user_agent: str) -> tuple[bytes, int, int]:
    last_error: Exception | None = None
    last_status = 0

    for attempt in range(1, RETRIES + 1):
        try:
            if is_http_url(feed_url):
                req = Request(
                    feed_url,
                    headers={
                        "User-Agent": user_agent,
                        "Accept": "application/atom+xml, application/rss+xml, application/xml, text/xml;q=0.9, */*;q=0.1",
                    },
                )
                with urlopen(req, timeout=timeout) as resp:
                    status = int(getattr(resp, "status", 200) or 200)
                    data = read_limited(resp, MAX_BYTES)
                    return data, status, attempt

            path = resolve_local_path(feed_url)
            with path.open("rb") as f:
                data = read_limited(f, MAX_BYTES)
            return data, 200, attempt
        except HTTPError as e:
            last_error = e
            last_status = e.code or 0
            if 400 <= (e.code or 0) < 500:
                break
        except (URLError, OSError, ValueError, socket.timeout) as e:
            last_error = e

        if attempt < RETRIES:
            time.sleep(BACKOFF_BASE_SECONDS * (2 ** (attempt - 1)))

    msg = f"{type(last_error).__name__}: {last_error}" if last_error else "unknown fetch error"
    raise FeedProcessingError("fetch", msg, attempts=RETRIES, status_code=last_status)


def preflight_network_check(timeout: float, user_agent: str, target_url: str = NETWORK_CHECK_URL) -> None:
    req = Request(target_url, headers={"User-Agent": user_agent, "Accept": "*/*"})
    try:
        with urlopen(req, timeout=max(3.0, min(timeout, 5.0))) as _resp:
            return
    except Exception as e:
        raise FeedProcessingError(
            "input",
            (
                "Network preflight failed. Network access may be disabled in sandbox. "
                "Enable network_access = true in workspace-write mode. "
                f"Preflight URL: {target_url}. Error: {type(e).__name__}: {e}"
            ),
        ) from e


def read_limited(stream: Any, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = stream.read(8192)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise FeedProcessingError("fetch", f"Feed exceeded max bytes ({max_bytes})")
        chunks.append(chunk)
    return b"".join(chunks)


def parse_feed(xml_bytes: bytes, feed_url: str) -> tuple[dict[str, str | None], list[dict[str, str | None]]]:
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        raise FeedProcessingError("parse", f"XML parse error: {e}") from e

    root_kind = local_name(root.tag)
    if root_kind == "rss":
        return parse_rss(root, feed_url)
    if root_kind == "feed":
        return parse_atom(root, feed_url)
    raise FeedProcessingError("parse", f"Unsupported feed root element: {root_kind}")


def parse_rss(root: ET.Element, feed_url: str) -> tuple[dict[str, str | None], list[dict[str, str | None]]]:
    channel = next((c for c in root if local_name(c.tag) == "channel"), None)
    if channel is None:
        raise FeedProcessingError("parse", "RSS channel element missing")

    feed_title = first_text(channel, ["title"])
    site = first_text(channel, ["link"])
    entries: list[dict[str, str | None]] = []

    for child in channel:
        if local_name(child.tag) != "item":
            continue
        entries.append(
            {
                "guid": first_text(child, ["guid"]),
                "title": first_text(child, ["title"]),
                "url": first_text(child, ["link"]),
                "published_raw": first_text(child, ["pubDate", "published", "updated"]),
                "summary_raw": first_text(child, ["description", "summary", "content"]),
            }
        )

    return {"feed_url": feed_url, "site": site, "title": feed_title}, entries


def parse_atom(root: ET.Element, feed_url: str) -> tuple[dict[str, str | None], list[dict[str, str | None]]]:
    feed_title = first_text(root, ["title"])
    site = first_attr(root, "link", "href")
    entries: list[dict[str, str | None]] = []

    for child in root:
        if local_name(child.tag) != "entry":
            continue

        link = None
        for link_node in child.iter():
            if local_name(link_node.tag) != "link":
                continue
            href = (link_node.attrib.get("href") or "").strip()
            rel = (link_node.attrib.get("rel") or "alternate").strip().lower()
            if href and rel == "alternate":
                link = href
                break
            if href and link is None:
                link = href

        entries.append(
            {
                "guid": first_text(child, ["id"]),
                "title": first_text(child, ["title"]),
                "url": link,
                "published_raw": first_text(child, ["published", "updated"]),
                "summary_raw": first_text(child, ["summary", "content"]),
            }
        )

    return {"feed_url": feed_url, "site": site, "title": feed_title}, entries


def make_item_id(feed_url: str, raw: dict[str, str | None]) -> str:
    guid = (raw.get("guid") or "").strip()
    title = (raw.get("title") or "").strip()
    url = (raw.get("url") or "").strip()
    published = (raw.get("published_raw") or "").strip()

    key = guid or url or f"{title}|{published}"
    base = f"{feed_url}|{key}|{url}|{published}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def normalize_item(feed_meta: dict[str, str | None], raw: dict[str, str | None], summary_max_chars: int) -> dict[str, Any]:
    title = (raw.get("title") or "").strip()
    url = (raw.get("url") or "").strip()
    summary_text = html_to_text(raw.get("summary_raw"), limit=None)

    if not title and not url:
        raise FeedProcessingError("normalize", "Item missing both title and url")

    return {
        "id": make_item_id(feed_meta["feed_url"] or "", raw),
        "title": title,
        "url": url,
        "published_at": parse_date_to_iso(raw.get("published_raw")),
        "summary": html_to_text(raw.get("summary_raw"), limit=summary_max_chars),
        "word_count": word_count(summary_text),
        "source": {
            "feed_url": feed_meta.get("feed_url") or "",
            "site": feed_meta.get("site"),
            "title": feed_meta.get("title"),
        },
    }


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"version": 1, "seen_ids": [], "feeds": {}}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise FeedProcessingError("input", f"Invalid state JSON at {path}: {e}") from e

    if not isinstance(data, dict):
        raise FeedProcessingError("input", f"State file must be a JSON object: {path}")

    data.setdefault("version", 1)
    data.setdefault("seen_ids", [])
    data.setdefault("feeds", {})

    if not isinstance(data["seen_ids"], list):
        raise FeedProcessingError("input", "state.seen_ids must be an array")
    if not isinstance(data["feeds"], dict):
        raise FeedProcessingError("input", "state.feeds must be an object")

    return data


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, payload: Any) -> None:
    ensure_parent(path)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def build_digest(items: list[dict[str, Any]]) -> str:
    lines = ["# Feed Digest", ""]
    if not items:
        lines.append("No new items.")
        lines.append("")
        return "\n".join(lines)

    for item in items:
        title = item.get("title") or "(untitled)"
        url = item.get("url") or ""
        published = item.get("published_at") or "unknown"
        source_title = item.get("source", {}).get("title") or item.get("source", {}).get("feed_url") or "unknown"

        lines.append(f"## {title}")
        lines.append("")
        lines.append(f"- Source: {source_title}")
        lines.append(f"- Published: {published}")
        if url:
            lines.append(f"- URL: {url}")
        summary = item.get("summary") or ""
        if summary:
            lines.append(f"- Summary: {summary}")
        lines.append("")

    return "\n".join(lines)


def update_feed_status(state: dict[str, Any], feed_url: str, success: bool, error_message: str | None = None) -> None:
    feed_meta = state["feeds"].setdefault(
        feed_url,
        {
            "last_success_at": None,
            "last_error_at": None,
            "last_error": None,
            "etag": None,
            "last_modified": None,
        },
    )

    if success:
        feed_meta["last_success_at"] = now_iso()
        feed_meta["last_error_at"] = None
        feed_meta["last_error"] = None
    else:
        feed_meta["last_error_at"] = now_iso()
        feed_meta["last_error"] = error_message


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Fetch RSS/Atom feeds and emit normalized outputs.")
    p.add_argument("--feeds", required=True, help="Path to feeds.txt")
    p.add_argument("--out-dir", default=None, help="Output directory")
    p.add_argument(
        "--runs-root",
        default=None,
        help="Root folder for dated run output (creates <runs-root>/<YYYY-MM-DD>/<HHMMSSZ>/)",
    )
    p.add_argument("--since-hours", type=int, default=None, help="Only include items newer than N hours")
    p.add_argument("--summary-max-chars", type=int, default=800, help="Max summary characters per item")
    p.add_argument("--max-items-per-feed", type=int, default=20, help="Max items per feed")
    p.add_argument("--timeout", type=float, default=10.0, help="HTTP timeout seconds")
    p.add_argument("--state-file", default=None, help="Path to state.json")
    p.add_argument("--skip-network-check", action="store_true", help="Skip startup internet connectivity preflight")
    return p.parse_args(argv)


def resolve_output_paths(args: argparse.Namespace) -> tuple[Path, Path]:
    if args.runs_root:
        now = datetime.now(timezone.utc)
        run_dir = Path(args.runs_root) / now.strftime("%Y-%m-%d") / now.strftime("%H%M%SZ")
        out_dir = run_dir
        state_path = Path(args.state_file) if args.state_file else run_dir / "state.json"
        return out_dir, state_path

    if args.out_dir and args.state_file:
        return Path(args.out_dir), Path(args.state_file)

    if args.out_dir and not args.state_file:
        out_dir = Path(args.out_dir)
        return out_dir, out_dir / "state.json"

    if args.state_file and not args.out_dir:
        raise FeedProcessingError("input", "--out-dir is required when --state-file is provided")

    raise FeedProcessingError("input", "Provide either --runs-root or --out-dir (and optionally --state-file)")


def run(argv: list[str]) -> int:
    args = parse_args(argv)

    if args.max_items_per_feed <= 0:
        raise FeedProcessingError("input", "--max-items-per-feed must be > 0")
    if args.timeout <= 0:
        raise FeedProcessingError("input", "--timeout must be > 0")
    if args.since_hours is not None and args.since_hours < 0:
        raise FeedProcessingError("input", "--since-hours must be >= 0")
    if args.summary_max_chars <= 0:
        raise FeedProcessingError("input", "--summary-max-chars must be > 0")

    feeds_path = Path(args.feeds)
    out_dir, state_path = resolve_output_paths(args)

    feeds = read_feeds_file(feeds_path)
    if not args.skip_network_check and any(is_http_url(feed_url) for feed_url in feeds):
        preflight_network_check(timeout=args.timeout, user_agent=DEFAULT_USER_AGENT)

    state = load_state(state_path)

    seen_ids = set(str(x) for x in state.get("seen_ids", []))
    errors: list[dict[str, Any]] = []
    new_items: list[dict[str, Any]] = []

    cutoff = None
    if args.since_hours is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=args.since_hours)

    for feed_url in feeds:
        try:
            xml_bytes, status_code, attempts = fetch_feed_bytes(feed_url, timeout=args.timeout, user_agent=DEFAULT_USER_AGENT)
            feed_meta, raw_items = parse_feed(xml_bytes, feed_url)

            feed_items: list[dict[str, Any]] = []
            for raw in raw_items:
                item = normalize_item(feed_meta, raw, summary_max_chars=args.summary_max_chars)
                if cutoff and item["published_at"]:
                    parsed = datetime.fromisoformat(item["published_at"].replace("Z", "+00:00"))
                    if parsed < cutoff:
                        continue
                feed_items.append(item)

            for item in feed_items[: args.max_items_per_feed]:
                if item["id"] in seen_ids:
                    continue
                seen_ids.add(item["id"])
                new_items.append(item)

            update_feed_status(state, feed_url, success=True)
        except FeedProcessingError as e:
            update_feed_status(state, feed_url, success=False, error_message=e.message)
            errors.append(
                {
                    "feed_url": feed_url,
                    "stage": e.stage,
                    "error": e.message,
                    "attempts": e.attempts,
                    "status_code": e.status_code,
                    "timestamp": now_iso(),
                }
            )
        except Exception as e:  # pragma: no cover
            update_feed_status(state, feed_url, success=False, error_message=str(e))
            errors.append(
                {
                    "feed_url": feed_url,
                    "stage": "unknown",
                    "error": f"{type(e).__name__}: {e}",
                    "attempts": 1,
                    "status_code": 0,
                    "timestamp": now_iso(),
                }
            )

    state["seen_ids"] = sorted(seen_ids)

    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "items.json", new_items)
    (out_dir / "digest.md").write_text(build_digest(new_items), encoding="utf-8")
    write_json(out_dir / "errors.json", errors)
    write_json(state_path, state)

    return 2 if errors else 0


def main() -> int:
    try:
        return run(sys.argv[1:])
    except FeedProcessingError as e:
        sys.stderr.write(f"{e.stage} error: {e.message}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
