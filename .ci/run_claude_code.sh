#!/usr/bin/env bash
# Run a single evalbench suite against the Claude Code SUT in an isolated
# working directory.
#
# Invoked from .ci/cloudbuild.yaml. Required env vars: ADC_KEY,
# CLAUDE_GCP_VERTEX_PROJECT_ID. Optional: CLAUDE_PLUGIN_BRANCH.
# Required argument: <suite-name> (e.g. core-cujs, freeform-input).

set -e

SUITE="${1:?usage: run_claude_code.sh <suite-name>}"
SUT="claude-code"
# Branch the Claude Code plugin is installed from. CI passes the PR's
# head branch via CLAUDE_PLUGIN_BRANCH ($_HEAD_BRANCH from Cloud Build);
# falls back to main for manual / non-PR runs.
PLUGIN_BRANCH="${CLAUDE_PLUGIN_BRANCH:-main}"

echo $CLAUDE_PLUGIN_BRANCH
# TODO: remove this CLAUDE_PLUGIN_BRANCH override once feat/claude-code-plugin is merged to main.
PLUGIN_BRANCH="feat/claude-code-plugin"

if [ ! -f /workspace/SHOULD_RUN_CLAUDE_CODE ]; then
  echo "Claude Code evals disabled by preflight (missing 'ci:eval-claude' label); skipping ${SUT}/${SUITE}."
  exit 0
fi

# ADC setup
echo "${ADC_KEY}" > /tmp/adc.json
chmod 600 /tmp/adc.json
export GOOGLE_APPLICATION_CREDENTIALS=/tmp/adc.json

# Isolate: copy this suite + the shared model_configs into a per-run working
# directory under /tmp so parallel runs don't fight over the same .venv /
# fake_home / .claude state, and sed edits don't leak across SUTs.
WORK_DIR="/tmp/workspace_${SUT}-${SUITE}"
OUTPUT_DIR="/workspace/eval-${SUT}-${SUITE}"
mkdir -p "${WORK_DIR}"
cp -r "/workspace/evals/${SUITE}" "${WORK_DIR}/"
cp -r "/workspace/evals/model_configs" "${WORK_DIR}/"
cd "${WORK_DIR}"

# Append the feature branch to the plugin install URL.
sed -i "s|db-context-enrichment.git\"|db-context-enrichment.git#${PLUGIN_BRANCH}\"|g" "model_configs/claude_code_model.yaml"

# Inject the Vertex project ID at the root level of claude_code_model.yaml
# (kept out of the repo so the project ID isn't committed).
sed -i "/^vertex_region:/a\\vertex_project_id: \"${CLAUDE_GCP_VERTEX_PROJECT_ID}\"" "model_configs/claude_code_model.yaml"

# evalbench runtime
export PYTHONPATH=/evalbench:/evalbench/evalproto
export PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python

echo "Launching ${SUT}/${SUITE} evaluation..."
uv run --no-sync --project /evalbench python /evalbench/evalbench/evalbench.py --experiment_config="${SUITE}/run_claude.yaml"

# Copy results into /workspace so the upload step (a separate Cloud Build
# step) can see them. /tmp is per-step and not shared across steps.
mkdir -p "${OUTPUT_DIR}"
cp -r "${WORK_DIR}/." "${OUTPUT_DIR}/"
touch "/workspace/EVAL_RAN_${SUT}-${SUITE}"
