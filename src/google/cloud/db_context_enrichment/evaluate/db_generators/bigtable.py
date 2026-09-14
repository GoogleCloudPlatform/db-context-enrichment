from typing import Any

import yaml

from .base import BaseDBConfigGenerator


class BigtableConfigGenerator(BaseDBConfigGenerator):
    """
    Dedicated generator mapping properties to explicit Bigtable configuration
    topologies. Bypasses the GDA Python SDK to construct the model configuration
    directly, as the SDK may lack native BigtableReference definitions.
    """

    SOURCE_TYPE = "bigtable"
    DIALECT = "bigtable"
    REQUIRED_FIELDS = {"project", "instance"}

    def generate_db_config(self) -> str:
        db_config = {
            "db_type": "bigtable",
            "dialect": self.DIALECT,
            "database_name": self.params.get("instance"),
            "database_path": f"projects/{self.params.get('project')}/instances/{self.params.get('instance')}",
            "instance_id": self.params.get("instance"),
            "gcp_project_id": self.params.get("project"),
            "max_executions_per_minute": 100,
        }
        return yaml.safe_dump(
            db_config, sort_keys=False, default_flow_style=False
        ).strip()

    def build_datasource_reference(self, context_set_id: str) -> dict[str, Any]:
        return {
            "bigtable_reference": {
                "database_reference": {
                    "project_id": self.params.get("project"),
                    "instance_id": self.params.get("instance"),
                },
                "agent_context_reference": {
                    "context_set_id": context_set_id,
                },
            }
        }
