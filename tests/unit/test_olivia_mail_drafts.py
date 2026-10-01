import json

import guard_routes
import httpx
import pytest
import respx

from mcp_connector.errors import ToolError
from mcp_connector.nextcloud import NcClients
from mcp_connector.nextcloud.clients import mail_drafts
from mcp_connector.nextcloud.credentials import Credentials
from mcp_connector.tools import drafts

pytestmark = pytest.mark.anyio


@pytest.fixture(autouse=True)
def _no_kein_ki_tag(monkeypatch: pytest.MonkeyPatch) -> None:
    """These tests assert the behaviour without any kein-ki tag; the guard states are
    tested in test_olivia_exclusion_links.py."""
    guard_routes.patch_untagged(monkeypatch)


BASE = "http://nc.test"
DRAFTS_URL = f"{BASE}{mail_drafts.DRAFTS_PATH}"
ACCOUNTS = [
    {"id": 2, "email": "drosera@abnet.it", "aliases": []},
    {"id": 3, "email": "alessandro.drosera@gmail.com", "aliases": [{"email": "ale@drosera.info"}]},
]
ORIGINAL = {
    "subject": "cauzioni",
    "messageId": "<abc@belloni>",
    "from": [{"label": "Elena", "email": "elena@belloni.it"}],
    "replyTo": [{"label": "Elena Studio", "email": "studio@belloni.it"}],
    "to": [{"label": "Ale", "email": "Alessandro.Drosera@gmail.com"}],
    "cc": [],
}


@pytest.fixture
def clients(monkeypatch):
    async def fake_require(clients, app):
        return None

    async def fake_accounts(client, creds):
        return ACCOUNTS

    async def fake_message(client, creds, message_id):
        assert str(message_id) == "140813"
        return ORIGINAL, False

    monkeypatch.setattr(drafts.capabilities, "require_app", fake_require)
    monkeypatch.setattr(drafts.mail_client, "get_accounts", fake_accounts)
    monkeypatch.setattr(drafts.mail_client, "get_message", fake_message)
    return NcClients(client=httpx.AsyncClient(), creds=Credentials(BASE, "alice", "pw"))


def created(attachments=()):
    return httpx.Response(
        201,
        json={
            "status": "success",
            "data": {"id": 7, "attachments": [{"fileName": name} for name in attachments]},
        },
    )


def test_recipients_with_commas_and_quotes():
    assert drafts.parse_recipients(['"Rossi, Mario" <m@x.it>', "anna@y.it"]) == [
        {"label": "Rossi, Mario", "email": "m@x.it"},
        {"label": "anna@y.it", "email": "anna@y.it"},
    ]
    with pytest.raises(ToolError):
        drafts.parse_recipients(["not an address"])


def test_reply_subject_does_not_stack_prefixes():
    assert drafts.reply_subject("cauzioni") == "Re: cauzioni"
    assert drafts.reply_subject("RE: cauzioni") == "RE: cauzioni"
    assert drafts.reply_subject("R: cauzioni") == "R: cauzioni"


async def test_a_new_draft_with_two_accounts_needs_an_account(clients):
    with pytest.raises(ToolError, match=r"drosera@abnet\.it"):
        await drafts.create(clients, to=["a@b.it"], subject="s", body="b")


async def test_a_new_draft_is_posted_with_the_exact_payload(clients):
    with respx.mock:
        route = respx.post(DRAFTS_URL).mock(return_value=created())
        result = await drafts.create(
            clients,
            to=["Anna <a@b.it>"],
            subject="Ciao",
            body="Testo",
            account="alessandro.drosera@gmail.com",
        )
    request = route.calls.last.request
    assert request.headers["OCS-APIRequest"] == "true"
    payload = json.loads(request.content)
    assert payload["accountId"] == 3
    assert payload["to"] == [{"label": "Anna", "email": "a@b.it"}]
    assert payload["bodyPlain"] == "Testo"
    assert payload["isHtml"] is False
    assert payload["inReplyToMessageId"] is None
    assert "sendAt" not in payload
    assert result["draft_id"] == 7
    assert result["note"] == drafts.DRAFT_NOTE


async def test_a_new_draft_with_one_account_uses_it_without_being_asked(clients, monkeypatch):
    async def one(client, creds):
        return [ACCOUNTS[1]]

    monkeypatch.setattr(drafts.mail_client, "get_accounts", one)
    with respx.mock:
        route = respx.post(DRAFTS_URL).mock(return_value=created())
        result = await drafts.create(clients, to=["a@b.it"], subject="s", body="b")
    payload = json.loads(route.calls.last.request.content)
    assert payload["accountId"] == 3
    assert result["account"] == "alessandro.drosera@gmail.com"


async def test_a_reply_addressed_to_an_alias_picks_its_account(clients, monkeypatch):
    async def aliased(client, creds, message_id):
        return {**ORIGINAL, "to": [{"label": "Ale", "email": "ale@drosera.info"}]}, False

    monkeypatch.setattr(drafts.mail_client, "get_message", aliased)
    with respx.mock:
        route = respx.post(DRAFTS_URL).mock(return_value=created())
        await drafts.create(clients, reply_to="mail:140813", body="x")
    payload = json.loads(route.calls.last.request.content)
    assert payload["accountId"] == 3


