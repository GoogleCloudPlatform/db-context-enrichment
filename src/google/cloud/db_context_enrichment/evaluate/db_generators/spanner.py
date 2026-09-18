from typing import Any

import yaml

from .base import BaseDBConfigGenerator


class SpannerConfigGenerator(BaseDBConfigGenerator):
    """
    Dedicated generator mapping properties to explicit Spanner configuration
    topologies utilized by both EvalBench binaries and GDA Context objects.
    Supports both GoogleSQL and PostgreSQL dialects.
    """

    SOURCE_TYPE = "spanner"
    REQUIRED_FIELDS = BaseDBConfigGenerator.REQUIRED_FIELDS | {
        "project",
        "instance",
        "database",
    }

    def __init__(self, params: dict[str, Any]):
        super().__init__(params)
        self.project = params.get("project")
        self.instance = params.get("instance")
        self.database = params.get("database")

        raw_dialect = (
            params.get("dialect")
            or params.get("engine")
            or params.get("database_dialect")
        )
        if not raw_dialect and params.get("type") in ("spanner-postgres", "spanner-pg"):
            raw_dialect = "POSTGRESQL"

        if raw_dialect:
            normalized = str(raw_dialect).strip().lower().replace("-", "_")
            if normalized in (
                "postgresql",
                "postgres",
                "spanner_pg",
                "pg",
                "spanner_postgres",
            ):
                self.engine = "POSTGRESQL"
                self._dialect = "spanner_pg"
            elif normalized in ("google_sql", "googlesql", "spanner_gsql", "gsql"):
                self.engine = "GOOGLE_SQL"
                self._dialect = "spanner_gsql"
            else:
                raise ValueError(
                    f"Unsupported Spanner dialect/engine: '{raw_dialect}'. Must be 'GOOGLE_SQL' or 'POSTGRESQL'."
                )
        else:
            self.engine = "GOOGLE_SQL"
            self._dialect = "spanner_gsql"

    @property
    def DIALECT(self) -> str:
        return self._dialect

    def generate_db_config(self) -> str:
        db_type = "spanner"
        db_path = f"projects/{self.project}/instances/{self.instance}/databases/{self.database}"

        db_config = {
            "db_type": db_type,
            "dialect": self.DIALECT,
            "database_name": self.database,
            "database_path": db_path,
            "instance_id": self.instance,
            "gcp_project_id": self.project,
            "max_executions_per_minute": 100,
        }
        return yaml.safe_dump(
            db_config, sort_keys=False, default_flow_style=False
        ).strip()

    def build_datasource_reference(self, context_set_id: str) -> dict[str, Any]:
        database_ref: dict[str, Any] = {
            "engine": self.engine,
            "project_id": self.project,
            "instance_id": self.instance,
            "database_id": self.database,
        }
        if graph_ids := self.params.get("graph_ids"):
            if self.engine == "POSTGRESQL":
                raise ValueError(
                    "graph_ids is not supported for Spanner PostgreSQL dialect"
                )
            if not isinstance(graph_ids, list) or not all(
                isinstance(g, str) for g in graph_ids
            ):
                raise ValueError("graph_ids must be a list of strings")
            database_ref["graph_ids"] = graph_ids

        spanner_ref: dict[str, Any] = {"database_reference": database_ref}
        if context_set_id:
            spanner_ref["agent_context_reference"] = {"context_set_id": context_set_id}
        return {"spanner_reference": spanner_ref}
