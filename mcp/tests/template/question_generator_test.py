import pytest
import json
from unittest.mock import patch, AsyncMock
from template.question_generator import (
    generate_sql_pairs,
    QuestionSQLPairs,
    QuestionSQLPair,
)


@pytest.fixture
def mock_genai_client():
    with patch("template.question_generator.genai.Client") as mock_client_class:
        mock_client_instance = mock_client_class.return_value
        mock_client_instance.aio.models.generate_content = AsyncMock()
        mock_client_instance.aio.aclose = AsyncMock()
        yield mock_client_instance


@pytest.mark.asyncio
async def test_generate_sql_pairs_success(mock_genai_client):
    mock_response = AsyncMock()
    mock_response.text = QuestionSQLPairs(
        pairs=[
            QuestionSQLPair(
                question="What is the total number of users?",
                sql="SELECT count(*) FROM users",
            ),
            QuestionSQLPair(
                question="List all users from California.",
                sql="SELECT * FROM users WHERE state = 'California'",
            ),
        ]
    ).model_dump_json()
    mock_genai_client.aio.models.generate_content.return_value = mock_response

    db_schema = '{"users": ["id", "name", "state"]}'
    result_json = await generate_sql_pairs(db_schema)
    result_data = json.loads(result_json)

    assert len(result_data) == 2
    assert result_data[0]["question"] == "What is the total number of users?"
    mock_genai_client.aio.models.generate_content.assert_called_once()
    mock_genai_client.aio.aclose.assert_called_once()


@pytest.mark.asyncio
async def test_generate_sql_pairs_api_error(mock_genai_client):
    mock_genai_client.aio.models.generate_content.side_effect = Exception("API Error")

    db_schema = '{"users": ["id", "name", "state"]}'
    with pytest.raises(
        Exception,
        match="An error occurred while calling the generative model: API Error",
    ):
        await generate_sql_pairs(db_schema)
    mock_genai_client.aio.aclose.assert_called_once()


@pytest.mark.asyncio
async def test_generate_sql_pairs_empty_response(mock_genai_client):
    mock_response = AsyncMock()
    mock_response.text = ""
    mock_genai_client.aio.models.generate_content.return_value = mock_response

    db_schema = '{"users": ["id", "name", "state"]}'
    result_json = await generate_sql_pairs(db_schema)

    assert result_json == "[]"
    mock_genai_client.aio.aclose.assert_called_once()


@pytest.mark.asyncio
async def test_generate_sql_pairs_with_context(mock_genai_client):
    mock_response = AsyncMock()
    mock_response.text = QuestionSQLPairs(pairs=[]).model_dump_json()
    mock_genai_client.aio.models.generate_content.return_value = mock_response

    db_schema = '{"users": ["id", "name", "state"]}'
    context = "Focus on aggregation queries."
    await generate_sql_pairs(db_schema, context=context)

    mock_genai_client.aio.models.generate_content.assert_called_once()
    prompt = mock_genai_client.aio.models.generate_content.call_args[1]["contents"]
    assert context in prompt
    mock_genai_client.aio.aclose.assert_called_once()
