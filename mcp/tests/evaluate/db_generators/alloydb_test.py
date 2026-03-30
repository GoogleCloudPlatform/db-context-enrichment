import pytest
import yaml
from evaluate.db_generators.alloydb import AlloyDBGenerator

@pytest.fixture
def mock_params():
    return {
        "project": "test-project",
        "region": "us-west1",
        "cluster": "test-cluster",
        "instance": "test-instance",
        "database": "test-db",
        "user": "test-user",
        "password": "test-password"
    }

def test_generate_db_config(mock_params):
    gen = AlloyDBGenerator(mock_params)
    db_config_yaml = gen.generate_db_config()
    
    assert gen.DIALECT == "postgres"
    
    config = yaml.safe_load(db_config_yaml)
    assert config == {
        "db_type": "alloydb",
        "dialect": "postgres",
        "database_name": "test-db",
        "database_path": "projects/test-project/locations/us-west1/clusters/test-cluster/instances/test-instance",
        "max_executions_per_minute": 180,
        "user_name": "test-user",
        "password": "test-password",
        "nl_config": ""
    }

def test_generate_model_config(mock_params):
    gen = AlloyDBGenerator(mock_params)
    model_config_yaml = gen.generate_model_config("projects/test-project/locations/us-west1/contextSets/my-context")
    m_config = yaml.safe_load(model_config_yaml)
    
    assert m_config == {
        "generator": "query_data_api",
        "project_id": "test-project",
        "location": "us-west1",
        "context": {
            "datasource_references": {
                "alloydb": {
                    "database_reference": {
                        "project_id": "test-project",
                        "region": "us-west1",
                        "cluster_id": "test-cluster",
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
