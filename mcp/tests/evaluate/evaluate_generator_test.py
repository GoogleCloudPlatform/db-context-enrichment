import json
import pytest
import textwrap

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

def test_generate_evalbench_configs_invalid_json():
    with pytest.raises(ValueError, match="must be a valid JSON dictionary"):
        generate_evalbench_configs("exp", "path", "ctx", "{invalid_json: false}")

def test_generate_evalbench_configs_missing_type():
    with pytest.raises(ValueError, match="Missing required field 'type'"):
        generate_evalbench_configs("exp", "path", "ctx", '{"project": "test"}')

def test_generate_evalbench_configs_unsupported_type():
    with pytest.raises(ValueError, match="Unsupported evaluating toolbox source type: 'unknown-db'"):
        generate_evalbench_configs("exp", "path", "ctx", '{"type": "unknown-db"}')


def test_generate_evalbench_configs(valid_postgres_params):
    json_str = json.dumps(valid_postgres_params)
    
    configs = generate_evalbench_configs(
        experiment_name="test-exp",
        dataset_path="/local/path/data.json",
        context_set_id="context-123",
        toolbox_db_info=json_str
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
        database_configs:
         - experiments/test-exp/eval_configs/db_config.yaml
        dialects:
         - postgres
        dialect: postgres
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
