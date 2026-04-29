# Evaluation

This directory contains the evaluation suite for the main functionalities of the DB Context Enrichment extension. This evaluation measures the agent's ability to handle standard database enrichment tasks and workflows.

## Overview

The evaluation uses the [evalbench](https://github.com/GoogleCloudPlatform/evalbench) framework with the `geminicli` orchestrator to run a set of simulated user tasks against the agent. 

## Configuration Files

- `core-cujs/dataset.json`: Defines the test cases, prompts, and expected behaviors for the Core CUJs.
- `core-cujs/run.yaml`: The main evaluation configuration file, defining the scorers, models, and reporting settings.
- `core-cujs/model.yaml`: The configuration for the system-under-test (SUT) model.
- `core-cujs/gemini_2.5_pro_model.yaml`: The configuration used for the simulated user and the LLM-as-a-judge scorers.

## Evaluation Metrics

The suite evaluates the agent across several dimensions using the following scorers:

* **Goal Completion**: An LLM-based judge that determines if the agent successfully fulfilled the 
* **Turn Count**: Number of interactions required to complete the task.
* **End-to-End Latency**: Total time taken to resolve the user query.
* **Tool Call Latency**: Time spent executing database context tools.
* **Token Consumption**: Input and output token usage.

## How to Run

From the `evals/` directory, execute the evaluation using latest [evalbench](https://github.com/GoogleCloudPlatform/evalbench/releases):

```bash
cd evals/
evalbench run core-cujs/run.yaml
```

Results will be generated in the `results/` directory as CSV reports.
