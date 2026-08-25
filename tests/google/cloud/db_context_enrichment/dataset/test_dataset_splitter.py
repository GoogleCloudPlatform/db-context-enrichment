import json
import os
import pathlib

import pytest

from google.cloud.db_context_enrichment.dataset.dataset_splitter import (
    split_dataset,
)


@pytest.fixture
def sample_golden_entries():
    entries = []
    # 5 items for 'sales'
    for i in range(1, 6):
        entries.append(
            {
                "id": f"eval_sales_{i}",
                "database": "test_db",
                "nlq": f"Count sales {i}",
                "golden_sql": f"SELECT COUNT(*) FROM sales WHERE id = {i}",
                "metadata": {"subdomain": "sales", "complexity_tier": "tier_1_simple"},
            }
        )
    # 5 items for 'billing'
    for i in range(1, 6):
        entries.append(
            {
                "id": f"eval_billing_{i}",
                "database": "test_db",
                "nlq": f"Count billing {i}",
                "golden_sql": f"SELECT COUNT(*) FROM billing WHERE id = {i}",
                "metadata": {"subdomain": "billing", "complexity_tier": "tier_2_multi_join_agg"},
            }
        )
    return entries


@pytest.mark.asyncio
async def test_split_dataset_stratified_success(tmp_path: pathlib.Path, sample_golden_entries):
    golden_file = tmp_path / "golden.json"
    golden_file.write_text(json.dumps(sample_golden_entries))

    output_dir = tmp_path / "experiment_1"

    result = await split_dataset(
        golden_dataset_path=str(golden_file),
        output_dir=str(output_dir),
        stratify_by="subdomain",
        train_ratio=0.8,
    )

    assert "Successfully partitioned and saved Dev and Holdout Test splits." in result
    assert "Stratified Partitioning" in result

    dev_file = output_dir / "splits" / "dev.json"
    test_file = output_dir / "splits" / "test.json"

    assert dev_file.exists()
    assert test_file.exists()

    dev_data = json.loads(dev_file.read_text())
    test_data = json.loads(test_file.read_text())

    # 4 sales dev + 4 billing dev = 8 dev items
    assert len(dev_data) == 8
    # 1 sales test + 1 billing test = 2 test items
    assert len(test_data) == 2

    # Check that each subdomain has 4 dev and 1 test
    dev_sales = [x for x in dev_data if x["metadata"]["subdomain"] == "sales"]
    test_sales = [x for x in test_data if x["metadata"]["subdomain"] == "sales"]
    assert len(dev_sales) == 4
    assert len(test_sales) == 1


@pytest.mark.asyncio
async def test_split_dataset_low_quorum_warning(tmp_path: pathlib.Path):
    # Only 3 items for 'inventory'
    entries = [
        {
            "id": f"eval_inv_{i}",
            "database": "test_db",
            "nlq": f"Check inventory {i}",
            "golden_sql": f"SELECT * FROM inventory WHERE id = {i}",
            "metadata": {"subdomain": "inventory"},
        }
        for i in range(1, 4)
    ]
    golden_file = tmp_path / "golden.json"
    golden_file.write_text(json.dumps(entries))

    output_dir = tmp_path / "experiment_2"

    result = await split_dataset(
        golden_dataset_path=str(golden_file),
        output_dir=str(output_dir),
    )

    assert "Stratum Quorum Notice" in result
    assert "`inventory`" in result
    assert "⚠️ Low Quorum (< 5)" in result


@pytest.mark.asyncio
async def test_split_dataset_single_item_stratum(tmp_path: pathlib.Path):
    entries = [
        {
            "id": "eval_rare_1",
            "database": "test_db",
            "nlq": "Rare query",
            "golden_sql": "SELECT 1",
            "metadata": {"subdomain": "rare"},
        }
    ]
    golden_file = tmp_path / "golden.json"
    golden_file.write_text(json.dumps(entries))

    output_dir = tmp_path / "experiment_3"

    result = await split_dataset(
        golden_dataset_path=str(golden_file),
        output_dir=str(output_dir),
    )

    assert "Successfully partitioned" in result
    dev_file = output_dir / "splits" / "dev.json"
    test_file = output_dir / "splits" / "test.json"

    dev_data = json.loads(dev_file.read_text())
    test_data = json.loads(test_file.read_text())

    assert len(dev_data) == 1
    assert len(test_data) == 0


