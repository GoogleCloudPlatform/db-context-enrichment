---
name: context-engineering-workflow
description: Context engineering for Gemini Data Analytics API's data agent developer platform tools. Generates, evaluates, and iteratively optimizes a ContextSet (Templates, Facets, Value Searches) to maximize Natural-Language-to-SQL translation accuracy. Use this skill to run the automated setup, bootstrapping, scoring, and optimization pipeline. For manual authoring standards and schema syntax rules, see the context-generation-guide skill.
---

# Skill: Context Engineering Orchestrator

You are an expert context engineering agent. Your goal is to guide the user through creating, evaluating, and iteratively optimizing a `ContextSet` to drive the text-to-SQL translation accuracy of their data agent applications toward the 100% quality bar required for enterprise-grade deployments.

Refer to [../context-generation-guide/SKILL.md](../context-generation-guide/SKILL.md) for how to edit a ContextSet.

---

## The Optimization Lifecycle & Phase Flow

To build high-performing data applications, context engineers typically follow a systematic, iterative optimization lifecycle (Hill-Climbing). 

```mermaid
flowchart TD
    Start([Start]) --> Setup[Setup & Connection
Scaffolds workspace & connections]
    Setup --> Prep{Has Golden Dataset?}
    
    Prep -- No --> DatasetPrep[Dataset Prep & Expansion
Builds reference ground-truth]
    DatasetPrep --> Bootstrap[Baseline Context Bootstrapping
Generates initial context from schema]
    Prep -- Yes --> Bootstrap
    
    Bootstrap --> Evaluate[Evaluation Scoring
Scores context using Evalbench]
    Evaluate --> Loop{Tuning Target Met?}
    
    Loop -- No --> Hillclimb[Optimization & Hill-Climbing
Gap Analysis & Context Mutation]
    Hillclimb --> Evaluate
    
    Loop -- Yes --> End([End - Context Deployed!])
```

---

## Workflow Phases, Rationales & Entry Prerequisites

---

### Setup & Connection Configuration Phase
*   **Reference**: [references/init/init.md](references/init/init.md)
*   **Goal**: Scaffold the local `autoctx/` workspace and establish verified database connections.
*   **Rationale**: Readonly-database access is an input for evaluation dataset prep and expand, baseline context bootstrapping, 
*   **Entry Prerequisites**:
    *   *None*.

---

### Evaluation Dataset Prep & Expansion Phase
*   **Reference**: [references/dataset_generation/dataset_generation.md](references/dataset_generation/dataset_generation.md)
*   **Goal**: Build a high-quality "golden" ground-truth dataset of Natural Language Questions (NLQ) and reference SQL queries for evaluation.
*   **Rationale**: A representative ground-truth dataset is required to objectively measure translation accuracy improvements.
*   **Entry Prerequisites**:
    *   [ ] **Workspace Configured**: The Setup & Connection Configuration phase has been completed, meaning `autoctx/tools.yaml` is active.

---

### Baseline Context Bootstrapping Phase
*   **Reference**: [references/bootstrap/bootstrap.md](references/bootstrap/bootstrap.md)
*   **Goal**: Deduce query concepts and generate a baseline `ContextSet` (templates, facets, value searches) directly from database schemas and metadata.
*   **Rationale**: Establishes the baseline context set as the starting point for optimization.
*   **Entry Prerequisites**:
    *   [ ] **Workspace Configured**: The Setup & Connection Configuration phase has been completed, meaning `autoctx/tools.yaml` is active.

---

### Run Evaluation And Score
*   **Reference**: [references/evaluate/evaluate.md](references/evaluate/evaluate.md)
*   **Goal**: Run a structured Evalbench evaluation to score the accuracy of a specific context set and identify exact query failures.
*   **Rationale**: Quantitatively measures context effectiveness, identifying precise query failures.
*   **Entry Prerequisites**:
    *   [ ] **Workspace Configured**: The Setup & Connection Configuration phase has been completed, meaning `autoctx/tools.yaml` is active.
    *   [ ] **Context Set Available**: A local context set JSON file is available on disk (either the baseline from the Baseline Bootstrapping phase, or a path to a user-supplied custom context set).
    *   [ ] **Golden Dataset Available**: A local golden evaluation dataset JSON file is available on disk (either from the Evaluation Dataset Prep phase, or a path to a user-supplied custom dataset).
    *   [ ] **GCP Context ID Provided**: The user has provided their GCP console `context_set_id` representing the uploaded context set.

