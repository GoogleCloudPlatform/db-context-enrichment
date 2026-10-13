from typing import Any

import yaml

from .base import BaseDBConfigGenerator


class BigQueryConfigGenerator(BaseDBConfigGenerator):
    """
    Dedicated generator mapping properties to explicit BigQuery configuration
    topologies utilized by both EvalBench binaries and GDA Context objects.
    """

    SOURCE_TYPE = "bigquery"
    DIALECT = "googlesql"
    # The toolbox BigQuery source has no `dataset` field; the target dataset is
    # declared via `allowedDatasets`, which must contain exactly one entry.
    REQUIRED_FIELDS = BaseDBConfigGenerator.REQUIRED_FIELDS | {
        "project",
        "allowedDatasets",
    }

    def __init__(self, params: dict[str, Any]):
        super().__init__(params)
        self.project = params.get("project")
        self.dataset = self._resolve_dataset(params.get("allowedDatasets"))
        # BigQuery dataset location (e.g. "US", "EU", "us-central1"), used only
        # by EvalBench to execute queries. It is intentionally NOT used as the
        # GDA API location in the model config: multi-regions like "US" are not
        # valid GDA locations, so the model config uses "global".
        self.location = params.get("location")
        # Table scope comes from `Table Ids` in the experiment's experiment_state.md
        # (tools.yaml has no place for it); the GDA API requires at least one table reference.
        self.tables = params.get("tables") or []

    @staticmethod
    def _resolve_dataset(allowed_datasets: Any) -> str:
        if isinstance(allowed_datasets, str):
            allowed_datasets = [allowed_datasets]
        if (
            not isinstance(allowed_datasets, list)
            or len(allowed_datasets) != 1
            or not isinstance(allowed_datasets[0], str)
        ):
            raise ValueError(
                "BigQuery source 'allowedDatasets' must list exactly one dataset "
                f"for evaluation, got: {allowed_datasets!r}"
            )
        # allowedDatasets entries may be `dataset` or `project.dataset`.
        return allowed_datasets[0].split(".")[-1]

    def generate_db_config(self) -> str:
        db_type = "bigquery"
        db_path = f"projects/{self.project}/datasets/{self.dataset}"

        db_config = {
            "db_type": db_type,
            "dialect": self.DIALECT,
            "database_name": self.dataset,
            "database_path": db_path,
            "gcp_project_id": self.project,
            "max_executions_per_minute": 100,
        }
        if self.location:
            db_config["location"] = self.location
        return yaml.safe_dump(
            db_config, sort_keys=False, default_flow_style=False
        ).strip()

    def build_datasource_reference(self, context_set_id: str) -> dict[str, Any]:
        if not self.tables:
            raise ValueError(
                "No BigQuery tables in scope: set `Table Ids` under "
                "`## Active Database` in the experiment's experiment_state.md "
                "(e.g. `- **Table Ids**: [orders, customers]`). "
                "The QueryData API requires at least one table reference."
            )
        table_references = [
            {
                "project_id": self.project,
                "dataset_id": self.dataset,
                "table_id": table_id,
            }
            for table_id in self.tables
        ]

        bq_ref: dict[str, Any] = {"table_references": table_references}
        if context_set_id:
            bq_ref["agent_context_reference"] = {"context_set_id": context_set_id}
        return {"bq": bq_ref}
