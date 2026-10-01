"""The ``kein-ki`` guard on the file family: read, download, list and search (EXCL-01).

No ``patch_untagged`` here: every test mocks the real guard requests through
``guard_routes`` and runs the real guard of a fresh ``NcClients``. The core of each test is
a pair: a withheld path and a path that does not exist must answer with the same
``(message, hint, reason)``, and a list must not betray a withheld entry by its count,
its ``truncated`` or its cursor.
"""

import json
import re
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
    "read_as_markdown": lambda clients, path: files_tools.read_as_markdown(clients, path=path),
}
#: The readers of one path; every refusal pair below holds for each of them. The fork has no
#: inline download (fork olivia): files_download hands out a link, tested in test_olivia_*.
READERS = ["read", "read_as_markdown"]


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
@pytest.mark.parametrize("name", ["read"])
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
@pytest.mark.parametrize("name", READERS)
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
    ("name", "path"),
    [
        ("read", "/Projekt/a.txt"),
        ("read_as_markdown", "/Projekt/a.docx"),
    ],
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
@pytest.mark.parametrize("name", READERS)
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
async def test_a_tagged_text_file_is_not_reported_as_text_already() -> None:
    """The mirror image for files_read_as_markdown: its type refusal must not come first."""
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as mock:
        guard_routes.active(mock, ("Docs/geheim.txt", "901", False))
        _stat_route(mock, "/Docs/geheim.txt", fileid="901")
        tagged = await _refusal(TOOLS["read_as_markdown"], "/Docs/geheim.txt")

    with respx.mock(assert_all_mocked=True, assert_all_called=False) as mock:
        guard_routes.active(mock, ("Docs/geheim.txt", "901", False))
        _missing_route(mock, "/Docs/geheim.txt")
        missing = await _refusal(TOOLS["read_as_markdown"], "/Docs/geheim.txt")

    assert "text already" not in tagged.message
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
@pytest.mark.parametrize("name", READERS)
async def test_the_fileid_decides_when_the_spelling_differs(name: str) -> None:
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as mock:
        guard_routes.active(mock, ("docs/Geheim.txt", "901", False))
        _stat_route(mock, "/Docs/geheim.txt", fileid="901")
        get = _get_route(mock, "/Docs/geheim.txt")
        tagged = await _refusal(TOOLS[name], "/Docs/geheim.txt")

    assert _tuple(tagged) == _tuple(dav.not_found("/Docs/geheim.txt"))
    assert get.call_count == 0


@pytest.mark.anyio
@pytest.mark.parametrize("name", READERS)
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
    ],
)
async def test_input_errors_still_come_before_any_request(
    name: str, kwargs: dict[str, Any]
) -> None:
    tool = files_tools.read
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as mock:
        with pytest.raises(ToolError):
            await tool(_clients(), path="/Docs/notes.txt", **kwargs)
        assert mock.calls.call_count == 0


# --- files_list ----------------------------------------------------------------------------


def _folder(path: str, fileid: str, *children: tuple[str, str, bool]) -> str:
    """A Depth-1 answer: the folder itself plus (name, fileid, is_folder) children."""
    entries = [(path, _props(fileid=fileid, folder=True))]
    entries += [
        (f"{path}/{name}", _props(fileid=child_id, folder=is_folder, name=name))
        for name, child_id, is_folder in children
    ]
    return _multistatus(*entries)


def _listing_route(mock: respx.MockRouter, path: str, body: str) -> respx.Route:
    return mock.route(method="PROPFIND", url=f"{HOME}{path}").mock(
        return_value=httpx.Response(207, text=body)
    )


DOCS = _folder(
    "/Docs",
    "10",
    ("a.txt", "11", False),
    ("geheim.txt", "901", False),
    ("Projekt", "900", True),
    ("z.txt", "12", False),
)
DOCS_TAGS = (("Docs/geheim.txt", "901", False), ("Docs/Projekt", "900", True))


async def _list(path: str, **kwargs: Any) -> dict[str, Any]:
    return await files_tools.list_dir(_clients(), path=path, **kwargs)


async def _list_refusal(path: str) -> ToolError:
    with pytest.raises(ToolError) as caught:
        await _list(path)
    return caught.value


@pytest.mark.anyio
async def test_list_leaves_tagged_children_out_and_counts_only_visible_ones() -> None:
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as mock:
        _, report = guard_routes.active(mock, *DOCS_TAGS)
        _listing_route(mock, "/Docs", DOCS)
        result = await _list("/Docs", limit=2)

    assert [item["path"] for item in result["items"]] == ["/Docs/a.txt", "/Docs/z.txt"]
    assert result["count"] == 2
    assert "truncated" not in result
    assert "next" not in result
    assert report.call_count == 1
    dumped = json.dumps(result)
    assert "withheld" not in dumped
    assert "exclusion" not in dumped
    assert "degraded" not in result


