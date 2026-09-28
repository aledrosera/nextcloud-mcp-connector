"""GATE-03 on the unit level, family files: a tagged target answers like a missing one.

For every pair case of the family ``files`` in ``tool_classes.PAIR_CASES`` the tool is called
through the real registry (``Client(mcp)``) twice: once with a target tagged ``kein-ki`` and
once with a target that does not exist. What is compared is the whole ``CallToolResult``
after ``result.model_dump(mode="json", by_alias=True)``: every text part, the structured
content and ``isError``. Before the comparison ``result_shapes.normalised`` replaces the
requested id by ``<ID>``, in the definition of ``requested_forms``: "requested id = the
argument, its path prefixes and for fetch the bare id". Nothing else is replaced.

The guard requests are mocked for real through ``guard_routes`` (no ``patch_untagged``), in
five states: active, 412 once (listed anew and then active), 412 twice, timeout and 5xx. The
response time is not part of the comparison (D-28-12); ``normalised`` carries no time value,
and ``test_time_is_not_part_of_the_comparison`` pins that.

A request that no route of a side expects is caught by a last catch-all route and fails the
test, so two sides that both run into the same unmocked request cannot pass as equal.

``tests/contract`` is on the pytest path (``pyproject.toml``) but not on the one of pyright,
hence the ``reportMissingImports`` ignore on the imports from there.
"""

from collections.abc import Callable, Iterator
from typing import Any

import guard_routes
import httpx
import pytest
import respx
from mcp import Client
from result_shapes import normalised  # pyright: ignore[reportMissingImports]

from mcp_connector.nextcloud import capabilities
from mcp_connector.server import mcp

BASE = guard_routes.BASE
USER = guard_routes.USER
SECRET = "app-password-test"
FILES = f"{BASE}/remote.php/dav/files/{USER}"
DAV_ROOT = f"{BASE}/remote.php/dav/"
UPLOADS = f"{BASE}/remote.php/dav/uploads/{USER}/"
CONTENT = b"streng vertraulich\n"

Node = tuple[str, str, bool]
Mocks = Callable[[respx.MockRouter], None]

GUARD_MODES = ("active", "stale_once", "stale_twice", "timeout", "server_error")

TAGGED_FILE: Node = ("Docs/geheim.txt", "901", False)
TAGGED_FOLDER: Node = ("Projekt", "900", True)
TAGS = (TAGGED_FILE, TAGGED_FOLDER)


@pytest.fixture(autouse=True)
def _fresh_caches() -> None:
    guard_routes.reset()
    capabilities.clear_cache()


@pytest.fixture(autouse=True)
def stdio_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """The environment an in-memory client call resolves its credentials from."""
    monkeypatch.setenv("NC_MCP_URL", BASE)
    monkeypatch.setenv("NC_MCP_USER", USER)
    monkeypatch.setenv("NC_MCP_APP_PASSWORD", SECRET)
    monkeypatch.delenv("NC_MCP_STATIC_BEARER", raising=False)


# --- guard states ---------------------------------------------------------------------------


def _stale_once(mock: respx.MockRouter, *nodes: Node) -> None:
    """412 on the first REPORT, then the tagged nodes: the guard lists anew and is active."""
    mock.route(method="PROPFIND", url=guard_routes.TAGS).mock(
        return_value=guard_routes.listed(
            guard_routes.tag_list(guard_routes.KEIN_KI, guard_routes.OTHER_TAG)
        )
    )
    answers = iter([httpx.Response(412)])

    def report(_request: httpx.Request) -> httpx.Response:
        return next(answers, None) or guard_routes.listed(guard_routes.report_207(*nodes))

    mock.route(method="REPORT", url=guard_routes.HOME).mock(side_effect=report)


def arm_guard(mock: respx.MockRouter, mode: str, *nodes: Node) -> None:
    """Mock the guard requests of one of the five states of ``GUARD_MODES``."""
    if mode == "active":
        guard_routes.active(mock, *nodes)
    elif mode == "stale_once":
        _stale_once(mock, *nodes)
    elif mode == "stale_twice":
        guard_routes.stale(mock)
    elif mode == "timeout":
        guard_routes.timeout(mock)
    elif mode == "server_error":
        guard_routes.unverifiable(mock)
    else:  # pragma: no cover - a typo in a parametrisation
        raise AssertionError(f"unknown guard mode {mode!r}")


