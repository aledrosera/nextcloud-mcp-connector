"""``deps.resolve_ticket_owner``: who a download link acts for (fork olivia).

Reuses the ``FakeContext``/``identity`` shape of ``tests/unit/test_oauth_credentials.py``
so a download link is resolved from the same two sources ``resolve_credentials`` already
reads: the OAuth identity the transport boundary left in the request state, or the AppAPI
impersonation header. A third case, Basic credentials of the HTTP passthrough mode with no
identity at all, is refused: that deployment has no connection a download route could later
rebuild credentials from.
"""

import base64
from collections.abc import Mapping
from typing import Any

import pytest
from starlette.requests import Request

from mcp_connector import config, deps
from mcp_connector.errors import ToolError
from mcp_connector.oauth.verifier import (
    CREDENTIAL_APP_PASSWORD,
    CREDENTIAL_IMPERSONATE,
    OAUTH_STATE_ATTR,
    OAuthIdentity,
)

APP_ID = "mcp_connector"
APP_SECRET = "app-secret-test"
APP_VERSION = "0.1.0"
BASE_URL = "http://nc.test"
NC_USER = "alice"
APP_PASSWORD = "aaaaa-bbbbb-ccccc-ddddd-eeeee"
AUTH_ID = "the-flow-this-authorization-was-born-in"
CLIENT_ID = "9d0f8f1a-0b3c-4a0e-9f4c-000000000001"


class FakeRequestContext:
    def __init__(self, request: Request) -> None:
        self.request = request


class FakeContext:
    """The context object of a tool call, in the two shapes ``deps`` reads it in."""

    def __init__(
        self,
        headers: Mapping[str, str] | None = None,
        identity: OAuthIdentity | None = None,
    ) -> None:
        self.headers = headers
        request = Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/mcp",
                "query_string": b"",
                "headers": [
                    (key.lower().encode(), value.encode()) for key, value in (headers or {}).items()
                ],
            }
        )
        if identity is not None:
            setattr(request.state, OAUTH_STATE_ATTR, identity)
        self.request_context = FakeRequestContext(request)


def identity(**fields: Any) -> OAuthIdentity:
    values: dict[str, Any] = {
        "nc_user": NC_USER,
        "principal": NC_USER,
        "app_password": APP_PASSWORD,
        "auth_id": AUTH_ID,
        "client_id": CLIENT_ID,
    }
    values.update(fields)
    return OAuthIdentity(**values)


def appapi_headers(user: str = "", secret: str = APP_SECRET) -> dict[str, str]:
    token = base64.b64encode(f"{user}:{secret}".encode()).decode()
    return {
        "EX-APP-ID": APP_ID,
        "EX-APP-VERSION": APP_VERSION,
        "AUTHORIZATION-APP-API": token,
    }


def basic_headers(user: str = NC_USER, secret: str = APP_PASSWORD) -> dict[str, str]:
    token = base64.b64encode(f"{user}:{secret}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


@pytest.fixture
def exapp_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(config.ENV_APP_ID, APP_ID)
    monkeypatch.setenv(config.ENV_APP_SECRET, APP_SECRET)
    monkeypatch.setenv(config.ENV_APP_VERSION, APP_VERSION)
    monkeypatch.setenv(config.ENV_NEXTCLOUD_URL, BASE_URL)
    monkeypatch.delenv(config.ENV_STATIC_BEARER, raising=False)
    monkeypatch.delenv(config.ENV_APP_PASSWORD, raising=False)


@pytest.fixture
def passthrough_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """No AppAPI, no static bearer, no OAuth: plain HTTP passthrough."""
    for name in (config.ENV_APP_ID, config.ENV_APP_SECRET, config.ENV_STATIC_BEARER):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.delenv(config.ENV_AUTH_MODE, raising=False)
    monkeypatch.setenv(config.ENV_URL, BASE_URL)


def test_an_oauth_identity_with_an_app_password_carries_its_authorization_id(
    exapp_env: None,
) -> None:
    owner = deps.resolve_ticket_owner(
        FakeContext(headers=appapi_headers(user=""), identity=identity())
    )

    assert owner.auth_id == AUTH_ID
    assert owner.nc_user == NC_USER


def test_an_appapi_impersonation_identity_carries_no_authorization_id(exapp_env: None) -> None:
    owner = deps.resolve_ticket_owner(
        FakeContext(
            headers=appapi_headers(user=""),
            identity=identity(app_password="", auth_id="", credential=CREDENTIAL_IMPERSONATE),
        )
    )

    assert owner.auth_id is None
    assert owner.nc_user == NC_USER


def test_basic_credentials_without_an_identity_are_refused(passthrough_env: None) -> None:
    with pytest.raises(ToolError, match="ExApp"):
        deps.resolve_ticket_owner(FakeContext(headers=basic_headers()))


def test_an_app_password_identity_without_an_authorization_id_is_refused(exapp_env: None) -> None:
    """An app-password identity with no ``auth_id`` has no connection a route could later

    rebuild credentials from by id, and it is not an impersonation identity either, so it
    must not fall back to impersonating the Nextcloud user by name (that would issue a link
    for a connection this deployment cannot honour again).
    """
    with pytest.raises(ToolError) as excinfo:
        deps.resolve_ticket_owner(
            FakeContext(
                headers=appapi_headers(user=""),
                identity=identity(auth_id="", credential=CREDENTIAL_APP_PASSWORD),
            )
        )

    assert excinfo.value.message == "This connection cannot issue download links."
    assert excinfo.value.hint == "Reconnect the connector in Claude and try again."
