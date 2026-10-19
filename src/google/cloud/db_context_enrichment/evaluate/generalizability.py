import math
from typing import Any

DEFAULT_ALPHA: float = 0.05


def calculate_z_test(
    dev_passed: int,
    dev_total: int,
    test_passed: int,
    test_total: int,
    alpha: float = DEFAULT_ALPHA,
) -> dict[str, Any]:
    """Calculates a two-proportion pooled z-test and derives the verdict.

    Args:
        dev_passed: Number of passed queries in hillclimbing split (Hillclimbing Questions).
        dev_total: Total queries in hillclimbing split (N_dev).
        test_passed: Number of passed queries in holdout split (Holdout Questions).
        test_total: Total queries in holdout split (N_test).
        alpha: Significance level (default: 0.05).

    Returns:
        Dict containing statistical metrics, p-value, and plain-language verdict.
    """
    if dev_total <= 0 or test_total <= 0:
        raise ValueError("dev_total and test_total must be positive integers.")
    if (
        dev_passed < 0
        or test_passed < 0
        or dev_passed > dev_total
        or test_passed > test_total
    ):
        raise ValueError("Passed counts must be between 0 and total counts.")

    p_dev = dev_passed / dev_total
    p_test = test_passed / test_total
    drop = p_dev - p_test
    diff = p_test - p_dev

    total_queries = dev_total + test_total
    total_passed = dev_passed + test_passed
    p_hat = total_passed / total_queries

    if 0.0 < p_hat < 1.0:
        se = math.sqrt(p_hat * (1.0 - p_hat) * (1.0 / dev_total + 1.0 / test_total))
        z = (p_dev - p_test) / se if se > 0 else 0.0
        p_value = math.erfc(abs(z) / math.sqrt(2.0))
    else:
        se = 0.0
        z = 0.0
        p_value = 1.0

    # Decision logic based on design doc & simulated outputs:
    # 1. Underpowered holdout size (N_test < 45) -> Inconclusive
    # 2. Statistically significant drop (p < alpha and p_dev > p_test) -> Investigate
    # 3. No statistically significant drop or holdout >= hillclimbing -> Pass
    if test_total < 45:
        verdict_type = "INCONCLUSIVE"
        verdict = "NOT PASS — INCONCLUSIVE (Sample Size Too Small)"
        status = "More Data Needed"
    elif p_value < alpha and p_dev > p_test:
        verdict_type = "INVESTIGATE"
        verdict = "NOT PASS — INVESTIGATE (Statistically Significant Performance Drop)"
        status = "Needs Optimization (Gaps Identified)"
    else:
        verdict_type = "PASS"
        verdict = "PASS — Ready for Production"
        status = "Ready for Production"

    return {
        "dev_passed": dev_passed,
        "dev_total": dev_total,
        "dev_accuracy": p_dev,
        "test_passed": test_passed,
        "test_total": test_total,
        "test_accuracy": p_test,
        "generalization_drop": drop,
        "difference": diff,
        "p_hat": p_hat,
        "standard_error": se,
        "z_statistic": z,
        "p_value": p_value,
        "alpha": alpha,
        "verdict_type": verdict_type,
        "verdict": verdict,
        "status": status,
    }


