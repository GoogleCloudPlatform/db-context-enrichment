import json
import os
import textwrap
from unittest.mock import mock_open, patch

import pytest
import yaml

from google.cloud.db_context_enrichment.evaluate.evaluate_generator import (
    generate_evalbench_configs,
)


@pytest.fixture
def valid_postgres_params():
    return {
        "type": "cloud-sql-postgres",
        "project": "test-project",
        "region": "us-central1",
        "instance": "test-instance",
        "database": "test-db",
        "user": "test-user",
        "password": "test-password",
    }


def test_generate_evalbench_configs_file_not_found(tmp_path):
    missing_file = str(tmp_path / "missing_tools.yaml")
    with pytest.raises(ValueError, match="Config file not found"):
        generate_evalbench_configs("exp", "path", "ctx", missing_file, "any-name")


def test_generate_evalbench_configs_permission_error():
    with patch(
        "builtins.open", side_effect=PermissionError("Mocked Permission Denied")
    ):
        with pytest.raises(ValueError, match="Permission denied reading config file"):
            generate_evalbench_configs(
                "exp", "path", "ctx", "fake_tools.yaml", "any-name"
            )


def test_generate_evalbench_configs_missing_source():
    mock_yaml = """
    kind: source
    name: other-source
    type: postgres
    """
    with patch("builtins.open", mock_open(read_data=mock_yaml)):
        with pytest.raises(
            ValueError, match="Could not find a 'kind: source' named 'test-source'"
        ):
            generate_evalbench_configs(
                "exp", "path", "ctx", "/fake/tools.yaml", "test-source"
            )


def test_generate_evalbench_configs_missing_type():
    mock_yaml = """
    kind: source
    name: test-source
    # missing type
    """
    with patch("builtins.open", mock_open(read_data=mock_yaml)):
        with pytest.raises(ValueError, match="is missing the 'type' field"):
            generate_evalbench_configs(
                "exp", "path", "ctx", "/fake/tools.yaml", "test-source"
            )


