#!/usr/bin/env bash
# Run the Claude Code evalbench suite (core-cujs only) in an isolated
# working directory.
#
# Invoked from .ci/cloudbuild.yaml. Required env vars: ADC_KEY,
# CLAUDE_GCP_VERTEX_PROJECT_ID.

set -e

SUITE="core-cujs"
# Branch the Claude Code plugin is installed from. CI passes the PR's
# head branch via CLAUDE_PLUGIN_BRANCH ($_HEAD_BRANCH from Cloud Build);
# falls back to main for manual / non-PR runs.
PLUGIN_BRANCH="${CLAUDE_PLUGIN_BRANCH:-main}"

echo $CLAUDE_PLUGIN_BRANCH
PLUGIN_BRANCH="feat/claude-code-plugin"

if [ ! -f /workspace/SHOULD_RUN ]; then
  echo "Evals disabled by preflight; skipping Claude ${SUITE}."
  exit 0
fi

# ADC setup
echo "${ADC_KEY}" > /tmp/adc.json
chmod 600 /tmp/adc.json
export GOOGLE_APPLICATION_CREDENTIALS=/tmp/adc.json

# Isolate: copy this suite into its own working directory so it doesn't
# clash with the Gemini run.
WORK_DIR="/workspace/eval-claude-${SUITE}"
mkdir -p "${WORK_DIR}"
cp -r "/workspace/evals/${SUITE}" "${WORK_DIR}/"
cd "${WORK_DIR}"

# Append the feature branch to the plugin install URL.
sed -i "s|db-context-enrichment.git\"|db-context-enrichment.git#${PLUGIN_BRANCH}\"|g" "${SUITE}/claude_code_model.yaml"

# Inject the Vertex project ID at the root level of claude_code_model.yaml
# (kept out of the repo so the project ID isn't committed).
sed -i "/^vertex_region:/a\\vertex_project_id: \"${CLAUDE_GCP_VERTEX_PROJECT_ID}\"" "${SUITE}/claude_code_model.yaml"

# evalbench runtime
export PYTHONPATH=/evalbench:/evalbench/evalproto
export PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python

echo "Launching Claude Code ${SUITE} evaluation..."
uv run --no-sync --project /evalbench python /evalbench/evalbench/evalbench.py --experiment_config="${SUITE}/run_claude.yaml"

touch "/workspace/EVAL_RAN_claude-${SUITE}"
