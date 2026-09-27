"""The ``kein-ki`` guard on the file family: read, download, list and search (EXCL-01).

No ``patch_untagged`` here: every test mocks the real guard requests through
``guard_routes`` and runs the real guard of a fresh ``NcClients``. The core of each test is
a pair: a withheld path and a path that does not exist must answer with the same
``(message, hint, reason)``, and a list must not betray a withheld entry by its count,
its ``truncated`` or its cursor.
"""

from collections.abc import Awaitable, Callable
from typing import Any

import guard_routes
import httpx
import pytest
import respx

from mcp_connector.errors import ToolError
from mcp_connector.nextcloud import NcClients
from mcp_connector.nextcloud.clients import dav
from mcp_connector.nextcloud.credentials import Credentials
from mcp_connector.tools import files as files_tools
from mcp_connector.tools import withhold

BASE = guard_routes.BASE
USER = guard_routes.USER
HOME = f"{BASE}/remote.php/dav/files/{USER}"
SEARCH_URL = f"{BASE}/remote.php/dav/"

Tool = Callable[[NcClients, str], Awaitable[dict[str, Any]]]
TOOLS: dict[str, Tool] = {
    "read": lambda clients, path: files_tools.read(clients, path=path),
    "download": lambda clients, path: files_tools.download(clients, path=path),
}


@pytest.fixture(autouse=True)
def _fresh_tag_cache() -> None:
    guard_routes.reset()


def _clients() -> NcClients:
    """One bundle per tool call, as ``deps.resolve_clients`` builds it: one guard each."""
    return NcClients(
        client=httpx.AsyncClient(follow_redirects=False),
        creds=Credentials(BASE, USER, "app-password-test"),
    )


def _tuple(err: ToolError) -> tuple[str, str, str]:
    return (err.message, err.hint, err.reason)


def _props(
    *,
    fileid: str,
    folder: bool = False,
    content_type: str = "text/plain",
    length: int = 5,
    name: str = "",
) -> str:
    resourcetype = "<d:collection/>" if folder else ""
    type_prop = "" if folder else f"<d:getcontenttype>{content_type}</d:getcontenttype>"
    name_prop = f"<d:displayname>{name}</d:displayname>" if name else ""
    return (
        f"{name_prop}<d:getcontentlength>{length}</d:getcontentlength>{type_prop}"
        f"<d:resourcetype>{resourcetype}</d:resourcetype><oc:fileid>{fileid}</oc:fileid>"
    )


def _multistatus(*entries: tuple[str, str]) -> str:
    """A 207 body; each entry is (path below the home, props)."""
    responses = "".join(
        f"<d:response><d:href>/remote.php/dav/files/{USER}{path}</d:href>"
        f"<d:propstat><d:prop>{props}</d:prop>"
        "<d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response>"
        for path, props in entries
    )
    return (
        '<?xml version="1.0"?><d:multistatus xmlns:d="DAV:" '
        f'xmlns:oc="http://owncloud.org/ns">{responses}</d:multistatus>'
    )


def _stat_route(mock: respx.MockRouter, path: str, **props: Any) -> respx.Route:
    return mock.route(method="PROPFIND", url=f"{HOME}{path}").mock(
        return_value=httpx.Response(207, text=_multistatus((path, _props(**props))))
    )


def _missing_route(mock: respx.MockRouter, path: str) -> respx.Route:
    return mock.route(method="PROPFIND", url=f"{HOME}{path}").mock(return_value=httpx.Response(404))


def _get_route(mock: respx.MockRouter, path: str) -> respx.Route:
    return mock.route(method="GET", url=f"{HOME}{path}").mock(
        return_value=httpx.Response(200, content=b"hello")
    )


async def _refusal(tool: Tool, path: str) -> ToolError:
    with pytest.raises(ToolError) as caught:
        await tool(_clients(), path)
    return caught.value


# --- files_read / files_download -----------------------------------------------------------


@pytest.mark.anyio
@pytest.mark.parametrize("name", ["read", "download"])
async def test_untagged_answers_as_before_and_sends_no_report(name: str) -> None:
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as mock:
        listing = guard_routes.untagged(mock)
        report = mock.route(method="REPORT", url=guard_routes.HOME)
        _stat_route(mock, "/Docs/notes.txt", fileid="11")
        get = _get_route(mock, "/Docs/notes.txt")
        result = await TOOLS[name](_clients(), "/Docs/notes.txt")

    assert result["path"] == "/Docs/notes.txt"
    assert result["size"] == 5
    assert result["truncated"] is False
    assert listing.call_count == 1
    assert report.call_count == 0
    assert get.call_count == 1


