# Dataset Generation Plan: Nexis Supply Chain

## 1. Goal & Scope
- **Target Volume**: 5 questions (Concise test set).
- **Database Engine**: Spanner Graph.
- **Goal**: Verify NL-to-SQL/GQL translation for complex supply chain graph traversals, multimodal cost aggregations, and capacity balancing.

## 2. Business Query Classes & Coverage
1.  **Disruption Triage (SPOF)**: 1 question. Focus on graph reachability, node failure impact, and single-point-of-failure links using `InfrastructureGraph`.
2.  **Multimodal Route Discovery**: 1 question. Focus on multi-hop pathfinding, mode comparisons (Air, Ocean, Truck, Rail), and inter-city corridors using `LogisticsNet`.
3.  **Cold-Chain Integrity & Specialized Storage**: 1 question. Focus on facility tags (`Cold`, `Dry`, `Hazardous`) and connectivity constraints.
4.  **Capacity Balancing & Metrics**: 1 question. Focus on numerical aggregation (SUM, AVG), capacity thresholds, and cross-facility throughput analysis.
5.  **Reverse Logistics & Returns**: 1 question. Focus on `ReturnRoute` traversal, reclamation pipelines, and return reason analysis using `LogisticsNet`.

## 3. Ambiguity & Real-World phrasing
- Use synonyms like "factory" / "plant" / "manufacturing site".
- Use "warehouse" / "depot" / "DC" / "distribution center".
- Use regional groupings like "APAC", "EMEA", "NA", "North America".
- Include informal naming (e.g., "Tokyo facility", "Munich plant").
- Vary question complexity from simple lookups to multi-hop graph traversals.

## 4. SQL/GQL Requirements
- Use Spanner Graph syntax (`GRAPH InfrastructureGraph MATCH ...` or `GRAPH LogisticsNet MATCH ...`).
- Use standard GoogleSQL for relational joins (e.g., `Shipments` JOIN `Locations`).
- Ensure deterministic ordering (`ORDER BY`).
- Use parameterized queries for values.

## 5. Approval Gate
- I have reviewed the `design_doc.md` and mapped the entities.
- Target volume: 5 questions.
- Ready to proceed to Intelligent Generation.
