import pytest
from unittest.mock import patch
from value_search import match_templates
from value_search.match_templates import Dialect, get_match_template, get_available_functions

def test_get_match_template_real_config_defaults():
    """
    Sanity check: Ensure we can retrieve the actual default Postgres templates
    defined in the codebase without any mocking.
    """
    template = get_match_template(
        dialect="postgresql",
        function_name="EXACT_MATCH_STRINGS"
    )
    assert "SELECT $value as value" in template["sql_template"]
    assert template["description"] is not None

def test_get_available_functions_postgres():
    """
    Ensure we can list functions for Postgres.
    """
    funcs = get_available_functions("postgresql")
    assert "EXACT_MATCH_STRINGS" in funcs
    assert "FUZZY_MATCH_STRINGS" in funcs

def test_get_match_template_invalid_dialect_real():
    """
    Ensure the Enum conversion raises the correct error for bad inputs.
    """
    with pytest.raises(ValueError, match="Dialect 'mysql' not supported"):
        get_match_template("mysql", "EXACT_MATCH_STRINGS")

@pytest.fixture
def mock_config():
    return {
        Dialect.POSTGRESQL: {
            "supported_versions": ["14", "15"],
            "defaults": {
                "TEST_FUNC": {"sql_template": "DEFAULT_SQL", "desc": "default"},
                "ONLY_DEFAULT": {"sql_template": "DEFAULT_ONLY", "desc": "default"}
            },
            "overrides": {
                "15": {
                    "TEST_FUNC": {"sql_template": "OVERRIDE_SQL_15", "desc": "override"}
                }
            }
        }
    }

def test_logic_fallback_to_default(mock_config):
    """
    If a version is provided (14) but it has no override for the requested function,
    it should return the default template.
    """
    with patch.dict(match_templates._MATCH_CONFIG, mock_config, clear=True):
        template = get_match_template("postgresql", "TEST_FUNC", version="14")
        assert template["sql_template"] == "DEFAULT_SQL"

def test_logic_version_override(mock_config):
    """
    If a version is provided (15) and it HAS an override, return the override.
    """
    with patch.dict(match_templates._MATCH_CONFIG, mock_config, clear=True):
        template = get_match_template("postgresql", "TEST_FUNC", version="15")
        assert template["sql_template"] == "OVERRIDE_SQL_15"

def test_logic_partial_override(mock_config):
    """
    If version 15 is requested, but we ask for a function that isn't overridden
    (ONLY_DEFAULT), it should still fall back to default correctly.
    """
    with patch.dict(match_templates._MATCH_CONFIG, mock_config, clear=True):
        template = get_match_template("postgresql", "ONLY_DEFAULT", version="15")
        assert template["sql_template"] == "DEFAULT_ONLY"

def test_logic_unsupported_version(mock_config):
    """
    If a version is not in 'supported_versions', it should raise a ValueError
    before even checking templates.
    """
    with patch.dict(match_templates._MATCH_CONFIG, mock_config, clear=True):
        with pytest.raises(ValueError, match="Version '99' is not supported"):
            get_match_template("postgresql", "TEST_FUNC", version="99")

def test_logic_missing_function(mock_config):
    """
    If the function name doesn't exist in defaults or overrides, raise ValueError.
    """
    with patch.dict(match_templates._MATCH_CONFIG, mock_config, clear=True):
        with pytest.raises(ValueError, match="Match function 'NON_EXISTENT' not found"):
            get_match_template("postgresql", "NON_EXISTENT")