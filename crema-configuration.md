# Crema Configuration

Crema requires certain information from the user to function correctly. Below is the minimum set of configurations (taking AlloyDB as an example):

- **DB connection information**
  - GCP Project
  - Region
  - AlloyDB Cluster
  - AlloyDB Instance
  - AlloyDB Database
- **Context set information**
  - Context set ID
- **Dataset information**
  - Local file path to the golden evaluation dataset

Note that the database user/password is not needed, since authentication relies on ADC.

The dataset uses the **simplified user-facing format** — a JSON list where each entry has `id`, `database`, `nlq`, and `golden_sql` fields. Crema's evaluation tooling converts this into the richer Evalbench-internal format (`golden_queries.json`) as part of config generation, so the user never has to author Evalbench-format datasets directly.

## Current state

DB connection information is collected when the user initializes Crema (e.g., "set up database connection" or "initialize my workspace") and stored in `tools.yaml`. This file serves two roles:

1. It is consumed by the MCP Toolbox to expose database tools (list schemas, execute SQL).
2. It acts as the source of truth for database connection information used downstream — for example, to construct the database config YAML for Evalbench during evaluation.

The context set ID, by contrast, is requested from the user only at evaluation time. This asymmetry is intentional: DB connection info is needed for nearly all Crema features, while the context set ID is only required for evaluation.

In addition to these required configurations, Evalbench supports a richer set of customizable options — for example, which scorer to use, which LLM model the scorer uses, the parallelization level, etc. These are currently set by Crema itself with default values.

Crema has a dedicated tool that deterministically turns the minimum set of information above into a valid Evalbench run configuration — specifically `db_config.yaml`, `llmrater_config.yaml`, `model_config.yaml`, and `run_config.yaml`. The generated configurations are written to the local filesystem so the agent can then shell out to Evalbench to run the evaluation.

## Questions

### Q1: Do we expect the user to tune the optional Evalbench configurations?

Rarely. We argue most users won't want that level of granular control. That said, the generated configuration should remain accessible and editable on disk for users who do want to tune it.

### Q2: Can the user-provided configuration set be simplified further?

No. The list above — DB connection info, context set ID, and dataset path — is the minimum information required for Crema to function correctly. None of these can be defaulted or inferred.

(Note: this question is about what the *user* must supply. Q4 below addresses whether the *generated Evalbench* configuration could be simplified — these are separate concerns.)

### Q3: Can we get rid of `tools.yaml`?

Theoretically yes, but practically we don't think it would simplify things. `tools.yaml` already holds the minimum information needed to connect to the database — the tool definitions may look unusual at first glance, but they also give the developer visibility into how database connections are wired up. Removing `tools.yaml` would likely just push the same information into a new `config.yaml`.

There is no easy way for Evalbench to read `tools.yaml` directly, so the database section of the generated Evalbench config will continue to be derived from `tools.yaml` rather than read from it at runtime.

### Q4: Can we simplify the generated Evalbench configuration?

We are **not** planning to simplify it. While it would technically be possible to collapse the four generated YAML files into a single slimmer file with defaults baked in, doing so would reduce the user's ability to tune the underlying values, and we don't see strong demand for that simplification today. The generated files stay as they are.

### Q5: How can we better offer the evaluation feature?

A good evaluation capability in Crema should satisfy these requirements:

1. A user can trigger an evaluation run by providing only the minimum set of information, without manually composing configurations.
2. A user can point Crema to a pre-existing evaluation configuration ("hey, this is my run config") and have Crema use it directly. The evaluation skill should give the agent sufficient knowledge to invoke Evalbench against that config.
3. For evaluations performed by Crema, the user knows which configuration was used and can inspect its details on disk.
4. A user can manually run evaluation against a specific configuration file — either system-generated or hand-written.

To support these requirements, we propose:

- **Reposition the evaluation skill to focus narrowly on the evaluation task itself.** The skill should give the agent a crisp, clear understanding of how to perform an evaluation, what configurations are required as input, where the generated configuration files land, and how to invoke Evalbench. It should not own experiment selection, base-context selection, or any other orchestration concerns.
- **Make every skill standalone, and capture the hill-climbing orchestration entirely within `autoctx-hillclimb`.** Today, the evaluation skill is partially intertwined with the hill-climb loop (e.g., it selects an experiment folder, records active experiments in `state.md`, and points the user toward refinement next steps). That orchestration logic should move into `autoctx-hillclimb`, leaving the evaluation skill independent and reusable in non-hill-climbing contexts (such as one-off evaluations against a user-supplied config).
