import csv
import os
from typing import Dict, List

def read_eval_results(run_folder_path: str) -> str:
    """
    Reads evaluation results from a folder and produces a markdown summary.
    
    Args:
        run_folder_path: Path to the evaluation run folder.
        
    Returns:
        A string in markdown format containing the summary and failure cases.
    """
    summary_path = os.path.join(run_folder_path, "summary.csv")
    scores_path = os.path.join(run_folder_path, "scores.csv")
    evals_path = os.path.join(run_folder_path, "evals.csv")
    
    if not os.path.exists(summary_path):
        return f"Error: {summary_path} not found."
    if not os.path.exists(scores_path):
        return f"Error: {scores_path} not found."
    if not os.path.exists(evals_path):
        return f"Error: {evals_path} not found."
        
    # Read Summary
    summary_md = "# Evaluation Summary\n\n"
    try:
        with open(summary_path, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                summary_md += f"- **Metric**: {row.get('metric_name')}\n"
                summary_md += f"  - **Score**: {row.get('metric_score')}\n"
                summary_md += f"  - **Correct**: {row.get('correct_results_count')}/{row.get('total_results_count')}\n"
                summary_md += f"  - **Run Time**: {row.get('run_time')}\n\n"
    except Exception as e:
        return f"Error reading summary.csv: {e}"
        
    # Read Scores to find failures
    failures = []
    try:
        with open(scores_path, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                score_str = row.get("score")
                if score_str is not None:
                    try:
                        score = float(score_str)
                        if score < 100:
                            failures.append({
                                "id": row.get("id"),
                                "score": score,
                                "error_analysis": row.get("comparison_logs"),
                                "generated_sql": row.get("generated_sql")
                            })
                    except ValueError:
                        # If score is not a number, skip or handle?
                        # Let's assume it's a number if present.
                        pass
    except Exception as e:
        return f"Error reading scores.csv: {e}"
        
    if not failures:
        return summary_md + "No failure cases found (all passed or score 100)."
        
    # Sort failures by ID
    failures.sort(key=lambda x: str(x.get("id", "")))
    
    # Add list of failed cases to summary
    summary_md += f"## Failed Cases\n{', '.join([str(f['id']) for f in failures])}\n\n"
        
    # Read Evals to get prompts and golden SQL
    evals_data = {}
    try:
        with open(evals_path, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                evals_data[row.get("id")] = {
                    "prompt": row.get("nl_prompt"),
                    "golden_sql": row.get("golden_sql"),
                    "generated_sql": row.get("generated_sql")
                }
    except Exception as e:
        return f"Error reading evals.csv: {e}"
        
    # Format Failures
    failures_md = "# Failure Cases\n\n"
    for fail in failures:
        fail_id = fail["id"]
        eval_info = evals_data.get(fail_id, {"prompt": "N/A", "golden_sql": "N/A"})
        
        failures_md += f"## Case ID: {fail_id} (Score: {fail['score']})\n\n"
        failures_md += f"**Prompt**:\n{eval_info['prompt']}\n\n"
        failures_md += f"**Golden SQL**:\n```sql\n{eval_info['golden_sql']}\n```\n\n"
        
        # Use generated SQL from scores if available, else from evals
        gen_sql = fail.get("generated_sql") or eval_info.get("generated_sql")
        failures_md += f"**Generated SQL**:\n```sql\n{gen_sql}\n```\n\n"        
        failures_md += f"**Evaluation Details**:\n{fail['error_analysis']}\n\n"
        failures_md += "---\n\n"
        
    return summary_md + failures_md
