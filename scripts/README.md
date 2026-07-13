# API E2E test scripts

Utility scripts for end-to-end verification of Context Store and Gemini Data Analytics (QueryData) APIs. These are **manual** — not run by CI. Use them for local sanity checks, bughunts, or reproducing reported failures against a known-good input.

## `e2e_context_store.py`

Round-trips a ContextSet through Context Store (create CSG → create CS → upload → download → diff) and then verifies the fresh resource is loadable via QueryData. Cleans up on success.

### Setup (first-run checklist)

If you've never run this script before, do these in order:

```bash
# 1. Clone + switch to the branch (or main once merged)
git clone https://github.com/GoogleCloudPlatform/db-context-enrichment.git
cd db-context-enrichment
git checkout chore/api-e2e-bughunt-script

# 2. Install uv if not already (https://docs.astral.sh/uv/getting-started/installation/)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 3. Install Python deps into the repo's venv
uv sync

# 4. Install / verify gcloud CLI (https://cloud.google.com/sdk/docs/install)
gcloud --version

# 5. Set up Application Default Credentials + quota project
gcloud auth application-default login
gcloud auth application-default set-quota-project <your-project>

# 6. Enable required APIs on the target project (skip if already enabled)
gcloud services enable dataplex.googleapis.com geminidataanalytics.googleapis.com --project=<your-project>

# 7. Ensure your IAM principal has:
#    - a Context Store role on the project (for CS create/read/write/delete)
#    - a Gemini Data Analytics role on the project (for QueryData calls)
#    Ask your IAM admin if you're unsure.

# 8. Have a seed ContextSet JSON ready with >=1 Template.
#    (Context Store's legacy validation rejects empty ContextSets.)
```

### Prerequisites (quick reference)

- **`uv` installed** — the script runs under the repo's uv venv so it can import `google.cloud.db_context_enrichment.common.context_store_client`.
- **Application Default Credentials** — `gcloud auth application-default login`.
- **ADC quota project set** — `gcloud auth application-default set-quota-project <project>`. Context Store requires the `X-Goog-User-Project` header; missing → 400.
- **APIs enabled on the target project** — `dataplex.googleapis.com` (Context Store), `geminidataanalytics.googleapis.com` (QueryData).
- **IAM on the ADC principal** — a Context Store role for the CS operations, a Gemini Data Analytics role for the QueryData call.
- **A seed ContextSet JSON** with at least one Template — Context Store's legacy validation rejects empty ContextSets.

### Usage

Run from the repo root:

```bash
uv run python scripts/e2e_context_store.py \
  --project astana-transformation \
  --csg-id my-bughunt-$(date +%Y%m%d) \
  --cs-id autoctx --version v1 \
  --seed ./tests/crema-test/test-1/bootstrap_context.json \
  --querydata-db 'engine=alloydb,project=astana-transformation,region=us-east4,cluster=juexinw-test,instance=juexinw-test-primary,database=financial' \
  --querydata-prompt 'How many clients?'
```

### Arguments

| Flag | Required | Description |
|---|---|---|
| `--project` | yes | GCP project id for both Context Store and QueryData. |
| `--csg-id` | yes | ContextSetGroup id. Use a fresh, date-stamped name per run so you're testing the create path (idempotent on 409, but fresh names catch bugs in the creation code paths). |
| `--cs-id` | no | ContextSet id (default `autoctx`). |
| `--version` | no | Version label (default `v1`). |
| `--seed` | yes | Path to a local ContextSet JSON with `≥1` Template. |
| `--querydata-endpoint` | no | QueryData API endpoint (default `autopush-geminidataanalytics.sandbox.googleapis.com`). Use the prod endpoint to test prod. |
| `--querydata-location` | no | QueryData API location (default `global`). |
| `--querydata-db` | yes | Target DB spec, comma-separated `key=value`. See below. |
| `--querydata-prompt` | no | NLQ to send (default `'How many clients?'`). |
| `--keep-csg` | no | Skip step 6 (delete CSG). Useful when you want to inspect state after a run. |

**`--querydata-db` format** — pick the shape matching your DB engine:

- AlloyDB: `engine=alloydb,project=P,region=R,cluster=C,instance=I,database=D`
- Cloud SQL: `engine=cloudsql,project=P,region=R,instance=I,database=D`
- Spanner: `engine=spanner,project=P,instance=I,database=D`

### Output

Six steps, each prints its own status line. Exit code:
- **0** — all steps passed. CSG deleted (unless `--keep-csg`).
- **1** — a step failed. Failing step's error is printed. CSG is left in place for inspection.

### Bughunt tips

- **Fresh CSG per run**: date-stamp `--csg-id` (e.g., `my-bughunt-20260712`) so you exercise the CSG-create code path each time. Idempotent runs (same name) also work but skip creation.
- **Test the prod endpoint**: swap `--querydata-endpoint prod-geminidataanalytics.googleapis.com` (or the real prod hostname) to catch regressions specific to the prod control plane.
- **Test different seeds**: try minimal (1 Template), rich (many Templates + Facets + Value Searches), and edge cases (empty Templates list — this should error at upload time by design).
- **Test different DB engines**: switch `--querydata-db engine=...` to exercise each Toolbox-supported engine.
- **Break auth and observe**: unset ADC or clear quota project, verify the error messages are actionable.
- **Concurrent runs**: run the same script in two shells with different `--csg-id` values to verify no cross-contamination.

### Reporting a failure

When filing a bughunt issue, include:
- The full script invocation (with your `--project`, `--csg-id`, etc.).
- The step number that failed.
- Verbatim error output.
- Any HTTP trace ID in the error (Sherlog needs it).
- Your ADC identity (`gcloud auth application-default print-access-token | ...` — or just email if you know it).
