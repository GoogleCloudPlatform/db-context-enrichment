from typing import Any

import yaml

from .base import BaseDBConfigGenerator


class MySQLConfigGenerator(BaseDBConfigGenerator):
    """
    Dedicated generator mapping properties to explicit Cloud SQL MySQL configuration
    topologies utilized by both EvalBench binaries and GDA Context objects.
    """

    SOURCE_TYPE = "cloud-sql-mysql"
    DIALECT = "mysql"
    REQUIRED_FIELDS = BaseDBConfigGenerator.REQUIRED_FIELDS | {
        "project",
        "region",
        "instance",
        "database",
    }

    def __init__(self, params: dict[str, Any]):
        super().__init__(params)
        self.project = params.get("project")
        self.region = params.get("region")
        self.instance = params.get("instance")
        self.database = params.get("database")
        self.user = params.get("user")
        self.password = params.get("password")

    def generate_db_config(self) -> str:
        db_type = "mysql"
        db_path = f"{self.project}:{self.region}:{self.instance}"

        db_config = {
            "db_type": db_type,
            "dialect": self.DIALECT,
            "database_name": self.database,
            "database_path": db_path,
            "max_executions_per_minute": 180,
        }
        if self.user:
            db_config["user_name"] = self.user
        if self.password:
            db_config["password"] = self.password
        return yaml.safe_dump(
            db_config, sort_keys=False, default_flow_style=False
        ).strip()

    def build_datasource_reference(self, context_set_id: str) -> dict[str, Any]:
        ref: dict[str, Any] = {
            "cloud_sql_reference": {
                "database_reference": {
                    "engine": "MYSQL",
                    "project_id": self.project,
                    "region": self.region,
                    "instance_id": self.instance,
                    "database_id": self.database,
                }
            }
        }
        if context_set_id:
            ref["cloud_sql_reference"]["agent_context_reference"] = {
                "context_set_id": context_set_id
            }
        return ref
