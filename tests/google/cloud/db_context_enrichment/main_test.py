import json
import os
from pathlib import Path

import pytest

from google.cloud.db_context_enrichment.main import (
    generate_evalbench_configs,
    generate_upload_url,
    mutate_context_set,
    read_evaluation_result,
    validate_context_set,
)


def test_mutate_context_set_success(tmp_path: Path):
    file_path = tmp_path / "context.json"
    mutations = [
        {
            "operation": "add",
            "type": "template",
            "value": {
                "nl_query": "Test query",
                "sql": "SELECT *",
                "intent": "Test intent",
                "manifest": "Test manifest",
                "parameterized": {
                    "parameterized_sql": "SELECT * FROM t",
                    "parameterized_intent": "Test",
                },
            },
        }
    ]

    result = mutate_context_set(str(file_path), json.dumps(mutations))

    assert "Successfully applied" in result
    assert file_path.exists()
    with open(file_path) as f:
        data = json.load(f)
    assert len(data.get("templates", [])) == 1
    assert data["templates"][0]["nl_query"] == "Test query"


def test_mutate_context_set_invalid_json(tmp_path: Path):
    file_path = tmp_path / "context.json"
    result = mutate_context_set(str(file_path), "invalid json")
    assert "Error applying mutations" in result
    assert "JSONDecodeError" in result or "invalid json" in result or "Error" in result


def test_mutate_context_set_non_list_json(tmp_path: Path):
    file_path = tmp_path / "context.json"
    result = mutate_context_set(
        str(file_path), json.dumps({"operation": "add", "type": "template"})
    )
    assert "must be a JSON list" in result


def test_mutate_context_set_validation_error(tmp_path: Path):
    file_path = tmp_path / "context.json"
    # Invalid operation
    mutations = [{"operation": "invalid", "type": "template"}]
    result = mutate_context_set(str(file_path), json.dumps(mutations))
    assert "Error applying mutations" in result


def test_validate_context_set_valid_file(tmp_path: Path):
    file_path = tmp_path / "context.json"
    file_path.write_text(
        json.dumps(
            {
                "value_searches": [
                    {
                        "query": "SELECT name FROM cities WHERE name = $value",
                        "concept_type": "City",
                    }
                ]
            }
        )
    )
    result = validate_context_set(str(file_path))
    parsed = json.loads(result)
    assert parsed["valid"] is True
    assert parsed["issues"] == []


def test_validate_context_set_reports_issues(tmp_path: Path):
    file_path = tmp_path / "context.json"
    file_path.write_text(
        json.dumps(
            {
                "value_searches": [
                    {"query": "SELECT 1", "concept_type": "City"},
                ]
            }
        )
    )
    result = validate_context_set(str(file_path))
    parsed = json.loads(result)
    assert parsed["valid"] is False
    assert any("$value" in i["message"] for i in parsed["issues"])


def test_validate_context_set_missing_file(tmp_path: Path):
    # End-to-end: wrapper returns a parseable JSON response for I/O errors
    # rather than raising. Error-case coverage lives in context_validator_test.
    result = validate_context_set(str(tmp_path / "missing.json"))
    parsed = json.loads(result)
    assert parsed["valid"] is False
    assert "missing.json" in parsed["issues"][0]["message"]


def test_generate_upload_url_bigtable_success():
    url = generate_upload_url(
        db_engine="bigtable",
        project_id="test-project",
        instance_id="test-instance",
    )
    assert (
        url
        == "https://console.cloud.google.com/bigtable/instances/test-instance/overview?project=test-project"
    )


def test_generate_upload_url_bigtable_missing_instance_id():
    result = generate_upload_url(
        db_engine="bigtable",
        project_id="test-project",
    )
    assert result == "Error: Missing instance_id or project_id for bigtable."


def test_generate_upload_url_bigtable_missing_project_id():
    result = generate_upload_url(
        db_engine="bigtable",
        project_id="",
        instance_id="test-instance",
    )
    assert result == "Error: Missing instance_id or project_id for bigtable."


def test_generate_upload_url_bigtable_none_instance():
    result = generate_upload_url(
        db_engine="bigtable",
        project_id="test-project",
        instance_id=None,
    )
    assert result == "Error: Missing instance_id or project_id for bigtable."


def test_generate_upload_url_alloydb_success():
    url = generate_upload_url(
        db_engine="alloydb",
        project_id="test-project",
        location="us-central1",
        cluster_id="test-cluster",
    )
    assert (
        url
        == "https://console.cloud.google.com/alloydb/locations/us-central1/clusters/test-cluster/studio?project=test-project"
    )