@pytest.fixture
def unexpected() -> Iterator[list[str]]:
    """Requests no route of a side expected; every test asserts the list stays empty."""
    found: list[str] = []
    yield found
    assert not found, f"unmocked requests: {found}"


async def _call(
    tool: str,
    args: dict[str, Any],
    mode: str,
    mocks: Mocks,
    unexpected: list[str],
) -> Any:
    guard_routes.reset()
    capabilities.clear_cache()
    with respx.mock(assert_all_called=False) as mock:
        arm_guard(mock, mode, *TAGS)
        mocks(mock)

        def catch_all(request: httpx.Request) -> httpx.Response:
            unexpected.append(f"{request.method} {request.url}")
            return httpx.Response(599)

        mock.route().mock(side_effect=catch_all)
        async with Client(mcp) as client:
            return await client.call_tool(tool, args)


async def pair(
    tool: str,
    tagged_args: dict[str, Any],
    unknown_args: dict[str, Any],
    tagged_value: str,
    unknown_value: str,
    mock_tagged: Mocks,
    mock_unknown: Mocks,
    mode: str,
    unexpected: list[str],
) -> tuple[str, str]:
    """Both answers of one pair, each normalised on its own requested id."""
    tagged = await _call(tool, tagged_args, mode, mock_tagged, unexpected)
    unknown = await _call(tool, unknown_args, mode, mock_unknown, unexpected)
    return normalised(tagged, tagged_value), normalised(unknown, unknown_value)


def _assert_equal(tagged: str, unknown: str) -> None:
    assert tagged == unknown, f"tagged:  {tagged}\nunknown: {unknown}"


# --- WebDAV answers -------------------------------------------------------------------------


