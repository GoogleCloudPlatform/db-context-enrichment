import re
from typing import Dict, Any, List
from pydantic import BaseModel, Field
from google import genai
import textwrap
from enum import Enum


class SQLDialect(Enum):
    """Enumeration for supported database dialects."""

    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    GOOGLESQL = "googlesql"


class ValuePhrasePair(BaseModel):
    """A key-value pair for a named entity and its types."""

    key: str = Field(..., description="The extracted named entity.")
    value: List[str] = Field(
        ..., description="A list of identified types for the entity."
    )


class ValuePhrasesList(BaseModel):
    """A list of named entity pairs."""

    value_phrases: List[ValuePhrasePair] = Field(
        ...,
        description="A list of key-value pairs, where each key is a named entity and the value is a list of its types.",
    )


async def extract_value_phrases(nl_question: str) -> Dict[str, List[str]]:
    """
    Extracts potential value phrases from a natural language question using an LLM.

    This function replicates the core logic of the `value_phrases_extractor`
    and `get_value_phrases_extractor_template` functions in `choose.sql`.
    It builds a prompt to perform named entity recognition (NER) and calls a
    generative model to extract entities based on a predefined list of types.

    Args:
        nl_question: The natural language question to analyze.

    Returns:
        A dictionary containing the extracted phrases and their types.

    Raises:
        Exception: If the model call fails or returns an invalid response.
    """
    prompt = textwrap.dedent(
        f"""
        Please extract the named entity (a real-world object, such as a person,
        location, organization, product, etc., that can be denoted with a proper name)
        from the query literally based on the following types:

        [Types]
        - country
        - city
        - email_address
        - language
        - law
        - organization
        - person
        - product
        - sport or activity
        - work of art
        - date
        - time
        - number
        - currency
        - region

        The output should be a JSON object containing a list of key-value pairs.
        Each pair should have a "key" (the extracted named entity) and a "value" (a list of its identified types).
        For example: {{"value_phrases": [{{"key": "entity1", "value": ["type1"]}}, {{"key": "entity2", "value": ["type2", "type3"]}}]}}
        DO NOT perform any spell checking or correction. If no entities are
        identified, return an empty list.

        [Query]
        {nl_question}
    """
    )

    client = genai.Client()
    try:
        response = await client.aio.models.generate_content(
            model="gemini-2.5-pro",
            contents=prompt,
            config={
                "response_mime_type": "application/json",
                "response_schema": ValuePhrasesList,
            },
        )
        if response.text:
            phrases_obj = ValuePhrasesList.model_validate_json(response.text)
            # Convert the list of pairs back to a dictionary
            return {pair.key: pair.value for pair in phrases_obj.value_phrases}
        else:
            # Return an empty dict if the model returns no text
            return {}
    except Exception as e:
        # Re-raise the exception to be handled by the caller
        raise Exception(f"An error occurred during value phrase extraction: {e}") from e
    finally:
        client.close()
        await client.aio.aclose()


def parameterize_sql_and_intent(
    value_phrases: Dict[str, Any],
    sql: str,
    intent: str,
    db_dialect: SQLDialect = SQLDialect.POSTGRESQL,
) -> Dict[str, str]:
    """
    Replaces value phrases in a SQL query and an intent string with placeholders.

    This function iterates through a dictionary of value phrases and replaces
    their occurrences in both the SQL and intent strings with positional
    parameters. The syntax of the parameters is determined by the specified
    database dialect.

    The phrases are processed in descending order of length to handle nested
    phrases correctly (e.g., "New York" before "York").

    The replacement logic handles both quoted and unquoted occurrences of the
    phrases, and it avoids replacing phrases that are already part of a
    placeholder.

    Args:
        value_phrases: A dictionary where keys are the string phrases to be
                       replaced. Values are not used.
        sql: The SQL query string to parameterize.
        intent: The natural language intent string to parameterize.
        db_dialect: The SQL dialect to use for parameterization.

    Returns:
        A dictionary containing the parameterized 'sql' and 'intent' strings.
    """
    psql = sql
    pintent = intent
    param_index = 1

    # Sort keys by length in descending order to prioritize longer matches
    sorted_phrases = sorted(value_phrases.keys(), key=len, reverse=True)

    for value in sorted_phrases:
        # Determine the placeholder based on the database dialect
        if db_dialect == SQLDialect.POSTGRESQL:
            placeholder = f"${param_index}"
        else:  # For mysql, googlesql, etc.
            placeholder = "?"

        search_phrase_quoted = f"'{value}'"
        replaced = False

        # Patterns with negative lookbehind to avoid replacing existing params
        # e.g., don't replace 'foo' in "$'foo'"
        quoted_pattern = re.compile(r"(?<!\$)" + re.escape(search_phrase_quoted))
        unquoted_pattern = re.compile(r"(?<!\$)" + r"\b" + re.escape(value) + r"\b")

        # Condition 1: Quoted in SQL, Quoted in Intent
        if quoted_pattern.search(psql) and quoted_pattern.search(pintent):
            psql = quoted_pattern.sub(placeholder, psql)
            pintent = quoted_pattern.sub(placeholder, pintent)
            replaced = True
        # Condition 2: Quoted in SQL, Unquoted in Intent
        elif quoted_pattern.search(psql) and unquoted_pattern.search(pintent):
            psql = quoted_pattern.sub(placeholder, psql)
            pintent = unquoted_pattern.sub(placeholder, pintent)
            replaced = True
        # Condition 3: Unquoted in SQL, Quoted in Intent
        elif unquoted_pattern.search(psql) and quoted_pattern.search(pintent):
            psql = unquoted_pattern.sub(placeholder, psql)
            pintent = quoted_pattern.sub(placeholder, pintent)
            replaced = True
        # Condition 4: Unquoted in SQL, Unquoted in Intent
        elif unquoted_pattern.search(psql) and unquoted_pattern.search(pintent):
            psql = unquoted_pattern.sub(placeholder, psql)
            pintent = unquoted_pattern.sub(placeholder, pintent)
            replaced = True

        if replaced:
            param_index += 1

    return {"sql": psql, "intent": pintent}
