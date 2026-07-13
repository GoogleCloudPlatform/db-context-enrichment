"""End-to-end test of Context Store + Gemini Data Analytics (QueryData) APIs.

Steps:
  1. ensure_context_set_group    -> create fresh CSG (idempotent on 409)
  2. ensure_context_set          -> create CS inside it (idempotent on 409)
  3. upload_context_set          -> upload body from a local ContextSet JSON
  4. download_context_set        -> download + round-trip diff (normalized)
  5. QueryData API load-check    -> call query_data with the fresh cs_resource_name
  6. delete_context_set_group    -> cascade cleanup

Round-trip: server drops empty-list fields on download; the diff normalizes
by removing empty-collection keys before comparing.

QueryData load-check: proves the API accepted the freshly-uploaded CS
resource name and returned a translation. Correctness of the generated SQL
against the target DB is not asserted.

Run from the repo root:

  uv run python scripts/e2e_context_store.py \\
    --project astana-transformation \\
    --csg-id my-bughunt \\
    --cs-id autoctx --version v1 \\
    --seed ./tests/crema-test/test-1/bootstrap_context.json \\
    --querydata-db \\
        engine=alloydb,project=astana-transformation,region=us-east4,cluster=juexinw-test,instance=juexinw-test-primary,database=financial \\
    --querydata-prompt "How many clients?"

Prerequisites:
  - `uv` installed (script assumes repo venv on PATH via `uv run`).
  - Application Default Credentials with a valid access token.
  - ADC quota project set (Context Store's X-Goog-User-Project header).
  - Dataplex + Gemini Data Analytics APIs enabled on the target project.
  - IAM: Context Store role for CS operations; GDA role for QueryData.

Exit code 0 on all-pass, 1 on any failure. Cleanup (step 6) runs on
success only; on failure, the CSG is left in place for inspection.
"""

import argparse
import json
import pathlib
import sys

import google.cloud.geminidataanalytics_v1beta as gda
from google.api_core.client_options import ClientOptions

from google.cloud.db_context_enrichment.common import context_store_client
from google.cloud.db_context_enrichment.model import context


def step(n: int, label: str) -> None:
    print(f"\n[{n}] {label}")


def parse_querydata_db(spec: str) -> dict:
    """Parse `engine=X,project=P,region=R,...` into a datasource_references block."""
    parts = dict(kv.split("=", 1) for kv in spec.split(","))
    engine = parts.get("engine", "").lower()

    if engine == "alloydb":
        return {
            "alloydb": {
                "database_reference": {
                    "project_id": parts["project"],
                    "region": parts["region"],
                    "cluster_id": parts["cluster"],
                    "instance_id": parts["instance"],
                    "database_id": parts["database"],
                }
            }
        }
    if engine == "cloudsql":
        return {
            "cloud_sql": {
                "database_reference": {
                    "project_id": parts["project"],
                    "region": parts["region"],
                    "instance_id": parts["instance"],
                    "database_id": parts["database"],
                }
            }
        }
    if engine == "spanner":
        return {
            "spanner": {
                "database_reference": {
                    "project_id": parts["project"],
                    "instance_id": parts["instance"],
                    "database_id": parts["database"],
                }
            }
        }
    raise ValueError(f"Unsupported engine: {engine!r}. Use alloydb, cloudsql, or spanner.")


def query_data_load_check(
    args: argparse.Namespace, cs_resource_name: str, db_block: dict
) -> bool:
    """Fire a lightweight QueryData call to prove the fresh CS is loadable."""
    client = gda.DataChatServiceClient(
        client_options=ClientOptions(api_endpoint=args.querydata_endpoint)
    )
    # Attach the CS resource under the engine-specific block.
    engine_key = next(iter(db_block))
    db_block[engine_key]["agent_context_reference"] = {"context_set_id": cs_resource_name}

    request = gda.QueryDataRequest(
        parent=f"projects/{args.project}/locations/{args.querydata_location}",
        prompt=args.querydata_prompt,
        context=gda.QueryDataContext(datasource_references=db_block),
        generation_options=gda.GenerationOptions(
            generate_query_result=False,
            generate_natural_language_answer=False,
            generate_explanation=True,
            generate_disambiguation_question=True,
        ),
    )
    response = client.query_data(request=request, timeout=300.0)
    generated_query = getattr(response, "generated_query", None)
    intent_explanation = getattr(response, "intent_explanation", "")
    disambiguation = list(getattr(response, "disambiguation_questions", []))
    print(f"    generated_query      : {generated_query}")
    print(f"    intent_explanation   : {intent_explanation}")
    print(f"    disambiguation_qs    : {disambiguation}")
    return bool(generated_query or intent_explanation or disambiguation)


