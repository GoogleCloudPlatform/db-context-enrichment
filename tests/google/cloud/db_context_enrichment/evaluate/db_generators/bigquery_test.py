import pytest
import yaml

from google.cloud.db_context_enrichment.evaluate.db_generators.bigquery import (
    BigQueryConfigGenerator,
)


@pytest.fixture
def mock_params():
    return {
        "project": "test-project",
        "allowedDatasets": ["test-dataset"],
        "tables": ["t1"],
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
    with pytest.raises(ValueError, match="allowedDatasets"):
        BigQueryConfigGenerator({"project": "test-project"})


@pytest.mark.parametrize(
    "allowed",
    [[], ["ds1", "ds2"], [1], None],
)
def test_allowed_datasets_must_have_exactly_one(mock_params, allowed):
    with pytest.raises(ValueError, match="exactly one dataset"):
        BigQueryConfigGenerator({**mock_params, "allowedDatasets": allowed})


@pytest.mark.parametrize(
    "allowed", ["test-dataset", ["test-dataset"], ["other-project.test-dataset"]]
)
def test_allowed_datasets_forms(mock_params, allowed):
    gen = BigQueryConfigGenerator({**mock_params, "allowedDatasets": allowed})
    assert gen.dataset == "test-dataset"


def test_model_config_requires_tables(mock_params):
    gen = BigQueryConfigGenerator({**mock_params, "tables": []})
    with pytest.raises(ValueError, match="Table Ids"):
        gen.generate_model_config("ctx")


def test_generate_model_config(mock_params):
    gen = BigQueryConfigGenerator(mock_params)
    model_config_yaml = gen.generate_model_config(
        "projects/test-project/locations/us-west1/contextSets/my-context"
    )
    m_config = yaml.safe_load(model_config_yaml)

    assert m_config["generator"] == "query_data_api"
    assert m_config["project_id"] == "test-project"
    assert m_config["location"] == "global"
    assert m_config["context"]["datasource_references"]["bq"]["table_references"] == [
        {"project_id": "test-project", "dataset_id": "test-dataset", "table_id": "t1"}
    ]


def test_model_config_location_ignores_dataset_location(mock_params):
    # The BigQuery dataset location only applies to db_config; the GDA
    # location stays "global".
    gen = BigQueryConfigGenerator({**mock_params, "location": "US"})
    m_config = yaml.safe_load(gen.generate_model_config("ctx"))
    assert m_config["location"] == "global"


def test_generate_model_config_with_tables(mock_params):
    gen = BigQueryConfigGenerator({**mock_params, "tables": ["t1", "t2"]})
    model_config_yaml = gen.generate_model_config(
        "projects/test-project/locations/us-west1/contextSets/my-context"
    )
    m_config = yaml.safe_load(model_config_yaml)

    table_refs = m_config["context"]["datasource_references"]["bq"]["table_references"]
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
