import pytest
import json
from unittest.mock import patch, AsyncMock
from template.template_generator import generate_templates_from_items
from model.context import ContextSet


@pytest.mark.asyncio
async def test_generate_templates_from_items_simple():
    template_inputs_json = json.dumps(
        [
            {
                "question": "How many users are in New York?",
                "sql": "SELECT count(*) FROM users WHERE city = 'New York'",
            }
        ]
    )
    mock_phrases = {"New York": ["city"]}

    with (
        patch(
            "common.parameterizer.extract_value_phrases", new_callable=AsyncMock
        ) as mock_extract_value_phrases,
        patch(
            "common.parameterizer.parameterize_sql_and_intent"
        ) as mock_parameterize_sql_and_intent,
    ):
        mock_extract_value_phrases.return_value = mock_phrases
        mock_parameterize_sql_and_intent.return_value = {
            "sql": "SELECT count(*) FROM users WHERE city = $1",
            "intent": "How many users are in $1?",
        }

        result_json = await generate_templates_from_items(template_inputs_json)
        result_context_set = ContextSet.model_validate_json(result_json)

        assert result_context_set.templates is not None
        assert len(result_context_set.templates) == 1
        template = result_context_set.templates[0]
        assert template.sql == "SELECT count(*) FROM users WHERE city = 'New York'"
        assert template.intent == "How many users are in New York?"
        assert template.manifest == "How many users are in a given city?"
        assert (
            template.parameterized.parameterized_sql
            == "SELECT count(*) FROM users WHERE city = $1"
        )
        assert (
            template.parameterized.parameterized_intent == "How many users are in $1?"
        )

        mock_extract_value_phrases.assert_called_once_with(
            nl_query="How many users are in New York?"
        )
        mock_parameterize_sql_and_intent.assert_called_once()


@pytest.mark.asyncio
async def test_generate_templates_from_items_invalid_json():
    template_inputs_json = "invalid json"
    result_json = await generate_templates_from_items(template_inputs_json)
    assert "error" in result_json
    assert "Invalid JSON format" in result_json


@pytest.mark.asyncio
async def test_generate_templates_from_items_invalid_dialect():
    template_inputs_json = json.dumps(
        [{"question": "Find users", "sql": "SELECT * FROM users"}]
    )
    result_json = await generate_templates_from_items(
        template_inputs_json, sql_dialect="invalid_dialect"
    )
    assert "error" in result_json
    assert "Invalid database dialect specified" in result_json


@pytest.mark.asyncio
async def test_generate_templates_from_items_with_explicit_intent():
    template_inputs_json = json.dumps(
        [
            {
                "question": "How many users?",
                "sql": "SELECT count(*) FROM users",
                "intent": "Count all users",
            }
        ]
    )
    mock_phrases = {}

    with (
        patch(
            "common.parameterizer.extract_value_phrases", new_callable=AsyncMock
        ) as mock_extract_value_phrases,
        patch(
            "common.parameterizer.parameterize_sql_and_intent"
        ) as mock_parameterize_sql_and_intent,
    ):
        mock_extract_value_phrases.return_value = mock_phrases
        mock_parameterize_sql_and_intent.return_value = {
            "sql": "SELECT count(*) FROM users",
            "intent": "Count all users",
        }

        result_json = await generate_templates_from_items(template_inputs_json)
        result_context_set = ContextSet.model_validate_json(result_json)

        assert result_context_set.templates is not None
        assert len(result_context_set.templates) == 1
        template = result_context_set.templates[0]
        assert template.intent == "Count all users"

        # Verify parameterizer was called with explicit intent
        # args match: phrases, sql, intent, db_dialect
        args, _ = mock_parameterize_sql_and_intent.call_args
        assert args[2] == "Count all users"
