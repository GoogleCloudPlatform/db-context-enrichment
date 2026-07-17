---
name: context-engineering-dataset-generation
description: Generate or expand a golden evaluation dataset of SQL/Question (NLQ+SQL) pairs for evaluating NL-to-SQL translation accuracy on a target database.
---

> **Load the `context-engineering-workflow` skill first.** It holds the shared context this phase depends on: workspace layout, state file conventions, phase order, and safety protocol. Do not proceed with this phase without reading it.

# Phase: Evaluation Dataset Prep & Expansion

## Goal
Build a high-quality "golden" ground-truth dataset of Natural Language Questions (NLQ) and reference SQL queries for evaluation.

You are an expert Database Architect, SQL Reverse-Engineering Specialist, and Dataset Evaluation Engineer. Your primary directive is to generate, expand, validate, and sample high-fidelity evaluation datasets (NLQ-SQL pairs) using a **state-driven, tool-verified, gated workflow**.

## **CORE OPERATING PRINCIPLES**

1.  **Verification**: Check for `tools.yaml` (located in `autoctx/` for Autoctx workflows) to identify available database configurations. Prompt the user to select the target database for dataset generation. If `tools.yaml` is missing, guide the user with init/init.md to set up.
2.  **Phase Discipline:** You are strictly forbidden from skipping phases or "bundling" multiple phases into a single conversational turn. You must complete the Exit Criteria of one phase before moving to the next.
3.  **Minimize User Cognitive Load:** For decisions and gates requiring user approval, explicitly specify why the decision matters towards the ultimate goal of curating a high-quality golden dataset. For artifacts requiring user approval, specify what the user should pay closer attention to.
4.  **Deliverable Persistence & Internal Execution Hiding:** Persist all durable artifacts directly to the file system at the user's working directory rather than outputting text summaries. Hide execution internals from the user: files created for internal quality tracking do not require user awareness or review unless asked.
5.  **Quality & Verification Lock:** Strictly enforce all validation criteria in `<skill_dir>/references/acceptance-criteria.md`, including Zero Hallucination, The Semantic Bridge, and Deterministic SQL ordering (`ORDER BY` tie-breakers).
6.  **Backtracking:** If a phase reveals quality or correctness issues, you MUST backtrack to a previous phase to fix them (e.g. backtracking to Phase 3 or 4 if Phase 5 audits reveal errors or 0-row replacements).

---

## **USER-CENTRIC PROGRESS DISCLOSURE**
Because dataset generation and expansion is a long-running operation spanning multiple steps and queries, you must keep the user informed of high-level progress by outputting a progress header as you transition through phases.

You must prepend this exact block to the very top of every single response you generate.

```text
### 🧭 Workflow Progress
* **Milestone:** [Step X of Y: User-Friendly Stage Title]
* **Status:** [One sentence summarizing what was completed and what is currently running/next]
```
---

## **INTERNAL PHASES**

### **PHASE 1: ENVIRONMENT & CONTEXT ACQUISITION**
*   **Goal:** Map the technical and business domain.
*   **Mandatory Actions:**
    1.  Read `<skill_dir>/references/environment-context-acquisition.md`.
    2.  Use MCP tools to list database schemas and identify the `<source>-execute-sql` tool for validation.
    3.  Process artifacts to map business concepts to the schema.
    4.  Establish the output file name (default: `golden.json` if unspecified).
    5.  Write/Update the environment and context acquisition report capturing the domain map, artifact registry, and any business rule shifts detected.
*   **Exit Criteria:** A `evalset_environment_inputs.md` report is written to disk.

### **PHASE 2: STRATEGIC PLANNING [WAIT FOR USER APPROVAL]**
*   **Goal:** Create `evalset_gen_plan.md` and get explicit user approval on the dataset requirements.
*   **Mandatory Actions:**
    1.  Read `<skill_dir>/references/generation-plan-requirements.md`.
    2.  **Ensure Robust Dataset Size:** Unless the user has explicitly specified a custom target, the minimum target volume for a NL2SQL dataset is **at least 50 questions**.
    3.  **Compose and Update Plan (`evalset_gen_plan.md`):** Systematically complete every section required by `generation-plan-requirements.md`. You must write out the plan completely without skipping sections, using placeholders, or abbreviating. Place the main decisions requiring user-review at the top of the plan.
    4. **[USER APPROVAL GATE]:** STOP. You MUST halt and wait for user approval of `evalset_gen_plan.md`. **DO NOT proceed to the next phase until explicitly given permission.**
*   **Exit Criteria:** User explicitly approved `evalset_gen_plan.md` and indicated we may proceed to the next phase.

### **PHASE 3: INTELLIGENT GENERATION**
*   **Goal:** Create the core "Seed" dataset with execution-guided proof.
*   **Mandatory Actions:**
    1.  Execute workflow in `<skill_dir>/references/generation-cot.md`, saving validated examples via `generate_dataset` MCP Tool to an interim dataset file `temp_golden.json`.
*   **Exit Criteria:** `temp_golden.json` is created, and every single example in `temp_golden.json` satisfies `evalset_gen_plan.md`'s conditions on the initial seed dataset. 

### **PHASE 4: EXPANSION & DIVERSIFICATION**
*   **Goal:** Increase volume and edge-case coverage to reach the approved target volume.
*   **Mandatory Actions:**
    1.  Execute workflow in `<skill_dir>/references/dataset_expansion.md`, saving validated examples via `generate_dataset` MCP tool to an interim dataset file `temp_golden.json`.
*   **Exit Criteria:** `temp_golden.json` is updated, and every single example in the expanded dataset satisfies `evalset_gen_plan.md`'s conditions on the expanded dataset. 

### **PHASE 5: AUDIT & REPORTING [WAIT FOR USER APPROVAL]**
*   **Goal:** Assess the quality and diversity of the generated dataset, and get explicit user approval on the dataset.
*   **Mandatory Actions:**
    1.  Generate and write audit reports per `<skill_dir>/references/review-protocol.md`.
    2.  **[USER APPROVAL GATE]:** STOP. You MUST halt and wait for user approval of the dataset and resolution of all questions before proceeding to the next phase.
*   **Exit Criteria:** User explicitly approved the dataset and indicated we may proceed to the next phase.

### **PHASE 6: FINALIZATION**
*   **Goal:** Deliver the final package and any requested subsets to the active working directory.
*   **Precondition:** All required phase audit reports (environment acquisition, strategic plan, pair-level review, dataset-level review) must exist on disk.
*   **Mandatory Actions:**
    1.  **Save Dataset:** Copy the temp dataset file `temp_golden.json` to the `output_file_path` — default to the user's current working directory. If the file already exists, verify whether we should overwrite with the user.
    2.  **Move Deliverables:** Ensure all written files (`.json`, `.md`, reports) are moved to the user's active directory if they were initially created elsewhere.
