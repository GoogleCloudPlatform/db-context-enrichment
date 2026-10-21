#!/usr/bin/env bash
# Prints the HTTP headers (as a JSON object) that the remote Context Set server
# MCP server needs, derived from Application Default Credentials.
#
# Used as Claude Code's `headersHelper` for the `ctxset` server
# (https://code.claude.com/docs/en/mcp#use-dynamic-headers-for-custom-authentication):
# Claude runs it at connect time and again automatically after a 401/403, so
# token expiry is handled without user action. Must finish in < 10 s and print
# nothing but JSON to stdout. Only dependency: `gcloud`.
#
# Antigravity and Gemini CLI do not use this script; they attach ADC natively
# via `authProviderType: "google_credentials"`, deriving X-Goog-User-Project
# from the same ADC quota project, so all three clients behave identically.
set -euo pipefail

token="$(gcloud auth application-default print-access-token 2>/dev/null)" || {
  echo 'adc_headers.sh: no Application Default Credentials. Run: gcloud auth application-default login' >&2
  exit 1
}

# X-Goog-User-Project (the Context Set server returns 400 without it).
# Derived strictly from quota_project_id in the ADC file (set by:
# gcloud auth application-default set-quota-project <project>)
quota=""
adc_file="${GOOGLE_APPLICATION_CREDENTIALS:-${CLOUDSDK_CONFIG:-$HOME/.config/gcloud}/application_default_credentials.json}"
if [ -f "$adc_file" ]; then
  quota="$(sed -n 's/.*"quota_project_id"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$adc_file" | head -n 1)"
fi

if [ -n "$quota" ] && ! [[ "$quota" =~ ^[a-zA-Z0-9.:-]+$ ]]; then
  echo "adc_headers.sh: warning: ignoring invalid quota project format: $quota" >&2
  quota=""
fi

if [ -n "$quota" ]; then
  printf '{"Authorization":"Bearer %s","X-Goog-User-Project":"%s"}' "$token" "$quota"
else
  echo 'adc_headers.sh: warning: no quota project found; set one with: gcloud auth application-default set-quota-project <project>' >&2
  printf '{"Authorization":"Bearer %s"}' "$token"
fi
