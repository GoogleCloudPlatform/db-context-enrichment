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

    with pytest.raises(
        ValueError,
        match=r"required minimum holdout size of 45.*min_holdout_size=6",
    ):
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


@pytest.mark.asyncio
async def test_split_dataset_small_min_holdout_and_does_not_create_dir_on_error(
    tmp_path: pathlib.Path,
):
    items = [
        {
            "id": f"eval_{i:03d}",
            "nlq": f"Revenue for {2000 + i}",
            "golden_sql": f"SELECT SUM(x) FROM s WHERE y = {2000 + i}",
            "database": "db",
        }
        for i in range(2)
    ] + [
        {
            "id": f"single_{i}",
            "nlq": f"Single {i}",
            "golden_sql": f"SELECT COUNT(*) FROM t_{i}",
            "database": "db",
        }
        for i in range(3)
    ]
    input_file = tmp_path / "small5.json"
    with open(input_file, "w", encoding="utf-8") as f:
        json.dump(items, f)

    # 5 items with 1 multi-variation pair (max_possible_holdout = 1) succeeds when min_holdout_size=1
    out_dir = tmp_path / "small5_out"
    await split_dataset(str(input_file), str(out_dir), 0.7, 1)
    assert (out_dir / "splits" / "holdout.json").exists()

    # Verify failed split does not leave behind an empty splits/ directory
    fail_out = tmp_path / "fail_out"
    with pytest.raises(ValueError):
        await split_dataset(str(input_file), str(fail_out), 0.7, 45)
    assert not (fail_out / "splits").exists()


def test_normalize_sql_template_comments_in_list_and_negatives():
    q1 = "SELECT * FROM t WHERE x IN (1, 2) AND y > -5 -- trailing comment"
    q2 = "/* block */ SELECT * FROM t WHERE x IN (10, 20, 30) AND y > -100;"
    assert _normalize_sql_template(q1) == _normalize_sql_template(q2)


def test_normalize_sql_template_bigtable_mql_and_group_by_positions():
    # 1. Bigtable column qualifiers cf['col'] should stay distinct
    bt1 = "SELECT cf['clicks'] FROM my_bt WHERE rowkey = 'user_1'"
    bt2 = "SELECT cf['views'] FROM my_bt WHERE rowkey = 'user_1'"
    bt1_var = "SELECT cf['clicks'] FROM my_bt WHERE rowkey = 'user_2'"
    assert _normalize_sql_template(bt1) != _normalize_sql_template(bt2)
    assert _normalize_sql_template(bt1) == _normalize_sql_template(bt1_var)

    # 2. JSON / MQL double-quoted values after colons should be masked
    mql1 = 'db.users.find({"city": "Prague", "age": 25})'
    mql2 = 'db.users.find({"city": "Brno", "age": 40})'
    assert _normalize_sql_template(mql1) == _normalize_sql_template(mql2)

    # 3. Positional integers in GROUP BY / ORDER BY stay distinct while LIMIT literals are masked
    gb1 = "SELECT a, b, COUNT(*) FROM t WHERE yr = 2022 GROUP BY 1 ORDER BY 1 DESC LIMIT 5"
    gb1_var = "SELECT a, b, COUNT(*) FROM t WHERE yr = 2023 GROUP BY 1 ORDER BY 1 DESC LIMIT 10"
    gb2 = "SELECT a, b, COUNT(*) FROM t WHERE yr = 2022 GROUP BY 2 ORDER BY 2 DESC LIMIT 5"
    assert _normalize_sql_template(gb1) == _normalize_sql_template(gb1_var)
    assert _normalize_sql_template(gb1) != _normalize_sql_template(gb2)


@pytest.mark.asyncio
async def test_split_dataset_excludes_previous_holdout_explicit_and_autodetected(
    tmp_path: pathlib.Path, sample_golden_entries
):
    # Experiment 1: 150 items (30 templates x 5 vars) -> 105 hillclimb, 45 holdout
    exp1_dir = tmp_path / ".context-engineering" / "experiments" / "exp1"
    exp1_dataset_dir = exp1_dir / "dataset"
    exp1_dataset_dir.mkdir(parents=True)
    exp1_golden = exp1_dataset_dir / "golden.json"
    exp1_golden.write_text(json.dumps(sample_golden_entries), encoding="utf-8")

    await split_dataset(str(exp1_golden), str(exp1_dataset_dir))
    exp1_holdout_path = exp1_dataset_dir / "splits" / "holdout.json"
    exp1_holdout = json.loads(exp1_holdout_path.read_text(encoding="utf-8"))
    exp1_holdout_ids = {item["id"] for item in exp1_holdout}
    assert len(exp1_holdout_ids) == 45

    # Expand dataset for Experiment 2: add 2 new variations per template (60 new items -> 210 total)
    expanded_entries = list(sample_golden_entries)
    for t in range(1, 31):
        for i in range(6, 8):
            expanded_entries.append(
                {
                    "id": f"eval_template_{t}_var_{i}",
                    "database": "test_db",
                    "nlq": f"Query template {t} variation {i}",
                    "golden_sql": f"SELECT COUNT(*) FROM table_{t} WHERE year = {2020 + i}",
                }
            )

    # Case B: Explicit previous_holdout_path
    exp2_explicit_dir = (
        tmp_path / ".context-engineering" / "experiments" / "exp2-explicit" / "dataset"
    )
    exp2_explicit_dir.mkdir(parents=True)
    exp2_golden = exp2_explicit_dir / "golden.json"
    exp2_golden.write_text(json.dumps(expanded_entries), encoding="utf-8")

    await split_dataset(
        str(exp2_golden),
        str(exp2_explicit_dir),
        previous_holdout_path=str(exp1_holdout_path),
    )
    exp2_explicit_holdout = json.loads(
        (exp2_explicit_dir / "splits" / "holdout.json").read_text(encoding="utf-8")
    )
    exp2_explicit_holdout_ids = {item["id"] for item in exp2_explicit_holdout}
    # Zero overlap with Experiment 1's holdout IDs!
    assert exp1_holdout_ids.isdisjoint(exp2_explicit_holdout_ids)

    # Case A: Auto-detected from <exp_root>/hillclimb/experiment_state.md
    exp2_auto_root = tmp_path / ".context-engineering" / "experiments" / "exp1-v2"
    exp2_auto_dataset = exp2_auto_root / "dataset"
    exp2_auto_hillclimb = exp2_auto_root / "hillclimb"
    exp2_auto_dataset.mkdir(parents=True)
    exp2_auto_hillclimb.mkdir(parents=True)
    (exp2_auto_dataset / "golden.json").write_text(
        json.dumps(expanded_entries), encoding="utf-8"
    )
    (exp2_auto_hillclimb / "experiment_state.md").write_text(
        "# Hill-Climbing Experiment: exp1-v2\n\n"
        "## Metadata\n"
        "- Cloned from: exp1\n"
        "- Source evaluation report: ./.context-engineering/experiments/exp1/hillclimb/final_evaluation_report.md\n",
        encoding="utf-8",
    )

    await split_dataset(
        str(exp2_auto_dataset / "golden.json"),
        str(exp2_auto_dataset),
    )
    exp2_auto_holdout = json.loads(
        (exp2_auto_dataset / "splits" / "holdout.json").read_text(encoding="utf-8")
    )
    exp2_auto_holdout_ids = {item["id"] for item in exp2_auto_holdout}
    assert exp1_holdout_ids.isdisjoint(exp2_auto_holdout_ids)
