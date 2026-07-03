import pytest
import yaml

from google.cloud.db_context_enrichment.evaluate.db_generators.firestore import (
    FirestoreConfigGenerator,
)


@pytest.fixture
def mock_params():
    return {
        "project": "cloud-db-nl2sql",
        "database": "nl2sql-mflix",
        "endpoint": "test-firestore.sandbox.googleapis.com",
    }


def test_generate_db_config(mock_params):
    gen = FirestoreConfigGenerator(mock_params)
    db_config_yaml = gen.generate_db_config()

    assert gen.DIALECT == "mongodb"

    config = yaml.safe_load(db_config_yaml)
    assert config == {
        "db_type": "mongodb",
        "dialect": "mongodb",
        "database_name": "nl2sql-mflix",
        "database_path": "",
        "max_executions_per_minute": 120,
    }


def test_generate_model_config(mock_params):
    gen = FirestoreConfigGenerator(mock_params)
    model_config_yaml = gen.generate_model_config(
        "projects/cloud-db-nl2sql/locations/us-central1/contextSets/mflix-context"
    )
    m_config = yaml.safe_load(model_config_yaml)

    assert m_config == {
        "generator": "query_data_api",
        "project_id": "cloud-db-nl2sql",
        "location": "global",
        "context": {
            "datasource_references": {
                "firestore_reference": {

                    "database_reference": {
                        "project_id": "cloud-db-nl2sql",
                        "database_id": "nl2sql-mflix",
                    },
                    "agent_context_reference": {
                        "context_set_id": "projects/cloud-db-nl2sql/locations/us-central1/contextSets/mflix-context"
                    },
                }
            }
        },
    }
