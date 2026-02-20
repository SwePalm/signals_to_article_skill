# Signal → Implication Pipeline

A deterministic-ish pipeline that transforms noisy signals into a single coherent LinkedIn post and image prompt.
Built using the **AgentSkills** specification, with hybrid harvesting (native web search + RSS 24h intake) and script-assisted ranking.

## 📂 Structure

*   `skills/`: Contains all the modular skills (Harvest, RSS Fetch, Filter, Scenario, etc.).
*   `artifacts/`: Stores the outputs of each phase (`SIGNALS.md`, `SCENARIOS.md`, `FINAL_POST.md`).
*   `AGENTS.md`: Instruction file for AI agents working in this repo.

## 🚀 How to Run

**For Agents:**
Read `AGENTS.md` and follow the instructions in `skills/orchestration/SKILL.md`.

**For Humans:**
1.  Verify you have Python installed.
2.  The pipeline is designed to be executed by an AI Agent (like me!).
3.  The agent will:
    *   Harvest signals from real-world sources using two channels: native web search and RSS feeds (`skills/rss-fetch`) filtered to the last 24 hours.
    *   Merge and dedupe into `artifacts/raw_signals.json`.
    *   Rank them (using `skills/signal_filter_rank`).
    *   Generate Scenarios, Implications, and Drafts (using LLM skills).
    *   Critique and Refine the output.

## 🛠️ Skills Overview

1.  **Signal Harvest:** Finds raw data.
2.  **Signal Filter:** Ranks for transformation potential.
3.  **Context Pack:** Adds "Why it matters".
4.  **Mechanism Map:** Identifies structural shifts.
5.  **Scenario Generator:** Projects near/edge futures.
6.  **Implication Synthesizer:** Derives strategic changes.
7.  **Drafting & Critique:** Writes and polishes the content.
