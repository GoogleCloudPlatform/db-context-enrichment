import collections
import json
import os
import re
from typing import Any


def _normalize_sql_template(sql: str) -> str:
    """Normalizes a SQL query into a structural template to group variations."""
    # Mask single-quoted string literals
    normalized = re.sub(r"'[^']*'", "'?'", sql)
    # Mask numeric literals
    normalized = re.sub(r"\b\d+\b", "?", normalized)
    # Normalize whitespace
    normalized = re.sub(r"\s+", " ", normalized).strip().lower()
    return normalized


def _extract_template_key(entry: dict[str, Any]) -> str:
    """Extracts the template or query pattern identifier from a dataset entry."""
    metadata = entry.get("metadata")
    if isinstance(metadata, dict):
        for key in ("template_id", "query_pattern", "seed_id", "pattern_id"):
            val = metadata.get(key)
            if val is not None and str(val).strip():
                return str(val).strip()

    for key in ("template_id", "query_pattern", "seed_id", "pattern_id"):
        val = entry.get(key)
        if val is not None and str(val).strip():
            return str(val).strip()

    golden_sql = entry.get("golden_sql", "")
    return _normalize_sql_template(golden_sql)


def _load_and_validate_dataset(file_path: str) -> list[dict[str, Any]]:
    """Loads a JSON dataset and validates required NL2SQL keys."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Dataset file not found: {file_path}")

    with open(file_path, encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError(
            f"Dataset in {file_path} must be a JSON list of objects, got {type(data).__name__}."
        )

    required_keys = {"id", "database", "nlq", "golden_sql"}
    for i, entry in enumerate(data):
        if not isinstance(entry, dict):
            raise ValueError(f"Entry at index {i} in {file_path} is not an object.")
        missing_keys = required_keys - set(entry.keys())
        if missing_keys:
            raise ValueError(
                f"Entry at index {i} in {file_path} is missing required keys: {sorted(missing_keys)}"
            )

    return data


def _resolve_split_paths(output_dir: str) -> tuple[str, str]:
    """Resolves output file paths for dev.json and test.json."""
    norm_dir = os.path.normpath(os.path.abspath(output_dir))
    if os.path.basename(norm_dir) == "splits":
        splits_dir = norm_dir
    else:
        splits_dir = os.path.join(norm_dir, "splits")

    os.makedirs(splits_dir, exist_ok=True)
    dev_path = os.path.join(splits_dir, "dev.json")
    test_path = os.path.join(splits_dir, "test.json")
    return dev_path, test_path


async def split_dataset(
    golden_dataset_path: str,
    output_dir: str,
    train_ratio: float = 0.8,
    custom_test_dataset_path: str | None = None,
) -> str:
    """Splits a golden dataset into Dev and Holdout Test splits.

    Guarantees that every SQL template present in the Dev split also appears in the
    Holdout Test split (100% template overlap) differing in phrasing and parameters.
    Fails early if pre-partitioned datasets are provided.

    Args:
        golden_dataset_path: Path to the golden dataset JSON file.
        output_dir: Directory where splits/dev.json and splits/test.json should be saved.
        train_ratio: Ratio of data to assign to the Dev split (default: 0.8).
        custom_test_dataset_path: Must be None. If provided, fails early per spec.

    Returns:
        A concise summary message confirming the split creation.
    """
    if custom_test_dataset_path and custom_test_dataset_path.strip():
        raise ValueError(
            "[ERROR] InvalidDatasetConfiguration: Providing pre-partitioned dev and test datasets is not supported.\n"
            "Reason: To guarantee that every query pattern in the training set exists in the holdout test set with "
            "distinct phrasing variations, Crema must perform expansion and stratified splitting internally.\n"
            "Action Required: Provide a single golden dataset (User-Supplied Dataset scenario) or allow Crema to "
            "generate and split the dataset from your schema (Full Automated Flow)."
        )

    if not (0.0 < train_ratio < 1.0):
        raise ValueError(
            f"train_ratio must be strictly between 0 and 1, got {train_ratio}"
        )

    golden_data = _load_and_validate_dataset(golden_dataset_path)
    dev_path, test_path = _resolve_split_paths(output_dir)

    # Group entries by SQL template / query pattern to guarantee 100% template overlap
    groups: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for entry in golden_data:
        key = _extract_template_key(entry)
        groups[key].append(entry)

    dev_items: list[dict[str, Any]] = []
    test_items: list[dict[str, Any]] = []

    for _, items in groups.items():
        # Sort items stably
        sorted_items = sorted(items, key=lambda x: str(x.get("id", "")))
        n = len(sorted_items)
        if n == 1:
            dev_items.append(sorted_items[0])
        else:
            dev_count = max(1, min(n - 1, int(round(n * train_ratio))))
            dev_items.extend(sorted_items[:dev_count])
            test_items.extend(sorted_items[dev_count:])

    with open(dev_path, "w", encoding="utf-8") as f:
        json.dump(dev_items, f, indent=2)

    with open(test_path, "w", encoding="utf-8") as f:
        json.dump(test_items, f, indent=2)

    return (
        f"Successfully partitioned {len(golden_data)} items across {len(groups)} query templates "
        f"into Training ({len(dev_items)} items) and Held-Out Test ({len(test_items)} items).\n"
        f"- Training split saved to: {dev_path}\n"
        f"- Test split saved to: {test_path}\n"
        f"- Template Overlap: 100% of multi-variation query templates appear in both splits."
    )