def normalize_for_diff(d: dict) -> dict:
    """Drop keys whose values are empty collections/None so round-trip diff isn't noisy."""
    return {k: v for k, v in d.items() if v not in ([], {}, None)}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="E2E test for Context Store + QueryData APIs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--project", required=True, help="GCP project id")
    parser.add_argument("--csg-id", required=True, help="ContextSetGroup id (fresh per run recommended)")
    parser.add_argument("--cs-id", default="autoctx", help="ContextSet id (default: autoctx)")
    parser.add_argument("--version", default="v1", help="Version label (default: v1)")
    parser.add_argument(
        "--seed",
        required=True,
        type=pathlib.Path,
        help="Path to a local ContextSet JSON (>=1 template) to upload",
    )
    parser.add_argument(
        "--querydata-endpoint",
        default="autopush-geminidataanalytics.sandbox.googleapis.com",
        help="QueryData API endpoint (default: autopush sandbox)",
    )
    parser.add_argument(
        "--querydata-location",
        default="global",
        help="QueryData API location (default: global)",
    )
    parser.add_argument(
        "--querydata-db",
        required=True,
        help=(
            "Target DB for QueryData call, comma-separated key=value pairs. "
            "AlloyDB: engine=alloydb,project=P,region=R,cluster=C,instance=I,database=D. "
            "CloudSQL: engine=cloudsql,project=P,region=R,instance=I,database=D. "
            "Spanner: engine=spanner,project=P,instance=I,database=D."
        ),
    )
    parser.add_argument(
        "--querydata-prompt",
        default="How many clients?",
        help="NLQ to send to QueryData (default: 'How many clients?')",
    )
    parser.add_argument(
        "--keep-csg",
        action="store_true",
        help="Skip step 6 (delete CSG). Useful for inspection after a run.",
    )
    args = parser.parse_args()

    client = context_store_client.ContextStoreClient()
    seed_ctx = context.ContextSet.model_validate_json(args.seed.read_text())
    db_block = parse_querydata_db(args.querydata_db)

    step(1, f"ensure_context_set_group(project={args.project}, csg={args.csg_id})")
    csg_resource_name = client.ensure_context_set_group(args.project, args.csg_id)
    print(f"    -> {csg_resource_name}")

    step(2, f"ensure_context_set(cs={args.cs_id}, version={args.version})")
    cs_resource_name = client.ensure_context_set(
        args.project, args.csg_id, args.cs_id, args.version
    )
    print(f"    -> {cs_resource_name}")

    step(3, f"upload_context_set (body from {args.seed.name})")
    client.upload_context_set(cs_resource_name, seed_ctx)
    print("    -> OK")

    step(4, "download_context_set + round-trip diff")
    downloaded = client.download_context_set(cs_resource_name)
    uploaded_json = normalize_for_diff(seed_ctx.model_dump(exclude_none=True))
    downloaded_json = normalize_for_diff(downloaded.model_dump(exclude_none=True))
    if uploaded_json != downloaded_json:
        print("    -> MISMATCH")
        print("    uploaded  :", json.dumps(uploaded_json, indent=2))
        print("    downloaded:", json.dumps(downloaded_json, indent=2))
        return 1
    print("    -> round-trip matches (normalized)")

    step(5, f"QueryData load-check (prompt={args.querydata_prompt!r})")
    try:
        ok = query_data_load_check(args, cs_resource_name, db_block)
    except Exception as e:
        print(f"    -> QueryData call raised: {type(e).__name__}: {e}")
        return 1
    if not ok:
        print("    -> QueryData returned empty response (unexpected)")
        return 1
    print("    -> QueryData accepted CS and returned a response")

    if args.keep_csg:
        print(f"\n[6] delete_context_set_group SKIPPED (--keep-csg). CSG remains: {csg_resource_name}")
    else:
        step(6, f"delete_context_set_group({csg_resource_name}) [cascade]")
        client.delete_context_set_group(csg_resource_name)
        print("    -> OK")

    print("\nAll steps passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
