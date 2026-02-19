---
name: Scenario Generator
description: Generates future scenarios based on a signal and mechanism.
allowed-tools: All
---

# Scenario Generator

**Goal:** Project a signal+mechanism into tangible future states.

## Instructions
1.  **Input:**
    *   **Chosen Signal:** (You must select the most promising one from `SIGNALS.md`)
    *   **Chosen Mechanism:** (Select the most relevant one from `MECHANISMS.md` for that signal)
    *   **Horizon:** 2-5 years.

2.  **Action: Analysis (Pre-Scoping)**
    *   Before writing the scenarios, perform a **Chain of Thought** analysis:
        *   Identify the central **tension** (e.g., Performance vs. Compliance, Autonomy vs. Control).
        *   Identify at least 2 **Industry-Specific terms** that would be used by stakeholders in this field (e.g., "Latent Compliance Debt," "Zero-Knowledge Attestation").
        *   Map the **Path of Least Resistance**: How would a lazy organization try to bypass this, and what consequence does that create?

3.  **Action: Generation**
    *   Generate two distinct scenarios.
    *   **Scenario A: Near Future (12-24 months)**
        *   *Constraint:* High plausibility. "This is basically already happening in beta."
        *   *Focus:* Operational changes, early adoption friction.
    *   **Scenario B: Edge Case (2-5 years)**
        *   *Constraint:* Plausible but uncomfortable/disruptive.
        *   *Focus:* Second-order effects, regulatory clashes, new business models.

4.  **Rules:**
    *   Must be concrete (specific roles, specific tools, specific conflicts).
    *   Must generally avoid "AGI saves everyone" tropes.
    *   Must include at least one human "Point of Friction".
    *   **Vocabulary:** Use the industry-specific terms identified in the analysis.

## Deliverable
Write to `artifacts/SCENARIOS.md`.

### Format
**Chosen Signal:** ...
**Chosen Mechanism:** ...

#### Scenario A: [Title]
[Description of the scenario, 150-200 words]

#### Scenario B: [Title]
[Description of the scenario, 150-200 words]
