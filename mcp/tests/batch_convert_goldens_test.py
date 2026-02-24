import pytest
import json
import os
from unittest.mock import patch, AsyncMock
from batch_convert_goldens import batch_convert

@pytest.mark.asyncio
async def test_batch_convert_success(tmp_path):
    # Setup temporary input and output files
    input_file = tmp_path / "test_goldens.json"
    output_file = tmp_path / "test_output.json"
    
    golden_data = [
        {"question": "How many tables?", "SQL": "SELECT count(*) FROM tables"}
    ]
    input_file.write_text(json.dumps(golden_data))
    
    mock_result = {
        "templates": [
            {
                "nl_query": "How many tables?",
                "sql": "SELECT count(*) FROM tables",
                "intent": "How many tables?",
                "manifest": "How many tables?",
                "parameterized": {
                    "parameterized_sql": "SELECT count(*) FROM tables",
                    "parameterized_intent": "How many tables?"
                }
            }
        ]
    }
    
    with patch("batch_convert_goldens.generate_templates", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = json.dumps(mock_result)
        
        await batch_convert(str(input_file), str(output_file), "postgresql")
        
        # Verify generate_templates was called with the right data (sql lowercase)
        expected_input = [{"question": "How many tables?", "sql": "SELECT count(*) FROM tables"}]
        mock_gen.assert_called_once_with(json.dumps(expected_input), sql_dialect="postgresql")
        
        # Verify output file content
        assert output_file.exists()
        with open(output_file, "r") as f:
            saved_data = json.load(f)
            assert saved_data == mock_result

@pytest.mark.asyncio
async def test_batch_convert_missing_fields(tmp_path, capsys):
    input_file = tmp_path / "invalid_goldens.json"
    output_file = tmp_path / "output.json"
    
    # Missing SQL field
    golden_data = [{"question": "Who are you?"}]
    input_file.write_text(json.dumps(golden_data))
    
    await batch_convert(str(input_file), str(output_file), "postgresql")
    
    captured = capsys.readouterr()
    assert "Warning: Skipping item with missing question or SQL" in captured.out
    assert "Error: No valid question/SQL pairs found in input file." in captured.out
    assert not output_file.exists()
