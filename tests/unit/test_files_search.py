"""Unit tests for the ``files_search`` tool logic.

All paths on purpose: happy, empty, capped limit, truncation with a cursor, an invalid
cursor, a cursor from another query, 4xx, 5xx and a folder parameter that tries to leave
the user's home.
"""

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
SEARCH_URL = f"{BASE}/remote.php/dav/"

_EMPTY_207 = """<?xml version="1.0"?>
<d:multistatus xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns"></d:multistatus>
"""


@pytest.fixture(autouse=True)
def _no_kein_ki_tag(monkeypatch: pytest.MonkeyPatch) -> None:
    """Existing tests assert the behaviour without any kein-ki tag; the guard states are
    tested in the *_exclusion test modules."""
    guard_routes.patch_untagged(monkeypatch)


def _hits_207(count: int, *, first: int = 0) -> str:
    entries = "".join(
        f"""
  <d:response>
    <d:href>/remote.php/dav/files/alice/Docs/budget-{index:03d}.md</d:href>
    <d:propstat>
      <d:prop>
        <d:displayname>budget-{index:03d}.md</d:displayname>
        <d:getcontenttype>text/markdown</d:getcontenttype>
        <d:getlastmodified>Thu, 14 Aug 2026 10:00:00 GMT</d:getlastmodified>
        <d:getcontentlength>{100 + index}</d:getcontentlength>
        <d:resourcetype/>
        <oc:fileid>{5000 + index}</oc:fileid>
      </d:prop>
      <d:status>HTTP/1.1 200 OK</d:status>
    </d:propstat>
  </d:response>"""
        for index in range(first, first + count)
    )
    return (
        '<?xml version="1.0"?>\n<d:multistatus xmlns:d="DAV:" '
        f'xmlns:oc="http://owncloud.org/ns">{entries}\n</d:multistatus>\n'
    )


@pytest.fixture
def clients() -> NcClients:
    return NcClients(
        client=httpx.AsyncClient(follow_redirects=False),
        creds=Credentials(BASE, USER, SECRET),
    )


@pytest.mark.anyio
async def test_search_returns_hits_with_stable_fields(clients: NcClients) -> None:
    with respx.mock(assert_all_called=True) as mock:
        mock.route(method="SEARCH", url=SEARCH_URL).mock(
            return_value=httpx.Response(207, text=_hits_207(2))
        )
        result = await files_tools.search(clients, query="budget")

    assert result["query"] == "budget"
    assert result["folder"] == "/"
    assert result["count"] == 2
    assert result["items"][0] == {
        "path": "/Docs/budget-000.md",
        "name": "budget-000.md",
        "kind": "file",
        "size": 100,
        "content_type": "text/markdown",
        "modified": "Thu, 14 Aug 2026 10:00:00 GMT",
        "id": "file:5000",
    }
    assert "truncated" not in result
    assert "next" not in result


@pytest.mark.anyio
async def test_every_answer_says_that_only_names_are_matched(clients: NcClients) -> None:
    """Pitfall 5: the note is what keeps the model from claiming a document is missing."""
    with respx.mock as mock:
        mock.route(method="SEARCH", url=SEARCH_URL).mock(
            return_value=httpx.Response(207, text=_hits_207(1))
        )
        with_hits = await files_tools.search(clients, query="budget")

        mock.route(method="SEARCH", url=SEARCH_URL).mock(
            return_value=httpx.Response(207, text=_EMPTY_207)
        )
        without_hits = await files_tools.search(clients, query="budget")

    assert with_hits["note"] == files_tools.SEARCH_NOTE
    assert without_hits["note"] == files_tools.SEARCH_NOTE
    assert without_hits["items"] == []
    assert without_hits["count"] == 0
    assert "names only" in files_tools.SEARCH_NOTE


@pytest.mark.anyio
async def test_a_folder_narrows_the_scope(clients: NcClients) -> None:
    with respx.mock as mock:
        route = mock.route(method="SEARCH", url=SEARCH_URL).mock(
            return_value=httpx.Response(207, text=_hits_207(1))
        )
        result = await files_tools.search(clients, query="budget", folder="/Docs")

    assert b"/files/alice/Docs" in route.calls[0].request.content
    assert result["folder"] == "/Docs"


@pytest.mark.anyio
async def test_a_limit_above_the_maximum_is_capped_instead_of_refused(
    clients: NcClients,
) -> None:
    with respx.mock as mock:
        route = mock.route(method="SEARCH", url=SEARCH_URL).mock(
            return_value=httpx.Response(207, text=_hits_207(3))
        )
        result = await files_tools.search(clients, query="budget", limit=5000)

    requested = route.calls[0].request.content
    assert f"<d:nresults>{files_tools.MAX_SEARCH_LIMIT + 1}</d:nresults>".encode() in requested
    assert result["count"] == 3


@pytest.mark.anyio
async def test_a_truncated_result_carries_a_handle_that_continues_correctly(
    clients: NcClients,
) -> None:
    with respx.mock as mock:
        route = mock.route(method="SEARCH", url=SEARCH_URL).mock(
            return_value=httpx.Response(207, text=_hits_207(30))
        )
        first = await files_tools.search(clients, query="budget", limit=10)

        assert first["truncated"] is True
        assert first["count"] == 10
        assert first["items"][0]["path"] == "/Docs/budget-000.md"
        assert b"<d:nresults>11</d:nresults>" in route.calls[0].request.content

        second = await files_tools.search(clients, query="budget", limit=10, cursor=first["next"])

    assert decode_cursor(first["next"]) == {"o": 10, "q": "budget", "f": "/"}
    assert second["items"][0]["path"] == "/Docs/budget-010.md"
    assert second["count"] == 10
    assert second["truncated"] is True


