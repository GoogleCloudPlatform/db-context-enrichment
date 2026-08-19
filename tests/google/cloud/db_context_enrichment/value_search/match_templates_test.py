import pytest
from unittest.mock import patch
from google.cloud.db_context_enrichment.value_search import match_templates
from google.cloud.db_context_enrichment.value_search.match_templates import Dialect, get_match_template, get_available_functions

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
    assert "TRIGRAM_STRING_MATCH" in funcs
    assert "SEMANTIC_SIMILARITY_GEMINI" in funcs

def test_get_match_template_invalid_dialect_real():
    """
    Ensure the Enum conversion raises the correct error for bad inputs.
    """
    with pytest.raises(ValueError, match="Dialect 'oracle' not supported"):
        get_match_template("oracle", "EXACT_MATCH_STRINGS")

@pytest.fixture
def mock_config():
    return {
        Dialect.POSTGRESQL: {
            "min_version": "14",
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

def test_logic_version_higher_than_min(mock_config):
    """
    If a version is provided (16) which is > min (14), it should still work and
    fall back to defaults if no override exists.
    """
    with patch.dict(match_templates._MATCH_CONFIG, mock_config, clear=True):
        template = get_match_template("postgresql", "TEST_FUNC", version="16")
        assert template["sql_template"] == "DEFAULT_SQL"

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
    If a version is below 'min_version', it should raise a ValueError
    with the correct error message.
    """
    with patch.dict(match_templates._MATCH_CONFIG, mock_config, clear=True):
        with pytest.raises(ValueError, match="Minimum required version: 14"):
            get_match_template("postgresql", "TEST_FUNC", version="13")

def test_logic_missing_function(mock_config):
    """
    If the function name doesn't exist in defaults or overrides, raise ValueError.
    """
    with patch.dict(match_templates._MATCH_CONFIG, mock_config, clear=True):
        with pytest.raises(ValueError, match="Match function 'NON_EXISTENT' not found"):
            get_match_template("postgresql", "NON_EXISTENT")

def test_get_match_template_bigtable_real():
    """
    Ensure we can retrieve the actual default Bigtable templates.
    """
    template = get_match_template(
        dialect="bigtable",
        function_name="EXACT_MATCH_STRINGS"
    )
    assert "SELECT CAST(T.`{column}` AS STRING) AS value" in template["sql_template"]
    assert "'' AS context" in template["sql_template"]
    assert "WHERE CAST(T.`{column}` AS STRING) = CAST($value AS STRING)" in template["sql_template"]
    assert template["description"] is not None

def test_get_available_functions_bigtable():
    """
    Ensure we can list functions for Bigtable.
    """
    funcs = get_available_functions("bigtable")
    assert "EXACT_MATCH_STRINGS" in funcs
    assert len(funcs) == 1  # Only exact match is supported for now


def test_bigtable_template_formatting_success():
    template = get_match_template(
        dialect="bigtable",
        function_name="EXACT_MATCH_STRINGS"
    )
    sql_template = template["sql_template"]
    format_args = {
        "table": "my_table",
        "column": "my_column",
        "concept_type": "my_concept",
    }
    formatted_sql = sql_template.format(**format_args)

    assert "SELECT CAST(T.`my_column` AS STRING) AS value" in formatted_sql
    assert "'my_column' AS `columns`" in formatted_sql
    assert "'my_concept' AS concept_type" in formatted_sql
    assert "0 AS distance" in formatted_sql
    assert "'' AS context" in formatted_sql
    assert "FROM `my_table` AS T" in formatted_sql
    # Ensure $value is preserved as-is
    assert "WHERE CAST(T.`my_column` AS STRING) = CAST($value AS STRING)" in formatted_sql


def test_bigtable_template_formatting_special_chars():
    template = get_match_template(
        dialect="bigtable",
        function_name="EXACT_MATCH_STRINGS"
    )
    sql_template = template["sql_template"]
    # Test special characters like backticks, quotes, braces, colons, slashes
    format_args = {
        "table": "my_table`with`backticks",
        "column": "my_column'with'quotes",
        "concept_type": "concept:with/special-chars",
    }
    formatted_sql = sql_template.format(**format_args)

    assert "SELECT CAST(T.`my_column'with'quotes` AS STRING) AS value" in formatted_sql
    assert "'my_column'with'quotes' AS `columns`" in formatted_sql
    assert "'concept:with/special-chars' AS concept_type" in formatted_sql
    assert "FROM `my_table`with`backticks` AS T" in formatted_sql
    assert "WHERE CAST(T.`my_column'with'quotes` AS STRING) = CAST($value AS STRING)" in formatted_sql


def test_bigtable_template_formatting_empty_values():
    template = get_match_template(
        dialect="bigtable",
        function_name="EXACT_MATCH_STRINGS"
    )
    sql_template = template["sql_template"]
    format_args = {
        "table": "",
        "column": "",
        "concept_type": "",
    }
    formatted_sql = sql_template.format(**format_args)

    assert "SELECT CAST(T.`` AS STRING) AS value" in formatted_sql
    assert "'' AS `columns`" in formatted_sql
    assert "'' AS concept_type" in formatted_sql
    assert "FROM `` AS T" in formatted_sql
    assert "WHERE CAST(T.`` AS STRING) = CAST($value AS STRING)" in formatted_sql


def test_bigtable_template_formatting_missing_placeholders():
    template = get_match_template(
        dialect="bigtable",
        function_name="EXACT_MATCH_STRINGS"
    )
    sql_template = template["sql_template"]
    # Table name missing
    format_args = {
        "column": "my_column",
        "concept_type": "my_concept",
    }
    with pytest.raises(KeyError, match="table"):
        sql_template.format(**format_args)