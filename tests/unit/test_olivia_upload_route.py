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


def _raw_scope(path):
    # Twin of the scope built inline by the disconnect test below: raw ASGI in, so the
    # fake ``receive`` can hand the route more than one ``http.request`` message and we can
    # assert on exactly how many of them the route consumed.
    return {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "PUT",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "root_path": "",
        "headers": [],
        "server": ("test", 80),
        "client": ("1.2.3.4", 5),
    }


def _receive_from(messages):
    # Raises instead of returning a synthetic disconnect once ``messages`` is empty, so a
    # route that asks for one more chunk than it should is caught as a hard failure, not
    # silently answered with an ASGI message the real server would never send here.
    async def receive():
        if not messages:
            raise AssertionError("route asked for more body than the client sent")
        return messages.pop(0)

    return receive


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


def test_the_client_declared_content_length_is_forwarded_to_nextcloud(world):
    # H1 (fix round 1): a truncated body must be caught by Nextcloud's own length check,
    # not just accepted as a shorter-than-promised chunked stream.
    _, tickets, client = world
    token = issue(tickets)
    with respx.mock:
        folders_ok()
        put = respx.put(FILE_URL).mock(return_value=httpx.Response(201))
        answer = client.put(f"/ul/{token}", content=b"x" * 1000)
    assert answer.status_code == 201
    assert put.calls.last.request.headers["Content-Length"] == "1000"


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
    assert run(tickets.peek(token)) is None


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
    assert run(tickets.peek(token)) is not None


def test_suspended_account_is_404_and_stays_usable(world):
    oauth, tickets, client = world
    token = issue(tickets)
    run(oauth.set_access("alice", disabled=True))
    answer = client.put(f"/ul/{token}", content=b"x")
    assert (answer.status_code, answer.text) == (404, "Not found")
    assert run(tickets.peek(token)) is not None


def test_the_log_masks_the_token(world, caplog):
    _, tickets, client = world
    token = issue(tickets)
    # Scoped to our own package, like test_the_delivery_log_names_user_and_file_but_never_the_
    # full_token in test_olivia_download_route.py: an unscoped caplog.at_level("INFO") also
    # captures the test client's own httpx request log, which logs the raw request URL
    # (token and all) and would make this assertion fail on infrastructure noise, not on the
    # route's own logging.
    with respx.mock, caplog.at_level("INFO", logger="mcp_connector"):
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
    # httpx re-raises ClientDisconnect unwrapped (verified by the round 1 review), so the
    # route's own ClientDisconnect branch always answers, never the generic httpx.HTTPError
    # one.
    assert sent[0]["status"] == 400
    assert run(tickets.peek(token)) is not None


# --- fix round 1, I2: every row of the brief's outcome table, MKCOL and PUT mapped apart --
# --- fix round 2, I1/M2: 401 split from 403 (403 is now its own "forbidden" answer, not the
# --- same 404 as an unknown link), and the PUT's own 400 ("invalid_name") added --


