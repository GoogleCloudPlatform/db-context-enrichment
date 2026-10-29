import json
import os
from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, ValidationError
from pydantic.alias_generators import to_snake

from google.cloud.db_context_enrichment.common import context_validator
from google.cloud.db_context_enrichment.model import context


def _build_model_alias_map() -> dict[str, str]:
    """Derives all field aliases dynamically from _BaseContextModel subclasses."""
    aliases: dict[str, str] = {}
    for model_cls in context._BaseContextModel.__subclasses__():
        for field_name, field_info in model_cls.model_fields.items():
            va = field_info.validation_alias
            choices = (
                va.choices if isinstance(va, AliasChoices) else ([va] if va else [])
            )
            for alias in choices:
                if isinstance(alias, str):
                    aliases[alias] = field_name
    return aliases


_MODEL_ALIASES = _build_model_alias_map()


def _to_snake_key(key: str) -> str:
    """Normalizes any model alias or camelCase key to canonical snake_case."""
    return _MODEL_ALIASES.get(key, to_snake(key))


def _normalize_item_keys(data: dict[str, Any]) -> dict[str, Any]:
    """Recursively normalizes item dictionary keys to canonical snake_case."""
    normalized: dict[str, Any] = {}
    for k, v in data.items():
        norm_k = _to_snake_key(k)
        if isinstance(v, dict):
            normalized[norm_k] = _normalize_item_keys(v)
        else:
            normalized[norm_k] = v
    return normalized


class Mutation(BaseModel):
    """Defines a strict schema for context modifications."""

    operation: Literal["add", "delete", "update"]
    type: Literal["template", "facet", "value_search"]
    identifier: dict[str, Any] = {}
    value: dict[str, Any] | None = None


def mutate_context_set(file_path: str, mutations: list[Mutation]) -> None:
    """
    Internal function to mutate (add, delete, update) elements in an existing ContextSet JSON file.

    The mutations is expected to be a list of Mutation objects.
    Each object specifies an 'operation', 'type', 'identifier' (to route to the correct item for deletes/updates), and 'value' (for adding/updating), for instance:

    [
      {
        "operation": "add",
        "type": "template",
        "value": {"nl_query": "...", "sql": "...", "intent": "...", "manifest": "...", "parameterized": {...}}
      },
      {
        "operation": "delete",
        "type": "template",
        "identifier": {"nl_query": "What are all users?"}
      },
      {
        "operation": "update",
        "type": "facet",
        "identifier": {"intent": "high price"},
        "value": {"sql_snippet": "price > 2000", "intent": "very high price"}
      }
    ]
    """

    # 1. Load existing raw JSON (or initialize empty dict) before full Pydantic validation
    # so that broken items in an existing file can be repaired or deleted by mutations.
    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
        raw_data: dict[str, Any] = {}
    else:
        try:
            with open(file_path, encoding="utf-8") as f:
                loaded = json.load(f)
            if not isinstance(loaded, dict):
                raise ValueError(
                    f"Top-level JSON in {file_path} must be an object, got {type(loaded).__name__}."
                )
            raw_data = {_to_snake_key(k): v for k, v in loaded.items()}
        except (json.JSONDecodeError, OSError) as e:
            raise RuntimeError(f"Error reading JSON from {file_path}: {e}") from e

    # 2. Model mapping for tracking and validation
    type_to_model = {
        "template": context.Template,
        "facet": context.Facet,
        "value_search": context.ValueSearch,
    }

    type_to_attr = {
        "template": "templates",
        "facet": "facets",
        "value_search": "value_searches",
    }

    # 3. Apply mutations
    for i, mut in enumerate(mutations):
        op = mut.operation
        item_type = mut.type
        identifier = _normalize_item_keys(mut.identifier or {})
        value_data = (
            _normalize_item_keys(mut.value)
            if isinstance(mut.value, dict)
            else mut.value
        )

        if item_type not in type_to_attr:
            continue

        if op in ("delete", "update") and not identifier:
            raise ValueError(
                f"Validation Error on mutation {i} during '{op}': 'identifier' is required and cannot be empty."
            )

        attr_name = type_to_attr[item_type]
        model_class = type_to_model[item_type]

        target_list = raw_data.get(attr_name)
        if not isinstance(target_list, list):
            target_list = []
            raw_data[attr_name] = target_list

        if op == "add":
            if value_data:
                try:
                    new_item = model_class.model_validate(value_data)
                    target_list.append(new_item.model_dump(exclude_none=True))
                except ValidationError as e:
                    raise ValueError(
                        f"Validation Error on mutation {i} during 'add': {e}"
                    ) from e

        elif op == "delete":
            new_list = []
            for raw_item in target_list:
                norm_item = (
                    _normalize_item_keys(raw_item) if isinstance(raw_item, dict) else {}
                )
                match = all(norm_item.get(k) == v for k, v in identifier.items())
                if not match:
                    new_list.append(raw_item)
            raw_data[attr_name] = new_list

        elif op == "update":
            for idx, raw_item in enumerate(target_list):
                norm_item = (
                    _normalize_item_keys(raw_item) if isinstance(raw_item, dict) else {}
                )
                match = all(norm_item.get(k) == v for k, v in identifier.items())
                if match and value_data:
                    updated_dict = {**norm_item, **value_data}
                    if isinstance(norm_item.get("parameterized"), dict) and isinstance(
                        value_data.get("parameterized"), dict
                    ):
                        updated_dict["parameterized"] = {
                            **norm_item["parameterized"],
                            **value_data["parameterized"],
                        }
                    try:
                        updated_item = model_class.model_validate(updated_dict)
                        target_list[idx] = updated_item.model_dump(exclude_none=True)
                        break  # Only update first match
                    except ValidationError as e:
                        raise ValueError(
                            f"Validation Error on mutation {i} during 'update': {e}"
                        ) from e

    # 4. Validate resulting ContextSet (schema + duplicate check) and save
    try:
        context_set = context.ContextSet.model_validate(raw_data)
    except ValidationError as e:
        raise ValueError(
            f"Validation Error loading ContextSet from {file_path}: {e}"
        ) from e

    normalized_dump = context_set.model_dump(exclude_none=True)
    dup_issues = context_validator._check_duplicates(normalized_dump)
    if dup_issues:
        dup_msgs = "; ".join(issue["message"] for issue in dup_issues)
        raise ValueError(
            f"Duplicate items detected in ContextSet for {file_path}: {dup_msgs}"
        )

    try:
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(context_set.model_dump_json(indent=2, exclude_none=True))
    except OSError as e:
        raise RuntimeError(f"Error saving ContextSet to {file_path}: {e}") from e
