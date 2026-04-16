from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple
import yaml
import google.cloud.geminidataanalytics_v1beta as gda
from google.protobuf.json_format import MessageToDict

class BaseDBConfigGenerator(ABC):
    """
    Abstract Base Class enforcing the construction contract for Evalbench database topologies.
    Each distinct DB type (Spanner, Postgres, AlloyDB, MySQL) must inherit and implement 
    the mappings required by both the standard EvalBench framework and the GDA SDK model.
    """
    
    SOURCE_TYPE = "unknown"
    DIALECT = "unknown"
    REQUIRED_FIELDS = {"project"}
    
    def __init__(self, params: Dict[str, Any]):
        self.params = params
        self.validate()

    @abstractmethod
    def generate_db_config(self) -> str:
        """
        Generates the Evalbench db_config.yaml payload natively.
        """
        raise NotImplementedError("Subclasses must implement generate_db_config")

    @abstractmethod
    def build_datasource_reference(self, context_set_id: str) -> gda.DatasourceReferences:
        """
        Constructs the strict Protocol Buffer DatasourceReference required by the QueryDataAPI 
        context generation flow.
        """
        raise NotImplementedError("Subclasses must implement build_datasource_reference")

    def validate(self) -> None:
        """
        Validates that the provided autoctx_config.yaml source configuration block contains all 
        the mandatory fields required by the specific Evalbench topology.
        """
        missing = [f for f in self.REQUIRED_FIELDS if f not in self.params]
        if missing:
            raise ValueError(
                f"Missing required fields in autoctx_config.yaml config for '{self.SOURCE_TYPE}': "
                f"{', '.join(missing)}"
            )

    def generate_model_config(self, context_set_id: str) -> str:
        """
        Standardized Model Builder converting the strictly typed GDA object into an EvalBench model dict.
        """
        datasource_ref = self.build_datasource_reference(context_set_id)
        
        query_context = gda.QueryDataContext(
            datasource_references=datasource_ref
        )

        query_context_dict = MessageToDict(
            query_context._pb, 
            preserving_proto_field_name=True
        )

        model_config = {
            "generator": "query_data_api",
            "project_id": self.params.get("project"),
            "location": self.params.get("region") or "global",
            "context": query_context_dict
        }
        
        return yaml.safe_dump(model_config, sort_keys=False, default_flow_style=False).strip()
