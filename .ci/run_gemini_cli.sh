#!/usr/bin/env bash
# Run a single evalbench suite against the Gemini CLI SUT in an isolated
# working directory.
#
# Invoked from .ci/cloudbuild.yaml. Required env vars: ADC_KEY,
# EVAL_GCP_PROJECT_ID, EVAL_GCP_PROJECT_REGION.
# Required argument: <suite-name> (e.g. core-cujs, freeform-input).

set -e

SUITE="${1:?usage: run_gemini_cli.sh <suite-name>}"
SUT="gemini-cli"

if [ ! -f /workspace/SHOULD_RUN_GEMINI_CLI ]; then
  echo "Gemini CLI evals disabled by preflight (missing 'ci:eval' label); skipping ${SUT}/${SUITE}."
  exit 0
fi

# ADC setup
echo "${ADC_KEY}" > /tmp/adc.json
chmod 600 /tmp/adc.json
export GOOGLE_APPLICATION_CREDENTIALS=/tmp/adc.json

# Isolate: copy this suite + the shared model_configs into a per-run working
# directory under /tmp so parallel runs don't fight over the same .venv /
# fake_home / .gemini/tmp state, and sed edits don't leak across SUTs.
WORK_DIR="/tmp/workspace_${SUT}-${SUITE}"
OUTPUT_DIR="/workspace/eval-${SUT}-${SUITE}"
mkdir -p "${WORK_DIR}"
cp -r "/workspace/evals/${SUITE}" "${WORK_DIR}/"
cp -r "/workspace/evals/model_configs" "${WORK_DIR}/"
cd "${WORK_DIR}"

# Point the Gemini CLI extension installer at the locally built extension
# instead of pulling from GitHub.
sed -i 's|https://github.com/GoogleCloudPlatform/db-context-enrichment|/workspace/staging|g' "model_configs/gemini_cli_model.yaml"

# Inject Vertex project/location into the CLI env block so the extension can
# talk to the right GCP project without the values being committed to the repo.
sed -i \
  -e "/^  GEMINI_MODEL:/a\\  GOOGLE_CLOUD_PROJECT: \"${EVAL_GCP_PROJECT_ID}\"" \
  -e "/^  GEMINI_MODEL:/a\\  GOOGLE_CLOUD_LOCATION: \"${EVAL_GCP_PROJECT_REGION}\"" \
  "model_configs/gemini_cli_model.yaml"

# evalbench runtime
export PYTHONPATH=/evalbench:/evalbench/evalproto
export PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python

echo "Launching ${SUT}/${SUITE} evaluation..."
uv run --no-sync --project /evalbench python /evalbench/evalbench/evalbench.py --experiment_config="${SUITE}/run_gemini_cli.yaml"

# Copy results into /workspace so the upload step (a separate Cloud Build
# step) can see them. /tmp is per-step and not shared across steps.
mkdir -p "${OUTPUT_DIR}"
cp -r "${WORK_DIR}/." "${OUTPUT_DIR}/"
touch "/workspace/EVAL_RAN_${SUT}-${SUITE}"
