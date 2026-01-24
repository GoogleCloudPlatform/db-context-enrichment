import os
import json
import pytest
from unittest.mock import patch, mock_open
from main import attach_context_set
from model.context import ContextSet


@pytest.fixture
def clean_context_set_json():
    return json.dumps(
        {
            "facets": [
                {
                    "sql_snippet": "new_snippet",
                    "intent": "new_intent",
                    "manifest": "new_manifest",
                    "parameterized": {
                        "parameterized_sql_snippet": "p_new_snippet",
                        "parameterized_intent": "p_new_intent",
                    },
                }
            ]
        }
    )


def test_attach_context_set_legacy_compatibility(tmp_path, clean_context_set_json):
    """Test attaching new context to a file with legacy 'fragment' and 'fragments' keys."""
    legacy_file = tmp_path / "legacy_context.json"
    legacy_content = {
        "fragments": [
            {
                "fragment": "old_snippet",
                "intent": "old_intent",
                "manifest": "old_manifest",
                "parameterized": {
                    "parameterized_fragment": "p_old_snippet",
                    "parameterized_intent": "p_old_intent",
                },
            }
        ]
    }
    legacy_file.write_text(json.dumps(legacy_content))

    # Call the tool
    attach_context_set.fn(
        context_set_json=clean_context_set_json, file_path=str(legacy_file)
    )

    # Verify the file was updated and migrated
    updated_content = json.loads(legacy_file.read_text())

    # Check that legacy content was correctly parsed and migrated to 'facets' and 'sql_snippet'
    assert "facets" in updated_content
    assert "fragments" not in updated_content
    assert len(updated_content["facets"]) == 2

    # Check old item (migrated)
    old_item = updated_content["facets"][0]
    assert old_item["sql_snippet"] == "old_snippet"

    # Check new item
    new_item = updated_content["facets"][1]
    assert new_item["sql_snippet"] == "new_snippet"


def test_attach_context_set_standard(tmp_path, clean_context_set_json):
    """Test attaching new context to a file with standard 'facets' key."""
    standard_file = tmp_path / "standard_context.json"
    standard_content = {
        "facets": [
            {
                "sql_snippet": "existing_snippet",
                "intent": "existing_intent",
                "manifest": "existing_manifest",
                "parameterized": {
                    "parameterized_sql_snippet": "p_existing_snippet",
                    "parameterized_intent": "p_existing_intent",
                },
            }
        ]
    }
    standard_file.write_text(json.dumps(standard_content))

    # Call the tool
    attach_context_set.fn(
        context_set_json=clean_context_set_json, file_path=str(standard_file)
    )

    # Verify the file was updated
    updated_content = json.loads(standard_file.read_text())

    assert "facets" in updated_content
    assert "fragments" not in updated_content
    assert len(updated_content["facets"]) == 2

    # Check existing item
    existing_item = updated_content["facets"][0]
    assert existing_item["sql_snippet"] == "existing_snippet"

    # Check new item
    new_item = updated_content["facets"][1]
    assert new_item["sql_snippet"] == "new_snippet"