@pytest.mark.anyio
@pytest.mark.parametrize("name", ["read", "download"])
async def test_a_tagged_file_answers_like_a_missing_one(name: str) -> None:
    tool = TOOLS[name]
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as mock:
        _, report = guard_routes.active(mock, ("Docs/geheim.txt", "901", False))
        _stat_route(mock, "/Docs/geheim.txt", fileid="901")
        get = _get_route(mock, "/Docs/geheim.txt")
        tagged = await _refusal(tool, "/Docs/geheim.txt")
        assert report.call_count == 1, "one REPORT per tool call"

    with respx.mock(assert_all_mocked=True, assert_all_called=False) as mock:
        guard_routes.active(mock, ("Docs/geheim.txt", "901", False))
        _missing_route(mock, "/Docs/geheim.txt")
        missing = await _refusal(tool, "/Docs/geheim.txt")

    assert _tuple(tagged) == _tuple(missing)
    assert _tuple(tagged) == _tuple(dav.not_found("/Docs/geheim.txt"))
    assert get.call_count == 0


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("name", "path"), [("read", "/Projekt/a.txt"), ("download", "/Projekt/a.pdf")]
)
async def test_a_file_below_a_tagged_folder_answers_like_a_missing_one(
    name: str, path: str
) -> None:
    tool = TOOLS[name]
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as mock:
        guard_routes.active(mock, ("Projekt", "900", True))
        _stat_route(mock, path, fileid="905")
        get = _get_route(mock, path)
        below = await _refusal(tool, path)

    with respx.mock(assert_all_mocked=True, assert_all_called=False) as mock:
        guard_routes.active(mock, ("Projekt", "900", True))
        _missing_route(mock, path)
        missing = await _refusal(tool, path)

    assert _tuple(below) == _tuple(missing)
    assert get.call_count == 0


@pytest.mark.anyio
@pytest.mark.parametrize("name", ["read", "download"])
async def test_a_tagged_folder_is_not_reported_as_a_folder(name: str) -> None:
    """No form check runs before the tag: "is a folder" would confirm the folder exists."""
    tool = TOOLS[name]
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as mock:
        guard_routes.active(mock, ("Projekt", "900", True))
        _stat_route(mock, "/Projekt", fileid="900", folder=True)
        tagged = await _refusal(tool, "/Projekt")

    with respx.mock(assert_all_mocked=True, assert_all_called=False) as mock:
        guard_routes.active(mock, ("Projekt", "900", True))
        _missing_route(mock, "/Projekt")
        missing = await _refusal(tool, "/Projekt")

    assert "folder" not in tagged.message
    assert _tuple(tagged) == _tuple(missing)


@pytest.mark.anyio
async def test_a_tagged_binary_file_is_not_reported_as_not_text() -> None:
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as mock:
        guard_routes.active(mock, ("Docs/scan.pdf", "902", False))
        _stat_route(mock, "/Docs/scan.pdf", fileid="902", content_type="application/pdf")
        tagged = await _refusal(TOOLS["read"], "/Docs/scan.pdf")

    with respx.mock(assert_all_mocked=True, assert_all_called=False) as mock:
        guard_routes.active(mock, ("Docs/scan.pdf", "902", False))
        _missing_route(mock, "/Docs/scan.pdf")
        missing = await _refusal(TOOLS["read"], "/Docs/scan.pdf")

    assert "not text" not in tagged.message
    assert _tuple(tagged) == _tuple(missing)


@pytest.mark.anyio
async def test_a_tagged_file_offset_is_not_checked_first() -> None:
    """An offset past the end would tell the size of a withheld file."""
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as mock:
        guard_routes.active(mock, ("Docs/geheim.txt", "901", False))
        _stat_route(mock, "/Docs/geheim.txt", fileid="901")
        with pytest.raises(ToolError) as caught:
            await files_tools.read(_clients(), path="/Docs/geheim.txt", offset=99)

    assert _tuple(caught.value) == _tuple(dav.not_found("/Docs/geheim.txt"))


@pytest.mark.anyio
@pytest.mark.parametrize("name", ["read", "download"])
async def test_the_fileid_decides_when_the_spelling_differs(name: str) -> None:
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as mock:
        guard_routes.active(mock, ("docs/Geheim.txt", "901", False))
        _stat_route(mock, "/Docs/geheim.txt", fileid="901")
        get = _get_route(mock, "/Docs/geheim.txt")
        tagged = await _refusal(TOOLS[name], "/Docs/geheim.txt")

    assert _tuple(tagged) == _tuple(dav.not_found("/Docs/geheim.txt"))
    assert get.call_count == 0


@pytest.mark.anyio
@pytest.mark.parametrize("name", ["read", "download"])
async def test_unverifiable_refuses_existing_and_missing_paths_alike(name: str) -> None:
    tool = TOOLS[name]
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as mock:
        guard_routes.unverifiable(mock)
        _stat_route(mock, "/Docs/notes.txt", fileid="11")
        get = _get_route(mock, "/Docs/notes.txt")
        existing = await _refusal(tool, "/Docs/notes.txt")

    with respx.mock(assert_all_mocked=True, assert_all_called=False) as mock:
        guard_routes.unverifiable(mock)
        _missing_route(mock, "/Docs/fehlt.txt")
        missing = await _refusal(tool, "/Docs/fehlt.txt")

    assert _tuple(existing) == _tuple(missing)
    assert _tuple(existing) == _tuple(withhold.unavailable_error())
    assert get.call_count == 0


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("name", "kwargs"),
    [
        ("read", {"offset": -1}),
        ("read", {"max_bytes": 0}),
        ("download", {"offset": -1}),
        ("download", {"max_bytes": files_tools.HARD_DOWNLOAD_BYTES + 1}),
    ],
)
async def test_input_errors_still_come_before_any_request(
    name: str, kwargs: dict[str, int]
) -> None:
    tool = files_tools.read if name == "read" else files_tools.download
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as mock:
        with pytest.raises(ToolError):
            await tool(_clients(), path="/Docs/notes.txt", **kwargs)
        assert mock.calls.call_count == 0
