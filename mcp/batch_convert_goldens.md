# Golden Data Batch Conversion Guide

This guide explains how to use the `batch_convert_goldens.py` script to convert natural language-to-SQL golden datasets into the structured JSON context format (`ContextSet`) required for DB context enrichment.

## Prerequisites

Ensure you are using the `local-eval-conversion` branch and have `uv` installed.

## Usage

Run the script using `uv` from within the `mcp` directory:

```bash
uv run python batch_convert_goldens.py --input <path_to_golden_json> --output <path_to_save_context_set>
```

### Arguments

| Argument    | Shorthand | Default                   | Description                                                                   |
| :---------- | :-------- | :------------------------ | :---------------------------------------------------------------------------- |
| `--input`   | `-i`      | (Required)                | Path to the golden JSON file (e.g., `../../eval_data/corretto_goldens.json`). |
| `--output`  | `-o`      | `context_set_output.json` | Path where the converted ContextSet will be saved.                            |
| `--dialect` | `-d`      | `postgresql`              | SQL dialect for parameterization (`postgresql`, `mysql`, `googlesql`).        |

## Input Format

The script expects a JSON array of objects with the following keys:

- `question`: The natural language query.
- `SQL` or `sql`: The ground truth SQL statement.

Example:

```json
[
  {
    "question": "How many users are there?",
    "SQL": "SELECT count(*) FROM users"
  }
]
```

## Output Format

The script generates a `ContextSet` JSON file containing `templates` with:

- Original query and SQL.
- Model-extracted `manifest` (generalized query).
- `parameterized` SQL and intent (using `$1`, `$2` etc. for Postgres).

## Testing

Run unit tests using:

```bash
uv run --extra test pytest tests/batch_convert_goldens_test.py
```
