from typing import Tuple, Dict, Any
import textwrap

import google.cloud.geminidataanalytics_v1beta as gda
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
        "project", "region", "instance", "database"
    }
    
    def __init__(self, params: Dict[str, Any]):
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
        return yaml.safe_dump(db_config, sort_keys=False, default_flow_style=False).strip()

    def build_datasource_reference(self, context_set_id: str) -> gda.DatasourceReferences:
        datasource_ref = gda.DatasourceReferences()
        
        datasource_ref.cloud_sql_reference = gda.CloudSqlReference(
            database_reference=gda.CloudSqlDatabaseReference(
                engine=gda.CloudSqlDatabaseReference.Engine.MYSQL,
                project_id=self.project,
                region=self.region,
                instance_id=self.instance,
                database_id=self.database
            ),
            agent_context_reference=gda.AgentContextReference(
                context_set_id=context_set_id
            )
        )
        return datasource_ref
