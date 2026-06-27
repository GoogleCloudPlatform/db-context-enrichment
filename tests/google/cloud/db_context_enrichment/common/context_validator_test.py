import json
from pathlib import Path

from google.cloud.db_context_enrichment.common.context_validator import (
    validate_context_set,
)


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
            "parameterized_intent": "active users",
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
