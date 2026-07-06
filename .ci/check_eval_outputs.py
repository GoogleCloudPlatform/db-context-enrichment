import json
import os
import sys

def check_outputs(suite_path, dataset_file):
    if not os.path.exists(dataset_file):
        print(f"Dataset file not found: {dataset_file}")
        sys.exit(1)

    with open(dataset_file, "r") as f:
        data = json.load(f)

    scenarios = data.get("scenarios", [])
    failed = False

    print(f"Starting mandatory output validation for {len(scenarios)} scenarios...")
    print(f"Suite path: {suite_path}")

    for scenario in scenarios:
        scenario_id = scenario.get("id")
        work_dir = scenario.get("work_dir")
        # Read mandatory files from the scenario item itself
        mandatory_files = scenario.get("mandatory_output_files", [])

        if not work_dir:
            print(f"Skipping scenario {scenario_id} (no work_dir)")
            continue

        full_work_dir = os.path.join(suite_path, work_dir)
        print(f"\nChecking scenario: {scenario_id}")
        print(f"Directory: {full_work_dir}")

        if not os.path.isdir(full_work_dir):
            print(f"  [FAILURE] Work directory does not exist: {full_work_dir}")
            failed = True
            continue

        if not mandatory_files:
            print(f"  [WARNING] No mandatory_output_files defined for this scenario.")
            continue

        for f in mandatory_files:
            file_path = os.path.join(full_work_dir, f)
            if not os.path.isfile(file_path):
                print(f"  [FAILURE] Missing mandatory file: {f}")
                failed = True
            else:
                # Check if file is not empty
                if os.path.getsize(file_path) == 0:
                    print(f"  [FAILURE] Mandatory file is empty: {f}")
                    failed = True
                else:
                    print(f"  [SUCCESS] Found {f} ({os.path.getsize(file_path)} bytes)")

    if failed:
        print("\n[ERROR] Output validation failed! One or more mandatory files are missing or empty.")
        sys.exit(1)
    else:
        print("\n[INFO] All mandatory outputs verified successfully.")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 check_eval_outputs.py <suite_path> <dataset_file>")
        sys.exit(1)
    
    suite_path_arg = sys.argv[1]
    dataset_file_arg = sys.argv[2]
    
    check_outputs(suite_path_arg, dataset_file_arg)
