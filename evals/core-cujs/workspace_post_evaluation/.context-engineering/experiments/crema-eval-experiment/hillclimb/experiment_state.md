# Hill-Climbing Experiment: crema-eval-experiment

## Metadata
- Workspace: ./.context-engineering/experiments/crema-eval-experiment/
- Context set id: crema-eval-experiment
- Final Context Set resource: projects/cloud-db-nl2sql/locations/us-central1/contextSets/crema-eval-experiment
- Draft Context Set resource: (none — new context set; iterations upload to the final name)
- Seed Context Set resource: (local file: ./bootstrap_context.json)
- Golden dataset: ./.context-engineering/experiments/crema-eval-experiment/dataset/golden.json (generated)
- Hillclimb dataset: ./.context-engineering/experiments/crema-eval-experiment/dataset/splits/hillclimb.json
- Holdout dataset: ./.context-engineering/experiments/crema-eval-experiment/dataset/splits/holdout.json

## Active Database
- **Config**: ./.context-engineering/tools.yaml
- **Source Name**: my-alloydb
- **Type**: alloydb-postgres
- **Tools**: my-alloydb-list-schemas, my-alloydb-execute-sql
- **Graph Ids**: []

## Iteration Log

### v0 (base)
- Local file: v0/context_set_v0.json
- Upload op: projects/cloud-db-nl2sql/locations/us-central1/operations/operation-crema-eval-v0
- Score: 0.75 (3 / 4)
- Analysis: (baseline — no analysis)
- Eval report: v0/eval/eval_reports/e637c96e-ab21-411b-99a2-47ec808ad968/
- Notes: baseline uploaded from bootstrap_context.json
