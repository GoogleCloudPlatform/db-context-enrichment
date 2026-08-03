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
# 1. Switch to Node v20+ and verify npm in PATH
source ~/.nvm/nvm.sh && nvm use 20

# 2. Clean up any dirty extension cache from previous crashed runs
rm -rf evals/.venv/fake_home/.gemini/extensions/google-cloud-db-context-engineering

# 3. Export required GCP project and location variables
export GOOGLE_CLOUD_PROJECT="cloud-db-nl2sql"
export GOOGLE_CLOUD_LOCATION="global"
export EVAL_GCP_PROJECT_ID="cloud-db-nl2sql"
export EVAL_GCP_PROJECT_REGION="global"

# 4. (Optional) Filter to a specific scenario ID
# export EVAL_SCENARIOS="spanner-graph-e2e-bootstrap"

# 5. Navigate to evals/ and execute the evaluation
cd evals/
uvx --default-index https://pypi.org/simple/ --from "google-evalbench==1.12.0" google-evalbench --experiment_config=core-cujs/run_gemini_cli.yaml
```

To run Spanner Graph CUJs:
```bash
uvx --default-index https://pypi.org/simple/ --from "google-evalbench==1.12.0" google-evalbench --experiment_config=spanner-graph-cujs/run_gemini_cli.yaml
```

---

### Flow 2: Agent-Initiated Evaluation Runs (Autonomous AI Subshell)

When an AI agent runs evaluations inside a non-interactive subshell against **unmerged local workspace changes**, follow these mandatory steps:

#### 1. Stage Extension Outside the Repository (Avoid EINVAL Directory Recursion)
Because Gemini CLI installs extensions by copying source files into `evals/.venv/fake_home/...`, pointing it directly at the root workspace will cause `cp` to fail with `EINVAL (cannot copy directory to a subdirectory of self)`. 

Always stage the repository to `/tmp/db-context-enrichment-staging/` first:
```bash
rsync -av --exclude='.git' --exclude='evals/.venv' /path/to/db-context-enrichment/ /tmp/db-context-enrichment-staging/
```

#### 2. Explicit Node Path in Non-Interactive Shells
Non-interactive agent subshells do not source `~/.nvm/nvm.sh` automatically. Prepend the installed Node v20+ binary path:
```bash
export PATH="$HOME/.nvm/versions/node/v20.20.2/bin:$PATH"
```

#### 3. Reset Workspace Fixtures
Before running a scenario that starts from an empty workspace, ensure generated files from prior runs are cleared:
```bash
rm -rf evals/spanner-graph-cujs/workspace_empty/*
touch evals/spanner-graph-cujs/workspace_empty/.gitkeep
```

#### 4. Run via Local EvalBench Runner or UVX
```bash
# Clean dirty extension state
rm -rf evals/.venv/fake_home/.gemini/extensions/google-cloud-db-context-engineering

# Export GCP credentials & environment
export GOOGLE_CLOUD_PROJECT="cloud-db-nl2sql"
export GOOGLE_CLOUD_LOCATION="global"
export EVAL_GCP_PROJECT_ID="cloud-db-nl2sql"
export EVAL_GCP_PROJECT_REGION="global"

# Execute evalbench from evals/ directory
cd evals
uvx --default-index https://pypi.org/simple/ --from "google-evalbench==1.12.0" google-evalbench --experiment_config=spanner-graph-cujs/run_gemini_cli.yaml
```

---

## Local Execution Caveats & Troubleshooting

1. **Node & NPM Version**: Gemini CLI requires Node.js **v20+** for modern regex and stream support. Verify with `node -v`.
2. **Dirty State Cleanup**: If a run terminates abruptly, `evals/.venv/fake_home/.gemini/extensions/` may contain incomplete installations. Always delete this folder before re-running.
3. **Authentication**: Ensure Google Cloud ADC is active via `gcloud auth application-default login`.
4. **Vertex AI Global Endpoint**: Both `GOOGLE_CLOUD_LOCATION="global"` and `EVAL_GCP_PROJECT_REGION="global"` must be exported for the simulated user model and judge raters.
