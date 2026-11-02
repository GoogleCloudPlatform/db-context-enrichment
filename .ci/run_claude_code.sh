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
# Ensure `quota_project_id` is populated in /tmp/adc.json (service-account keys
# lack it by default, and `gcloud auth application-default set-quota-project`
# does not work on service-account key files) and copy it into the sandboxed
# fake_home (`~/.config/gcloud/application_default_credentials.json`) because
# evalbench's ClaudeCodeGenerator sets `HOME` and `CLOUDSDK_CONFIG` to fake_home
# without forwarding `GOOGLE_APPLICATION_CREDENTIALS` from the host environment.
if [ -n "${EVAL_GCP_PROJECT_ID:-}" ] && command -v jq >/dev/null 2>&1; then
  printf '%s' "${ADC_KEY}" | jq --arg qp "${EVAL_GCP_PROJECT_ID}" '. + {quota_project_id: (.quota_project_id // $qp)}' > /tmp/adc.json
else
  echo "${ADC_KEY}" > /tmp/adc.json
fi
chmod 600 /tmp/adc.json
export GOOGLE_APPLICATION_CREDENTIALS=/tmp/adc.json
export GOOGLE_CLOUD_PROJECT="${EVAL_GCP_PROJECT_ID:-}"
export GOOGLE_CLOUD_QUOTA_PROJECT="${EVAL_GCP_PROJECT_ID:-}"
export CLAUDE_PLUGIN_ROOT="/workspace/plugin"

# Isolate: copy this suite + the shared model_configs into its own working
# directory so parallel runs don't fight over the same .venv / fake_home /
# .claude state, and sed edits don't leak across SUTs.
WORK_DIR="/workspace/eval-${SUT}-${SUITE}"
mkdir -p "${WORK_DIR}"
cp -r "/workspace/evals/${SUITE}" "${WORK_DIR}/"
cp -r "/workspace/evals/model_configs" "${WORK_DIR}/"
cd "${WORK_DIR}"

# Pre-seed ADC and gcloud project config inside both real HOME and Claude Code's
# sandboxed fake_home so `plugin/scripts/adc_headers.sh` (`headersHelper` for
# `ctxset`) and `gcloud` commands inside Claude Code can mint tokens and read
# `quota_project_id` immediately at plugin install and startup time.
for GCLOUD_DIR in "${HOME}/.config/gcloud" "${WORK_DIR}/.venv/fake_home_claude/.config/gcloud"; do
  mkdir -p "${GCLOUD_DIR}/configurations"
  cp /tmp/adc.json "${GCLOUD_DIR}/application_default_credentials.json"
  chmod 600 "${GCLOUD_DIR}/application_default_credentials.json"
  if [ -n "${EVAL_GCP_PROJECT_ID:-}" ]; then
    printf '[core]\nproject = %s\n' "${EVAL_GCP_PROJECT_ID}" > "${GCLOUD_DIR}/configurations/config_default"
    printf 'default' > "${GCLOUD_DIR}/active_config"
  fi
done

# Repoint `skills_dir` at the in-repo plugin checkout (/workspace/dev-plugin)
# so we don't need to stage a copy inside WORK_DIR.
sed -i "s|skills_dir: \"./dev-plugin\"|skills_dir: \"/workspace/dev-plugin\"|g" "model_configs/claude_code_model.yaml"

# Inject the Vertex project ID at the root level of claude_code_model.yaml
# (kept out of the repo so the project ID isn't committed).
sed -i "/^vertex_region:/a\\vertex_project_id: \"${CLAUDE_GCP_VERTEX_PROJECT_ID}\"" "model_configs/claude_code_model.yaml"

# Append the runtime release_version and resolve the reporting-project
# placeholder so evalbench's BigQuery reporter records them.
RELEASE_VERSION="$(cat /workspace/RELEASE_VERSION 2>/dev/null || echo unknown)"
CONFIG="${SUITE}/run_claude.yaml"
printf '\nrelease_version: %s\n' "${RELEASE_VERSION}" >> "${CONFIG}"
sed -i "s|\${EVAL_REPORTING_PROJECT}|${EVAL_REPORTING_PROJECT:-}|g" "${CONFIG}"

# evalbench runtime
export PYTHONPATH=/evalbench:/evalbench/evalproto
export PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python

echo "Launching ${SUT}/${SUITE} evaluation..."
uv run --no-sync --project /evalbench python /evalbench/evalbench/evalbench.py --experiment_config="${SUITE}/run_claude.yaml"

echo "Validating mandatory output files for ${SUITE}..."
python3 /workspace/.ci/check_eval_outputs.py "${WORK_DIR}/${SUITE}" "${WORK_DIR}/${SUITE}/dataset.json"

touch "/workspace/EVAL_RAN_${SUT}-${SUITE}"
