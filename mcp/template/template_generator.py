import json
from common import parameterizer
from model import context


async def generate_templates_from_items(
    template_inputs_json: str, sql_dialect: str = "postgresql"
) -> str:
    """
    Generates the final, detailed templates based on user-approved items.
    """
    try:
        # Convert the string to the Enum member
        db_dialect = parameterizer.SQLDialect(sql_dialect)
    except ValueError:
        return f'{{"error": "Invalid database dialect specified: {sql_dialect}"}}'

    try:
        # The input is now expected to be a direct list of items
        item_list = json.loads(template_inputs_json)
        if not isinstance(item_list, list):
            raise json.JSONDecodeError("Input is not a list.", template_inputs_json, 0)
    except json.JSONDecodeError:
        return '{"error": "Invalid JSON format for approved items. Expected a JSON array."}'

    final_templates = []

    for item in item_list:
        question = item["question"]
        sql = item["sql"]
        intent = item.get("intent", question)  # Use provided intent or fallback to question

        # 1. Extract value phrases from the question
        phrases = await parameterizer.extract_value_phrases(nl_query=question)

        # 2. Generate the manifest
        manifest = question
        # Sort keys by length descending to replace longer phrases first
        sorted_phrases = sorted(phrases.keys(), key=len, reverse=True)
        for phrase in sorted_phrases:
            # Use the first identified type for the manifest
            phrase_type = phrases[phrase][0] if phrases[phrase] else "value"
            manifest = manifest.replace(phrase, f"a given {phrase_type}")

        # 3. Parameterize the SQL and Intent
        parameterized_result = parameterizer.parameterize_sql_and_intent(
            phrases, sql, intent, db_dialect=db_dialect
        )

        # 4. Assemble the final template object
        template = context.Template(
            nl_query=question,
            sql=sql,
            intent=intent,
            manifest=manifest,
            parameterized=context.ParameterizedTemplate(
                parameterized_sql=parameterized_result["sql"],
                parameterized_intent=parameterized_result["intent"],
            ),
        )
        final_templates.append(template)

    context_set = context.ContextSet(templates=final_templates, facets=None)
    return context_set.model_dump_json(indent=2, exclude_none=True)
