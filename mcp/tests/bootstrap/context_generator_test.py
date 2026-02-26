import pytest
import json
from unittest.mock import patch, AsyncMock
from bootstrap.context_generator import bootstrap_context, BootstrapInput, TemplateInput, FacetInput
from model.context import ContextSet

@pytest.fixture
def mock_genai_client():
    with patch("bootstrap.context_generator.genai.Client") as mock_client_class:
        mock_client_instance = mock_client_class.return_value
        mock_client_instance.aio.models.generate_content = AsyncMock()
        mock_client_instance.aio.aclose = AsyncMock()
        yield mock_client_instance

@pytest.mark.asyncio
async def test_bootstrap_context_success(mock_genai_client):
    # 1. Mock GenAI response
    mock_response = AsyncMock()
    mock_input = BootstrapInput(
        template_inputs=[
            TemplateInput(question="How many users?", sql="SELECT count(*) FROM users", intent="Count all users")
        ],
        facet_inputs=[
            FacetInput(intent="Active users", sql_snippet="status = 'active'")
        ]
    )
    mock_response.text = mock_input.model_dump_json()
    mock_genai_client.aio.models.generate_content.return_value = mock_response

    # 2. Mock individual generators
    with (
        patch("bootstrap.context_generator.template_generator.generate_templates", new_callable=AsyncMock) as mock_gen_templates,
        patch("bootstrap.context_generator.facet_generator.generate_facets", new_callable=AsyncMock) as mock_gen_facets
    ):
        mock_gen_templates.return_value = json.dumps({
            "templates": [{
                "nl_query": "How many users?",
                "sql": "SELECT count(*) FROM users",
                "intent": "Count all users",
                "manifest": "Count all users",
                "parameterized": {"parameterized_sql": "SELECT count(*) FROM users", "parameterized_intent": "Count all users"}
            }]
        })
        mock_gen_facets.return_value = json.dumps({
            "facets": [{
                "sql_snippet": "status = 'active'",
                "intent": "Active users",
                "manifest": "Active users",
                "parameterized": {"parameterized_sql_snippet": "status = 'active'", "parameterized_intent": "Active users"}
            }]
        })

        db_schema = "CREATE TABLE users (id INT, status TEXT);"
        result_json = await bootstrap_context(db_schema)
        result_data = ContextSet.model_validate_json(result_json)

        assert len(result_data.templates) == 1
        assert len(result_data.facets) == 1
        assert result_data.templates[0].intent == "Count all users"
        assert result_data.facets[0].intent == "Active users"

        mock_genai_client.aio.models.generate_content.assert_called_once()
        mock_gen_templates.assert_called_once()
        mock_gen_facets.assert_called_once()
        mock_genai_client.aio.aclose.assert_called_once()

@pytest.mark.asyncio
async def test_bootstrap_context_empty_response(mock_genai_client):
    mock_response = AsyncMock()
    mock_response.text = ""
    mock_genai_client.aio.models.generate_content.return_value = mock_response

    db_schema = "CREATE TABLE users (id INT);"
    result_json = await bootstrap_context(db_schema)
    result_data = json.loads(result_json)

    assert result_data["templates"] == []
    assert result_data["facets"] == []
    mock_genai_client.aio.aclose.assert_called_once()
