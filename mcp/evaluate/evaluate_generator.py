import json
import textwrap
from typing import Dict, Any

from .db_generators.base import BaseDBConfigGenerator
from .db_generators.alloydb import AlloyDBGenerator
from .db_generators.spanner import SpannerGenerator
from .db_generators.postgres import PostgresGenerator
from .db_generators.mysql import MySQLGenerator

# Dependencies resolved externally


def generate_evalbench_configs(
    experiment_name: str,
    dataset_path: str,
    context_set_id: str,
    toolbox_db_info: str
) -> Dict[str, str]:
    """
    Main entrypoint: Generates Evalbench-compatible YAML configurations natively using 
    private DB format converters and the google-cloud-geminidataanalytics API validations.
    """
    params = _extract_toolbox_params(toolbox_db_info)
    generator = _get_db_generator(params)
    
    db_config_yaml = generator.generate_db_config()
    model_config_yaml = generator.generate_model_config(context_set_id)
    run_config_yaml = _generate_run_config(experiment_name, dataset_path, generator.DIALECT)

    return {
        "db_config.yaml": db_config_yaml,
        "model_config.yaml": model_config_yaml,
        "run_config.yaml": run_config_yaml
    }


def _extract_toolbox_params(toolbox_db_info: str) -> Dict[str, Any]:
    """Safely extracts and parses the stringified JSON payload into a connection dictionary."""
    try:
        params = json.loads(toolbox_db_info)
    except json.JSONDecodeError as e:
        raise ValueError(f"toolbox_db_info must be a valid JSON dictionary: {e}") from e
    
    source_type = params.get("type", "").lower()
    if not source_type:
        raise ValueError("Missing required field 'type' in the parsed tools.yaml")

    return params


def _get_db_generator(params: Dict[str, Any]) -> BaseDBConfigGenerator:
    """Factory function to build the correct Evaluation Generator."""
    source_type = params.get("type", "").lower()
    
    generators = {
        AlloyDBGenerator.SOURCE_TYPE: AlloyDBGenerator,
        PostgresGenerator.SOURCE_TYPE: PostgresGenerator,
        MySQLGenerator.SOURCE_TYPE: MySQLGenerator,
        SpannerGenerator.SOURCE_TYPE: SpannerGenerator,
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
        database_configs:
         - experiments/{experiment_name}/eval_configs/db_config.yaml
        dialects:
         - {dialect}
        dialect: {dialect}
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
          exact_match: null
          executable_sql: null

        ############################################################
        ### Reporting Related Configs
        ############################################################
        reporting:
          csv:
            output_directory: 'experiments/{experiment_name}/eval_reports/'
    """).strip()
