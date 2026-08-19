import pytest
import yaml

from google.cloud.db_context_enrichment.evaluate.db_generators.bigtable import (
    BigtableConfigGenerator,
)


@pytest.fixture
def mock_params():
    return {
        "project": "test-project",
        "instance": "test-instance",
    }


def test_generate_db_config(mock_params):
    gen = BigtableConfigGenerator(mock_params)
    db_config_yaml = gen.generate_db_config()

    assert gen.DIALECT == "bigtable"

    config = yaml.safe_load(db_config_yaml)
    assert config == {
        "db_type": "bigtable",
        "dialect": "bigtable",
        "database_name": "test-instance",
        "database_path": "projects/test-project/instances/test-instance",
        "instance_id": "test-instance",
        "gcp_project_id": "test-project",
        "max_executions_per_minute": 100,
    }


def test_generate_model_config(mock_params):
    gen = BigtableConfigGenerator(mock_params)
    model_config_yaml = gen.generate_model_config(
        "projects/test-project/locations/global/contextSets/my-context"
    )
    m_config = yaml.safe_load(model_config_yaml)

    assert m_config == {
        "generator": "query_data_api",
        "project_id": "test-project",
        "location": "global",
        "use_rest_api": True,
        "context": {
            "datasource_references": {
                "bigtable_reference": {
                    "database_reference": {
                        "project_id": "test-project",
                        "instance_id": "test-instance",
                    },
                    "agent_context_reference": {
                        "context_set_id": "projects/test-project/locations/global/contextSets/my-context"
                    },
                }
            }
        },
    }


def test_build_datasource_reference_success(mock_params):
    gen = BigtableConfigGenerator(mock_params)
    ref = gen.build_datasource_reference(
        "projects/test-project/locations/global/contextSets/my-context"
    )
    assert ref == {
        "bigtable_reference": {
            "database_reference": {
                "project_id": "test-project",
                "instance_id": "test-instance",
            },
            "agent_context_reference": {
                "context_set_id": "projects/test-project/locations/global/contextSets/my-context"
            },
        }
    }


def test_bigtable_generator_validation_missing_fields():
    bad_params = {"project": "test-project"}
    with pytest.raises(
        ValueError,
        match="Missing required fields in tools.yaml config for 'bigtable': instance",
    ):
        BigtableConfigGenerator(bad_params)


def test_bigtable_generator_validation_missing_project():
    bad_params = {"instance": "test-instance"}
    with pytest.raises(
        ValueError,
        match="Missing required fields in tools.yaml config for 'bigtable': project",
    ):
        BigtableConfigGenerator(bad_params)


def test_bigtable_generator_validation_none_values():
    params = {"project": None, "instance": "test-instance"}
    gen = BigtableConfigGenerator(params)
    db_config_yaml = gen.generate_db_config()
    db_config = yaml.safe_load(db_config_yaml)
    assert db_config["gcp_project_id"] is None
    assert db_config["database_path"] == "projects/None/instances/test-instance"

    model_config_yaml = gen.generate_model_config("context-123")
    model_config = yaml.safe_load(model_config_yaml)
    assert (
        model_config["context"]["datasource_references"]["bigtable_reference"][
            "database_reference"
        ]["project_id"]
        is None
    )


def test_bigtable_generator_validation_empty_values():
    params = {"project": "", "instance": ""}
    gen = BigtableConfigGenerator(params)
    db_config_yaml = gen.generate_db_config()
    db_config = yaml.safe_load(db_config_yaml)
    assert db_config["gcp_project_id"] == ""
    assert db_config["database_path"] == "projects//instances/"


def test_bigtable_generator_validation_invalid_types():
    params = {"project": 12345, "instance": 67890}
    gen = BigtableConfigGenerator(params)
    db_config_yaml = gen.generate_db_config()
    db_config = yaml.safe_load(db_config_yaml)
    assert db_config["gcp_project_id"] == 12345
    assert db_config["database_path"] == "projects/12345/instances/67890"


def test_bigtable_generator_extra_parameters():
    params = {
        "project": "test-project",
        "instance": "test-instance",
        "extra_field": "ignored-value",
        "nested": {"key": "val"},
    }
    gen = BigtableConfigGenerator(params)
    db_config_yaml = gen.generate_db_config()
    db_config = yaml.safe_load(db_config_yaml)
    assert "extra_field" not in db_config
    assert "nested" not in db_config


def test_bigtable_generator_special_characters():
    params = {
        "project": "project:name:with:colons",
        "instance": "instance#with#special/chars",
    }
    gen = BigtableConfigGenerator(params)
    db_config_yaml = gen.generate_db_config()
    db_config = yaml.safe_load(db_config_yaml)
    assert db_config["gcp_project_id"] == "project:name:with:colons"
    assert (
        db_config["database_path"]
        == "projects/project:name:with:colons/instances/instance#with#special/chars"
    )
