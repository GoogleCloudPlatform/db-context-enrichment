import pytest
import json
from pathlib import Path

from common.context_mutator import mutate_context_set, Mutation
from model.context import ContextSet

# Helper to load existing JSON from disk to assert correctness
def load_context_from_file(path: Path) -> dict:
    with open(path, "r") as f:
        return json.load(f)

# === TEST ADD / CREATE CASES ===

def test_add_to_new_file(tmp_path: Path):
    """Test creating a new context set file automatically when path doesn't exist."""
    file_path = tmp_path / "new_context.json"
    
    mutation = Mutation(
        operation="add",
        type="template",
        identifier={},
        value={
            "nl_query": "Test query",
            "sql": "SELECT *",
            "intent": "Test intent",
            "manifest": "Test manifest",
            "parameterized": {
                "parameterized_sql": "SELECT * FROM t",
                "parameterized_intent": "Test"
            }
        }
    )
    
    mutate_context_set(str(file_path), [mutation])
    
    # Assert
    assert file_path.exists()
    data = load_context_from_file(file_path)
    assert len(data.get("templates", [])) == 1
    assert data["templates"][0]["nl_query"] == "Test query"
    assert data["templates"][0]["parameterized"]["parameterized_sql"] == "SELECT * FROM t"

def test_add_to_existing_file(tmp_path: Path):
    """Test appending to an existing initialized context set file."""
    file_path = tmp_path / "exist_context.json"
    
    # Pre-populate an existing context
    initial_context = ContextSet(
        templates=[], 
        facets=[{
            "sql_snippet": "price > 100", 
            "intent": "expensive", 
            "manifest": "manifest",
            "parameterized": {
                "parameterized_sql_snippet": "price > {v}", 
                "parameterized_intent": "expensive {v}"
            }
        }]
    )
    file_path.write_text(initial_context.model_dump_json(exclude_none=True))
    
    mutation = Mutation(
        operation="add",
        type="value_search",
        identifier={},
        value={
            "query": "SELECT *",
            "concept_type": "City",
            "description": "City search"
        }
    )
    
    mutate_context_set(str(file_path), [mutation])
    
    # Assert
    data = load_context_from_file(file_path)
    assert len(data.get("facets", [])) == 1
    assert len(data.get("value_searches", [])) == 1
    assert data["value_searches"][0]["concept_type"] == "City"

# === TEST DELETE CASES ===

def test_delete_full_match(tmp_path: Path):
    """Test deleting an item using an exact matching identifier."""
    file_path = tmp_path / "delete_context.json"
    
    initial_context = {
        "value_searches": [
            {"query": "Q1", "concept_type": "C1", "description": "D1"},
            {"query": "Q2", "concept_type": "C2", "description": "D2"}
        ]
    }
    file_path.write_text(json.dumps(initial_context))
    
    mutation = Mutation(
        operation="delete",
        type="value_search",
        identifier={"query": "Q1", "concept_type": "C1", "description": "D1"}
    )
    
    mutate_context_set(str(file_path), [mutation])
    
    # Assert it deleted Q1 but kept Q2
    data = load_context_from_file(file_path)
    assert len(data["value_searches"]) == 1
    assert data["value_searches"][0]["query"] == "Q2"

def test_delete_partial_match(tmp_path: Path):
    """Test deleting an item using a subset partial match on the identifier."""
    file_path = tmp_path / "delete_context.json"
    
    initial_context = {
        "value_searches": [
            {"query": "Q1", "concept_type": "City"},
            {"query": "Q2", "concept_type": "State"}
        ]
    }
    file_path.write_text(json.dumps(initial_context))
    
    # Uses partial lookup (only "concept_type") which satisfies the predicate
    mutation = Mutation(
        operation="delete",
        type="value_search",
        identifier={"concept_type": "City"}
    )
    
    mutate_context_set(str(file_path), [mutation])
    
    # Assert
    data = load_context_from_file(file_path)
    assert len(data["value_searches"]) == 1
    assert data["value_searches"][0]["query"] == "Q2"

def test_delete_no_match(tmp_path: Path):
    """Test that a non-matching identifier leaves the list unchanged."""
    file_path = tmp_path / "delete_context.json"
    initial_context = {
        "value_searches": [
            {"query": "Q1", "concept_type": "City"}
        ]
    }
    file_path.write_text(json.dumps(initial_context))
    
    mutation = Mutation(
        operation="delete",
        type="value_search",
        identifier={"concept_type": "Country"}
    )
    
    mutate_context_set(str(file_path), [mutation])
    
    # Assert unchanged
    data = load_context_from_file(file_path)
    assert len(data["value_searches"]) == 1
    assert data["value_searches"][0]["concept_type"] == "City"

# === TEST UPDATE CASES ===

def test_update_partial_match(tmp_path: Path):
    """Test updating an item when identifier acts as a partial match selector."""
    file_path = tmp_path / "update_context.json"
    
    initial_context = {
        "value_searches": [
            {"query": "Q1", "concept_type": "City", "description": "old"}
        ]
    }
    file_path.write_text(json.dumps(initial_context))
    
    mutation = Mutation(
        operation="update",
        type="value_search",
        identifier={"concept_type": "City"},
        value={"query": "NEW_Q", "description": "new"}
    )
    
    mutate_context_set(str(file_path), [mutation])
    
    # Assert updated values and retained subset values
    data = load_context_from_file(file_path)
    assert len(data["value_searches"]) == 1
    updated = data["value_searches"][0]
    assert updated["query"] == "NEW_Q"
    assert updated["concept_type"] == "City"
    assert updated["description"] == "new"

# === TEST VALIDATION CASES ===

def test_invalid_mutation_raises_validation_error(tmp_path: Path):
    """Test that pushing an invalid payload for Add raises a ValueError immediately."""
    file_path = tmp_path / "valid_context.json"
    
    # Incomplete payload: value_search is missing 'concept_type'
    mutation = Mutation(
        operation="add",
        type="value_search",
        identifier={},
        value={"query": "Q1"} 
    )
    
    with pytest.raises(ValueError, match="Validation Error on mutation 0"):
        mutate_context_set(str(file_path), [mutation])
