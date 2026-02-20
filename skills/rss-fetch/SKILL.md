---
name: rss-fetch
description: Fetch RSS/Atom feeds, normalize new items to stable JSON, write digest/state/errors artifacts for downstream orchestrators.
---

# rss-fetch

## Purpose
`rss-fetch` is a deterministic, file-based skill that ingests RSS/Atom feeds and emits four stable output artifacts:

1. `data/items.json` (new normalized items only)
2. `data/digest.md` (human-readable digest)
3. `data/state.json` (seen IDs + feed metadata)
4. `data/errors.json` (per-feed errors)

This skill is intentionally implemented as local scripts (no MCP server) with stable paths and schemas so it can be swapped behind the same output contract later.

## Compatibility
- Runtime: Python `>=3.10`
- Dependencies: Python standard library only (no external package install required)
- Network behavior: explicit timeout, user-agent, max bytes, retries with backoff, per-feed error isolation

## Entrypoint
Run:

```bash
python3 skills/rss-fetch/scripts/rss_fetch.py \
  --feeds skills/rss-fetch/templates/feeds.txt \
  --out-dir skills/rss-fetch/data \
  --state-file skills/rss-fetch/data/state.json
```

Or use dated run folders (recommended for structured history):

```bash
python3 skills/rss-fetch/scripts/rss_fetch.py \
  --feeds skills/rss-fetch/templates/feeds.txt \
  --runs-root output/runs
```

This creates outputs in a per-run folder:

```text
output/runs/<YYYY-MM-DD>/<HHMMSSZ>/
```

## Inputs

### Feed list
- Default template file: `skills/rss-fetch/templates/feeds.txt`
- Format: one feed URL per line
- Blank lines and lines starting with `#` are ignored
- Supported feed sources:
  - `https://...` / `http://...`
  - `file:///...` (for local testing)
  - absolute/relative local file paths (for local testing)

### CLI flags
- `--feeds` (required): path to feed list file
- `--out-dir` (optional): output directory for `items.json`, `digest.md`, `errors.json`
- `--state-file` (optional): path to state file (defaults to `<out-dir>/state.json` when `--out-dir` is used)
- `--runs-root` (optional): run history root. If set, outputs go to `<runs-root>/<YYYY-MM-DD>/<HHMMSSZ>/` and state defaults to that run folder.
- `--since-hours` (optional, int): include only items published within N hours from current UTC time
- `--summary-max-chars` (optional, int, default `800`): max characters kept in `summary`
- `--max-items-per-feed` (optional, int, default `20`): cap normalized items per feed after date filtering
- `--timeout` (optional, float, default `10.0`): per-request timeout in seconds
- `--skip-network-check` (optional): skip startup connectivity preflight for HTTP(S) feeds

## Outputs

### 1) `items.json`
Path: `<out-dir>/items.json` (or `<runs-root>/<YYYY-MM-DD>/<HHMMSSZ>/items.json` when using `--runs-root`)

Always written. Contains only **new** items (not previously seen in `state.json`).

Schema:

```json
[
  {
    "id": "string",
    "title": "string",
    "url": "string",
    "published_at": "string|null",
    "summary": "string",
    "word_count": 0,
    "source": {
      "feed_url": "string",
      "site": "string|null",
      "title": "string|null"
    }
  }
]
```

### 2) `digest.md`
Path: `<out-dir>/digest.md` (or `<runs-root>/<YYYY-MM-DD>/<HHMMSSZ>/digest.md` when using `--runs-root`)

Always written. If no items are new, file still exists with header and `No new items.`.

### 3) `state.json`
Path: `--state-file` (defaults to `<out-dir>/state.json`, or run folder `state.json` when `--runs-root` is used)

Always written. Stores dedupe IDs and feed metadata.

Schema:

```json
{
  "version": 1,
  "seen_ids": ["string"],
  "feeds": {
    "<feed_url>": {
      "last_success_at": "ISO8601|null",
      "last_error_at": "ISO8601|null",
      "last_error": "string|null",
      "etag": "string|null",
      "last_modified": "string|null"
    }
  }
}
```

### 4) `errors.json`
Path: `<out-dir>/errors.json` (or `<runs-root>/<YYYY-MM-DD>/<HHMMSSZ>/errors.json` when using `--runs-root`)

Always written. Per-feed errors only; empty array when all succeed.

Schema:

```json
[
  {
    "feed_url": "string",
    "stage": "fetch|parse|normalize",
    "error": "string",
    "attempts": 1,
    "status_code": 0,
    "timestamp": "ISO8601"
  }
]
```

## Dedupe and state behavior
- Each normalized item gets a deterministic `id` derived from feed/item fields.
- On each run, IDs already present in `state.json.seen_ids` are skipped.
- New IDs are merged into `seen_ids` and saved sorted for stable output.
- Running twice with unchanged feeds should produce:
  - second run `items.json` as `[]`
  - second run digest with `No new items.`

## Failure modes and exit codes
- `0`: completed with no per-feed errors
- `2`: completed but one or more feeds failed (errors recorded in `errors.json`)
- `1`: invalid input/arguments or unrecoverable setup failure

The skill is fail-soft per feed: one feed error does not block others.
When HTTP(S) feeds are configured, a startup preflight checks internet connectivity and fails fast with a sandbox guidance message if network appears unavailable.

## Self-check
Run offline fixture validation:

```bash
python3 skills/rss-fetch/scripts/self_check.py
```

Checks performed:
- schema fields exist in emitted `items.json`
- dedupe works across two consecutive runs
- error isolation records a missing feed while successful feeds still emit items

## Feed Health Management
Use `feed_health.py` to track chronic failures and quarantine feeds safely.

Dry-run report (recommended after each fetch run):

```bash
python3 skills/rss-fetch/scripts/feed_health.py
```

Apply quarantine updates:

```bash
python3 skills/rss-fetch/scripts/feed_health.py \
  --apply \
  --failure-threshold 5 \
  --min-active-feeds 20
```

Behavior:
- Tracks consecutive failures per feed in `skills/rss-fetch/data/feed_health_state.json`
- Writes summary to `skills/rss-fetch/data/feed_health_report.json`
- In `--apply` mode, moves chronic failures from `templates/feeds.txt` to `templates/feeds.quarantine.txt`
- Never drops below `--min-active-feeds`