@pytest.mark.anyio
async def test_list_truncated_and_next_rest_on_the_filtered_list() -> None:
    children = [(f"v{index}.txt", str(20 + index), False) for index in range(1, 6)]
    children += [(f"t{index}.txt", str(950 + index), False) for index in range(1, 4)]
    body = _folder("/Docs", "10", *children)
    tags = tuple((f"Docs/t{index}.txt", str(950 + index), False) for index in range(1, 4))

    pages: list[dict[str, Any]] = []
    cursor: str | None = None
    for _ in range(3):
        with respx.mock(assert_all_mocked=True, assert_all_called=False) as mock:
            guard_routes.active(mock, *tags)
            _listing_route(mock, "/Docs", body)
            page = await _list("/Docs", limit=2, cursor=cursor)
        pages.append(page)
        cursor = page.get("next")

    assert [[item["name"] for item in page["items"]] for page in pages] == [
        ["v1.txt", "v2.txt"],
        ["v3.txt", "v4.txt"],
        ["v5.txt"],
    ]
    assert pages[0]["truncated"] is True
    assert pages[1]["truncated"] is True
    assert "truncated" not in pages[2]
    assert "next" not in pages[2]


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("path", "body"),
    [
        ("/Projekt", _folder("/Projekt", "900", ("a.txt", "905", False))),
        ("/Projekt/Unter", _folder("/Projekt/Unter", "906")),
        ("/Docs/geheim.txt", _multistatus(("/Docs/geheim.txt", _props(fileid="901")))),
    ],
)
async def test_a_tagged_list_target_answers_like_a_missing_one(path: str, body: str) -> None:
    """Also a tagged file: "is a file, not a folder" would confirm that it exists."""
    tags = (("Projekt", "900", True), ("Docs/geheim.txt", "901", False))
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as mock:
        guard_routes.active(mock, *tags)
        _listing_route(mock, path, body)
        tagged = await _list_refusal(path)

    with respx.mock(assert_all_mocked=True, assert_all_called=False) as mock:
        guard_routes.active(mock, *tags)
        _missing_route(mock, path)
        missing = await _list_refusal(path)

    assert _tuple(tagged) == _tuple(missing)
    assert _tuple(tagged) == _tuple(dav.not_found(path))


@pytest.mark.anyio
async def test_list_unverifiable_answers_the_same_for_existing_and_missing_folders() -> None:
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as mock:
        guard_routes.unverifiable(mock)
        _listing_route(mock, "/Docs", DOCS)
        existing = await _list("/Docs", limit=1)

    with respx.mock(assert_all_mocked=True, assert_all_called=False) as mock:
        guard_routes.unverifiable(mock)
        _missing_route(mock, "/Docs")
        missing = await _list("/Docs", limit=1)

    assert existing == missing
    assert existing == {
        "path": "/Docs",
        "count": 0,
        "items": [],
        "degraded": [withhold.degraded_entry("source")],
    }


@pytest.mark.anyio
async def test_list_untagged_is_json_equal_to_the_answer_without_a_guard() -> None:
    with pytest.MonkeyPatch.context() as patch:
        guard_routes.patch_untagged(patch)
        with respx.mock(assert_all_mocked=True, assert_all_called=False) as mock:
            _listing_route(mock, "/Docs", DOCS)
            baseline = await _list("/Docs", limit=2)

    with respx.mock(assert_all_mocked=True, assert_all_called=False) as mock:
        guard_routes.untagged(mock)
        report = mock.route(method="REPORT", url=guard_routes.HOME)
        _listing_route(mock, "/Docs", DOCS)
        result = await _list("/Docs", limit=2)

    assert json.dumps(result) == json.dumps(baseline)
    assert result["truncated"] is True
    assert report.call_count == 0


# --- files_search --------------------------------------------------------------------------


def _hits(indices: range) -> str:
    return _multistatus(
        *(
            (
                f"/Docs/budget-{index}.md",
                _props(fileid=str(5000 + index), name=f"budget-{index}.md"),
            )
            for index in indices
        )
    )


#: budget-1 and budget-2 carry the tag.
SEARCH_TAGS = (("Docs/budget-1.md", "5001", False), ("Docs/budget-2.md", "5002", False))