def test_generate_upload_url_alloydb_missing_params():
    result = generate_upload_url(
        db_engine="alloydb",
        project_id="test-project",
        location="us-central1",
    )
    assert result == "Error: Missing location, cluster_id, or project_id for alloydb."


def test_generate_upload_url_cloudsql_success():
    url = generate_upload_url(
        db_engine="cloudsql",
        project_id="test-project",
        instance_id="test-instance",
    )
    assert (
        url
        == "https://console.cloud.google.com/sql/instances/test-instance/studio?project=test-project"
    )


def test_generate_upload_url_cloudsql_missing_params():
    result = generate_upload_url(
        db_engine="cloudsql",
        project_id="test-project",
    )
    assert result == "Error: Missing instance_id or project_id for cloudsql."


def test_generate_upload_url_spanner_success():
    url = generate_upload_url(
        db_engine="spanner",
        project_id="test-project",
        instance_id="test-instance",
        database_id="test-database",
    )
    assert (
        url
        == "https://console.cloud.google.com/spanner/instances/test-instance/databases/test-database/details/query?project=test-project"
    )


def test_generate_upload_url_spanner_missing_params():
    result = generate_upload_url(
        db_engine="spanner",
        project_id="test-project",
        instance_id="test-instance",
    )
    assert (
        result == "Error: Missing instance_id, database_id, or project_id for spanner."
    )


def test_generate_upload_url_invalid_db_engine():
    result = generate_upload_url(
        db_engine="oracle",
        project_id="test-project",
    )
    assert (
        result
        == "Error: Invalid db_engine. Must be one of 'alloydb', 'cloudsql', 'spanner', or 'bigtable'."
    )


def test_generate_evalbench_configs_tool_bigtable(tmp_path: Path):
    golden_file = tmp_path / "golden.json"
    golden_file.write_text(
        json.dumps(
            [
                {
                    "id": "h1",
                    "database": "hotels",
                    "nlq": "Find all hotels",
                    "golden_sql": "SELECT * FROM `hotels`",
                }
            ]
        )
    )
    tools_file = tmp_path / "tools.yaml"
    tools_file.write_text(
        """kind: source
name: my-bigtable-source
type: bigtable
project: test-p
instance: test-i
"""
    )
    cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        out_dir = str(tmp_path / "autoctx" / "experiments" / "test_exp")
        result = generate_evalbench_configs(
            output_dir=out_dir,
            dataset_path=str(golden_file),
            context_set_id="test_ctx_id",
            toolbox_config_path=str(tools_file),
            toolbox_source_name="my-bigtable-source",
        )
        assert "Successfully generated all configs for evaluation" in result
        eval_dir = tmp_path / "autoctx" / "experiments" / "test_exp" / "eval_configs"
        assert (eval_dir / "db_config.yaml").exists()
        assert (eval_dir / "model_config.yaml").exists()
        assert (eval_dir / "run_config.yaml").exists()
        assert (eval_dir / "llmrater_config.yaml").exists()
        assert (eval_dir / "golden_queries.json").exists()
    finally:
        os.chdir(cwd)


@pytest.mark.asyncio
async def test_read_evaluation_result_tool(tmp_path: Path):
    run_dir = tmp_path / "run_001"
    run_dir.mkdir()
    (run_dir / "summary.csv").write_text(
        "metric_name,metric_score,correct_results_count,total_results_count,job_id,run_time\n"
        "llmrater,100,5,5,run_001,2026-08-17 22:00:00\n"
    )
    (run_dir / "scores.csv").write_text(
        "comparator,comparison_error,comparison_logs,database,dialects,generated_error,generated_sql,id,job_id,score\n"
        "llmrater,,Skipped,hotels,['bigtable'],,,h1,run_001,100\n"
    )
    (run_dir / "evals.csv").write_text(
        "cleanup_sql,database,dialects,eval_query,eval_results,generated_error,generated_prompt,generated_result,generated_sql,golden_error,golden_eval_results,golden_result,golden_sql,id,job_id,nl_prompt,other,payload,prompt,prompt_generator_error,query_type,run_time,sanitized_sql,setup_sql,sql_generator_error,sql_generator_time,tags,trace_id\n"
    )
    report = await read_evaluation_result(str(run_dir))
    assert "Evaluation Summary" in report
    assert "No failure cases found (all passed)." in report
