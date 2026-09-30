import asyncio

import httpx
import pytest
import respx
from starlette.applications import Starlette
from starlette.testclient import TestClient

from mcp_connector import config
from mcp_connector.downloads import store as dl_store
from mcp_connector.downloads import upload, upload_route
from mcp_connector.oauth import store as oauth_store_module

BASE = "http://nc.test"
KEY = bytes(range(32))
ENV = {
    config.ENV_APP_ID: "mcp_connector",
    config.ENV_APP_SECRET: "app-secret-test",
    config.ENV_APP_VERSION: "0.3.2",
    config.ENV_NEXTCLOUD_URL: BASE,
}
ROOT = f"{BASE}/remote.php/dav/files/alice"
TARGET = "/Clienti/Rossi/Preventivo à #1.docx"
FILE_URL = f"{ROOT}/Clienti/Rossi/Preventivo%20%C3%A0%20%231.docx"


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

    app = Starlette(routes=upload_route.upload_routes(ENV, oauth_store=provider, tickets=tickets))
    return oauth, tickets, TestClient(app)


def issue(tickets, path=TARGET):
    token, _ = run(
        tickets.issue(
            auth_id="auth-1",
            nc_user="alice",
            path=upload.upload_ticket_path(path),
            name=path.rsplit("/", 1)[-1],
            content_type="",
            size=0,
            ttl_seconds=1800,
        )
    )
    return token


def folders_ok():
    respx.route(method="MKCOL", url__startswith=ROOT).mock(return_value=httpx.Response(405))


def test_a_completed_upload_creates_the_file_and_burns_the_link(world):
    _, tickets, client = world
    token = issue(tickets)
    with respx.mock:
        folders_ok()
        put = respx.put(FILE_URL).mock(return_value=httpx.Response(201))
        answer = client.put(f"/ul/{token}", content=b"x" * 1000)
    assert answer.status_code == 201
    assert answer.json() == {"path": TARGET, "size": 1000}
    assert put.calls.last.request.headers["If-None-Match"] == "*"
    assert run(tickets.peek(token)) is None
    again = client.put(f"/ul/{token}", content=b"x")
    assert (again.status_code, again.text) == (404, "Not found")


def test_unknown_malformed_and_download_tickets_get_the_same_404(world):
    _, tickets, client = world
    dl_token, _ = run(
        tickets.issue(
            auth_id="auth-1",
            nc_user="alice",
            path="/Docs/a.pdf",
            name="a.pdf",
            content_type="application/pdf",
            size=1,
            ttl_seconds=600,
        )
    )
    for path in ("/ul/" + "A" * 43, "/ul/short", f"/ul/{dl_token}"):
        answer = client.put(path, content=b"x")
        assert (answer.status_code, answer.text) == (404, "Not found")
    assert run(tickets.peek(dl_token)) is not None


def test_a_file_that_appeared_meanwhile_is_409_exists_and_burns(world):
    _, tickets, client = world
    token = issue(tickets)
    with respx.mock:
        folders_ok()
        respx.put(FILE_URL).mock(return_value=httpx.Response(412))
        answer = client.put(f"/ul/{token}", content=b"x")
    assert answer.status_code == 409
    assert answer.json()["error"] == "exists"
    assert run(tickets.peek(token)) is None


def test_a_folder_that_is_a_file_is_409_conflict(world):
    _, tickets, client = world
    token = issue(tickets)
    with respx.mock:
        folders_ok()
        respx.put(FILE_URL).mock(return_value=httpx.Response(409))
        answer = client.put(f"/ul/{token}", content=b"x")
    assert answer.status_code == 409
    assert answer.json()["error"] == "conflict"


def test_declared_size_over_the_limit_is_413_before_claiming(world):
    _, tickets, client = world
    token = issue(tickets)
    answer = client.put(
        f"/ul/{token}", content=b"x", headers={"Content-Length": str(upload.MAX_UPLOAD_BYTES + 1)}
    )
    assert answer.status_code == 413
    assert run(tickets.peek(token)) is not None


def test_real_size_over_the_limit_is_413_and_releases(world, monkeypatch):
    _, tickets, client = world
    monkeypatch.setattr(upload_route, "MAX_UPLOAD_BYTES", 5)
    token = issue(tickets)

    def body():
        yield b"123"
        yield b"456"

    with respx.mock:
        folders_ok()

        async def consume(request):
            await request.aread()
            return httpx.Response(201)

        respx.put(FILE_URL).mock(side_effect=consume)
        answer = client.put(f"/ul/{token}", content=body())
    assert answer.status_code == 413
    assert run(tickets.peek(token)) is not None


def test_nextcloud_down_is_502_and_releases(world):
    _, tickets, client = world
    token = issue(tickets)
    with respx.mock:
        folders_ok()
        respx.put(FILE_URL).mock(side_effect=httpx.ConnectError("down"))
        answer = client.put(f"/ul/{token}", content=b"x")
    assert answer.status_code == 502
    assert run(tickets.peek(token)) is not None


def test_rejected_credentials_are_404_and_burn(world):
    _, tickets, client = world
    token = issue(tickets)
    with respx.mock:
        respx.route(method="MKCOL", url__startswith=ROOT).mock(return_value=httpx.Response(401))
        answer = client.put(f"/ul/{token}", content=b"x")
    assert (answer.status_code, answer.text) == (404, "Not found")
    assert run(tickets.peek(token)) is None


def test_revoked_connection_is_404(world):
    oauth, tickets, client = world
    token = issue(tickets)
    run(oauth.revoke_authorization("auth-1"))
    answer = client.put(f"/ul/{token}", content=b"x")
    assert (answer.status_code, answer.text) == (404, "Not found")


def test_the_log_masks_the_token(world, caplog):
    _, tickets, client = world
    token = issue(tickets)
    # Scoped to our own logger, like test_the_delivery_log_names_user_and_file_but_never_the_
    # full_token in test_olivia_download_route.py: an unscoped caplog.at_level("INFO") also
    # captures the test client's own httpx2 request log, which logs the raw request URL
    # (token and all) and would make this assertion fail on infrastructure noise, not on the
    # route's own logging.
    with respx.mock, caplog.at_level("INFO", logger="mcp_connector.downloads.upload_route"):
        folders_ok()
        respx.put(FILE_URL).mock(return_value=httpx.Response(201))
        client.put(f"/ul/{token}", content=b"x")
    assert f"link={token[:4]}…" in caplog.text
    assert token not in caplog.text


def test_a_client_that_disconnects_mid_upload_leaves_the_link_usable(world):
    _, tickets, client = world
    token = issue(tickets)
    messages = [
        {"type": "http.request", "body": b"abc", "more_body": True},
        {"type": "http.disconnect"},
    ]
    sent = []

    async def receive():
        return messages.pop(0) if messages else {"type": "http.disconnect"}

    async def send(message):
        sent.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "PUT",
        "scheme": "http",
        "path": f"/ul/{token}",
        "raw_path": f"/ul/{token}".encode(),
        "query_string": b"",
        "root_path": "",
        "headers": [],
        "server": ("test", 80),
        "client": ("1.2.3.4", 5),
    }
    with respx.mock:
        folders_ok()

        async def consume(request):
            await request.aread()
            return httpx.Response(201)

        respx.put(FILE_URL).mock(side_effect=consume)
        run(client.app(scope, receive, send))
    assert sent[0]["status"] in (400, 502)
    assert run(tickets.peek(token)) is not None
