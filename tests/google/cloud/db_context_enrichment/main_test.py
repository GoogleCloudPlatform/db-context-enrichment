import json
import pathlib

import pytest

from google.cloud.db_context_enrichment.main import (
    mutate_context_set,
    split_dataset,
)


def test_mutate_context_set_success(tmp_path: pathlib.Path):
    file_path = tmp_path / "context.json"
    mutations = [
        {
            "operation": "add",
            "type": "template",
            "value": {
                "nl_query": "Test query",
                "sql": "SELECT *",
                "intent": "Test intent",
                "manifest": "Test manifest",
                "parameterized": {
                    "parameterized_sql": "SELECT * FROM t",
                    "parameterized_intent": "Test",
                },
            },
        }
    ]

    result = mutate_context_set(str(file_path), json.dumps(mutations))

    assert "Successfully applied" in result
    assert file_path.exists()
    with open(file_path) as f:
        data = json.load(f)
    assert len(data.get("templates", [])) == 1
    assert data["templates"][0]["nl_query"] == "Test query"


def test_mutate_context_set_invalid_json(tmp_path: pathlib.Path):
    file_path = tmp_path / "context.json"
    result = mutate_context_set(str(file_path), "invalid json")
    assert "Error applying mutations" in result
    assert "JSONDecodeError" in result or "invalid json" in result or "Error" in result


def test_mutate_context_set_non_list_json(tmp_path: pathlib.Path):
    file_path = tmp_path / "context.json"
    result = mutate_context_set(
        str(file_path), json.dumps({"operation": "add", "type": "template"})
    )
    assert "must be a JSON list" in result


def test_mutate_context_set_validation_error(tmp_path: pathlib.Path):
    file_path = tmp_path / "context.json"
    # Invalid operation
    mutations = [{"operation": "invalid", "type": "template"}]
    result = mutate_context_set(str(file_path), json.dumps(mutations))
    assert "Error applying mutations" in result


@pytest.mark.asyncio
async def test_main_split_dataset(tmp_path: pathlib.Path):
    golden_file = tmp_path / "golden.json"
    golden_file.write_text(
        json.dumps(
            [
                {
                    "id": f"eval_{i}",
                    "database": "db",
                    "nlq": f"q {i}",
                    "golden_sql": f"SELECT {i}",
                    "metadata": {"subdomain": "crm"},
                }
                for i in range(1, 6)
            ]
        )
    )
    res = await split_dataset(
        golden_dataset_path=str(golden_file),
        output_dir=str(tmp_path / "exp"),
    )
    assert "Successfully partitioned" in res
    assert (tmp_path / "exp" / "splits" / "dev.json").exists()
    assert (tmp_path / "exp" / "splits" / "test.json").exists()

