#!/usr/bin/env bash
# Preflight check for the gcp-customer-context-builder skill.
# Exits 0 if everything is ready; non-zero with a remediation message otherwise.
set -u

ok=true
fail() { echo "MISSING: $1"; echo "  fix: $2"; ok=false; }

command -v gcloud >/dev/null 2>&1 || fail "gcloud CLI" \
  "install Google Cloud SDK: https://cloud.google.com/sdk/docs/install"
command -v bq >/dev/null 2>&1 || fail "bq CLI" \
  "install Google Cloud SDK (includes bq): https://cloud.google.com/sdk/docs/install"
command -v python3 >/dev/null 2>&1 || fail "python3" \
  "install Python 3.9 or newer"

if command -v gcloud >/dev/null 2>&1; then
  active=$(gcloud auth list --filter=status:ACTIVE --format="value(account)" 2>/dev/null)
  [ -n "$active" ] || fail "gcloud not authenticated" \
    "run: gcloud auth login"
fi

# Auth for Drive/Docs/Sheets APIs. Two valid paths:
#   1. GOOGLE_APPLICATION_CREDENTIALS env var pointing to a service-account JSON
#   2. Application Default Credentials from `gcloud auth application-default login`
if [ -n "${GOOGLE_APPLICATION_CREDENTIALS:-}" ]; then
  [ -f "$GOOGLE_APPLICATION_CREDENTIALS" ] || fail \
    "GOOGLE_APPLICATION_CREDENTIALS=$GOOGLE_APPLICATION_CREDENTIALS but file does not exist" \
    "either fix the path or unset the env var to fall back to user ADC"
else
  adc_path="${HOME}/.config/gcloud/application_default_credentials.json"
  [ -f "$adc_path" ] || fail "Application Default Credentials" \
    "either: (a) gcloud auth application-default login --scopes=openid,https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/drive.readonly,https://www.googleapis.com/auth/documents.readonly,https://www.googleapis.com/auth/spreadsheets.readonly  OR  (b) export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json"
fi

if command -v python3 >/dev/null 2>&1; then
  python3 -c "import googleapiclient, google.auth" 2>/dev/null || fail \
    "Python deps (google-api-python-client, google-auth)" \
    "run: pip install -r $(dirname "$0")/requirements.txt"
fi

if $ok; then
  echo "All prerequisites OK."
  exit 0
else
  exit 1
fi
