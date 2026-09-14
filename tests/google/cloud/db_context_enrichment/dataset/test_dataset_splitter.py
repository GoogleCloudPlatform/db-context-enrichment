import json
import pathlib

import pytest

from google.cloud.db_context_enrichment.dataset.dataset_splitter import (
    _normalize_sql_template,
    split_dataset,
)


@pytest.fixture
def sample_golden_entries():
    entries = []
    # 2 query templates, 5 variations each
    for i in range(1, 6):
        entries.append(
            {
                "id": f"eval_sales_{i}",
                "database": "test_db",
                "nlq": f"Sales query variation {i}",
                "golden_sql": f"SELECT COUNT(*) FROM sales WHERE year = {2020 + i}",
            }
        )
    for i in range(1, 6):
        entries.append(
            {
                "id": f"eval_billing_{i}",
                "database": "test_db",
                "nlq": f"Billing query variation {i}",
                "golden_sql": f"SELECT SUM(amount) FROM billing WHERE status = 'PAID' AND id = {i}",
            }
        )
    return entries


@pytest.mark.asyncio
async def test_split_dataset_template_overlap(tmp_path: pathlib.Path, sample_golden_entries):
    input_file = tmp_path / "golden.json"
    with open(input_file, "w", encoding="utf-8") as f:
        json.dump(sample_golden_entries, f)

    output_dir = tmp_path / "experiment"
    res = await split_dataset(str(input_file), str(output_dir), train_ratio=0.8)

    assert "Successfully partitioned" in res
    dev_file = output_dir / "splits" / "dev.json"
    test_file = output_dir / "splits" / "test.json"

    assert dev_file.exists()
    assert test_file.exists()

    with open(dev_file) as f:
        dev_data = json.load(f)
    with open(test_file) as f:
        test_data = json.load(f)

    # 10 items total: 4 dev + 1 test per template -> 8 dev, 2 test
    assert len(dev_data) == 8
    assert len(test_data) == 2

    # Check 100% template overlap
    dev_templates = {_normalize_sql_template(e["golden_sql"]) for e in dev_data}
    test_templates = {_normalize_sql_template(e["golden_sql"]) for e in test_data}

    expected_templates = {
        "select count(*) from sales where year = ?",
        "select sum(amount) from billing where status = '?' and id = ?",
    }
    assert dev_templates == expected_templates
    assert test_templates == expected_templates


@pytest.mark.asyncio
async def test_split_dataset_fail_early_on_pre_partitioned(
    tmp_path: pathlib.Path, sample_golden_entries
):
    input_file = tmp_path / "golden.json"
    with open(input_file, "w", encoding="utf-8") as f:
        json.dump(sample_golden_entries, f)

    output_dir = tmp_path / "experiment"
    with pytest.raises(ValueError, match=r"\[ERROR\] InvalidDatasetConfiguration"):
        await split_dataset(
            str(input_file),
            str(output_dir),
            custom_test_dataset_path="custom_test.json",
        )


@pytest.mark.asyncio
async def test_split_dataset_missing_file(tmp_path: pathlib.Path):
    non_existent = tmp_path / "missing.json"
    with pytest.raises(FileNotFoundError):
        await split_dataset(str(non_existent), str(tmp_path / "out"))


@pytest.mark.asyncio
async def test_split_dataset_missing_required_keys(tmp_path: pathlib.Path):
    input_file = tmp_path / "invalid.json"
    with open(input_file, "w", encoding="utf-8") as f:
        json.dump([{"id": "eval_1", "database": "db"}], f)

    with pytest.raises(ValueError, match="missing required keys"):
        await split_dataset(str(input_file), str(tmp_path / "out"))
