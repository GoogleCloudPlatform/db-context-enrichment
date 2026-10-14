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
    # 30 query templates, 5 variations each -> 150 total items (default size before split)
    for t in range(1, 31):
        for i in range(1, 6):
            entries.append(
                {
                    "id": f"eval_template_{t}_var_{i}",
                    "database": "test_db",
                    "nlq": f"Query template {t} variation {i}",
                    "golden_sql": f"SELECT COUNT(*) FROM table_{t} WHERE year = {2020 + i}",
                }
            )
    return entries


@pytest.mark.asyncio
async def test_split_dataset_default_150_to_105_and_45(
    tmp_path: pathlib.Path, sample_golden_entries
):
    input_file = tmp_path / "golden.json"
    with open(input_file, "w", encoding="utf-8") as f:
        json.dump(sample_golden_entries, f)

    output_dir = tmp_path / "experiment"
    # Default hillclimb_ratio=0.7, min_holdout_size=45
    res = await split_dataset(str(input_file), str(output_dir))

    assert (
        "Successfully partitioned 150 items across 30 query templates into Hillclimbing (105 items) and Holdout (45 items)"
        in res
    )
    dev_file = output_dir / "splits" / "hillclimb.json"
    test_file = output_dir / "splits" / "holdout.json"

    assert dev_file.exists()
    assert test_file.exists()

    with open(dev_file) as f:
        dev_data = json.load(f)
    with open(test_file) as f:
        test_data = json.load(f)

    # 150 items total with ratio 0.7 -> 105 hillclimb, 45 holdout
    assert len(dev_data) == 105
    assert len(test_data) == 45

    # Check 100% template overlap across all 30 templates
    dev_templates = {_normalize_sql_template(e["golden_sql"]) for e in dev_data}
    test_templates = {_normalize_sql_template(e["golden_sql"]) for e in test_data}

    assert len(dev_templates) == 30
    assert dev_templates == test_templates


@pytest.mark.asyncio
async def test_split_dataset_enforces_min_holdout_size_45(tmp_path: pathlib.Path):
    # Only 20 items across 4 templates -> max holdout is 16 < 45 -> raises ValueError
    small_entries = []
    for t in range(1, 5):
        for i in range(1, 6):
            small_entries.append(
                {
                    "id": f"eval_{t}_{i}",
                    "database": "test_db",
                    "nlq": f"Query {t} var {i}",
                    "golden_sql": f"SELECT * FROM table_{t} WHERE id = {i}",
                }
            )
    input_file = tmp_path / "small.json"
    with open(input_file, "w", encoding="utf-8") as f:
        json.dump(small_entries, f)

    with pytest.raises(ValueError, match="required minimum holdout size of 45"):
        await split_dataset(str(input_file), str(tmp_path / "out"))


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


@pytest.mark.asyncio
async def test_split_dataset_enforces_all_holdout_keys_in_hillclimb_with_singletons_and_pairs(
    tmp_path: pathlib.Path,
):
    # 50 templates with 2 variations each (100 items) + 50 single-variation templates (50 items) = 150 items
    entries = []
    for t in range(1, 51):
        for i in range(1, 3):
            entries.append(
                {
                    "id": f"eval_pair_{t}_{i}",
                    "database": "test_db",
                    "nlq": f"Pair template {t} var {i}",
                    "golden_sql": f"SELECT * FROM pair_table_{t} WHERE amount > {10.5 * i} AND name = 'O''Reilly';",
                }
            )
    for s in range(1, 51):
        entries.append(
            {
                "id": f"eval_singleton_{s}",
                "database": "test_db",
                "nlq": f"Singleton query {s}",
                "golden_sql": f"SELECT COUNT(*) FROM singleton_table_{s}",
            }
        )

    input_file = tmp_path / "mixed_golden.json"
    with open(input_file, "w", encoding="utf-8") as f:
        json.dump(entries, f)

    output_dir = tmp_path / "mixed_out"
    res = await split_dataset(str(input_file), str(output_dir))
    assert "100% of holdout SQL templates (45/45) are included in hillclimb.json" in res

    with open(output_dir / "splits" / "hillclimb.json", encoding="utf-8") as f:
        hillclimb_data = json.load(f)
    with open(output_dir / "splits" / "holdout.json", encoding="utf-8") as f:
        holdout_data = json.load(f)

    assert len(hillclimb_data) == 105
    assert len(holdout_data) == 45

    hillclimb_keys = {_normalize_sql_template(e["golden_sql"]) for e in hillclimb_data}
    holdout_keys = {_normalize_sql_template(e["golden_sql"]) for e in holdout_data}

    # Every normalized SQL key in holdout.json MUST be included in hillclimb.json
    assert holdout_keys.issubset(hillclimb_keys)
    assert len(holdout_keys - hillclimb_keys) == 0
