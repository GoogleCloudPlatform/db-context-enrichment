"""Module for executing EvalBench evaluation runs with automatic transport fallback."""

import logging
import os
import subprocess
import sys
import yaml

RUN_CONFIG_NAME = "run_config.yaml"
MODEL_CONFIG_NAME = "model_config.yaml"




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
    Executes EvalBench evaluation for an experiment, strictly using REST transport
    for QueryData API (supporting non-public fields).
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
        # Strictly use REST transport (bypassing gRPC to allow unreleased proto fields).
        logger.info(f"Attempting QueryData evaluation via REST API for experiment: {experiment_name}...")
        _update_model_config(
            model_config_path,
            use_rest_api=True,
            api_endpoint=None,
        )
        code, output = _exec_evalbench(cmd)
        if code == 0:
            logger.info("Evaluation completed successfully via REST API.")
            return

        logger.error(f"Evaluation failed via REST API:\n{output[:500]}")
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
