import json
from pathlib import Path

from pydantic import AliasChoices

from google.cloud.db_context_enrichment.common.context_validator import (
    _ALIAS_TO_ATTR,
    validate_context_set,
)
from google.cloud.db_context_enrichment.model import context


def _write(path: Path, data) -> Path:
    if isinstance(data, str):
        path.write_text(data)
    else:
        path.write_text(json.dumps(data))
    return path


def _valid_template() -> dict:
    return {
        "nl_query": "How many users?",
        "sql": "SELECT count(*) FROM users",
        "intent": "Count users",
        "manifest": "Count users",
        "parameterized": {
            "parameterized_sql": "SELECT count(*) FROM users",
            "parameterized_intent": "Count users",
        },
    }


def _valid_facet() -> dict:
    return {
        "sql_snippet": "users.active = true",
        "intent": "active users",
        "manifest": "active users",
        "parameterized": {
            "parameterized_sql_snippet": "users.active = ?",
            "parameterized_intent": "users with active = ?",
        },
    }


def _valid_value_search() -> dict:
    return {
        "query": "SELECT name FROM cities WHERE name = $value",
        "concept_type": "City",
        "description": "City exact match",
    }


# ===== Happy path / empty cases =====


def test_valid_file_returns_no_issues(tmp_path: Path):
    file_path = _write(
        tmp_path / "ctx.json",
        {
            "templates": [_valid_template()],
            "facets": [_valid_facet()],
            "value_searches": [_valid_value_search()],
        },
    )
    result = validate_context_set(str(file_path))
    assert result["valid"] is True
    assert result["issues"] == []


def test_empty_file_is_valid(tmp_path: Path):
    file_path = _write(tmp_path / "ctx.json", "")
    result = validate_context_set(str(file_path))
    assert result["valid"] is True
    assert result["issues"] == []


def test_empty_object_is_valid(tmp_path: Path):
    file_path = _write(tmp_path / "ctx.json", {})
    result = validate_context_set(str(file_path))
    assert result["valid"] is True
    assert result["issues"] == []


# ===== INVALID_JSON =====


def test_invalid_json_returns_one_issue(tmp_path: Path):
    file_path = _write(tmp_path / "ctx.json", "not json {")
    result = validate_context_set(str(file_path))
    assert result["valid"] is False
    assert len(result["issues"]) == 1
    issue = result["issues"][0]
    assert issue["location"] is None
    assert "JSON" in issue["message"]


def test_missing_file_returns_issue(tmp_path: Path):
    result = validate_context_set(str(tmp_path / "missing.json"))
    assert result["valid"] is False
    assert len(result["issues"]) == 1
    msg = result["issues"][0]["message"]
    assert "missing.json" in msg
    assert "FileNotFoundError" in msg


def test_directory_path_returns_issue(tmp_path: Path):
    result = validate_context_set(str(tmp_path))
    assert result["valid"] is False
    assert "IsADirectoryError" in result["issues"][0]["message"]


def test_non_object_top_level_returns_issue(tmp_path: Path):
    file_path = _write(tmp_path / "ctx.json", [1, 2, 3])
    result = validate_context_set(str(file_path))
    assert result["valid"] is False
    assert any("object" in i["message"].lower() for i in result["issues"])


# ===== Schema mismatch =====


def test_missing_required_field_reports_field_and_identifier(tmp_path: Path):
    template = _valid_template()
    del template["manifest"]
    file_path = _write(tmp_path / "ctx.json", {"templates": [template]})
    result = validate_context_set(str(file_path))
    assert result["valid"] is False
    issues = [
        i for i in result["issues"] if i["location"] == {"type": "template", "index": 0}
    ]
    assert len(issues) == 1
    msg = issues[0]["message"]
    assert "manifest" in msg
    assert "How many users?" in msg


def test_wrong_field_type_reports_field(tmp_path: Path):
    template = _valid_template()
    template["sql"] = 123  # should be string
    file_path = _write(tmp_path / "ctx.json", {"templates": [template]})
    result = validate_context_set(str(file_path))
    assert result["valid"] is False
    assert any("sql" in i["message"] for i in result["issues"])


def test_top_level_wrong_shape_is_invalid(tmp_path: Path):
    # templates is a string instead of list
    file_path = _write(tmp_path / "ctx.json", {"templates": "oops"})
    result = validate_context_set(str(file_path))
    assert result["valid"] is False
    assert len(result["issues"]) >= 1


