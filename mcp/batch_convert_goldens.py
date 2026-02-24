import asyncio
import json
import argparse
import os
import sys

# Ensure we can import from the current directory (mcp folder)
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from template.template_generator import generate_templates
from common.parameterizer import SQLDialect

async def batch_convert(input_file: str, output_file: str, dialect: str):
    """
    Reads a golden JSON file, converts it to the format expected by generate_templates,
    and saves the resulting ContextSet.
    """
    if not os.path.exists(input_file):
        print(f"Error: Input file '{input_file}' not found.")
        return

    try:
        with open(input_file, 'r') as f:
            goldens = json.load(f)
    except Exception as e:
        print(f"Error reading input file: {e}")
        return

    if not isinstance(goldens, list):
        print("Error: Golden file must contain a JSON array.")
        return

    # Map golden fields to template input fields
    # Golden: {"question": "...", "SQL": "..."}
    # Template Input: {"question": "...", "sql": "...", "intent": "..."}
    template_inputs = []
    for item in goldens:
        question = item.get("question")
        sql = item.get("SQL") or item.get("sql") # Handle both cases
        if not question or not sql:
            print(f"Warning: Skipping item with missing question or SQL: {item}")
            continue
        
        template_inputs.append({
            "question": question,
            "sql": sql
        })

    if not template_inputs:
        print("Error: No valid question/SQL pairs found in input file.")
        return

    print(f"Converting {len(template_inputs)} items...")
    
    # Call the existing conversion logic
    result_json = await generate_templates(json.dumps(template_inputs), sql_dialect=dialect)
    
    try:
        result_data = json.loads(result_json)
        if "error" in result_data:
            print(f"Error during conversion: {result_data['error']}")
            return
            
        with open(output_file, 'w') as f:
            json.dump(result_data, f, indent=2)
        print(f"Successfully saved ContextSet to {output_file}")
    except Exception as e:
        print(f"Error saving output file: {e}")

def main():
    parser = argparse.ArgumentParser(description="Batch convert golden data to ContextSet JSON context.")
    parser.add_stdio = False # argparse doesn't have this, just adding a note
    parser.add_argument("--input", "-i", required=True, help="Path to the golden JSON file.")
    parser.add_argument("--output", "-o", default="context_set_output.json", help="Path to save the generated ContextSet.")
    parser.add_argument("--dialect", "-d", default="postgresql", choices=[d.value for d in SQLDialect], help="SQL dialect for parameterization.")

    args = parser.parse_args()

    asyncio.run(batch_convert(args.input, args.output, args.dialect))

if __name__ == "__main__":
    main()
