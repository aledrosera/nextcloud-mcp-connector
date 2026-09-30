import asyncio
import base64
import logging

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


# --- fix round 1 -------------------------------------------------------------------------


@pytest.mark.parametrize(
    "make_unusable",
    [
        pytest.param(
            lambda oauth, tickets, token: run(oauth.revoke_authorization("auth-1")), id="revoked"
        ),
        pytest.param(
            lambda oauth, tickets, token: run(oauth.set_access("alice", disabled=True)),
            id="suspended",
        ),
    ],
)
def test_revoked_or_suspended_links_answer_exactly_not_found(world, make_unusable):
    oauth, tickets, client = world
    token = issue(tickets)
    make_unusable(oauth, tickets, token)
    response = client.get(f"/dl/{token}")
    assert (response.status_code, response.text) == (404, "Not found")


def test_a_gone_file_answers_exactly_not_found(world):
    _, tickets, client = world
    token = issue(tickets)
    with respx.mock:
        respx.get(FILE_URL).mock(return_value=httpx.Response(404))
        response = client.get(f"/dl/{token}")
    assert (response.status_code, response.text) == (404, "Not found")


@pytest.mark.parametrize("status", [401, 403])
def test_nextcloud_rejecting_the_credentials_burns_the_ticket(world, status):
    """A rejected credential (401/403) is not released for a retry: it would only resend the

    same rejected credential and feed Nextcloud's failed-login counter, so the ticket is
    burned instead and a second GET on the same token is a plain 404.
    """
    _, tickets, client = world
    token = issue(tickets)
    with respx.mock:
        respx.get(FILE_URL).mock(return_value=httpx.Response(status))
        response = client.get(f"/dl/{token}")
    assert (response.status_code, response.text) == (404, "Not found")
    assert run(tickets.peek(token)) is None
    assert client.get(f"/dl/{token}").status_code == 404


@pytest.mark.parametrize(
    "make_ticket_unusable",
    [
        pytest.param(None, id="unknown_token"),
        pytest.param("claim", id="in_progress"),
        pytest.param("revoke", id="revoked_connection"),
    ],
)
def test_head_answers_404_with_an_empty_body(world, make_ticket_unusable):
    oauth, tickets, client = world
    if make_ticket_unusable is None:
        token = "A" * 43
    else:
        token = issue(tickets)
        if make_ticket_unusable == "claim":
            run(tickets.claim(token))
        elif make_ticket_unusable == "revoke":
            run(oauth.revoke_authorization("auth-1"))
    response = client.head(f"/dl/{token}")
    assert response.status_code == 404
    assert response.content == b""


def test_appapi_impersonation_sends_the_headers_of_the_ticket_owner(world):
    _, tickets, client = world
    token, _ = run(
        tickets.issue(
            auth_id=None,
            nc_user="alice",
            path="/Docs/Relazione à.pdf",
            name="Relazione à.pdf",
            content_type="application/pdf",
            size=len(BODY),
            ttl_seconds=600,
        )
    )
    captured: dict[str, httpx.Headers] = {}

    def responder(request: httpx.Request) -> httpx.Response:
        captured["headers"] = request.headers
        return httpx.Response(200, content=BODY)

    with respx.mock:
        respx.get(FILE_URL).mock(side_effect=responder)
        response = client.get(f"/dl/{token}")

    assert response.status_code == 200
    assert response.content == BODY
    headers = captured["headers"]
    assert headers["EX-APP-ID"] == ENV[config.ENV_APP_ID]
    assert headers["EX-APP-VERSION"] == ENV[config.ENV_APP_VERSION]
    token_b64 = headers["AUTHORIZATION-APP-API"]
    assert base64.b64decode(token_b64).decode() == f"alice:{ENV[config.ENV_APP_SECRET]}"


def test_the_delivery_log_names_user_and_file_but_never_the_full_token(world, caplog):
    _, tickets, client = world
    token = issue(tickets)
    with caplog.at_level(logging.INFO, logger="mcp_connector.downloads.route"), respx.mock:
        respx.get(FILE_URL).mock(return_value=httpx.Response(200, content=BODY))
        response = client.get(f"/dl/{token}")
    assert response.status_code == 200
    assert "alice" in caplog.text
    assert "Relazione à.pdf" in caplog.text
    assert f"{token[:4]}…" in caplog.text
    assert token not in caplog.text


def test_missing_content_length_is_not_replaced_by_the_ticket_size(world):
    _, tickets, client = world
    token = issue(tickets)

    class _Whole(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield BODY

    with respx.mock:
        respx.get(FILE_URL).mock(return_value=httpx.Response(200, stream=_Whole()))
        response = client.get(f"/dl/{token}")
    assert response.status_code == 200
    assert "content-length" not in response.headers
    assert response.content == BODY


def test_control_characters_in_the_filename_are_stripped_from_the_fallback(world):
    _, tickets, client = world
    token = issue(tickets, name="a\x01b.pdf")
    with respx.mock:
        respx.get(FILE_URL).mock(return_value=httpx.Response(200, content=BODY))
        response = client.get(f"/dl/{token}")
    assert response.status_code == 200
    disposition = response.headers["content-disposition"]
    assert 'filename="ab.pdf"' in disposition
    assert "filename*=UTF-8''a%01b.pdf" in disposition


def test_an_upload_ticket_on_the_download_route_is_404_and_stays_usable(world):
    _, tickets, client = world
    token, _ = run(
        tickets.issue(
            auth_id="auth-1",
            nc_user="alice",
            path="upload:/Docs/a.pdf",
            name="a.pdf",
            content_type="",
            size=0,
            ttl_seconds=600,
        )
    )
    head = client.head(f"/dl/{token}")
    assert (head.status_code, head.content) == (404, b"")
    get = client.get(f"/dl/{token}")
    assert (get.status_code, get.text) == (404, "Not found")
    assert run(tickets.peek(token)) is not None


def test_an_unexpected_error_after_claim_fails_hard_and_returns_the_ticket(tmp_path):
    tickets = dl_store.TicketStore(tmp_path / dl_store.TICKETS_FILENAME)
    token = issue(tickets)

    async def broken_provider():
        raise RuntimeError("boom")

    app = Starlette(
        routes=dl_route.download_routes(ENV, oauth_store=broken_provider, tickets=tickets)
    )
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get(f"/dl/{token}")

    assert response.status_code == 500
    assert run(tickets.peek(token)) is not None
