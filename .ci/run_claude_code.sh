#!/usr/bin/env bash
# Run a single evalbench suite against the Claude Code SUT in an isolated
# working directory.
#
# Invoked from .ci/cloudbuild.yaml. Required env vars: ADC_KEY,
# CLAUDE_GCP_VERTEX_PROJECT_ID.
# Required argument: <suite-name> (e.g. core-cujs, freeform-input).

set -e

SUITE="${1:?usage: run_claude_code.sh <suite-name>}"
SUT="claude-code"

# The smoke-test suite always runs regardless of PR labels; other suites are
# gated by the ci:eval-claude label (marker written by the preflight step).
if [ "${SUITE}" != "smoke-test" ] && [ ! -f /workspace/SHOULD_RUN_CLAUDE_CODE ]; then
  echo "Claude Code evals disabled by preflight (missing 'ci:eval-claude' label); skipping ${SUT}/${SUITE}."
  exit 0
fi

# ADC setup
echo "${ADC_KEY}" > /tmp/adc.json
chmod 600 /tmp/adc.json
export GOOGLE_APPLICATION_CREDENTIALS=/tmp/adc.json

# Isolate: copy this suite + the shared model_configs into its own working
# directory so parallel runs don't fight over the same .venv / fake_home /
# .claude state, and sed edits don't leak across SUTs.
WORK_DIR="/workspace/eval-${SUT}-${SUITE}"
mkdir -p "${WORK_DIR}"
cp -r "/workspace/evals/${SUITE}" "${WORK_DIR}/"
cp -r "/workspace/evals/model_configs" "${WORK_DIR}/"
cd "${WORK_DIR}"

# Repoint `skills_dir` at the in-repo marketplace checkout (/workspace/dev) so
# we don't need to stage a copy inside WORK_DIR.
sed -i "s|skills_dir: \"./dev\"|skills_dir: \"/workspace/dev\"|g" "model_configs/claude_code_model.yaml"

# Inject the Vertex project ID at the root level of claude_code_model.yaml
# (kept out of the repo so the project ID isn't committed).
sed -i "/^vertex_region:/a\\vertex_project_id: \"${CLAUDE_GCP_VERTEX_PROJECT_ID}\"" "model_configs/claude_code_model.yaml"

# Point the db-context-engineering MCP server at the local checkout instead of
# `uvx <pkg>@latest`, so the eval exercises the PR's code rather than whatever
# is published on PyPI. The mutation is idempotent — parallel Claude suites
# write the same value to the shared /workspace/plugin tree.
sed -i 's|"google-cloud-db-context-engineering@latest"|"--from", "/workspace", "google-cloud-db-context-engineering"|' "/workspace/plugin/.claude-plugin/plugin.json"

# evalbench runtime
export PYTHONPATH=/evalbench:/evalbench/evalproto
export PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python

echo "Launching ${SUT}/${SUITE} evaluation..."
uv run --no-sync --project /evalbench python /evalbench/evalbench/evalbench.py --experiment_config="${SUITE}/run_claude.yaml"

touch "/workspace/EVAL_RAN_${SUT}-${SUITE}"
