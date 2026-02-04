import json
from typing import Optional
from model import context
from value_search import match_templates
import json
from typing import List, Dict, Any

def generate_value_searches(
    value_search_inputs_json: str,
    db_engine: str,
    db_version: Optional[str] = None,
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
        db_engine: The database engine (e.g., 'postgresql').
        db_version: The specific database version (optional).

    Returns:
        A JSON string representation of a ContextSet containing all generated value searches.
    """
    try:
        inputs: List[Dict[str, Any]] = json.loads(value_search_inputs_json)
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"Invalid JSON format: {str(e)}"})

    value_searches = []

    for item in inputs:
        table_name = item.get("table_name")
        column_name = item.get("column_name")
        concept_type = item.get("concept_type")
        match_function = item.get("match_function")
        description = item.get("description")

        if not all([table_name, column_name, concept_type, match_function]):
            continue

        try:
            template_def = match_templates.get_match_template(
                dialect=db_engine,
                function_name=match_function,
                version=db_version,
            )
            raw_sql = template_def["sql_template"]

            value_search_query = raw_sql.format(
                table=table_name,
                column=column_name,
                concept_type=concept_type,
            )

            vs = context.ValueSearch(
                concept_type=concept_type,
                query=value_search_query,
                description=description,
            )
            value_searches.append(vs)

        except ValueError as e:
            continue

    return context.ContextSet(value_searches=value_searches).model_dump_json(
        indent=2, exclude_none=True
    )