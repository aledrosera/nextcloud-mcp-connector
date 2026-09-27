"""Unit tests for the ``files_list`` tool logic.

The folder itself must never appear in its own listing, a file must produce an explanation
instead of an empty list, and a truncated listing must continue exactly where it stopped.
"""

from pathlib import Path

import guard_routes
import httpx
import pytest
import respx

from mcp_connector.errors import ToolError
from mcp_connector.nextcloud import NcClients
from mcp_connector.nextcloud.credentials import Credentials
from mcp_connector.paging import decode_cursor, encode_cursor
from mcp_connector.tools import files as files_tools

BASE = "http://nc.test"
USER = "alice"
SECRET = "app-password-test"
FILES_ROOT = f"{BASE}/remote.php/dav/files/{USER}"
#: PROPFIND on the home itself keeps the trailing slash of the collection URL.
ROOT_URL = f"{FILES_ROOT}/"

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
PROPFIND_207 = (FIXTURES / "webdav_propfind_207.xml").read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def _no_kein_ki_tag(monkeypatch: pytest.MonkeyPatch) -> None:
    """Existing tests assert the behaviour without any kein-ki tag; the guard states are
    tested in the *_exclusion test modules."""
    guard_routes.patch_untagged(monkeypatch)


def _folder_207(count: int) -> str:
    entries = "".join(
        f"""
  <d:response>
    <d:href>/remote.php/dav/files/alice/file-{index:03d}.md</d:href>
    <d:propstat>
      <d:prop>
        <d:displayname>file-{index:03d}.md</d:displayname>
        <d:getcontenttype>text/markdown</d:getcontenttype>
        <d:getlastmodified>Thu, 14 Aug 2026 10:00:00 GMT</d:getlastmodified>
        <d:getcontentlength>{200 + index}</d:getcontentlength>
        <d:resourcetype/>
        <oc:fileid>{7000 + index}</oc:fileid>
      </d:prop>
      <d:status>HTTP/1.1 200 OK</d:status>
    </d:propstat>
  </d:response>"""
        for index in range(count)
    )
    root = """
  <d:response>
    <d:href>/remote.php/dav/files/alice/</d:href>
    <d:propstat>
      <d:prop>
        <d:displayname>alice</d:displayname>
        <d:resourcetype><d:collection/></d:resourcetype>
        <oc:fileid>1</oc:fileid>
        <oc:size>99999</oc:size>
      </d:prop>
      <d:status>HTTP/1.1 200 OK</d:status>
    </d:propstat>
  </d:response>"""
    return (
        '<?xml version="1.0"?>\n<d:multistatus xmlns:d="DAV:" '
        f'xmlns:oc="http://owncloud.org/ns">{root}{entries}\n</d:multistatus>\n'
    )


@pytest.fixture
def clients() -> NcClients:
    return NcClients(
        client=httpx.AsyncClient(follow_redirects=False),
        creds=Credentials(BASE, USER, SECRET),
    )


@pytest.mark.anyio
async def test_list_returns_the_children_without_the_folder_itself(clients: NcClients) -> None:
    with respx.mock(assert_all_called=True) as mock:
        mock.route(method="PROPFIND", url=f"{FILES_ROOT}/Docs").mock(
            return_value=httpx.Response(207, text=PROPFIND_207)
        )
        result = await files_tools.list_dir(clients, path="/Docs")

    assert result["path"] == "/Docs"
    assert result["count"] == 3
    assert [item["path"] for item in result["items"]] == [
        "/Docs/Bilder",
        "/Docs/Grüße & Co.txt",
        "/Docs/notes.md",
    ]
    assert "/Docs" not in [item["path"] for item in result["items"]]
    assert result["items"][0]["kind"] == "folder", "folders first, then names"
    assert result["items"][2] == {
        "path": "/Docs/notes.md",
        "name": "notes.md",
        "kind": "file",
        "size": 2048,
        "content_type": "text/markdown",
        "modified": "Thu, 14 Aug 2026 09:00:00 GMT",
        "id": "file:11",
    }
    assert "truncated" not in result


@pytest.mark.anyio
async def test_listing_the_root_folder_works(clients: NcClients) -> None:
    with respx.mock as mock:
        route = mock.route(method="PROPFIND", url=ROOT_URL).mock(
            return_value=httpx.Response(207, text=_folder_207(3))
        )
        result = await files_tools.list_dir(clients, path="/")

    assert route.calls[0].request.headers["depth"] == "1"
    assert result["path"] == "/"
    assert result["count"] == 3


@pytest.mark.anyio
async def test_an_empty_folder_is_an_empty_list_and_not_an_error(clients: NcClients) -> None:
    with respx.mock as mock:
        mock.route(method="PROPFIND", url=ROOT_URL).mock(
            return_value=httpx.Response(207, text=_folder_207(0))
        )
        result = await files_tools.list_dir(clients, path="/")

    assert result["items"] == []
    assert result["count"] == 0


