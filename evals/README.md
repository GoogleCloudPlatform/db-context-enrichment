# Evaluation

This directory contains the evaluation suite for the main functionalities of the Context Engineering Agent. This evaluation measures the agent's ability to handle standard database enrichment tasks and workflows.

## Overview

The evaluation uses the [evalbench](https://github.com/GoogleCloudPlatform/evalbench) framework with the various agent harness orchestrators to run a set of simulated user tasks.

## Configuration Files

Each suite folder (`core-cujs/`, `freeform-input/`) contains only the things
that are suite-specific:

- `dataset.json`: test cases, prompts, and expected behaviors.
- `run_gemini_cli.yaml`: orchestrator + scorer config for the Gemini CLI SUT.
- `run_claude.yaml`: orchestrator + scorer config for the Claude Code SUT.

SUT and judge model configs are shared across suites under `model_configs/`:

- `model_configs/gemini_cli_model.yaml`: Gemini CLI SUT.
- `model_configs/claude_code_model.yaml`: Claude Code SUT.
- `model_configs/gemini_model.yaml`: simulated user and LLM-as-judge scorer.

## Evaluation Metrics

The suite evaluates the agent across several dimensions using the following scorers:

* **Goal Completion**: An LLM-based judge that determines if the agent successfully fulfilled the user's goal.
* **Turn Count**: Number of interactions required to complete the task.
* **End-to-End Latency**: Total time taken to resolve the user query.
* **Tool Call Latency**: Time spent executing database context tools.
* **Token Consumption**: Input and output token usage.

## How to Run

When running locally, you must align your Node environment, clean up any dirty extension state from previous runs, and export your GCP project variables. 

Here is an easy-to-copy-and-paste block to run the evaluation from the root repository directory:

```bash
# 1. Switch to Node v20+ and ensure npm is in PATH
source ~/.nvm/nvm.sh && nvm use 20

# 2. Clean up dirty extension state from any previous crashed runs
rm -rf evals/.venv/fake_home/.gemini/extensions/google-cloud-db-context-engineering

# 3. Export required GCP project and location variables
export GOOGLE_CLOUD_PROJECT="your-gcp-project-id"
export GOOGLE_CLOUD_LOCATION="global"
export EVAL_GCP_PROJECT_ID="your-gcp-project-id"
export EVAL_GCP_PROJECT_REGION="global"

# 4. Navigate to evals/ and run the evaluation
cd evals/
uvx --default-index https://pypi.org/simple/ google-evalbench --experiment_config=core-cujs/run_gemini_cli.yaml
```

### Local Execution Caveats
Unlike CI (which auto-injects values and queries the metadata server), running locally requires the specific alignments in the script above:

1.  **Node & NPM Version**: The Gemini CLI harness requires Node v20+ and `npm` available in your `$PATH`.
2.  **Dirty State Cleanup**: If a previous run crashed midway, `evals/.venv/fake_home/.gemini/extensions/` may contain partial installations that cause subsequent runs to fail.
3.  **Environment Variables & Authentication**: Both standard GCP and EvalBench's simulated user model require explicit project ID and `"global"` location exports, alongside active `gcloud auth application-default login` credentials.
