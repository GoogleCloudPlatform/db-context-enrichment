# Dataset Format Requirements

All evaluation example and dataset file must use the following schema:

```json
[
    {
        "id": "eval_001",
        "database": "<database_name>",
        "nlq": "How many accounts in Prague are eligible for loans?",
        "golden_sql": "SELECT COUNT(DISTINCT a.account_id) FROM account a JOIN district d ON a.district_id = d.district_id JOIN loan l ON a.account_id = l.account_id WHERE d.A3 = 'Prague'",
        "tags": [
            "complexity: medium",
            "topic: loan_eligibility",
            "source: expansion:value_substitution",
            "expansion_source_id: eval_002",
            "substituted_column: district.A3",
            "flagged:empty_result"
        ]
    }
]
```

- **id** `<example_id>`: unique identifier for each example, follows the `eval_<number>` format and is used to establish a collision-free generation environment. If using optional user-provided input dataset, retain the id of the original dataset (e.g., eval_001, eval_002, etc.) in the generated dataset.
- **`complexity`**: Query execution complexity:`"low"` (single table, no aggregation), `"medium"` (multi-table JOIN or aggregation), `"high"` (CTEs, subqueries, window functions, multi-condition logic).
- **`topic`**: Business domain or analytical theme (e.g., `"loan_eligibility"`, `"account_activity"`, `"regional_distribution"`).
- **`source`**:
  - If from user provided inputs, must be "user_provided:file_name", e.g. `"user_provided:input-dataset.json"`.
  - If from dataset generation, must include tag "generated:source(s)", e.g. `"generated:schema+code"`.
  - If from dataset expansion, must include a tag "expansion:strategy_name(s)", e.g. `"expansion:value_substitution"`.
- **`expansion_source_id`** / **`expansion_source_ids`**: Optional, only for expanded examples: traceability back to the originating example(s).
- **`flagged`**: To call reviewer attention to an example.
  - If an executed query returned 0 result set, use "flagged:empty_result". 