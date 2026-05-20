#!/usr/bin/env bash
# Preflight check for the gcp-data-qa skill.
# Exits 0 if everything is ready; non-zero with remediation otherwise.
#
# Usage: check_prereqs.sh <project_id>
set -u

PROJECT="${1:-}"

ok=true
fail() { echo "MISSING: $1"; echo "  fix: $2"; ok=false; }

# CLI tools
command -v gcloud >/dev/null 2>&1 || fail "gcloud CLI" \
  "install Google Cloud SDK: https://cloud.google.com/sdk/docs/install"
command -v python3 >/dev/null 2>&1 || fail "python3" \
  "install Python 3.9 or newer"

# gcloud auth
if command -v gcloud >/dev/null 2>&1; then
  active=$(gcloud auth list --filter=status:ACTIVE --format="value(account)" 2>/dev/null)
  [ -n "$active" ] || fail "gcloud not authenticated" "run: gcloud auth login"
fi

# ADC (either user creds OR a service-account key)
if [ -n "${GOOGLE_APPLICATION_CREDENTIALS:-}" ]; then
  [ -f "$GOOGLE_APPLICATION_CREDENTIALS" ] || fail \
    "GOOGLE_APPLICATION_CREDENTIALS=$GOOGLE_APPLICATION_CREDENTIALS but file does not exist" \
    "either fix the path or unset the env var to fall back to user ADC"
else
  adc_path="${HOME}/.config/gcloud/application_default_credentials.json"
  [ -f "$adc_path" ] || fail "Application Default Credentials" \
    "either: (a) gcloud auth application-default login  OR  (b) export GOOGLE_APPLICATION_CREDENTIALS=/path/to/sa.json"
fi

# Conversational Analytics API enabled in target project (if a project was passed)
if [ -n "$PROJECT" ] && command -v gcloud >/dev/null 2>&1; then
  enabled=$(gcloud services list --enabled --project="$PROJECT" \
    --filter="config.name:geminidataanalytics.googleapis.com" \
    --format="value(config.name)" 2>/dev/null)
  if [ -z "$enabled" ]; then
    fail "Conversational Analytics API not enabled in project $PROJECT" \
      "run: gcloud services enable geminidataanalytics.googleapis.com --project=$PROJECT"
  fi
fi

# Python SDK
if command -v python3 >/dev/null 2>&1; then
  python3 -c "from google.cloud import geminidataanalytics" 2>/dev/null || fail \
    "Python SDK (google-cloud-geminidataanalytics)" \
    "run: pip install -r $(dirname "$0")/requirements.txt"
fi

if $ok; then
  echo "All prerequisites OK."
  exit 0
else
  exit 1
fi
