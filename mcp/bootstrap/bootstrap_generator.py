import json
from template import template_generator
from facet import facet_generator
from model import context
from pydantic import ValidationError
from common.context_mutator import mutate_context_set, Mutation


async def generate_context(
    output_file_path: str,
    sql_dialect: str,
    template_inputs_json: str | None = None,
    facet_inputs_json: str | None = None,
) -> str:
    """
    Core logic for generating a single unified ContextSet from key information and saving it to a file.
    """
    final_templates = None
    final_facets = None

    if template_inputs_json:
        res_str = await template_generator.generate_templates(template_inputs_json, sql_dialect)
        if '"error":' in res_str:
            raise RuntimeError(f"Error generating templates: {res_str}")
        try:
            res_dict = json.loads(res_str)
            final_templates = [context.Template(**t) for t in res_dict.get("templates", [])]
        except (json.JSONDecodeError, ValidationError) as e:
            raise ValueError(f"Error parsing generated templates: {e}") from e

    if facet_inputs_json:
        res_str = await facet_generator.generate_facets(facet_inputs_json, sql_dialect)
        if '"error":' in res_str:
            raise RuntimeError(f"Error generating facets: {res_str}")
        try:
            res_dict = json.loads(res_str)
            final_facets = [context.Facet(**f) for f in res_dict.get("facets", [])]
        except (json.JSONDecodeError, ValidationError) as e:
            raise ValueError(f"Error parsing generated facets: {e}") from e

    mutations: list[Mutation] = []

    if final_templates:
        for t in final_templates:
            mutations.append(Mutation(
                operation="add",
                type="template",
                value=t.model_dump(exclude_none=True)
            ))

    if final_facets:
        for f in final_facets:
            mutations.append(Mutation(
                operation="add",
                type="facet",
                value=f.model_dump(exclude_none=True)
            ))

    if not mutations:
        raise ValueError("No templates or facets were generated to save.")

    mutate_context_set(output_file_path, mutations)
    return output_file_path
