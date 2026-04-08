import pytest
from unittest.mock import patch, mock_open
import os

from evaluate.result_reader import read_eval_results

def test_read_eval_results_success():
    summary_data = "metric_name,metric_score,correct_results_count,total_results_count,run_time\nm1,90,9,10,1s\n"
    scores_data = "id,score,comparison_logs,generated_sql\n1,90,Error analysis for 1,SELECT 1\n"
    evals_data = "id,nl_prompt,golden_sql,generated_sql,sql_generator_error,other\n1,Prompt 1,SELECT 2,SELECT 1,,Other info 1\n"

    m_summary = mock_open(read_data=summary_data)
    m_scores = mock_open(read_data=scores_data)
    m_evals = mock_open(read_data=evals_data)

    # We need to mock os.path.exists to return True for all files
    with patch("os.path.exists", return_value=True):
        with patch("builtins.open", side_effect=[m_summary.return_value, m_scores.return_value, m_evals.return_value]):
            result = read_eval_results("/fake/path")

    assert "# Evaluation Summary" in result
    assert "- **Metric**: m1" in result
    assert "## Case ID: 1 (Score: 90.0)" in result
    assert "**Prompt**:\nPrompt 1" in result
    assert "**Golden SQL**:\n```sql\nSELECT 2\n```" in result
    assert "**Generated SQL**:\n```sql\nSELECT 1\n```" in result
    assert "**Evaluation Details**:\nError analysis for 1" in result
    assert "**Additional Output**:\n```\nOther info 1\n```" in result

def test_read_eval_results_no_failures():
    summary_data = "metric_name,metric_score,correct_results_count,total_results_count,run_time\nm1,100,10,10,1s\n"
    scores_data = "id,score,comparison_logs,generated_sql\n1,100,,SELECT 1\n"

    m_summary = mock_open(read_data=summary_data)
    m_scores = mock_open(read_data=scores_data)

    with patch("os.path.exists", return_value=True):
        with patch("builtins.open", side_effect=[m_summary.return_value, m_scores.return_value]):
            result = read_eval_results("/fake/path")

    assert "# Evaluation Summary" in result
    assert "No failure cases found" in result

def test_read_eval_results_generator_error():
    summary_data = "metric_name,metric_score,correct_results_count,total_results_count,run_time\nm1,0,0,10,1s\n"
    scores_data = "id,score,comparison_logs,generated_sql\n1,0,,\n"
    evals_data = "id,nl_prompt,golden_sql,generated_sql,sql_generator_error,other\n1,Prompt 1,SELECT 2,,Generation failed,Other info 1\n"

    m_summary = mock_open(read_data=summary_data)
    m_scores = mock_open(read_data=scores_data)
    m_evals = mock_open(read_data=evals_data)

    with patch("os.path.exists", return_value=True):
        with patch("builtins.open", side_effect=[m_summary.return_value, m_scores.return_value, m_evals.return_value]):
            result = read_eval_results("/fake/path")

    assert "# Evaluation Summary" in result
    assert "## Case ID: 1 (Score: 0.0)" in result
    assert "**SQL Generator Error**:\n```\nGeneration failed\n```" in result
    assert "**Evaluation Details**:" not in result # Should skip eval details

def test_read_eval_results_batching():
    summary_data = "metric_name,metric_score,correct_results_count,total_results_count,run_time\nm1,50,5,10,1s\n"
    # Create 12 failures to test batching (limit is 10)
    scores_data = "id,score,comparison_logs,generated_sql\n"
    for i in range(1, 13):
        scores_data += f"{i},50,Error {i},SELECT {i}\n"
        
    evals_data = "id,nl_prompt,golden_sql,generated_sql,sql_generator_error,other\n"
    for i in range(1, 13):
        evals_data += f"{i},Prompt {i},SELECT {i},SELECT {i},,\n"

    m_summary = mock_open(read_data=summary_data)
    m_scores = mock_open(read_data=scores_data)
    m_evals = mock_open(read_data=evals_data)

    # Test first batch (offset 0)
    with patch("os.path.exists", return_value=True):
        with patch("builtins.open", side_effect=[m_summary.return_value, m_scores.return_value, m_evals.return_value]):
            result = read_eval_results("/fake/path", offset=0)

    assert "**Showing failures**: 1 to 10 of 12" in result
    assert "## Case ID: 1 (" in result
    assert "## Case ID: 10 (" in result
    assert "## Case ID: 11 (" not in result

    # Test second batch (offset 10)
    m_summary2 = mock_open(read_data=summary_data)
    m_scores2 = mock_open(read_data=scores_data)
    m_evals2 = mock_open(read_data=evals_data)
    
    with patch("os.path.exists", return_value=True):
        with patch("builtins.open", side_effect=[m_summary2.return_value, m_scores2.return_value, m_evals2.return_value]):
            result2 = read_eval_results("/fake/path", offset=10)

    assert "**Showing failures**: 11 to 12 of 12" in result2
    assert "## Case ID: 11 (" in result2
    assert "## Case ID: 12 (" in result2
    assert "## Case ID: 10 (" not in result2

def test_read_eval_results_file_not_found():
    with patch("os.path.exists", return_value=False):
        result = read_eval_results("/fake/path")
    assert "Error: " in result and "not found" in result
