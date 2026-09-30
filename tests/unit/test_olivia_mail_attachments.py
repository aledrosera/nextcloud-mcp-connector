"""Task: a fetched mail lists its attachments, each with its own single-use download link
served by the same ``/dl/{token}`` route a binary file already gets (fork olivia).

Covers the whole slice: the ticket path codec, the streamed GET of one attachment, the
``/dl`` route dispatching a mail attachment ticket to it instead of to ``dav.open_download``,
``_fetch_mail`` building the ``Attachments`` section, and ``issue.issue_ticket`` as the shared
half of ``issue_link``.
"""

import asyncio

import httpx
import pytest
import respx
from starlette.applications import Starlette
from starlette.testclient import TestClient

from mcp_connector import config
from mcp_connector.deps import TicketOwner
from mcp_connector.downloads import issue, mail_attachment
from mcp_connector.downloads import route as dl_route
from mcp_connector.downloads import store as dl_store
from mcp_connector.errors import REASON_PERMISSION_DENIED, REASON_UNKNOWN_ID, ToolError
from mcp_connector.nextcloud.credentials import Credentials
from mcp_connector.oauth import store as oauth_store_module
from mcp_connector.tools import chatgpt

pytestmark = pytest.mark.anyio
BASE = "http://nc.test"


def run(work):
    return asyncio.run(work)


def clients_stub(base_url: str = "https://cloud.example"):
    return type("C", (), {"client": None, "creds": type("K", (), {"base_url": base_url})()})()


# --- ticket path codec ---------------------------------------------------------------------


def test_ticket_path_roundtrips():
    path = mail_attachment.ticket_path("21", "2")
    assert path == "mail:21/2"
    assert mail_attachment.parse_ticket_path(path) == ("21", "2")


def test_ticket_path_roundtrips_a_dotted_imap_sub_part():
    path = mail_attachment.ticket_path("21", "2.1")
    assert path == "mail:21/2.1"
    assert mail_attachment.parse_ticket_path(path) == ("21", "2.1")


@pytest.mark.parametrize(
    "path",
    [
        "mail:abc/2",
        "mail:1/../x",
        "/Docs/a.pdf",
        "mail:1/",
        "mail:1",
        "mail:1/2/3",
        "mail:/2",
        "",
    ],
)
def test_parse_ticket_path_rejects_anything_that_is_not_the_exact_shape(path):
    assert mail_attachment.parse_ticket_path(path) is None


# --- open_attachment -------------------------------------------------------------------------

ATTACHMENT_URL = f"{BASE}/index.php/apps/mail/api/messages/21/attachment/2"


async def test_open_attachment_streams_the_whole_file():
    body = b"%PDF-" + b"x" * 200_000
    creds = Credentials(BASE, "alice", "app-password-test")
    async with httpx.AsyncClient() as client:
        with respx.mock(assert_all_called=True) as mock:
            route = mock.get(ATTACHMENT_URL).mock(return_value=httpx.Response(200, content=body))
            response = await mail_attachment.open_attachment(client, creds, "21", "2")
            data = b"".join([chunk async for chunk in response.aiter_raw()])
            await response.aclose()
    assert data == body
    assert route.calls[0].request.method == "GET"
    assert route.calls[0].request.headers["accept-encoding"] == "identity"


async def test_open_attachment_raises_unknown_id_and_closes_on_404():
    creds = Credentials(BASE, "alice", "app-password-test")
    async with httpx.AsyncClient() as client:
        with respx.mock:
            respx.get(ATTACHMENT_URL).mock(return_value=httpx.Response(404))
            with pytest.raises(ToolError) as caught:
                await mail_attachment.open_attachment(client, creds, "21", "2")
    assert caught.value.reason == REASON_UNKNOWN_ID


