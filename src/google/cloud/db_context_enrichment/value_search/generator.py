import json

from google.cloud.db_context_enrichment.model import context
from google.cloud.db_context_enrichment.value_search import match_templates


def _escape_sql_literal(val: str) -> str:
    """Escapes single quotes for SQL string literals."""
    if not isinstance(val, str):
        return str(val)
    return val.replace("'", "''")


def _escape_identifier(val: str, dialect: str) -> str:
    """Escapes identifier characters based on the database dialect."""
    if not isinstance(val, str):
        return str(val)
    if dialect.lower() in ("postgresql", "postgres"):
        return val.replace('"', '""')
    return val.replace("`", "``")


def generate_value_searches(
    value_search_inputs_json: str,
    db_engine: str,
    db_version: str | None = None,
) -> str:
    """
    Generates a list of Value Search configurations based on a JSON input list.

    Args:
        value_search_inputs_json: A JSON string representing a list of dictionaries.
            Each dictionary must contain:
            - table_name (str)
            - column_name (str)
            - concept_type (str)
            - match_function (str)
            - description (str, optional)
        db_engine: The database engine (e.g., 'postgresql', 'bigtable', 'googlesql', 'mysql').
        db_version: The specific database version (optional).

    Returns:
        A JSON string representation of a ContextSet containing all generated value searches.
    """
    try:
        inputs = json.loads(value_search_inputs_json)
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"Invalid JSON format: {str(e)}"})

    if not isinstance(inputs, list):
        return json.dumps(
            {"error": "value_search_inputs_json must be a JSON list of objects"}
        )

    value_searches = []

    for index, item in enumerate(inputs):
        if not isinstance(item, dict):
            return json.dumps({"error": f"Item at index {index} must be a dictionary"})

        required_fields = [
            "table_name",
            "column_name",
            "concept_type",
            "match_function",
        ]
        for field in required_fields:
            if not item.get(field):
                return json.dumps(
                    {"error": f"Field '{field}' is missing at index {index}"}
                )

        table_name = str(item.get("table_name"))
        column_name = str(item.get("column_name"))
        concept_type = str(item.get("concept_type"))
        match_function = str(item.get("match_function"))
        description = item.get("description")

        try:
            template_def = match_templates.get_match_template(
                dialect=db_engine,
                function_name=match_function,
                version=db_version,
            )
            raw_sql = template_def["sql_template"]

            # Prepare safely escaped formatting arguments
            format_args = {
                # Distinct placeholders for identifiers and literals
                "table_ident": _escape_identifier(table_name, db_engine),
                "column_ident": _escape_identifier(column_name, db_engine),
                "table_lit": _escape_sql_literal(table_name),
                "column_lit": _escape_sql_literal(column_name),
                "concept_type": _escape_sql_literal(concept_type),
                "column_tokens_ident": _escape_identifier(
                    str(item.get("column_tokens", "")), db_engine
                ),
                "column_tokens_lit": _escape_sql_literal(
                    str(item.get("column_tokens", ""))
                ),
                "column_embedding_ident": _escape_identifier(
                    str(item.get("column_embedding", "")), db_engine
                ),
                "column_embedding_lit": _escape_sql_literal(
                    str(item.get("column_embedding", ""))
                ),
                # Fallback for templates using plain {table} and {column}
                "table": _escape_identifier(table_name, db_engine),
                "column": _escape_identifier(column_name, db_engine),
                "column_tokens": _escape_identifier(
                    str(item.get("column_tokens", "")), db_engine
                ),
                "column_embedding": _escape_identifier(
                    str(item.get("column_embedding", "")), db_engine
                ),
            }

            value_search_query = raw_sql.format(**format_args)

            vs = context.ValueSearch(
                concept_type=concept_type,
                query=value_search_query,
                description=description,
            )
            value_searches.append(vs)

        except ValueError as e:
            return json.dumps(
                {
                    "error": f"Error while processing value search at index {index}: {str(e)}"
                }
            )

    return context.ContextSet(value_searches=value_searches).model_dump_json(
        indent=2, exclude_none=True
    )
