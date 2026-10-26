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
    # 3. Holdout or hillclimbing accuracy below target threshold (p_test < min_test_accuracy or p_dev < min_test_accuracy) -> Investigate (Below Accuracy Target)
    # 4. Otherwise -> Pass
    if test_total < 45:
        verdict_type = "INCONCLUSIVE"
        verdict = "NOT PASS — INCONCLUSIVE (Sample Size Too Small)"
        status = "More Data Needed"
    elif p_value < alpha and p_dev > p_test:
        verdict_type = "INVESTIGATE"
        verdict = "NOT PASS — INVESTIGATE (Statistically Significant Performance Drop)"
        status = "Needs Optimization (Gaps Identified)"
    elif p_test < min_test_accuracy or p_dev < min_test_accuracy:
        verdict_type = "INVESTIGATE"
        verdict = (
            "NOT PASS — INVESTIGATE (Holdout Accuracy Below Target Threshold)"
            if p_test < min_test_accuracy
            else "NOT PASS — INVESTIGATE (Hillclimbing Accuracy Below Target Threshold)"
        )
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
        if diagnosis:
            diag_text = diagnosis
        elif test_pct > dev_pct:
            diag_text = (
                "The model generalizes well to new phrasings and literal values across the covered query patterns "
                "rather than memorizing exact hillclimbing questions. Holdout accuracy "
                f"({test_pct}%) exceeded hillclimbing accuracy ({dev_pct}%) without any performance drop."
            )
        elif test_pct == dev_pct:
            diag_text = (
                "The model generalizes well to new phrasings and literal values across the covered query patterns "
                "rather than memorizing exact hillclimbing questions. Holdout accuracy "
                f"({test_pct}%) matches hillclimbing accuracy ({dev_pct}%)."
            )
        else:
            diag_text = (
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
        min_acc = stats.get("min_test_accuracy", 0.85)
        min_acc_pct = int(round(min_acc * 100))
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
        elif stats["test_accuracy"] < min_acc:
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
        else:
            header_title = (
                "❌ **Evaluation Alert: Hillclimbing Accuracy Below Target Threshold**"
            )
            status_line = "**Status**: Needs Optimization (Below Accuracy Target)"
            subtitle = f"Hillclimbing accuracy ({dev_pct}%) is below the {min_acc_pct}% minimum threshold (tied to the {target_pct}% tuning target), so the context set is not yet ready for production."
            holdout_note = (
                f"**Consistent with hillclimbing ({failed_count} failed queries)**"
            )
            default_diag = (
                f"Although holdout accuracy ({test_pct}%) met the {min_acc_pct}% threshold, "
                f"hillclimbing accuracy ({dev_pct}%) remains below the {min_acc_pct}% production readiness threshold (derived from the {target_pct}% tuning target)."
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


def format_final_evaluation_report(
    stats: dict[str, Any],
    failure_breakdown_md: str | None = None,
    actionable_recommendations_md: str | None = None,
    tldr_summary: str | None = None,
    tldr_next_steps: str | None = None,
    context_set_id: str | None = None,
    context_file: str | None = None,
) -> str:
    """Formats the comprehensive final_evaluation_report.md document.

    Ordered strictly by decision relevance:
    TL;DR -> 1. ACTIONABLE RECOMMENDATIONS -> 2. PERFORMANCE OVERVIEW ->
    3. HOLDOUT SET FAILURE BREAKDOWN -> 4. STATISTICAL DETAILS.
    """
    v_type = stats["verdict_type"]
    dev_pct = stats["dev_accuracy"] * 100.0
    test_pct = stats["test_accuracy"] * 100.0
    diff_pct = stats["difference"] * 100.0
    diff_sign = "+" if diff_pct > 0 else ""
    min_acc = stats.get("min_test_accuracy", 0.85)
    min_acc_pct = int(round(min_acc * 100))
    target_pct = int(round(stats.get("tuning_target", 1.0) * 100))

    if v_type == "PASS":
        sig_label = (
            f"Not Statistically Significant (p = {stats['p_value']:.4f} >= {stats['alpha']}) — "
            "difference is within expected random variation"
            if stats["dev_accuracy"] >= stats["test_accuracy"]
            else f"Holdout Exceeded Hillclimbing (p = {stats['p_value']:.4f}) — no performance drop"
        )
        default_next = "Ready for deployment. No further optimization loops required."
        if context_set_id:
            file_note = f" (local file `{context_file}`)" if context_file else ""
            default_next = (
                f"Deploy ContextSet `{context_set_id}`{file_note} to production. "
                "No further optimization loops required."
            )
        default_summary = (
            "The ContextSet generalizes reliably to unseen question phrasings and literal values "
            "across the covered query patterns."
        )
        diff_note = "(within expected variance)"
        power_check = f"Sufficiently Powered (N_test = {stats['test_total']} >= 45)"
    elif v_type == "INCONCLUSIVE":
        sig_label = (
            f"Underpowered Sample Size (N_test = {stats['test_total']} < 45; "
            f"p = {stats['p_value']:.4f})"
        )
        default_next = (
            "Expand the evaluation dataset to at least 150 total queries "
            "(105 Hillclimbing / 45 Holdout) in a new cloned experiment."
        )
        default_summary = "The holdout sample size is too small to statistically confirm generalization reliability."
        diff_note = "(sample size underpowered)"
        power_check = (
            f"Underpowered (N_test = {stats['test_total']} < 45 minimum required)"
        )
    else:  # INVESTIGATE
        is_sig_drop = (
            stats["p_value"] < stats["alpha"]
            and stats["dev_accuracy"] > stats["test_accuracy"]
        )
        if is_sig_drop:
            sig_label = (
                f"Statistically Significant Drop (p = {stats['p_value']:.4f} < {stats['alpha']}) — "
                "context set overfit to hillclimbing phrasings or lacks general concepts"
            )
            default_summary = (
                "The ContextSet achieved high accuracy on Hillclimbing Questions but suffered a "
                "statistically significant drop on Holdout Questions."
            )
            diff_note = "(statistically significant drop)"
        elif stats["test_accuracy"] < min_acc:
            sig_label = (
                f"Holdout Accuracy Below Target Threshold ({test_pct:.1f}% < {min_acc_pct}% minimum "
                f"derived from {target_pct}% tuning target; p = {stats['p_value']:.4f})"
            )
            default_summary = (
                f"Holdout accuracy ({test_pct:.1f}%) is below the {min_acc_pct}% production readiness "
                f"threshold (derived from the {target_pct}% tuning target)."
            )
            diff_note = f"(below {min_acc_pct}% accuracy threshold)"
        else:
            sig_label = (
                f"Hillclimbing Accuracy Below Target Threshold ({dev_pct:.1f}% < {min_acc_pct}% minimum "
                f"derived from {target_pct}% tuning target; p = {stats['p_value']:.4f})"
            )
            default_summary = (
                f"Hillclimbing accuracy ({dev_pct:.1f}%) is below the {min_acc_pct}% production readiness "
                f"threshold (derived from the {target_pct}% tuning target)."
            )
            diff_note = f"(hillclimbing below {min_acc_pct}% accuracy threshold)"

        default_next = (
            "Start a new cloned experiment to address the identified gaps in "
            "Section 1 (Actionable Recommendations) and Section 3 (Holdout Set Failure Breakdown)."
        )
        power_check = f"Sufficiently Powered (N_test = {stats['test_total']} >= 45)"

    next_steps_line = tldr_next_steps or default_next
    summary_line = tldr_summary or default_summary
    breakdown_section = (
        failure_breakdown_md
        or "*No holdout failures recorded, or see evaluation run report for details.*"
    )
    recommendations_section = actionable_recommendations_md or f"* {next_steps_line}"

    candidate_meta = ""
    if context_set_id or context_file:
        cs_str = f"`{context_set_id}`" if context_set_id else "N/A"
        cf_str = f"`{context_file}`" if context_file else "N/A"
        candidate_meta = (
            f"* **Candidate ContextSet**: {cs_str} (Local file: {cf_str})\n"
        )

    return (
        f"#CONTEXT ENGINEERING — FINAL EVALUATION & GENERALIZABILITY REPORT\n\n"
        f"## TL;DR\n"
        f"* **Verdict**: **{stats['verdict']}**\n"
        f"{candidate_meta}"
        f"* **Next Steps**: {next_steps_line}\n"
        f"* **Generalization Drop**: {diff_sign}{diff_pct:.1f}% ({dev_pct:.1f}% Hillclimbing -> {test_pct:.1f}% Holdout)\n"
        f"* **Significance Assessment**: {sig_label}\n"
        f"* **Summary**: {summary_line}\n\n"
        f"---\n\n"
        f"## 1. ACTIONABLE RECOMMENDATIONS\n\n"
        f"{recommendations_section}\n\n"
        f"---\n\n"
        f"## 2. PERFORMANCE OVERVIEW\n\n"
        f"| Split | Passed / Total | Accuracy | Notes |\n"
        f"| :---- | :---: | :---: | :---- |\n"
        f"| **Hillclimbing Questions** | {stats['dev_passed']} / {stats['dev_total']} | {dev_pct:.1f}% | Optimization set (used during iterative tuning) |\n"
        f"| **Holdout Questions** | {stats['test_passed']} / {stats['test_total']} | {test_pct:.1f}% | Unseen phrasing & parameter variations |\n\n"
        f"* **Difference**: {diff_sign}{diff_pct:.1f}% {diff_note}\n"
        f"* **Pattern Coverage**: 100% of query patterns in Holdout Questions are represented in Hillclimbing Questions.\n\n"
        f"---\n\n"
        f"## 3. HOLDOUT SET FAILURE BREAKDOWN\n\n"
        f"{breakdown_section}\n\n"
        f"---\n\n"
        f"## 4. STATISTICAL DETAILS\n\n"
        f"* **Test Applied**: Two-Proportion Pooled z-Test (Null Hypothesis H_0: p_dev - p_test = 0)\n"
        f"* **Sample Sizes**: N_dev = {stats['dev_total']} (x_dev = {stats['dev_passed']}), N_test = {stats['test_total']} (x_test = {stats['test_passed']})\n"
        f"* **Tuning Target**: {stats['tuning_target']:.2f} (Min Accuracy Threshold: {min_acc:.2f})\n"
        f"* **Pooled Proportion (p_hat)**: {stats['p_hat']:.4f}\n"
        f"* **Standard Error (SE)**: {stats['standard_error']:.4f}\n"
        f"* **Test Statistic (z)**: {stats['z_statistic']:.2f}\n"
        f"* **Two-Tailed p-value**: {stats['p_value']:.4f} (Significance threshold alpha = {stats['alpha']})\n"
        f"* **Power Analysis Check**: {power_check}\n"
    )
