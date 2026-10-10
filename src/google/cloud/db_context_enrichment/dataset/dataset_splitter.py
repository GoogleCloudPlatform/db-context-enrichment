import collections
import json
import os
import re
from typing import Any


def _normalize_sql_template(sql: str) -> str:
    """Normalizes a SQL query into a structural template key to group variations."""
    cleaned = sql.strip().rstrip(";").strip()
    # Mask single-quoted string literals (including escaped '' quotes)
    normalized = re.sub(r"'(?:''|[^'])*'", "'?'", cleaned)
    # Mask numeric literals (integers and decimals)
    normalized = re.sub(r"\b\d+(?:\.\d+)?\b", "?", normalized)
    # Normalize whitespace
    normalized = re.sub(r"\s+", " ", normalized).strip().lower()
    return normalized


def _extract_template_key(entry: dict[str, Any]) -> str:
    """Extracts the structural query template from a dataset entry's golden_sql."""
    return _normalize_sql_template(entry.get("golden_sql", ""))


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
    """Resolves output file paths for hillclimb.json and holdout.json."""
    norm_dir = os.path.normpath(os.path.abspath(output_dir))
    if os.path.basename(norm_dir) == "splits":
        splits_dir = norm_dir
    else:
        splits_dir = os.path.join(norm_dir, "splits")

    os.makedirs(splits_dir, exist_ok=True)
    dev_path = os.path.join(splits_dir, "hillclimb.json")
    test_path = os.path.join(splits_dir, "holdout.json")
    return dev_path, test_path


