import pytest
import json
from unittest.mock import patch, MagicMock

from bootstrap import bootstrap_generator
from common.context_mutator import Mutation

@pytest.fixture
def valid_templates_json():
    return json.dumps({
        "templates": [
            {
                "nl_query": "Test query",
                "sql": "SELECT * FROM test",
                "intent": "Test intent",
                "manifest": "Test manifest",
                "parameterized": {
                    "parameterized_sql": "SELECT * FROM test",
                    "parameterized_intent": "Test intent"
                }
            }
        ]
    })

@pytest.fixture
def valid_facets_json():
    return json.dumps({
        "facets": [
            {
                "sql_snippet": "price > 10",
                "intent": "cheap",
                "manifest": "cheap",
                "parameterized": {
                    "parameterized_sql_snippet": "price > {v}",
                    "parameterized_intent": "cheap"
                }
            }
        ]
    })

@pytest.mark.asyncio
@patch("bootstrap.bootstrap_generator.mutate_context_set")
@patch("bootstrap.bootstrap_generator.template_generator.generate_templates")
@patch("bootstrap.bootstrap_generator.facet_generator.generate_facets")
async def test_generate_context_success_both(mock_gen_facets, mock_gen_templates, mock_mutate, valid_templates_json, valid_facets_json):
    """Test successful generation of both templates and facets."""
    mock_gen_templates.return_value = valid_templates_json
    mock_gen_facets.return_value = valid_facets_json

    out_path = "out.json"
    res = await bootstrap_generator.generate_context(out_path, "postgresql", template_inputs_json="{}", facet_inputs_json="{}")
    
    assert res == out_path
    mock_gen_templates.assert_awaited_once_with("{}", "postgresql")
    mock_gen_facets.assert_awaited_once_with("{}", "postgresql")
    
    mock_mutate.assert_called_once()
    mutations = mock_mutate.call_args[0][1]
    assert len(mutations) == 2
    assert mutations[0].type == "template"
    assert mutations[1].type == "facet"

@pytest.mark.asyncio
@patch("bootstrap.bootstrap_generator.mutate_context_set")
@patch("bootstrap.bootstrap_generator.template_generator.generate_templates")
async def test_generate_context_templates_only(mock_gen_templates, mock_mutate, valid_templates_json):
    """Test successful generation of only templates."""
    mock_gen_templates.return_value = valid_templates_json

    await bootstrap_generator.generate_context("out.json", "postgresql", template_inputs_json="{}")
    
    mock_mutate.assert_called_once()
    mutations = mock_mutate.call_args[0][1]
    assert len(mutations) == 1
    assert mutations[0].type == "template"

@pytest.mark.asyncio
@patch("bootstrap.bootstrap_generator.template_generator.generate_templates")
async def test_generate_context_template_runtime_error(mock_gen_templates):
    """Test that a generator returning an error string raises a RuntimeError."""
    mock_gen_templates.return_value = '{"error": "API failed"}'

    with pytest.raises(RuntimeError, match="Error generating templates:"):
        await bootstrap_generator.generate_context("out.json", "postgresql", template_inputs_json="{}")

@pytest.mark.asyncio
@patch("bootstrap.bootstrap_generator.template_generator.generate_templates")
async def test_generate_context_template_value_error(mock_gen_templates):
    """Test that a generator returning bad json or unparseable context raises ValueError."""
    mock_gen_templates.return_value = 'invalid json'

    with pytest.raises(ValueError, match="Error parsing generated templates:"):
        await bootstrap_generator.generate_context("out.json", "postgresql", template_inputs_json="{}")

@pytest.mark.asyncio
async def test_generate_context_no_mutations_error():
    """Test that providing no inputs raises a ValueError because no context is built."""
    with pytest.raises(ValueError, match="No templates or facets were generated to save."):
        await bootstrap_generator.generate_context("out.json", "postgresql")
