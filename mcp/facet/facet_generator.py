import json
from common import parameterizer
from model import context


async def generate_facets(
    facet_inputs_json: str, sql_dialect: str = "postgresql"
) -> str:
    """
    Generates the final, detailed facets based on user-approved items.
    """
    try:
        # Convert the string to the Enum member
        db_dialect = parameterizer.SQLDialect(sql_dialect)
    except ValueError:
        return f'{{"error": "Invalid database dialect specified: {sql_dialect}"}}'

    try:
        # The input is expected to be a direct list of items
        item_list = json.loads(facet_inputs_json)
        if not isinstance(item_list, list):
            raise json.JSONDecodeError("Input is not a list.", facet_inputs_json, 0)
    except json.JSONDecodeError:
        return '{"error": "Invalid JSON format for approved items. Expected a JSON array."}'

    final_facets = []

    for item in item_list:

        sql_snippet = item.get("sql_snippet")
        if not sql_snippet:
            return '{"error": "Each item must have a \'sql_snippet\' key."}'

        intent = item.get("intent")
        if not intent:
             return '{"error": "Each item must have an \'intent\' key."}'

        # 1. Extract value phrases from the intent (used as nl_query)
        phrases = await parameterizer.extract_value_phrases(nl_query=intent)

        # 2. Generate the manifest
        manifest = intent
        # Sort keys by length descending to replace longer phrases first
        sorted_phrases = sorted(phrases.keys(), key=len, reverse=True)
        for phrase in sorted_phrases:
            # Use the first identified type for the manifest
            phrase_type = phrases[phrase][0] if phrases[phrase] else "value"
            manifest = manifest.replace(phrase, f"a given {phrase_type}")

        # 3. Parameterize the SQL and Intent
        parameterized_result = parameterizer.parameterize_sql_and_intent(
            phrases, sql_snippet, intent, db_dialect=db_dialect
        )

        # 4. Assemble the final facet object
        facet = context.Facet(
            sql_snippet=sql_snippet,
            intent=intent,
            manifest=manifest,
            parameterized=context.ParameterizedFacet(
                parameterized_sql_snippet=parameterized_result["sql"],
                parameterized_intent=parameterized_result["intent"],
            ),
        )
        final_facets.append(facet)

    context_set = context.ContextSet(templates=None, facets=final_facets)
    return context_set.model_dump_json(indent=2, exclude_none=True)