def test_schema_mismatch_without_identifying_field_still_validates(tmp_path: Path):
    # template missing both nl_query and manifest — no natural identifier to include
    template = {
        "sql": "SELECT 1",
        "intent": "x",
        "parameterized": {
            "parameterized_sql": "SELECT 1",
            "parameterized_intent": "x",
        },
    }
    file_path = _write(tmp_path / "ctx.json", {"templates": [template]})
    result = validate_context_set(str(file_path))
    # Should not crash; should report issues with the template at index 0
    assert result["valid"] is False
    assert any(
        i["location"] == {"type": "template", "index": 0} for i in result["issues"]
    )


# ===== Duplicates =====


def test_duplicate_template_reports_identifier(tmp_path: Path):
    tpl = _valid_template()
    file_path = _write(tmp_path / "ctx.json", {"templates": [tpl, tpl]})
    result = validate_context_set(str(file_path))
    dups = [i for i in result["issues"] if "duplicate" in i["message"].lower()]
    assert len(dups) == 1
    assert dups[0]["location"] == {"type": "template", "index": 1}
    assert "How many users?" in dups[0]["message"]


def test_duplicate_facet_reports_identifier(tmp_path: Path):
    f = _valid_facet()
    file_path = _write(tmp_path / "ctx.json", {"facets": [f, f]})
    result = validate_context_set(str(file_path))
    dups = [i for i in result["issues"] if "duplicate" in i["message"].lower()]
    assert len(dups) == 1
    assert dups[0]["location"] == {"type": "facet", "index": 1}
    assert "active users" in dups[0]["message"]


def test_duplicate_value_search_reports_identifier(tmp_path: Path):
    v = _valid_value_search()
    file_path = _write(tmp_path / "ctx.json", {"value_searches": [v, v]})
    result = validate_context_set(str(file_path))
    dups = [i for i in result["issues"] if "duplicate" in i["message"].lower()]
    assert len(dups) == 1
    assert dups[0]["location"] == {"type": "value_search", "index": 1}
    assert "City" in dups[0]["message"]


def test_triplicate_reports_two_issues(tmp_path: Path):
    tpl = _valid_template()
    file_path = _write(tmp_path / "ctx.json", {"templates": [tpl, tpl, tpl]})
    result = validate_context_set(str(file_path))
    dups = [i for i in result["issues"] if "duplicate" in i["message"].lower()]
    assert len(dups) == 2
    indices = {i["location"]["index"] for i in dups}
    assert indices == {1, 2}


# ===== Alias keys =====


def test_camel_case_alias_is_checked_like_snake_case(tmp_path: Path):
    # The Context Set server returns camelCase on download; checks must still apply.
    v = _valid_value_search()
    camel = _write(tmp_path / "camel.json", {"valueSearches": [v, v]})
    snake = _write(tmp_path / "snake.json", {"value_searches": [v, v]})
    assert validate_context_set(str(camel)) == validate_context_set(str(snake))


def test_camel_case_alias_reports_location(tmp_path: Path):
    file_path = _write(tmp_path / "ctx.json", {"valueSearches": [{"query": "$value"}]})
    result = validate_context_set(str(file_path))
    assert result["valid"] is False
    assert result["issues"][0]["location"] == {"type": "value_search", "index": 0}


def test_alias_map_covers_every_model_alias():
    # Guards against drift: a new alias on ContextSet that _ALIAS_TO_ATTR does
    # not know would silently skip the duplicate and $value checks.
    for attr, field in context.ContextSet.model_fields.items():
        validation_alias = field.validation_alias
        aliases = (
            validation_alias.choices
            if isinstance(validation_alias, AliasChoices)
            else [validation_alias]
        )
        for alias in aliases:
            if isinstance(alias, str) and alias != attr:
                assert _ALIAS_TO_ATTR.get(alias) == attr, (
                    f"ContextSet accepts {alias!r} for {attr!r} "
                    f"but _ALIAS_TO_ATTR does not map it"
                )


def test_deprecated_fragments_alias_is_checked(tmp_path: Path):
    f = _valid_facet()
    file_path = _write(tmp_path / "ctx.json", {"fragments": [f, f]})
    result = validate_context_set(str(file_path))
    dups = [i for i in result["issues"] if "duplicate" in i["message"].lower()]
    assert len(dups) == 1
    assert dups[0]["location"] == {"type": "facet", "index": 1}


