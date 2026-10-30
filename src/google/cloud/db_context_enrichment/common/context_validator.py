import collections
import json
import re
from typing import Any

from pydantic import ValidationError

from google.cloud.db_context_enrichment.model import context

_ATTR_TO_TYPE = {
    "templates": "template",
    "facets": "facet",
    "value_searches": "value_search",
}

# ContextSet accepts camelCase aliases (the Context Set server returns them on download)
# and the deprecated "fragments" name. Map them back to the canonical attribute
# so every check below only has to handle one spelling.
_ALIAS_TO_ATTR = {
    "valueSearches": "value_searches",
    "fragments": "facets",
}

_POSITIONAL_PARAM_RE = re.compile(r"(?<!\$)\$(\d+)\b(?![.,]\d)")
_QUOTED_POSITIONAL_PARAM_RE = re.compile(r"'\$(\d+)'")
_SQL_QMARK_PARAM_RE = re.compile(r"(?<![?|&])\?(?![?|&])")
_INTENT_QMARK_PARAM_RE = re.compile(r"(?:^|(?<=[\s=(<>:,\[]))['\"]?\?")
_VALUE_PARAM_RE = re.compile(r"(?<!\$)\$value\b")


_SINGLE_QUOTED_LIT_RE = re.compile(r"'(?:''|\\'|[^'])*'")
_MQL_QUOTED_LIT_RE = re.compile(r"'(?:''|\\'|[^'])*'|\"(?:\\\"|[^\"])*\"")


def _strip_sql_comments_and_strings(
    sql: str,
    *,
    allow_mql_quoted_params: bool = True,
    literal_strings: collections.Counter[str] | set[str] | None = None,
) -> str:
    """Strips SQL comments and string literals before scanning for placeholders.

    In parameterized MQL queries/snippets (starting with 'db.', '{', or '['),
    standalone single- or double-quoted positional placeholders like '$1' or "$1"
    are preserved (unless accounted for by the baseline count of literal strings
    in the unparameterized query) so they match intent placeholders.
    """
    no_comments = _strip_sql_comments(sql)
    starts_like_mql = no_comments.lstrip().startswith(("db.", "{", "["))
    is_mql = allow_mql_quoted_params and starts_like_mql
    remaining_literals: collections.Counter[str] = (
        collections.Counter(literal_strings)
        if literal_strings is not None
        else collections.Counter()
    )

    def _replace_quoted(m: re.Match[str]) -> str:
        tok = m.group(0)
        if is_mql and re.fullmatch(r"""['"]\$\d+['"]""", tok):
            if remaining_literals[tok] > 0:
                remaining_literals[tok] -= 1
                return "''"
            return tok[1:-1]
        return "''"

    lit_re = _MQL_QUOTED_LIT_RE if starts_like_mql else _SINGLE_QUOTED_LIT_RE
    return lit_re.sub(
        _replace_quoted,
        no_comments,
    )


def _strip_sql_comments(sql: str) -> str:
    """Strips SQL block and line comments."""
    no_comments = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    return re.sub(r"--[^\n]*", " ", no_comments)


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

    raw = _normalize_aliases(raw)

    issues: list[dict[str, Any]] = []
    issues.extend(_check_unknown_top_level_keys(raw))
    issues.extend(_check_pydantic(raw))
    issues.extend(_check_non_empty_strings(raw))
    issues.extend(_check_duplicates(raw))
    issues.extend(_check_parameterization(raw))
    issues.extend(_check_value_search_value_param(raw))

    return {"valid": len(issues) == 0, "issues": issues}


def _make_issue(message: str, location: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"location": location, "message": message}


def _normalize_aliases(raw: dict[str, Any]) -> dict[str, Any]:
    """Rewrite alias keys to their canonical ContextSet attribute names."""
    return {_ALIAS_TO_ATTR.get(key, key): value for key, value in raw.items()}


