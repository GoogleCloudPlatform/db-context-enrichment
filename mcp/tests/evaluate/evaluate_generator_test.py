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
    
    with patch("builtins.open", mock_open(read_data=mock_yaml)) as m:
        with patch("evaluate.evaluate_generator._convert_dataset", return_value='[{"mock": "data"}]'):
            with patch("evaluate.evaluate_generator.os.makedirs") as mock_makedirs:
                configs = generate_evalbench_configs(
                    experiment_name="test-exp",
                    dataset_path="/local/path/data.json",
                    context_set_id="context-123",
                    toolbox_config_path="/fake/tools.yaml",
                    toolbox_source_name="test-source"
                )
    
    assert configs is None
    mock_makedirs.assert_called_once_with("autoctx/experiments/test-exp/eval_configs", exist_ok=True)
    
    # Verify all file writes
    m.assert_any_call("autoctx/experiments/test-exp/eval_configs/db_config.yaml", "w")
    m.assert_any_call("autoctx/experiments/test-exp/eval_configs/model_config.yaml", "w")
    m.assert_any_call("autoctx/experiments/test-exp/eval_configs/run_config.yaml", "w")
    m.assert_any_call("autoctx/experiments/test-exp/eval_configs/llmrater_config.yaml", "w")
    m.assert_any_call("autoctx/experiments/test-exp/eval_configs/golden_queries.json", "w")
    
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

    expected_llmrater_config = textwrap.dedent("""\
        generator: gcp_vertex_gemini
        vertex_model: gemini-2.5-flash
        gcp_project_id: test-project
        gcp_region: global
        base_prompt: ""
        execs_per_minute: 20
    """).strip()
    
    expected_run_config = textwrap.dedent("""\
        ############################################################
        ### Dataset / Eval Items
        ############################################################
        dataset_config: autoctx/experiments/test-exp/eval_configs/golden_queries.json
        dataset_format: evalbench-standard-format
        database_configs:
         - autoctx/experiments/test-exp/eval_configs/db_config.yaml
        dialect: postgres    # DB connection mapping
        query_types:
         - dql

        ############################################################
        ### Prompt and Generation Modules
        ############################################################
        model_config: autoctx/experiments/test-exp/eval_configs/model_config.yaml
        prompt_generator: 'NOOPGenerator'

        ############################################################
        ### Evaluator Execution / Parallelism Tuning
        ############################################################
        runners:
          eval_runners: 4
          sqlgen_runners: 20

        ############################################################
        ### Scorer Related Configs
        ############################################################
        scorers:
          llmrater:
            model_config: autoctx/experiments/test-exp/eval_configs/llmrater_config.yaml

        ############################################################
        ### Reporting Related Configs
        ############################################################
        reporting:
          csv:
            output_directory: 'autoctx/experiments/test-exp/eval_reports/'
    """).strip()
    
    # Verify content written
    m().write.assert_any_call(expected_db_config)
    m().write.assert_any_call(expected_model_config)
    m().write.assert_any_call(expected_llmrater_config)
    m().write.assert_any_call(expected_run_config)
    m().write.assert_any_call('[{"mock": "data"}]')


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
        with patch("builtins.open", mock_open(read_data=mock_yaml)) as m:
            with patch("evaluate.evaluate_generator._convert_dataset", return_value='[{"mock": "data"}]'):
                with patch("evaluate.evaluate_generator.os.makedirs"):
                    configs = generate_evalbench_configs(
                        experiment_name="test-exp",
                        dataset_path="/local/path/data.json",
                        context_set_id="context-123",
                        toolbox_config_path="/fake/tools.yaml",
                        toolbox_source_name="test-source"
                    )
            
    assert configs is None
    # assert the project was interpolated in file write
    calls = [call.args[0] for call in m().write.call_args_list]
    assert any("env-project" in call for call in calls)


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
        with patch("builtins.open", mock_open(read_data=mock_yaml)) as m:
            with patch("evaluate.evaluate_generator._convert_dataset", return_value='[{"mock": "data"}]'):
                with patch("evaluate.evaluate_generator.os.makedirs"):
                    configs = generate_evalbench_configs(
                        experiment_name="test-exp",
                        dataset_path="/local/path/data.json",
                        context_set_id="context-123",
                        toolbox_config_path="/fake/tools.yaml",
                        toolbox_source_name="test-source"
                    )
            
    assert configs is None
    # assert the project was fallbacked in file write
    calls = [call.args[0] for call in m().write.call_args_list]
    assert any("fallback-project" in call for call in calls)


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


def test_convert_dataset():
    from evaluate.evaluate_generator import _convert_dataset
    
    mock_dataset = textwrap.dedent("""\
        [
          {
            "id": "eval_001",
            "database": "my_db",
            "nlq": "Count users",
            "golden_sql": "SELECT COUNT(*) FROM users"
          }
        ]
    """).strip()
    
    with patch("builtins.open", mock_open(read_data=mock_dataset)):
        result_json = _convert_dataset("/fake/dataset.json", "postgres")
        
    data = json.loads(result_json)
    assert len(data) == 1
    assert data[0]["id"] == "eval_001"
    assert data[0]["nl_prompt"] == "Count users"
    assert data[0]["golden_sql"]["postgres"] == ["SELECT COUNT(*) FROM users"]
    assert data[0]["query_type"] == "DQL"


def test_convert_dataset_not_list():
    from evaluate.evaluate_generator import _convert_dataset
    
    mock_dataset = '{"not": "a list"}'
    
    with patch("builtins.open", mock_open(read_data=mock_dataset)):
        with pytest.raises(ValueError, match="Dataset must be a JSON list."):
            _convert_dataset("/fake/dataset.json", "postgres")


def test_convert_dataset_missing_keys():
    from evaluate.evaluate_generator import _convert_dataset
    
    mock_dataset = textwrap.dedent("""\
        [
          {
            "id": "eval_001",
            "database": "my_db",
            "nlq": "Count users"
          }
        ]
    """).strip()
    
    with patch("builtins.open", mock_open(read_data=mock_dataset)):
        with pytest.raises(ValueError, match="is missing required keys"):
            _convert_dataset("/fake/dataset.json", "postgres")


def test_convert_dataset_case_sensitive():
    from evaluate.evaluate_generator import _convert_dataset
    
    # Rigid format requires exact keys. Uppercase should fail.
    mock_dataset = textwrap.dedent("""\
        [
          {
            "ID": "eval_001",
            "database": "my_db",
            "nlq": "Count users",
            "golden_sql": "SELECT COUNT(*) FROM users"
          }
        ]
    """).strip()
    
    with patch("builtins.open", mock_open(read_data=mock_dataset)):
        with pytest.raises(ValueError, match="is missing required keys"):
            _convert_dataset("/fake/dataset.json", "postgres")
