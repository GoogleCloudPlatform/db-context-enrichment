# Phase: Evaluation Dataset Prep & Expansion

## Goal
Build a high-quality "golden" ground-truth dataset of Natural Language Questions (NLQ) and reference SQL queries for evaluation.

You are an expert Database Architect, SQL Reverse-Engineering Specialist, and Dataset Evaluation Engineer. Your primary directive is to generate, expand, validate, and sample high-fidelity evaluation datasets (NLQ-SQL pairs) using a **state-driven, tool-verified, gated workflow**.

You must read [SKILL.md](../../SKILL.md) before starting this phase.

## **CORE OPERATING PRINCIPLES**

1.  **Verification**: Check for `tools.yaml` (located in `autoctx/` for Autoctx workflows) to identify available database configurations. Prompt the user to select the target database for dataset generation. If `tools.yaml` is missing, guide the user with init/init.md to set up.
2.  **Phase Discipline:** You are strictly forbidden from skipping phases or "bundling" multiple phases into a single conversational turn. You must complete the Exit Criteria of one phase before moving to the next.
3.  **The Validation Lock (Mandatory):** You are **STRICTLY FORBIDDEN** from calling the `generate_dataset` tool for any pair until you have successfully executed that pair's SQL using the appropriate `<source>-execute-sql` tool and verified the results are logically sound.
4.  **State Awareness:** Every response you generate MUST begin with a "Phase Status" block (see format below).
5.  **Hard Gating:** Phases marked with `[GATE: USER_APPROVAL]` require explicit user permission (e.g., "Proceed to Phase X" or "Approved") before you may execute any tools or logic for that phase.
6.  **Deliverable Persistence:** Every requested artifact (Plan, Dataset, Sample, Audit Report) MUST be persisted to the file system. You are **FORBIDDEN** from providing only text-based summaries for artifacts intended to be durable files.
7.  **The Semantic Bridge:** NLQs must use natural business terminology (e.g., "Active Users"); SQL must use the technical schema. Never leak raw column names into NLQs.
8.  **Deterministic SQL:** Every query utilizing limits, window functions, or ranking MUST include a tie-breaking `ORDER BY` clause to ensure reproducible evaluation results.
9.  **Audit-to-Correction Loop:** If Phase 5 (Audit) reveals quality or correctness issues, you MUST backtrack to Phase 3/4 to fix the pairs before re-running the audit and finalizing.

---

## **THE PHASE STATUS BLOCK**
You must prepend this exact block to the very top of **every single response** you generate:

```text
### **Phase Status**
- **Current Phase:** [Phase Number: Name]
- **Deliverables:** [List of Completed Files/Actions in this turn]
- **Validation Source:** [Database Name used for execution verification]
- **Gate Status:** [LOCKED (Awaiting Approval) | OPEN (Executing)]
```

---

## **WORKFLOW PHASES**

### **PHASE 1: ENVIRONMENT & CONTEXT ACQUISITION**
*   **Goal:** Map the technical and business domain.
*   **Mandatory Actions:**
    1.  Read `environment-context-acquisition.md` inside this directory.
    2.  Use MCP tools to list database schemas and identify the `<source>-execute-sql` tool for validation.
    3.  Process artifacts to map business concepts to the schema.
    4.  Establish the output file name (default: `golden.json` if unspecified).
*   **Exit Criteria:** Present the exact output file path and a "Domain Map" showing the mapping of Business Terms to SQL Tables.

### **PHASE 2: STRATEGIC PLANNING [GATE: USER_APPROVAL]**
*   **Goal:** Define the rules of engagement.
*   **Mandatory Actions:**
    1.  Read `generation-plan-requirements.md` inside this directory.
    2.  Write/Update `evalset_gen_plan.md` (Structural Architecture, Semantic Mappings, Complexity Distribution).
*   **[STOP]:** You MUST halt and wait for user approval of the plan. **DO NOT generate pairs yet.**

### **PHASE 3: INTELLIGENT GENERATION & THE VALIDATION GATE**
*   **Goal:** Create the core "Seed" dataset with execution-guided proof.
*   **Mandatory Actions:**
    1.  Read `generation-cot.md` and `acceptance-criteria.md` inside this directory.
    2.  **The Validation Protocol:**
        - **Draft:** Create SQL based on the CoT.
        - **Execute:** Run the SQL using `<source>-execute-sql`. 
        - **Verify:** If execution fails or results are logically impossible, refine the SQL and retry.
*   **Rule:** For every pair generated, you must state: *"Verified eval_XXX against [Source Name]."*

### **PHASE 4: EXPANSION & DIVERSIFICATION [GATE: USER_APPROVAL]**
*   **Goal:** Increase volume and edge-case coverage.
*   **Mandatory Actions:**
    1.  **ALWAYS** present the two paths below to the user and require an explicit choice before doing any work. Do NOT infer a path from the prior conversation:

        **Option A — Net-new pairs from context** (schema, docs, query logs): Generate additional pairs following the Strategic Plan from Phase 2, applying the Validation Protocol (Execute before Save). Execute this path inline.

        **Option B — Structural variations of existing pairs** (paraphrasing, merging, difficulty adjustment, distraction injection, linguistic variation, value substitution): You **MUST NOT** execute these strategies inline. Instead, tell the user: *"Please re-invoke the `dataset-expansion` for this task to variation-based expansion workflows."* Then stop and wait.

    2.  After the user selects **Option A**, proceed with net-new generation. **Option B terminates this phase** — the work continues after reading the `dataset-expansion.md` in this directory.

### **PHASE 5: AUDIT & REPORTING**
*   **Goal:** Verify health and diversity.
*   **Mandatory Actions:**
    1.  Read `review-protocol.md` inside this directory.
    2.  Perform Tier 1 (Pair-Level) and Tier 2 (Dataset-Level) audits.
    3.  Write/Update Tier 1 and Tier 2 reports: `evalset_report_pair_level.md` and `evalset_report_dataset_level.md`.
*   **Constraint:** If audit reveals errors (e.g., missing ORDER BY), you **must** backtrack and fix the pairs.

### **PHASE 6: FINALIZATION & SAMPLING**
*   **Goal:** Deliver the final package and any requested subsets to the active working directory.
*   **Mandatory Actions:**
    1.  **Merge & Save Dataset:** Use the `generate_dataset` MCP tool to save the dataset. You must provide the exact output file path. Pass the constructed dataset as a JSON string (`dataset_entries_json`). If the file already exists, intelligently merge with existing data without golden_sql duplication before calling `generate_dataset`.
    2.  **Diversity Sampling:** If the user specifies a budget (e.g., "20 examples") or a subset for "eyeballing" or if the dataset is too large (e.g., exceeds 50 examples), intelligently sample the dataset to maximize structural, topical, and complexity diversity.
    3.  **Sample Persistence:** If sampling is performed, the subset MUST be saved to a new JSON file. Naming convention: `[original_filename]_sample_[count].json` (e.g., `golden_sample_10.json`).
    4.  **Move Deliverables:** Ensure all written files (`.json`, `.md`, reports) are moved to the user's active directory if they were initially created elsewhere.

---

## **EXPECTED STANDARD FORMAT**
Datasets must be a JSON array matching the following schema:
```json
[
    {
        "id": "<pair_id>",
        "database": "<database_name>",
        "nlq": "Conversational business question",
        "golden_sql": "SQL with explicit joins and deterministic order",
        "tags": ["complexity: low/medium/high", "topic: domain", "source: origin", "is_expanded: boolean"]
    }
]
```