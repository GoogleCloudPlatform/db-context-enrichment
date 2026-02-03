from typing import Optional
from model import context
from value_search import match_templates


def generate_value_search(
    table_name: str,
    column_name: str,
    concept_type: str,
    match_function: str,
    db_engine: str,
    db_version: Optional[str] = None,
    description: Optional[str] = None,
) -> str:
    """
    Generates a single Value Search configuration based on specific inputs.

    Args:
        table_name: The name of the table.
        column_name: The name of the column.
        concept_type: The semantic type (e.g., 'City').
        match_function: The match function to use (e.g., 'EXACT_MATCH_STRINGS').
        db_engine: The database engine (e.g., 'postgresql').
        db_version: The specific database version (optional).

    Returns:
        A JSON string representation of a ContextSet containing the generated value search.
    """
    template_def = match_templates.get_match_template(
        dialect=db_engine,
        function_name=match_function,
        version=db_version,
    )
    raw_sql = template_def["sql_template"]

    # Replace {table}, {column}, {concept_type} with the user's inputs.
    # $value remains as a placeholder.
    value_search_query = raw_sql.format(
        table=table_name,
        column=column_name,
        concept_type=concept_type,
    )

    # Wrap this single value search in a list because ContextSet expects a list.
    vs = context.ValueSearch(
        concept_type=concept_type,
        query=value_search_query,
        description=description,
    )

    # Return as ContextSet JSON
    return context.ContextSet(value_searches=[vs]).model_dump_json(
        indent=2, exclude_none=True
    )