@pytest.mark.anyio
async def test_a_file_path_is_explained_instead_of_listed(clients: NcClients) -> None:
    body = """<?xml version="1.0"?>
<d:multistatus xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns">
  <d:response>
    <d:href>/remote.php/dav/files/alice/Docs/notes.md</d:href>
    <d:propstat><d:prop>
      <d:displayname>notes.md</d:displayname>
      <d:getcontentlength>10</d:getcontentlength>
      <d:resourcetype/>
      <oc:fileid>11</oc:fileid>
    </d:prop><d:status>HTTP/1.1 200 OK</d:status></d:propstat>
  </d:response>
</d:multistatus>
"""
    with respx.mock as mock:
        mock.route(method="PROPFIND", url=f"{FILES_ROOT}/Docs/notes.md").mock(
            return_value=httpx.Response(207, text=body)
        )
        with pytest.raises(ToolError) as excinfo:
            await files_tools.list_dir(clients, path="/Docs/notes.md")

    assert "file" in excinfo.value.message.lower()
    assert "files_read" in excinfo.value.hint


@pytest.mark.anyio
async def test_a_truncated_listing_continues_with_its_handle(clients: NcClients) -> None:
    with respx.mock as mock:
        mock.route(method="PROPFIND", url=ROOT_URL).mock(
            return_value=httpx.Response(207, text=_folder_207(25))
        )
        first = await files_tools.list_dir(clients, path="/", limit=10)
        second = await files_tools.list_dir(clients, path="/", limit=10, cursor=first["next"])
        third = await files_tools.list_dir(clients, path="/", limit=10, cursor=second["next"])

    assert first["truncated"] is True
    assert decode_cursor(first["next"]) == {"o": 10, "p": "/"}
    assert first["items"][0]["name"] == "file-000.md"
    assert second["items"][0]["name"] == "file-010.md"
    assert third["count"] == 5
    assert "truncated" not in third


@pytest.mark.anyio
async def test_a_limit_above_the_maximum_is_capped(clients: NcClients) -> None:
    with respx.mock as mock:
        mock.route(method="PROPFIND", url=ROOT_URL).mock(
            return_value=httpx.Response(207, text=_folder_207(3))
        )
        result = await files_tools.list_dir(clients, path="/", limit=99_999)

    assert result["count"] == 3


@pytest.mark.anyio
async def test_a_cursor_from_another_folder_is_refused(clients: NcClients) -> None:
    stale = encode_cursor({"o": 10, "p": "/Docs"})
    with respx.mock as mock:
        with pytest.raises(ToolError) as excinfo:
            await files_tools.list_dir(clients, path="/", cursor=stale)
        assert len(mock.calls) == 0

    assert "cursor" in excinfo.value.message.lower()


@pytest.mark.anyio
async def test_an_invalid_cursor_never_reaches_the_network(clients: NcClients) -> None:
    with respx.mock as mock:
        with pytest.raises(ToolError):
            await files_tools.list_dir(clients, path="/", cursor="!!!not-a-handle!!!")
        assert len(mock.calls) == 0


@pytest.mark.anyio
async def test_an_unknown_folder_reports_the_path(clients: NcClients) -> None:
    with respx.mock as mock:
        mock.route(method="PROPFIND", url=f"{FILES_ROOT}/Nope").mock(
            return_value=httpx.Response(404)
        )
        with pytest.raises(ToolError) as excinfo:
            await files_tools.list_dir(clients, path="/Nope")

    assert "/Nope" in excinfo.value.message
    assert "not found" in excinfo.value.message.lower()


@pytest.mark.anyio
async def test_a_forbidden_folder_reports_a_permission_hint(clients: NcClients) -> None:
    with respx.mock as mock:
        mock.route(method="PROPFIND", url=f"{FILES_ROOT}/Shared").mock(
            return_value=httpx.Response(403)
        )
        with pytest.raises(ToolError) as excinfo:
            await files_tools.list_dir(clients, path="/Shared")

    assert "permission" in (excinfo.value.message + excinfo.value.hint).lower()


@pytest.mark.anyio
async def test_a_server_error_is_reported_without_the_body(clients: NcClients) -> None:
    with respx.mock as mock:
        mock.route(method="PROPFIND", url=ROOT_URL).mock(
            return_value=httpx.Response(500, text="<html>stack trace</html>")
        )
        with pytest.raises(ToolError) as excinfo:
            await files_tools.list_dir(clients, path="/")

    assert "500" in excinfo.value.message
    assert "stack trace" not in excinfo.value.message


@pytest.mark.anyio
async def test_an_unsafe_path_never_reaches_the_network(clients: NcClients) -> None:
    with respx.mock as mock:
        with pytest.raises(ToolError):
            await files_tools.list_dir(clients, path="/Docs/../../etc")
        assert len(mock.calls) == 0
