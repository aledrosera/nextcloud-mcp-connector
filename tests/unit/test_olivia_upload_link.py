import httpx
import pytest
import respx

from mcp_connector import config
from mcp_connector.deps import TicketOwner
from mcp_connector.downloads import store as dl_store
from mcp_connector.downloads import upload
from mcp_connector.errors import ConflictError, ToolError
from mcp_connector.nextcloud import NcClients
from mcp_connector.nextcloud.credentials import Credentials

pytestmark = pytest.mark.anyio
BASE = "http://nc.test"
ENV = {config.ENV_PUBLIC_URL: "https://cloud.example/exapps/mcp_connector"}
TARGET = "/Clienti/Rossi/Preventivo à #1.docx"
URL = f"{BASE}/remote.php/dav/files/alice/Clienti/Rossi/Preventivo%20%C3%A0%20%231.docx"


def clients():
    return NcClients(client=httpx.AsyncClient(), creds=Credentials(BASE, "alice", "pw"))


def test_ticket_path_round_trip():
    assert upload.parse_upload_path(upload.upload_ticket_path("/a/b.pdf")) == "/a/b.pdf"
    assert upload.parse_upload_path("/a/b.pdf") is None
    assert upload.parse_upload_path("mail:1/2") is None
    assert upload.parse_upload_path("upload:relative.pdf") is None
    assert upload.parse_upload_path("upload:/") is None
    assert upload.parse_upload_path("upload:/a/b/") is None


async def test_link_is_issued_for_a_free_path(tmp_path):
    tickets = dl_store.TicketStore(tmp_path / dl_store.TICKETS_FILENAME)
    with respx.mock:
        respx.route(method="PROPFIND", url=URL).mock(return_value=httpx.Response(404))
        card = await upload.issue_upload_link(
            clients(), TicketOwner("auth-1", "alice"), TARGET, env=ENV, tickets=tickets, now=1000
        )
    assert card["path"] == TARGET
    assert card["upload_url"].startswith("https://cloud.example/exapps/mcp_connector/ul/")
    assert card["method"] == "PUT"
    assert card["expires_at"] == "1970-01-01T00:46:40+00:00"  # 1000 + 1800
    assert card["single_use"] is True
    assert card["max_bytes"] == 104857600
    assert "curl --fail-with-body" in card["how_to"]
    token = card["upload_url"].rsplit("/", 1)[-1]
    ticket = await tickets.claim(token, now=1001)
    assert ticket is not None
    assert ticket.path == f"upload:{TARGET}"
    assert ticket.auth_id == "auth-1"


async def test_an_existing_path_is_refused(tmp_path):
    tickets = dl_store.TicketStore(tmp_path / dl_store.TICKETS_FILENAME)
    body = (
        '<?xml version="1.0"?><d:multistatus xmlns:d="DAV:"><d:response>'
        "<d:href>/remote.php/dav/files/alice/Clienti/Rossi/x</d:href><d:propstat><d:prop>"
        "<d:getcontentlength>1</d:getcontentlength><d:resourcetype/></d:prop>"
        "<d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response></d:multistatus>"
    )
    with respx.mock:
        respx.route(method="PROPFIND", url=URL).mock(return_value=httpx.Response(207, text=body))
        with pytest.raises(ConflictError, match="already exists"):
            await upload.issue_upload_link(
                clients(), TicketOwner("auth-1", "alice"), TARGET, env=ENV, tickets=tickets
            )


async def test_a_folder_target_is_refused(tmp_path):
    tickets = dl_store.TicketStore(tmp_path / dl_store.TICKETS_FILENAME)
    with pytest.raises(ToolError, match="folder"):
        await upload.issue_upload_link(
            clients(), TicketOwner("auth-1", "alice"), "/Clienti/", env=ENV, tickets=tickets
        )