@pytest.mark.anyio
async def test_the_last_page_is_not_marked_as_truncated(clients: NcClients) -> None:
    with respx.mock as mock:
        mock.route(method="SEARCH", url=SEARCH_URL).mock(
            return_value=httpx.Response(207, text=_hits_207(12))
        )
        last = await files_tools.search(
            clients,
            query="budget",
            limit=10,
            cursor=encode_cursor({"o": 10, "q": "budget", "f": "/"}),
        )

    assert last["count"] == 2
    assert "truncated" not in last
    assert "next" not in last


@pytest.mark.anyio
async def test_a_page_at_the_fetch_ceiling_is_marked_truncated_without_a_cursor(
    clients: NcClients,
) -> None:
    """WR-02: a fetch clamped at MAX_SEARCH_FETCH that comes back full is not complete."""
    cursor = encode_cursor({"o": 480, "q": "budget", "f": "/"})
    with respx.mock as mock:
        route = mock.route(method="SEARCH", url=SEARCH_URL).mock(
            return_value=httpx.Response(207, text=_hits_207(files_tools.MAX_SEARCH_FETCH))
        )
        result = await files_tools.search(clients, query="budget", limit=25, cursor=cursor)

    requested = route.calls[0].request.content
    assert f"<d:nresults>{files_tools.MAX_SEARCH_FETCH}</d:nresults>".encode() in requested
    assert result["count"] == 20, "the window past the ceiling holds only the clamped rest"
    assert result["truncated"] is True
    assert "next" not in result, "no cursor: a later page cannot be served past the ceiling"
    assert files_tools.SEARCH_CAP_NOTE in result["note"]
    assert "names only" in result["note"], "the cap note must not displace the names-only note"


@pytest.mark.anyio
async def test_a_short_answer_at_the_ceiling_window_stays_complete(clients: NcClients) -> None:
    """The server returned fewer hits than the clamped fetch: the answer really is all."""
    cursor = encode_cursor({"o": 480, "q": "budget", "f": "/"})
    with respx.mock as mock:
        mock.route(method="SEARCH", url=SEARCH_URL).mock(
            return_value=httpx.Response(207, text=_hits_207(490))
        )
        result = await files_tools.search(clients, query="budget", limit=25, cursor=cursor)

    assert result["count"] == 10
    assert "truncated" not in result
    assert "next" not in result
    assert result["note"] == files_tools.SEARCH_NOTE


@pytest.mark.anyio
async def test_an_invalid_cursor_never_reaches_the_network(clients: NcClients) -> None:
    with respx.mock as mock:
        with pytest.raises(ToolError) as excinfo:
            await files_tools.search(clients, query="budget", cursor="nicht-base64")
        assert len(mock.calls) == 0

    assert excinfo.value.hint


@pytest.mark.anyio
async def test_a_cursor_from_another_query_is_refused(clients: NcClients) -> None:
    stale = encode_cursor({"o": 10, "q": "invoice", "f": "/"})
    with respx.mock as mock:
        with pytest.raises(ToolError) as excinfo:
            await files_tools.search(clients, query="budget", cursor=stale)
        assert len(mock.calls) == 0

    assert "cursor" in excinfo.value.message.lower()


@pytest.mark.anyio
@pytest.mark.parametrize("query", ["", "   "])
async def test_an_empty_query_is_refused_before_the_request(clients: NcClients, query: str) -> None:
    with respx.mock as mock:
        with pytest.raises(ToolError) as excinfo:
            await files_tools.search(clients, query=query)
        assert len(mock.calls) == 0

    assert excinfo.value.hint


@pytest.mark.anyio
async def test_a_folder_outside_the_home_never_reaches_the_network(clients: NcClients) -> None:
    with respx.mock as mock:
        with pytest.raises(ToolError) as excinfo:
            await files_tools.search(clients, query="budget", folder="/Docs/../../etc")
        assert len(mock.calls) == 0

    assert excinfo.value.hint


@pytest.mark.anyio
async def test_a_forbidden_search_reports_a_permission_hint(clients: NcClients) -> None:
    with respx.mock as mock:
        mock.route(method="SEARCH", url=SEARCH_URL).mock(return_value=httpx.Response(403))
        with pytest.raises(ToolError) as excinfo:
            await files_tools.search(clients, query="budget")

    assert "permission" in (excinfo.value.message + excinfo.value.hint).lower()


@pytest.mark.anyio
async def test_a_server_error_is_reported_without_the_body(clients: NcClients) -> None:
    with respx.mock as mock:
        mock.route(method="SEARCH", url=SEARCH_URL).mock(
            return_value=httpx.Response(503, text="<html>stack trace</html>")
        )
        with pytest.raises(ToolError) as excinfo:
            await files_tools.search(clients, query="budget")

    assert "503" in excinfo.value.message
    assert "stack trace" not in excinfo.value.message
    assert excinfo.value.hint
