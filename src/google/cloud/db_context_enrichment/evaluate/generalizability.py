import math
from typing import Any


def calculate_z_test(
    dev_passed: int,
    dev_total: int,
    test_passed: int,
    test_total: int,
    alpha: float = 0.05,
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
    if dev_passed < 0 or test_passed < 0 or dev_passed > dev_total or test_passed > test_total:
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
        status = "Needs Optimization"
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
        notes_test = (
            "Consistent with hillclimbing (1-question variance)"
            if (dev_passed - test_passed <= 2)
            else "Consistent with hillclimbing"
        )
        diag_text = (
            diagnosis
            or "The model is generalizing well and not simply memorizing hillclimbing phrases. The minor difference between hillclimbing and holdout is well within normal statistical expectations."
        )
        next_text = (
            next_step
            or "Export `improved_context_v3.json` to production. No further optimization iterations required."
        )

        return (
            f"🎯 **Evaluation Complete: Context Set Generalizes Reliably**\n\n"
            f"**Status**: Ready for Production\n\n"
            f"Your context set successfully handles new ways of asking questions without performance drops.\n\n"
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
            or "**Expand Evaluation Dataset**. Add questions to reach at least **150 total pairs** (>= 105 Hillclimbing / >= 45 Holdout) and restart context engineering."
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
        p_val_str = f"{stats['p_value']:.3f}"
        diag_text = (
            diagnosis
            or "Evaluation revealed statistically significant drops on holdout question phrasings due to missing domain contexts or phrasing gaps."
        )
        action_text = (
            recommended_action
            or "Review the failure breakdown below, generate missing facets/values, and re-run optimization with a fresh holdout set."
        )

        return (
            f"❌ **Evaluation Alert: Performance Drop on Holdout Questions**\n\n"
            f"**Status**: Needs Optimization\n\n"
            f"The model passed hillclimbing questions but dropped on holdout phrasings.\n\n"
            f"| Split | Accuracy | Correct Queries | Notes |\n"
            f"| :---- | :---: | :---: | :---- |\n"
            f"| **Hillclimbing Questions** | **{dev_pct}%** | **{dev_passed} / {dev_total}** | **Baseline optimization accuracy** |\n"
            f"| **Holdout Questions** | **{test_pct}%** | **{test_passed} / {test_total}** | **Statistically significant drop (-{diff_pct}%, p = {p_val_str})** |\n\n"
            f"**Summary & Recommendation**:\n"
            f"* **Diagnosis**: {diag_text}\n"
            f"* **Recommended Action**: {action_text}"
        )


def format_final_evaluation_report(
    stats: dict[str, Any],
    failure_breakdown_md: str,
    actionable_recommendations_md: str,
    tldr_summary: str,
    tldr_next_steps: str,
) -> str:
    """Formats the complete final_evaluation_report.md artifact for disk persistence."""
    drop_pct = f"{stats['generalization_drop'] * 100:.1f}%"
    dev_pct = f"{stats['dev_accuracy'] * 100:.1f}%"
    test_pct = f"{stats['test_accuracy'] * 100:.1f}%"
    diff_pct = f"{stats['difference'] * 100:.1f}%"
    diff_queries = stats["test_passed"] - stats["dev_passed"]

    if stats["verdict_type"] == "PASS":
        sig_text = f"Not Statistically Significant (p = {stats['p_value']:.2f})"
        decision_text = (
            f"Retain null hypothesis (H0: p_dev - p_test = 0).\n"
            f"Because p = {stats['p_value']:.4f} >= {stats['alpha']} with N_test = {stats['test_total']}, "
            f"the observed difference is not statistically significant."
        )
    elif stats["verdict_type"] == "INCONCLUSIVE":
        sig_text = f"Inconclusive (p = {stats['p_value']:.2f}, statistical power < 25%)"
        decision_text = (
            f"Inconclusive. Statistical power < 25% to detect a drop at alpha = {stats['alpha']}.\n"
            f"Minimum recommended holdout sample size is N_test >= 45."
        )
    else:
        sig_text = f"Statistically Significant Drop (p = {stats['p_value']:.4f} < {stats['alpha']})"
        decision_text = f"Reject H0 (p < {stats['alpha']}). Statistically significant performance drop."

    return (
        f"================================================================================\n"
        f"FINAL EVALUATION & GENERALIZABILITY REPORT\n"
        f"================================================================================\n"
        f"TL;DR\n"
        f"--------------------------------------------------------------------------------\n"
        f"Verdict: {stats['verdict']}\n"
        f"Next Steps: {tldr_next_steps}\n"
        f"Generalization Drop: {drop_pct} ({dev_pct} Hillclimbing -> {test_pct} Holdout)\n"
        f"Significance Assessment: {sig_text}\n"
        f"Summary: {tldr_summary}\n\n"
        f"--------------------------------------------------------------------------------\n"
        f"1. ACTIONABLE RECOMMENDATIONS\n"
        f"--------------------------------------------------------------------------------\n"
        f"{actionable_recommendations_md.strip()}\n\n"
        f"--------------------------------------------------------------------------------\n"
        f"2. PERFORMANCE OVERVIEW\n"
        f"--------------------------------------------------------------------------------\n"
        f"Hillclimbing Set:            {stats['dev_passed']:3d} / {stats['dev_total']:3d} passed ({dev_pct})\n"
        f"Holdout Set (New Phrasings): {stats['test_passed']:3d} / {stats['test_total']:3d} passed ({test_pct})\n"
        f"Difference:                  {diff_queries:+d} queries ({diff_pct})\n\n"
        f"--------------------------------------------------------------------------------\n"
        f"3. HOLDOUT SET FAILURE BREAKDOWN\n"
        f"--------------------------------------------------------------------------------\n"
        f"{failure_breakdown_md.strip()}\n\n"
        f"--------------------------------------------------------------------------------\n"
        f"4. STATISTICAL DETAILS\n"
        f"--------------------------------------------------------------------------------\n"
        f"- Test Method: Two-proportion pooled z-test\n"
        f"- Significance Level: alpha = {stats['alpha']}\n"
        f"- Sample Sizes: N_dev = {stats['dev_total']} (x_dev = {stats['dev_passed']}), N_test = {stats['test_total']} (x_test = {stats['test_passed']})\n"
        f"- Pooled Proportion: p_hat = {stats['p_hat']:.4f}\n"
        f"- Standard Error (SE): {stats['standard_error']:.4f}\n"
        f"- Test Statistic (z): {stats['z_statistic']:.2f}\n"
        f"- Two-Tailed p-value: p = {stats['p_value']:.4f}\n"
        f"- Statistical Decision: {decision_text}\n"
        f"================================================================================\n"
    )
