import asyncio

import httpx
import pytest
import respx
from starlette.applications import Starlette
from starlette.testclient import TestClient

from mcp_connector import config
from mcp_connector.downloads import route as dl_route
from mcp_connector.downloads import store as dl_store
from mcp_connector.oauth import store as oauth_store_module

BASE = "http://nc.test"
KEY = bytes(range(32))
ENV = {
    config.ENV_APP_ID: "mcp_connector",
    config.ENV_APP_SECRET: "app-secret-test",
    config.ENV_APP_VERSION: "0.3.2",
    config.ENV_NEXTCLOUD_URL: BASE,
}
FILE_URL = f"{BASE}/remote.php/dav/files/alice/Docs/Relazione%20%C3%A0.pdf"
BODY = b"%PDF-1.7 " + b"y" * 100_000


def run(work):
    return asyncio.run(work)


@pytest.fixture
def world(tmp_path):
    oauth = oauth_store_module.OAuthStore(tmp_path / oauth_store_module.STORE_FILENAME, KEY)
    run(oauth.save_client("client-1", metadata_json='{"client_id": "client-1"}'))
    run(
        oauth.create_authorization(
            "auth-1",
            client_id="client-1",
            nc_user="alice",
            nc_account_id="alice",
            app_password="app-password-test",
            scopes="nextcloud",
            resource="https://nc.example/exapps/x/mcp",
        )
    )
    tickets = dl_store.TicketStore(tmp_path / dl_store.TICKETS_FILENAME)

    async def provider():
        return oauth

    app = Starlette(routes=dl_route.download_routes(ENV, oauth_store=provider, tickets=tickets))
    return oauth, tickets, TestClient(app)


def issue(tickets, *, auth_id="auth-1", name="Relazione à.pdf"):
    token, _ = run(
        tickets.issue(
            auth_id=auth_id,
            nc_user="alice",
            path="/Docs/Relazione à.pdf",
            name=name,
            content_type="application/pdf",
            size=len(BODY),
            ttl_seconds=600,
        )
    )
    return token


def test_unknown_and_malformed_tokens_get_the_same_404(world):
    _, _, client = world
    a = client.get("/dl/" + "A" * 43)
    b = client.get("/dl/short")
    assert (a.status_code, a.text) == (404, "Not found")
    assert (b.status_code, b.text) == (404, "Not found")


def test_get_streams_once_then_404(world):
    _, tickets, client = world
    token = issue(tickets)
    with respx.mock:
        respx.get(FILE_URL).mock(return_value=httpx.Response(200, content=BODY))
        first = client.get(f"/dl/{token}")
    assert first.status_code == 200
    assert first.content == BODY
    assert first.headers["content-type"] == "application/pdf"
    assert first.headers["cache-control"] == "no-store"
    assert first.headers["x-content-type-options"] == "nosniff"
    disposition = first.headers["content-disposition"]
    assert disposition.startswith('attachment; filename="Relazione .pdf"')
    assert "filename*=UTF-8''Relazione%20%C3%A0.pdf" in disposition
    assert client.get(f"/dl/{token}").status_code == 404


def test_head_does_not_consume(world):
    _, tickets, client = world
    token = issue(tickets)
    head = client.head(f"/dl/{token}")
    assert head.status_code == 200
    assert head.headers["content-length"] == str(len(BODY))
    assert run(tickets.peek(token)) is not None


def test_revoked_connection_gets_404(world):
    oauth, tickets, client = world
    token = issue(tickets)
    run(oauth.revoke_authorization("auth-1"))
    assert client.get(f"/dl/{token}").status_code == 404


def test_paused_account_gets_404(world):
    oauth, tickets, client = world
    token = issue(tickets)
    run(oauth.set_access("alice", disabled=True))
    assert client.get(f"/dl/{token}").status_code == 404


def test_file_gone_gets_404_and_keeps_the_ticket_usable(world):
    _, tickets, client = world
    token = issue(tickets)
    with respx.mock:
        respx.get(FILE_URL).mock(return_value=httpx.Response(404))
        assert client.get(f"/dl/{token}").status_code == 404
    assert run(tickets.peek(token)) is not None


def test_nextcloud_down_gets_502(world):
    _, tickets, client = world
    token = issue(tickets)
    with respx.mock:
        respx.get(FILE_URL).mock(return_value=httpx.Response(503))
        assert client.get(f"/dl/{token}").status_code == 502
    assert run(tickets.peek(token)) is not None


class _Broken(httpx.AsyncByteStream):
    async def __aiter__(self):
        yield b"%PDF-partial"
        raise httpx.ReadError("connection reset")


def test_interrupted_download_releases_the_ticket(world):
    _, tickets, client = world
    token = issue(tickets)
    with respx.mock:
        respx.get(FILE_URL).mock(return_value=httpx.Response(200, stream=_Broken()))
        with pytest.raises(Exception):  # noqa: B017, PT011 - transport failure, any raise counts
            client.get(f"/dl/{token}")
    assert run(tickets.peek(token)) is not None
