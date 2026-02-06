import pytest
import json
from unittest.mock import patch
from value_search.generator import generate_value_searches
from value_search import match_templates
from value_search.match_templates import Dialect
from model.context import ContextSet


def test_generate_value_searches_postgres_single():
    """
    Test generating a single standard Postgres exact match via the new JSON API.
    """
    # Construct the input as a JSON string
    input_data = [
        {
            "table_name": "users",
            "column_name": "country_code",
            "concept_type": "Country",
            "match_function": "EXACT_MATCH_STRINGS",
            "description": "Find users by country"
        }
    ]
    input_json = json.dumps(input_data)

    result_json = generate_value_searches(
        value_search_inputs_json=input_json,
        db_engine="postgresql",
    )

    # Validate JSON structure and content
    context_set = ContextSet.model_validate_json(result_json)
    
    assert context_set.value_searches is not None
    assert len(context_set.value_searches) == 1
    
    vs = context_set.value_searches[0]
    assert vs.concept_type == "Country"
    assert "users.country_code" in vs.query
    assert "$value" in vs.query


def test_generate_value_searches_batch_mixed():
    """
    Test generating MULTIPLE searches at once.
    """
    input_data = [
        # Valid Item 1
        {
            "table_name": "users",
            "column_name": "city",
            "concept_type": "City",
            "match_function": "EXACT_MATCH_STRINGS"
        },
        # Invalid Item (missing column_name) -> Should return error
        {
            "table_name": "products",
            "concept_type": "Product",
            "match_function": "EXACT_MATCH_STRINGS"
        },
        # Valid Item 2
        {
            "table_name": "products",
            "column_name": "name",
            "concept_type": "ProductName",
            "match_function": "FUZZY_MATCH_STRINGS"
        }
    ]
    
    result_json = generate_value_searches(
        value_search_inputs_json=json.dumps(input_data),
        db_engine="postgresql"
    )

    result = json.loads(result_json)
    assert "error" in result
    assert "Field 'column_name' is missing at index 1" in result["error"]


def test_generate_value_searches_invalid_dialect():
    """
    Test invalid database engine.
    Expected: Returns an error JSON.
    """
    input_data = [{
        "table_name": "t", "column_name": "c", "concept_type": "C", 
        "match_function": "EXACT_MATCH_STRINGS"
    }]
    
    result_json = generate_value_searches(
        value_search_inputs_json=json.dumps(input_data),
        db_engine="invalid_db"
    )
    
    result = json.loads(result_json)
    assert "error" in result
    assert "Dialect 'invalid_db' not supported" in result["error"]


def test_generate_value_searches_invalid_function():
    """
    Test unknown match function.
    Expected: Returns an error JSON.
    """
    input_data = [{
        "table_name": "t", "column_name": "c", "concept_type": "C", 
        "match_function": "BAD_FUNC"
    }]

    result_json = generate_value_searches(
        value_search_inputs_json=json.dumps(input_data),
        db_engine="postgresql"
    )
    
    result = json.loads(result_json)
    assert "error" in result
    assert "not found" in result["error"]


def test_generate_value_searches_malformed_json():
    """
    Test that really bad JSON returns an error object, not a ContextSet.
    """
    result_json = generate_value_searches(
        value_search_inputs_json="{ bad json ",
        db_engine="postgresql"
    )
    
    # result_json should be '{"error": "Invalid JSON format: ..."}'
    result = json.loads(result_json)
    assert "error" in result
    assert "Invalid JSON format" in result["error"]


def test_generate_value_searches_specific_version_success():
    """
    Mock the registry to test specific version override logic with the new list input.
    """
    fake_config = {
        Dialect.POSTGRESQL: {
            "supported_versions": ["99.0"],
            "defaults": {},
            "overrides": {
                "99.0": {
                    "TEST_FUNC": {
                        "sql_template": "SELECT {table}.{column} WHERE version=99",
                        "description": "Test Description"
                    }
                }
            }
        }
    }

    input_data = [{
        "table_name": "users", "column_name": "age", "concept_type": "Age", 
        "match_function": "TEST_FUNC"
    }]

    with patch.dict(match_templates._MATCH_CONFIG, fake_config, clear=True):
        result_json = generate_value_searches(
            value_search_inputs_json=json.dumps(input_data),
            db_engine="postgresql",
            db_version="99.0"
        )

        context_set = ContextSet.model_validate_json(result_json)
        assert len(context_set.value_searches) == 1
        vs = context_set.value_searches[0]
        assert "WHERE version=99" in vs.query


def test_generate_value_searches_specific_version_not_supported():
    """
    Verify strict version checking. 
    New behavior: Version error -> catches ValueError -> returns empty list.
    """
    input_data = [{
        "table_name": "t", "column_name": "c", "concept_type": "C", 
        "match_function": "EXACT_MATCH_STRINGS"
    }]

    # 999.0 is not in the real supported_versions list for postgres
    result_json = generate_value_searches(
        value_search_inputs_json=json.dumps(input_data),
        db_engine="postgresql",
        db_version="999.0"
    )
    
    result = json.loads(result_json)
    assert "error" in result
    assert "Version '999.0' is not supported" in result["error"]