import collections
import json
import os
from typing import Any


def _extract_stratum(entry: dict[str, Any], stratify_by: str) -> str:
    """Extracts the stratification dimension value from a dataset entry."""
    # 1. Check metadata dictionary
    metadata = entry.get("metadata")
    if isinstance(metadata, dict):
        val = metadata.get(stratify_by)
        if val is not None and str(val).strip():
            return str(val).strip()

    # 2. Check top-level key
    val = entry.get(stratify_by)
    if val is not None and str(val).strip():
        return str(val).strip()

    # 3. Check tags list
    tags = entry.get("tags")
    if isinstance(tags, list):
        prefix = f"{stratify_by}:"
        for tag in tags:
            if isinstance(tag, str) and tag.lower().startswith(prefix.lower()):
                val = tag[len(prefix) :].strip()
                if val:
                    return val

        # Fallback tags for common alias names
        if stratify_by in ("subdomain", "domain"):
            for tag in tags:
                if isinstance(tag, str) and tag.lower().startswith("topic:"):
                    val = tag[len("topic:") :].strip()
                    if val:
                        return val
        elif stratify_by in ("complexity_tier", "complexity"):
            for tag in tags:
                if isinstance(tag, str) and tag.lower().startswith("complexity:"):
                    val = tag[len("complexity:") :].strip()
                    if val:
                        return val

    # 4. Fallback aliases on top-level or metadata
    if stratify_by in ("subdomain", "domain"):
        if isinstance(metadata, dict) and metadata.get("topic"):
            return str(metadata.get("topic")).strip()
        if entry.get("topic"):
            return str(entry.get("topic")).strip()
    elif stratify_by in ("complexity_tier", "complexity"):
        if isinstance(metadata, dict) and metadata.get("complexity"):
            return str(metadata.get("complexity")).strip()
        if entry.get("complexity"):
            return str(entry.get("complexity")).strip()

    return "general"


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
    custom_test_dataset_path: str | None = None,
    stratify_by: str = "subdomain",
    train_ratio: float = 0.8,
) -> str:
    """Splits a golden dataset into Dev and Holdout Test splits.

    Args:
        golden_dataset_path: Path to the golden dataset JSON file.
        output_dir: Directory where splits/dev.json and splits/test.json should be saved.
        custom_test_dataset_path: Optional path to an existing custom test dataset file.
        stratify_by: Metadata attribute to stratify by (default: 'subdomain').
        train_ratio: Ratio of data to assign to the Dev split (default: 0.8).

    Returns:
        A markdown report detailing the split summary, item counts, and output paths.
    """
    try:
        if not (0.0 < train_ratio < 1.0):
            raise ValueError(
                f"train_ratio must be strictly between 0 and 1, got {train_ratio}"
            )

        golden_data = _load_and_validate_dataset(golden_dataset_path)
        dev_path, test_path = _resolve_split_paths(output_dir)

        # Case A: Custom test dataset provided
        if custom_test_dataset_path and custom_test_dataset_path.strip():
            custom_test_data = _load_and_validate_dataset(custom_test_dataset_path.strip())

            with open(dev_path, "w", encoding="utf-8") as f:
                json.dump(golden_data, f, indent=2)

            with open(test_path, "w", encoding="utf-8") as f:
                json.dump(custom_test_data, f, indent=2)

            return (
                f"# Evaluation Dataset Split Report\n\n"
                f"- **Split Mode**: Custom Holdout Test Dataset\n"
                f"- **Golden Dataset**: `{golden_dataset_path}` ({len(golden_data)} items)\n"
                f"- **Custom Test Dataset**: `{custom_test_dataset_path}` ({len(custom_test_data)} items)\n"
                f"- **Dev Split Saved**: `{dev_path}` ({len(golden_data)} items)\n"
                f"- **Holdout Test Split Saved**: `{test_path}` ({len(custom_test_data)} items)\n\n"
                f"Successfully saved Dev and Holdout Test splits."
            )

        # Case B: Automated Stratified Partitioning
        groups: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
        for entry in golden_data:
            stratum = _extract_stratum(entry, stratify_by)
            groups[stratum].append(entry)

        dev_items: list[dict[str, Any]] = []
        test_items: list[dict[str, Any]] = []
        stratum_stats: list[dict[str, Any]] = []
        low_quorum_strata: list[str] = []

        for stratum, items in groups.items():
            n = len(items)
            if n == 1:
                dev_count = 1
                test_count = 0
                dev_items.append(items[0])
            else:
                dev_count = max(1, min(n - 1, int(round(n * train_ratio))))
                test_count = n - dev_count
                dev_items.extend(items[:dev_count])
                test_items.extend(items[dev_count:])

            is_low_quorum = n < 5
            if is_low_quorum:
                low_quorum_strata.append(stratum)

            stratum_stats.append(
                {
                    "stratum": stratum,
                    "total": n,
                    "dev": dev_count,
                    "test": test_count,
                    "status": "⚠️ Low Quorum (< 5)" if is_low_quorum else "OK (>= 5)",
                }
            )

        with open(dev_path, "w", encoding="utf-8") as f:
            json.dump(dev_items, f, indent=2)

        with open(test_path, "w", encoding="utf-8") as f:
            json.dump(test_items, f, indent=2)

        dev_pct = int(round(train_ratio * 100))
        test_pct = 100 - dev_pct

        table_rows = "\n".join(
            f"| `{s['stratum']}` | {s['total']} | {s['dev']} | {s['test']} | {s['status']} |"
            for s in stratum_stats
        )

        warning_block = ""
        if low_quorum_strata:
            quoted_strata = ", ".join(f"`{s}`" for s in low_quorum_strata)
            warning_block = (
                f"\n> ⚠️ **Stratum Quorum Notice**: The following subdomain(s)/strata have fewer than 5 pairs: {quoted_strata}. "
                f"Holdout test evaluation will proceed, but expanding pairs for these subdomains via "
                f"`context-engineering-dataset-generation` is recommended for robust test coverage.\n"
            )

        return (
            f"# Evaluation Dataset Split Report\n\n"
            f"- **Split Mode**: Stratified Partitioning (stratified by `{stratify_by}`, {dev_pct}% Dev / {test_pct}% Test)\n"
            f"- **Source Dataset**: `{golden_dataset_path}` ({len(golden_data)} items)\n"
            f"- **Dev Split Saved**: `{dev_path}` ({len(dev_items)} items)\n"
            f"- **Holdout Test Split Saved**: `{test_path}` ({len(test_items)} items)\n\n"
            f"### Stratum Breakdown\n\n"
            f"| Stratum (`{stratify_by}`) | Total Items | Dev Items | Test Items | Status |\n"
            f"| :--- | :--- | :--- | :--- | :--- |\n"
            f"{table_rows}\n"
            f"{warning_block}\n"
            f"Successfully partitioned and saved Dev and Holdout Test splits."
        )

    except (json.JSONDecodeError, ValueError, OSError, FileNotFoundError) as e:
        return f"Error splitting dataset: {str(e)}"
