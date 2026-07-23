This is not an officially supported Google product. This project is not eligible for the [Google Open Source Software Vulnerability Rewards Program](https://bughunters.google.com/open-source-security), [Google Cloud Platform/SecOps Terms of Service](https://cloud.google.com/terms), [How Gemini for Google Cloud uses your data](https://cloud.google.com/gemini/docs/discover/data-governance). This tool is provided "as is" without warranty of any kind. Users are solely responsible for understanding and managing the tool's interaction with their databases. Use of this tool constitutes acceptance of all risks associated with database access, reading, usage, and modifications.

# Context Engineering Agent

The **Context Engineering Agent** is an AI coding agent plugin designed to run in developer agent harnesses (such as Claude Code, Antigravity, or Gemini CLI). It generates, evaluates, and iteratively tunes tailored context artifacts (`ContextSets` comprising `Templates`, `Facets`, and `Value Searches`) to enrich database schemas for **Gemini Data Analytics's data agent developer platform tools**, such as QueryData ([AlloyDB](https://cloud.google.com/gemini/docs/data-agents/querydata/alloydb/data-agent-overview) | Cloud SQL: [PostgreSQL](https://cloud.google.com/gemini/docs/data-agents/querydata/cloud-sql-postgres/data-agent-overview) / [MySQL](https://cloud.google.com/gemini/docs/data-agents/querydata/cloud-sql-mysql/data-agent-overview) | [Spanner (GoogleSQL)](https://cloud.google.com/gemini/docs/data-agents/querydata/spanner/data-agent-overview)).

---

## Why Context Engineering?

When building data agents and natural language analytics interfaces, accurately translating user intent into database queries is critical. 

As outlined in the **QueryData Data Agent Overview** ([AlloyDB](https://cloud.google.com/gemini/docs/data-agents/querydata/alloydb/data-agent-overview) | Cloud SQL: [PostgreSQL](https://cloud.google.com/gemini/docs/data-agents/querydata/cloud-sql-postgres/data-agent-overview) / [MySQL](https://cloud.google.com/gemini/docs/data-agents/querydata/cloud-sql-mysql/data-agent-overview) | [Spanner (GoogleSQL)](https://cloud.google.com/gemini/docs/data-agents/querydata/spanner/data-agent-overview)), by optimizing a `ContextSet` to match your application's expected query stream, the **QueryData API** acts as a data agent tool capable of achieving **~100% NL-to-SQL translation accuracy with low latency**.

---

## Core Concepts

A `ContextSet` is the central artifact generated and managed by the agent, containing structured knowledge in three primary forms:

* **Templates**: Links a natural language query pattern to a complete query statement.
* **Facets**: Reusable, modular query fragments (e.g., parameterized `WHERE` clauses or specialized join filters) linked to domain vocabulary.
* **Value Searches**: Specialized mapping queries that dynamically resolve user-supplied values (e.g., *"Lndn"*) to database records (*"London"*) via the capabilities of the underlying database, such as embedding search, AI operators, or simple trigram search.

For full schema details, structure specifications, and dialect-specific JSON representations of `ContextSets`, see the official **Context Sets Overview** ([AlloyDB](https://cloud.google.com/gemini/docs/data-agents/querydata/alloydb/context-sets-overview) | Cloud SQL: [PostgreSQL](https://cloud.google.com/gemini/docs/data-agents/querydata/cloud-sql-postgres/context-sets-overview) / [MySQL](https://cloud.google.com/gemini/docs/data-agents/querydata/cloud-sql-mysql/context-sets-overview) | [Spanner (GoogleSQL)](https://cloud.google.com/gemini/docs/data-agents/querydata/spanner/context-sets-overview)).

---

## Prerequisites & Environment Setup

Before getting started, prepare your GCP environment, required APIs (Data Analytics API, Gemini for Google Cloud API, Dataplex Universal Catalog API), IAM permissions, and database Data API settings.

Follow the step-by-step setup guide in the official documentation:
👉 **Prepare Your Environment**: ([AlloyDB](https://cloud.google.com/gemini/docs/data-agents/querydata/alloydb/build-context-gemini-cli#prepare-your-environment) | Cloud SQL: [PostgreSQL](https://cloud.google.com/gemini/docs/data-agents/querydata/cloud-sql-postgres/build-context-gemini-cli#prepare-your-environment) / [MySQL](https://cloud.google.com/gemini/docs/data-agents/querydata/cloud-sql-mysql/build-context-gemini-cli#prepare-your-environment) | [Spanner (GoogleSQL)](https://cloud.google.com/gemini/docs/data-agents/querydata/spanner/build-context-gemini-cli#prepare-your-environment))

---

## Primary Workflow Phases

The extension enables you to craft an optimized context for QueryData API through three primary phases:

### Phase 1: Artifact Ingestion
*Why it matters: Without broader context on the application's goals and scope, AI models generate sterile queries based solely on database column names, missing how your users actually ask for information.*

1. **Connect & Discover**: Inspect any resources shared with the agent that may be relevant to your application and its domain.
2. **Domain Concept Extraction**: Extract key terminology, domain rules, jargon, and common query patterns.
3. **Schema Mapping**: Map extracted concepts directly to their corresponding underlying database tables and columns.

### Phase 2: Dataset Creation
*Why it matters: A realistic golden dataset establishes your benchmark for accuracy, ensuring your data agent is evaluated against messy human language rather than artificially simple database queries.*

1. **Dataset Planning**: Set goals for your dataset, deciding on question difficulty, business topics to cover, and total dataset size.
2. **Initial Question Generation**: Create a core set of natural language questions grounded in your business documents, verifying that each question's corresponding query runs accurately on your database.
3. **Dataset Expansion**: Scale up the question set by adding real-world variations, such as different human phrasing, complex combinations such as joins and measures, and realistic values—to cover ambiguity of language. 
4. **Dataset Validation**: Audit the full dataset against your original plan and ask for your approval before proceeding. 

### Phase 3: Context Optimization via Recursive Hill-Climbing
*Why it matters: Iterative evaluation and gap analysis systematically fix query translation failures, driving accuracy toward ~100% while ensuring fixes don't break previously working queries.*

The optimization loop creates an initial `ContextSet` and then iteratively refines it using evaluation feedback:

1. **Bootstrap**: Generate an initial baseline context.
2. **Evaluate**: Measure context effectiveness against a golden dataset.
3. **Hill-Climbing**: Perform gap analysis on failures and generate automated fixes.
4. **Iterate**: Apply the improved context and re-run evaluation to continuously improve quality.
5. **Final Validation** (Optional): Verify mutations against a separated test set to ensure generalization and prevent overfitting.

*Note: While there is a typical ordering for these CUJs, the agent is flexible to how you want to execute. You can run the full pipeline end-to-end, trigger any individual phase, or ask for targeted changes to the `ContextSet`.*

---

## Bring Artifacts via Filesystem or MCP

To prevent the AI from generating trivial schema-only questions (e.g., *"What is the count of users?"*), the agent bridges the semantic gap by grounding generation with real-world business documents—such as **product glossaries**, **business wikis**, **SOPs**, **ORM data models**, **emails**, or **application or database logs**.

You can provide business artifacts directly to the agent from local filesystems or via **Model Context Protocol (MCP) Servers**.

---

## How to Use

Launch your agent harness (Gemini CLI, Claude Code, or Antigravity) in your workspace directory and interact in natural language:

### Example Natural Language Prompts
* **End-to-End**: (From the app directory) *"Optimize context for my app."*
* **Dataset Curation**: *"Expand my dataset with app changes in `<PULL_REQUEST_LINK>`."*
* **Adhoc Evaluation**: *"Evaluate accuracy of QueryData with `ContextSet` `<context_set_id>` on dataset.json."*
* **Targeted Authoring**: *"Add a facet for active premium subscriptions."*

---

> 🛠️ **Developer Note**: For developer setup instructions, local CLI linking, unit testing (`pytest`), linting (`ruff`), and fork release testing, see [docs/development.md](docs/development.md).
