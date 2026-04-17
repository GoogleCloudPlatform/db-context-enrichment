import csv
import os
import re
import textwrap
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class ScoreRecord:
    id: str
    score: float
    comparison_logs: str = "N/A"


@dataclass
class EvalRecord:
    id: str
    nl_prompt: str = "N/A"
    golden_sql: str = "N/A"
    generated_sql: str = "N/A"
    sql_generator_error: str = "N/A"
    generated_error: str = "N/A"
    other: str = "N/A"


def read_eval_results(run_folder_path: str, offset: int = 0, batch_size: int = 10) -> str:
    """
    Reads evaluation results from a folder and produces a markdown summary.

    Args:
        run_folder_path: The absolute path to the evaluation run result folder, which ends with the eval run job id.
        offset: Offset to start reading failure cases from (default: 0).
        batch_size: Number of failure cases to show in the report (default: 10).

    Returns:
        A string in markdown format containing the summary and failure cases.
    """
    scores_path = os.path.join(run_folder_path, "scores.csv")
    evals_path = os.path.join(run_folder_path, "evals.csv")

    # Read Summary
    summary_md = _read_summary(run_folder_path)

    # Read Scores to find failures
    with open(scores_path, mode="r", encoding="utf-8") as f:
        failures = sorted(
            [
                ScoreRecord(
                    id=row["id"],
                    score=score,
                    comparison_logs=row.get("comparison_logs") or "N/A",
                )
                for row in csv.DictReader(f)
                if (score := _get_score(row)) is not None and score < 100
            ],
            key=lambda x: _natural_sort_key(x.id),
        )

    if not failures:
        return summary_md + "No failure cases found (all passed)."

    # Apply batching
    batched_failures = failures[offset : offset + batch_size]

    # Add failures info to summary
    summary_md += textwrap.dedent(
        f"""\
        ## All Failures
        {', '.join([str(f.id) for f in failures])}

        **Showing failures**: {offset + 1} to {min(offset + batch_size, len(failures))} of {len(failures)}

        """
    )

    # Read Evals to get prompts and golden SQL
    with open(evals_path, mode="r", encoding="utf-8") as f:
        evals_data = {
            row["id"]: EvalRecord(
                id=row["id"],
                nl_prompt=row.get("nl_prompt") or "N/A",
                golden_sql=row.get("golden_sql") or "N/A",
                generated_sql=row.get("generated_sql") or "N/A",
                sql_generator_error=row.get("sql_generator_error") or "N/A",
                generated_error=row.get("generated_error") or "N/A",
                other=row.get("other") or "N/A",
            )
            for row in csv.DictReader(f)
        }

    # Format Failures
    failures_md = _format_failures(batched_failures, evals_data)

    return summary_md + failures_md


def _format_failures(failures: List[ScoreRecord], evals_data: Dict[str, EvalRecord]) -> str:
    failures_md = "# Failure Cases\n\n"
    for fail in failures:
        fail_id = fail.id
        eval_info = evals_data.get(fail_id, EvalRecord(id=fail_id))

        failures_md += textwrap.dedent(
            f"""\
            ## Case ID: {fail_id} (Score: {fail.score})

            **Prompt**:
            {eval_info.nl_prompt}

            **Golden SQL**:
            ```sql
            {eval_info.golden_sql}
            ```

            **Generated SQL**:
            ```sql
            {eval_info.generated_sql}
            ```

            **SQL Generator Error** (Errors during SQL generation):
            ```
            {eval_info.sql_generator_error}
            ```

            **Execution Error** (Errors when executing the generated SQL):
            ```
            {eval_info.generated_error}
            ```

            **Additional Output**:
            ```
            {eval_info.other}
            ```

            **Evaluation Details**:
            {fail.comparison_logs}
            
            ---

            """
        )
    return failures_md


def _read_summary(run_folder_path: str) -> str:
    summary_path = os.path.join(run_folder_path, "summary.csv")
    summary_md = "# Evaluation Summary\n\n"
    with open(summary_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            summary_md += textwrap.dedent(
                f"""\
                - **Metric**: {row.get("metric_name", "N/A")}
                  - **Correct / Total**: {row.get("correct_results_count", "N/A")}/{row.get("total_results_count", "N/A")}
                  - **Run Time**: {row.get("run_time", "N/A")}

                """
            )
    return summary_md


def _natural_sort_key(val):
    """
    Splits a string into a list of string and integer chunks.
    Example: "user10" -> ["user", 10, ""]
    """
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', str(val))]


def _get_score(row: Dict[str, str]) -> Optional[float]:
    try:
        return float(row.get("score", ""))
    except ValueError:
        return None

