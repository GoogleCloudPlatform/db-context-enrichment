"""REST client for the Context Store API.

Hand-rolled because the service is GOOGLE_INTERNAL and has no public SDK.
All calls target the autopush sandbox endpoint pinned in this module.
"""

import json
import time
from typing import Any

import google.auth
import google.auth.exceptions
import requests
from google.auth.transport import requests as auth_requests

from google.cloud.db_context_enrichment.model import context

CONTEXT_STORE_ENDPOINT = "https://dataplex.googleapis.com"
CONTEXT_STORE_LOCATION = "us-central1"
API_VERSION = "v1"
DEFAULT_OAUTH_SCOPES = ("https://www.googleapis.com/auth/cloud-platform",)

# Per-request HTTP timeout + LRO poll schedule. Transient-error retry is
# intentionally NOT done here — the MCP agent driving these tools retries
# failed tool calls on its own, and the Cloud SDK (once available) will bring
# proper retry back. Only the per-call timeout and op polling stay in this
# hand-rolled client.
_LRO_POLL_INTERVALS_SECONDS = (2.0, 4.0, 8.0, 16.0, 16.0, 16.0)
_REQUEST_TIMEOUT_SECONDS = 30


class ContextStoreClient:
    """REST client for the Context Store API (autopush sandbox).

    The client is stateless w.r.t. project. Operations that build a resource
    path from IDs (`ensure_*`) take `project_id` as an explicit argument;
    operations that take a fully-qualified resource name don't need it.

    The quota project (billing / quota) is taken from ADC's
    `quota_project_id` if set, else the project ADC returns alongside the
    credentials (user default via `gcloud config get-value project`, or the
    SA key's `project_id`). Sent as `X-Goog-User-Project` on every request.
    Omitted if neither is available.
    """

    def __init__(self):
        try:
            credentials, default_project = google.auth.default(
                scopes=DEFAULT_OAUTH_SCOPES
            )
        except google.auth.exceptions.DefaultCredentialsError as e:
            raise RuntimeError(
                "No Application Default Credentials found. Run "
                "'gcloud auth application-default login' first."
            ) from e
        # Matches how the generated Google SDKs pick a billing project:
        # explicit ADC quota project first, then ADC's default project.
        quota_project = credentials.quota_project_id or default_project
        self._session = auth_requests.AuthorizedSession(credentials)
        if quota_project:
            self._session.headers["X-Goog-User-Project"] = quota_project

    def ensure_context_set_group(self, project_id: str, csg_id: str) -> str:
        """Return a CSG's full resource name, creating it if absent.

        Idempotent: a 409 (already exists, whether pre-existing or from a
        concurrent create) is treated as success.
        """
        parent = f"projects/{project_id}/locations/{CONTEXT_STORE_LOCATION}"
        create_url = (
            f"{CONTEXT_STORE_ENDPOINT}/{API_VERSION}/{parent}/contextSetGroups"
            f"?context_set_group_id={csg_id}"
        )
        try:
            self._request_lro("POST", create_url, json_body={})
        except requests.HTTPError as e:
            if e.response.status_code != 409:
                raise
        return f"{parent}/contextSetGroups/{csg_id}"

    def delete_context_set_group(self, csg_resource_name: str) -> None:
        """Delete a ContextSetGroup by full resource name. Blocks on LRO.

        Idempotent: a 404 (already deleted or never existed) is treated as
        success. Cascades: all ContextSets inside the group are also deleted.
        """
        try:
            self._request_lro(
                "DELETE", f"{CONTEXT_STORE_ENDPOINT}/{API_VERSION}/{csg_resource_name}"
            )
        except requests.HTTPError as e:
            if e.response.status_code != 404:
                raise

    def ensure_context_set(
        self, project_id: str, csg_id: str, cs_id: str, version: str
    ) -> str:
        """Return a CS's full resource name, creating it (and the parent CSG)
        if absent.

        Idempotent: a 409 on the CS create is treated as success. Body is not
        touched — the caller still needs `upload_context_set` to overwrite it.
        """
        csg_resource_name = self.ensure_context_set_group(project_id, csg_id)
        url = (
            f"{CONTEXT_STORE_ENDPOINT}/{API_VERSION}/{csg_resource_name}/contextSets"
            f"?context_set_id={cs_id}"
        )
        body = {"context_set_id": cs_id, "version": version}
        try:
            self._request("POST", url, json_body=body)
        except requests.HTTPError as e:
            if e.response.status_code != 409:
                raise
        return f"{csg_resource_name}/contextSets/{cs_id}@{version}"

    def upload_context_set(
        self, cs_resource_name: str, ctx: context.ContextSet
    ) -> None:
        """Populate an existing ContextSet's body.

        The resource must already exist (call `ensure_context_set` first).
        """
        url = f"{CONTEXT_STORE_ENDPOINT}/{API_VERSION}/{cs_resource_name}:upload"
        body = {"context_json": ctx.model_dump_json(exclude_none=True)}
        self._request("POST", url, json_body=body)

    def download_context_set(self, cs_resource_name: str) -> context.ContextSet:
        """Download and parse a ContextSet by full resource name."""
        url = f"{CONTEXT_STORE_ENDPOINT}/{API_VERSION}/{cs_resource_name}:download"
        resp = self._request("POST", url, json_body={})
        raw = resp.get("contextJson")
        if raw is None:
            raise ValueError(f"DownloadContextSet response missing contextJson: {resp}")
        # ContextSet models accept camelCase aliases too (see
        # `_BaseContextModel`), so the server's mixed casing validates
        # without conversion.
        return context.ContextSet.model_validate(json.loads(raw))

    def _request(
        self,
        method: str,
        url: str,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send one HTTP request and return parsed JSON.

        Returns an empty dict if the response body is empty (eg. 204 No
        Content). Raises `requests.HTTPError` on 4xx/5xx,
        `requests.RequestException` on network failure.
        """
        response = self._session.request(
            method, url, json=json_body, timeout=_REQUEST_TIMEOUT_SECONDS
        )
        response.raise_for_status()
        return response.json() if response.content else {}

    def _request_lro(
        self,
        method: str,
        url: str,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Issue a request that returns an LRO and poll until it completes.

        - HTTP layer (`_request`): each call returns 200; raises on 4xx/5xx.
        - Op layer: `done` / `response` / `error` live in the JSON body, not
          the HTTP status.
        - Sleeps per `_LRO_POLL_INTERVALS_SECONDS`; raises `TimeoutError`
          on budget exhaustion or `RuntimeError` on op-reported error.
        """
        op = self._request(method, url, json_body=json_body)
        op_name = op.get("name")
        if not op_name:
            raise RuntimeError(f"{method} {url} returned no operation name: {op}")

        # Skip the poll cycle if the initial op is already done (some LROs
        # complete synchronously). Otherwise poll until it does or the
        # budget is exhausted.
        poll_url = f"{CONTEXT_STORE_ENDPOINT}/{API_VERSION}/{op_name}"
        for delay in _LRO_POLL_INTERVALS_SECONDS:
            if op.get("done"):
                break
            time.sleep(delay)
            op = self._request("GET", poll_url)
        if not op.get("done"):
            raise TimeoutError(f"LRO {op_name} did not complete within the poll budget")
        if "error" in op:
            err = op["error"]
            raise RuntimeError(
                f"LRO {op_name} failed: [{err.get('code')}] "
                f"{err.get('message', 'unknown LRO error')}"
            )
        return op.get("response", {})
