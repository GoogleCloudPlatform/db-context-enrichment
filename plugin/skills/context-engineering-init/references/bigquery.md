## BigQuery

**Required Information:**
- Data Source Name (e.g., `my-bigquery-db`)
- Google Cloud Project ID
- Dataset ID
- *(Optional)* Dataset location (e.g., `US`, `EU`, `us-central1`)

> The toolbox BigQuery source has **no `dataset` field** (toolbox rejects unknown fields). Declare the target dataset in `allowedDatasets` instead — evaluation requires exactly one entry. This also restricts the toolbox tools to that dataset.

**Template:**

```yaml
kind: source
name: <data_source_name>
type: bigquery
project: <project_id>
location: <dataset_location>  # optional; omit to use the BigQuery default
allowedDatasets:
  - <dataset_id>
---
kind: tool
name: <data_source_name>-list-schemas
type: bigquery-sql
source: <data_source_name>
description: |
  Use this tool to list tables and their schemas in the <data_source_name> dataset.

  Progressive Schema Discovery (Recommended):
  1) Fetch structure first,
  2) Go deep on specific parts if interested,
  3) Use batching if info is too large.
statement: |
  SELECT table_name, column_name, data_type, description FROM `<project_id>`.`<dataset_id>`.INFORMATION_SCHEMA.COLUMN_FIELD_PATHS ORDER BY table_name, column_name
---
kind: tool
name: <data_source_name>-execute-sql
type: bigquery-execute-sql
source: <data_source_name>
description: Use this tool to execute SQL statements against the <data_source_name> BigQuery dataset.
```
