# Environment & Context Acquisition Protocol

This protocol serves as a guide to build a comprehensive, grounded understanding of the business domain and technical environment. 

**1. Session State & Operational Readiness**
*   **Objective:** Establish a collision-free generation environment.
*   **Action:** Use your filesystem tools to find the highest existing <pair_id> in the format `eval_<number>` in the generated NL-SQL pair output file. Auto-increment this integer to establish the starting ID for the current session (e.g., if `eval_002` exists, start at `eval_003`). If no file exists, default to `eval_001`. 
*   **Required State:** The starting ID for the current session for the sequence of NL-SQL pairs to be generated.

**2. Schema & Artifact Integration (Domain Mapping)**
*   **Objective:** Bridge the gap between technical architecture and business terminology.
*   **Action:** Check for `tools.yaml` to identify DB configurations. Use `<source>-list-schemas` tools to fetch schemas. If unavailable, ask the user to run the initialization workflow for auto context generation. Process business context artifacts (e.g., documents, Markdown, PDFs, source codes locally or from a remote repo such as github, etc.), offline or MCP-fetched schemas, or application source code. **Assign a friendly short name to each ingested artifact (e.g., "Q1_2024_Sales_Report.pdf" → "Sales Report", "https://github.com/kupp0/google-dach-summit26-database-labs" → "github-google-dach-summit26-database-labs") so they can be concisely referred to as sources in the grounding citations for generated pairs. Save this artifact-to-short-name mapping to an output file named `evalset_environment_inputs.md`.** Map business definitions to technical schema elements. 
*   **Required State:** A clear mapping between business concepts (found in PDFs, Markdown, source codes locally or from a remote repo) and actual database elements (fetched via `<source>-list-schemas`). This mapping should naturally filter out irrelevant system tables, migration records, or deprecated columns. The `evalset_environment_inputs.md` file must be successfully created and populated with the artifact short names.

**3. Usage Heatmapping**
*   **Objective:** Identify the highest-value data structures based on real-world application behavior.
*   **Action:** Analyze source code, ORMs, or Query Logs to identify high-priority tables, frequently joined relationships, and common filter criteria. Ignore system tables or deprecated columns unless explicitly requested.
*   **Required State:** An aggregated view of prioritized tables, frequently utilized `JOIN` paths, and common filter criteria, derived by analyzing provided application source code, ORMs, design doc, historical query logs, etc., which are written to the `evalset_environment_inputs.md`.

**4. Log Reverse-Translation (Seed Derivation)**
*   **Objective:** Extract authentic business intents to serve as the foundation for dataset generation.
*   **Action:** If query logs are provided, filter out DML/administrative queries. Translate meaningful analytical SELECT statements into business NLQs to serve as "Seed Pairs".
*   **Required State:** A curated set of "Seed Pairs", which are written to the `evalset_environment_inputs.md`.

**5. Business Rule Shift Resolution**
*   **Objective:** Resolve the source of truth in the ingested schemas and artfacts when some of them contains outdated business rules or mismatched information.
*   **Action:** Analyze the schemas and artifacts (source codes, query logs, documents, etc) to detect any inconsistency and mismatched information which represent a business rule shift (e.g., document mentions use of `table_a` while application code use `table_b` for the same entity and similar logic). If yes, inspect the content and reason for the most updated business rules to resolve the conflicts. 
*   **Required State:** A detected set of shifted business rules and the single source of truth for each business rule shift that should be used for the grounded understanding, which are written to the `evalset_environment_inputs.md`.