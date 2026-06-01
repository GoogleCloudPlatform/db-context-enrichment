import json
from unittest.mock import MagicMock

import google.auth.exceptions
import pytest
import requests

from google.cloud.db_context_enrichment.common import context_store_client
from google.cloud.db_context_enrichment.common.context_store_client import (
    ContextStoreClient,
    ContextStoreError,
)
from google.cloud.db_context_enrichment.model.context import ContextSet


def _make_response(status_code: int, body=None):
    """Build a fake requests.Response object with controllable status/body."""
    response = MagicMock(spec=requests.Response)
    response.status_code = status_code
    if body is None:
        response.content = b""
        response.text = ""
        response.json.side_effect = ValueError("no body")
    elif isinstance(body, str):
        response.content = body.encode()
        response.text = body
        response.json.side_effect = ValueError("not json")
    else:
        encoded = json.dumps(body)
        response.content = encoded.encode()
        response.text = encoded
        response.json.return_value = body
    return response


@pytest.fixture
def client(monkeypatch):
    """Construct a client with mocked ADC + a controllable session."""
    fake_credentials = MagicMock()
    fake_credentials.quota_project_id = None
    fake_credentials.valid = True
    fake_credentials.token = "fake-token"

    monkeypatch.setattr(
        "google.auth.default",
        lambda scopes=None: (fake_credentials, "test-project"),
    )
    monkeypatch.setattr(
        context_store_client, "AuthorizedSession", lambda creds: MagicMock()
    )
    monkeypatch.setattr(context_store_client.time, "sleep", lambda *a, **k: None)

    return ContextStoreClient(location="us-central1")


_CSG_NAME = "projects/test-project/locations/us-central1/contextSetGroups/exp-1"


# === Constructor ===


def test_constructor_raises_when_adc_missing(monkeypatch):
    def raise_default(scopes=None):
        raise google.auth.exceptions.DefaultCredentialsError("no ADC")

    monkeypatch.setattr("google.auth.default", raise_default)

    with pytest.raises(ContextStoreError, match="Application Default Credentials"):
        ContextStoreClient(location="us-central1")


def test_constructor_raises_when_no_project(monkeypatch):
    fake_credentials = MagicMock()
    fake_credentials.quota_project_id = None
    monkeypatch.setattr(
        "google.auth.default",
        lambda scopes=None: (fake_credentials, None),
    )
    monkeypatch.setattr(
        context_store_client, "AuthorizedSession", lambda creds: MagicMock()
    )

    with pytest.raises(ContextStoreError, match="no default project"):
        ContextStoreClient(location="us-central1")


def test_constructor_uses_quota_project_when_present(monkeypatch):
    fake_credentials = MagicMock()
    fake_credentials.quota_project_id = "quota-proj"
    monkeypatch.setattr(
        "google.auth.default",
        lambda scopes=None: (fake_credentials, "fallback-proj"),
    )
    session_mock = MagicMock()
    monkeypatch.setattr(
        context_store_client, "AuthorizedSession", lambda creds: session_mock
    )
    monkeypatch.setattr(context_store_client.time, "sleep", lambda *a, **k: None)

    ContextStoreClient(location="us-central1")

    session_mock.headers.__setitem__.assert_any_call(
        "X-Goog-User-Project", "quota-proj"
    )


# === ensure_context_set_group ===


def test_ensure_csg_returns_existing(client):
    client._session.request.return_value = _make_response(200, {"name": _CSG_NAME})

    name = client.ensure_context_set_group("exp-1")

    assert name == _CSG_NAME
    assert client._session.request.call_count == 1


def test_ensure_csg_creates_when_missing(client):
    client._session.request.side_effect = [
        _make_response(404, {"error": {"code": 404, "message": "not found"}}),
        _make_response(200, {"name": "operations/op-123"}),
        _make_response(200, {"done": True, "response": {}}),
    ]

    name = client.ensure_context_set_group("exp-1")

    assert name == _CSG_NAME
    assert client._session.request.call_count == 3


def test_ensure_csg_polls_until_done(client):
    client._session.request.side_effect = [
        _make_response(404, {}),
        _make_response(200, {"name": "operations/op-2"}),
        _make_response(200, {"done": False}),
        _make_response(200, {"done": False}),
        _make_response(200, {"done": True, "response": {}}),
    ]

    name = client.ensure_context_set_group("exp-1")

    assert name == _CSG_NAME
    assert client._session.request.call_count == 5


