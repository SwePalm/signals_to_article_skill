---
name: Signal Filter Rank
description: Scores and ranks signals to find the top candidates.
allowed-tools: All
---

# Signal Filter & Rank

**Goal:** Select the top 3 signals with the highest transformation potential.

## Instructions
1.  **Input:** Takes a JSON list of signals from `artifacts/raw_signals.json` (produced by `signal_harvest` merge step).
2.  **Run the rank script:**
    Use `artifacts/raw_signals.json` directly, or save to a temp file.
    ```bash
    python skills/signal_filter_rank/scripts/rank.py --input artifacts/raw_signals.json
    ```
3.  **Output:** Top 3 signals object.

## Criteria
*   **Novelty:** Is this new or just noise?
*   **Relevance:** Does it fit the theme?
*   **Credibility:** Is the source reliable?
*   **Transformation Potential:** Can this change how things work?
