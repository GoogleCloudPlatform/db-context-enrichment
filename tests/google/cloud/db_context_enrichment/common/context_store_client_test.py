import json
from unittest.mock import MagicMock

import google.auth.exceptions
import pydantic
import pytest
import requests

from google.cloud.db_context_enrichment.common import context_store_client
from google.cloud.db_context_enrichment.common.context_store_client import (
    ContextStoreClient,
)
from google.cloud.db_context_enrichment.model.context import ContextSet


def _make_response(status_code: int, body=None):
    """Build a fake requests.Response with controllable status/body.

    For 4xx/5xx codes, `raise_for_status` is wired to raise
    `requests.HTTPError`, matching real `requests` behavior.
    """
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
    if status_code >= 400:
        response.raise_for_status.side_effect = requests.HTTPError(
            f"HTTP {status_code}", response=response
        )
    return response


@pytest.fixture
def client(monkeypatch):
    """Construct a client with mocked ADC + a controllable session."""
    fake_credentials = MagicMock()
    fake_credentials.quota_project_id = "test-project"
    fake_credentials.valid = True
    fake_credentials.token = "fake-token"

    monkeypatch.setattr(
        "google.auth.default",
        lambda scopes=None: (fake_credentials, None),
    )
    monkeypatch.setattr(
        context_store_client.auth_requests,
        "AuthorizedSession",
        lambda creds: MagicMock(),
    )
    monkeypatch.setattr(context_store_client.time, "sleep", lambda *a, **k: None)

    return ContextStoreClient()


_CSG_RESOURCE_NAME = (
    "projects/test-project/locations/us-central1/contextSetGroups/exp-1"
)


# === Constructor ===


def test_constructor_raises_when_adc_missing(monkeypatch):
    def raise_default(scopes=None):
        raise google.auth.exceptions.DefaultCredentialsError("no ADC")

    monkeypatch.setattr("google.auth.default", raise_default)

    with pytest.raises(RuntimeError, match="Application Default Credentials"):
        ContextStoreClient()


def test_constructor_omits_user_project_header_when_none_available(monkeypatch):
    fake_credentials = MagicMock()
    fake_credentials.quota_project_id = None
    monkeypatch.setattr(
        "google.auth.default",
        lambda scopes=None: (fake_credentials, None),
    )
    fake_session = MagicMock()
    fake_session.headers = {}
    monkeypatch.setattr(
        context_store_client.auth_requests,
        "AuthorizedSession",
        lambda creds: fake_session,
    )

    client = ContextStoreClient()

    assert "X-Goog-User-Project" not in client._session.headers


def test_constructor_falls_back_to_default_project_for_quota(monkeypatch):
    fake_credentials = MagicMock()
    fake_credentials.quota_project_id = None
    monkeypatch.setattr(
        "google.auth.default",
        lambda scopes=None: (fake_credentials, "adc-default-project"),
    )
    fake_session = MagicMock()
    fake_session.headers = {}
    monkeypatch.setattr(
        context_store_client.auth_requests,
        "AuthorizedSession",
        lambda creds: fake_session,
    )

    client = ContextStoreClient()

    assert client._session.headers["X-Goog-User-Project"] == "adc-default-project"


def test_constructor_sends_quota_project_header(monkeypatch):
    fake_credentials = MagicMock()
    fake_credentials.quota_project_id = "quota-proj"
    monkeypatch.setattr(
        "google.auth.default",
        lambda scopes=None: (fake_credentials, None),
    )
    session_mock = MagicMock()
    monkeypatch.setattr(
        context_store_client.auth_requests,
        "AuthorizedSession",
        lambda creds: session_mock,
    )
    monkeypatch.setattr(context_store_client.time, "sleep", lambda *a, **k: None)

    ContextStoreClient()

    session_mock.headers.__setitem__.assert_any_call(
        "X-Goog-User-Project", "quota-proj"
    )


def test_ensure_csg_uses_explicit_project_id(monkeypatch):
    """The method-level `project_id` shapes the built resource path,
    independent of the ADC quota project."""
    fake_credentials = MagicMock()
    fake_credentials.quota_project_id = "quota-proj"
    monkeypatch.setattr(
        "google.auth.default",
        lambda scopes=None: (fake_credentials, None),
    )
    session_mock = MagicMock()
    # ensure_csg's POST returns 409 (already exists) — treated as success.
    session_mock.request.return_value = _make_response(
        409, {"error": {"message": "exists"}}
    )
    monkeypatch.setattr(
        context_store_client.auth_requests,
        "AuthorizedSession",
        lambda creds: session_mock,
    )
    monkeypatch.setattr(context_store_client.time, "sleep", lambda *a, **k: None)

    client = ContextStoreClient()

    # Header still comes from ADC quota project.
    session_mock.headers.__setitem__.assert_any_call(
        "X-Goog-User-Project", "quota-proj"
    )
    # Resource paths use the method-level project_id.
    name = client.ensure_context_set_group("resource-proj", "g")
    assert name == "projects/resource-proj/locations/us-central1/contextSetGroups/g"


