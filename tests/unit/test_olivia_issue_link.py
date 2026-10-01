import guard_routes
import httpx
import pytest
import respx

from mcp_connector import config
from mcp_connector.deps import TicketOwner
from mcp_connector.downloads import issue
from mcp_connector.downloads import store as dl_store
from mcp_connector.errors import ToolError
from mcp_connector.nextcloud import NcClients
from mcp_connector.nextcloud.credentials import Credentials

pytestmark = pytest.mark.anyio


@pytest.fixture(autouse=True)
def _no_kein_ki_tag(monkeypatch: pytest.MonkeyPatch) -> None:
    """These tests assert the behaviour without any kein-ki tag; the guard states are
    tested in test_olivia_exclusion_links.py."""
    guard_routes.patch_untagged(monkeypatch)


BASE = "http://nc.test"
URL = f"{BASE}/remote.php/dav/files/alice/Docs/scan.pdf"
ENV = {
    config.ENV_PUBLIC_URL: "https://cloud.example/exapps/mcp_connector",
    config.ENV_DOWNLOAD_TTL_MINUTES: "5",
}


def propfind(*, collection=False, length=1234, content_type="application/pdf"):
    kind = "<d:collection/>" if collection else ""
    return (
        '<?xml version="1.0"?><d:multistatus xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns">'
        "<d:response><d:href>/remote.php/dav/files/alice/Docs/scan.pdf</d:href><d:propstat><d:prop>"
        f"<d:getcontentlength>{length}</d:getcontentlength><d:getcontenttype>{content_type}</d:getcontenttype>"
        f"<d:resourcetype>{kind}</d:resourcetype><oc:fileid>4711</oc:fileid>"
        "</d:prop><d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response></d:multistatus>"
    )


async def test_issue_link_returns_a_single_use_url(tmp_path):
    tickets = dl_store.TicketStore(tmp_path / dl_store.TICKETS_FILENAME)
    clients = NcClients(client=httpx.AsyncClient(), creds=Credentials(BASE, "alice", "pw"))
    with respx.mock:
        respx.route(method="PROPFIND", url=URL).mock(
            return_value=httpx.Response(207, text=propfind())
        )
        result = await issue.issue_link(
            clients,
            TicketOwner("auth-1", "alice"),
            "/Docs/scan.pdf",
            env=ENV,
            tickets=tickets,
            now=1000,
        )
    assert result["download_url"].startswith("https://cloud.example/exapps/mcp_connector/dl/")
    assert result["name"] == "scan.pdf"
    assert result["size"] == 1234
    assert result["content_type"] == "application/pdf"
    assert result["single_use"] is True
    assert result["expires_at"] == "1970-01-01T00:21:40+00:00"  # 1000 + 5 * 60
    assert "web_fetch" in result["how_to"]
    assert "curl -fL -o" in result["how_to"]
    token = result["download_url"].rsplit("/", 1)[-1]
    claimed = await tickets.claim(token, now=1001)
    assert claimed is not None
    assert claimed.auth_id == "auth-1"


async def test_issue_link_refuses_a_folder(tmp_path):
    tickets = dl_store.TicketStore(tmp_path / dl_store.TICKETS_FILENAME)
    clients = NcClients(client=httpx.AsyncClient(), creds=Credentials(BASE, "alice", "pw"))
    with respx.mock:
        respx.route(method="PROPFIND", url=URL).mock(
            return_value=httpx.Response(207, text=propfind(collection=True))
        )
        with pytest.raises(ToolError, match="folder"):
            await issue.issue_link(
                clients, TicketOwner("auth-1", "alice"), "/Docs/scan.pdf", env=ENV, tickets=tickets
            )
