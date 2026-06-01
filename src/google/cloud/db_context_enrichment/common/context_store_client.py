"""REST client for the Context Store API.

Hand-rolled because the service is GOOGLE_INTERNAL and has no public SDK.
All calls target the autopush sandbox endpoint pinned in this module.
"""

import json
import logging
import re
import time
from typing import Any

import google.auth
import google.auth.exceptions
import requests
from google.auth.transport.requests import AuthorizedSession

from google.cloud.db_context_enrichment.model.context import ContextSet

logger = logging.getLogger(__name__)

CONTEXT_STORE_ENDPOINT = "https://autopush-dataplex.sandbox.googleapis.com"
API_VERSION = "v1"
DEFAULT_OAUTH_SCOPES = ("https://www.googleapis.com/auth/cloud-platform",)

_MAX_REQUEST_RETRIES = 3
_INITIAL_RETRY_BACKOFF_SECONDS = 1.0
_LRO_POLL_INTERVALS_SECONDS = (2.0, 4.0, 8.0, 16.0, 16.0, 16.0)
_REQUEST_TIMEOUT_SECONDS = 30
_RETRIABLE_STATUS_CODES = (429, 500, 502, 503, 504)


class ContextStoreError(Exception):
    """Raised when a Context Store API call cannot be completed.

    `response_text` and `response_json` carry the raw server response (when
    the failure came from an HTTP response, not a client-side problem) so
    callers can inspect structured fields like the gRPC error envelope's
    `error.details[]` without re-parsing `str(self)`.
    """

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response_text: str | None = None,
        response_json: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.response_text = response_text
        self.response_json = response_json