# ===== value_search $value =====


def test_value_search_missing_value_param_reports_issue(tmp_path: Path):
    v = _valid_value_search()
    v["query"] = "SELECT name FROM cities WHERE name = 'London'"  # no $value
    file_path = _write(tmp_path / "ctx.json", {"value_searches": [v]})
    result = validate_context_set(str(file_path))
    issues = [i for i in result["issues"] if "$value" in i["message"]]
    assert len(issues) == 1
    assert issues[0]["location"] == {"type": "value_search", "index": 0}
    assert "City" in issues[0]["message"]


def test_value_search_with_value_param_passes(tmp_path: Path):
    file_path = _write(
        tmp_path / "ctx.json", {"value_searches": [_valid_value_search()]}
    )
    result = validate_context_set(str(file_path))
    assert not any("$value" in i["message"] for i in result["issues"])


# ===== Multiple issues =====


def test_multiple_issues_reported_together(tmp_path: Path):
    tpl = _valid_template()
    v = _valid_value_search()
    v["query"] = "SELECT 1"  # no $value
    file_path = _write(
        tmp_path / "ctx.json",
        {
            "templates": [tpl, tpl],  # duplicate
            "value_searches": [v],  # missing $value
        },
    )
    result = validate_context_set(str(file_path))
    assert result["valid"] is False
    messages = " ".join(i["message"] for i in result["issues"])
    assert "duplicate" in messages.lower()
    assert "$value" in messages


# ===== Server-side 400 prevention checks =====


def test_unknown_top_level_key_reports_issue(tmp_path: Path):
    file_path = _write(
        tmp_path / "ctx.json",
        {"template": [_valid_template()]},
    )
    result = validate_context_set(str(file_path))
    assert result["valid"] is False
    assert any(
        "Unknown top-level key 'template'" in i["message"] and i["location"] is None
        for i in result["issues"]
    )


def test_empty_or_whitespace_required_strings_report_issues(tmp_path: Path):
    tpl = _valid_template()
    tpl["manifest"] = "   "
    tpl["parameterized"]["parameterized_sql"] = ""

    facet = _valid_facet()
    facet["sql_snippet"] = ""

    vs = _valid_value_search()
    vs["concept_type"] = "  "

    file_path = _write(
        tmp_path / "ctx.json",
        {
            "templates": [tpl],
            "facets": [facet],
            "value_searches": [vs],
        },
    )
    result = validate_context_set(str(file_path))
    assert result["valid"] is False
    messages = [i["message"] for i in result["issues"]]
    assert any("manifest must not be empty" in m for m in messages)
    assert any(
        "parameterized.parameterized_sql must not be empty" in m for m in messages
    )
    assert any("sql_snippet must not be empty" in m for m in messages)
    assert any("concept_type must not be empty" in m for m in messages)


def test_duplicate_value_search_primary_key_with_different_description(tmp_path: Path):
    v1 = _valid_value_search()
    v2 = _valid_value_search()
    v2["description"] = "Different description but same (concept_type, query) PK"

    file_path = _write(tmp_path / "ctx.json", {"value_searches": [v1, v2]})
    result = validate_context_set(str(file_path))
    assert result["valid"] is False
    assert any(
        "Duplicate value_search (concept_type, query) key" in i["message"]
        and i["location"] == {"type": "value_search", "index": 1}
        for i in result["issues"]
    )


def test_template_mismatched_positional_placeholders_reports_issue(tmp_path: Path):
    tpl = _valid_template()
    tpl["parameterized"] = {
        "parameterized_sql": "SELECT * FROM users WHERE city = $1 AND age > $2",
        "parameterized_intent": "Users in $1",
    }
    file_path = _write(tmp_path / "ctx.json", {"templates": [tpl]})
    result = validate_context_set(str(file_path))
    assert result["valid"] is False
    assert any(
        "mismatched positional placeholders" in i["message"]
        and i["location"] == {"type": "template", "index": 0}
        for i in result["issues"]
    )


