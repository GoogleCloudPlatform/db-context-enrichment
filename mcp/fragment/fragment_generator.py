import json
from common import parameterizer
from model import context


async def generate_fragments_from_pairs(
    approved_pairs_json: str, db_dialect_str: str = "postgresql"
) -> str:
    """
    Generates the final, detailed fragments based on user-approved question/SQL fragment pairs.
    """
    try:
        # Convert the string to the Enum member
        db_dialect = parameterizer.SQLDialect(db_dialect_str)
    except ValueError:
        return f'{{"error": "Invalid database dialect specified: {db_dialect_str}"}}'

    try:
        # The input is expected to be a direct list of pairs
        pair_list = json.loads(approved_pairs_json)
        if not isinstance(pair_list, list):
            raise json.JSONDecodeError("Input is not a list.", approved_pairs_json, 0)
    except json.JSONDecodeError:
        return '{"error": "Invalid JSON format for approved pairs. Expected a JSON array."}'

    final_fragments = []

    for pair in pair_list:
        question = pair["question"]
        fragment_text = pair["fragment"]
        intent = question  # The intent starts as the original question

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
            phrases, fragment_text, intent, db_dialect=db_dialect
        )

        # 4. Assemble the final fragment object
        fragment = context.Fragment(
            fragment=fragment_text,
            intent=intent,
            manifest=manifest,
            parameterized=context.ParameterizedFragment(
                parameterized_fragment=parameterized_result["sql"],
                parameterized_intent=parameterized_result["intent"],
            ),
        )
        final_fragments.append(fragment)

    context_set = context.ContextSet(templates=None, fragments=final_fragments)
    return context_set.model_dump_json(indent=2, exclude_none=True)
