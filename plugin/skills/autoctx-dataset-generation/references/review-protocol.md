# NL2SQL Dataset Audit & Review Protocol

This protocol dictates the strict evaluation standards and reporting formats for the generated NL-SQL pairs. The audit is broken into two distinct tiers: Individual Pair-Level Review and Aggregate Dataset-Level Reporting.

## Tier 1: Pair-Level Audit Criteria
Evaluate every generated NL2SQL pair against the following dimensions. 

1. **Context Utilization & Grounding:** 
   * **Review:** Does the pair rely heavily on the provided business context, or is it generic? 
   * **Action:** You must cite the exact source (e.g., local file path, URL, database schema snippet, or specific seed question) that grounded the generation of this pair.
2. **NLQ Quality (Realism & Ambiguity):** 
   * **Review:** Is the English question conversational and realistic for a business user? Does it avoid sounding like "SQL translated to English"?
3. **SQL Correctness & Equivalence:** 
   * **Review:** Is the SQL syntactically sound and logically equivalent to the NLQ intent? Does it strictly adhere to the `acceptance-criteria.md` (no hallucinated schema, deterministic ordering)?
4. **Complexity Categorization:** 
   * **Review:** Tag the pair's SQL complexity as **Simple** (basic SELECT/WHERE), **Medium** (JOINs, basic aggregations, GROUP BY), or **Complex** (CTEs, Window Functions, Subqueries, layered conditions).

## Tier 2: Dataset-Level Aggregation Metrics
After evaluating individual pairs, aggregate the metadata to compute the overall health and diversity of the dataset.

1. **Schema Heatmap:** Analyze which tables and columns are queried most frequently. Identify any critical schema elements that were neglected.
2. **Complexity Distribution:** Calculate the percentage breakdown of Simple vs. Medium vs. Complex queries. Ensure it aligns with the requested target distribution.
3. **SQL Taxonomy Coverage:** List the frequency of specific SQL features used across the dataset (e.g., `% of pairs using CTEs`, `% using LEFT JOINs`, `% using Date/Time functions`, `% using Window functions`).
4. **Intent Diversity:** Categorize the types of business questions asked (e.g., Operational lookups, Temporal comparisons, Financial aggregations, Ranking/Top-N).

## Deliverables & File Management
You must generate two final markdown reports. Pay strict attention to file persistence: 
* **If file already exists:** Read the existing files and intelligently append/update the new metrics without destroying the historical data.
* **If file does not exist:** Create the files.

**Deliverable 1: `evalset_report_pair_level.md`**
* Format as a structured list or table containing every finalized pair.
* Include the NLQ, the SQL, the Complexity Tag, the Grounding Citation, and a brief 1-sentence justification for its Quality/Correctness score.

**Deliverable 2: `evalset_report_dataset_level.md`**
* Format as an executive summary.
* Include the Total Pair Count, Schema Heatmap, Complexity Distribution, SQL Taxonomy Coverage, and a "Gap Analysis" (a brief note on what SQL patterns or tables should be targeted in the next expansion).