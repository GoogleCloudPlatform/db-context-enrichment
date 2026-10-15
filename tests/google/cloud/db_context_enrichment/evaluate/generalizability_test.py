import pytest

from google.cloud.db_context_enrichment.evaluate.generalizability import (
    calculate_z_test,
    format_final_evaluation_report,
    format_on_screen_card,
)


def test_calculate_z_test_invalid_inputs():
    with pytest.raises(ValueError, match="must be positive integers"):
        calculate_z_test(0, 0, 10, 45)
    with pytest.raises(ValueError, match="must be positive integers"):
        calculate_z_test(10, 105, 0, 0)
    with pytest.raises(
        ValueError, match="Passed counts must be between 0 and total counts"
    ):
        calculate_z_test(-1, 105, 40, 45)
    with pytest.raises(
        ValueError, match="Passed counts must be between 0 and total counts"
    ):
        calculate_z_test(106, 105, 40, 45)
    with pytest.raises(
        ValueError, match="Passed counts must be between 0 and total counts"
    ):
        calculate_z_test(90, 105, 46, 45)


def test_calculate_z_test_inconclusive_underpowered():
    stats = calculate_z_test(dev_passed=36, dev_total=40, test_passed=8, test_total=10)
    assert stats["verdict_type"] == "INCONCLUSIVE"
    assert "INCONCLUSIVE" in stats["verdict"]
    assert stats["status"] == "More Data Needed"
    assert stats["dev_accuracy"] == pytest.approx(0.9)
    assert stats["test_accuracy"] == pytest.approx(0.8)


def test_calculate_z_test_investigate_significant_drop():
    stats = calculate_z_test(
        dev_passed=97, dev_total=105, test_passed=32, test_total=45
    )
    assert stats["verdict_type"] == "INVESTIGATE"
    assert "INVESTIGATE" in stats["verdict"]
    assert stats["status"] == "Needs Optimization"
    assert stats["p_value"] < 0.05
    assert stats["generalization_drop"] > 0


def test_calculate_z_test_pass_within_variance():
    stats = calculate_z_test(
        dev_passed=95, dev_total=105, test_passed=39, test_total=45
    )
    assert stats["verdict_type"] == "PASS"
    assert "PASS" in stats["verdict"]
    assert stats["status"] == "Ready for Production"
    assert stats["p_value"] >= 0.05


def test_calculate_z_test_pass_when_holdout_exceeds_dev():
    # Even if p < 0.05, test accuracy > dev accuracy is a PASS
    stats = calculate_z_test(
        dev_passed=60, dev_total=105, test_passed=44, test_total=45
    )
    assert stats["verdict_type"] == "PASS"
    assert stats["p_value"] < 0.05
    assert stats["test_accuracy"] > stats["dev_accuracy"]


def test_calculate_z_test_boundary_zero_or_hundred_percent():
    stats_all_pass = calculate_z_test(
        dev_passed=105, dev_total=105, test_passed=45, test_total=45
    )
    assert stats_all_pass["p_hat"] == 1.0
    assert stats_all_pass["standard_error"] == 0.0
    assert stats_all_pass["z_statistic"] == 0.0
    assert stats_all_pass["p_value"] == 1.0
    assert stats_all_pass["verdict_type"] == "PASS"

    stats_all_fail = calculate_z_test(
        dev_passed=0, dev_total=105, test_passed=0, test_total=45
    )
    assert stats_all_fail["p_hat"] == 0.0
    assert stats_all_fail["standard_error"] == 0.0
    assert stats_all_fail["z_statistic"] == 0.0
    assert stats_all_fail["p_value"] == 1.0
    assert stats_all_fail["verdict_type"] == "PASS"


def test_format_on_screen_card_pass_defaults_and_overrides():
    # dev_passed - test_passed <= 2 branch (e.g., 45 vs 44)
    stats_close = calculate_z_test(45, 50, 44, 50)
    card_close = format_on_screen_card(
        stats_close,
        context_set_id="projects/p/locations/l/contextSets/cs1",
        context_file="v2/context_set_v2.json",
    )
    assert "Evaluation Complete: Context Set Generalizes Reliably" in card_close
    assert "Consistent with hillclimbing (1-question variance)" in card_close
    assert "projects/p/locations/l/contextSets/cs1" in card_close
    assert "v2/context_set_v2.json" in card_close

    # dev_passed - test_passed > 2 branch + custom next_step without context_set_id
    stats_normal = calculate_z_test(95, 105, 39, 45)
    card_custom = format_on_screen_card(
        stats_normal,
        diagnosis="Custom diagnosis text.",
        next_step="Deploy immediately.",
        context_set_id="projects/p/locations/l/contextSets/cs1",
    )
    assert (
        "**Holdout Questions** | **87%** | **39 / 45** | **Consistent with hillclimbing**"
        in card_custom
    )
    assert "Custom diagnosis text." in card_custom
    assert (
        "Deploy immediately. (Full Context Set ID: `projects/p/locations/l/contextSets/cs1`)"
        in card_custom
    )

    # Custom next_step already containing context_set_id
    card_included = format_on_screen_card(
        stats_normal,
        next_step="Live at projects/p/locations/l/contextSets/cs1 now.",
        context_set_id="projects/p/locations/l/contextSets/cs1",
    )
    assert card_included.count("projects/p/locations/l/contextSets/cs1") == 1


def test_format_on_screen_card_inconclusive():
    stats = calculate_z_test(36, 40, 8, 10)
    card = format_on_screen_card(stats)
    assert "Evaluation Inconclusive: Sample Size Too Small" in card
    assert "**Status**: More Data Needed" in card
    assert "2 failures; sample size underpowered" in card
    assert (
        "With only 10 holdout questions, each question changes accuracy by 10%." in card
    )
    assert "Expand Evaluation Dataset" in card


def test_format_on_screen_card_investigate():
    stats = calculate_z_test(97, 105, 32, 45)
    card = format_on_screen_card(
        stats,
        diagnosis="Missing business rule facets.",
        recommended_action="Add facets and clone experiment.",
    )
    assert "Evaluation Alert: Performance Drop on Holdout Questions" in card
    assert "**Status**: Needs Optimization" in card
    assert "Statistically significant drop (-21%," in card
    assert "Missing business rule facets." in card
    assert "Add facets and clone experiment." in card


def test_format_final_evaluation_report_all_verdicts():
    for dev_p, dev_t, test_p, test_t, expected_verdict in [
        (95, 105, 39, 45, "PASS — Ready for Production"),
        (36, 40, 8, 10, "NOT PASS — INCONCLUSIVE"),
        (97, 105, 32, 45, "NOT PASS — INVESTIGATE"),
    ]:
        stats = calculate_z_test(dev_p, dev_t, test_p, test_t)
        report = format_final_evaluation_report(
            stats=stats,
            failure_breakdown_md="- Query 1 failed due to missing join",
            actionable_recommendations_md="- Add facet for active status",
            tldr_summary="Summary of run.",
            tldr_next_steps="Proceed with recommended action.",
        )
        assert "FINAL EVALUATION & GENERALIZABILITY REPORT" in report
        assert expected_verdict in report
        assert "1. ACTIONABLE RECOMMENDATIONS" in report
        assert "- Add facet for active status" in report
        assert "2. PERFORMANCE OVERVIEW" in report
        assert "3. HOLDOUT SET FAILURE BREAKDOWN" in report
        assert "- Query 1 failed due to missing join" in report
        assert "4. STATISTICAL DETAILS" in report
        assert "Two-proportion pooled z-test" in report
