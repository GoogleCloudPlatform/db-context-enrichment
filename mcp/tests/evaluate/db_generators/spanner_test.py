import pytest
import yaml
from evaluate.db_generators.spanner import SpannerGenerator

@pytest.fixture
def mock_params():
    return {
        "project": "test-project",
        "instance": "test-instance",
        "database": "test-db",
    }

def test_generate_db_config(mock_params):
    gen = SpannerGenerator(mock_params)
    db_config_yaml = gen.generate_db_config()
    
    assert gen.DIALECT == "spanner_gsql"
    
    config = yaml.safe_load(db_config_yaml)
    assert config == {
        "db_type": "spanner",
        "dialect": "spanner_gsql",
        "database_name": "test-db",
        "database_path": "projects/test-project/instances/test-instance/databases/test-db",
        "instance_id": "test-instance",
        "gcp_project_id": "test-project",
        "max_executions_per_minute": 100
    }

def test_generate_model_config(mock_params):
    gen = SpannerGenerator(mock_params)
    model_config_yaml = gen.generate_model_config("projects/test-project/locations/us-west1/contextSets/my-context")
    m_config = yaml.safe_load(model_config_yaml)
    
    assert m_config == {
        "generator": "query_data_api",
        "project_id": "test-project",
        "location": "global",
        "context": {
            "datasource_references": {
                "spanner_reference": {
                    "database_reference": {
                        "engine": "GOOGLE_SQL",
                        "project_id": "test-project",
                        "instance_id": "test-instance",
                        "database_id": "test-db"
                    },
                    "agent_context_reference": {
                        "context_set_id": "projects/test-project/locations/us-west1/contextSets/my-context"
                    }
                }
            }
        }
    }
