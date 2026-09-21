"""
Contract Test Suite: Custom Database Engine SPI Extension Surface.

This suite tests the public extension contracts for client teams integrating
custom database engines and model generators into AutoCtx:

1. Option 1 (Config-Driven SPI via tools.yaml):
   Client teams declare type: custom with connector_class and/or generator_class.
   AutoCtx must forward all custom connection parameters without loss or rejection.

2. Option 2 (External Package SPI via AUTOCTX_CUSTOM_GENERATORS):
   External partner packages subclass BaseDBConfigGenerator and register via env var.
   AutoCtx must dynamically discover the engine, validate, and execute the full
   evalbench config generation pipeline end-to-end.

These tests serve as an automated CI safety net: any breaking changes to the
public contract or BaseDBConfigGenerator interface will fail this suite in CI.
"""

import json
import textwrap
import types
from typing import Any
from unittest.mock import mock_open, patch

import pytest
import yaml

from google.cloud.db_context_enrichment.evaluate.db_generators.base import (
    BaseDBConfigGenerator,
)
from google.cloud.db_context_enrichment.evaluate.evaluate_generator import (
    generate_evalbench_configs,
)


# ==============================================================================
# Option 1: Config-Driven SPI Contract (tools.yaml)
# ==============================================================================


def test_contract_option1_config_driven_full_pipeline():
    """
    Contract: Client team provides type: custom with arbitrary parameters.
    AutoCtx must:
    - Retain and forward ALL custom parameters into db_config.yaml
    - Forward custom parameters into model_config.yaml
    - Set the correct dialect in run_config.yaml and golden_queries.json
    """
    tools_yaml = textwrap.dedent("""\
        kind: source
        name: client-custom-db
        type: custom
        connector_class: client_pkg.connectors.F1DB
        generator_class: client_pkg.generators.F1ModelGen
        dialect: googlesql
        server: /f1/query/prod
        database_name: default
        custom_deadline_ms: 15000
        auth_mode: internal_cert
        max_executions_per_minute: 200
    """).strip()

    dummy_dataset = json.dumps([
        {
            "id": "q001",
            "database": "default",
            "nlq": "Count all active accounts",
            "golden_sql": "SELECT COUNT(1) FROM accounts WHERE active = true",
        }
    ])

    written_files = {}

    def capture_open(path, mode="r", *args, **kwargs):
        if "tools.yaml" in str(path):
            return mock_open(read_data=tools_yaml)()
        if "dataset.json" in str(path):
            return mock_open(read_data=dummy_dataset)()
        # Capture generated output files
        m = mock_open()()
        m.write.side_effect = lambda content: written_files.update({str(path): content})
        return m

    with patch("builtins.open", side_effect=capture_open):
        with patch("google.cloud.db_context_enrichment.evaluate.evaluate_generator.os.makedirs"):
            generate_evalbench_configs(
                output_dir="/eval_output",
                dataset_path="/data/dataset.json",
                context_set_id="projects/p1/locations/l1/contextSets/cs1",
                toolbox_config_path="/configs/tools.yaml",
                toolbox_source_name="client-custom-db",
            )

    # 1. Verify db_config.yaml contract
    db_config_path = next(p for p in written_files if p.endswith("db_config.yaml"))
    db_config = yaml.safe_load(written_files[db_config_path])

    assert db_config["db_type"] == "custom"
    assert db_config["connector_class"] == "client_pkg.connectors.F1DB"
    assert db_config["dialect"] == "googlesql"
    assert db_config["server"] == "/f1/query/prod"
    assert db_config["database_name"] == "default"
    assert db_config["custom_deadline_ms"] == 15000
    assert db_config["auth_mode"] == "internal_cert"
    assert db_config["max_executions_per_minute"] == 200

    # 2. Verify model_config.yaml contract
    model_config_path = next(p for p in written_files if p.endswith("model_config.yaml"))
    model_config = yaml.safe_load(written_files[model_config_path])

    assert model_config["generator"] == "custom"
    assert model_config["generator_class"] == "client_pkg.generators.F1ModelGen"
    assert model_config["context_set_id"] == "projects/p1/locations/l1/contextSets/cs1"
    assert model_config["server"] == "/f1/query/prod"

    # 3. Verify run_config.yaml contract
    run_config_path = next(p for p in written_files if p.endswith("run_config.yaml"))
    run_config = yaml.safe_load(written_files[run_config_path])
    assert run_config["dialect"] == "googlesql"

    # 4. Verify golden_queries.json conversion contract
    golden_path = next(p for p in written_files if p.endswith("golden_queries.json"))
    golden_data = json.loads(written_files[golden_path])
    assert golden_data[0]["dialects"] == ["googlesql"]
    assert "googlesql" in golden_data[0]["golden_sql"]