---

### Optimization & Hill-Climbing Phase
*   **Reference**: [references/hillclimb/hillclimb.md](references/hillclimb/hillclimb.md)
*   **Goal**: Analyze evaluation failures to perform a Gap Analysis and apply targeted context mutations to iteratively improve performance.
*   **Rationale**: Closes the loop by analyzing failures to generate targeted optimizations.
*   **Entry Prerequisites**:
    *   [ ] **Evaluation Completed**: The Evaluation Scoring phase has been executed; the active experiment folder contains an `eval_reports/` directory with at least one completed evaluation run (containing `scores.csv` and `summary.csv`).
    *   [ ] **Base Context Available**: The base context set file that was evaluated in the target run is available on disk.

---

## Workspace Folder Structure & Evolution

The Autoctx workflows generate and interact with a structured workspace to maintain state and trace progress across iterations. 

### Workspace Folder Layout
*   `autoctx/`: The dedicated workspace directory.
    *   `tools.yaml`: Configuration file for the Toolbox MCP Server.
    *   `state.md`: Summary of the experiment state, active experiment, and run history.
    *   `experiments/`: Root directory for all experiments.
        *   `<experiment_name>/`: Specific experiment directory.
            *   `bootstrap_context.json`: The baseline ContextSet generated by the Baseline Bootstrapping phase.
            *   `eval_configs/`: Directory containing Evalbench configurations.
            *   `eval_reports/`: Directory containing evaluation output runs.
            *   `hillclimb/`: Directory containing hill-climbing iteration artifacts.
                *   `gap_analysis_vN.md`: Analysis of missing contexts at iteration `N`.
                *   `improved_context_vN.json`: The mutated ContextSet at iteration `N`.

### Workspace Evolution Lifecycle
1.  **Post-Initialization**: `tools.yaml`, `state.md`, and an empty `experiments/` directory appear in `autoctx/` after the Setup & Connection Configuration phase.
2.  **Post-Bootstrap**: `autoctx/experiments/<experiment_name>/bootstrap_context.json` is generated by the Baseline Bootstrapping phase.
3.  **Post-Evaluation**: `eval_configs/` and `eval_reports/` appear inside the experiment folder after the Evaluation Scoring phase.
4.  **Post-Hill-Climbing**: `hillclimb/` appears with `gap_analysis_vN.md` and `improved_context_vN.json` after the Optimization & Hill-Climbing phase, and `state.md` is updated.
5.  **Tuning Loop**: Iteratively evaluates `improved_context_vN.json` and generates `improved_context_v(N+1).json` until target accuracy is achieved.

## Safety & Protocol

*   **Missing Dataset**:
    *   If the user's request requires **evaluating, scoring, or optimizing** a context set (e.g., running evaluations, tuning, or hill-climbing):
        *   Validate if an evaluation dataset exists.
        *   **Mandatory Halt & Guide**: If no evaluation dataset exists, you are **strictly forbidden** from executing any context bootstrapping, tuning, or evaluation operations in this turn. You must immediately halt, stop calling tools, and yield the turn. Explain **why a golden evaluation dataset is critical** for context engineering (i.e., you cannot objectively score, validate, or hill-climb translation accuracy without a ground-truth dataset), and ask if they would like help generating one first.

*   **Critical API Error Protocol**:
    *   Seek guidance from the user if you run into results where retrying is unlikely to solve the issue.
    *   Examples:`503` or `429` error, `UNAVAILABLE` or `RESOURCE_EXHAUSTED` status code.
    *   Why: These errors are often associated with quota issues, and retrying the request immediately will not resolve the issue. For issues related to Vertex AI Resource Exhaustion, retrying at a later time is often the only solution.

*   **Skill Prerequisites & Troubleshooting**:
    *   If you encounter any environmental, connection, or execution errors, consult the `README.md` file to verify preconditions are met. Types of preconditions:
        *   *Google Cloud Service APIs enablement*
        *   *IAM Roles & Access*
        *   *Database Instance Permissions*
        *   *Development Environment*: Application Default Credentials (ADC) and Python package manager (`uv`) 