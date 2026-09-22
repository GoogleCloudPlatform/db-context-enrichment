import pytest
import yaml

from google.cloud.db_context_enrichment.evaluate.db_generators.custom import (
    CustomDBConfigGenerator,
)


def test_custom_generator_defaults():
    params = {
        "connector_class": "my_pkg.connectors.MyConnector",
        "server": "/custom/path",
        "custom_key": "custom_val",
    }
    gen = CustomDBConfigGenerator(params)

    # Dialect defaults to sql
    assert gen.DIALECT == "sql"

    # db_config generation
    db_config = yaml.safe_load(gen.generate_db_config())
    assert db_config["db_type"] == "custom"
    assert db_config["connector_class"] == "my_pkg.connectors.MyConnector"
    assert db_config["dialect"] == "sql"
    assert db_config["server"] == "/custom/path"
    assert db_config["custom_key"] == "custom_val"

    # model_config generation defaults to query_data_api when generator_class is absent
    model_config = yaml.safe_load(gen.generate_model_config("test-context-id"))
    assert model_config["generator"] == "query_data_api"
    assert model_config["datasource_references"] == []


def test_custom_generator_explicit_dialect():
    params = {
        "connector_class": "my_pkg.connectors.MyConnector",
        "dialect": "googlesql",
    }
    gen = CustomDBConfigGenerator(params)
    assert gen.DIALECT == "googlesql"

    db_config = yaml.safe_load(gen.generate_db_config())
    assert db_config["dialect"] == "googlesql"


def test_custom_generator_with_generator_class():
    params = {
        "generator_class": "my_pkg.generators.MyGenerator",
        "dialect": "postgres",
        "model_temperature": 0.2,
    }
    gen = CustomDBConfigGenerator(params)
    assert gen.DIALECT == "postgres"

    model_config = yaml.safe_load(gen.generate_model_config("test-context-id"))
    assert model_config["generator"] == "custom"
    assert model_config["generator_class"] == "my_pkg.generators.MyGenerator"
    assert model_config["context_set_id"] == "test-context-id"
    assert model_config["model_temperature"] == 0.2


def test_custom_generator_validation_missing_both_classes():
    with pytest.raises(
        ValueError,
        match="Custom source configuration must specify at least 'connector_class' or 'generator_class'",
    ):
        CustomDBConfigGenerator({"dialect": "sql"})


def test_custom_generator_project_resolution_from_google_cloud_project(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "env-project-123")
    monkeypatch.delenv("GCP_PROJECT", raising=False)
    params = {"connector_class": "my_pkg.connectors.MyConnector"}
    gen = CustomDBConfigGenerator(params)
    assert gen.params["project"] == "env-project-123"


def test_custom_generator_project_resolution_from_gcp_project(monkeypatch):
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    monkeypatch.setenv("GCP_PROJECT", "env-gcp-project-456")
    params = {"connector_class": "my_pkg.connectors.MyConnector"}
    gen = CustomDBConfigGenerator(params)
    assert gen.params["project"] == "env-gcp-project-456"


def test_custom_generator_explicit_project_not_overridden(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "env-project-ignored")
    monkeypatch.setenv("GCP_PROJECT", "env-gcp-project-ignored")
    params = {
        "connector_class": "my_pkg.connectors.MyConnector",
        "project": "explicit-project",
    }
    gen = CustomDBConfigGenerator(params)
    assert gen.params["project"] == "explicit-project"
