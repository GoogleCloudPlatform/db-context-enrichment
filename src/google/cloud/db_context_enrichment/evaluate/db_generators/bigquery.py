from typing import Any

import google.cloud.geminidataanalytics_v1beta as gda
import yaml

from .base import BaseDBConfigGenerator


class BigQueryConfigGenerator(BaseDBConfigGenerator):
    """
    Dedicated generator mapping properties to explicit BigQuery configuration
    topologies utilized by both EvalBench binaries and GDA Context objects.
    """

    SOURCE_TYPE = "bigquery"
    DIALECT = "googlesql"
    REQUIRED_FIELDS = BaseDBConfigGenerator.REQUIRED_FIELDS | {
        "project",
        "dataset",
    }

    def __init__(self, params: dict[str, Any]):
        super().__init__(params)
        self.project = params.get("project")
        self.dataset = params.get("dataset")
        self.location = params.get("location")
        # Optional explicit table scoping; the public GDA proto references
        # BigQuery at table granularity rather than dataset granularity.
        self.tables = params.get("tables") or []

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

    def build_datasource_reference(
        self, context_set_id: str
    ) -> gda.DatasourceReferences:
        datasource_ref = gda.DatasourceReferences()

        table_references = [
            gda.BigQueryTableReference(
                project_id=self.project,
                dataset_id=self.dataset,
                table_id=table_id,
            )
            for table_id in self.tables
        ]

        bq_references = gda.BigQueryTableReferences(
            table_references=table_references
        )

        # The agent_context_reference field on BigQueryTableReferences is not
        # yet available in the public google-cloud-geminidataanalytics SDK
        # (restricted-visibility rollout; see the Wave2 FR). Attach it
        # dynamically so this generator works with internal SDK builds and
        # degrades gracefully on public ones.
        if "agent_context_reference" in {
            f.name for f in type(bq_references).pb(bq_references).DESCRIPTOR.fields
        }:
            bq_references.agent_context_reference = gda.AgentContextReference(
                context_set_id=context_set_id
            )

        datasource_ref.bq = bq_references
        return datasource_ref