def test_facet_non_contiguous_positional_placeholders_reports_issue(tmp_path: Path):
    f = _valid_facet()
    f["parameterized"] = {
        "parameterized_sql_snippet": "users.city = $1 AND users.age > $3",
        "parameterized_intent": "users in $1 older than $3",
    }
    file_path = _write(tmp_path / "ctx.json", {"facets": [f]})
    result = validate_context_set(str(file_path))
    assert result["valid"] is False
    assert any(
        "numbered contiguously starting from $1" in i["message"]
        and i["location"] == {"type": "facet", "index": 0}
        for i in result["issues"]
    )


def test_unparameterized_sql_with_positional_placeholder_reports_issue(tmp_path: Path):
    tpl = _valid_template()
    tpl["sql"] = "SELECT * FROM users WHERE city = $1"
    tpl["parameterized"] = {
        "parameterized_sql": "SELECT * FROM users WHERE city = $1",
        "parameterized_intent": "Users in $1",
    }
    file_path = _write(tmp_path / "ctx.json", {"templates": [tpl]})
    result = validate_context_set(str(file_path))
    assert result["valid"] is False
    assert any(
        "sql must contain literal values, not positional placeholders ($1)"
        in i["message"]
        for i in result["issues"]
    )


def test_dollar_amount_inside_sql_string_literal_or_comment_is_allowed(tmp_path: Path):
    tpl = _valid_template()
    tpl["sql"] = "SELECT * FROM plans WHERE tier = '$100 plan' -- $2 comment"
    tpl["parameterized"] = {
        "parameterized_sql": "SELECT * FROM plans WHERE tier = '$100 plan' AND org = $1",
        "parameterized_intent": "Plans in $1",
    }
    file_path = _write(tmp_path / "ctx.json", {"templates": [tpl]})
    result = validate_context_set(str(file_path))
    assert result["valid"] is True
    assert result["issues"] == []


def test_value_search_rejects_prefix_only_or_commented_value_param(tmp_path: Path):
    v1 = _valid_value_search()
    v1["query"] = "SELECT name FROM cities WHERE name = $value_id"
    v2 = _valid_value_search()
    v2["concept_type"] = "Country"
    v2["query"] = "SELECT name FROM countries -- $value"
    file_path = _write(tmp_path / "ctx.json", {"value_searches": [v1, v2]})
    result = validate_context_set(str(file_path))
    assert result["valid"] is False
    issues = [i for i in result["issues"] if "$value" in i["message"]]
    assert len(issues) == 2


def test_question_mark_placeholders_valid_and_mismatched(tmp_path: Path):
    # 1. Valid `?` in both parameterized_sql and parameterized_intent (including trailing `?` question mark)
    tpl_valid = _valid_template()
    tpl_valid["sql"] = (
        "SELECT name, city FROM `hotels_view` WHERE city = 'Basel' LIMIT 5"
    )
    tpl_valid["parameterized"] = {
        "parameterized_sql": "SELECT name, city FROM `hotels_view` WHERE city = ? LIMIT ?",
        "parameterized_intent": "Find up to ? hotels in '?'?",
    }
    file_path = _write(tmp_path / "ctx_valid.json", {"templates": [tpl_valid]})
    assert validate_context_set(str(file_path)) == {"valid": True, "issues": []}

    # 2. Mismatched: `?` in parameterized_sql vs `$1` in parameterized_intent
    tpl_mixed = _valid_template()
    tpl_mixed["parameterized"] = {
        "parameterized_sql": "SELECT name FROM `hotels_view` WHERE city = ?",
        "parameterized_intent": "Find hotels in $1",
    }
    file_mixed = _write(tmp_path / "ctx_mixed.json", {"templates": [tpl_mixed]})
    res_mixed = validate_context_set(str(file_mixed))
    assert res_mixed["valid"] is False
    assert any(
        "mismatched positional placeholders: sql has ['?'], intent has ['$1']"
        in i["message"]
        for i in res_mixed["issues"]
    )

    # 3. Mismatched count of `?` between parameterized_sql and parameterized_intent
    tpl_count = _valid_template()
    tpl_count["parameterized"] = {
        "parameterized_sql": "SELECT name FROM `hotels_view` WHERE city = ? LIMIT ?",
        "parameterized_intent": "Find hotels in '?'",
    }
    file_count = _write(tmp_path / "ctx_count.json", {"templates": [tpl_count]})
    res_count = validate_context_set(str(file_count))
    assert res_count["valid"] is False
    assert any(
        "mismatched positional placeholders: sql has ['?', '?'], intent has ['?']"
        in i["message"]
        for i in res_count["issues"]
    )

    # 4. Unparameterized `?` in literal `sql` (outside string literals/comments)
    tpl_unparam = _valid_template()
    tpl_unparam["sql"] = "SELECT name FROM `hotels_view` WHERE city = ?"
    tpl_unparam["parameterized"] = {
        "parameterized_sql": "SELECT name FROM `hotels_view` WHERE city = ?",
        "parameterized_intent": "Find hotels in '?'",
    }
    file_unparam = _write(tmp_path / "ctx_unparam.json", {"templates": [tpl_unparam]})
    res_unparam = validate_context_set(str(file_unparam))
    assert res_unparam["valid"] is False
    assert any(
        "sql must contain literal values, not positional placeholders (?)"
        in i["message"]
        for i in res_unparam["issues"]
    )