def format_on_screen_card(
    stats: dict[str, Any],
    diagnosis: str | None = None,
    recommended_action: str | None = None,
    next_step: str | None = None,
    context_set_id: str | None = None,
    context_file: str | None = None,
) -> str:
    """Formats the primary on-screen summary card for the chat UI.

    Designed for non-experts: clear, intuitive, and ordered by decision relevance.
    """
    v_type = stats["verdict_type"]
    dev_pct = int(round(stats["dev_accuracy"] * 100))
    test_pct = int(round(stats["test_accuracy"] * 100))
    dev_passed = stats["dev_passed"]
    dev_total = stats["dev_total"]
    test_passed = stats["test_passed"]
    test_total = stats["test_total"]

    if v_type == "PASS":
        notes_test = "Consistent with hillclimbing"
        diag_text = diagnosis or (
            "The model generalizes well to new phrasings and literal values across the covered query patterns "
            "rather than memorizing exact hillclimbing questions. The minor difference between hillclimbing "
            f"and holdout ({test_pct}% vs {dev_pct}%) is well within normal statistical expectations."
        )
        cs_id_display = context_set_id or "<Final Context Set resource>"
        if next_step:
            next_text = (
                next_step
                if (not context_set_id or context_set_id in next_step)
                else f"{next_step} (Full Context Set ID: `{context_set_id}`)"
            )
        else:
            file_note = f" (local file `{context_file}`)" if context_file else ""
            next_text = (
                f"The context set is live at `{cs_id_display}`{file_note}. "
                f"Point your application at it. No further optimization iterations required."
            )

        return (
            f"🎯 **Evaluation Complete: Context Set Generalizes Reliably**\n\n"
            f"**Status**: Ready for Production\n\n"
            f"Your context set successfully handles unseen phrasings and parameter variations across the covered query patterns without performance drops.\n\n"
            f"| Split | Accuracy | Correct Queries | Notes |\n"
            f"| :---- | :---: | :---: | :---- |\n"
            f"| **Hillclimbing Questions** | **{dev_pct}%** | **{dev_passed} / {dev_total}** | **Baseline optimization accuracy** |\n"
            f"| **Holdout Questions** | **{test_pct}%** | **{test_passed} / {test_total}** | **{notes_test}** |\n\n"
            f"**Summary**:\n"
            f"* **Robustness**: {diag_text}\n"
            f"* **Next Step**: {next_text}"
        )

    elif v_type == "INCONCLUSIVE":
        diag_text = diagnosis or (
            f"With only {test_total} holdout questions, each question changes accuracy by {int(round(100 / test_total))}%. "
            f"A statistical test cannot distinguish normal variation from genuine performance drops."
        )
        action_text = (
            recommended_action
            or "**Expand Evaluation Dataset** to at least **150 total questions** (>= 105 Hillclimbing / >= 45 Holdout) in a new cloned experiment — use the copy-paste prompt under **Next step** below."
        )

        return (
            f"⚠️ **Evaluation Inconclusive: Sample Size Too Small**\n\n"
            f"**Status**: More Data Needed\n\n"
            f"The holdout set is too small to determine whether the context set generalizes reliably.\n\n"
            f"| Split | Accuracy | Correct Queries | Notes |\n"
            f"| :---- | :---: | :---: | :---- |\n"
            f"| **Hillclimbing Questions** | **{dev_pct}%** | **{dev_passed} / {dev_total}** | **Baseline optimization accuracy** |\n"
            f"| **Holdout Questions** | **{test_pct}%** | **{test_passed} / {test_total}** | **{test_total - test_passed} failures; sample size underpowered** |\n\n"
            f"**Summary & Recommendation**:\n"
            f"* **Diagnosis**: {diag_text}\n"
            f"* **Recommended Action**: {action_text}"
        )

    else:  # INVESTIGATE
        diff_pct = abs(int(round(stats["difference"] * 100)))
        failed_count = test_total - test_passed
        diag_text = (
            diagnosis
            or "Evaluation revealed a significant drop on holdout question phrasings due to missing context definitions or unseen phrasing patterns."
        )
        action_text = (
            recommended_action
            or "Inspect `final_evaluation_report.md` and use the copy-paste prompt under **Next step** below to start a cloned experiment."
        )

        return (
            f"❌ **Evaluation Alert: Performance Drop on Holdout Questions**\n\n"
            f"**Status**: Needs Optimization (Gaps Identified)\n\n"
            f"The model passed hillclimbing questions but dropped on holdout phrasings due to missing context definitions or unseen phrasing patterns.\n\n"
            f"| Split | Accuracy | Correct Queries | Notes |\n"
            f"| :---- | :---: | :---: | :---- |\n"
            f"| **Hillclimbing Questions** | **{dev_pct}%** | **{dev_passed} / {dev_total}** | **Baseline optimization accuracy** |\n"
            f"| **Holdout Questions** | **{test_pct}%** | **{test_passed} / {test_total}** | **Significant drop (-{diff_pct}% across {failed_count} queries)** |\n\n"
            f"**Summary & Recommendation**:\n"
            f"* **Diagnosis**: {diag_text}\n"
            f"* **Recommended Action**: {action_text}"
        )
