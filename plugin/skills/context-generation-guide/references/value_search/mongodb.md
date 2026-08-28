# MongoDB (MQL / Firestore Enterprise Edition) Value Search Templates

This reference provides MQL query templates and examples for Value Search in MongoDB MQL (`firestore_mql`) and Firestore Enterprise Edition with MongoDB Compatible API.

## Requirements & Schema Contract

Value Search queries map user-supplied natural language terms (e.g., `"London"`, `"electronics"`, `"credit card"`) to stored field values in collections.

When evaluated by the value linking engine, value search queries project a standard shape:
- `value`: The matched database field value.
- `columns`: The qualified collection and field name (`'{collection}.{field}'`).
- `concept_type`: The semantic concept category (`'{concept_type}'`).
- `distance`: Similarity distance score (0 for exact match, fractional for fuzzy/scored matches).
- `context`: Any auxiliary context string.

---

## Supported Match Functions

### 1. EXACT_MATCH_STRINGS

**Description**: Exact match for string field values.
**Example**: Use when finding specific status codes, categorical identifiers, or exact names where precise spelling is required.

**Template (Aggregation Pipeline)**:
```json
{
  "query": "db.{collection}.aggregate([{ $match: { '{field}': $value } }, { $project: { _id: 0, value: '${field}', columns: { $literal: '{collection}.{field}' }, concept_type: { $literal: '{concept_type}' }, distance: { $literal: 0 }, context: { $literal: '' } } }, { $limit: 10 }])",
  "concept_type": "{concept_type}",
  "description": "Exact match for {field} in {collection}"
}
```

---

### 2. REGEX_STRING_MATCH (Fuzzy / Case-Insensitive)

**Description**: Case-insensitive substring and regex matching.
**Example**: Use when searching for names, store locations, or tags where users might provide lowercase, uppercase, or partial matches.

**Template (Aggregation Pipeline)**:
```json
{
  "query": "db.{collection}.aggregate([{ $match: { '{field}': { $regex: $value, $options: 'i' } } }, { $project: { _id: 0, value: '${field}', columns: { $literal: '{collection}.{field}' }, concept_type: { $literal: '{concept_type}' }, distance: { $literal: 0 }, context: { $literal: '' } } }, { $limit: 10 }])",
  "concept_type": "{concept_type}",
  "description": "Case-insensitive regex substring search for {field} in {collection}"
}
```

**Template (Simple Find Query)**:
```json
{
  "query": "db.{collection}.find({ '{field}': { $regex: $value, $options: 'i' } }, { _id: 0, '{field}': 1 })",
  "concept_type": "{concept_type}",
  "description": "Case-insensitive find query for {field} in {collection}"
}
```

---

### 3. TEXT_SEARCH_MATCH (Full-Text Indexed Match)

**Description**: Full-text search with relevance ranking.
**Prerequisites**: Requires a text index on the target collection/field: `db.{collection}.createIndex({ '{field}': 'text' })`.
**Example**: Use when searching for product descriptions, articles, customer reviews, or unstructured narrative text.

**Template (Aggregation Pipeline)**:
```json
{
  "query": "db.{collection}.aggregate([{ $match: { $text: { $search: $value } } }, { $project: { _id: 0, value: '${field}', columns: { $literal: '{collection}.{field}' }, concept_type: { $literal: '{concept_type}' }, distance: { $subtract: [1, { $meta: 'textScore' }] }, context: { $literal: '' } } }, { $sort: { distance: 1 } }, { $limit: 10 }])",
  "concept_type": "{concept_type}",
  "description": "Full-text relevance search for {field} in {collection}"
}
```

---

## Best Practices

*   Use qualified field paths (e.g. `items.name` or `customer.email`) when querying nested subdocuments.
*   Always include `{ $limit: 10 }` in aggregation pipelines to constrain result set size and avoid streaming large document collections during value linking.
*   Use projection stages to exclude `_id` and non-essential fields to optimize memory and network throughput.