@pytest.mark.parametrize("status", [401, 403])
async def test_open_attachment_raises_permission_denied_and_closes(status):
    creds = Credentials(BASE, "alice", "app-password-test")
    async with httpx.AsyncClient() as client:
        with respx.mock:
            respx.get(ATTACHMENT_URL).mock(return_value=httpx.Response(status))
            with pytest.raises(ToolError) as caught:
                await mail_attachment.open_attachment(client, creds, "21", "2")
    assert caught.value.reason == REASON_PERMISSION_DENIED


async def test_open_attachment_raises_on_server_error_and_closes():
    creds = Credentials(BASE, "alice", "app-password-test")
    async with httpx.AsyncClient() as client:
        with respx.mock:
            respx.get(ATTACHMENT_URL).mock(return_value=httpx.Response(500))
            with pytest.raises(ToolError) as caught:
                await mail_attachment.open_attachment(client, creds, "21", "2")
    assert caught.value.reason != REASON_PERMISSION_DENIED
    assert caught.value.reason != REASON_UNKNOWN_ID


# --- the /dl route dispatching a mail attachment ticket --------------------------------------

ROUTE_ENV = {
    config.ENV_APP_ID: "mcp_connector",
    config.ENV_APP_SECRET: "app-secret-test",
    config.ENV_APP_VERSION: "0.3.2",
    config.ENV_NEXTCLOUD_URL: BASE,
}
ATTACHMENT_BODY = b"%PDF-1.7 " + b"y" * 1000


@pytest.fixture
def world(tmp_path):
    oauth = oauth_store_module.OAuthStore(
        tmp_path / oauth_store_module.STORE_FILENAME, bytes(range(32))
    )
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

    app = Starlette(
        routes=dl_route.download_routes(ROUTE_ENV, oauth_store=provider, tickets=tickets)
    )
    return oauth, tickets, TestClient(app)


def issue_attachment_ticket(tickets, *, auth_id="auth-1"):
    token, _ = run(
        tickets.issue(
            auth_id=auth_id,
            nc_user="alice",
            path="mail:21/2",
            name="Rapporto.pdf",
            content_type="application/pdf",
            size=len(ATTACHMENT_BODY),
            ttl_seconds=600,
        )
    )
    return token


def test_the_route_streams_a_mail_attachment_once_then_404s(world):
    _, tickets, client = world
    token = issue_attachment_ticket(tickets)
    with respx.mock:
        respx.get(ATTACHMENT_URL).mock(return_value=httpx.Response(200, content=ATTACHMENT_BODY))
        first = client.get(f"/dl/{token}")
    assert first.status_code == 200
    assert first.content == ATTACHMENT_BODY
    assert 'filename="Rapporto.pdf"' in first.headers["content-disposition"]
    assert client.get(f"/dl/{token}").status_code == 404


def test_a_gone_mail_attachment_answers_not_found_and_keeps_the_ticket_usable(world):
    _, tickets, client = world
    token = issue_attachment_ticket(tickets)
    with respx.mock:
        respx.get(ATTACHMENT_URL).mock(return_value=httpx.Response(404))
        response = client.get(f"/dl/{token}")
    assert (response.status_code, response.text) == (404, "Not found")
    assert run(tickets.peek(token)) is not None


def test_a_rejected_mail_credential_answers_not_found_and_burns_the_ticket(world):
    _, tickets, client = world
    token = issue_attachment_ticket(tickets)
    with respx.mock:
        respx.get(ATTACHMENT_URL).mock(return_value=httpx.Response(401))
        response = client.get(f"/dl/{token}")
    assert (response.status_code, response.text) == (404, "Not found")
    assert run(tickets.peek(token)) is None


# --- _fetch_mail: the Attachments section -----------------------------------------------------


def base_message(**attachments_kwargs):
    return {
        "subject": "Ciao",
        "body": "<p>testo</p>",
        "mailboxId": 6,
        "databaseId": 21,
        "dateInt": 1790000000,
        **attachments_kwargs,
    }


