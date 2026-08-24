# Evaluation

This directory contains the evaluation suite for the Context Engineering Agent. It measures the agent's ability to handle end-to-end database enrichment tasks across relational databases (AlloyDB, Cloud SQL) and graph databases (Cloud Spanner Graph).

## Overview

The evaluation framework uses [EvalBench](https://github.com/GoogleCloudPlatform/evalbench) with various System Under Test (SUT) agent harnesses (Gemini CLI, Claude Code) to run simulated multi-turn user tasks against live databases.

---

## Test Suites & Directory Structure

Each suite folder contains only suite-specific files:

- **`core-cujs/`**: Full lifecycle CUJ scenarios on relational databases (AlloyDB).
- **`spanner-graph-cujs/`**: End-to-end Spanner Graph CUJ scenarios (schema discovery, property graph scope gating, GQL + SQL generation, and evaluation).
- **`freeform-input/`**: Freeform user input and exploratory workflow tests.

Within each suite directory:
- `dataset.json`: Test scenarios, starting prompts, and conversation plans.
- `run_gemini_cli.yaml`: Orchestrator and scorer config for Gemini CLI SUT.
- `run_claude.yaml`: Orchestrator and scorer config for Claude Code SUT.
- `workspace_*/`: Initial workspace fixtures for test scenarios.

Shared model configs reside under `model_configs/`:
- `model_configs/gemini_cli_model.yaml`: Gemini CLI SUT configuration.
- `model_configs/claude_code_model.yaml`: Claude Code SUT configuration.
- `model_configs/gemini_model.yaml`: Simulated user and LLM judge model.

---

## Evaluation Metrics

The suite scores agent performance across multiple dimensions:

* **Goal Completion**: An LLM judge evaluates whether the agent achieved the user's objective based on the conversation plan.
* **Trajectory Matcher**: Verifies that expected tools were called in the proper order.
* **Turn Count**: Number of user-agent interaction turns to completion.
* **Latency**: End-to-end task time and database tool execution latency.
* **Token Consumption**: Input, prompt, cached, and output token usage.

---

## Execution Guide: Human vs. Agent Runs

There are two primary execution workflows depending on whether a human developer is running evals manually or an AI coding agent (e.g. Antigravity) is executing them in a subshell.

---

### Flow 1: Human-Initiated Evaluation Runs (Interactive Terminal)

Use this flow when running evaluations directly from your local developer terminal.

#### Quick Start (Copy-and-Paste Block):

```bash
# 1. Switch to Node v20+ and ensure npm/node are in PATH
source ~/.nvm/nvm.sh && nvm use 20
export PATH="$(dirname "$(nvm which 20 2>/dev/null || which node)"):$PATH"

# 2. Clean up dirty extension cache, temporary files, and reset workspace
rm -rf evals/.venv/fake_home/.gemini/extensions/google-cloud-db-context-engineering
rm -rf evals/.venv/fake_home/.gemini/tmp/*
rm -f evals/.venv/fake_home/*.md evals/.venv/fake_home/*.json
find evals/spanner-graph-cujs/workspace_supply_chain/ -mindepth 1 ! -name 'design_doc.md' -delete

# 3. Stage local repository changes (excluding evals/ so test rubrics don't leak)
rm -rf /tmp/db-context-enrichment-staging
rsync -av --exclude='.git' --exclude='.venv' --exclude='evals' \
  /Users/lindazhang/Documents/GitHub/db-context-enrichment/ /tmp/db-context-enrichment-staging/

# 4. Export required GCP project, location, and reporting variables
export GOOGLE_CLOUD_PROJECT="cloud-db-nl2sql"
export GOOGLE_CLOUD_LOCATION="global"
export EVAL_GCP_PROJECT_ID="cloud-db-nl2sql"
export EVAL_GCP_PROJECT_REGION="global"
export EVAL_REPORTING_PROJECT="cloud-db-nl2sql"

# 5. (Optional) Filter to a specific scenario ID
# export EVAL_SCENARIOS="spanner-graph-full-workflow"

# 6. Navigate to evals/ and execute the evaluation
cd evals/
uvx --default-index https://pypi.org/simple/ --from "google-evalbench==1.10.0" \
  google-evalbench --experiment_config=spanner-graph-cujs/run_gemini_cli.yaml
```

To run Core CUJs:
```bash
uvx --default-index https://pypi.org/simple/ --from "google-evalbench==1.10.0" \
  google-evalbench --experiment_config=core-cujs/run_gemini_cli.yaml
```

---

### Flow 2: Agent-Initiated Evaluation Runs (Autonomous AI Subshell)

When an AI agent runs evaluations inside a non-interactive subshell against **unmerged local workspace changes**, follow these mandatory steps:

#### 1. Stage Extension Outside the Repository (Avoid EINVAL & Test Leakage)
Because Gemini CLI installs extensions by copying source files into `evals/.venv/fake_home/...`, pointing it directly at the root workspace will cause `cp` to fail with `EINVAL (cannot copy directory to a subdirectory of self)`. 

Additionally, the `evals/` directory must be excluded from the staged extension so that test scenarios, evaluation rubrics (`dataset.json`), and fixtures are not packaged into the extension directory or searchable by the agent under test.

Always stage the repository to `/tmp/db-context-enrichment-staging/` first:
```bash
rsync -av --exclude='.git' --exclude='.venv' --exclude='evals' /path/to/db-context-enrichment/ /tmp/db-context-enrichment-staging/
```

#### 2. Explicit Node Path in Non-Interactive Shells
Non-interactive agent subshells do not source `~/.nvm/nvm.sh` automatically. Prepend the installed Node v20+ binary path (adjust the version number to match your local installation):
```bash
# Automatically resolve active Node v20+ path:
export PATH="$(dirname "$(nvm which 20 2>/dev/null || which node)"):$PATH"

# Or specify your local installed Node version explicitly (e.g. v20.x.x):
# export PATH="$HOME/.nvm/versions/node/v20.20.2/bin:$PATH"
```

#### 3. Reset Workspace Fixtures & Clean State
Before running any evaluation scenario, ensure generated artifacts, stray files, and session caches from prior runs are cleared:
```bash
# Clean dirty extension state and temporary session logs
rm -rf evals/.venv/fake_home/.gemini/extensions/google-cloud-db-context-engineering
rm -rf evals/.venv/fake_home/.gemini/tmp/*
rm -f evals/.venv/fake_home/*.md evals/.venv/fake_home/*.json

# Reset scenario workspace (e.g. workspace_supply_chain: keep only design_doc.md)
find evals/spanner-graph-cujs/workspace_supply_chain/ -mindepth 1 ! -name 'design_doc.md' -delete

# For empty workspace fixtures:
rm -rf evals/core-cujs/workspace_empty/*
touch evals/core-cujs/workspace_empty/.gitkeep
```

#### 4. Run via Local EvalBench Runner or UVX
```bash
# Export GCP credentials & environment
export GOOGLE_CLOUD_PROJECT="cloud-db-nl2sql"
export GOOGLE_CLOUD_LOCATION="global"
export EVAL_GCP_PROJECT_ID="cloud-db-nl2sql"
export EVAL_GCP_PROJECT_REGION="global"
export EVAL_REPORTING_PROJECT="cloud-db-nl2sql"

# Execute evalbench from evals/ directory
cd evals
uvx --default-index https://pypi.org/simple/ --from "google-evalbench==1.10.0" \
  google-evalbench --experiment_config=spanner-graph-cujs/run_gemini_cli.yaml
```

---

## Local Execution Caveats & Troubleshooting

1. **Node & NPM Version**: Gemini CLI requires Node.js **v20+** for modern regex and stream support. Verify with `node -v` and ensure `npm` is accessible in `PATH`.
2. **BigQuery Reporting Variable**: Set `export EVAL_REPORTING_PROJECT="cloud-db-nl2sql"` (or your target GCP project) so EvalBench can write evaluation results to BigQuery without error.
3. **Workspace Reset**: Always clean generated files (`autoctx/`, `golden.json`, `context_set.json`, `evalset_*.md`) from the scenario workspace and `fake_home` before running, otherwise the agent will detect existing state and skip initialization phases.
4. **Dirty State Cleanup**: If a run terminates abruptly, `evals/.venv/fake_home/.gemini/extensions/` and `.gemini/tmp/` may contain incomplete installations and previous session logs. Always delete them before re-running.
5. **Authentication**: Ensure Google Cloud ADC is active via `gcloud auth application-default login`.
6. **Vertex AI Global Endpoint**: Both `GOOGLE_CLOUD_LOCATION="global"` and `EVAL_GCP_PROJECT_REGION="global"` must be exported for the simulated user model and judge raters.
