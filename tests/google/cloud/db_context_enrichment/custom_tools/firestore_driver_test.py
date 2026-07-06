import json
from unittest.mock import MagicMock, patch

import pytest

from google.cloud.db_context_enrichment.custom_tools.firestore_driver import (
    _flatten_schema,
    make_execute_mongodb_tool,
    make_list_collections_tool,
)


def test_flatten_schema():
    fields = {
        "title": {"stringValue": "Inception"},
        "year": {"integerValue": 2010},
        "info": {
            "valueType": "mapValue",
            "mapValue": {
                "fields": {
                    "director": {"stringValue": "Christopher Nolan"},
                    "rating": {"doubleValue": 8.8},
                }
            },
        },
    }

    columns = _flatten_schema(fields)
    column_names = [col["name"] for col in columns]

    assert "title" in column_names
    assert "year" in column_names
    assert "info.director" in column_names
    assert "info.rating" in column_names


@pytest.mark.asyncio
async def test_make_list_collections_tool():
    tool_doc = {
        "name": "test-firestore-list-schemas",
        "description": "Test list schemas",
    }
    source_info = {
        "project": "cloud-db-nl2sql",
        "database": "nl2sql-mflix",
        "collections": ["movies"],
    }

    tool_func = make_list_collections_tool(tool_doc, source_info)

    mock_response = {
        "results": [
            {
                "fields": {
                    "title": {"stringValue": "STRING"},
                    "year": {"integerValue": "INT"},
                }
            }
        ]
    }

    with patch("google.cloud.db_context_enrichment.custom_tools.firestore_driver._execute_pipeline_rest", return_value=mock_response):
        res_json = await tool_func()
        data = json.loads(res_json)

        assert isinstance(data, list)
        assert data[0]["collection"] == "movies"
        assert len(data[0]["columns"]) >= 2


@pytest.mark.asyncio
async def test_make_execute_mongodb_tool():
    tool_doc = {
        "name": "test-firestore-execute-query",
        "description": "Test execute query",
    }
    source_info = {
        "project": "cloud-db-nl2sql",
        "database": "nl2sql-mflix",
    }

    tool_func = make_execute_mongodb_tool(tool_doc, source_info)

    mock_response = {
        "results": [
            {"fields": {"title": {"stringValue": "The Matrix"}}}
        ]
    }

    with patch("google.cloud.db_context_enrichment.custom_tools.firestore_driver._execute_pipeline_rest", return_value=mock_response):
        res_json = await tool_func('{"find": "movies", "limit": 1}')
        data = json.loads(res_json)

        assert data["status"] == "SUCCESS"
        assert data["count"] == 1