def test_ensure_csg_lro_error_raises(client):
    client._session.request.side_effect = [
        _make_response(404, {}),
        _make_response(200, {"name": "operations/op"}),
        _make_response(
            200, {"done": True, "error": {"code": 5, "message": "boom"}}
        ),
    ]

    with pytest.raises(ContextStoreError, match="boom"):
        client.ensure_context_set_group("exp-1")


def test_ensure_csg_lro_timeout(client):
    polls = [_make_response(200, {"done": False})] * len(
        context_store_client._LRO_POLL_INTERVALS_SECONDS
    )
    client._session.request.side_effect = [
        _make_response(404, {}),
        _make_response(200, {"name": "operations/op"}),
        *polls,
    ]

    with pytest.raises(ContextStoreError, match="did not complete"):
        client.ensure_context_set_group("exp-1")


def test_ensure_csg_create_missing_operation_name_raises(client):
    client._session.request.side_effect = [
        _make_response(404, {}),
        _make_response(200, {}),  # Create succeeded but no op name.
    ]

    with pytest.raises(ContextStoreError, match="no operation name"):
        client.ensure_context_set_group("exp-1")


# === delete_context_set_group ===


def test_delete_context_set_group_success(client):
    client._session.request.side_effect = [
        _make_response(200, {"name": "operations/op-del"}),
        _make_response(200, {"done": True, "response": {}}),
    ]

    client.delete_context_set_group(_CSG_NAME)

    assert client._session.request.call_count == 2
    first = client._session.request.call_args_list[0]
    assert first.args[0] == "DELETE"


def test_delete_context_set_group_missing_op_name_raises(client):
    client._session.request.return_value = _make_response(200, {})

    with pytest.raises(ContextStoreError, match="no operation name"):
        client.delete_context_set_group(_CSG_NAME)


# === create_context_set ===


def test_create_context_set_success(client):
    client._session.request.return_value = _make_response(200, {})

    name = client.create_context_set(
        csg_name=_CSG_NAME, cs_id="autoctx", version="baseline"
    )

    assert name == f"{_CSG_NAME}/contextSets/autoctx@baseline"
    call = client._session.request.call_args
    assert call.args[0] == "POST"
    sent_url = call.args[1] if len(call.args) > 1 else call.kwargs["url"]
    assert sent_url.endswith(
        "/contextSetGroups/exp-1/contextSets?context_set_id=autoctx"
    )


def test_create_context_set_409_surfaces_raw_409(client):
    client._session.request.return_value = _make_response(
        409, {"error": {"message": "exists"}}
    )

    with pytest.raises(ContextStoreError) as excinfo:
        client.create_context_set(
            csg_name=_CSG_NAME, cs_id="autoctx", version="v1"
        )

    # Raw status surfaces unchanged — callers match on status_code, and the
    # server's original error envelope is reachable via response_json.
    assert excinfo.value.status_code == 409
    assert excinfo.value.response_json == {"error": {"message": "exists"}}


# === upload_context_set ===


def test_upload_success(client):
    client._session.request.return_value = _make_response(200, {})

    resource = f"{_CSG_NAME}/contextSets/autoctx@baseline"
    client.upload_context_set(resource, ContextSet())

    call = client._session.request.call_args
    sent_url = call.args[1] if len(call.args) > 1 else call.kwargs["url"]
    assert sent_url.endswith("/contextSets/autoctx@baseline:upload")
    assert "context_json" in call.kwargs["json"]


def test_upload_serializes_context_set_to_json_string(client):
    client._session.request.return_value = _make_response(200, {})

    resource = f"{_CSG_NAME}/contextSets/autoctx@v1"
    client.upload_context_set(resource, ContextSet())

    body = client._session.request.call_args.kwargs["json"]
    parsed = json.loads(body["context_json"])
    assert isinstance(parsed, dict)


# === download_context_set ===


def test_download_success(client):
    encoded = ContextSet().model_dump_json(exclude_none=True)
    client._session.request.return_value = _make_response(
        200, {"contextJson": encoded}
    )

    result = client.download_context_set(f"{_CSG_NAME}/contextSets/autoctx@v1")

    assert isinstance(result, ContextSet)


