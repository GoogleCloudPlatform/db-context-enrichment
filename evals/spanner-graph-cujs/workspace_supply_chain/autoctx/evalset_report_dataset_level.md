# Dataset-Level Audit Report: Nexis Supply Chain Test Set

## 1. Distribution Summary
- **Total Questions**: 5
- **Graph Queries (GQL)**: 4
- **Relational Queries (SQL)**: 1

## 2. Capability Coverage
- **Disruption Triage**: 20% (1/5)
- **Multimodal Route Discovery**: 20% (1/5)
- **Cold-Chain Integrity**: 20% (1/5)
- **Capacity Balancing**: 20% (1/5)
- **Reverse Logistics**: 20% (1/5)

## 3. Schema Coverage
- **Nodes**: Factories, Warehouses, Locations
- **Edges**: ShipsTo, Route, ReturnRoute
- **Tables**: Shipments (referenced in Class 2/4 in larger sets, covered via Join in this subset)

## 4. Quality Assurance
- [x] All queries use Spanner Graph or standard GoogleSQL.
- [x] All queries have deterministic `ORDER BY` clauses.
- [x] Natural language varies in phrasing and entity naming.
- [x] Coverage of all core business requirement classes.
