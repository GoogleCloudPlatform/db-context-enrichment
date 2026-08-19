"""Unit tests for value search generator."""

import json
import pytest
from google.cloud.db_context_enrichment.model.context import ContextSet
from google.cloud.db_context_enrichment.value_search.generator import generate_value_searches


def test_generate_value_searches_bigtable_exact_match_success():
    """Test generating value search for Bigtable with EXACT_MATCH_STRINGS."""
    inputs = [
        {
            "table_name": "hotels",
            "column_name": "cf['location']",
            "concept_type": "City",
            "match_function": "EXACT_MATCH_STRINGS",
            "description": "Exact match for hotel location in Bigtable",
        }
    ]
    result_str = generate_value_searches(
        value_search_inputs_json=json.dumps(inputs),
        db_engine="bigtable",
    )
    data = json.loads(result_str)
    assert "error" not in data
    cs = ContextSet.model_validate(data)
    assert cs.value_searches is not None
    assert len(cs.value_searches) == 1

    vs = cs.value_searches[0]
    assert vs.concept_type == "City"
    assert vs.description == "Exact match for hotel location in Bigtable"
    assert "FROM `hotels` AS T" in vs.query
    assert "CAST(T.`cf['location']` AS STRING)" in vs.query
    assert "CAST($value AS STRING)" in vs.query
    assert "'' AS context" in vs.query


def test_generate_value_searches_bigtable_batch_multiple():
    """Test generating multiple value searches in a single batch for Bigtable."""
    inputs = [
        {
            "table_name": "hotels",
            "column_name": "cf['location']",
            "concept_type": "City",
            "match_function": "EXACT_MATCH_STRINGS",
            "description": "City search",
        },
        {
            "table_name": "hotels",
            "column_name": "cf['price_tier']",
            "concept_type": "PriceTier",
            "match_function": "EXACT_MATCH_STRINGS",
        },
    ]
    result_str = generate_value_searches(
        value_search_inputs_json=json.dumps(inputs),
        db_engine="bigtable",
    )
    data = json.loads(result_str)
    assert "error" not in data
    cs = ContextSet.model_validate(data)
    assert cs.value_searches is not None
    assert len(cs.value_searches) == 2
    assert cs.value_searches[0].concept_type == "City"
    assert cs.value_searches[1].concept_type == "PriceTier"
    assert cs.value_searches[1].description is None


def test_generate_value_searches_empty_input_list():
    """Test generating value searches with empty input list."""
    result_str = generate_value_searches(
        value_search_inputs_json="[]",
        db_engine="bigtable",
    )
    data = json.loads(result_str)
    assert "error" not in data
    cs = ContextSet.model_validate(data)
    assert cs.value_searches == []


def test_generate_value_searches_invalid_json():
    """Test error handling when input is malformed JSON."""
    result_str = generate_value_searches(
        value_search_inputs_json="not-valid-json",
        db_engine="bigtable",
    )
    data = json.loads(result_str)
    assert "error" in data
    assert "Invalid JSON format" in data["error"]


@pytest.mark.parametrize(
    "missing_field",
    ["table_name", "column_name", "concept_type", "match_function"],
)
def test_generate_value_searches_missing_required_field(missing_field: str):
    """Test error handling when a required field is missing in input dictionary."""
    valid_input = {
        "table_name": "hotels",
        "column_name": "cf['location']",
        "concept_type": "City",
        "match_function": "EXACT_MATCH_STRINGS",
    }
    del valid_input[missing_field]

    result_str = generate_value_searches(
        value_search_inputs_json=json.dumps([valid_input]),
        db_engine="bigtable",
    )
    data = json.loads(result_str)
    assert "error" in data
    assert f"Field '{missing_field}' is missing at index 0" in data["error"]


def test_generate_value_searches_unsupported_dialect():
    """Test error handling when db_engine is not supported."""
    inputs = [
        {
            "table_name": "hotels",
            "column_name": "location",
            "concept_type": "City",
            "match_function": "EXACT_MATCH_STRINGS",
        }
    ]
    result_str = generate_value_searches(
        value_search_inputs_json=json.dumps(inputs),
        db_engine="unsupported_engine",
    )
    data = json.loads(result_str)
    assert "error" in data
    assert "Dialect 'unsupported_engine' not supported" in data["error"]


def test_generate_value_searches_unsupported_function_for_bigtable():
    """Test error handling when a match function is unsupported in Bigtable (e.g. trigram)."""
    inputs = [
        {
            "table_name": "hotels",
            "column_name": "cf['name']",
            "concept_type": "HotelName",
            "match_function": "TRIGRAM_STRING_MATCH",
        }
    ]
    result_str = generate_value_searches(
        value_search_inputs_json=json.dumps(inputs),
        db_engine="bigtable",
    )
    data = json.loads(result_str)
    assert "error" in data
    assert "TRIGRAM_STRING_MATCH" in data["error"]
    assert "EXACT_MATCH_STRINGS" in data["error"]


def test_generate_value_searches_postgres_support():
    """Test value search generation for PostgreSQL to ensure multi-dialect compatibility."""
    inputs = [
        {
            "table_name": "users",
            "column_name": "username",
            "concept_type": "Username",
            "match_function": "EXACT_MATCH_STRINGS",
        }
    ]
    result_str = generate_value_searches(
        value_search_inputs_json=json.dumps(inputs),
        db_engine="postgresql",
    )
    data = json.loads(result_str)
    assert "error" not in data
    cs = ContextSet.model_validate(data)
    assert cs.value_searches is not None
    assert len(cs.value_searches) == 1
    assert "FROM \"users\" T" in cs.value_searches[0].query


def test_generate_value_searches_non_list_json():
    """Test error handling when input JSON is an object instead of a list."""
    result_str = generate_value_searches(
        value_search_inputs_json='{"table_name": "hotels"}',
        db_engine="bigtable",
    )
    data = json.loads(result_str)
    assert "error" in data
    assert "must be a JSON list of objects" in data["error"]


def test_generate_value_searches_non_dict_element():
    """Test error handling when list contains non-dictionary elements."""
    result_str = generate_value_searches(
        value_search_inputs_json='["invalid_item"]',
        db_engine="bigtable",
    )
    data = json.loads(result_str)
    assert "error" in data
    assert "must be a dictionary" in data["error"]


def test_generate_value_searches_escaping_quotes_and_backticks():
    """Test that single quotes in literals and backticks in identifiers are escaped."""
    inputs = [
        {
            "table_name": "hotel`table",
            "column_name": "cf['city']",
            "concept_type": "Hotel's City",
            "match_function": "EXACT_MATCH_STRINGS",
        }
    ]
    result_str = generate_value_searches(
        value_search_inputs_json=json.dumps(inputs),
        db_engine="bigtable",
    )
    data = json.loads(result_str)
    assert "error" not in data
    cs = ContextSet.model_validate(data)
    assert len(cs.value_searches) == 1
    query = cs.value_searches[0].query
    # Identifier backtick doubled
    assert "FROM `hotel``table` AS T" in query
    # Literal single quote doubled
    assert "'Hotel''s City' AS concept_type" in query