# === ensure_context_set_group ===


def test_ensure_csg_creates_when_missing(client):
    """Happy path: POST create returns an LRO op, we poll to done."""
    client._session.request.side_effect = [
        _make_response(200, {"name": "operations/op-123"}),
        _make_response(200, {"done": True, "response": {}}),
    ]

    name = client.ensure_context_set_group("test-project", "exp-1")

    assert name == _CSG_RESOURCE_NAME
    assert client._session.request.call_count == 2


def test_ensure_csg_lro_completes_synchronously(client):
    """When the create response already has done: true, we skip polling."""
    client._session.request.return_value = _make_response(
        200, {"name": "operations/op", "done": True, "response": {}}
    )

    name = client.ensure_context_set_group("test-project", "exp-1")

    assert name == _CSG_RESOURCE_NAME
    # 1 request total: POST returns an already-done op. No poll GETs.
    assert client._session.request.call_count == 1


def test_ensure_csg_polls_until_done(client):
    client._session.request.side_effect = [
        _make_response(200, {"name": "operations/op-2"}),
        _make_response(200, {"done": False}),
        _make_response(200, {"done": False}),
        _make_response(200, {"done": True, "response": {}}),
    ]

    name = client.ensure_context_set_group("test-project", "exp-1")

    assert name == _CSG_RESOURCE_NAME
    assert client._session.request.call_count == 4


def test_ensure_csg_lro_error_raises(client):
    client._session.request.side_effect = [
        _make_response(200, {"name": "operations/op"}),
        _make_response(200, {"done": True, "error": {"code": 5, "message": "boom"}}),
    ]

    with pytest.raises(RuntimeError, match="boom"):
        client.ensure_context_set_group("test-project", "exp-1")


def test_ensure_csg_lro_timeout(client):
    polls = [_make_response(200, {"done": False})] * len(
        context_store_client._LRO_POLL_INTERVALS_SECONDS
    )
    client._session.request.side_effect = [
        _make_response(200, {"name": "operations/op"}),
        *polls,
    ]

    with pytest.raises(TimeoutError, match="did not complete"):
        client.ensure_context_set_group("test-project", "exp-1")


def test_ensure_csg_treats_create_409_as_success(client):
    """A 409 on create (already exists / race) is treated as success."""
    client._session.request.return_value = _make_response(
        409, {"error": {"message": "already exists"}}
    )

    name = client.ensure_context_set_group("test-project", "exp-1")

    assert name == _CSG_RESOURCE_NAME
    assert client._session.request.call_count == 1


def test_ensure_csg_create_missing_operation_name_raises(client):
    client._session.request.return_value = _make_response(
        200, {}
    )  # Create succeeded but no op name.

    with pytest.raises(RuntimeError, match="no operation name"):
        client.ensure_context_set_group("test-project", "exp-1")


# === delete_context_set_group ===


def test_delete_context_set_group_success(client):
    client._session.request.side_effect = [
        _make_response(200, {"name": "operations/op-del"}),
        _make_response(200, {"done": True, "response": {}}),
    ]

    client.delete_context_set_group(_CSG_RESOURCE_NAME)

    assert client._session.request.call_count == 2
    first = client._session.request.call_args_list[0]
    assert first.args[0] == "DELETE"


def test_delete_context_set_group_missing_op_name_raises(client):
    client._session.request.return_value = _make_response(200, {})

    with pytest.raises(RuntimeError, match="no operation name"):
        client.delete_context_set_group(_CSG_RESOURCE_NAME)


def test_delete_context_set_group_treats_404_as_success(client):
    """Deleting a CSG that doesn't exist is idempotent."""
    client._session.request.return_value = _make_response(
        404, {"error": {"message": "not found"}}
    )

    # Should not raise.
    client.delete_context_set_group(_CSG_RESOURCE_NAME)


# === ensure_context_set ===


def test_ensure_cs_creates_when_missing(client):
    # ensure_cs internally calls ensure_csg first: POST csg (409 = already
    # exists), then POST cs (200 = created).
    client._session.request.side_effect = [
        _make_response(409, {"error": {"message": "csg exists"}}),  # ensure_csg
        _make_response(200, {}),  # POST cs
    ]

    name = client.ensure_context_set(
        "test-project", "exp-1", cs_id="autoctx", version="v1"
    )

    assert name == f"{_CSG_RESOURCE_NAME}/contextSets/autoctx@v1"
    assert client._session.request.call_count == 2
    # Last call is the CS POST.
    call = client._session.request.call_args
    assert call.args[0] == "POST"
    sent_url = call.args[1] if len(call.args) > 1 else call.kwargs["url"]
    assert sent_url.endswith(
        "/contextSetGroups/exp-1/contextSets?context_set_id=autoctx"
    )


