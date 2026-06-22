# Evaluation

This directory contains the evaluation suite for the main functionalities of the Context Engineering Agent. This evaluation measures the agent's ability to handle standard database enrichment tasks and workflows.

## Overview

The evaluation uses the [evalbench](https://github.com/GoogleCloudPlatform/evalbench) framework with the Gemini CLI and Claude Code orchestrator to run a set of simulated user tasks against the agent.

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

From the `evals/` directory, run the evaluation using `uvx`:
```bash
cd evals/
UV_CONFIG_FILE=uv.toml uvx --index-url https://pypi.org/simple/ google-evalbench@1.9.0 --experiment_config=core-cujs/run_gemini_cli.yaml
```

### Local Execution Caveats
Unlike CI (which auto-injects values and queries the metadata server), running locally requires these specific alignments:

1.  **SUT Environment Isolation**: The Gemini CLI SUT runs in an isolated subprocess. You must manually add `GOOGLE_CLOUD_PROJECT: "<your-gcp-project-id>"` and `GOOGLE_CLOUD_LOCATION: "global"` to the `env:` block in `evals/model_configs/gemini_cli_model.yaml` (CI does this dynamically via sed).
2.  **Global Endpoint**: The preview model `gemini-3-flash-preview` is hosted on the global Vertex endpoint. The location in both `gemini_model.yaml` (`gcp_region`) and `gemini_cli_model.yaml` (`GOOGLE_CLOUD_LOCATION`) must be set to `global` (not standard regions like `us-central1`).
3.  **Node Version**: Switch your active shell session to Node v20+ before running to support modern regular expressions:
    ```bash
    source ~/.nvm/nvm.sh && nvm use 20
    ```
4.  **Dirty State Cleanup**: If a run crashes midway, wipe the dirty extension installation before retrying:
    ```bash
    rm -rf evals/.venv/fake_home/.gemini/extensions/google-cloud-db-context-engineering
    ```