def _check_unknown_top_level_keys(raw: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for key in raw:
        if key not in _ATTR_TO_TYPE:
            issues.append(
                _make_issue(
                    f"Unknown top-level key {key!r}; expected one of: "
                    "templates, facets, value_searches"
                )
            )
    return issues


def _check_pydantic(raw: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    try:
        context.ContextSet.model_validate(raw)
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


def _get_first_present(d: dict[str, Any], keys: tuple[str, ...]) -> tuple[str, Any]:
    for k in keys:
        if k in d:
            return k, d[k]
    return keys[0], None


def _check_non_empty_strings(raw: dict[str, Any]) -> list[dict[str, Any]]:
    """Reject empty or whitespace-only required strings that fail server-side upload."""
    issues: list[dict[str, Any]] = []

    templates = raw.get("templates")
    if isinstance(templates, list):
        for idx, item in enumerate(templates):
            if not isinstance(item, dict):
                continue
            loc = {"type": "template", "index": idx}
            descriptor = _describe("template", item)
            suffix = f" ({descriptor})" if descriptor else ""
            for field_keys in (
                ("nl_query", "nlQuery"),
                ("sql",),
                ("intent",),
                ("manifest",),
            ):
                field_name, val = _get_first_present(item, field_keys)
                if isinstance(val, str) and val.strip() == "":
                    issues.append(
                        _make_issue(
                            f"{field_name} must not be empty{suffix}",
                            location=loc,
                        )
                    )
            param = item.get("parameterized")
            if isinstance(param, dict):
                for field_keys in (
                    ("parameterized_sql", "parameterizedSql"),
                    ("parameterized_intent", "parameterizedIntent"),
                ):
                    field_name, val = _get_first_present(param, field_keys)
                    if isinstance(val, str) and val.strip() == "":
                        issues.append(
                            _make_issue(
                                f"parameterized.{field_name} must not be empty{suffix}",
                                location=loc,
                            )
                        )

    facets = raw.get("facets")
    if isinstance(facets, list):
        for idx, item in enumerate(facets):
            if not isinstance(item, dict):
                continue
            loc = {"type": "facet", "index": idx}
            descriptor = _describe("facet", item)
            suffix = f" ({descriptor})" if descriptor else ""
            for field_keys in (
                ("sql_snippet", "sqlSnippet", "fragment"),
                ("intent",),
                ("manifest",),
            ):
                field_name, val = _get_first_present(item, field_keys)
                if isinstance(val, str) and val.strip() == "":
                    issues.append(
                        _make_issue(
                            f"{field_name} must not be empty{suffix}",
                            location=loc,
                        )
                    )
            param = item.get("parameterized")
            if isinstance(param, dict):
                for field_keys in (
                    (
                        "parameterized_sql_snippet",
                        "parameterizedSqlSnippet",
                        "parameterized_fragment",
                    ),
                    ("parameterized_intent", "parameterizedIntent"),
                ):
                    field_name, val = _get_first_present(param, field_keys)
                    if isinstance(val, str) and val.strip() == "":
                        issues.append(
                            _make_issue(
                                f"parameterized.{field_name} must not be empty{suffix}",
                                location=loc,
                            )
                        )

    value_searches = raw.get("value_searches")
    if isinstance(value_searches, list):
        for idx, item in enumerate(value_searches):
            if not isinstance(item, dict):
                continue
            loc = {"type": "value_search", "index": idx}
            descriptor = _describe("value_search", item)
            suffix = f" ({descriptor})" if descriptor else ""
            for field_keys in (
                ("concept_type", "conceptType"),
                ("query",),
            ):
                field_name, val = _get_first_present(item, field_keys)
                if isinstance(val, str) and val.strip() == "":
                    issues.append(
                        _make_issue(
                            f"{field_name} must not be empty{suffix}",
                            location=loc,
                        )
                    )

    return issues


def _check_duplicates(raw: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for attr, item_type in _ATTR_TO_TYPE.items():
        items = raw.get(attr)
        if not isinstance(items, list):
            continue
        seen: dict[str, int] = {}
        seen_vs_pk: dict[tuple[str, str], int] = {}
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
                continue
            seen[key] = idx

            if item_type == "value_search" and isinstance(item, dict):
                _, ct = _get_first_present(item, ("concept_type", "conceptType"))
                query = item.get("query")
                if isinstance(ct, str) and isinstance(query, str):
                    pk = (ct, query)
                    if pk in seen_vs_pk:
                        descriptor = _describe(item_type, item)
                        suffix = f" ({descriptor})" if descriptor else ""
                        issues.append(
                            _make_issue(
                                "Duplicate value_search (concept_type, query) key "
                                f"with index {seen_vs_pk[pk]}{suffix}",
                                location={"type": item_type, "index": idx},
                            )
                        )
                    else:
                        seen_vs_pk[pk] = idx
    return issues


def _extract_positional_params(
    text: str,
    strip_sql_literals: bool = False,
    allow_mql_quoted_params: bool = True,
    literal_strings: collections.Counter[str] | set[str] | None = None,
    max_index: int | None = None,
) -> set[int]:
    cleaned = (
        _strip_sql_comments_and_strings(
            text,
            allow_mql_quoted_params=allow_mql_quoted_params,
            literal_strings=literal_strings,
        )
        if strip_sql_literals
        else text
    )
    return {
        int(m.group(1))
        for m in _POSITIONAL_PARAM_RE.finditer(cleaned)
        if int(m.group(1)) >= 1 and (max_index is None or int(m.group(1)) <= max_index)
    }


def _count_qmark_params(text: str, *, is_sql: bool) -> int:
    if is_sql:
        cleaned = _strip_sql_comments_and_strings(text)
        return sum(1 for _ in _SQL_QMARK_PARAM_RE.finditer(cleaned))
    normalized = re.sub(r"\?\s+\?\s*$", "??", text)
    if _extract_positional_params(normalized):
        normalized = re.sub(r"\s+\?\s*$", "?", normalized)
    return sum(1 for _ in _INTENT_QMARK_PARAM_RE.finditer(normalized))


def _check_parameterization(raw: dict[str, Any]) -> list[dict[str, Any]]:
    """Validate placeholder consistency in templates and facets."""
    issues: list[dict[str, Any]] = []

    for attr, item_type, sql_keys, param_sql_keys in (
        (
            "templates",
            "template",
            ("sql",),
            ("parameterized_sql", "parameterizedSql"),
        ),
        (
            "facets",
            "facet",
            ("sql_snippet", "sqlSnippet", "fragment"),
            (
                "parameterized_sql_snippet",
                "parameterizedSqlSnippet",
                "parameterized_fragment",
            ),
        ),
    ):
        items = raw.get(attr)
        if not isinstance(items, list):
            continue
        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            loc = {"type": item_type, "index": idx}
            descriptor = _describe(item_type, item)
            suffix = f" ({descriptor})" if descriptor else ""

            sql_field_name, raw_sql = _get_first_present(item, sql_keys)
            raw_sql_literals: collections.Counter[str] = collections.Counter()
            if isinstance(raw_sql, str):
                no_comment_raw = _strip_sql_comments(raw_sql)
                lit_re = (
                    _MQL_QUOTED_LIT_RE
                    if no_comment_raw.lstrip().startswith(("db.", "{", "["))
                    else _SINGLE_QUOTED_LIT_RE
                )
                raw_sql_literals = collections.Counter(lit_re.findall(no_comment_raw))
                unparam_placeholders = _extract_positional_params(
                    raw_sql,
                    strip_sql_literals=True,
                    allow_mql_quoted_params=False,
                )
                unparam_qmarks = _count_qmark_params(raw_sql, is_sql=True)
                if unparam_placeholders or unparam_qmarks:
                    formatted_parts = [
                        f"${n}" for n in sorted(unparam_placeholders)
                    ] + (["?"] * unparam_qmarks)
                    formatted = ", ".join(formatted_parts)
                    issues.append(
                        _make_issue(
                            f"{sql_field_name} must contain literal values, not "
                            f"positional placeholders ({formatted}){suffix}",
                            location=loc,
                        )
                    )

            param = item.get("parameterized")
            if not isinstance(param, dict):
                continue
            param_sql_name, param_sql = _get_first_present(param, param_sql_keys)
            _, param_intent = _get_first_present(
                param, ("parameterized_intent", "parameterizedIntent")
            )
            if not isinstance(param_sql, str) or not isinstance(param_intent, str):
                continue

            sql_params = _extract_positional_params(
                param_sql,
                strip_sql_literals=True,
                literal_strings=raw_sql_literals,
            )
            sql_qmarks = _count_qmark_params(param_sql, is_sql=True)
            max_intent_index = max(max(sql_params, default=0) + 5, 9)
            intent_params = _extract_positional_params(
                param_intent, max_index=max_intent_index
            )
            intent_qmarks = _count_qmark_params(param_intent, is_sql=False)

            sql_fmt = [f"${n}" for n in sorted(sql_params)] + ["?"] * sql_qmarks
            intent_fmt = [f"${n}" for n in sorted(intent_params)] + [
                "?"
            ] * intent_qmarks

            if sql_params != intent_params or sql_qmarks != intent_qmarks:
                no_comment_sql = _strip_sql_comments(param_sql)
                quoted_sql_params = {
                    int(m.group(1))
                    for m in _QUOTED_POSITIONAL_PARAM_RE.finditer(no_comment_sql)
                    if int(m.group(1)) >= 1
                } - sql_params
                quoted_note = ""
                if quoted_sql_params:
                    quoted_fmt = [f"'${n}'" for n in sorted(quoted_sql_params)]
                    quoted_note = (
                        f" (found single-quoted placeholder(s) {quoted_fmt} "
                        "inside SQL string literal; remove surrounding single quotes)"
                    )
                issues.append(
                    _make_issue(
                        f"parameterized.{param_sql_name} and "
                        "parameterized.parameterized_intent have mismatched "
                        f"positional placeholders: sql has {sql_fmt}, "
                        f"intent has {intent_fmt}{quoted_note}{suffix}",
                        location=loc,
                    )
                )
            elif sql_params and sql_qmarks:
                issues.append(
                    _make_issue(
                        f"parameterized.{param_sql_name} cannot mix $N and ? "
                        f"positional placeholders (got {sql_fmt}){suffix}",
                        location=loc,
                    )
                )
            elif sql_params:
                expected = set(range(1, len(sql_params) + 1))
                if sql_params != expected:
                    actual_fmt = [f"${n}" for n in sorted(sql_params)]
                    expected_fmt = [f"${n}" for n in sorted(expected)]
                    issues.append(
                        _make_issue(
                            "Positional placeholders must be numbered contiguously "
                            f"starting from $1 (expected {expected_fmt}, "
                            f"got {actual_fmt}){suffix}",
                            location=loc,
                        )
                    )

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
        if isinstance(query, str) and not _VALUE_PARAM_RE.search(
            _strip_sql_comments(query)
        ):
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