class ContextStoreClient:
    """REST client for the Context Store API (autopush sandbox).

    Project and quota project are resolved from Application Default Credentials.
    """

    def __init__(self, location: str):
        self._location = location
        try:
            credentials, project = google.auth.default(scopes=DEFAULT_OAUTH_SCOPES)
        except google.auth.exceptions.DefaultCredentialsError as e:
            raise ContextStoreError(
                "No Application Default Credentials found. Run "
                "'gcloud auth application-default login' first."
            ) from e
        if not project:
            raise ContextStoreError(
                "ADC returned no default project. Set one with "
                "'gcloud auth application-default set-quota-project <PROJECT_ID>'."
            )
        self._project = project
        self._session = AuthorizedSession(credentials)
        self._session.headers["X-Goog-User-Project"] = (
            credentials.quota_project_id or project
        )

    def ensure_context_set_group(self, csg_id: str) -> str:
        """Return a CSG's full resource name, creating it if absent."""
        parent = f"projects/{self._project}/locations/{self._location}"
        csg_name = f"{parent}/contextSetGroups/{csg_id}"
        try:
            self._request("GET", f"{CONTEXT_STORE_ENDPOINT}/{API_VERSION}/{csg_name}")
            return csg_name
        except ContextStoreError as e:
            if e.status_code != 404:
                raise

        create_url = (
            f"{CONTEXT_STORE_ENDPOINT}/{API_VERSION}/{parent}/contextSetGroups"
            f"?context_set_group_id={csg_id}"
        )
        self._request_lro("POST", create_url, json_body={})
        return csg_name

    def delete_context_set_group(self, csg_name: str) -> None:
        """Delete a ContextSetGroup by full resource name. Blocks on LRO."""
        self._request_lro("DELETE", f"{CONTEXT_STORE_ENDPOINT}/{API_VERSION}/{csg_name}")

    def create_context_set(self, csg_name: str, cs_id: str, version: str) -> str:
        """Create an empty ContextSet at (cs_id, version); return its full
        resource name. Must be called before upload_context_set.

        Raises `ContextStoreError` with `status_code=409` if the version
        already exists — callers can match on status_code rather than message
        text.
        """
        url = (
            f"{CONTEXT_STORE_ENDPOINT}/{API_VERSION}/{csg_name}/contextSets"
            f"?context_set_id={cs_id}"
        )
        body = {"context_set_id": cs_id, "version": version}
        self._request("POST", url, json_body=body)
        return f"{csg_name}/contextSets/{cs_id}@{version}"

    def upload_context_set(self, resource_name: str, ctx: ContextSet) -> None:
        """Populate an existing ContextSet's body. The resource must already
        exist (call create_context_set first)."""
        url = f"{CONTEXT_STORE_ENDPOINT}/{API_VERSION}/{resource_name}:upload"
        body = {"context_json": ctx.model_dump_json(exclude_none=True)}
        self._request("POST", url, json_body=body)

    def download_context_set(self, resource_name: str) -> ContextSet:
        """Download and parse a ContextSet by full resource name."""
        url = f"{CONTEXT_STORE_ENDPOINT}/{API_VERSION}/{resource_name}:download"
        resp = self._request("POST", url, json_body={})
        raw = resp.get("contextJson")
        if raw is None:
            raise ContextStoreError(
                f"DownloadContextSet response missing contextJson: {resp}"
            )
        try:
            # Server normalizes proto-known fields to camelCase; ContextSet
            # model expects snake_case. Convert before validating.
            return ContextSet.model_validate(_snake_keys(json.loads(raw)))
        except Exception as e:
            raise ContextStoreError(
                f"Failed to parse downloaded ContextSet JSON: {e}"
            ) from e

    def delete_context_set(self, resource_name: str) -> None:
        """Delete a ContextSet by full resource name. Synchronous (no LRO)."""
        url = f"{CONTEXT_STORE_ENDPOINT}/{API_VERSION}/{resource_name}"
        self._request("DELETE", url)

    def _request(
        self,
        method: str,
        url: str,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        backoff = _INITIAL_RETRY_BACKOFF_SECONDS
        for attempt in range(_MAX_REQUEST_RETRIES + 1):
            logger.debug(
                "HTTP %s %s%s body=%s",
                method,
                url,
                f" (retry {attempt})" if attempt else "",
                json.dumps(json_body) if json_body is not None else "<none>",
            )
            try:
                response = self._session.request(
                    method, url, json=json_body, timeout=_REQUEST_TIMEOUT_SECONDS
                )
            except requests.RequestException as e:
                logger.debug("HTTP error (network): %s", e)
                if attempt < _MAX_REQUEST_RETRIES:
                    time.sleep(backoff)
                    backoff *= 2
                    continue
                raise ContextStoreError(f"Request failed: {e}") from e

            logger.debug(
                "HTTP %s response status=%s body=%s",
                method,
                response.status_code,
                response.text[:2000] if response.text else "<empty>",
            )
            if response.status_code < 400:
                try:
                    return response.json()
                except ValueError:
                    return {}

            try:
                response_json = response.json()
            except ValueError:
                response_json = None
            err = ContextStoreError(
                f"HTTP {response.status_code}: "
                f"{response.text.strip() or '(empty response body)'}",
                status_code=response.status_code,
                response_text=response.text,
                response_json=response_json,
            )
            if (
                response.status_code in _RETRIABLE_STATUS_CODES
                and attempt < _MAX_REQUEST_RETRIES
            ):
                time.sleep(backoff)
                backoff *= 2
                continue
            raise err

    def _request_lro(
        self,
        method: str,
        url: str,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Issue a request that returns an LRO; block until it completes."""
        op = self._request(method, url, json_body=json_body)
        op_name = op.get("name")
        if not op_name:
            raise ContextStoreError(
                f"{method} {url} returned no operation name: {op}"
            )
        return self._poll_lro(op_name)

    def _poll_lro(self, operation_name: str) -> dict[str, Any]:
        url = f"{CONTEXT_STORE_ENDPOINT}/{API_VERSION}/{operation_name}"
        for delay in _LRO_POLL_INTERVALS_SECONDS:
            time.sleep(delay)
            op = self._request("GET", url)
            if not op.get("done"):
                continue
            if "error" in op:
                err = op["error"]
                raise ContextStoreError(
                    f"LRO {operation_name} failed: [{err.get('code')}] "
                    f"{err.get('message', 'unknown LRO error')}"
                )
            return op.get("response", {})
        raise ContextStoreError(
            f"LRO {operation_name} did not complete within the timeout window"
        )


_CAMEL_RE = re.compile(r"(?<!^)(?=[A-Z])")


def _camel_to_snake(name: str) -> str:
    return _CAMEL_RE.sub("_", name).lower()


def _snake_keys(value: Any) -> Any:
    """Recursively convert camelCase dict keys to snake_case."""
    if isinstance(value, dict):
        return {_camel_to_snake(k): _snake_keys(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_snake_keys(v) for v in value]
    return value
