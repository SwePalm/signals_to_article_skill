#!/usr/bin/env python3
"""Merge web-search and RSS signals into a single ranked-input JSON list."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


CATEGORY_KEYWORDS = {
    "Regulation": ["regulation", "regulatory", "ai act", "policy", "compliance", "gdpr", "law"],
    "Infrastructure": ["platform", "infrastructure", "cloud", "bedrock", "vertex", "api", "runtime"],
    "Agents": ["agent", "autonomous", "operator", "multi-agent", "orchestration"],
    "DevTools": ["developer", "dev", "copilot", "code", "github", "ci", "testing"],
    "Security": ["security", "identity", "audit", "verification", "trust", "attestation"],
    "Enterprise Software": ["enterprise", "saas", "crm", "erp", "workflow", "copilot studio"],
    "Fintech": ["bank", "banking", "fintech", "payments", "wallet", "trading"],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge web and RSS signals into one JSON list")
    parser.add_argument("--web-signals", default="artifacts/web_signals.json", help="Path to web signals JSON list")
    parser.add_argument("--rss-items", default="skills/rss-fetch/data/items.json", help="Path to rss-fetch items.json")
    parser.add_argument("--output", default="artifacts/raw_signals.json", help="Path to merged output JSON")
    parser.add_argument("--max-signals", type=int, default=12, help="Maximum number of merged signals")
    parser.add_argument("--min-web", type=int, default=4, help="Minimum number of web channel signals to keep (if available)")
    parser.add_argument("--min-rss", type=int, default=4, help="Minimum number of rss channel signals to keep (if available)")
    return parser.parse_args()


def load_json_array(path: Path) -> list[dict]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"Expected JSON array in {path}")
    return [x for x in data if isinstance(x, dict)]


def normalize_title(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9\s]", "", value)
    value = re.sub(r"\s+", " ", value)
    return value


def iso_or_none(value: str | None) -> str | None:
    if not value:
        return None
    raw = str(value).strip().replace("Z", "+00:00")
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).date().isoformat()
    except ValueError:
        return None


def infer_category(title: str, summary: str) -> str:
    text = f"{title} {summary}".lower()
    best_name = "Industry"
    best_score = 0
    for name, terms in CATEGORY_KEYWORDS.items():
        score = sum(1 for term in terms if term in text)
        if score > best_score:
            best_score = score
            best_name = name
    return best_name


def stable_id(channel: str, title: str, url: str) -> str:
    raw = f"{channel}|{title.strip().lower()}|{url.strip().lower()}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:10]
    return f"sig_{channel}_{digest}"


def format_source(source: str | None, url: str) -> str:
    if source:
        return str(source).strip()
    parsed = urlparse(url)
    if parsed.netloc:
        return parsed.netloc
    return "Unknown"


def to_web_signal(item: dict) -> dict | None:
    title = str(item.get("title", "")).strip()
    if not title:
        return None
    url = str(item.get("url", "")).strip()
    summary = str(item.get("summary", "")).strip()
    category = str(item.get("category", "")).strip() or infer_category(title, summary)
    date = iso_or_none(item.get("date"))

    return {
        "id": str(item.get("id") or stable_id("web", title, url)),
        "title": title,
        "summary": summary,
        "category": category,
        "source": format_source(item.get("source"), url),
        "date": date,
        "url": url,
        "channel": "web",
    }


def to_rss_signal(item: dict) -> dict | None:
    title = str(item.get("title", "")).strip()
    url = str(item.get("url", "")).strip()
    if not title and not url:
        return None
    summary = str(item.get("summary", "")).strip()
    source_obj = item.get("source") or {}
    if not isinstance(source_obj, dict):
        source_obj = {}
    source = source_obj.get("title") or source_obj.get("site") or source_obj.get("feed_url")
    category = infer_category(title, summary)
    date = iso_or_none(item.get("published_at"))

    return {
        "id": stable_id("rss", title or url, url),
        "title": title or url,
        "summary": summary,
        "category": category,
        "source": format_source(source, url),
        "date": date,
        "url": url,
        "channel": "rss",
    }


def dedupe(signals: list[dict]) -> list[dict]:
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    out: list[dict] = []

    for sig in signals:
        url = str(sig.get("url", "")).strip().lower()
        nt = normalize_title(str(sig.get("title", "")))
        if url and url in seen_urls:
            continue
        if nt and nt in seen_titles:
            continue
        if url:
            seen_urls.add(url)
        if nt:
            seen_titles.add(nt)
        out.append(sig)

    return out


def sort_key(sig: dict) -> tuple:
    date = sig.get("date") or "1970-01-01"
    channel = sig.get("channel") or ""
    title = sig.get("title") or ""
    # Prefer newest, then web (often more curated), then title
    return (date, channel == "web", title)


def select_balanced(signals: list[dict], max_signals: int, min_web: int, min_rss: int) -> list[dict]:
    web = [s for s in signals if s.get("channel") == "web"]
    rss = [s for s in signals if s.get("channel") == "rss"]
    other = [s for s in signals if s.get("channel") not in {"web", "rss"}]

    web.sort(key=sort_key, reverse=True)
    rss.sort(key=sort_key, reverse=True)
    other.sort(key=sort_key, reverse=True)

    selected: list[dict] = []

    for item in web[: max(0, min_web)]:
        if len(selected) < max_signals:
            selected.append(item)
    for item in rss[: max(0, min_rss)]:
        if len(selected) < max_signals:
            selected.append(item)

    used_ids = {item.get("id") for item in selected}
    remainder = [s for s in sorted(signals, key=sort_key, reverse=True) if s.get("id") not in used_ids]
    for item in remainder:
        if len(selected) >= max_signals:
            break
        selected.append(item)

    return selected


def main() -> int:
    args = parse_args()

    web_items = load_json_array(Path(args.web_signals))
    rss_items = load_json_array(Path(args.rss_items))

    merged: list[dict] = []
    for item in web_items:
        sig = to_web_signal(item)
        if sig:
            merged.append(sig)
    for item in rss_items:
        sig = to_rss_signal(item)
        if sig:
            merged.append(sig)

    deduped = dedupe(merged)
    final = select_balanced(
        deduped,
        max_signals=args.max_signals,
        min_web=args.min_web,
        min_rss=args.min_rss,
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(final, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(json.dumps({"web": len(web_items), "rss": len(rss_items), "merged": len(merged), "deduped": len(deduped), "written": len(final)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
