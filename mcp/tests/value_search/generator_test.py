import pytest
import json
from unittest.mock import patch
from value_search.generator import generate_value_search
from value_search import match_templates
from value_search.match_templates import Dialect
from model.context import ContextSet

def test_generate_value_search_postgres_default():
    """
    Test generating a standard Postgres exact match using real defaults.
    """
    result_json = generate_value_search(
        table_name="users",
        column_name="country_code",
        concept_type="Country",
        match_function="EXACT_MATCH_STRINGS",
        db_engine="postgresql",
    )

    # Validate JSON structure and content
    context_set = ContextSet.model_validate_json(result_json)
    
    # Check List Structure
    assert context_set.value_searches is not None
    assert len(context_set.value_searches) == 1
    
    # Check ValueSearch Object
    vs = context_set.value_searches[0]
    assert vs.concept_type == "Country"
    
    # Check SQL Parameterization
    # Should replace {table} and {column} but keep $value
    assert "users.country_code" in vs.query
    assert "FROM users T" in vs.query
    assert "$value" in vs.query


def test_generate_value_search_invalid_dialect():
    """
    Test error handling for unknown database engine.
    """
    with pytest.raises(ValueError, match="Dialect 'invalid_db' not supported"):
        generate_value_search(
            table_name="t", 
            column_name="c", 
            concept_type="C",
            match_function="EXACT_MATCH_STRINGS",
            db_engine="invalid_db"
        )


def test_generate_value_search_invalid_function():
    """
    Test error handling for unknown match function.
    """
    with pytest.raises(ValueError, match="Match function 'BAD_FUNC' not found"):
        generate_value_search(
            table_name="t", 
            column_name="c", 
            concept_type="C",
            match_function="BAD_FUNC",
            db_engine="postgresql"
        )


def test_generate_value_search_specific_version_success():
    """
    Mock the registry to test specific version override logic.
    We must mock the _MATCH_CONFIG structure exactly.
    """
    fake_config = {
        Dialect.POSTGRESQL: {
            "supported_versions": ["99.0"],
            "defaults": {
                "TEST_FUNC": {
                     "sql_template": "SELECT DEFAULT",
                     "description": "Default"
                }
            },
            "overrides": {
                "99.0": {
                    "TEST_FUNC": {
                        "sql_template": "SELECT {table}.{column} FROM {table} WHERE version=99",
                        "description": "Test Description"
                    }
                }
            }
        }
    }

    with patch.dict(match_templates._MATCH_CONFIG, fake_config, clear=True):
        result_json = generate_value_search(
            table_name="users", 
            column_name="age", 
            concept_type="Age",
            match_function="TEST_FUNC",
            db_engine="postgresql",
            db_version="99.0"
        )

        context_set = ContextSet.model_validate_json(result_json)
        vs = context_set.value_searches[0]
        
        # Ensure we got the override template, not the default
        assert "WHERE version=99" in vs.query
        assert "users.age" in vs.query


def test_generate_value_search_specific_version_not_supported():
    """
    Verify strict version checking raises an error if version is not in supported_versions.
    """
    with pytest.raises(ValueError, match="Version '999.0' is not supported"):
        generate_value_search(
            table_name="t", 
            column_name="c", 
            concept_type="C",
            match_function="EXACT_MATCH_STRINGS",
            db_engine="postgresql",
            db_version="999.0"
        )

def test_generate_value_search_fallback_to_default():
    """
    Test that if a version is supported, but has no specific override for a function,
    it falls back to the 'defaults' definition.
    """
    fake_config = {
        Dialect.POSTGRESQL: {
            "supported_versions": ["15"],
            "defaults": {
                "FALLBACK_FUNC": {
                    "sql_template": "SELECT DEFAULT FROM {table}",
                    "description": "Default"
                }
            },
            # No override for FALLBACK_FUNC in version 15
            "overrides": {
                "15": {} 
            }
        }
    }

    with patch.dict(match_templates._MATCH_CONFIG, fake_config, clear=True):
        result_json = generate_value_search(
            table_name="users", 
            column_name="name", 
            concept_type="Name",
            match_function="FALLBACK_FUNC",
            db_engine="postgresql",
            db_version="15"
        )
        
        context_set = ContextSet.model_validate_json(result_json)
        vs = context_set.value_searches[0]
        assert "SELECT DEFAULT FROM users" in vs.query