def test_generate_evalbench_configs_unsupported_type():
    mock_yaml = """
    kind: source
    name: test-source
    type: unknown-db
    """
    with patch("builtins.open", mock_open(read_data=mock_yaml)):
        with pytest.raises(
            ValueError, match="Unsupported evaluating toolbox source type: 'unknown-db'"
        ):
            generate_evalbench_configs(
                "exp", "path", "ctx", "/fake/tools.yaml", "test-source"
            )


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
        with patch(
            "google.cloud.db_context_enrichment.evaluate.evaluate_generator._convert_dataset",
            return_value='[{"mock": "data"}]',
        ):
            with patch(
                "google.cloud.db_context_enrichment.evaluate.evaluate_generator.os.makedirs"
            ) as mock_makedirs:
                configs = generate_evalbench_configs(
                    output_dir="/test/out",
                    dataset_path="/local/path/data.json",
                    context_set_id="context-123",
                    toolbox_config_path="/fake/tools.yaml",
                    toolbox_source_name="test-source",
                )

    assert configs is None
    # Filesystem operations use native separators (backslash on Windows) —
    # match with os.path.join so assertions are platform-portable.
    eval_configs_dir = os.path.join("/test/out", "eval_configs")
    mock_makedirs.assert_called_once_with(eval_configs_dir, exist_ok=True)

    # Verify all file writes
    m.assert_any_call(os.path.join(eval_configs_dir, "db_config.yaml"), "w")
    m.assert_any_call(os.path.join(eval_configs_dir, "model_config.yaml"), "w")
    m.assert_any_call(os.path.join(eval_configs_dir, "run_config.yaml"), "w")
    m.assert_any_call(os.path.join(eval_configs_dir, "llmrater_config.yaml"), "w")
    m.assert_any_call(os.path.join(eval_configs_dir, "golden_queries.json"), "w")

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
        use_rest_api: true
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
        vertex_model: gemini-3.1-flash-lite
        gcp_project_id: test-project
        gcp_region: global
        base_prompt: ""
        execs_per_minute: 20
    """).strip()

    expected_run_config = textwrap.dedent("""\
        ############################################################
        ### Dataset / Eval Items
        ############################################################
        dataset_config: /test/out/eval_configs/golden_queries.json
        dataset_format: evalbench-standard-format
        database_configs:
         - /test/out/eval_configs/db_config.yaml
        dialect: postgres    # DB connection mapping
        query_types:
         - dql

        ############################################################
        ### Prompt and Generation Modules
        ############################################################
        model_config: /test/out/eval_configs/model_config.yaml
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
            model_config: /test/out/eval_configs/llmrater_config.yaml

        ############################################################
        ### Reporting Related Configs
        ############################################################
        reporting:
          csv:
            output_directory: '/test/out/eval_reports/'
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
            with patch(
                "google.cloud.db_context_enrichment.evaluate.evaluate_generator._convert_dataset",
                return_value='[{"mock": "data"}]',
            ):
                with patch(
                    "google.cloud.db_context_enrichment.evaluate.evaluate_generator.os.makedirs"
                ):
                    configs = generate_evalbench_configs(
                        output_dir="/test/out",
                        dataset_path="/local/path/data.json",
                        context_set_id="context-123",
                        toolbox_config_path="/fake/tools.yaml",
                        toolbox_source_name="test-source",
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
            with patch(
                "google.cloud.db_context_enrichment.evaluate.evaluate_generator._convert_dataset",
                return_value='[{"mock": "data"}]',
            ):
                with patch(
                    "google.cloud.db_context_enrichment.evaluate.evaluate_generator.os.makedirs"
                ):
                    configs = generate_evalbench_configs(
                        output_dir="/test/out",
                        dataset_path="/local/path/data.json",
                        context_set_id="context-123",
                        toolbox_config_path="/fake/tools.yaml",
                        toolbox_source_name="test-source",
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
            with pytest.raises(
                ValueError,
                match="Environment variable 'MISSING_PROJECT' not found and no default provided.",
            ):
                generate_evalbench_configs(
                    "exp", "path", "ctx", "/fake/tools.yaml", "test-source"
                )


def test_convert_dataset():
    from google.cloud.db_context_enrichment.evaluate.evaluate_generator import (
        _convert_dataset,
    )

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
    from google.cloud.db_context_enrichment.evaluate.evaluate_generator import (
        _convert_dataset,
    )

    mock_dataset = '{"not": "a list"}'

    with patch("builtins.open", mock_open(read_data=mock_dataset)):
        with pytest.raises(ValueError, match="Dataset must be a JSON list."):
            _convert_dataset("/fake/dataset.json", "postgres")


def test_convert_dataset_missing_keys():
    from google.cloud.db_context_enrichment.evaluate.evaluate_generator import (
        _convert_dataset,
    )

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
    from google.cloud.db_context_enrichment.evaluate.evaluate_generator import (
        _convert_dataset,
    )

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


def test_parse_graph_ids_from_state_md(tmp_path):
    from google.cloud.db_context_enrichment.evaluate.evaluate_generator import (
        _parse_graph_ids_from_state_md,
    )

    state_file = tmp_path / "state.md"
    state_file.write_text(
        '# State Tracking\n\n## Active Database\n- **Graph Ids**: ["ResearchGraph", "LogisticsNet"]\n'
    )
    assert _parse_graph_ids_from_state_md(str(state_file)) == [
        "ResearchGraph",
        "LogisticsNet",
    ]

    # Empty list
    state_empty = tmp_path / "state_empty.md"
    state_empty.write_text("- **Graph Ids**: []\n")
    assert _parse_graph_ids_from_state_md(str(state_empty)) is None

    # Empty list with trailing comment (template default)
    state_empty_comment = tmp_path / "state_empty_comment.md"
    state_empty_comment.write_text(
        "- **Graph Ids**: [] # (Populated during schema inspection)\n"
    )
    assert _parse_graph_ids_from_state_md(str(state_empty_comment)) is None

    # List with trailing comment
    state_comment = tmp_path / "state_comment.md"
    state_comment.write_text(
        '- **Graph Ids**: ["ResearchGraph", "LogisticsNet"] # some comment\n'
    )
    assert _parse_graph_ids_from_state_md(str(state_comment)) == [
        "ResearchGraph",
        "LogisticsNet",
    ]

    # Unbracketed comma-separated with trailing comment
    state_unbracketed = tmp_path / "state_unbracketed.md"
    state_unbracketed.write_text(
        "- **Graph Ids**: ResearchGraph, LogisticsNet # some comment\n"
    )
    assert _parse_graph_ids_from_state_md(str(state_unbracketed)) == [
        "ResearchGraph",
        "LogisticsNet",
    ]

    # None / N/A / dash sentinels
    state_none = tmp_path / "state_none.md"
    state_none.write_text("- **Graph Ids**: None\n")
    assert _parse_graph_ids_from_state_md(str(state_none)) is None

    state_na = tmp_path / "state_na.md"
    state_na.write_text("- **Graph Ids**: N/A # none available\n")
    assert _parse_graph_ids_from_state_md(str(state_na)) is None

    state_dash = tmp_path / "state_dash.md"
    state_dash.write_text("- **Graph Ids**: -\n")
    assert _parse_graph_ids_from_state_md(str(state_dash)) is None

    # Colon inside bold
    state_colon_inside = tmp_path / "state_colon_inside.md"
    state_colon_inside.write_text('**Graph Ids:** ["ResearchGraph"]\n')
    assert _parse_graph_ids_from_state_md(str(state_colon_inside)) == ["ResearchGraph"]

    # Multiline bullet items
    state_multiline = tmp_path / "state_multiline.md"
    state_multiline.write_text(
        textwrap.dedent("""\
            # State Tracking
            - **Source Name**: spanner-db
            - **Graph Ids**:
              - ResearchGraph
              - `LogisticsNet`
            - **Other Setting**: something_else
        """)
    )
    assert _parse_graph_ids_from_state_md(str(state_multiline)) == [
        "ResearchGraph",
        "LogisticsNet",
    ]

    # Missing file
    assert _parse_graph_ids_from_state_md(str(tmp_path / "nonexistent.md")) is None


def test_generate_evalbench_configs_spanner_graph_from_state_md(tmp_path):
    tools_yaml = tmp_path / "tools.yaml"
    tools_yaml.write_text(
        textwrap.dedent("""\
            kind: source
            name: spanner-source
            type: spanner
            project: test-project
            instance: test-instance
            database: test-db
        """)
    )

    state_md = tmp_path / "state.md"
    state_md.write_text(
        textwrap.dedent("""\
            # Context Authoring Experiment State Tracking

            ## Active Database
            - **Source Name**: spanner-source
            - **Type**: spanner
            - **Graph Ids**: ["ResearchGraph", "LogisticsNet"]
        """)
    )

    dataset_json = tmp_path / "dataset.json"
    dataset_json.write_text(
        json.dumps(
            [{"id": "1", "database": "test-db", "nlq": "q", "golden_sql": "SELECT 1"}]
        )
    )

    out_dir = tmp_path / "experiments" / "exp1"

    generate_evalbench_configs(
        output_dir=str(out_dir),
        dataset_path=str(dataset_json),
        context_set_id="projects/test-project/locations/us-central1/contextSets/context-123",
        toolbox_config_path=str(tools_yaml),
        toolbox_source_name="spanner-source",
    )

    model_config_path = out_dir / "eval_configs" / "model_config.yaml"
    assert model_config_path.exists()
    model_config = yaml.safe_load(model_config_path.read_text())
    assert model_config["use_rest_api"] is True
    spanner_ref = model_config["context"]["datasource_references"]["spanner_reference"]
    assert spanner_ref["database_reference"]["graph_ids"] == [
        "ResearchGraph",
        "LogisticsNet",
    ]


def test_generate_evalbench_configs_spanner_no_state_md_graphs(tmp_path):
    tools_yaml = tmp_path / "tools.yaml"
    tools_yaml.write_text(
        textwrap.dedent("""\
            kind: source
            name: spanner-source
            type: spanner
            project: test-project
            instance: test-instance
            database: test-db
        """)
    )

    dataset_json = tmp_path / "dataset.json"
    dataset_json.write_text(
        json.dumps(
            [{"id": "1", "database": "test-db", "nlq": "q", "golden_sql": "SELECT 1"}]
        )
    )

    out_dir = tmp_path / "experiments" / "exp2"

    generate_evalbench_configs(
        output_dir=str(out_dir),
        dataset_path=str(dataset_json),
        context_set_id="projects/test-project/locations/us-central1/contextSets/context-123",
        toolbox_config_path=str(tools_yaml),
        toolbox_source_name="spanner-source",
    )

    model_config_path = out_dir / "eval_configs" / "model_config.yaml"
    assert model_config_path.exists()
    model_config = yaml.safe_load(model_config_path.read_text())
    spanner_ref = model_config["context"]["datasource_references"]["spanner_reference"]
    assert "graph_ids" not in spanner_ref["database_reference"]


def test_generate_evalbench_configs_spanner_postgres():
    tools_yaml_content = textwrap.dedent("""\
        kind: source
        name: spanner-pg-source
        type: spanner
        project: test-project
        instance: test-instance
        database: test-db
        engine: POSTGRESQL
    """).strip()

    with patch("builtins.open", mock_open(read_data=tools_yaml_content)) as m:
        with patch(
            "google.cloud.db_context_enrichment.evaluate.evaluate_generator._convert_dataset",
            return_value='[{"mock": "data"}]',
        ):
            with patch(
                "google.cloud.db_context_enrichment.evaluate.evaluate_generator.os.makedirs"
            ):
                generate_evalbench_configs(
                    output_dir="/test/out",
                    dataset_path="/fake/dataset.json",
                    context_set_id="projects/test-project/locations/us-central1/contextSets/context-123",
                    toolbox_config_path="/fake/tools.yaml",
                    toolbox_source_name="spanner-pg-source",
                )

    written_data = {}
    for call in m().write.call_args_list:
        content = call[0][0]
        if "spanner_reference" in content:
            written_data["model_config"] = content
        elif "db_type: spanner" in content:
            written_data["db_config"] = content
        elif "dialect: spanner_pg" in content and "dataset_config" in content:
            written_data["run_config"] = content

    assert "model_config" in written_data
    model_config = yaml.safe_load(written_data["model_config"])
    spanner_ref = model_config["context"]["datasource_references"]["spanner_reference"]
    assert spanner_ref["database_reference"]["engine"] == "POSTGRESQL"

    assert "db_config" in written_data
    db_config = yaml.safe_load(written_data["db_config"])
    assert db_config["dialect"] == "spanner_pg"
    assert db_config["db_type"] == "spanner"

    assert "run_config" in written_data
    run_config = yaml.safe_load(written_data["run_config"])
    assert run_config["dialect"] == "spanner_pg"