def _sent_limits(route: respx.Route) -> list[int]:
    limits = []
    for call in route.calls:
        found = re.search(rb"nresults>(\d+)<", call.request.content)
        assert found is not None
        limits.append(int(found[1]))
    return limits


def _names(result: dict[str, Any]) -> list[str]:
    return [item["name"] for item in result["items"]]


@pytest.mark.anyio
async def test_search_fetches_more_when_tagged_hits_leave_the_window_short() -> None:
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as mock:
        _, report = guard_routes.active(mock, *SEARCH_TAGS)
        search = mock.route(method="SEARCH", url=SEARCH_URL).mock(
            side_effect=[
                httpx.Response(207, text=_hits(range(4))),
                httpx.Response(207, text=_hits(range(8))),
            ]
        )
        result = await files_tools.search(_clients(), query="budget", limit=3)

    assert _sent_limits(search) == [4, 8]
    assert report.call_count == 1, "the second SEARCH shares the scope, no second REPORT"
    assert _names(result) == ["budget-0.md", "budget-3.md", "budget-4.md"]
    assert result["count"] == 3
    assert result["truncated"] is True
    assert "next" in result


@pytest.mark.anyio
async def test_search_truncated_never_comes_from_the_raw_list() -> None:
    """Four raw hits for a window of three, but only three visible: nothing is truncated."""
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as mock:
        guard_routes.active(mock, *SEARCH_TAGS)
        search = mock.route(method="SEARCH", url=SEARCH_URL).mock(
            side_effect=[
                httpx.Response(207, text=_hits(range(4))),
                httpx.Response(207, text=_hits(range(5))),
            ]
        )
        result = await files_tools.search(_clients(), query="budget", limit=3)

    assert _sent_limits(search) == [4, 8]
    assert _names(result) == ["budget-0.md", "budget-3.md", "budget-4.md"]
    assert "truncated" not in result
    assert "next" not in result
    dumped = json.dumps(result)
    assert "withheld" not in dumped
    assert "exclusion" not in dumped


@pytest.mark.anyio
async def test_search_short_raw_list_needs_no_second_search() -> None:
    """Three raw hits for a fetch of four: nothing more exists, one visible remains."""
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as mock:
        guard_routes.active(mock, *SEARCH_TAGS)
        search = mock.route(method="SEARCH", url=SEARCH_URL).mock(
            return_value=httpx.Response(207, text=_hits(range(3)))
        )
        result = await files_tools.search(_clients(), query="budget", limit=3)

    assert search.call_count == 1
    assert result["count"] == 1
    assert _names(result) == ["budget-0.md"]
    assert "truncated" not in result


@pytest.mark.anyio
async def test_search_next_page_counts_visible_hits_only() -> None:
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as mock:
        guard_routes.active(mock, *SEARCH_TAGS)
        mock.route(method="SEARCH", url=SEARCH_URL).mock(
            return_value=httpx.Response(207, text=_hits(range(6)))
        )
        first = await files_tools.search(_clients(), query="budget", limit=2)
        second = await files_tools.search(_clients(), query="budget", limit=2, cursor=first["next"])

    assert _names(first) == ["budget-0.md", "budget-3.md"]
    assert _names(second) == ["budget-4.md", "budget-5.md"]
    assert "truncated" not in second


@pytest.mark.anyio
async def test_search_unverifiable_answers_empty_with_one_degraded_entry() -> None:
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as mock:
        guard_routes.unverifiable(mock)
        mock.route(method="SEARCH", url=SEARCH_URL).mock(
            return_value=httpx.Response(207, text=_hits(range(10)))
        )
        result = await files_tools.search(_clients(), query="budget", limit=3)

    assert result == {
        "query": "budget",
        "folder": "/",
        "count": 0,
        "items": [],
        "note": files_tools.SEARCH_NOTE,
        "degraded": [withhold.degraded_entry("source")],
    }


@pytest.mark.anyio
async def test_search_untagged_is_json_equal_and_sends_one_search() -> None:
    with pytest.MonkeyPatch.context() as patch:
        guard_routes.patch_untagged(patch)
        with respx.mock(assert_all_mocked=True, assert_all_called=False) as mock:
            mock.route(method="SEARCH", url=SEARCH_URL).mock(
                return_value=httpx.Response(207, text=_hits(range(4)))
            )
            baseline = await files_tools.search(_clients(), query="budget", limit=3)

    with respx.mock(assert_all_mocked=True, assert_all_called=False) as mock:
        guard_routes.untagged(mock)
        report = mock.route(method="REPORT", url=guard_routes.HOME)
        search = mock.route(method="SEARCH", url=SEARCH_URL).mock(
            return_value=httpx.Response(207, text=_hits(range(4)))
        )
        result = await files_tools.search(_clients(), query="budget", limit=3)

    assert json.dumps(result) == json.dumps(baseline)
    assert result["truncated"] is True
    assert search.call_count == 1
    assert report.call_count == 0


