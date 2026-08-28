## Firestore (MongoDB API)

**Required Information:**
- Data Source Name (e.g., `my-firestore-db`)
- Google Cloud Project ID
- Database Name (e.g., `(default)` or specific database ID)

**Template:**

```yaml
kind: source
name: <data_source_name>
type: firestore
project: <project_id>
database: <database_name>
---
kind: tool
name: <data_source_name>-get-schema
type: firestore-mongodb-get-schema
source: <data_source_name>
description: Use this tool to retrieve schemas for Firestore collections.
---
kind: tool
name: <data_source_name>-execute-mql
type: firestore-mongodb-execute-mql
source: <data_source_name>
description: Use this tool to execute MQL queries against Firestore.
```
