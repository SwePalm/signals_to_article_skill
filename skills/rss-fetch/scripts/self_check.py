#!/usr/bin/env python3
"""Offline self-check for rss-fetch schema, dedupe, and error isolation."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FETCH_SCRIPT = ROOT / "scripts" / "rss_fetch.py"
FIXTURES = ROOT / "tests" / "fixtures"

REQUIRED_ITEM_KEYS = {"id", "title", "url", "published_at", "summary", "word_count", "source"}
REQUIRED_SOURCE_KEYS = {"feed_url", "site", "title"}


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def run_fetch(feeds_file: Path, out_dir: Path, state_file: Path) -> subprocess.CompletedProcess[str]:
    cmd = [
        sys.executable,
        str(FETCH_SCRIPT),
        "--feeds",
        str(feeds_file),
        "--out-dir",
        str(out_dir),
        "--state-file",
        str(state_file),
        "--max-items-per-feed",
        "10",
        "--timeout",
        "2",
    ]
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    rss_file = (FIXTURES / "sample_rss.xml").resolve()
    atom_file = (FIXTURES / "sample_atom.xml").resolve()
    missing_file = (FIXTURES / "missing.xml").resolve()

    assert_true(rss_file.exists(), f"Missing fixture: {rss_file}")
    assert_true(atom_file.exists(), f"Missing fixture: {atom_file}")

    with tempfile.TemporaryDirectory(prefix="rss-fetch-selfcheck-") as tmp:
        tmp_dir = Path(tmp)
        out_dir = tmp_dir / "data"
        state_file = out_dir / "state.json"
        feeds_file = tmp_dir / "feeds.txt"

        feeds_file.write_text(
            "\n".join(
                [
                    rss_file.as_uri(),
                    atom_file.as_uri(),
                    missing_file.as_uri(),
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        first = run_fetch(feeds_file, out_dir, state_file)
        assert_true(first.returncode == 2, f"Expected exit 2 on first run, got {first.returncode}")

        items_path = out_dir / "items.json"
        digest_path = out_dir / "digest.md"
        errors_path = out_dir / "errors.json"
        assert_true(items_path.exists(), "items.json not created")
        assert_true(digest_path.exists(), "digest.md not created")
        assert_true(errors_path.exists(), "errors.json not created")
        assert_true(state_file.exists(), "state.json not created")

        items = load_json(items_path)
        errors = load_json(errors_path)

        assert_true(isinstance(items, list), "items.json is not an array")
        assert_true(len(items) >= 2, "Expected at least two new items from fixtures")
        assert_true(isinstance(errors, list) and len(errors) == 1, "Expected one isolated feed error")

        for item in items:
            assert_true(REQUIRED_ITEM_KEYS.issubset(item.keys()), f"Item missing keys: {item}")
            assert_true(isinstance(item["source"], dict), "item.source must be object")
            assert_true(REQUIRED_SOURCE_KEYS.issubset(item["source"].keys()), "item.source missing keys")
            assert_true(isinstance(item["word_count"], int) and item["word_count"] >= 0, "item.word_count invalid")

        second = run_fetch(feeds_file, out_dir, state_file)
        assert_true(second.returncode == 2, f"Expected exit 2 on second run, got {second.returncode}")

        second_items = load_json(items_path)
        second_digest = digest_path.read_text(encoding="utf-8")

        assert_true(second_items == [], "Dedupe failed: second run should emit zero new items")
        assert_true("No new items." in second_digest, "Digest should indicate no new items")

    print("self-check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
