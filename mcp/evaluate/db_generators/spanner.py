from typing import Tuple, Dict, Any
import textwrap
import google.cloud.geminidataanalytics_v1beta as gda
from .base import BaseDBConfigGenerator

class SpannerConfigGenerator(BaseDBConfigGenerator):
    """
    Dedicated generator mapping properties to explicit Spanner configuration
    topologies utilized by both EvalBench binaries and GDA Context objects.
    """
    SOURCE_TYPE = "spanner"
    DIALECT = "spanner_gsql"
    REQUIRED_FIELDS = BaseDBConfigGenerator.REQUIRED_FIELDS | {
        "project", "instance", "database"
    }
    
    def __init__(self, params: Dict[str, Any]):
        super().__init__(params)
        self.project = params.get("project")
        self.instance = params.get("instance")
        self.database = params.get("database")
    
    def generate_db_config(self) -> str:
        db_type = "spanner"
        db_path = f"projects/{self.project}/instances/{self.instance}/databases/{self.database}"
        
        db_config_yaml = textwrap.dedent(f"""\
            db_type: {db_type}
            dialect: {self.DIALECT}
            database_name: {self.database}
            database_path: {db_path}
            instance_id: {self.instance}
            gcp_project_id: {self.project}
            max_executions_per_minute: 100
        """)
        return db_config_yaml.strip()

    def build_datasource_reference(self, context_set_id: str) -> gda.DatasourceReferences:
        datasource_ref = gda.DatasourceReferences()
        
        datasource_ref.spanner_reference = gda.SpannerReference(
            database_reference=gda.SpannerDatabaseReference(
                engine=gda.SpannerDatabaseReference.Engine.GOOGLE_SQL,
                project_id=self.project,
                instance_id=self.instance,
                database_id=self.database
            ),
            agent_context_reference=gda.AgentContextReference(
                context_set_id=context_set_id
            )
        )
        return datasource_ref
