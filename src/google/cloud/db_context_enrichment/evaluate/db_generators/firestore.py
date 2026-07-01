from typing import Any

import google.cloud.geminidataanalytics_v1beta as gda
import yaml

from .base import BaseDBConfigGenerator


class FirestoreConfigGenerator(BaseDBConfigGenerator):
    """
    Dedicated generator mapping properties to Firestore (MongoDB query dialect)
    topologies utilized by both EvalBench binaries and GDA Context objects.
    """

    SOURCE_TYPE = "firestore-mongodb"
    DIALECT = "mongodb"
    REQUIRED_FIELDS = BaseDBConfigGenerator.REQUIRED_FIELDS | {
        "project",
        "database",
    }

    def __init__(self, params: dict[str, Any]):
        super().__init__(params)
        self.project = params.get("project")
        self.database = params.get("database", "nl2sql-mflix")
        self.connection_string = params.get("connection_string")

    def generate_db_config(self) -> str:
        db_type = "mongodb"

        db_config = {
            "db_type": db_type,
            "dialect": self.DIALECT,
            "database_name": self.database,
            "database_path": "",
            "max_executions_per_minute": 120,
        }
        if self.connection_string:
            db_config["connection_string"] = self.connection_string

        return yaml.safe_dump(
            db_config, sort_keys=False, default_flow_style=False
        ).strip()

    def build_datasource_reference(
        self, context_set_id: str
    ) -> gda.DatasourceReferences:
        return gda.DatasourceReferences()

    def build_custom_query_context(self, context_set_id: str) -> dict[str, Any]:
        return {
            "datasource_references": {
                "firestore": {
                    "database_reference": {
                        "project_id": self.project,
                        "database_id": self.database,
                    },
                    "agent_context_reference": {
                        "context_set_id": context_set_id
                    },
                }
            }
        }

