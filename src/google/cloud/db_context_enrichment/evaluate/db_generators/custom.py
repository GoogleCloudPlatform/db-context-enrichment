import os
from typing import Any

import yaml

from .base import BaseDBConfigGenerator


class CustomDBConfigGenerator(BaseDBConfigGenerator):
    """
    Pluggable generator mapping properties to custom evaluation configurations.
    Enables arbitrary third-party or proprietary internal engines to be plugged
    into the evaluation framework via dynamic connector and generator SPIs
    without exposing engine-specific code or configuration schemas.
    """

    SOURCE_TYPE = "custom"
    DIALECT = "sql"
    REQUIRED_FIELDS = set()

    def __init__(self, params: dict[str, Any]):
        self.params = params
        if "project" not in self.params:
            project_id = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get(
                "GCP_PROJECT"
            )
            if project_id:
                self.params["project"] = project_id
        self.connector_class = params.get("connector_class", "")
        self.generator_class = params.get("generator_class", "")
        self.DIALECT = params.get("dialect", self.DIALECT)
        self.validate()

    def validate(self) -> None:
        """
        Validates that either connector_class or generator_class is specified.
        """
        if not self.connector_class and not self.generator_class:
            raise ValueError(
                "Custom source configuration must specify at least 'connector_class' or 'generator_class'."
            )

    def generate_db_config(self) -> str:
        """
        Generates the db_config.yaml payload for custom connectors.
        """
        db_config: dict[str, Any] = {
            "db_type": self.params.get("db_type", "custom"),
            "dialect": self.DIALECT,
        }
        if self.connector_class:
            db_config["connector_class"] = self.connector_class

        # Forward all non-meta parameters from tools.yaml source block
        excluded_keys = {
            "kind",
            "name",
            "type",
            "connector_class",
            "generator_class",
            "dialect",
            "db_type",
        }
        for key, value in self.params.items():
            if key not in excluded_keys:
                db_config[key] = value

        return yaml.safe_dump(
            db_config, sort_keys=False, default_flow_style=False
        ).strip()

    def build_datasource_reference(self, context_set_id: str) -> dict[str, Any]:
        """
        Datasource reference dictionary. Custom engines manage their own
        schema references or context binding.
        """
        return {}

    def generate_model_config(self, context_set_id: str) -> str:
        """
        Generates model_config.yaml. If generator_class is specified, produces
        a custom generator configuration for dynamic instantiation.
        """
        if self.generator_class:
            model_config: dict[str, Any] = {
                "generator": "custom",
                "generator_class": self.generator_class,
                "context_set_id": context_set_id,
            }
            excluded_keys = {
                "kind",
                "name",
                "type",
                "connector_class",
                "generator_class",
            }
            for key, value in self.params.items():
                if key not in excluded_keys:
                    model_config[key] = value
            return yaml.safe_dump(
                model_config, sort_keys=False, default_flow_style=False
            ).strip()

        return super().generate_model_config(context_set_id)
