#!/usr/bin/env bash
# Run a single evalbench suite in an isolated working directory.
#
# Invoked from .ci/cloudbuild.yaml. Required env vars: ADC_KEY,
# GEMINI_API_KEY, EVAL_GCP_PROJECT_ID, EVAL_GCP_PROJECT_REGION.
# Required argument: <suite-name> (e.g. core-cujs, freeform-input).

set -e

SUITE="${1:?usage: run_eval.sh <suite-name>}"

if [ ! -f /workspace/SHOULD_RUN ]; then
  echo "Evals disabled by preflight; skipping ${SUITE}."
  exit 0
fi

# ADC setup
echo "${ADC_KEY}" > /tmp/adc.json
chmod 600 /tmp/adc.json
export GOOGLE_APPLICATION_CREDENTIALS=/tmp/adc.json

# Isolate: copy this suite into its own working directory so parallel
# runs don't fight over the same .venv / fake_home / .gemini/tmp state.
WORK_DIR="/workspace/eval-${SUITE}"
mkdir -p "${WORK_DIR}"
cp -r "/workspace/evals/${SUITE}" "${WORK_DIR}/"
cd "${WORK_DIR}"

# Point model.yaml at the locally built extension and inject the Gemini API
# key into the CLI's env (orchestrator auth — the extension itself no longer
# needs the key, so we no longer touch the `settings: {}` block).
sed -i 's|https://github.com/GoogleCloudPlatform/db-context-enrichment|/workspace/staging|g' "${SUITE}/model.yaml"

# evalbench runtime
export PYTHONPATH=/evalbench:/evalbench/evalproto
export PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python

echo "Launching ${SUITE} evaluation..."
uv run --project /evalbench python /evalbench/evalbench/evalbench.py --experiment_config="${SUITE}/run.yaml"

touch "/workspace/EVAL_RAN_${SUITE}"
