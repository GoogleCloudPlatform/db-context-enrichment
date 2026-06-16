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

From the `evals/` directory, execute the evaluation using latest [evalbench](https://github.com/GoogleCloudPlatform/evalbench/releases):

```bash
cd evals/
evalbench run core-cujs/run_gemini_cli.yaml      # Gemini CLI
evalbench run core-cujs/run_claude.yaml          # Claude Code
```

Results will be generated in the `results/` directory as CSV reports.