def test_contract_option1_connector_only_query_data_api_fallback():
    """
    Contract: If client specifies connector_class without generator_class,
    AutoCtx must fall back cleanly to query_data_api with empty datasource_references.
    """
    tools_yaml = textwrap.dedent("""\
        kind: source
        name: client-db-only
        type: custom
        connector_class: client_pkg.connectors.CustomConnector
        dialect: custom_sql
        server: /endpoint
    """).strip()

    dummy_dataset = json.dumps([
        {
            "id": "q1",
            "database": "db1",
            "nlq": "Find all users",
            "golden_sql": "SELECT * FROM users",
        }
    ])

    written_files = {}

    def capture_open(path, *args, **kwargs):
        if "tools.yaml" in str(path):
            return mock_open(read_data=tools_yaml)()
        if "dataset.json" in str(path):
            return mock_open(read_data=dummy_dataset)()
        m = mock_open()()
        m.write.side_effect = lambda content: written_files.update({str(path): content})
        return m

    with patch("builtins.open", side_effect=capture_open):
        with patch("google.cloud.db_context_enrichment.evaluate.evaluate_generator.os.makedirs"):
            generate_evalbench_configs(
                output_dir="/eval_output",
                dataset_path="/data/dataset.json",
                context_set_id="projects/p/locations/l/contextSets/c",
                toolbox_config_path="/configs/tools.yaml",
                toolbox_source_name="client-db-only",
            )

    model_config_path = next(p for p in written_files if p.endswith("model_config.yaml"))
    model_config = yaml.safe_load(written_files[model_config_path])
    assert model_config["generator"] == "query_data_api"
    assert model_config["datasource_references"] == []


# ==============================================================================
# Option 2: External Package SPI Contract (AUTOCTX_CUSTOM_GENERATORS)
# ==============================================================================


