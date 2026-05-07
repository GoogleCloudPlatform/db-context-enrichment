import pytest
from common.parameterizer import (
    parameterize_sql_and_intent,
    SQLDialect,
    ValuePhrasesList,
    ValuePhrasePair,
)
from unittest.mock import patch, AsyncMock


def test_parameterize_sql_and_intent_simple():
    sql = "SELECT * FROM users WHERE name = 'John Doe'"
    intent = "Find users named John Doe"
    value_phrases = {"John Doe": ["person"]}
    result = parameterize_sql_and_intent(value_phrases, sql, intent)
    assert result["sql"] == "SELECT * FROM users WHERE name = $1"
    assert result["intent"] == "Find users named $1"


def test_parameterize_sql_and_intent_multiple():
    sql = "SELECT * FROM users WHERE name = 'John Doe' AND city = 'New York'"
    intent = "Find users named John Doe in New York"
    value_phrases = {"John Doe": ["person"], "New York": ["city"]}
    result = parameterize_sql_and_intent(value_phrases, sql, intent)
    assert result["sql"] == "SELECT * FROM users WHERE name = $1 AND city = $2"
    assert result["intent"] == "Find users named $1 in $2"


def test_parameterize_sql_and_intent_no_match():
    sql = "SELECT * FROM users WHERE name = 'Jane Doe'"
    intent = "Find users named Jane Doe"
    value_phrases = {"John Doe": ["person"]}
    result = parameterize_sql_and_intent(value_phrases, sql, intent)
    assert result["sql"] == sql
    assert result["intent"] == intent


def test_parameterize_sql_and_intent_mysql_dialect():
    sql = "SELECT * FROM users WHERE name = 'John Doe'"
    intent = "Find users named John Doe"
    value_phrases = {"John Doe": ["person"]}
    result = parameterize_sql_and_intent(
        value_phrases, sql, intent, db_dialect=SQLDialect.MYSQL
    )
    assert result["sql"] == "SELECT * FROM users WHERE name = ?"
    assert result["intent"] == "Find users named ?"


@pytest.mark.asyncio
async def test_extract_value_phrases():
    mock_response_text = '{"value_phrases": [{"key": "New York", "value": ["city"]}, {"key": "John Doe", "value": ["person"]}]}'
    expected_result = {"New York": ["city"], "John Doe": ["person"]}

    with patch("google.genai.Client") as MockClient:
        mock_instance = MockClient.return_value
        mock_instance.aio.models.generate_content = AsyncMock(
            return_value=AsyncMock(text=mock_response_text)
        )
        mock_instance.aio.aclose = AsyncMock()

        from common.parameterizer import extract_value_phrases

        result = await extract_value_phrases(
            nl_query="Find users in New York named John Doe"
        )
        assert result == expected_result
