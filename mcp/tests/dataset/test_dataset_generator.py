import pytest
import json
import os
from dataset.dataset_generator import generate_dataset

@pytest.mark.asyncio
async def test_generate_dataset_success(tmp_path):
    output_file = tmp_path / "dataset.json"
    entries = [
        {"id": "1", "database": "db1", "nlq": "Get users", "golden_sql": "SELECT * FROM users"}
    ]
    entries_json = json.dumps(entries)

    result = await generate_dataset(entries_json, str(output_file))
    
    assert "Successfully saved dataset" in result
    assert os.path.exists(output_file)
    
    with open(output_file, "r") as f:
        saved_data = json.load(f)
    assert saved_data == entries

@pytest.mark.asyncio
async def test_generate_dataset_invalid_json(tmp_path):
    output_file = tmp_path / "dataset.json"
    result = await generate_dataset("invalid json", str(output_file))
    assert "Error saving dataset" in result

@pytest.mark.asyncio
async def test_generate_dataset_not_a_list(tmp_path):
    output_file = tmp_path / "dataset.json"
    result = await generate_dataset('{"id": "1"}', str(output_file))
    assert "Error saving dataset" in result
    assert "Dataset entries must be a list of objects" in result

@pytest.mark.asyncio
async def test_generate_dataset_missing_keys(tmp_path):
    output_file = tmp_path / "dataset.json"
    entries = [{"id": "1", "database": "db1"}] # missing 'nlq', 'golden_sql'
    entries_json = json.dumps(entries)

    result = await generate_dataset(entries_json, str(output_file))
    assert "Error saving dataset" in result
    assert "missing required keys" in result
