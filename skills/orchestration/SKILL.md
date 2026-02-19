---
name: Orchestrator
description: The main driver for the Signal -> Implication pipeline.
allowed-tools: All
---

# Signal → Implication Pipeline Orchestrator

This skill describes the step-by-step process to transform weak signals into a coherent LinkedIn post and image prompt.
**Role:** You are the Lead Editor and Strategist. You are responsible for executing this pipeline by calling the sub-skills defined below.

## Pipeline Phases

### Phase 0: Initialize Session
**Goal:** Establish the context and constraints for the session to avoid drift.
1.  **Action:** Create a file named `SESSION_BRIEF.md`.
2.  **Content:**
    *   **Theme for the week:** (Ask the user or pick a relevant current tech/business theme if not specified)
    *   **Target Audience:** (e.g., Enterprise CTOs, Innovation Leaders)
    *   **Tone:** Professional, insightful, slightly provocative but grounded.
    *   **Length:** ~200-300 words.
    *   **Transformation Lens:** (Pick one: Trust, Coordination, Identity, Accountability, Verification).

### Phase 1: Signal Capture (Parallelish)
**Goal:** Find and select the best signal.
1.  **Execute Skill:** `skills/signal_harvest`
    *   *Instruction:* Run the harvest script or perform web searches to find 8-12 recent signals related to the theme.
    *   *Output:* A raw list of signals.
2.  **Execute Skill:** `skills/signal_filter_rank`
    *   *Input:* The list from step 1.
    *   *Instruction:* Score them based on novelty, relevance, and transformation potential.
    *   *Output:* Top 3 ranked signals.
3.  **Execute Skill:** `skills/signal_context_pack`
    *   *Input:* Top 3 signals.
    *   *Instruction:* Create a brief context pack for each (What happened, Why it matters, What's missing).
    *   *Deliverable:* Write to `artifacts/SIGNALS.md`.

### Phase 2: Mechanism Extraction
**Goal:** Identify the underlying system change.
1.  **Execute Skill:** `skills/mechanism_map`
    *   *Input:* The context packs from `SIGNALS.md`.
    *   *Instruction:* For each signal, map it to 2-4 possible mechanisms (e.g., Trust Infrastructure, Workflow Control Plane).
    *   *Deliverable:* Write to `artifacts/MECHANISMS.md`.

### Phase 3: Scenario Generation
**Goal:** Project the mechanism into the future.
1.  **Selection:** Select **ONE** Signal and **ONE** Mechanism from the previous steps to proceed with. (Pick the most promising one).
2.  **Execute Skill:** `skills/scenario_generator`
    *   *Input:* Selected Signal, Selected Mechanism.
    *   *Instruction:* Generate two scenarios:
        *   **Near Scenario** (12-24 months): Very plausible.
        *   **Edge Scenario** (2-5 years): Plausible but uncomfortable.
    *   *Deliverable:* Write to `artifacts/SCENARIOS.md`.

### Phase 4: Implication Synthesis
**Goal:** Analyze the impact.
1.  **Execute Skill:** `skills/implication_synthesizer`
    *   *Input:* The scenarios from `SCENARIOS.md`.
    *   *Instruction:* Derive implications in 3 layers: Operational, Organizational, Strategic.
    *   *Deliverable:* Write to `artifacts/IMPLICATIONS.md`.

### Phase 5: Post Drafting
**Goal:** Write the first draft.
1.  **Execute Skill:** `skills/linkedin_post_draft`
    *   *Input:* Signal, Mechanism, Scenarios, Implications.
    *   *Constraint:* Must include "This is not a prediction." sentence. End with a hard question.
    *   *Output:* Draft text.

### Phase 6: Critique & Refinement
**Goal:** Polish and stress-test.
1.  **Execute Skill:** `skills/critics`
    *   *Input:* The draft from Phase 5.
    *   *Roles:* Clarity Critic, Skeptic Critic, Credibility Guard, Structure Guard.
    *   *Output:* List of critiques.
2.  **Execute Skill:** `skills/post_refiner`
    *   *Input:* Draft + Critiques.
    *   *Instruction:* Rewrite the post to address the critiques.
    *   *Deliverable:* Write to `artifacts/FINAL_POST.md`.

### Phase 7: Image Prompt
**Goal:** Visual accompaniment.
1.  **Execute Skill:** `skills/image_prompt_gen`
    *   *Input:* `FINAL_POST.md`
    *   *Instruction:* Generate a photorealistic, human-centered image prompt (no abstract concepts/symbols).
    *   *Deliverable:* Write to `artifacts/IMAGE_PROMPT.md`.

---
**Final Step:** Present the `FINAL_POST.md` and `IMAGE_PROMPT.md` to the user.
