import pytest
import yaml
from evaluate.db_generators.mysql import MySQLConfigGenerator

@pytest.fixture
def mock_params():
    return {
        "project": "test-project",
        "region": "us-west1",
        "instance": "test-instance",
        "database": "test-db",
        "user": "test-user",
        "password": "test-password"
    }

def test_generate_db_config(mock_params):
    gen = MySQLConfigGenerator(mock_params)
    db_config_yaml = gen.generate_db_config()
    
    assert gen.DIALECT == "mysql"
    
    config = yaml.safe_load(db_config_yaml)
    assert config == {
        "db_type": "mysql",
        "dialect": "mysql",
        "database_name": "test-db",
        "database_path": "test-project:us-west1:test-instance",
        "max_executions_per_minute": 180,
        "user_name": "test-user",
        "password": "test-password"
    }

def test_generate_model_config(mock_params):
    gen = MySQLConfigGenerator(mock_params)
    model_config_yaml = gen.generate_model_config("projects/test-project/locations/us-west1/contextSets/my-context")
    m_config = yaml.safe_load(model_config_yaml)
    
    assert m_config == {
        "generator": "query_data_api",
        "project_id": "test-project",
        "location": "us-west1",
        "context": {
            "datasource_references": {
                "cloud_sql_reference": {
                    "database_reference": {
                        "engine": "MYSQL",
                        "project_id": "test-project",
                        "region": "us-west1",
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

def test_generate_db_config_no_credentials():
    params = {
        "project": "test-project",
        "region": "us-west1",
        "instance": "test-instance",
        "database": "test-db"
    }
    gen = MySQLConfigGenerator(params)
    db_config_yaml = gen.generate_db_config()
    
    config = yaml.safe_load(db_config_yaml)
    assert config == {
        "db_type": "mysql",
        "dialect": "mysql",
        "database_name": "test-db",
        "database_path": "test-project:us-west1:test-instance",
        "max_executions_per_minute": 180,
    }
    assert "user_name" not in config
    assert "password" not in config

