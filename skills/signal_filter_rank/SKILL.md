---
name: Signal Filter Rank
description: Scores and ranks signals to find the top candidates.
allowed-tools: All
---

# Signal Filter & Rank

**Goal:** Select the top 3 signals with the highest transformation potential.

## Instructions
1.  **Input:** Takes a JSON list of signals (from `signal_harvest`).
2.  **Run the rank script:**
    Save the signals to a temp file `temp_signals.json` or pipe them.
    ```bash
    python skills/signal_filter_rank/scripts/rank.py --input temp_signals.json
    ```
3.  **Output:** Top 3 signals object.

## Criteria
*   **Novelty:** Is this new or just noise?
*   **Relevance:** Does it fit the theme?
*   **Credibility:** Is the source reliable?
*   **Transformation Potential:** Can this change how things work?
