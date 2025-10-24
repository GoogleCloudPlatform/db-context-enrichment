from pydantic import BaseModel, Field
from typing import List
import textwrap
from google import genai
from google.genai import types


class Parameterized(BaseModel):
    """Defines the parameterized version of a SQL query and intent."""

    parameterized_sql: str = Field(
        ..., description="The SQL query with placeholders (eg., $1)."
    )
    parameterized_intent: str = Field(
        ..., description="The natural language intent with placeholders."
    )


class Template(BaseModel):
    """Represents a single, complete template."""

    nl_query: str = Field(
        ..., description="A natural language question about the data."
    )
    sql: str = Field(..., description="The corresponding, complete SQL query.")
    intent: str = Field(..., description="The user's specific intent.")
    manifest: str = Field(
        ..., description="A general description of what the template does."
    )
    parameterized: Parameterized


class TemplateList(BaseModel):
    """A list of final Template objects."""

    templates: List[Template]


async def generate_templates_from_pairs(approved_pairs_json: str) -> str:
    """
    Generates the final, detailed templates based on user-approved question/SQL pairs.
    """
    prompt = textwrap.dedent(
        f"""
        Based on the following list of user-approved Question/SQL pairs, generate a final, detailed template for each one.

        For each pair, you must generate:
        1.  `nl_query`: The original natural language question.
        2.  `sql`: The original SQL query.
        3.  `intent`: The original user intent.
        4.  `manifest`: A general, one-sentence description of what the template does (e.g., "Lists all athletes from a given country").
        5.  `parameterized`:
            - `parameterized_sql`: The SQL query with values replaced by placeholders (e.g., `$1`, `$2`).
            - `parameterized_intent`: The intent with values replaced by placeholders.

        Here is the list of approved pairs:
        {approved_pairs_json}
        """
    )

    client = genai.Client()
    try:
        response = await client.aio.models.generate_content(
            model="gemini-2.5-pro",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=TemplateList,
            ),
        )
        if response.text:
            final_templates = TemplateList.model_validate_json(response.text)
            return final_templates.model_dump_json(indent=2)
        else:
            return '{"error": "The model did not return any text content for the final templates."}'

    except Exception as e:
        return f'{{"error": "An error occurred while generating the final templates: {str(e)}"}}'
    finally:
        client.close()
        await client.aio.aclose()
