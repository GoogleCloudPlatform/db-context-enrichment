import json
from typing import Any

from pydantic import ValidationError

from google.cloud.db_context_enrichment.model.context import ContextSet

_ATTR_TO_TYPE = {
    "templates": "template",
    "facets": "facet",
    "value_searches": "value_search",
}


def validate_context_set(file_path: str) -> dict[str, Any]:
    """Validate a ContextSet file and return a structured report of issues.

    Always returns a dict of the shape:
      {
        "valid": bool,
        "issues": [
          {
            "location": {"type": str, "index": int} | None,
            "message": str,
          },
          ...
        ],
      }

    File access failures (missing path, permission denied, path is a directory,
    etc.) are surfaced as a single issue rather than raised.
    """
    try:
        with open(file_path, encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        return {
            "valid": False,
            "issues": [
                _make_issue(f"Could not read file {file_path}: {type(e).__name__}: {e}")
            ],
        }

    if text.strip() == "":
        return {"valid": True, "issues": []}

    try:
        raw = json.loads(text)
    except json.JSONDecodeError as e:
        snippet = e.doc[max(0, e.pos - 30) : e.pos + 30]
        return {
            "valid": False,
            "issues": [_make_issue(f"File is not valid JSON: {e}. Near: {snippet!r}")],
        }

    if not isinstance(raw, dict):
        return {
            "valid": False,
            "issues": [_make_issue("Top-level value must be a JSON object")],
        }

    issues: list[dict[str, Any]] = []
    issues.extend(_check_pydantic(raw))
    issues.extend(_check_duplicates(raw))
    issues.extend(_check_value_search_value_param(raw))

    return {"valid": len(issues) == 0, "issues": issues}


def _make_issue(message: str, location: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"location": location, "message": message}


def _check_pydantic(raw: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    try:
        ContextSet.model_validate(raw)
        return issues
    except ValidationError as e:
        for err in e.errors():
            loc = err.get("loc", ())
            msg = err.get("msg", "validation error")
            location: dict[str, Any] | None = None
            descriptor = ""

            if len(loc) >= 1 and loc[0] in _ATTR_TO_TYPE:
                item_type = _ATTR_TO_TYPE[loc[0]]
                if len(loc) >= 2 and isinstance(loc[1], int):
                    item_index = loc[1]
                    location = {"type": item_type, "index": item_index}
                    items = raw.get(loc[0])
                    if isinstance(items, list) and 0 <= item_index < len(items):
                        descriptor = _describe(item_type, items[item_index])

            field_path = ".".join(str(p) for p in loc) if loc else ""
            parts = [msg]
            if field_path:
                parts.append(f"at {field_path}")
            if descriptor:
                parts.append(descriptor)
            full_msg = parts[0] + (
                " (" + "; ".join(parts[1:]) + ")" if len(parts) > 1 else ""
            )

            issues.append(_make_issue(full_msg, location=location))
    return issues


def _check_duplicates(raw: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for attr, item_type in _ATTR_TO_TYPE.items():
        items = raw.get(attr)
        if not isinstance(items, list):
            continue
        seen: dict[str, int] = {}
        for idx, item in enumerate(items):
            try:
                key = _canonical(item)
            except (TypeError, ValueError):
                continue
            if key in seen:
                descriptor = _describe(item_type, item)
                suffix = f" ({descriptor})" if descriptor else ""
                issues.append(
                    _make_issue(
                        f"Exact duplicate of {item_type} at index {seen[key]}{suffix}",
                        location={"type": item_type, "index": idx},
                    )
                )
            else:
                seen[key] = idx
    return issues


def _check_value_search_value_param(raw: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    items = raw.get("value_searches")
    if not isinstance(items, list):
        return issues
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        query = item.get("query")
        if isinstance(query, str) and "$value" not in query:
            descriptor = _describe("value_search", item)
            suffix = f" ({descriptor})" if descriptor else ""
            issues.append(
                _make_issue(
                    f"value_search query must reference the $value parameter{suffix}",
                    location={"type": "value_search", "index": idx},
                )
            )
    return issues


def _describe(item_type: str, item: Any) -> str:
    """Short human-readable identifier for an item, e.g. "intent: 'active users'"."""
    if not isinstance(item, dict):
        return ""
    if item_type == "template":
        nl = item.get("nl_query")
        return f"nl_query: {nl!r}" if nl else ""
    if item_type == "facet":
        intent = item.get("intent")
        return f"intent: {intent!r}" if intent else ""
    if item_type == "value_search":
        ct = item.get("concept_type")
        return f"concept_type: {ct!r}" if ct else ""
    return ""


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False)