def _props(*, fileid: str, folder: bool = False, name: str = "") -> str:
    resourcetype = "<d:collection/>" if folder else ""
    type_prop = "" if folder else "<d:getcontenttype>text/plain</d:getcontenttype>"
    name_prop = f"<d:displayname>{name}</d:displayname>" if name else ""
    return (
        f"{name_prop}<d:getcontentlength>{len(CONTENT)}</d:getcontentlength>{type_prop}"
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


def _existing_file(path: str, fileid: str) -> Mocks:
    """PROPFIND and GET of a file that exists; the GET is never reached for a tagged one."""

    def mocks(mock: respx.MockRouter) -> None:
        mock.route(method="PROPFIND", url=f"{FILES}{path}").mock(
            return_value=httpx.Response(207, text=_multistatus((path, _props(fileid=fileid))))
        )
        mock.route(method="GET", url=f"{FILES}{path}").mock(
            return_value=httpx.Response(200, content=CONTENT)
        )

    return mocks


def _missing(path: str) -> Mocks:
    def mocks(mock: respx.MockRouter) -> None:
        mock.route(method="PROPFIND", url=f"{FILES}{path}").mock(return_value=httpx.Response(404))

    return mocks


def _existing_folder(path: str, fileid: str, *children: tuple[str, str]) -> Mocks:
    """A Depth-1 listing: the folder plus (name, fileid) file children."""
    entries = [(path, _props(fileid=fileid, folder=True))]
    entries += [(f"{path}/{name}", _props(fileid=cid, name=name)) for name, cid in children]
    body = _multistatus(*entries)

    def mocks(mock: respx.MockRouter) -> None:
        mock.route(method="PROPFIND", url=f"{FILES}{path}").mock(
            return_value=httpx.Response(207, text=body)
        )

    return mocks


#: (tagged path, its fileid) for a tagged file and a file below a tagged folder.
TAGGED_READ_TARGETS = (("/Docs/geheim.txt", "901"), ("/Projekt/a.txt", "905"))
UNKNOWN_PATH = "/Docs/fehlt.txt"


# --- files_read / files_download ------------------------------------------------------------


@pytest.mark.anyio
@pytest.mark.parametrize("mode", GUARD_MODES)
async def test_files_read_answers_a_tagged_path_like_a_missing_one(
    mode: str, unexpected: list[str]
) -> None:
    for path, fileid in TAGGED_READ_TARGETS:
        tagged, unknown = await pair(
            "files_read",
            {"path": path},
            {"path": UNKNOWN_PATH},
            path,
            UNKNOWN_PATH,
            _existing_file(path, fileid),
            _missing(UNKNOWN_PATH),
            mode,
            unexpected,
        )
        _assert_equal(tagged, unknown)
        assert '"isError": true' in tagged


@pytest.mark.anyio
@pytest.mark.parametrize("mode", GUARD_MODES)
async def test_files_download_answers_a_tagged_path_like_a_missing_one(
    mode: str, unexpected: list[str]
) -> None:
    for path, fileid in TAGGED_READ_TARGETS:
        tagged, unknown = await pair(
            "files_download",
            {"path": path},
            {"path": UNKNOWN_PATH},
            path,
            UNKNOWN_PATH,
            _existing_file(path, fileid),
            _missing(UNKNOWN_PATH),
            mode,
            unexpected,
        )
        _assert_equal(tagged, unknown)
        assert '"isError": true' in tagged


# --- files_list -----------------------------------------------------------------------------


@pytest.mark.anyio
@pytest.mark.parametrize("mode", GUARD_MODES)
async def test_files_list_answers_a_tagged_folder_like_an_invented_one(
    mode: str, unexpected: list[str]
) -> None:
    targets = (
        ("/Projekt", _existing_folder("/Projekt", "900", ("a.txt", "905"))),
        ("/Projekt/Unter", _existing_folder("/Projekt/Unter", "906")),
    )
    for path, mocks in targets:
        tagged, unknown = await pair(
            "files_list",
            {"path": path},
            {"path": "/erfunden-1"},
            path,
            "/erfunden-1",
            mocks,
            _missing("/erfunden-1"),
            mode,
            unexpected,
        )
        _assert_equal(tagged, unknown)


# --- fetch(file:) ---------------------------------------------------------------------------


def _found(fileid: str, path: str) -> httpx.Response:
    name = path.rsplit("/", 1)[-1]
    return httpx.Response(207, text=_multistatus((path, _props(fileid=fileid, name=name))))


def _nothing() -> httpx.Response:
    return httpx.Response(207, text=_multistatus())


def _fetchable(fileid: str, path: str) -> Mocks:
    """Lookup, stat and content of one file."""

    def mocks(mock: respx.MockRouter) -> None:
        mock.route(method="SEARCH", url=DAV_ROOT).mock(return_value=_found(fileid, path))
        _existing_file(path, fileid)(mock)

    return mocks


def _no_file(mock: respx.MockRouter) -> None:
    mock.route(method="SEARCH", url=DAV_ROOT).mock(return_value=_nothing())


UNKNOWN_FILEID = "999999999"


@pytest.mark.anyio
@pytest.mark.parametrize("mode", GUARD_MODES)
async def test_fetch_file_answers_a_tagged_id_like_an_unknown_one(
    mode: str, unexpected: list[str]
) -> None:
    for path, fileid in TAGGED_READ_TARGETS:
        tagged, unknown = await pair(
            "fetch",
            {"id": f"file:{fileid}"},
            {"id": f"file:{UNKNOWN_FILEID}"},
            f"file:{fileid}",
            f"file:{UNKNOWN_FILEID}",
            _fetchable(fileid, path),
            _no_file,
            mode,
            unexpected,
        )
        _assert_equal(tagged, unknown)
        assert "geheim" not in tagged
        assert '"isError": true' in tagged


@pytest.mark.anyio
@pytest.mark.parametrize("status", [500, 503])
async def test_fetch_file_answers_a_failing_lookup_alike(
    status: int, unexpected: list[str]
) -> None:
    """D-28-17: a 5xx of the fileid SEARCH answers a tagged id and an invented one alike."""

    def failing(mock: respx.MockRouter) -> None:
        mock.route(method="SEARCH", url=DAV_ROOT).mock(return_value=httpx.Response(status))

    tagged, unknown = await pair(
        "fetch",
        {"id": "file:901"},
        {"id": f"file:{UNKNOWN_FILEID}"},
        "file:901",
        f"file:{UNKNOWN_FILEID}",
        failing,
        failing,
        "active",
        unexpected,
    )
    _assert_equal(tagged, unknown)
    assert '"isError": true' in tagged