async def test_a_reply_takes_account_recipient_subject_and_thread_from_the_original(clients):
    with respx.mock:
        route = respx.post(DRAFTS_URL).mock(return_value=created())
        await drafts.create(clients, reply_to="mail:140813", body="Grazie")
    payload = json.loads(route.calls.last.request.content)
    assert payload["accountId"] == 3
    assert payload["to"] == [{"label": "Elena Studio", "email": "studio@belloni.it"}]
    assert payload["subject"] == "Re: cauzioni"
    assert payload["inReplyToMessageId"] == "<abc@belloni>"


async def test_a_reply_with_no_account_among_the_recipients_is_refused(clients, monkeypatch):
    async def bcc_message(client, creds, message_id):
        return {**ORIGINAL, "to": [{"label": "L", "email": "list@x.it"}]}, False

    monkeypatch.setattr(drafts.mail_client, "get_message", bcc_message)
    with pytest.raises(ToolError, match="account"):
        await drafts.create(clients, reply_to="mail:140813", body="x")


async def test_attachments_are_checked_before_the_draft(clients, monkeypatch):
    async def fake_stat(client, creds, path):
        if path == "/Docs/missing.pdf":
            raise ToolError(message="File not found", hint="h", reason="unknown_id")
        return {"is_collection": path == "/Docs", "size": 10}

    monkeypatch.setattr(drafts.dav, "stat", fake_stat)
    for bad in (["/Docs/missing.pdf"], ["/Docs"], [f"/Docs/{i}.pdf" for i in range(11)]):
        with respx.mock:
            route = respx.post(DRAFTS_URL).mock(return_value=created())
            with pytest.raises(ToolError):
                await drafts.create(
                    clients, to=["a@b.it"], subject="s", body="b", account="3", attachments=bad
                )
        assert not route.called


async def test_attachments_over_25_mb_are_refused(clients, monkeypatch):
    async def big(client, creds, path):
        return {"is_collection": False, "size": 20 * 1024 * 1024}

    monkeypatch.setattr(drafts.dav, "stat", big)
    with pytest.raises(ToolError, match="25"):
        await drafts.create(
            clients,
            to=["a@b.it"],
            subject="s",
            body="b",
            account="3",
            attachments=["/a.pdf", "/b.pdf"],
        )


async def test_attachments_are_sent_as_cloud_files_and_missing_ones_reported(clients, monkeypatch):
    async def ok(client, creds, path):
        return {"is_collection": False, "size": 10}

    monkeypatch.setattr(drafts.dav, "stat", ok)
    with respx.mock:
        route = respx.post(DRAFTS_URL).mock(return_value=created(["a.pdf"]))
        result = await drafts.create(
            clients,
            to=["a@b.it"],
            subject="s",
            body="b",
            account="3",
            attachments=["/Docs/a.pdf", "/Docs/b.pdf"],
        )
    payload = json.loads(route.calls.last.request.content)
    assert payload["attachments"] == [
        {"type": "cloud", "fileName": "/Docs/a.pdf"},
        {"type": "cloud", "fileName": "/Docs/b.pdf"},
    ]
    assert result["attachments"] == ["a.pdf"]
    assert result["missing_attachments"] == ["b.pdf"]


async def test_only_the_drafts_route_is_ever_called(clients):
    with respx.mock(assert_all_called=False) as mock:
        mock.post(DRAFTS_URL).mock(return_value=created())
        await drafts.create(clients, to=["a@b.it"], subject="s", body="b", account="2")
        assert [str(call.request.url) for call in mock.calls] == [DRAFTS_URL]


async def test_same_named_attachments_from_two_folders_are_counted(clients, monkeypatch):
    async def ok(client, creds, path):
        return {"is_collection": False, "size": 10}

    monkeypatch.setattr(drafts.dav, "stat", ok)
    with respx.mock:
        respx.post(DRAFTS_URL).mock(return_value=created(["a.pdf"]))
        result = await drafts.create(
            clients,
            to=["a@b.it"],
            subject="s",
            body="b",
            account="3",
            attachments=["/Docs/a.pdf", "/Other/a.pdf"],
        )
    assert result["missing_attachments"] == ["a.pdf"]


async def test_no_mail_account_is_a_clear_error(clients, monkeypatch):
    async def none(client, creds):
        return []

    monkeypatch.setattr(drafts.mail_client, "get_accounts", none)
    with pytest.raises(ToolError, match="No mail account"):
        await drafts.create(clients, to=["a@b.it"], subject="s", body="b")


async def test_a_reply_to_a_mail_without_sender_address_needs_to(clients, monkeypatch):
    async def anonymous(client, creds, message_id):
        return {**ORIGINAL, "replyTo": [], "from": [{"label": "?"}]}, False

    monkeypatch.setattr(drafts.mail_client, "get_message", anonymous)
    with pytest.raises(ToolError, match="no sender"):
        await drafts.create(clients, reply_to="mail:140813", body="x")
