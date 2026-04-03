import json
import os
import re
import textwrap
import yaml
from typing import Dict, Any

from .db_generators.base import BaseDBConfigGenerator
from .db_generators.alloydb import AlloyDBConfigGenerator
from .db_generators.spanner import SpannerConfigGenerator
from .db_generators.postgres import PostgresConfigGenerator
from .db_generators.mysql import MySQLConfigGenerator


def generate_evalbench_configs(
    experiment_name: str,
    dataset_path: str,
    context_set_id: str,
    toolbox_config_path: str,
    toolbox_source_name: str
) -> Dict[str, str]:
    """
    Main entrypoint: Generates Evalbench-compatible YAML configurations natively using 
    private DB format converters and the google-cloud-geminidataanalytics API validations.
    """
    params = _extract_toolbox_params(toolbox_config_path, toolbox_source_name)
    generator = _get_db_generator(params)
    
    db_config_yaml = generator.generate_db_config()
    model_config_yaml = generator.generate_model_config(context_set_id)
    run_config_yaml = _generate_run_config(experiment_name, dataset_path, generator.DIALECT)
    
    llmrater_config = _generate_llmrater_config()

    return {
        "db_config.yaml": db_config_yaml,
        "model_config.yaml": model_config_yaml,
        "run_config.yaml": run_config_yaml,
        "llmrater_config.yaml": llmrater_config
    }


def _extract_toolbox_params(toolbox_config_path: str, toolbox_source_name: str) -> Dict[str, Any]:
    """Deterministically extracts connection parameters for a specific database source from tools.yaml."""
    try:
        with open(toolbox_config_path, "r") as f:
            content = f.read()
            interpolated = _interpolate_env_vars(content)
            docs = yaml.safe_load_all(interpolated)
            for doc in docs:
                if not doc:
                    continue
                if doc.get("kind") == "source" and doc.get("name") == toolbox_source_name:
                    if not doc.get("type"):
                        raise ValueError(f"Selected source '{toolbox_source_name}' is missing the 'type' field.")
                    return doc
            
            raise ValueError(f"Could not find a 'kind: source' named '{toolbox_source_name}' in {toolbox_config_path}")
            
    except FileNotFoundError:
        raise ValueError(f"Config file not found: {toolbox_config_path}")
    except yaml.YAMLError as e:
        raise ValueError(f"Failed to parse {toolbox_config_path} as YAML: {e}")


def _interpolate_env_vars(raw_yaml: str) -> str:
    """Replaces ${ENV_NAME} or ${ENV_NAME:default_value} with environment variables."""
    # Matches ${VAR_NAME} or ${VAR_NAME:fallback}
    pattern = re.compile(r'\$\{(\w+)(?::([^}]*))?\}')
    
    def replacer(match):
        var_name = match.group(1)
        fallback = match.group(2)
        
        if var_name in os.environ:
            return os.environ[var_name]
        if fallback is not None:
            return fallback
        raise ValueError(f"Environment variable '{var_name}' not found and no default provided.")

    return pattern.sub(replacer, raw_yaml)


def _get_db_generator(params: Dict[str, Any]) -> BaseDBConfigGenerator:
    """Factory function to build the correct Evaluation Generator."""
    source_type = params.get("type", "").lower()
    
    generators = {
        AlloyDBConfigGenerator.SOURCE_TYPE: AlloyDBConfigGenerator,
        PostgresConfigGenerator.SOURCE_TYPE: PostgresConfigGenerator,
        MySQLConfigGenerator.SOURCE_TYPE: MySQLConfigGenerator,
        SpannerConfigGenerator.SOURCE_TYPE: SpannerConfigGenerator,
    }
    
    if source_type not in generators:
        supported = ", ".join(generators.keys())
        raise ValueError(f"Unsupported evaluating toolbox source type: '{source_type}'. Must be one of: {supported}")

    return generators[source_type](params)


def _generate_run_config(experiment_name: str, dataset_path: str, dialect: str) -> str:
    """Generates the main EvalBench Run Experiment scaffolding."""
    return textwrap.dedent(f"""\
        ############################################################
        ### Dataset / Eval Items
        ############################################################
        dataset_config: {dataset_path}
        dataset_format: evalbench-standard-format
        database_configs:
         - experiments/{experiment_name}/eval_configs/db_config.yaml
        dialect: {dialect}    # DB connection mapping
        query_types:
         - dql

        ############################################################
        ### Prompt and Generation Modules
        ############################################################
        model_config: experiments/{experiment_name}/eval_configs/model_config.yaml
        prompt_generator: 'NOOPGenerator'

        ############################################################
        ### Scorer Related Configs
        ############################################################
        scorers:
          llmrater:
            model_config: experiments/{experiment_name}/eval_configs/llmrater_config.yaml

        ############################################################
        ### Reporting Related Configs
        ############################################################
        reporting:
          csv:
            output_directory: 'experiments/{experiment_name}/eval_reports/'
    """).strip()


def _generate_llmrater_config() -> str:
    """Generates a dedicated LLM rater model configuration mimicking standard text models."""
    return textwrap.dedent("""\
        generator: gcp_vertex_gemini
        vertex_model: gemini-2.5-flash
        gcp_region: global
        base_prompt: ""
        execs_per_minute: 5
    """).strip()
