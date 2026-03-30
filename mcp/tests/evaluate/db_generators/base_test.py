import pytest
from evaluate.db_generators.alloydb import AlloyDBGenerator

def test_base_generator_validation_missing_fields():
    # BaseDBConfigGenerator validate() method is strictly enforced natively during object construction
    # We verify the Abstract Base class cleanly intercepts broken configurations using a dummy subclass
    bad_params = {"toolbox_source_type": "alloydb-postgres", "project": "test-project"}
    with pytest.raises(ValueError, match="Missing required fields in tools.yaml config for 'alloydb-postgres':"):
        AlloyDBGenerator(bad_params)
