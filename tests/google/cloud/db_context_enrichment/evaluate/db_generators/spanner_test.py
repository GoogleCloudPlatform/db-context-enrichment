import pytest
import yaml

from google.cloud.db_context_enrichment.evaluate.db_generators.spanner import (
    SpannerConfigGenerator,
)


@pytest.fixture
def mock_params():
    return {
        "project": "test-project",
        "instance": "test-instance",
        "database": "test-db",
    }


def test_generate_db_config(mock_params):
    gen = SpannerConfigGenerator(mock_params)
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
        "max_executions_per_minute": 100,
    }


def test_generate_model_config(mock_params):
    gen = SpannerConfigGenerator(mock_params)
    model_config_yaml = gen.generate_model_config(
        "projects/test-project/locations/us-west1/contextSets/my-context"
    )
    m_config = yaml.safe_load(model_config_yaml)

    assert m_config == {
        "generator": "query_data_api",
        "project_id": "test-project",
        "location": "global",
        "use_rest_api": True,
        "context": {
            "datasource_references": {
                "spanner_reference": {
                    "database_reference": {
                        "engine": "GOOGLE_SQL",
                        "project_id": "test-project",
                        "instance_id": "test-instance",
                        "database_id": "test-db",
                    },
                    "agent_context_reference": {
                        "context_set_id": "projects/test-project/locations/us-west1/contextSets/my-context"
                    },
                }
            }
        },
    }


def test_generate_model_config_with_graph(mock_params):
    mock_params["graph_ids"] = ["ResearchGraph"]
    gen = SpannerConfigGenerator(mock_params)
    model_config_yaml = gen.generate_model_config(
        "projects/test-project/locations/us-west1/contextSets/my-context"
    )
    m_config = yaml.safe_load(model_config_yaml)

    assert m_config == {
        "generator": "query_data_api",
        "project_id": "test-project",
        "location": "global",
        "use_rest_api": True,
        "context": {
            "datasource_references": {
                "spanner_reference": {
                    "database_reference": {
                        "engine": "GOOGLE_SQL",
                        "project_id": "test-project",
                        "instance_id": "test-instance",
                        "database_id": "test-db",
                        "graph_ids": ["ResearchGraph"],
                    },
                    "agent_context_reference": {
                        "context_set_id": "projects/test-project/locations/us-west1/contextSets/my-context"
                    },
                }
            }
        },
    }


def test_generate_model_config_with_graph_list(mock_params):
    mock_params["graph_ids"] = ["ResearchGraph", "LogisticsNet"]
    gen = SpannerConfigGenerator(mock_params)
    model_config_yaml = gen.generate_model_config(
        "projects/test-project/locations/us-west1/contextSets/my-context"
    )
    m_config = yaml.safe_load(model_config_yaml)

    assert m_config["context"]["datasource_references"]["spanner_reference"][
        "database_reference"
    ]["graph_ids"] == ["ResearchGraph", "LogisticsNet"]


def test_generate_model_config_invalid_graph_ids(mock_params):
    mock_params["graph_ids"] = "not-a-list"
    gen = SpannerConfigGenerator(mock_params)
    with pytest.raises(ValueError, match="graph_ids must be a list of strings"):
        gen.generate_model_config(
            "projects/test-project/locations/us-west1/contextSets/my-context"
        )

    mock_params["graph_ids"] = [123]
    gen = SpannerConfigGenerator(mock_params)
    with pytest.raises(ValueError, match="graph_ids must be a list of strings"):
        gen.generate_model_config(
            "projects/test-project/locations/us-west1/contextSets/my-context"
        )


def test_generate_db_config_postgres(mock_params):
    mock_params["dialect"] = "POSTGRESQL"
    gen = SpannerConfigGenerator(mock_params)
    db_config_yaml = gen.generate_db_config()

    assert gen.DIALECT == "spanner_pg"
    assert gen.engine == "POSTGRESQL"

    config = yaml.safe_load(db_config_yaml)
    assert config == {
        "db_type": "spanner",
        "dialect": "spanner_pg",
        "database_name": "test-db",
        "database_path": "projects/test-project/instances/test-instance/databases/test-db",
        "instance_id": "test-instance",
        "gcp_project_id": "test-project",
        "max_executions_per_minute": 100,
    }


def test_generate_model_config_postgres(mock_params):
    mock_params["engine"] = "POSTGRESQL"
    gen = SpannerConfigGenerator(mock_params)
    model_config_yaml = gen.generate_model_config(
        "projects/test-project/locations/us-west1/contextSets/my-context"
    )
    m_config = yaml.safe_load(model_config_yaml)

    assert m_config == {
        "generator": "query_data_api",
        "project_id": "test-project",
        "location": "global",
        "use_rest_api": True,
        "context": {
            "datasource_references": {
                "spanner_reference": {
                    "database_reference": {
                        "engine": "POSTGRESQL",
                        "project_id": "test-project",
                        "instance_id": "test-instance",
                        "database_id": "test-db",
                    },
                    "agent_context_reference": {
                        "context_set_id": "projects/test-project/locations/us-west1/contextSets/my-context"
                    },
                }
            }
        },
    }


@pytest.mark.parametrize(
    "dialect_input",
    [
        "postgresql",
        "POSTGRESQL",
        "spanner_pg",
        "postgres",
        "pg",
        "spanner-postgres",
        "spanner_postgres",
    ],
)
def test_postgres_aliases_and_case_insensitive(mock_params, dialect_input):
    mock_params["dialect"] = dialect_input
    gen = SpannerConfigGenerator(mock_params)
    assert gen.DIALECT == "spanner_pg"
    assert gen.engine == "POSTGRESQL"


def test_postgres_disallows_graph_ids(mock_params):
    mock_params["dialect"] = "POSTGRESQL"
    mock_params["graph_ids"] = ["ResearchGraph"]
    gen = SpannerConfigGenerator(mock_params)
    with pytest.raises(
        ValueError, match="graph_ids is not supported for Spanner PostgreSQL dialect"
    ):
        gen.generate_model_config(
            "projects/test-project/locations/us-west1/contextSets/my-context"
        )


def test_unsupported_dialect_raises_error(mock_params):
    mock_params["dialect"] = "oracle"
    with pytest.raises(
        ValueError, match="Unsupported Spanner dialect/engine: 'oracle'"
    ):
        SpannerConfigGenerator(mock_params)


@pytest.mark.parametrize("type_input", ["spanner-postgres", "spanner-pg"])
def test_postgres_fallback_from_type(mock_params, type_input):
    mock_params["type"] = type_input
    mock_params.pop("dialect", None)
    mock_params.pop("engine", None)
    mock_params.pop("database_dialect", None)
    gen = SpannerConfigGenerator(mock_params)
    assert gen.DIALECT == "spanner_pg"
    assert gen.engine == "POSTGRESQL"
