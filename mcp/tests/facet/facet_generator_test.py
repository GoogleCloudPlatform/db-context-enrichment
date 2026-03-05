import pytest
import json
from unittest.mock import patch, AsyncMock
from facet.facet_generator import generate_facets
from model.context import ContextSet, Facet, ParameterizedFacet


@pytest.mark.asyncio
async def test_generate_facets_from_items_simple():
    facet_inputs_json = json.dumps(
        [{"intent": "Find users in New York", "sql_snippet": "city = 'New York'"}]
    )
    mock_phrases = {"New York": ["city"]}

    with patch(
        "common.parameterizer.extract_value_phrases", new_callable=AsyncMock
    ) as mock_extract_value_phrases:
        with patch(
            "common.parameterizer.parameterize_sql_and_intent"
        ) as mock_parameterize_sql_and_intent:
            mock_extract_value_phrases.return_value = mock_phrases
            mock_parameterize_sql_and_intent.return_value = {
                "sql": "city = $1",
                "intent": "Find users in $1",
            }

            result_json = await generate_facets(facet_inputs_json)
            result_context_set = ContextSet.model_validate_json(result_json)

            assert result_context_set.facets is not None
            assert len(result_context_set.facets) == 1
            facet = result_context_set.facets[0]
            assert facet.sql_snippet == "city = 'New York'"
            assert facet.intent == "Find users in New York"
            # Manifest defaults to intent if no phrases, but here we have phrases so it helps
            assert facet.manifest == "Find users in a given city"
            assert facet.parameterized.parameterized_sql_snippet == "city = $1"
            assert facet.parameterized.parameterized_intent == "Find users in $1"

            mock_extract_value_phrases.assert_called_once_with(
                nl_query="Find users in New York"
            )
            mock_parameterize_sql_and_intent.assert_called_once()


@pytest.mark.asyncio
async def test_generate_facets_from_items_multiple_phrases():
    facet_inputs_json = json.dumps(
        [
            {
                "intent": "Find users named John Doe in New York",
                "sql_snippet": "name = 'John Doe' AND city = 'New York'",
            }
        ]
    )
    mock_phrases = {"John Doe": ["person"], "New York": ["city"]}

    with patch(
        "common.parameterizer.extract_value_phrases", new_callable=AsyncMock
    ) as mock_extract_value_phrases:
        with patch(
            "common.parameterizer.parameterize_sql_and_intent"
        ) as mock_parameterize_sql_and_intent:
            mock_extract_value_phrases.return_value = mock_phrases
            mock_parameterize_sql_and_intent.return_value = {
                "sql": "name = $1 AND city = $2",
                "intent": "Find users named $1 in $2",
            }

            result_json = await generate_facets(facet_inputs_json)
            result_context_set = ContextSet.model_validate_json(result_json)

            assert result_context_set.facets is not None
            assert len(result_context_set.facets) == 1
            facet = result_context_set.facets[0]
            assert facet.sql_snippet == "name = 'John Doe' AND city = 'New York'"
            assert facet.intent == "Find users named John Doe in New York"
            assert facet.manifest == "Find users named a given person in a given city"
            assert (
                facet.parameterized.parameterized_sql_snippet
                == "name = $1 AND city = $2"
            )
            assert (
                facet.parameterized.parameterized_intent == "Find users named $1 in $2"
            )

            mock_extract_value_phrases.assert_called_once_with(
                nl_query="Find users named John Doe in New York"
            )


@pytest.mark.asyncio
async def test_generate_facets_from_items_empty_phrases():
    facet_inputs_json = json.dumps([{"intent": "List all users", "sql_snippet": "TRUE"}])
    mock_phrases = {}

    with patch(
        "common.parameterizer.extract_value_phrases", new_callable=AsyncMock
    ) as mock_extract_value_phrases:
        with patch(
            "common.parameterizer.parameterize_sql_and_intent"
        ) as mock_parameterize_sql_and_intent:
            mock_extract_value_phrases.return_value = mock_phrases
            mock_parameterize_sql_and_intent.return_value = {
                "sql": "TRUE",
                "intent": "List all users",
            }

            result_json = await generate_facets(facet_inputs_json)
            result_context_set = ContextSet.model_validate_json(result_json)

            assert result_context_set.facets is not None
            assert len(result_context_set.facets) == 1
            facet = result_context_set.facets[0]
            assert facet.sql_snippet == "TRUE"
            assert facet.intent == "List all users"
            assert facet.manifest == "List all users"
            assert facet.parameterized.parameterized_sql_snippet == "TRUE"
            assert facet.parameterized.parameterized_intent == "List all users"

            mock_extract_value_phrases.assert_called_once_with(
                nl_query="List all users"
            )


@pytest.mark.asyncio
async def test_generate_facets_from_items_invalid_json():
    facet_inputs_json = "invalid json"
    with pytest.raises(ValueError, match="Invalid JSON format"):
        await generate_facets(facet_inputs_json)


@pytest.mark.asyncio
async def test_generate_facets_missing_intent():
    facet_inputs_json = json.dumps([{"sql_snippet": "price > 100"}])
    with pytest.raises(ValueError, match="Each item must have an 'intent' key"):
        await generate_facets(facet_inputs_json)


@pytest.mark.asyncio
async def test_generate_facets_missing_sql_snippet():
    facet_inputs_json = json.dumps([{"intent": "Some intent"}])
    with pytest.raises(ValueError, match="Each item must have a 'sql_snippet' key"):
        await generate_facets(facet_inputs_json)


@pytest.mark.asyncio
async def test_generate_facets_from_items_invalid_dialect():
    facet_inputs_json = json.dumps([{"intent": "Find users", "sql_snippet": "id = 1"}])
    with pytest.raises(ValueError, match="Invalid database dialect specified"):
        await generate_facets(
            facet_inputs_json, sql_dialect="invalid_dialect"
        )
