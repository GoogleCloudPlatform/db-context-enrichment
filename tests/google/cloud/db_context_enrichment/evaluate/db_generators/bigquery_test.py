import pytest
import yaml

from google.cloud.db_context_enrichment.evaluate.db_generators.bigquery import (
    BigQueryConfigGenerator,
)


@pytest.fixture
def mock_params():
    return {
        "project": "test-project",
        "dataset": "test-dataset",
    }


def test_generate_db_config(mock_params):
    gen = BigQueryConfigGenerator(mock_params)
    db_config_yaml = gen.generate_db_config()

    assert gen.DIALECT == "googlesql"

    config = yaml.safe_load(db_config_yaml)
    assert config == {
        "db_type": "bigquery",
        "dialect": "googlesql",
        "database_name": "test-dataset",
        "database_path": "projects/test-project/datasets/test-dataset",
        "gcp_project_id": "test-project",
        "max_executions_per_minute": 100,
    }


def test_generate_db_config_with_location(mock_params):
    gen = BigQueryConfigGenerator({**mock_params, "location": "US"})
    config = yaml.safe_load(gen.generate_db_config())
    assert config["location"] == "US"


def test_missing_required_fields():
    with pytest.raises(ValueError, match="dataset"):
        BigQueryConfigGenerator({"project": "test-project"})


def test_generate_model_config(mock_params):
    gen = BigQueryConfigGenerator(mock_params)
    model_config_yaml = gen.generate_model_config(
        "projects/test-project/locations/us-west1/contextSets/my-context"
    )
    m_config = yaml.safe_load(model_config_yaml)

    assert m_config["generator"] == "query_data_api"
    assert m_config["project_id"] == "test-project"
    assert m_config["location"] == "global"
    # The public GDA SDK references BigQuery at table granularity; with no
    # explicit tables configured the reference set is empty but present.
    assert "bq" in m_config["context"]["datasource_references"]


def test_generate_model_config_with_tables(mock_params):
    gen = BigQueryConfigGenerator({**mock_params, "tables": ["t1", "t2"]})
    model_config_yaml = gen.generate_model_config(
        "projects/test-project/locations/us-west1/contextSets/my-context"
    )
    m_config = yaml.safe_load(model_config_yaml)

    table_refs = m_config["context"]["datasource_references"]["bq"][
        "table_references"
    ]
    assert table_refs == [
        {
            "project_id": "test-project",
            "dataset_id": "test-dataset",
            "table_id": "t1",
        },
        {
            "project_id": "test-project",
            "dataset_id": "test-dataset",
            "table_id": "t2",
        },
    ]
