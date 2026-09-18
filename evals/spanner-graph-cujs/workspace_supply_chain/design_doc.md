# Product Requirements & System Architecture Specification
## Nexis Global Supply Chain Control Tower & Logistics Copilot (v2.4)

---

### 1. Executive Summary & Product Vision

The **Nexis Global Supply Chain Control Tower** is an enterprise-grade operational resilience platform designed for Fortune 500 manufacturers and global logistics operators. Global supply chains face unprecedented volatility—geopolitical disruptions, port closures, severe weather, and carrier capacity bottlenecks can instantly strand millions of dollars in freight.

The Control Tower integrates real-time manufacturing telemetry, multi-echelon warehouse storage management, multimodal freight tracking, and an embedded **Logistics AI Copilot**. The copilot enables logistics directors, incident responders, and facility coordinators to query, simulate, and resolve network bottlenecks using conversational natural language.

---

### 2. Target User Personas & Core Workflows

```
┌────────────────────────────────────────────────────────────────────────┐
│                        Nexis Logistics Platform                        │
│                                                                        │
│   ┌───────────────────────┐  ┌───────────────────┐  ┌──────────────┐   │
│   │ Logistics Director    │  │ Incident Manager  │  │ Plant Lead   │   │
│   │ (Network Optimization)│  │ (Disruption Triage│  │ (Capacity)   │   │
│   └───────────┬───────────┘  └─────────┬─────────┘  └───────┬──────┘   │
│               │                        │                    │          │
│               └────────────────────────┼────────────────────┘          │
│                                        │                               │
│                                        ▼                               │
│                     ┌──────────────────────────────────────┐           │
│                     │       Natural Language Copilot       │           │
│                     │  • Disruption Simulation             │           │
│                     │  • Multimodal Route Optimization     │           │
│                     │  • Cold-Chain Storage Allocation     │           │
│                     │  • Reverse Logistics Routing         │           │
│                     └──────────────────────────────────────┘           │
└────────────────────────────────────────────────────────────────────────┘
```

#### Persona A: Global Logistics Director (Strategic Planning & Cost Control)
- **Role**: Oversees global carrier contracts, freight budget allocation, and regional logistics efficiency across North America (NA), Europe/Middle East (EMEA), and Asia-Pacific (APAC).
- **Core Workflow**: Evaluates transport mode cost tradeoffs (`Air` vs. `Ocean` vs. `Rail` vs. `Truck`), analyzes regional capacity utilization, and identifies structural network inefficiencies.

#### Persona B: Disruption Response Coordinator (Live Incident Management)
- **Role**: On-call responder managing active supply chain crises (e.g., port strikes, severe storms, warehouse power failures).
- **Core Workflow**: Identifies stranded manufacturing plants when a distribution hub goes offline, evaluates multi-hop bypass routes, and dynamically reroutes time-critical freight to secondary hubs.

#### Persona C: Plant & Warehouse Operations Lead (Facility Allocation)
- **Role**: Manages physical facility throughput, inbound/outbound staging, and regulatory compliance (e.g., cold-chain integrity, hazardous materials).
- **Core Workflow**: Verifies factory manufacturing capacity against downstream warehouse intake bandwidth and routes perishable goods exclusively through temperature-controlled (`Cold`) storage facilities.

---

### 3. Natural Language Component: The "Logistics Copilot"

The platform embeds a conversational AI assistant directly into the main operations dashboard and emergency response console.

#### Interaction Model & Design Goals
- **Zero-Friction Conversational Triage**: Operators must not need to construct complex relational queries or manually navigate multi-layered map filters during critical disruption incidents.
- **Entity & Geographic Grounding**: The assistant must seamlessly resolve real-world facility names, city identifiers, transport modes, and regional groupings (e.g., `"APAC hubs"`, `"European plants"`, `"refrigerated storage"`).
- **Ambiguity & Disambiguation Handling**: When users ask for a specific facility by informal name (e.g., *"Tokyo facility"* vs. *"Tokyo Central warehouse"* vs. *"Tokyo Manufacturing plant"*), the system resolves to the exact operational entity.

---

### 4. Key Business Query Capabilities & Functional Requirements

The Natural Language Copilot must reliably answer 5 core classes of business questions:

