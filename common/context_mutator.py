import json
import os
from typing import Any, Literal
from pydantic import BaseModel, ValidationError
from model import context

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

    # 1. Load exiting ContextSet (or create an empty one)
    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
        context_set = context.ContextSet()
    else:
        try:
            with open(file_path, "r") as f:
                raw_data = json.load(f)
            context_set = context.ContextSet.model_validate(raw_data)
        except ValidationError as e:
            raise ValueError(f"Validation Error loading ContextSet from {file_path}: {e}") from e
        except (json.JSONDecodeError, OSError) as e:
            raise RuntimeError(f"Error reading JSON from {file_path}: {e}") from e

    # 2. Model mapping for tracking and validation
    type_to_model = {
        "template": context.Template,
        "facet": context.Facet,
        "value_search": context.ValueSearch
    }
    
    type_to_attr = {
        "template": "templates",
        "facet": "facets",
        "value_search": "value_searches"
    }

    # 3. Apply mutations
    for i, mut in enumerate(mutations):
        op = mut.operation
        item_type = mut.type
        identifier = mut.identifier
        value_data = mut.value

        if item_type not in type_to_attr:
            continue
            
        attr_name = type_to_attr[item_type]
        model_class = type_to_model[item_type]
        
        target_list = getattr(context_set, attr_name)
        if target_list is None:
            target_list = []
            setattr(context_set, attr_name, target_list)

        if op == "add":
            if value_data:
                try:
                    new_item = model_class.model_validate(value_data)
                    target_list.append(new_item)
                except ValidationError as e:
                    raise ValueError(f"Validation Error on mutation {i} during 'add': {e}") from e
                    
        elif op == "delete":
            new_list = []
            for item in target_list:
                item_dict = item.model_dump()
                match = all(item_dict.get(k) == v for k, v in identifier.items())
                if not match:
                    new_list.append(item)
            setattr(context_set, attr_name, new_list)
            
        elif op == "update":
            for idx, item in enumerate(target_list):
                item_dict = item.model_dump()
                match = all(item_dict.get(k) == v for k, v in identifier.items())
                if match and value_data:
                    updated_dict = {**item_dict, **value_data}
                    try:
                        updated_item = model_class.model_validate(updated_dict)
                        target_list[idx] = updated_item
                        break # Only update first match
                    except ValidationError as e:
                        raise ValueError(f"Validation Error on mutation {i} during 'update': {e}") from e

    # 4. Save validated ContextSet
    try:
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        with open(file_path, "w") as f:
            f.write(context_set.model_dump_json(indent=2, exclude_none=True))
    except OSError as e:
        raise RuntimeError(f"Error saving ContextSet to {file_path}: {e}") from e