def test_firestore_mql_template_and_sql_quoted_placeholder_diagnostics(
    tmp_path: Path,
):
    # 1. Firestore MQL template with either unquoted $1 or single-quoted '$1' is valid
    for mql_param in ("status: $1", "status: '$1'", 'status: "$1"'):
        tpl_mql = {
            "nl_query": "What is the total revenue for completed orders?",
            "sql": "db.orders.aggregate([{ $match: { status: 'completed' } }, { $group: { _id: null, totalRevenue: { $sum: '$total_amount' } } }, { $project: { _id: 0, totalRevenue: 1 } }])",
            "intent": "Total revenue for completed orders",
            "manifest": "Total revenue for orders with a given status",
            "parameterized": {
                "parameterized_sql": f"db.orders.aggregate([{{ $match: {{ {mql_param} }} }}, {{ $group: {{ _id: null, totalRevenue: {{ $sum: '$total_amount' }} }} }}, {{ $project: {{ _id: 0, totalRevenue: 1 }} }}])",
                "parameterized_intent": "Total revenue for orders with status $1",
            },
        }
        p = _write(tmp_path / "mql.json", {"templates": [tpl_mql]})
        assert validate_context_set(str(p)) == {"valid": True, "issues": []}

    # 2. Standard SQL with single-quoted '$1' reports explicit diagnostic about quoted placeholder
    tpl_sql_quoted = _valid_template()
    tpl_sql_quoted["parameterized"] = {
        "parameterized_sql": "SELECT * FROM orders WHERE status = '$1'",
        "parameterized_intent": "Orders with status $1",
    }
    p_sql = _write(tmp_path / "sql_quoted.json", {"templates": [tpl_sql_quoted]})
    res_sql = validate_context_set(str(p_sql))
    assert res_sql["valid"] is False
    assert any(
        "found single-quoted placeholder(s) [\"'$1'\"] inside SQL string literal"
        in i["message"]
        for i in res_sql["issues"]
    )


def test_intent_spaced_trailing_qmark_and_currency_literals(tmp_path: Path):
    # 1. Trailing question mark preceded by a space in a $N-parameterized intent
    tpl_spaced_q = _valid_template()
    tpl_spaced_q["sql"] = (
        'SELECT "account_id" FROM "trans" WHERE to_char("date"::timestamptz, \'YYYY\') = \'1995\' ORDER BY "date" ASC LIMIT 1'
    )
    tpl_spaced_q["parameterized"] = {
        "parameterized_sql": 'SELECT "account_id" FROM "trans" WHERE to_char("date"::timestamptz, $1) = $2 ORDER BY "date" ASC LIMIT 1',
        "parameterized_intent": "List out the accounts who have the earliest trading date in $2 with format $1 ?",
    }

    # 2. Unparameterized currency amounts ($4000, $1,000, $50) in parameterized_intent
    tpl_currency = _valid_template()
    tpl_currency["sql"] = (
        "SELECT count(*) FROM customers WHERE birth_year BETWEEN 1970 AND 1980 AND payment > 4000"
    )
    tpl_currency["parameterized"] = {
        "parameterized_sql": "SELECT count(*) FROM customers WHERE birth_year BETWEEN $1 AND $2 AND payment > 4000",
        "parameterized_intent": "How many customers born between $1 and $2 have made a payment in excess of $4000 (or $1,000 / $50) ?",
    }

    p = _write(
        tmp_path / "bird_edge_cases.json",
        {"templates": [tpl_spaced_q, tpl_currency]},
    )
    assert validate_context_set(str(p)) == {"valid": True, "issues": []}