async def test_fetch_mail_without_attachments_key_is_unchanged(monkeypatch):
    async def fake_require(clients, app):
        return None

    async def fake_get_message(client, creds, message_id):
        return base_message(), False

    monkeypatch.setattr(chatgpt.capabilities, "require_app", fake_require)
    monkeypatch.setattr(chatgpt.mail_client, "get_message", fake_get_message)
    result = await chatgpt._fetch_mail(clients_stub(), "21")  # pyright: ignore[reportArgumentType]
    assert "Attachments" not in result["text"]
    assert "attachments" not in result["metadata"]


async def test_fetch_mail_with_an_empty_attachments_list_is_unchanged(monkeypatch):
    async def fake_require(clients, app):
        return None

    async def fake_get_message(client, creds, message_id):
        return base_message(attachments=[]), False

    monkeypatch.setattr(chatgpt.capabilities, "require_app", fake_require)
    monkeypatch.setattr(chatgpt.mail_client, "get_message", fake_get_message)
    result = await chatgpt._fetch_mail(clients_stub(), "21")  # pyright: ignore[reportArgumentType]
    assert "Attachments" not in result["text"]
    assert "attachments" not in result["metadata"]


async def test_fetch_mail_with_owner_lists_attachments_with_links(monkeypatch):
    async def fake_require(clients, app):
        return None

    async def fake_get_message(client, creds, message_id):
        return (
            base_message(
                attachments=[
                    {
                        "id": "2",
                        "fileName": "Rapporto.pdf",
                        "mime": "application/pdf",
                        "size": 67378,
                    },
                    # A missing fileName and mime happens for an embedded message; the
                    # fallbacks the brief specifies still produce a usable line.
                    {"id": "3", "size": None},
                ]
            ),
            False,
        )

    issued: list[str] = []

    async def fake_issue_ticket(owner, *, path, name, content_type, size):
        issued.append(path)
        return {"download_url": f"https://cloud.example/dl/{path.replace(':', '_')}"}

    monkeypatch.setattr(chatgpt.capabilities, "require_app", fake_require)
    monkeypatch.setattr(chatgpt.mail_client, "get_message", fake_get_message)
    monkeypatch.setattr(chatgpt.issue, "issue_ticket", fake_issue_ticket)
    result = await chatgpt._fetch_mail(clients_stub(), "21", owner=TicketOwner("a", "alice"))  # pyright: ignore[reportArgumentType]

    lines = result["text"].split("\n")
    assert "Attachments (2):" in lines
    assert (
        "- Rapporto.pdf (application/pdf, 67378 bytes): https://cloud.example/dl/mail_21/2" in lines
    )
    assert (
        "- 3.eml (application/octet-stream, 0 bytes): https://cloud.example/dl/mail_21/3" in lines
    )
    assert issue.HOW_TO in result["text"]
    assert result["metadata"]["attachments"] == "2"
    assert issued == ["mail:21/2", "mail:21/3"]


async def test_fetch_mail_without_owner_lists_attachments_without_links(monkeypatch):
    async def fake_require(clients, app):
        return None

    async def fake_get_message(client, creds, message_id):
        return (
            base_message(
                attachments=[
                    {"id": "2", "fileName": "Rapporto.pdf", "mime": "application/pdf", "size": 100}
                ]
            ),
            False,
        )

    monkeypatch.setattr(chatgpt.capabilities, "require_app", fake_require)
    monkeypatch.setattr(chatgpt.mail_client, "get_message", fake_get_message)
    result = await chatgpt._fetch_mail(clients_stub(), "21")  # pyright: ignore[reportArgumentType]

    lines = result["text"].split("\n")
    assert "Attachments (1):" in lines
    assert "- Rapporto.pdf (application/pdf, 100 bytes)" in lines
    assert issue.HOW_TO not in result["text"]
    assert result["metadata"]["attachments"] == "1"


