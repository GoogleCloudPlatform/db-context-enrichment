from unittest.mock import mock_open, patch

import pytest

from google.cloud.db_context_enrichment.evaluate.evaluate_runner import (
    EvalBenchResult,
    _update_model_config,
    run_evaluation,
)


def test_update_model_config(tmp_path):
    config_path = tmp_path / "model_config.yaml"
    config_path.write_text("generator: query_data_api\nproject_id: test-proj\n")

    # Set REST API with custom endpoint
    _update_model_config(
        str(config_path), use_rest_api=True, api_endpoint="custom.endpoint.com"
    )
    content = config_path.read_text()
    assert "use_rest_api: true" in content
    assert "api_endpoint: custom.endpoint.com" in content

    # Clear custom endpoint
    _update_model_config(str(config_path), use_rest_api=True, api_endpoint=None)
    content_cleared = config_path.read_text()
    assert "use_rest_api: true" in content_cleared
    assert "api_endpoint" not in content_cleared


@patch("os.path.exists", return_value=True)
@patch(
    "builtins.open",
    new_callable=mock_open,
    read_data="generator: query_data_api\ncontext:\n  datasource_references:\n    firestore_reference:\n      database_id: nl2sql-supplies\n",
)
@patch("google.cloud.db_context_enrichment.evaluate.evaluate_runner._exec_evalbench")
@patch(
    "google.cloud.db_context_enrichment.evaluate.evaluate_runner._update_model_config"
)
def test_run_evaluation_rest_production_success(
    mock_update_cfg, mock_exec, mock_file, mock_exists
):
    mock_exec.return_value = EvalBenchResult(0, "Success via REST")
    run_evaluation("test_exp")

    mock_exec.assert_called_once()
    mock_update_cfg.assert_called_once_with(
        "autoctx/experiments/test_exp/eval_configs/model_config.yaml",
        use_rest_api=True,
        api_endpoint=None,
    )


@patch("os.path.isdir", return_value=True)
@patch("os.path.exists", return_value=True)
@patch(
    "builtins.open",
    new_callable=mock_open,
    read_data="generator: query_data_api\ncontext:\n  datasource_references:\n    firestore_reference:\n      database_id: nl2sql-supplies\n",
)
@patch("google.cloud.db_context_enrichment.evaluate.evaluate_runner._exec_evalbench")
@patch(
    "google.cloud.db_context_enrichment.evaluate.evaluate_runner._update_model_config"
)
def test_run_evaluation_path_target_success(
    mock_update_cfg, mock_exec, mock_file, mock_exists, mock_isdir
):
    mock_exec.return_value = EvalBenchResult(0, "Success via REST")
    run_evaluation("evals/core-cujs/workspace_post_evaluation/autoctx/experiments/my-alloydb-tuning-experiment")

    mock_exec.assert_called_once()
    mock_update_cfg.assert_called_once_with(
        "evals/core-cujs/workspace_post_evaluation/autoctx/experiments/my-alloydb-tuning-experiment/eval_configs/model_config.yaml",
        use_rest_api=True,
        api_endpoint=None,
    )


@patch("os.path.exists", return_value=True)
@patch(
    "builtins.open",
    new_callable=mock_open,
    read_data="generator: query_data_api\ncontext:\n  datasource_references:\n    firestore_reference:\n      database_id: nl2sql-supplies\n",
)
@patch("google.cloud.db_context_enrichment.evaluate.evaluate_runner._exec_evalbench")
@patch(
    "google.cloud.db_context_enrichment.evaluate.evaluate_runner._update_model_config"
)
def test_run_evaluation_rest_failure_raises(
    mock_update_cfg, mock_exec, mock_file, mock_exists
):
    mock_exec.return_value = EvalBenchResult(1, "400 Bad Request: Unknown field firestore_reference")
    with pytest.raises(
        RuntimeError, match="EvalBench evaluation failed for target 'test_exp'"
    ):
        run_evaluation("test_exp")

    mock_exec.assert_called_once()
