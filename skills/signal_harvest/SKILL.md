---
name: Signal Harvest
description: Captures raw signals from the environment.
allowed-tools: All
---

# Signal Harvest

**Goal:** Gather 8-12 raw signals relevant to the session theme.

## Instructions
1.  **Run the harvest script:**
    ```bash
    python skills/signal_harvest/scripts/harvest.py
    ```
2.  **Output:** The script will output a JSON list of signals.
3.  **Alternative:** If you need real-time data, use your `search_web` tool to find recent news on the theme, then format them similarly to the script output.

## Script Usage
The `harvest.py` script returns a list of signal objects with `title`, `summary`, and `category`.
