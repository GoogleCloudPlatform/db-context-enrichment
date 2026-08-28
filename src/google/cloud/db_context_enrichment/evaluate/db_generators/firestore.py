from typing import Any

import yaml

from .base import BaseDBConfigGenerator


class FirestoreConfigGenerator(BaseDBConfigGenerator):
    """
    Dedicated generator mapping properties to Firestore (MongoDB query dialect)
    topologies utilized by both EvalBench binaries and GDA REST API.
    """

    SOURCE_TYPE = "firestore"
    DIALECT = "mongodb"
    REQUIRED_FIELDS = BaseDBConfigGenerator.REQUIRED_FIELDS | {
        "project",
    }

    def __init__(self, params: dict[str, Any]):
        super().__init__(params)
        self.project = params.get("project")
        self.database = params.get("database") or "(default)"
        self.connection_string = params.get("connection_string")
        self.collection_ids = params.get("collection_ids") or params.get("table_ids")

    def generate_db_config(self) -> str:
        db_type = "mongodb"

        db_config = {
            "db_type": db_type,
            "dialect": self.DIALECT,
            "database_name": self.database,
            "database_path": "",
            "firestore_database": f"projects/{self.project}/databases/{self.database}",
            "max_executions_per_minute": 120,
        }
        if self.connection_string:
            db_config["connection_string"] = self.connection_string

        return yaml.safe_dump(
            db_config, sort_keys=False, default_flow_style=False
        ).strip()

    def build_datasource_reference(self, context_set_id: str) -> dict[str, Any]:
        db_ref: dict[str, Any] = {
            "project_id": self.project,
            "database_id": self.database,
        }
        if self.collection_ids:
            db_ref["collection_ids"] = self.collection_ids

        ref: dict[str, Any] = {"firestore_reference": {"database_reference": db_ref}}
        if context_set_id:
            ref["firestore_reference"]["agent_context_reference"] = {
                "context_set_id": context_set_id
            }

        return ref
