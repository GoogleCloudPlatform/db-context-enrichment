import json
import textwrap
from typing import List, Dict
from pydantic import BaseModel, Field
from google import genai
from template import template_generator
from facet import facet_generator
from model import context

class TemplateInput(BaseModel):
    question: str
    sql: str
    intent: str

class FacetInput(BaseModel):
    intent: str
    sql_snippet: str

class BootstrapInput(BaseModel):
    template_inputs: List[TemplateInput]
    facet_inputs: List[FacetInput]

async def bootstrap_context(
    db_schema: str,
    sql_dialect: str = "postgresql"
) -> str:
    """
    Orchestrates the bootstrapping of a ContextSet from a database schema.
    """
    
    # 1. Prepare the prompt for the LLM to propose templates and facets
    prompt = textwrap.dedent(
        f"""
        Analyze the following database schema to propose a comprehensive natural language-to-SQL context.
        
        **Database Schema:**
        {db_schema}
        
        **Task:**
        Generate a curated list of:
        1. **Template Inputs**: Natural language questions mapped to complete SQL queries, and a descriptive **intent** (e.g., "Count total employees in California"). (At least 3)
        2. **Facet Inputs**: Natural language intents mapped to SQL snippets (e.g., WHERE clauses, complex expressions). (At least 3)
        
        **Quality Guidelines:**
        - Ensure SQL queries and snippets are correct and optimized for the provided schema.
        - Use clear, descriptive natural language for questions and intents.
        - For SQL dialect: {sql_dialect}.
        """
    )

    client = genai.Client()
    try:
        response = await client.aio.models.generate_content(
            model="gemini-2.5-pro",
            contents=prompt,
            config={
                "response_mime_type": "application/json",
                "response_schema": BootstrapInput,
            },
        )
        
        if not response.text:
            return json.dumps({"templates": [], "facets": []})

        proposal = BootstrapInput.model_validate_json(response.text)
        
        # 2. Leverage existing tools for parameterization
        # We call the generator functions directly
        templates_json = await template_generator.generate_templates(
            json.dumps([item.model_dump() for item in proposal.template_inputs]), sql_dialect
        )
        facets_json = await facet_generator.generate_facets(
            json.dumps([item.model_dump() for item in proposal.facet_inputs]), sql_dialect
        )
        
        # 3. Merge the results
        templates_data = json.loads(templates_json)
        facets_data = json.loads(facets_json)
        
        merged_context = context.ContextSet(
            templates=templates_data.get("templates"),
            facets=facets_data.get("facets")
        )
        
        return merged_context.model_dump_json(indent=2, exclude_none=True)

    finally:
        await client.aio.aclose()
