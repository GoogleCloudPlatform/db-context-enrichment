import pytest
import textwrap
from unittest.mock import patch, mock_open
import os

from evaluate.result_reader import read_eval_results

def test_read_eval_results_success():
    summary_data = "metric_name,metric_score,correct_results_count,total_results_count,run_time\nm1,90,9,10,1s\n"
    scores_data = "id,score,comparison_logs\n1,90,Error analysis for 1\n2,100,\n"
    evals_data = "id,nl_prompt,golden_sql,generated_sql,sql_generator_error,generated_error,other\n1,Prompt 1,SELECT 2,SELECT 1,,,Other info 1\n2,Prompt 2,SELECT 4,SELECT 4,,,\n"

    m_summary = mock_open(read_data=summary_data)
    m_scores = mock_open(read_data=scores_data)
    m_evals = mock_open(read_data=evals_data)

    with patch("builtins.open", side_effect=[m_summary.return_value, m_scores.return_value, m_evals.return_value]):
        result = read_eval_results("/fake/path")

    expected = textwrap.dedent("""\
        # Evaluation Summary

        - **Metric**: m1
          - **Correct / Total**: 9/10
          - **Run Time**: 1s

        ## All Failures
        1

        **Showing failures**: 1 to 1 of 1

        # Failure Cases

        ## Case ID: 1 (Score: 90.0)

        **Prompt**:
        Prompt 1

        **Golden SQL**:
        ```sql
        SELECT 2
        ```

        **Generated SQL**:
        ```sql
        SELECT 1
        ```

        **SQL Generator Error** (Errors during SQL generation):
        ```
        N/A
        ```

        **Execution Error** (Errors when executing the generated SQL):
        ```
        N/A
        ```

        **Additional Output**:
        ```
        Other info 1
        ```

        **Evaluation Details**:
        Error analysis for 1
        
        ---

        """)
    assert result == expected

def test_read_eval_results_no_failures():
    summary_data = "metric_name,metric_score,correct_results_count,total_results_count,run_time\nm1,100,10,10,1s\n"
    scores_data = "id,score,comparison_logs\n1,100,\n"

    m_summary = mock_open(read_data=summary_data)
    m_scores = mock_open(read_data=scores_data)

    with patch("builtins.open", side_effect=[m_summary.return_value, m_scores.return_value]):
        result = read_eval_results("/fake/path")

    expected = textwrap.dedent("""\
        # Evaluation Summary

        - **Metric**: m1
          - **Correct / Total**: 10/10
          - **Run Time**: 1s

        No failure cases found (all passed).""")
    assert result == expected

def test_read_eval_results_generator_error():
    summary_data = "metric_name,metric_score,correct_results_count,total_results_count,run_time\nm1,0,0,10,1s\n"
    scores_data = "id,score,comparison_logs\n1,0,\n"
    evals_data = "id,nl_prompt,golden_sql,generated_sql,sql_generator_error,generated_error,other\n1,Prompt 1,SELECT 2,,Generation failed,,Other info 1\n"

    m_summary = mock_open(read_data=summary_data)
    m_scores = mock_open(read_data=scores_data)
    m_evals = mock_open(read_data=evals_data)

    with patch("builtins.open", side_effect=[m_summary.return_value, m_scores.return_value, m_evals.return_value]):
        result = read_eval_results("/fake/path")

    expected = textwrap.dedent("""\
        # Evaluation Summary

        - **Metric**: m1
          - **Correct / Total**: 0/10
          - **Run Time**: 1s

        ## All Failures
        1

        **Showing failures**: 1 to 1 of 1

        # Failure Cases

        ## Case ID: 1 (Score: 0.0)

        **Prompt**:
        Prompt 1

        **Golden SQL**:
        ```sql
        SELECT 2
        ```

        **Generated SQL**:
        ```sql
        N/A
        ```

        **SQL Generator Error** (Errors during SQL generation):
        ```
        Generation failed
        ```

        **Execution Error** (Errors when executing the generated SQL):
        ```
        N/A
        ```

        **Additional Output**:
        ```
        Other info 1
        ```

        **Evaluation Details**:
        N/A
        
        ---

        """)
    assert result == expected

def test_read_eval_results_batching():
    summary_data = "metric_name,metric_score,correct_results_count,total_results_count,run_time\nm1,50,5,10,1s\n"
    # Create 12 failures to test batching (limit is 10)
    scores_data = "id,score,comparison_logs\n"
    for i in range(1, 13):
        scores_data += f"{i},50,Error {i}\n"
        
    evals_data = "id,nl_prompt,golden_sql,generated_sql,sql_generator_error,generated_error,other\n"
    for i in range(1, 13):
        evals_data += f"{i},Prompt {i},SELECT {i},SELECT {i},,,\n"

    m_summary = mock_open(read_data=summary_data)
    m_scores = mock_open(read_data=scores_data)
    m_evals = mock_open(read_data=evals_data)

    # Test first batch (offset 0)
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
    
    with patch("builtins.open", side_effect=[m_summary2.return_value, m_scores2.return_value, m_evals2.return_value]):
        result2 = read_eval_results("/fake/path", offset=10)

    assert "**Showing failures**: 11 to 12 of 12" in result2
    assert "## Case ID: 11 (" in result2
    assert "## Case ID: 12 (" in result2
    assert "## Case ID: 10 (" not in result2

def test_read_eval_results_file_not_found():
    with pytest.raises(FileNotFoundError):
        read_eval_results("/fake/path")
