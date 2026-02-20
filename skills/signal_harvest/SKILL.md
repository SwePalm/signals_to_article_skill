---
name: Signal Harvest
description: Captures raw signals from the environment.
allowed-tools: All
---

# Signal Harvest

**Goal:** Gather 8-12 raw signals relevant to the session theme.

## Instructions
1.  **Web harvest (required):** Use the model's native web search capability to collect 4-8 recent, real-world signals related to the current theme.
2.  **RSS harvest (required):** Run rss-fetch with a 24-hour window:
    ```bash
    python3 skills/rss-fetch/scripts/rss_fetch.py \
      --feeds skills/rss-fetch/templates/feeds.txt \
      --out-dir skills/rss-fetch/data \
      --state-file skills/rss-fetch/data/state.json \
      --since-hours 24
    ```
3.  **Save web results:** Write web-search results to `artifacts/web_signals.json` using this schema:
    * `title`
    * `summary`
    * `category`
    * `source`
    * `date` (YYYY-MM-DD)
    * `url`
4.  **Merge and normalize sources:** Combine web + RSS into one list:
    ```bash
    python3 skills/signal_harvest/scripts/merge_signals.py \
      --web-signals artifacts/web_signals.json \
      --rss-items skills/rss-fetch/data/items.json \
      --output artifacts/raw_signals.json \
      --max-signals 12 \
      --min-web 4 \
      --min-rss 4
    ```
5.  **Output contract:** `artifacts/raw_signals.json` should contain 8-12 deduped signals with:
    * `id`
    * `title`
    * `summary`
    * `category`
    * `source`
    * `date`
    * `url`
    * `channel` (`web` or `rss`)
6.  **Quality bar:**
    * Avoid duplicates across channels.
    * Prefer concrete events over opinion-only commentary.
    * Prefer primary announcements, official docs, or high-credibility reporting.
7.  **Fallback (optional):** If web search is unavailable, run the mock script and label output as demo:
    ```bash
    python skills/signal_harvest/scripts/harvest.py
    ```
    Then merge it with RSS by saving mock output to `artifacts/web_signals.json` and running `merge_signals.py`.

## Script Usage
* `harvest.py` is a mock fallback for testing and should not be treated as live market intelligence.
* `merge_signals.py` is the deterministic combiner for web + RSS channels.