@pytest.mark.asyncio
async def test_split_dataset_custom_test_dataset(tmp_path: pathlib.Path, sample_golden_entries):
    golden_file = tmp_path / "golden.json"
    golden_file.write_text(json.dumps(sample_golden_entries))

    custom_test_entries = [
        {
            "id": "eval_custom_1",
            "database": "test_db",
            "nlq": "Custom test 1",
            "golden_sql": "SELECT 1",
        },
        {
            "id": "eval_custom_2",
            "database": "test_db",
            "nlq": "Custom test 2",
            "golden_sql": "SELECT 2",
        },
    ]
    custom_test_file = tmp_path / "custom_test.json"
    custom_test_file.write_text(json.dumps(custom_test_entries))

    output_dir = tmp_path / "experiment_custom"

    result = await split_dataset(
        golden_dataset_path=str(golden_file),
        output_dir=str(output_dir),
        custom_test_dataset_path=str(custom_test_file),
    )

    assert "Custom Holdout Test Dataset" in result
    assert "Successfully saved Dev and Holdout Test splits." in result

    dev_file = output_dir / "splits" / "dev.json"
    test_file = output_dir / "splits" / "test.json"

    dev_data = json.loads(dev_file.read_text())
    test_data = json.loads(test_file.read_text())

    assert len(dev_data) == len(sample_golden_entries)
    assert len(test_data) == 2


@pytest.mark.asyncio
async def test_split_dataset_output_dir_is_splits(tmp_path: pathlib.Path, sample_golden_entries):
    golden_file = tmp_path / "golden.json"
    golden_file.write_text(json.dumps(sample_golden_entries))

    splits_dir = tmp_path / "custom_splits" / "splits"

    result = await split_dataset(
        golden_dataset_path=str(golden_file),
        output_dir=str(splits_dir),
    )

    assert "Successfully partitioned" in result
    assert os.path.exists(splits_dir / "dev.json")
    assert os.path.exists(splits_dir / "test.json")


@pytest.mark.asyncio
async def test_split_dataset_tags_fallback(tmp_path: pathlib.Path):
    entries = [
        {
            "id": f"eval_{i}",
            "database": "test_db",
            "nlq": f"Query {i}",
            "golden_sql": f"SELECT {i}",
            "tags": ["topic: marketing", "complexity: low"],
        }
        for i in range(1, 6)
    ]
    golden_file = tmp_path / "golden.json"
    golden_file.write_text(json.dumps(entries))

    output_dir = tmp_path / "experiment_tags"

    result = await split_dataset(
        golden_dataset_path=str(golden_file),
        output_dir=str(output_dir),
        stratify_by="subdomain",
    )

    assert "`marketing`" in result


@pytest.mark.asyncio
async def test_split_dataset_file_not_found(tmp_path: pathlib.Path):
    result = await split_dataset(
        golden_dataset_path=str(tmp_path / "non_existent.json"),
        output_dir=str(tmp_path),
    )
    assert "Error splitting dataset" in result
    assert "Dataset file not found" in result


@pytest.mark.asyncio
async def test_split_dataset_invalid_json(tmp_path: pathlib.Path):
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("invalid json")
    result = await split_dataset(
        golden_dataset_path=str(bad_file),
        output_dir=str(tmp_path),
    )
    assert "Error splitting dataset" in result


@pytest.mark.asyncio
async def test_split_dataset_missing_keys(tmp_path: pathlib.Path):
    bad_file = tmp_path / "bad.json"
    bad_file.write_text(json.dumps([{"id": "1", "database": "db1"}]))
    result = await split_dataset(
        golden_dataset_path=str(bad_file),
        output_dir=str(tmp_path),
    )
    assert "Error splitting dataset" in result
    assert "missing required keys" in result
