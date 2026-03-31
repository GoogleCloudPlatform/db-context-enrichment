import json
import pytest
import textwrap
from unittest.mock import patch, mock_open

from evaluate.evaluate_generator import generate_evalbench_configs
from evaluate.db_generators.postgres import PostgresConfigGenerator

@pytest.fixture
def valid_postgres_params():
    return {
        "type": "cloud-sql-postgres",
        "project": "test-project",
        "region": "us-central1",
        "instance": "test-instance",
        "database": "test-db",
        "user": "test-user",
        "password": "test-password"
    }

def test_generate_evalbench_configs_file_not_found():
    with pytest.raises(ValueError, match="Config file not found"):
        generate_evalbench_configs("exp", "path", "ctx", "/nonexistent/tools.yaml", "any-name")


def test_generate_evalbench_configs_missing_source():
    mock_yaml = """
    kind: source
    name: other-source
    type: postgres
    """
    with patch("builtins.open", mock_open(read_data=mock_yaml)):
        with pytest.raises(ValueError, match="Could not find a 'kind: source' named 'test-source'"):
            generate_evalbench_configs("exp", "path", "ctx", "/fake/tools.yaml", "test-source")


def test_generate_evalbench_configs_missing_type():
    mock_yaml = """
    kind: source
    name: test-source
    # missing type
    """
    with patch("builtins.open", mock_open(read_data=mock_yaml)):
        with pytest.raises(ValueError, match="is missing the 'type' field"):
            generate_evalbench_configs("exp", "path", "ctx", "/fake/tools.yaml", "test-source")


def test_generate_evalbench_configs_unsupported_type():
    mock_yaml = """
    kind: source
    name: test-source
    type: unknown-db
    """
    with patch("builtins.open", mock_open(read_data=mock_yaml)):
        with pytest.raises(ValueError, match="Unsupported evaluating toolbox source type: 'unknown-db'"):
            generate_evalbench_configs("exp", "path", "ctx", "/fake/tools.yaml", "test-source")


def test_generate_evalbench_configs():
    mock_yaml = textwrap.dedent("""\
        ---
        kind: tool
        name: list_tables
        ---
        kind: source
        name: other-source
        type: cloud-sql-mysql
        project: other-project
        region: us-central1
        instance: other-instance
        database: other-db
        user: other-user
        password: other-password
        ---
        kind: source
        name: test-source
        type: cloud-sql-postgres
        project: test-project
        region: us-central1
        instance: test-instance
        database: test-db
        user: test-user
        password: test-password
    """).strip()
    
    with patch("builtins.open", mock_open(read_data=mock_yaml)):
        configs = generate_evalbench_configs(
            experiment_name="test-exp",
            dataset_path="/local/path/data.json",
            context_set_id="context-123",
            toolbox_config_path="/fake/tools.yaml",
            toolbox_source_name="test-source"
        )
    
    assert set(configs.keys()) == {"db_config.yaml", "model_config.yaml", "run_config.yaml"}
    
    expected_db_config = textwrap.dedent("""\
        db_type: postgres
        dialect: postgres
        database_name: test-db
        database_path: test-project:us-central1:test-instance
        max_executions_per_minute: 180
        user_name: test-user
        password: test-password
    """).strip()
    
    expected_model_config = textwrap.dedent("""\
        generator: query_data_api
        project_id: test-project
        location: us-central1
        context:
          datasource_references:
            cloud_sql_reference:
              database_reference:
                engine: POSTGRESQL
                project_id: test-project
                region: us-central1
                instance_id: test-instance
                database_id: test-db
              agent_context_reference:
                context_set_id: context-123
    """).strip()
    
    expected_run_config = textwrap.dedent("""\
        ############################################################
        ### Dataset / Eval Items
        ############################################################
        dataset_config: /local/path/data.json
        dataset_format: evalbench-standard-format
        database_configs:
         - experiments/test-exp/eval_configs/db_config.yaml
        dialect: postgres    # DB connection mapping
        query_types:
         - dql

        ############################################################
        ### Prompt and Generation Modules
        ############################################################
        model_config: experiments/test-exp/eval_configs/model_config.yaml
        prompt_generator: 'NOOPGenerator'

        ############################################################
        ### Scorer Related Configs
        ############################################################
        scorers:
          exact_match: null
          executable_sql: null

        ############################################################
        ### Reporting Related Configs
        ############################################################
        reporting:
          csv:
            output_directory: 'experiments/test-exp/eval_reports/'
    """).strip()
    
    assert configs["db_config.yaml"] == expected_db_config
    assert configs["model_config.yaml"] == expected_model_config
    assert configs["run_config.yaml"] == expected_run_config


def test_generate_evalbench_configs_env_interpolation():
    mock_yaml = textwrap.dedent("""\
        kind: source
        name: test-source
        type: cloud-sql-postgres
        project: ${TEST_PROJECT}
        region: us-central1
        instance: test-instance
        database: test-db
        user: test-user
        password: test-password
    """).strip()
    
    with patch.dict("os.environ", {"TEST_PROJECT": "env-project"}):
        with patch("builtins.open", mock_open(read_data=mock_yaml)):
            configs = generate_evalbench_configs(
                experiment_name="test-exp",
                dataset_path="/local/path/data.json",
                context_set_id="context-123",
                toolbox_config_path="/fake/tools.yaml",
                toolbox_source_name="test-source"
            )
            
    # assert the project was interpolated
    assert "env-project" in configs["db_config.yaml"]


def test_generate_evalbench_configs_env_fallback():
    mock_yaml = textwrap.dedent("""\
        kind: source
        name: test-source
        type: cloud-sql-postgres
        project: ${TEST_PROJECT:fallback-project}
        region: us-central1
        instance: test-instance
        database: test-db
        user: test-user
        password: test-password
    """).strip()
    
    with patch.dict("os.environ", {}):  # Ensure empty
        with patch("builtins.open", mock_open(read_data=mock_yaml)):
            configs = generate_evalbench_configs(
                experiment_name="test-exp",
                dataset_path="/local/path/data.json",
                context_set_id="context-123",
                toolbox_config_path="/fake/tools.yaml",
                toolbox_source_name="test-source"
            )
            
    assert "fallback-project" in configs["db_config.yaml"]


def test_generate_evalbench_configs_env_missing():
    mock_yaml = textwrap.dedent("""\
        kind: source
        name: test-source
        type: cloud-sql-postgres
        project: ${MISSING_PROJECT}
        region: us-central1
        instance: test-instance
        database: test-db
        user: test-user
        password: test-password
    """).strip()
    
    with patch.dict("os.environ", {}):
        with patch("builtins.open", mock_open(read_data=mock_yaml)):
            with pytest.raises(ValueError, match="Environment variable 'MISSING_PROJECT' not found and no default provided."):
                generate_evalbench_configs("exp", "path", "ctx", "/fake/tools.yaml", "test-source")
