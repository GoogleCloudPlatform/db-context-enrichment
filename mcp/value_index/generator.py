from typing import Optional
from model import context
from value_index import match_templates


def generate_value_index(
    table_name: str,
    column_name: str,
    concept_type: str,
    match_function: str,
    db_engine: str,
    db_version: Optional[str] = None,
    description: Optional[str] = None,
) -> str:
    """
    Generates a single Value Index configuration based on specific inputs.

    Args:
        table_name: The name of the table.
        column_name: The name of the column.
        concept_type: The semantic type (e.g., 'City').
        match_function: The match function to use (e.g., 'EXACT_MATCH_STRINGS').
        db_engine: The database engine (e.g., 'postgresql').
        db_version: The specific database version (optional).

    Returns:
        A JSON string representation of a ContextSet containing the generated index.
    """
    template_def = match_templates.get_match_template(
        dialect=db_engine,
        function_name=match_function,
        version=db_version,
    )
    raw_sql = template_def["sql_template"]

    # Replace {table}, {column}, {concept_type} with the user's inputs.
    # $value remains as a placeholder.
    value_index_query = raw_sql.format(
        table=table_name,
        column=column_name,
        concept_type=concept_type,
    )

    # Wrap this single index in a list because ContextSet expects a list.
    vi = context.ValueIndex(
        concept_type=concept_type,
        query=value_index_query,
        description=description,
    )

    # Return as ContextSet JSON
    return context.ContextSet(value_indices=[vi]).model_dump_json(
        indent=2, exclude_none=True
    )