def test_ensure_cs_treats_409_as_success(client):
    client._session.request.side_effect = [
        _make_response(409, {"error": {"message": "csg exists"}}),  # ensure_csg
        _make_response(409, {"error": {"message": "cs exists"}}),  # POST cs conflict
    ]

    name = client.ensure_context_set(
        "test-project", "exp-1", cs_id="autoctx", version="v1"
    )

    # 409 on the CS create is swallowed; we return the resource name.
    assert name == f"{_CSG_RESOURCE_NAME}/contextSets/autoctx@v1"


def test_ensure_cs_reraises_non_409_errors(client):
    client._session.request.side_effect = [
        _make_response(409, {"error": {"message": "csg exists"}}),  # ensure_csg
        _make_response(500, {"error": {"message": "boom"}}),  # POST cs errors
    ]

    with pytest.raises(requests.HTTPError) as excinfo:
        client.ensure_context_set(
            "test-project", "exp-1", cs_id="autoctx", version="v1"
        )

    assert excinfo.value.response.status_code == 500


# === upload_context_set ===


def test_upload_success(client):
    client._session.request.return_value = _make_response(200, {})

    resource = f"{_CSG_RESOURCE_NAME}/contextSets/autoctx@baseline"
    client.upload_context_set(resource, ContextSet())

    call = client._session.request.call_args
    sent_url = call.args[1] if len(call.args) > 1 else call.kwargs["url"]
    assert sent_url.endswith("/contextSets/autoctx@baseline:upload")
    assert "context_json" in call.kwargs["json"]


def test_upload_serializes_context_set_to_json_string(client):
    client._session.request.return_value = _make_response(200, {})

    resource = f"{_CSG_RESOURCE_NAME}/contextSets/autoctx@v1"
    client.upload_context_set(resource, ContextSet())

    body = client._session.request.call_args.kwargs["json"]
    parsed = json.loads(body["context_json"])
    assert isinstance(parsed, dict)


# === download_context_set ===


def test_download_success(client):
    encoded = ContextSet().model_dump_json(exclude_none=True)
    client._session.request.return_value = _make_response(200, {"contextJson": encoded})

    result = client.download_context_set(f"{_CSG_RESOURCE_NAME}/contextSets/autoctx@v1")

    assert isinstance(result, ContextSet)


def test_download_missing_field_raises(client):
    client._session.request.return_value = _make_response(200, {})

    with pytest.raises(ValueError, match="missing contextJson"):
        client.download_context_set(f"{_CSG_RESOURCE_NAME}/contextSets/autoctx@v1")


def test_download_invalid_inner_json_raises(client):
    client._session.request.return_value = _make_response(
        200, {"contextJson": "not a json blob"}
    )

    # json.loads raises JSONDecodeError (a ValueError subclass).
    with pytest.raises(ValueError):
        client.download_context_set(f"{_CSG_RESOURCE_NAME}/contextSets/autoctx@v1")


def test_download_invalid_context_set_shape_raises(client):
    # contextJson is valid JSON but doesn't match ContextSet schema.
    client._session.request.return_value = _make_response(
        200, {"contextJson": '{"templates": "not-a-list"}'}
    )

    with pytest.raises(pydantic.ValidationError):
        client.download_context_set(f"{_CSG_RESOURCE_NAME}/contextSets/autoctx@v1")


# === HTTP error surfaces ===


def test_authz_failures_surface_raw_403(client):
    client._session.request.return_value = _make_response(
        403, {"error": {"message": "denied"}}
    )

    with pytest.raises(requests.HTTPError) as excinfo:
        client.ensure_context_set_group("test-project", "exp-1")

    assert excinfo.value.response.status_code == 403
    assert excinfo.value.response.json() == {"error": {"message": "denied"}}


def test_non_retriable_4xx_raises_immediately(client):
    client._session.request.return_value = _make_response(
        400, {"error": {"message": "bad request"}}
    )

    with pytest.raises(requests.HTTPError) as excinfo:
        client.ensure_context_set_group("test-project", "exp-1")

    assert excinfo.value.response.status_code == 400
    assert client._session.request.call_count == 1


def test_error_exposes_raw_response_body(client):
    """Callers can read structured server fields via `e.response.json()`."""
    payload = {
        "error": {
            "code": 7,
            "message": "permission denied",
            "details": [{"@type": "type.googleapis.com/google.rpc.ErrorInfo"}],
        }
    }
    client._session.request.return_value = _make_response(403, payload)

    with pytest.raises(requests.HTTPError) as excinfo:
        client.ensure_context_set_group("test-project", "exp-1")

    assert excinfo.value.response.json() == payload


def test_error_exposes_raw_text_when_body_not_json(client):
    """When the body isn't JSON, `.response.text` still surfaces it."""
    client._session.request.return_value = _make_response(400, "plain text crash")

    with pytest.raises(requests.HTTPError) as excinfo:
        client.ensure_context_set_group("test-project", "exp-1")

    assert excinfo.value.response.text == "plain text crash"
