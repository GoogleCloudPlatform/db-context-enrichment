# Environment & Context Acquisition Report

## 1. Domain Mapping
- **Product**: Nexis Global Supply Chain Control Tower
- **Domain**: Global Logistics, Supply Chain Resilience, Multimodal Freight, Cold-Chain Management.
- **Key Concepts**:
  - **Factories**: Production facilities with capacity metrics.
  - **Warehouses**: Storage facilities with specialized types (Cold, Dry, Hazardous).
  - **Locations**: Cities and Regions (NA, EMEA, APAC).
  - **Shipments**: Freight movement with transport modes (Air, Ocean, Truck, Rail) and cost.
  - **Routes**: Direct shipping links and inter-city corridors.

## 2. Schema Registry (Inferred from design_doc.md)
### Nodes / Tables
- `Factories` (`FactName`, `Capacity`, `LocId`)
- `Warehouses` (`WhName`, `StorageType`, `LocId`)
- `Locations` (`City`, `Region`)
- `Shipments` (`Mode`, `Cost`) - *Note: Might be a relationship or a table depending on implementation.*

### Edges / Relationships
- `ShipsTo`: `(Factories)-[:ShipsTo]->(Warehouses)`
- `Route`: `(Locations)-[:Route]->(Locations)`
- `ReturnRoute`: `(Warehouses)-[:ReturnRoute]->(Locations)`

## 3. Artifact Registry
- `design_doc.md`: Primary source for requirements and vocabulary.

## 4. Business Rules & Logic
- Perishable goods MUST route through `Cold` storage.
- Disruption triage requires tracing directed paths from source (Factories) to destination (Warehouses).
- Route comparisons involve aggregating `Cost` across `Mode`.
- Reverse logistics uses `ReturnRoute` from `Warehouses` to `Locations`.
