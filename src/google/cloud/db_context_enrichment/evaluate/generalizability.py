import math
from typing import Any

DEFAULT_ALPHA: float = 0.05
DEFAULT_TUNING_TARGET: float = 1.0
ACCURACY_MARGIN: float = 0.15


def calculate_z_test(
    dev_passed: int,
    dev_total: int,
    test_passed: int,
    test_total: int,
    alpha: float = DEFAULT_ALPHA,
    tuning_target: float = DEFAULT_TUNING_TARGET,
) -> dict[str, Any]:
    """Calculates a two-proportion pooled z-test and derives the verdict.

    Args:
        dev_passed: Number of passed queries in hillclimbing split (Hillclimbing Questions).
        dev_total: Total queries in hillclimbing split (N_dev).
        test_passed: Number of passed queries in holdout split (Holdout Questions).
        test_total: Total queries in holdout split (N_test).
        alpha: Significance level (default: 0.05).
        tuning_target: Target accuracy for hillclimbing (default: 1.0). The minimum
            holdout accuracy required for a PASS verdict is `tuning_target - 0.15`
            (e.g., 85% when tuning_target is 1.0).

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
    if not (0.0 < tuning_target <= 1.0):
        raise ValueError("tuning_target must be in (0.0, 1.0].")

    p_dev = dev_passed / dev_total
    p_test = test_passed / test_total
    drop = p_dev - p_test
    diff = p_test - p_dev
    min_test_accuracy = max(0.0, round(tuning_target - ACCURACY_MARGIN, 10))

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

    # Decision logic:
    # 1. Underpowered holdout size (N_test < 45) -> Inconclusive
    # 2. Statistically significant drop (p < alpha and p_dev > p_test) -> Investigate (Gaps Identified)
    # 3. Holdout accuracy below target threshold (p_test < tuning_target - 0.15) -> Investigate (Below Accuracy Target)
    # 4. Otherwise -> Pass
    if test_total < 45:
        verdict_type = "INCONCLUSIVE"
        verdict = "NOT PASS — INCONCLUSIVE (Sample Size Too Small)"
        status = "More Data Needed"
    elif p_value < alpha and p_dev > p_test:
        verdict_type = "INVESTIGATE"
        verdict = "NOT PASS — INVESTIGATE (Statistically Significant Performance Drop)"
        status = "Needs Optimization (Gaps Identified)"
    elif p_test < min_test_accuracy:
        verdict_type = "INVESTIGATE"
        verdict = "NOT PASS — INVESTIGATE (Holdout Accuracy Below Target Threshold)"
        status = "Needs Optimization (Below Accuracy Target)"
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
        "tuning_target": tuning_target,
        "min_test_accuracy": min_test_accuracy,
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
        is_sig_drop = (
            stats["p_value"] < stats["alpha"]
            and stats["dev_accuracy"] > stats["test_accuracy"]
        )
        min_acc_pct = int(round(stats.get("min_test_accuracy", 0.85) * 100))
        target_pct = int(round(stats.get("tuning_target", 1.0) * 100))

        if is_sig_drop:
            header_title = (
                "❌ **Evaluation Alert: Performance Drop on Holdout Questions**"
            )
            status_line = "**Status**: Needs Optimization (Gaps Identified)"
            subtitle = "The model passed hillclimbing questions but dropped on holdout phrasings due to missing context definitions or unseen phrasing patterns."
            holdout_note = (
                f"**Significant drop (-{diff_pct}% across {failed_count} queries)**"
            )
            default_diag = "Evaluation revealed a significant drop on holdout question phrasings due to missing context definitions or unseen phrasing patterns."
        else:
            header_title = (
                "❌ **Evaluation Alert: Holdout Accuracy Below Target Threshold**"
            )
            status_line = "**Status**: Needs Optimization (Below Accuracy Target)"
            subtitle = f"Holdout accuracy ({test_pct}%) is below the {min_acc_pct}% minimum threshold (tied to the {target_pct}% tuning target), so the context set is not yet ready for production."
            holdout_note = (
                f"**Below {min_acc_pct}% threshold ({failed_count} failed queries)**"
            )
            default_diag = (
                f"Although holdout accuracy ({test_pct}%) is statistically consistent with hillclimbing ({dev_pct}%), "
                f"overall accuracy remains below the {min_acc_pct}% production readiness threshold (derived from the {target_pct}% tuning target)."
            )

        diag_text = diagnosis or default_diag
        action_text = (
            recommended_action
            or "Inspect `final_evaluation_report.md` and use the copy-paste prompt under **Next step** below to start a cloned experiment."
        )

        return (
            f"{header_title}\n\n"
            f"{status_line}\n\n"
            f"{subtitle}\n\n"
            f"| Split | Accuracy | Correct Queries | Notes |\n"
            f"| :---- | :---: | :---: | :---- |\n"
            f"| **Hillclimbing Questions** | **{dev_pct}%** | **{dev_passed} / {dev_total}** | **Baseline optimization accuracy** |\n"
            f"| **Holdout Questions** | **{test_pct}%** | **{test_passed} / {test_total}** | {holdout_note} |\n\n"
            f"**Summary & Recommendation**:\n"
            f"* **Diagnosis**: {diag_text}\n"
            f"* **Recommended Action**: {action_text}"
        )
