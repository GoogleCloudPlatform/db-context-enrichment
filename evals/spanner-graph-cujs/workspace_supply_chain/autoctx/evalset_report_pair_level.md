# Dataset Pair-Level Audit Report

| ID | NLQ | SQL Logic | Complexity |
| :--- | :--- | :--- | :--- |
| supply_chain_test_001 | Which factories lose their primary shipping link if the Tokyo distribution center goes offline? | Graph match `(f:Factories)-[:ShipsTo]->(w:Warehouses)` with filter on `WhName`. | Simple Graph Match |
| supply_chain_test_002 | What are the available inter-facility routes from the Munich manufacturing plant to distribution hubs in Tokyo, including up to 3 hops? | Variable-length path match `[:ShipsTo\|Route*1..3]`. | Complex Graph Path |
| supply_chain_test_003 | Identify all factories in North America that have direct shipping connections to cold storage warehouses. | Graph match with multiple property filters (`StorageType`, `Region`). | Filtered Graph Match |
| supply_chain_test_004 | List the total manufacturing capacity for each region, sorted by capacity in descending order. | Relational JOIN and GROUP BY with SUM aggregation. | Relational Aggregation |
| supply_chain_test_005 | Show all available return routes originating from warehouses in the NA region to their inspection cities. | Graph match `(w:Warehouses)-[:ReturnRoute]->(l:Locations)` with region filter. | Directed Graph Traversal |