async def split_dataset(
    golden_dataset_path: str,
    output_dir: str,
    hillclimb_ratio: float = 0.7,
    min_holdout_size: int = 45,
    custom_test_dataset_path: str | None = None,
) -> str:
    """Splits a golden dataset into Hillclimbing and Holdout splits.

    Strictly enforces that every normalized SQL template (key) present in holdout.json
    is also included in hillclimb.json (holdout_keys <= hillclimb_keys), differing in
    natural-language phrasing and/or literal parameters.
    Enforces a minimum holdout set size of 45 by default and a default hillclimb ratio of 0.7
    (e.g., 150 total items -> 105 hillclimb.json and 45 holdout.json).
    Fails early if pre-partitioned datasets are provided.

    Args:
        golden_dataset_path: Path to the golden dataset JSON file.
        output_dir: Directory where splits/hillclimb.json and splits/holdout.json should be saved.
        hillclimb_ratio: Ratio of data to assign to the Hillclimbing split (default: 0.7).
        min_holdout_size: Minimum required number of items in the Holdout split (default: 45).
        custom_test_dataset_path: Must be None. If provided, fails early per spec.

    Returns:
        A concise summary message confirming the split creation.
    """
    if custom_test_dataset_path and custom_test_dataset_path.strip():
        raise ValueError(
            "[ERROR] InvalidDatasetConfiguration: Providing pre-partitioned hillclimbing and holdout datasets is not supported.\n"
            "Reason: To guarantee that every normalized SQL query template in the holdout set is included in the "
            "hillclimbing set with distinct phrasing variations, Crema must perform expansion and stratified splitting internally.\n"
            "Action Required: Provide a single golden dataset (User-Supplied Dataset scenario) or allow Crema to "
            "generate and split the dataset from your schema (Full Automated Flow)."
        )

    if not (0.0 < hillclimb_ratio < 1.0):
        raise ValueError(
            f"hillclimb_ratio must be strictly between 0 and 1, got {hillclimb_ratio}"
        )

    if min_holdout_size < 1:
        raise ValueError(f"min_holdout_size must be at least 1, got {min_holdout_size}")

    golden_data = _load_and_validate_dataset(golden_dataset_path)
    total_items = len(golden_data)
    dev_path, test_path = _resolve_split_paths(output_dir)

    # Group entries by normalized SQL template key to guarantee every holdout template exists in hillclimb
    groups_dict: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for entry in golden_data:
        key = _extract_template_key(entry)
        groups_dict[key].append(entry)

    # Sort groups deterministically by template key, and sort items within each group by id
    sorted_keys = sorted(groups_dict.keys())
    groups: list[list[dict[str, Any]]] = [
        sorted(groups_dict[k], key=lambda x: str(x.get("id", ""))) for k in sorted_keys
    ]

    # Calculate maximum possible holdout items while keeping at least 1 item per template in hillclimb.json
    max_possible_holdout = sum(len(g) - 1 for g in groups if len(g) >= 2)
    target_holdout = max(
        min_holdout_size, int(round(total_items * (1.0 - hillclimb_ratio)))
    )

    if max_possible_holdout < target_holdout:
        num_singletons = sum(1 for g in groups if len(g) == 1)
        num_multi = len(groups) - num_singletons
        raise ValueError(
            f"Dataset has {total_items} items across {len(groups)} normalized SQL templates "
            f"({num_multi} multi-variation templates, {num_singletons} single-variation templates), "
            f"which can yield at most {max_possible_holdout} holdout items while ensuring every normalized SQL "
            f"template in holdout.json is included in hillclimb.json. This is smaller than "
            f"the required minimum holdout size of {min_holdout_size} (or target {target_holdout}). "
            f"Please expand existing query templates using template-preserving strategies (Paraphrasing, "
            f"Distraction Injection, Linguistic Variation, or Value Substitution) so that there are at least "
            f"150 items with sufficient multi-variation templates (105 hillclimbing / 45 holdout)."
        )

    # Initial holdout allocation per group:
    # - Single-item groups (n == 1) MUST have holdout_count = 0 so their template goes to hillclimb.json.
    # - Multi-item groups (n >= 2) can allocate at most n - 1 items to holdout.json so at least 1 item stays in hillclimb.json.
    holdout_counts: list[int] = []
    for g in groups:
        n = len(g)
        if n == 1:
            holdout_counts.append(0)
        else:
            h = max(1, min(n - 1, int(n * (1.0 - hillclimb_ratio))))
            holdout_counts.append(h)

    current_holdout = sum(holdout_counts)

    # Adjust holdout_counts up to reach target_holdout if needed (never exceeding n - 1 so dev_count >= 1)
    while current_holdout < target_holdout:
        best_idx = -1
        best_remainder = -1e9
        for idx, g in enumerate(groups):
            n = len(g)
            if holdout_counts[idx] < n - 1:
                remainder = (n * (1.0 - hillclimb_ratio)) - holdout_counts[idx]
                if remainder > best_remainder:
                    best_remainder = remainder
                    best_idx = idx
        if best_idx == -1:
            break
        holdout_counts[best_idx] += 1
        current_holdout += 1

    # Adjust holdout_counts down if initial allocation exceeded target_holdout.
    # First prefer reducing groups with holdout_counts[idx] > 1 to maximize template diversity in holdout;
    # if all multi-item groups are already at 1 and current_holdout still exceeds target_holdout,
    # allow reducing from 1 to 0 (moving the item to hillclimb.json, which still preserves holdout_keys <= hillclimb_keys).
    while current_holdout > target_holdout:
        worst_idx = -1
        worst_remainder = 1e9
        min_allowed = 1 if any(c > 1 for c in holdout_counts) else 0
        for idx, g in enumerate(groups):
            n = len(g)
            if holdout_counts[idx] > min_allowed:
                remainder = (n * (1.0 - hillclimb_ratio)) - holdout_counts[idx]
                if remainder < worst_remainder:
                    worst_remainder = remainder
                    worst_idx = idx
        if worst_idx == -1:
            break
        holdout_counts[worst_idx] -= 1
        current_holdout -= 1

    dev_items: list[dict[str, Any]] = []
    test_items: list[dict[str, Any]] = []

    for idx, g in enumerate(groups):
        h = holdout_counts[idx]
        dev_count = len(g) - h
        if h > 0 and dev_count < 1:
            raise ValueError(
                f"Internal split error: group {idx} has {h} holdout items but 0 hillclimb items."
            )
        dev_items.extend(g[:dev_count])
        test_items.extend(g[dev_count:])

    if len(test_items) < min_holdout_size:
        raise ValueError(
            f"Holdout set size ({len(test_items)}) is smaller than the required minimum size of {min_holdout_size}."
        )

    # Explicitly enforce that every normalized SQL key in holdout.json is included in hillclimb.json
    hillclimb_keys = {_extract_template_key(item) for item in dev_items}
    holdout_keys = {_extract_template_key(item) for item in test_items}
    missing_in_hillclimb = holdout_keys - hillclimb_keys
    if missing_in_hillclimb:
        raise ValueError(
            f"Split invariant violated: {len(missing_in_hillclimb)} normalized SQL template(s) in holdout.json "
            f"are not included in hillclimb.json."
        )

    with open(dev_path, "w", encoding="utf-8") as f:
        json.dump(dev_items, f, indent=2)

    with open(test_path, "w", encoding="utf-8") as f:
        json.dump(test_items, f, indent=2)

    return (
        f"Successfully partitioned {len(golden_data)} items across {len(groups)} query templates "
        f"into Hillclimbing ({len(dev_items)} items) and Holdout ({len(test_items)} items).\n"
        f"- Hillclimbing split saved to: {dev_path}\n"
        f"- Holdout split saved to: {test_path}\n"
        f"- Template Overlap: 100% of holdout SQL templates ({len(holdout_keys)}/{len(holdout_keys)}) are included in hillclimb.json."
    )