def test_download_missing_field_raises(client):
    client._session.request.return_value = _make_response(200, {})

    with pytest.raises(ContextStoreError, match="missing contextJson"):
        client.download_context_set(f"{_CSG_NAME}/contextSets/autoctx@v1")


def test_download_invalid_inner_json_raises(client):
    client._session.request.return_value = _make_response(
        200, {"contextJson": "not a json blob"}
    )

    with pytest.raises(ContextStoreError, match="Failed to parse"):
        client.download_context_set(f"{_CSG_NAME}/contextSets/autoctx@v1")


# === delete_context_set ===


def test_delete_context_set_success(client):
    client._session.request.return_value = _make_response(200, {})

    client.delete_context_set(f"{_CSG_NAME}/contextSets/autoctx@v1")

    call = client._session.request.call_args
    assert call.args[0] == "DELETE"
    sent_url = call.args[1] if len(call.args) > 1 else call.kwargs["url"]
    assert sent_url.endswith("/contextSets/autoctx@v1")


def test_delete_context_set_404_raises(client):
    client._session.request.return_value = _make_response(
        404, {"error": {"message": "not found"}}
    )

    with pytest.raises(ContextStoreError) as excinfo:
        client.delete_context_set(f"{_CSG_NAME}/contextSets/autoctx@v1")

    assert excinfo.value.status_code == 404


# === Error handling and retry ===


def test_authz_failures_surface_raw_403(client):
    client._session.request.return_value = _make_response(
        403, {"error": {"message": "denied"}}
    )

    with pytest.raises(ContextStoreError) as excinfo:
        client.ensure_context_set_group("exp-1")

    assert excinfo.value.status_code == 403
    assert excinfo.value.response_json == {"error": {"message": "denied"}}


def test_429_retries_then_succeeds(client):
    client._session.request.side_effect = [
        _make_response(429, "rate limit"),
        _make_response(429, "rate limit"),
        _make_response(200, {"name": _CSG_NAME}),
    ]

    name = client.ensure_context_set_group("exp-1")

    assert name == _CSG_NAME
    assert client._session.request.call_count == 3


def test_503_retries_then_succeeds(client):
    client._session.request.side_effect = [
        _make_response(503, "unavailable"),
        _make_response(200, {"name": _CSG_NAME}),
    ]

    name = client.ensure_context_set_group("exp-1")

    assert name == _CSG_NAME
    assert client._session.request.call_count == 2


def test_non_retriable_4xx_raises_immediately(client):
    client._session.request.return_value = _make_response(
        400, {"error": {"message": "bad request"}}
    )

    with pytest.raises(ContextStoreError) as excinfo:
        client.ensure_context_set_group("exp-1")

    assert excinfo.value.status_code == 400
    assert client._session.request.call_count == 1


def test_error_exposes_raw_response_body(client):
    """Agents/callers can read structured server fields without regex on str(e)."""
    payload = {
        "error": {
            "code": 7,
            "message": "permission denied",
            "details": [{"@type": "type.googleapis.com/google.rpc.ErrorInfo"}],
        }
    }
    client._session.request.return_value = _make_response(403, payload)

    with pytest.raises(ContextStoreError) as excinfo:
        client.ensure_context_set_group("exp-1")

    assert excinfo.value.response_json == payload
    assert excinfo.value.response_text  # raw JSON string also available


def test_error_response_json_none_for_non_json_body(client):
    client._session.request.return_value = _make_response(500, "plain text crash")

    with pytest.raises(ContextStoreError) as excinfo:
        client.ensure_context_set_group("exp-1")

    assert excinfo.value.response_json is None
    assert excinfo.value.response_text == "plain text crash"


def test_network_error_retries(client):
    client._session.request.side_effect = [
        requests.ConnectionError("conn refused"),
        _make_response(200, {"name": _CSG_NAME}),
    ]

    name = client.ensure_context_set_group("exp-1")

    assert name == _CSG_NAME
    assert client._session.request.call_count == 2


def test_persistent_429_exhausts_retries(client):
    client._session.request.return_value = _make_response(429, "rate limit")

    with pytest.raises(ContextStoreError) as excinfo:
        client.ensure_context_set_group("exp-1")

    assert excinfo.value.status_code == 429
    assert client._session.request.call_count == 4  # 1 initial + 3 retries