# --- files_search with a tagged folder as its root (B5, D-28-19) ---------------------------

#: The SEARCH answer of an invented scope, as nc35 gave it in 28-01 (A3): a Sabre 404.
_SEARCH_404 = (
    '<?xml version="1.0" encoding="utf-8"?>'
    '<d:error xmlns:d="DAV:" xmlns:s="http://sabredav.org/ns">'
    "<s:exception>Sabre\\DAV\\Exception\\NotFound</s:exception>"
    "<s:message>File with name /Projekt could not be located</s:message></d:error>"
)
#: The SEARCH answer of a tagged scope in 28-01: an empty 207.
_SEARCH_EMPTY = '<?xml version="1.0"?><d:multistatus xmlns:d="DAV:"/>'
FOLDER_TAGS = (("Projekt", "900", True),)


async def _search_refusal(folder: str, status: int, body: str) -> tuple[ToolError, int]:
    """One files_search under an active guard; the refusal and the number of SEARCHes."""
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as mock:
        guard_routes.active(mock, *FOLDER_TAGS)
        search = mock.route(method="SEARCH", url=SEARCH_URL).mock(
            return_value=httpx.Response(status, text=body)
        )
        with pytest.raises(ToolError) as caught:
            await files_tools.search(_clients(), query="budget", folder=folder)
    return caught.value, search.call_count


@pytest.mark.anyio
@pytest.mark.parametrize("folder", ["/Projekt", "/Projekt/Unter"])
async def test_search_in_a_tagged_folder_answers_like_an_invented_folder(folder: str) -> None:
    """D-28-19: the tagged root answers up front with the 404 of an invented root.

    Before the fix the tagged folder gave an empty hit list without an error, while the
    invented one failed with ``File not found: /files/<user>/<folder>`` (28-01, A3). The
    mocked answers are the ones nc35 gave: an empty 207 and a Sabre 404.
    """
    tagged, tagged_calls = await _search_refusal(folder, 207, _SEARCH_EMPTY)
    invented, invented_calls = await _search_refusal(folder, 404, _SEARCH_404)

    assert _tuple(tagged) == _tuple(invented)
    assert _tuple(tagged) == _tuple(dav.not_found(f"/files/{USER}{folder}"))
    assert tagged_calls == invented_calls == 1, "no own SEARCH, no extra request"


@pytest.mark.anyio
async def test_search_in_a_tagged_folder_and_an_invented_one_differ_only_in_the_path() -> None:
    """Two different folders: the answers are equal once the two paths are replaced."""
    tagged, _ = await _search_refusal("/Projekt", 207, _SEARCH_EMPTY)
    invented, _ = await _search_refusal("/erfunden-1", 404, _SEARCH_404)

    tagged_text = tagged.message.replace("/Projekt", "<F>")
    invented_text = invented.message.replace("/erfunden-1", "<F>")
    assert tagged_text == invented_text
    assert (tagged.hint, tagged.reason) == (invented.hint, invented.reason)


@pytest.mark.anyio
async def test_search_in_a_visible_sibling_of_a_tagged_folder_is_not_refused() -> None:
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as mock:
        guard_routes.active(mock, *FOLDER_TAGS)
        mock.route(method="SEARCH", url=SEARCH_URL).mock(
            return_value=httpx.Response(207, text=_hits(range(1)))
        )
        result = await files_tools.search(_clients(), query="budget", folder="/Projekt2")

    assert result["count"] == 1


@pytest.mark.anyio
async def test_search_unverifiable_answers_tagged_and_invented_folders_alike() -> None:
    answers = []
    for status, body in ((207, _SEARCH_EMPTY), (404, _SEARCH_404)):
        with respx.mock(assert_all_mocked=True, assert_all_called=False) as mock:
            guard_routes.unverifiable(mock)
            mock.route(method="SEARCH", url=SEARCH_URL).mock(
                return_value=httpx.Response(status, text=body)
            )
            answers.append(await files_tools.search(_clients(), query="budget", folder="/Projekt"))

    assert answers[0] == answers[1]
    assert answers[0]["degraded"] == [withhold.degraded_entry("source")]
    assert answers[0]["count"] == 0
