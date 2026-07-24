"""Module for executing EvalBench evaluation runs with automatic transport fallback."""

import logging
import os
import subprocess
import sys
from typing import NamedTuple

import yaml

RUN_CONFIG_NAME = "run_config.yaml"
MODEL_CONFIG_NAME = "model_config.yaml"

_STAGING_API_ENDPOINT = "staging-geminidataanalytics.sandbox.googleapis.com"


class RestFallbackTier(NamedTuple):
    """Configuration tier for REST API fallback execution."""

    name: str
    use_rest_api: bool
    api_endpoint: str | None = None


_PROTO_FIELD_ERROR_PATTERNS = (
    "attributeerror",
    "typeerror",
    "valueerror",
    "protocol message",
    "unknown field",
    "invalid field",
    "has no attribute",
    "querydatacontext",
    "datasourcereferences",
)


def _exec_evalbench(cmd: list[str]) -> tuple[int, str]:
    """Executes EvalBench command, streaming stdout/stderr in real-time to sys.stdout

    for harness liveness heartbeats while capturing full output.
    """
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    output_lines = []
    if process.stdout:
        for line in iter(process.stdout.readline, ""):
            sys.stdout.write(line)
            sys.stdout.flush()
            output_lines.append(line)
        process.stdout.close()

    returncode = process.wait()
    combined_output = "".join(output_lines)
    return returncode, combined_output


def _is_proto_field_error(output: str) -> bool:
    """Returns True if output contains errors related to missing/unreleased proto fields."""
    out_lower = output.lower()
    return any(pattern in out_lower for pattern in _PROTO_FIELD_ERROR_PATTERNS)


def _update_model_config(
    model_config_path: str,
    use_rest_api: bool = True,
    api_endpoint: str | None = None,
) -> None:
    """Updates model_config.yaml with REST API transport flags."""
    with open(model_config_path) as f:
        cfg = yaml.safe_load(f) or {}

    cfg["use_rest_api"] = use_rest_api
    if api_endpoint:
        cfg["api_endpoint"] = api_endpoint
    else:
        cfg.pop("api_endpoint", None)

    with open(model_config_path, "w") as f:
        yaml.safe_dump(cfg, f, sort_keys=False, default_flow_style=False)


def run_evaluation(experiment_name: str) -> None:
    """
    Executes EvalBench evaluation for an experiment, using standard SDK gRPC client
    and falling back to REST (supports non-public fields).
    """
    logger = logging.getLogger(__name__)
    eval_configs_dir = f"autoctx/experiments/{experiment_name}/eval_configs"
    run_config_path = os.path.join(eval_configs_dir, RUN_CONFIG_NAME)
    model_config_path = os.path.join(eval_configs_dir, MODEL_CONFIG_NAME)

    cmd = [
        "uvx",
        "google-evalbench@1.9.0",
        f"--experiment_config={run_config_path}",
    ]

    original_model_config = None
    if os.path.exists(model_config_path):
        with open(model_config_path) as f:
            original_model_config = f.read()

    try:
        # 1. Standard SDK gRPC Execution
        logger.info(f"Running EvalBench evaluation for experiment: {experiment_name}")
        code, output = _exec_evalbench(cmd)
        if code == 0 and not _is_proto_field_error(output):
            logger.info("EvalBench completed successfully via gRPC SDK.")
            return

        if not _is_proto_field_error(output):
            logger.error(
                f"EvalBench execution failed with non-proto error:\n{output[:500]}"
            )
            raise RuntimeError(
                f"EvalBench execution failed with exit code {code}:\n{output}"
            )

        # 2. REST API Fallback Tiers (Production REST, then Staging REST)
        rest_tiers = [
            RestFallbackTier(
                name="Production REST API",
                use_rest_api=True,
                api_endpoint=None,
            ),
            RestFallbackTier(
                name=f"Staging REST API ({_STAGING_API_ENDPOINT})",
                use_rest_api=True,
                api_endpoint=_STAGING_API_ENDPOINT,
            ),
        ]

        for tier in rest_tiers:
            logger.info(f"Attempting evaluation fallback via {tier.name}...")
            try:
                _update_model_config(
                    model_config_path,
                    use_rest_api=tier.use_rest_api,
                    api_endpoint=tier.api_endpoint,
                )
                code, output = _exec_evalbench(cmd)
                if code == 0:
                    logger.info(f"Evaluation completed successfully via {tier.name}.")
                    return
                logger.warning(f"{tier.name} failed with code {code}:\n{output[:300]}")
            except Exception as err:
                logger.debug(f"{tier.name} execution failed: {err}")

        logger.error(f"Evaluation failed across all transport modes:\n{output[:500]}")
        raise RuntimeError(
            f"EvalBench evaluation failed for experiment '{experiment_name}'.\n"
            "You may be attempting to use an unreleased or non-public QueryData feature. Please reach out to your accounts team for access."
        )
    except Exception:
        if original_model_config is not None:
            with open(model_config_path, "w") as f:
                f.write(original_model_config)
        raise


def cli_main() -> None:
    """CLI entrypoint for autoctx-eval command."""
    if len(sys.argv) < 2:
        print("Usage: autoctx-eval <experiment_name>")
        sys.exit(1)

    experiment_name = sys.argv[1]
    run_evaluation(experiment_name)
