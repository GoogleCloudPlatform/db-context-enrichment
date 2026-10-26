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
    with pytest.raises(ValueError, match="tuning_target must be in"):
        calculate_z_test(90, 105, 40, 45, tuning_target=0.0)
    with pytest.raises(ValueError, match="tuning_target must be in"):
        calculate_z_test(90, 105, 40, 45, tuning_target=1.1)


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
    assert stats["status"] == "Needs Optimization (Gaps Identified)"
    assert stats["p_value"] < 0.05
    assert stats["generalization_drop"] > 0


def test_calculate_z_test_investigate_below_target_threshold_and_custom_target():
    # Low plateau: 10/105 (9.5%) dev, 4/45 (8.9%) test -> p >= 0.05, but < 85% threshold
    stats_low = calculate_z_test(
        dev_passed=10, dev_total=105, test_passed=4, test_total=45
    )
    assert stats_low["p_value"] >= 0.05
    assert stats_low["verdict_type"] == "INVESTIGATE"
    assert "Below Target Threshold" in stats_low["verdict"]
    assert stats_low["status"] == "Needs Optimization (Below Accuracy Target)"

    # 80% dev (84/105), 71% test (32/45) -> p = 0.23 >= 0.05, fails default 85% threshold (tuning_target=1.0)
    stats_default = calculate_z_test(
        dev_passed=84, dev_total=105, test_passed=32, test_total=45
    )
    assert stats_default["p_value"] >= 0.05
    assert stats_default["verdict_type"] == "INVESTIGATE"
    assert stats_default["status"] == "Needs Optimization (Below Accuracy Target)"

    # With custom tuning_target=0.85 -> min_test_accuracy=0.70 -> 32/45 (71.1%) passes!
    stats_custom = calculate_z_test(
        dev_passed=84,
        dev_total=105,
        test_passed=32,
        test_total=45,
        tuning_target=0.85,
    )
    assert stats_custom["min_test_accuracy"] == pytest.approx(0.70)
    assert stats_custom["verdict_type"] == "PASS"
    assert stats_custom["status"] == "Ready for Production"


def test_calculate_z_test_pass_within_variance():
    stats = calculate_z_test(
        dev_passed=95, dev_total=105, test_passed=39, test_total=45
    )
    assert stats["verdict_type"] == "PASS"
    assert "PASS" in stats["verdict"]
    assert stats["status"] == "Ready for Production"
    assert stats["p_value"] >= 0.05


def test_calculate_z_test_pass_when_holdout_exceeds_dev():
    # Even if p < 0.05, test accuracy > dev accuracy and both >= 85% is a PASS
    stats = calculate_z_test(
        dev_passed=90, dev_total=105, test_passed=44, test_total=45
    )
    assert stats["verdict_type"] == "PASS"
    assert stats["p_value"] < 0.05
    assert stats["test_accuracy"] > stats["dev_accuracy"]

    # If dev accuracy is below min_test_accuracy (e.g., 60/105 = 57.1%), it is INVESTIGATE even if holdout is 44/45
    stats_low_dev = calculate_z_test(
        dev_passed=60, dev_total=105, test_passed=44, test_total=45
    )
    assert stats_low_dev["verdict_type"] == "INVESTIGATE"
    assert "Hillclimbing Accuracy Below Target Threshold" in stats_low_dev["verdict"]
    card_low_dev = format_on_screen_card(stats_low_dev)
    assert (
        "Evaluation Alert: Hillclimbing Accuracy Below Target Threshold" in card_low_dev
    )

    # Verify PASS card wording when holdout exceeds hillclimbing does not say "minor difference"
    card_exceeds = format_on_screen_card(stats)
    assert (
        "exceeded hillclimbing accuracy (86%) without any performance drop"
        in card_exceeds
    )
    assert "minor difference" not in card_exceeds


def test_format_final_evaluation_report_sections():
    stats = calculate_z_test(95, 105, 39, 45)
    report = format_final_evaluation_report(
        stats,
        failure_breakdown_md="* Query `eval_010` failed due to casing.",
        actionable_recommendations_md="* Add Value Search on `region`.",
        context_set_id="projects/p/locations/l/contextSets/cs1",
        context_file="v2/context_set_v2.json",
    )
    assert "## 1. ACTIONABLE RECOMMENDATIONS" in report
    assert "## 2. PERFORMANCE OVERVIEW" in report
    assert "## 3. HOLDOUT SET FAILURE BREAKDOWN" in report
    assert "## 4. STATISTICAL DETAILS" in report
    assert report.index("## 1. ACTIONABLE RECOMMENDATIONS") < report.index(
        "## 2. PERFORMANCE OVERVIEW"
    )
    assert "Add Value Search on `region`." in report
    assert "Query `eval_010` failed due to casing." in report
    assert "Min Accuracy Threshold: 0.85" in report


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
    assert stats_all_fail["verdict_type"] == "INVESTIGATE"
    assert stats_all_fail["status"] == "Needs Optimization (Below Accuracy Target)"


def test_format_on_screen_card_pass_defaults_and_overrides():
    stats_close = calculate_z_test(95, 105, 39, 45)
    card_close = format_on_screen_card(
        stats_close,
        context_set_id="projects/p/locations/l/contextSets/cs1",
        context_file="v2/context_set_v2.json",
    )
    assert "Evaluation Complete: Context Set Generalizes Reliably" in card_close
    assert (
        "**Holdout Questions** | **87%** | **39 / 45** | **Consistent with hillclimbing**"
        in card_close
    )
    assert "projects/p/locations/l/contextSets/cs1" in card_close
    assert "v2/context_set_v2.json" in card_close

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

    # Default next_step when context_file is None should not render `None`
    card_no_file = format_on_screen_card(
        stats_normal,
        context_set_id="projects/p/locations/l/contextSets/cs1",
    )
    assert "`None`" not in card_no_file
    assert (
        "The context set is live at `projects/p/locations/l/contextSets/cs1`."
        in card_no_file
    )


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
    assert "**Status**: Needs Optimization (Gaps Identified)" in card
    assert "Significant drop (-21% across 13 queries)" in card
    assert "p =" not in card
    assert "Missing business rule facets." in card
    assert "Add facets and clone experiment." in card

    stats_below = calculate_z_test(10, 105, 4, 45)
    card_below = format_on_screen_card(stats_below)
    assert "Evaluation Alert: Holdout Accuracy Below Target Threshold" in card_below
    assert "**Status**: Needs Optimization (Below Accuracy Target)" in card_below
    assert "Below 85% threshold (41 failed queries)" in card_below