@pytest.mark.parametrize(
    ("kind", "status", "expected_status", "expected_error", "ticket_gone"),
    [
        pytest.param("put", 200, 502, "precondition_ignored", True, id="put_200_ignored"),
        pytest.param("put", 204, 502, "precondition_ignored", True, id="put_204_ignored"),
        pytest.param("put", 413, 413, None, False, id="put_413_stays_usable"),
        pytest.param("put", 404, 409, "conflict", True, id="put_404_conflict"),
        pytest.param("put", 409, 409, "conflict", True, id="put_409_conflict"),
        pytest.param("put", 405, 409, "exists", True, id="put_405_exists"),
        pytest.param("put", 412, 409, "exists", True, id="put_412_exists"),
        pytest.param("put", 400, 400, "invalid_name", True, id="put_400_invalid_name"),
        pytest.param("put", 401, 404, None, True, id="put_401_not_found"),
        pytest.param("put", 403, 403, "forbidden", True, id="put_403_forbidden"),
        pytest.param("put", 500, 502, None, False, id="put_500_stays_usable"),
        pytest.param("mkcol", 401, 404, None, True, id="mkcol_401_not_found"),
        pytest.param("mkcol", 403, 403, "forbidden", True, id="mkcol_403_forbidden"),
        pytest.param("mkcol", 409, 409, "conflict", True, id="mkcol_409_conflict"),
        pytest.param("mkcol", 500, 502, None, False, id="mkcol_500_stays_usable"),
    ],
)
def test_the_outcome_table(
    world, caplog, kind, status, expected_status, expected_error, ticket_gone
):
    _, tickets, client = world
    token = issue(tickets)
    with respx.mock, caplog.at_level("ERROR", logger="mcp_connector.downloads.upload_route"):
        if kind == "mkcol":
            respx.route(method="MKCOL", url__startswith=ROOT).mock(
                return_value=httpx.Response(status)
            )
        else:
            folders_ok()
            respx.put(FILE_URL).mock(return_value=httpx.Response(status))
        answer = client.put(f"/ul/{token}", content=b"x")
    assert answer.status_code == expected_status
    if expected_error is not None:
        assert answer.json()["error"] == expected_error
    if kind == "put" and status in (200, 204):
        assert "ignored If-None-Match" in caplog.text
    remaining = run(tickets.peek(token))
    assert (remaining is None) == ticket_gone


# --- drain fix (2026-09-30 live incident): an error answered without reading the rest of the
# --- body leaves data unread when uvicorn closes the connection, which HaRP saw as a
# --- truncated response and Cloudflare turned into a 502 instead of the intended 404/409 ---


def test_an_unknown_token_still_drains_the_body(world):
    _, _tickets, client = world
    token = "A" * 43  # well formed per TOKEN_PATTERN, never issued: store.claim() returns None
    messages = [
        {"type": "http.request", "body": b"a", "more_body": True},
        {"type": "http.request", "body": b"b", "more_body": True},
        {"type": "http.request", "body": b"c", "more_body": False},
    ]
    sent = []

    async def send(message):
        sent.append(message)

    run(client.app(_raw_scope(f"/ul/{token}"), _receive_from(messages), send))
    assert sent[0]["status"] == 404
    assert messages == []


def test_a_put_answer_that_never_read_the_body_still_drains_it(world, monkeypatch):
    # Nextcloud can answer 412 (If-None-Match) before reading the streamed body at all, but
    # httpx's MockTransport (used under respx) always fully drains a streamed ``content=``
    # before invoking the mocked handler, so respx alone cannot reproduce "answers without
    # reading" here (verified: even a bare ``respx.put(...).mock(return_value=...)`` consumes
    # the whole async generator first). Stubbing ``dav.put_new_stream`` to ignore its ``body``
    # argument reproduces the real scenario the brief describes.
    _, tickets, client = world
    token = issue(tickets)
    messages = [
        {"type": "http.request", "body": b"a", "more_body": True},
        {"type": "http.request", "body": b"b", "more_body": True},
        {"type": "http.request", "body": b"c", "more_body": False},
    ]
    sent = []

    async def send(message):
        sent.append(message)

    async def put_without_reading(client_, creds, path, body, *, content_length=None):
        return 412

    monkeypatch.setattr(upload_route.dav, "put_new_stream", put_without_reading)

    with respx.mock:
        folders_ok()
        run(client.app(_raw_scope(f"/ul/{token}"), _receive_from(messages), send))
    assert sent[0]["status"] == 409
    assert messages == []


def test_a_successful_upload_reads_the_body_exactly_once(world):
    _, tickets, client = world
    token = issue(tickets)
    messages = [{"type": "http.request", "body": b"x" * 1000, "more_body": False}]
    sent = []

    async def send(message):
        sent.append(message)

    with respx.mock:
        folders_ok()
        respx.put(FILE_URL).mock(return_value=httpx.Response(201))
        run(client.app(_raw_scope(f"/ul/{token}"), _receive_from(messages), send))
    assert sent[0]["status"] == 201
    assert messages == []
