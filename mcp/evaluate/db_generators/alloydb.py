from typing import Tuple, Dict, Any
import textwrap
import google.cloud.geminidataanalytics_v1beta as gda
from .base import BaseDBConfigGenerator

class AlloyDBConfigGenerator(BaseDBConfigGenerator):
    """
    Dedicated generator mapping properties to explicit AlloyDB configuration
    topologies utilized by both EvalBench binaries and GDA Context objects.
    """
    SOURCE_TYPE = "alloydb-postgres"
    DIALECT = "postgres"
    REQUIRED_FIELDS = BaseDBConfigGenerator.REQUIRED_FIELDS | {
        "project", "region", "cluster", "instance", "database", "user", "password"
    }
    
    def __init__(self, params: Dict[str, Any]):
        super().__init__(params)
        self.project = params.get("project")
        self.region = params.get("region")
        self.cluster = params.get("cluster")
        self.instance = params.get("instance")
        self.database = params.get("database")
        self.user = params.get("user")
        self.password = params.get("password")
    
    def generate_db_config(self) -> str:
        db_type = "alloydb"
        db_path = f"projects/{self.project}/locations/{self.region}/clusters/{self.cluster}/instances/{self.instance}"
        
        db_config_yaml = textwrap.dedent(f"""\
            db_type: {db_type}
            dialect: {self.DIALECT}
            database_name: {self.database}
            database_path: {db_path}
            max_executions_per_minute: 180
            user_name: {self.user}
            password: {self.password}
            nl_config: '' # Required by evalbench schema
        """)
        return db_config_yaml.strip()

    def build_datasource_reference(self, context_set_id: str) -> gda.DatasourceReferences:
        datasource_ref = gda.DatasourceReferences()
        
        datasource_ref.alloydb = gda.AlloyDbReference(
            database_reference=gda.AlloyDbDatabaseReference(
                project_id=self.project,
                region=self.region,
                cluster_id=self.cluster,
                instance_id=self.instance,
                database_id=self.database
            ),
            agent_context_reference=gda.AgentContextReference(
                context_set_id=context_set_id
            )
        )
        return datasource_ref