#### Class 1: Disruption Triage & Single-Point-of-Failure (SPOF) Simulation
*When a key logistics node is compromised, coordinators must instantly understand upstream and downstream exposure.*
- **Sample Business Questions**:
  - *"If our distribution center in Tokyo is shut down, which factories lose their primary shipping destination?"*
  - *"Which manufacturing plants have single-point-of-failure links to Asian transit hubs?"*
  - *"Find all active freight shipments currently passing through the EMEA region."*
- **Operational Requirement**: The copilot must trace the directed supply chain graph from manufacturing sources through intermediate transfer hubs to destination distribution centers.

#### Class 2: Multimodal Route Discovery & Carrier Tradeoff Optimization
*Logistics planners need to compare speed, transit legs, and cost profiles across transport modes.*
- **Sample Business Questions**:
  - *"What are the available multi-hop shipping routes from our Munich manufacturing plant to distribution hubs in Tokyo?"*
  - *"Compare the average and total shipment cost for Air freight versus Ocean freight over the last quarter."*
  - *"List all shipments that exceeded $5,000 in transit cost and their transport modes."*
- **Operational Requirement**: Must support multi-leg pathfinding across geographic locations while aggregating transactional transit metrics (average cost, total volume, mode breakdowns).

#### Class 3: Cold-Chain Integrity & Specialized Storage Allocation
*Pharmaceutical and perishable goods require strict adherence to temperature-controlled logistics corridors.*
- **Sample Business Questions**:
  - *"Which factories are connected via direct shipping links to Cold storage warehouses in North America?"*
  - *"Show all distribution centers certified for Hazardous material storage and their regional locations."*
  - *"List warehouses that have Dry storage capacity in the APAC region."*
- **Operational Requirement**: Must cross-reference facility storage capability tags (`Cold`, `Dry`, `Hazardous`) with upstream manufacturing outputs and geographic boundaries.

#### Class 4: Manufacturing Capacity vs. Distribution Intake Balancing
*Operations planners must ensure high-output manufacturing plants do not overwhelm localized regional storage.*
- **Sample Business Questions**:
  - *"Show all factories with capacity greater than 1,000 units and the cities where they are located."*
  - *"What is the total manufacturing capacity grouped by geographical region?"*
  - *"Find factories whose output capacity exceeds the storage capacity of their primary connected warehouses."*
- **Operational Requirement**: Must perform numerical aggregation, filtering, and cross-facility capacity comparisons.

#### Class 5: Reverse Logistics & Customer Return Pipelines
*Returns and defective product recalls must be routed to specialized reclamation and repair centers.*
- **Sample Business Questions**:
  - *"What return routes are available from warehouses in the NA region?"*
  - *"List all return records originating from European distribution centers and the reasons for return."*
- **Operational Requirement**: Must traverse dedicated reverse logistics routes connecting customer return staging points back to regional inspection facilities.

---

### 5. Domain Vocabulary & Semantic Mapping

The Copilot must understand the following enterprise terminology:

| User Natural Language Term | Application Concept | Domain Entities / Attributes |
| :--- | :--- | :--- |
| **Plant / Manufacturing Site / Factory** | Production Facility | `Factories` (`FactName`, `Capacity`, `LocId`) |
| **Warehouse / Distribution Center / Depot / DC** | Storage Facility | `Warehouses` (`WhName`, `StorageType`, `LocId`) |
| **City / Hub / Regional Center** | Geographic Location | `Locations` (`City`, `Region` [e.g., `NA`, `EMEA`, `APAC`]) |
| **Shipment / Freight / Transit Leg** | Cargo Movement | `Shipments` (`Mode` [e.g., `Air`, `Ocean`, `Truck`], `Cost`) |
| **Cold Storage / Refrigerated / Temp-Controlled** | Storage Specification | `Warehouses.StorageType = 'Cold'` |
| **Direct Supply Link / Primary Route** | Infrastructure Connection | `(Factories)-[:ShipsTo]->(Warehouses)` |
| **Inter-City Transit Corridor** | Intermodal Route | `(Locations)-[:Route]->(Locations)` |
| **Return Pipeline / Reverse Freight** | Reverse Logistics Link | `(Warehouses)-[:ReturnRoute]->(Locations)` |
