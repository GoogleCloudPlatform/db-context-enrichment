import pytest
import yaml

from google.cloud.db_context_enrichment.evaluate.db_generators.alloydb import (
    AlloyDBConfigGenerator,
)
from google.cloud.db_context_enrichment.evaluate.db_generators.base import (
    BaseDBConfigGenerator,
)


class DummyDictGenerator(BaseDBConfigGenerator):
    SOURCE_TYPE = "dummy"
    DIALECT = "dummy_sql"
    REQUIRED_FIELDS = ["project"]

    def generate_db_config(self) -> str:
        return "db_type: dummy"

    def build_datasource_reference(self, context_set_id: str):
        return {"dummy_reference": {"custom_field": "test_value"}}


def test_base_generator_validation_missing_fields():
    # BaseDBConfigGenerator validate() method is strictly enforced natively during object construction
    # We verify the Abstract Base class cleanly intercepts broken configurations using a dummy subclass
    bad_params = {"toolbox_source_type": "alloydb-postgres", "project": "test-project"}
    with pytest.raises(
        ValueError,
        match="Missing required fields in tools.yaml config for 'alloydb-postgres':",
    ):
        AlloyDBConfigGenerator(bad_params)


def test_base_generator_dict_datasource_reference():
    generator = DummyDictGenerator({"project": "test-proj", "region": "us-central1"})
    yaml_out = generator.generate_model_config(context_set_id="")
    parsed = yaml.safe_load(yaml_out)

    assert parsed["generator"] == "query_data_api"
    assert parsed["project_id"] == "test-proj"
    assert parsed["location"] == "us-central1"
    assert parsed["context"]["datasource_references"] == {
        "dummy_reference": {"custom_field": "test_value"}
    }

