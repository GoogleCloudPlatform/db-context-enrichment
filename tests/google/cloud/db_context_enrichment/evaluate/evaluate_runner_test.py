from unittest.mock import patch

import pytest

from google.cloud.db_context_enrichment.evaluate.evaluate_runner import (
    _is_proto_field_error,
    _update_model_config,
    run_evaluation,
)


def test_is_proto_field_error():
    assert _is_proto_field_error(
        "ValueError: Unknown field for SpannerDatabaseReference"
    )
    assert _is_proto_field_error("AttributeError: 'NoneType' object has no attribute")
    assert not _is_proto_field_error("401 Unauthorized: Invalid credentials")
    assert not _is_proto_field_error("404 Not Found")


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


@patch("google.cloud.db_context_enrichment.evaluate.evaluate_runner._exec_evalbench")
@patch(
    "google.cloud.db_context_enrichment.evaluate.evaluate_runner._update_model_config"
)
def test_run_evaluation_grpc_success(mock_update_cfg, mock_exec):
    mock_exec.return_value = (0, "Success")
    run_evaluation("test_exp")

    mock_exec.assert_called_once()
    mock_update_cfg.assert_not_called()


@patch("google.cloud.db_context_enrichment.evaluate.evaluate_runner._exec_evalbench")
@patch(
    "google.cloud.db_context_enrichment.evaluate.evaluate_runner._update_model_config"
)
def test_run_evaluation_non_proto_error_raises(mock_update_cfg, mock_exec):
    mock_exec.return_value = (1, "401 Unauthorized")
    with pytest.raises(
        RuntimeError, match="EvalBench execution failed with exit code 1"
    ):
        run_evaluation("test_exp")

    mock_exec.assert_called_once()
    mock_update_cfg.assert_not_called()


@patch("google.cloud.db_context_enrichment.evaluate.evaluate_runner._exec_evalbench")
@patch(
    "google.cloud.db_context_enrichment.evaluate.evaluate_runner._update_model_config"
)
def test_run_evaluation_fallback_to_production_rest_success(mock_update_cfg, mock_exec):
    mock_exec.side_effect = [
        (
            0,
            "ValueError: Unknown field graph_ids",
        ),  # Attempt 1: gRPC fails on proto field
        (0, "Success via REST"),  # Attempt 2: Production REST succeeds
    ]
    run_evaluation("test_exp")

    assert mock_exec.call_count == 2
    mock_update_cfg.assert_called_once_with(
        "autoctx/experiments/test_exp/eval_configs/model_config.yaml",
        use_rest_api=True,
        api_endpoint=None,
    )


@patch("google.cloud.db_context_enrichment.evaluate.evaluate_runner._exec_evalbench")
@patch(
    "google.cloud.db_context_enrichment.evaluate.evaluate_runner._update_model_config"
)
def test_run_evaluation_fallback_to_staging_rest_success(mock_update_cfg, mock_exec):
    mock_exec.side_effect = [
        (
            0,
            "ValueError: Unknown field graph_ids",
        ),  # Attempt 1: gRPC fails on proto field
        (1, "404 Not Found"),  # Attempt 2: Production REST fails
        (0, "Success via Staging REST"),  # Attempt 3: Staging REST succeeds
    ]
    run_evaluation("test_exp")

    assert mock_exec.call_count == 3
    assert mock_update_cfg.call_count == 2


@patch("google.cloud.db_context_enrichment.evaluate.evaluate_runner._exec_evalbench")
@patch(
    "google.cloud.db_context_enrichment.evaluate.evaluate_runner._update_model_config"
)
def test_run_evaluation_all_modes_fail_raises(mock_update_cfg, mock_exec):
    mock_exec.return_value = (1, "ValueError: Unknown field graph_ids")
    with pytest.raises(
        RuntimeError, match="EvalBench evaluation failed for experiment 'test_exp'"
    ):
        run_evaluation("test_exp")

    assert mock_exec.call_count == 3
