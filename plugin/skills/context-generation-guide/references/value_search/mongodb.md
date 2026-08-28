# MongoDB (MQL / Firestore Enterprise Edition) Value Search Templates

This reference provides MQL query templates and examples for Value Search in MongoDB MQL (`firestore_mql`) and Firestore Enterprise Edition with MongoDB Compatible API.

## Requirements & Server-Side Contract

Value Search queries map user-supplied natural language terms (e.g., `"London"`, `"electronics"`, `"credit card"`) to stored field values in collections.

Under the server-side value linking contract (see `valuelinking.go`), all value search queries must project a specific 5-field schema:

| Field Name | Type | Description |
|---|---|---|
| `value` | string / scalar | The matching field value from the document |
| `columns` | string | The qualified collection and field name (e.g. `'{collection}.{field}'`) |
| `concept_type` | string | The semantic concept category (e.g. `'{concept_type}'`) |
| `distance` | float / int | Distance score between 0 (exact match) and 1 |
| `context` | string / object | Auxiliary context string or JSON metadata (`''` or `{}`) |

In MongoDB MQL, aggregation pipelines (`db.{collection}.aggregate([...])`) with a `$project` stage are used to produce this uniform schema.

---

## Supported Match Functions

### 1. EXACT_MATCH_STRINGS

**Description**: Exact match for string field values.
**Example**: Use when finding specific status codes, categorical identifiers, or exact names where precise spelling is required.

**Template**:
```json
{
  "query": "db.{collection}.aggregate([{ $match: { '{field}': $value } }, { $project: { _id: 0, value: '${field}', columns: { $literal: '{collection}.{field}' }, concept_type: { $literal: '{concept_type}' }, distance: { $literal: 0 }, context: { $literal: '' } } }, { $limit: 10 }])",
  "concept_type": "{concept_type}",
  "description": "Exact match for {field} in {collection}"
}
```

---

### 2. REGEX_STRING_MATCH (Fuzzy / Case-Insensitive)

**Description**: Case-insensitive substring and regex matching for fuzzy value resolution.
**Example**: Use when searching for names, store locations, or tags where users might provide lowercase, uppercase, or partial matches.

**Template**:
```json
{
  "query": "db.{collection}.aggregate([{ $match: { '{field}': { $regex: $value, $options: 'i' } } }, { $project: { _id: 0, value: '${field}', columns: { $literal: '{collection}.{field}' }, concept_type: { $literal: '{concept_type}' }, distance: { $literal: 0 }, context: { $literal: '' } } }, { $limit: 10 }])",
  "concept_type": "{concept_type}",
  "description": "Case-insensitive regex substring search for {field} in {collection}"
}
```

---

### 3. TEXT_SEARCH_MATCH (Full-Text Search)

**Description**: Full-text keyword search using MongoDB text index with relevance scoring.
**Prerequisites**: Requires a text index on the target collection/field: `db.{collection}.createIndex({ '{field}': 'text' })`.
**Example**: Use when searching for product descriptions, articles, customer reviews, or unstructured narrative text.

**Template**:
```json
{
  "query": "db.{collection}.aggregate([{ $match: { $text: { $search: $value } } }, { $project: { _id: 0, value: '${field}', columns: { $literal: '{collection}.{field}' }, concept_type: { $literal: '{concept_type}' }, distance: { $subtract: [1, { $meta: 'textScore' }] }, context: { $literal: '' } } }, { $sort: { distance: 1 } }, { $limit: 10 }])",
  "concept_type": "{concept_type}",
  "description": "Full-text relevance search for {field} in {collection}"
}
```

---

### 4. SEMANTIC_SIMILARITY_MATCH (Vector Search)

**Description**: Vector similarity search over pre-computed embeddings.
**Prerequisites**: Requires vector indexing on the embedding field (`{embedding_field}`).
**Example**: Use when matching unstructured semantic queries where keywords do not overlap with document contents.

**Template**:
```json
{
  "query": "db.{collection}.aggregate([{ $vectorSearch: { index: '{vector_index}', path: '{embedding_field}', queryVector: $embedding, numCandidates: 100, limit: 10 } }, { $project: { _id: 0, value: '${field}', columns: { $literal: '{collection}.{field}' }, concept_type: { $literal: '{concept_type}' }, distance: { $subtract: [1, { $meta: 'vectorSearchScore' }] }, context: { $literal: '' } } }])",
  "concept_type": "{concept_type}",
  "description": "Vector semantic similarity search for {field} in {collection}"
}
```

---

## Best Practices

*   **Projection Compliance**: Always include `$project` stage returning `value`, `columns`, `concept_type`, `distance`, and `context` to satisfy the server-side value linking contract.
*   **Result Limits**: Constrain pipeline execution using `{ $limit: 10 }` to avoid streaming large document collections.
*   **Nested Subdocuments**: Use dot notation (e.g. `items.name`, `customer.address.city`) for `{field}` paths in nested subdocuments.
