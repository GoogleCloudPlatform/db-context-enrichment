import pytest
import json
from unittest.mock import patch
from value_index.generator import generate_value_index
from value_index import match_templates
from model.context import ContextSet


def test_generate_value_index_postgres_default():
    # Test generating a standard Postgres exact match (uses default version)
    result_json = generate_value_index(
        table_name="users",
        column_name="country_code",
        concept_type="Country",
        match_function="EXACT_MATCH_STRINGS",
        db_engine="postgresql",
    )

    # Validate JSON structure and content
    context_set = ContextSet.model_validate_json(result_json)
    
    # Check List Structure
    assert context_set.value_indices is not None
    assert len(context_set.value_indices) == 1
    
    # Check ValueIndex Object
    vi = context_set.value_indices[0]
    assert vi.concept_type == "Country"
    
    # Check SQL Parameterization
    # Should replace {table} and {column} but keep $value
    assert "users.country_code" in vi.query
    assert "FROM users T" in vi.query
    assert "$value" in vi.query


def test_generate_value_index_invalid_dialect():
    # Test error handling for unknown database engine
    with pytest.raises(ValueError, match="Dialect 'invalid_db' not supported"):
        generate_value_index(
            table_name="t", 
            column_name="c", 
            concept_type="C",
            match_function="EXACT_MATCH_STRINGS",
            db_engine="invalid_db"
        )


def test_generate_value_index_invalid_function():
    # Test error handling for unknown match function
    with pytest.raises(ValueError, match="Match function 'BAD_FUNC' not found"):
        generate_value_index(
            table_name="t", 
            column_name="c", 
            concept_type="C",
            match_function="BAD_FUNC",
            db_engine="postgresql"
        )


def test_generate_value_index_specific_version_success():
    # Mock the registry to test specific version logic without relying on real data
    fake_registry = {
        "postgresql": {
            "99.0": {
                "TEST_FUNC": {
                    "sql_template": "SELECT {table}.{column} FROM {table} WHERE version=99",
                    "description": "Test Description"
                }
            }
        }
    }

    # Inject the fake registry into the module
    with patch.dict(match_templates.MATCH_TEMPLATES, fake_registry, clear=True):
        result_json = generate_value_index(
            table_name="users", 
            column_name="age", 
            concept_type="Age",
            match_function="TEST_FUNC",
            db_engine="postgresql",
            db_version="99.0"
        )

        context_set = ContextSet.model_validate_json(result_json)
        vi = context_set.value_indices[0]
        assert "WHERE version=99" in vi.query
        assert "users.age" in vi.query


def test_generate_value_index_specific_version_not_found():
    # Verify strict version checking: Should raise Error, NOT fallback to default
    with pytest.raises(ValueError, match="Version '999.0' not found"):
        generate_value_index(
            table_name="t", 
            column_name="c", 
            concept_type="C",
            match_function="EXACT_MATCH_STRINGS",
            db_engine="postgresql",
            db_version="999.0"
        )