def test_contract_option2_external_package_spi_end_to_end(monkeypatch):
    """
    Contract: External client/partner package subclasses BaseDBConfigGenerator
    and exposes a CUSTOM_GENERATORS dictionary. When AUTOCTX_CUSTOM_GENERATORS
    points to this module:
    - AutoCtx recognizes the new source type (e.g., 'snowflake_enterprise')
    - Custom validation runs and enforces REQUIRED_FIELDS
    - Custom generate_db_config and build_datasource_reference are called
    - Generated configurations match the external package's exact output
    """

    class ExternalSnowflakeGenerator(BaseDBConfigGenerator):
        SOURCE_TYPE = "snowflake_enterprise"
        DIALECT = "snowflake"
        REQUIRED_FIELDS = {"account", "warehouse", "database"}

        def generate_db_config(self) -> str:
            return yaml.safe_dump({
                "db_type": "snowflake",
                "dialect": self.DIALECT,
                "account_id": self.params["account"],
                "warehouse": self.params["warehouse"],
                "database_name": self.params["database"],
                "max_executions_per_minute": 120,
            })

        def build_datasource_reference(self, context_set_id: str) -> dict[str, Any]:
            return {
                "snowflake_reference": {
                    "account_id": self.params["account"],
                    "database_id": self.params["database"],
                }
            }

    # Simulate an external third-party python package
    mock_partner_pkg = types.ModuleType("partner_snowflake_extension")
    mock_partner_pkg.CUSTOM_GENERATORS = {
        "snowflake_enterprise": ExternalSnowflakeGenerator,
    }

    monkeypatch.setenv("AUTOCTX_CUSTOM_GENERATORS", "partner_snowflake_extension")

    tools_yaml = textwrap.dedent("""\
        kind: source
        name: my-snowflake-dw
        type: snowflake_enterprise
        account: xy99881
        warehouse: ANALYTICS_WH
        database: PROD_DB
    """).strip()

    dummy_dataset = json.dumps([
        {
            "id": "q100",
            "database": "PROD_DB",
            "nlq": "Total revenue this quarter",
            "golden_sql": "SELECT SUM(revenue) FROM sales",
        }
    ])

    written_files = {}

    def capture_open(path, *args, **kwargs):
        if "tools.yaml" in str(path):
            return mock_open(read_data=tools_yaml)()
        if "dataset.json" in str(path):
            return mock_open(read_data=dummy_dataset)()
        m = mock_open()()
        m.write.side_effect = lambda content: written_files.update({str(path): content})
        return m

    with patch("importlib.import_module", return_value=mock_partner_pkg):
        with patch("builtins.open", side_effect=capture_open):
            with patch("google.cloud.db_context_enrichment.evaluate.evaluate_generator.os.makedirs"):
                generate_evalbench_configs(
                    output_dir="/eval_output",
                    dataset_path="/data/dataset.json",
                    context_set_id="projects/p/locations/l/contextSets/snowflake-ctx",
                    toolbox_config_path="/configs/tools.yaml",
                    toolbox_source_name="my-snowflake-dw",
                )

    # 1. Verify db_config.yaml was produced by external generator
    db_config_path = next(p for p in written_files if p.endswith("db_config.yaml"))
    db_config = yaml.safe_load(written_files[db_config_path])
    assert db_config["db_type"] == "snowflake"
    assert db_config["dialect"] == "snowflake"
    assert db_config["account_id"] == "xy99881"
    assert db_config["warehouse"] == "ANALYTICS_WH"

    # 2. Verify model_config.yaml received external datasource reference
    model_config_path = next(p for p in written_files if p.endswith("model_config.yaml"))
    model_config = yaml.safe_load(written_files[model_config_path])
    assert model_config["generator"] == "query_data_api"
    assert model_config["datasource_references"] == [
        {
            "snowflake_reference": {
                "account_id": "xy99881",
                "database_id": "PROD_DB",
            }
        }
    ]

    # 3. Verify run_config.yaml captured dialect
    run_config_path = next(p for p in written_files if p.endswith("run_config.yaml"))
    run_config = yaml.safe_load(written_files[run_config_path])
    assert run_config["dialect"] == "snowflake"


def test_contract_option2_external_package_validation_enforced(monkeypatch):
    """
    Contract: When an external generator specifies REQUIRED_FIELDS,
    AutoCtx must enforce validation and raise ValueError with missing field names.
    """

    class StrictExternalGenerator(BaseDBConfigGenerator):
        SOURCE_TYPE = "strict_db"
        REQUIRED_FIELDS = {"mandatory_token", "cluster_id"}

        def generate_db_config(self) -> str:
            return ""

        def build_datasource_reference(self, context_set_id: str) -> dict[str, Any]:
            return {}

    mock_mod = types.ModuleType("strict_plugin")
    mock_mod.CUSTOM_GENERATORS = {"strict_db": StrictExternalGenerator}

    monkeypatch.setenv("AUTOCTX_CUSTOM_GENERATORS", "strict_plugin")

    # Incomplete tools.yaml missing mandatory_token
    tools_yaml = textwrap.dedent("""\
        kind: source
        name: broken-source
        type: strict_db
        cluster_id: c-123
    """).strip()

    with patch("importlib.import_module", return_value=mock_mod):
        with patch("builtins.open", mock_open(read_data=tools_yaml)):
            with pytest.raises(ValueError, match="Missing required fields.*mandatory_token"):
                generate_evalbench_configs(
                    output_dir="/out",
                    dataset_path="/data.json",
                    context_set_id="ctx",
                    toolbox_config_path="/tools.yaml",
                    toolbox_source_name="broken-source",
                )
