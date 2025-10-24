from pydantic import BaseModel, Field
from typing import List, Optional
import textwrap
from google import genai
from google.genai import types
from google.genai.types import HttpOptions


class QuestionSQLPair(BaseModel):
    """A pair of a natural language question and its corresponding SQL query."""

    question: str = Field(
        ..., description="The natural language question from the user."
    )
    sql: str = Field(..., description="The corresponding SQL query.")


class QuestionSQLPairs(BaseModel):
    """A list of QuestionSQLPair objects."""

    pairs: List[QuestionSQLPair]


async def generate_sql_pairs_from_schema(
    db_schema: str,
    context: Optional[str] = None,
    table_names: Optional[List[str]] = None,
    db_engine: Optional[str] = None,
    num_pairs: int = 10,
) -> str:
    """
    Generates a list of question/SQL pairs based on a database schema.

    Args:
        db_schema: A string containing the database schema.
        context: Optional user feedback or context to guide generation.
        table_names: Optional list of table names to focus on.
        db_engine: Optional name of the database engine for SQL dialect.
        num_pairs: The number of pairs to generate.

    Returns:
        A JSON string containing a list of question/SQL pairs.
    """
    prompt = textwrap.dedent(
        f"""
        Based on the following database schema, generate a list of {num_pairs} diverse and useful question and SQL query pairs.
        The user will review these pairs. Each pair should have a 'question' and a 'sql' query.
        """
    )

    if table_names:
        prompt += f"\nFocus on generating pairs related to the following tables: {', '.join(table_names)}."
    else:
        prompt += "\nGenerate pairs for all tables in the schema."

    if db_engine:
        prompt += f"\nThe SQL dialect should be for '{db_engine}'."
    else:
        prompt += "\nInfer the SQL dialect from the provided database schema."

    prompt += f"\n\n**Database Schema:**\n{db_schema}"

    if context:
        prompt += f"\n\n**Context:**\n{context}"

    client = genai.Client()
    try:
        response = await client.aio.models.generate_content(
            model="gemini-2.5-pro",
            contents=prompt,
            config={
                "response_mime_type": "application/json",
                "response_schema": QuestionSQLPairs,
            },
        )
        if response.text:
            pair_list = QuestionSQLPairs.model_validate_json(response.text)
            return pair_list.model_dump_json(indent=2)
        else:
            return '{"error": "The model did not return any text content."}'

    except Exception as e:
        return f'{{"error": "An error occurred while calling the generative model: {str(e)}"}}'
    finally:
        client.close()
        await client.aio.aclose()
