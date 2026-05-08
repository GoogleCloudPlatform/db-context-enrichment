import os
import json

async def generate_dataset(
    dataset_entries_json: str,
    output_file_path: str,
) -> str:
    """
    Validates a list of evaluation dataset entries and saves them to a JSON file.

    Args:
        dataset_entries_json: A JSON string representing a list of dataset items.
                             Each item should have "id", "database", "nlq", and "golden_sql" keys.
                             Example: '[{"id": "eval_001", "database": "my_db", "nlq": "Count users", "golden_sql": "SELECT COUNT(*) FROM users"}]'
        output_file_path: The absolute path where the dataset JSON file should be saved.

    Returns:
        The absolute file path where the dataset was saved.
    """
    try:
        data = json.loads(dataset_entries_json)
        if not isinstance(data, list):
            raise ValueError("Dataset entries must be a list of objects.")
        
        # Simple validation of keys
        for i, entry in enumerate(data):
            if not isinstance(entry, dict):
                raise ValueError(f"Entry at index {i} is not an object.")
            missing_keys = {"id", "database", "nlq", "golden_sql"} - set(entry.keys())
            if missing_keys:
                raise ValueError(f"Entry at index {i} is missing required keys: {missing_keys}")

        # Ensure directory exists
        os.makedirs(os.path.dirname(os.path.abspath(output_file_path)), exist_ok=True)
        
        with open(output_file_path, "w") as f:
            json.dump(data, f, indent=2)
            
        return f"Successfully saved dataset to {output_file_path}"
    except (json.JSONDecodeError, ValueError, OSError) as e:
        return f"Error saving dataset: {str(e)}"
