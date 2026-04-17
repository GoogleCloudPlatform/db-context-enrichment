import json
import os
import re
import textwrap
import yaml
from typing import Dict, Any
from common import config

from .db_generators.base import BaseDBConfigGenerator
from .db_generators.alloydb import AlloyDBConfigGenerator
from .db_generators.spanner import SpannerConfigGenerator
from .db_generators.postgres import PostgresConfigGenerator
from .db_generators.mysql import MySQLConfigGenerator

# Constants for EvalBench configuration filenames
DB_CONFIG_NAME = "db_config.yaml"
MODEL_CONFIG_NAME = "model_config.yaml"
RUN_CONFIG_NAME = "run_config.yaml"
LLMRATER_CONFIG_NAME = "llmrater_config.yaml"
GOLDEN_QUERIES_NAME = "golden_queries.json"


def generate_evalbench_configs(
    experiment_name: str,
    dataset_path: str,
    context_set_id: str,
    toolbox_config_path: str,
    toolbox_source_name: str
) -> None:
    """
    Main entrypoint: Generates Evalbench-compatible YAML configurations natively using 
    private DB format converters and the google-cloud-geminidataanalytics API validations.
    """
    params = _extract_toolbox_params(toolbox_config_path, toolbox_source_name)
    generator = _get_db_generator(params)
    
    db_config_yaml = generator.generate_db_config()
    model_config_yaml = generator.generate_model_config(context_set_id)
    llmrater_config_yaml = _generate_llmrater_config(params.get("project"))
    run_config_yaml = _generate_run_config(experiment_name, generator.DIALECT)
    
    # Convert simplified dataset to EvalBench standard format
    golden_queries_json = _convert_dataset(dataset_path, generator.DIALECT)

    # Write all files directly
    eval_configs_dir = f"autoctx/experiments/{experiment_name}/eval_configs"
    os.makedirs(eval_configs_dir, exist_ok=True)
    
    with open(os.path.join(eval_configs_dir, DB_CONFIG_NAME), "w") as f:
        f.write(db_config_yaml)
        
    with open(os.path.join(eval_configs_dir, MODEL_CONFIG_NAME), "w") as f:
        f.write(model_config_yaml)
        
    with open(os.path.join(eval_configs_dir, RUN_CONFIG_NAME), "w") as f:
        f.write(run_config_yaml)
        
    with open(os.path.join(eval_configs_dir, LLMRATER_CONFIG_NAME), "w") as f:
        f.write(llmrater_config_yaml)
        
    with open(os.path.join(eval_configs_dir, GOLDEN_QUERIES_NAME), "w") as f:
        f.write(golden_queries_json)


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


def _generate_run_config(experiment_name: str, dialect: str) -> str:
    """Generates the main EvalBench Run Experiment scaffolding."""
    configs_dir = f"autoctx/experiments/{experiment_name}/eval_configs"
    reports_dir = f"autoctx/experiments/{experiment_name}/eval_reports"
    
    return textwrap.dedent(f"""\
        ############################################################
        ### Dataset / Eval Items
        ############################################################
        dataset_config: {configs_dir}/{GOLDEN_QUERIES_NAME}
        dataset_format: evalbench-standard-format
        database_configs:
         - {configs_dir}/{DB_CONFIG_NAME}
        dialect: {dialect}    # DB connection mapping
        query_types:
         - dql

        ############################################################
        ### Prompt and Generation Modules
        ############################################################
        model_config: {configs_dir}/{MODEL_CONFIG_NAME}
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
            model_config: {configs_dir}/{LLMRATER_CONFIG_NAME}

        ############################################################
        ### Reporting Related Configs
        ############################################################
        reporting:
          csv:
            output_directory: '{reports_dir}/'
    """).strip()


def _generate_llmrater_config(project_id: str) -> str:
    """Generates a dedicated LLM rater model configuration mimicking standard text models."""
    return textwrap.dedent(f"""\
        generator: gcp_vertex_gemini
        vertex_model: {config.get_model_name()}
        gcp_project_id: {project_id}
        gcp_region: global
        base_prompt: ""
        execs_per_minute: 20
    """).strip()


def _convert_dataset(dataset_path: str, dialect: str) -> str:
    """Reads simplified dataset and converts to EvalBench standard format."""
    try:
        with open(dataset_path, "r") as f:
            data = json.load(f)
            
        if not isinstance(data, list):
            raise ValueError("Dataset must be a JSON list.")
            
        required_keys = {"id", "nlq", "database", "golden_sql"}
        for i, entry in enumerate(data):
            if not isinstance(entry, dict):
                raise ValueError(f"Dataset entry at index {i} is not a dictionary.")
            missing = required_keys - set(entry.keys())
            if missing:
                raise ValueError(f"Dataset entry at index {i} is missing required keys: {missing}")
            
        converted = []
        for entry in data:
            converted_entry = {
                "id": entry.get("id"),
                "nl_prompt": entry.get("nlq"),
                "query_type": "DQL",
                "database": entry.get("database"),
                "dialects": [dialect],
                "golden_sql": {
                    dialect: [entry.get("golden_sql")]
                },
                "eval_query": {},
                "setup_sql": {},
                "cleanup_sql": {},
                "other": {},
                "tags": []
            }
            converted.append(converted_entry)
            
        return json.dumps(converted, indent=2)
    except Exception as e:
        raise ValueError(f"Failed to convert dataset at {dataset_path}: {e}")
