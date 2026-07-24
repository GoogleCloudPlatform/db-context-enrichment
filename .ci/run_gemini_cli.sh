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

# The smoke-test suite always runs regardless of PR labels; other suites are
# gated by the ci:eval label (marker written by the preflight step).
if [ "${SUITE}" != "smoke-test" ] && [ ! -f /workspace/SHOULD_RUN_GEMINI_CLI ]; then
  echo "Gemini CLI evals disabled by preflight (missing 'ci:eval' label); skipping ${SUT}/${SUITE}."
  exit 0
fi

# ADC setup
echo "${ADC_KEY}" > /tmp/adc.json
chmod 600 /tmp/adc.json
export GOOGLE_APPLICATION_CREDENTIALS=/tmp/adc.json

# Isolate: copy this suite + the shared model_configs into its own working
# directory so parallel runs don't fight over the same .venv / fake_home /
# .gemini/tmp state, and sed edits don't leak across SUTs.
WORK_DIR="/workspace/eval-${SUT}-${SUITE}"
mkdir -p "${WORK_DIR}"
cp -r "/workspace/evals/${SUITE}" "${WORK_DIR}/"
cp -r "/workspace/evals/model_configs" "${WORK_DIR}/"
cd "${WORK_DIR}"

# Point the Gemini CLI extension installer at the locally built extension.
sed -i "s|<extension-source>|/workspace/staging|g" "model_configs/gemini_cli_model.yaml"

# Substitute Vertex project/location placeholders in the CLI env block so the
# extension can talk to the right GCP project without the values being
# committed to the repo.
sed -i \
  -e "s|<gcp-project>|${EVAL_GCP_PROJECT_ID}|g" \
  -e "s|<gcp-location>|${EVAL_GCP_PROJECT_REGION}|g" \
  "model_configs/gemini_cli_model.yaml"

# Append the runtime release_version and resolve the reporting-project
# placeholder so evalbench's BigQuery reporter records them.
RELEASE_VERSION="$(cat /workspace/RELEASE_VERSION 2>/dev/null || echo unknown)"
CONFIG="${SUITE}/run_gemini_cli.yaml"
printf '\nrelease_version: %s\n' "${RELEASE_VERSION}" >> "${CONFIG}"
sed -i "s|\${EVAL_REPORTING_PROJECT}|${EVAL_REPORTING_PROJECT:-}|g" "${CONFIG}"

# evalbench runtime
export PYTHONPATH=/evalbench:/evalbench/evalproto
export PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python

# Optional scenario filter: set EVAL_SCENARIOS=<id>[,<id>...] to run a subset.
SCENARIO_ARG=""
[ -n "${EVAL_SCENARIOS:-}" ] && SCENARIO_ARG="--scenarios=${EVAL_SCENARIOS}"

echo "Launching ${SUT}/${SUITE} evaluation${SCENARIO_ARG:+ (scenarios: ${EVAL_SCENARIOS})}..."
uv run --no-sync --project /evalbench python /evalbench/evalbench/evalbench.py --experiment_config="${SUITE}/run_gemini_cli.yaml" ${SCENARIO_ARG}

echo "Validating mandatory output files for ${SUITE}..."
python3 /workspace/.ci/check_eval_outputs.py "${WORK_DIR}/${SUITE}" "${WORK_DIR}/${SUITE}/dataset.json"

touch "/workspace/EVAL_RAN_${SUT}-${SUITE}"
