"""Module for executing EvalBench evaluation runs with REST transport."""

import logging
import os
import subprocess
import sys
from typing import NamedTuple

import yaml

RUN_CONFIG_NAME = "run_config.yaml"
MODEL_CONFIG_NAME = "model_config.yaml"


class EvalBenchResult(NamedTuple):
    """Result of an EvalBench execution."""

    returncode: int
    output: str


def _exec_evalbench(cmd: list[str]) -> EvalBenchResult:
    """Executes EvalBench command, streaming stdout/stderr in real-time

    to sys.stdout for harness liveness heartbeats while capturing full output.
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
    return EvalBenchResult(returncode, combined_output)


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


def run_evaluation(target: str) -> None:
    """
    Executes EvalBench evaluation for a target experiment name or path,
    using REST transport for QueryData API (supporting non-public fields).
    """
    logger = logging.getLogger(__name__)

    if os.path.isdir(target):
        if os.path.exists(os.path.join(target, "eval_configs")):
            eval_configs_dir = os.path.join(target, "eval_configs")
        else:
            eval_configs_dir = target
    else:
        eval_configs_dir = f"autoctx/experiments/{target}/eval_configs"

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
        # Use REST transport (bypassing gRPC to allow unreleased proto fields).
        logger.info(
            f"Attempting QueryData eval via REST API for target: {target}..."
        )
        _update_model_config(
            model_config_path,
            use_rest_api=True,
            api_endpoint=None,
        )
        res = _exec_evalbench(cmd)
        if res.returncode == 0:
            logger.info("Evaluation completed successfully.")
            return

        logger.error(f"Evaluation failed:\n{res.output[:500]}")
        raise RuntimeError(
            f"EvalBench evaluation failed for target '{target}'.\n"
            "You may be attempting to use an unreleased or non-public QueryData"
            " feature that your project does not have access to. Please reach"
            " out to your accounts team for access."
        )
    except Exception:
        if original_model_config is not None:
            with open(model_config_path, "w") as f:
                f.write(original_model_config)
        raise


def cli_main() -> None:
    """CLI entrypoint for autoctx-eval command."""
    if len(sys.argv) < 2:
        print("Usage: autoctx-eval <experiment_name_or_path>")
        sys.exit(1)

    target = sys.argv[1]
    run_evaluation(target)