async def test_fetch_mail_lists_an_attachment_without_a_link_when_issuing_fails(monkeypatch):
    async def fake_require(clients, app):
        return None

    async def fake_get_message(client, creds, message_id):
        return (
            base_message(
                attachments=[
                    {"id": "2", "fileName": "Rapporto.pdf", "mime": "application/pdf", "size": 100}
                ]
            ),
            False,
        )

    async def fake_issue_ticket(owner, *, path, name, content_type, size):
        raise ToolError(message="The download link could not be created.", hint="Retry.")

    monkeypatch.setattr(chatgpt.capabilities, "require_app", fake_require)
    monkeypatch.setattr(chatgpt.mail_client, "get_message", fake_get_message)
    monkeypatch.setattr(chatgpt.issue, "issue_ticket", fake_issue_ticket)
    result = await chatgpt._fetch_mail(clients_stub(), "21", owner=TicketOwner("a", "alice"))  # pyright: ignore[reportArgumentType]

    lines = result["text"].split("\n")
    assert "- Rapporto.pdf (application/pdf, 100 bytes)" in lines
    assert issue.HOW_TO not in result["text"]
    assert result["metadata"]["attachments"] == "1"


async def test_fetch_mail_lists_an_attachment_without_a_link_when_its_id_is_not_a_valid_ticket(
    monkeypatch,
):
    async def fake_require(clients, app):
        return None

    async def fake_get_message(client, creds, message_id):
        return (
            base_message(
                attachments=[
                    {"id": "not-numeric", "fileName": "weird.eml", "mime": None, "size": None}
                ]
            ),
            False,
        )

    async def fail_if_called(owner, *, path, name, content_type, size):
        raise AssertionError("issue_ticket must not be called for an unroutable attachment id")

    monkeypatch.setattr(chatgpt.capabilities, "require_app", fake_require)
    monkeypatch.setattr(chatgpt.mail_client, "get_message", fake_get_message)
    monkeypatch.setattr(chatgpt.issue, "issue_ticket", fail_if_called)
    result = await chatgpt._fetch_mail(clients_stub(), "21", owner=TicketOwner("a", "alice"))  # pyright: ignore[reportArgumentType]

    lines = result["text"].split("\n")
    assert "- weird.eml (application/octet-stream, 0 bytes)" in lines


async def test_fetch_mail_caps_attachment_lines_at_twenty(monkeypatch):
    async def fake_require(clients, app):
        return None

    attachments = [
        {"id": str(i), "fileName": f"f{i}.pdf", "mime": "application/pdf", "size": 10}
        for i in range(25)
    ]

    async def fake_get_message(client, creds, message_id):
        return base_message(attachments=attachments), False

    monkeypatch.setattr(chatgpt.capabilities, "require_app", fake_require)
    monkeypatch.setattr(chatgpt.mail_client, "get_message", fake_get_message)
    result = await chatgpt._fetch_mail(clients_stub(), "21")  # pyright: ignore[reportArgumentType]

    lines = result["text"].split("\n")
    assert "Attachments (25):" in lines
    shown = [line for line in lines if line.startswith("- f")]
    assert len(shown) == 20
    assert "- … and 5 more" in lines
    assert result["metadata"]["attachments"] == "25"


# --- issue.issue_ticket ------------------------------------------------------------------------

ISSUE_ENV = {
    config.ENV_PUBLIC_URL: "https://cloud.example/exapps/mcp_connector",
    config.ENV_DOWNLOAD_TTL_MINUTES: "5",
}


async def test_issue_ticket_returns_the_same_keys_as_issue_link(tmp_path):
    tickets = dl_store.TicketStore(tmp_path / dl_store.TICKETS_FILENAME)
    result = await issue.issue_ticket(
        TicketOwner("auth-1", "alice"),
        path="mail:21/2",
        name="Rapporto.pdf",
        content_type="application/pdf",
        size=100,
        env=ISSUE_ENV,
        tickets=tickets,
        now=1000,
    )
    assert set(result) == {
        "path",
        "name",
        "size",
        "content_type",
        "download_url",
        "expires_at",
        "single_use",
        "how_to",
    }
    assert result["download_url"].startswith("https://cloud.example/exapps/mcp_connector/dl/")
    token = result["download_url"].rsplit("/", 1)[-1]
    claimed = await tickets.claim(token, now=1001)
    assert claimed is not None
    assert claimed.path == "mail:21/2"
