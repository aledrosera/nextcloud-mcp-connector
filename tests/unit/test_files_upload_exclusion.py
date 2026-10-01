"""The ``kein-ki`` guard on uploads: the write oracle is closed (D-27-01, D-27-02).

An upload into a tagged folder, or onto a tagged file, is refused before any write with
exactly the refusal Nextcloud gives for a missing parent folder, so the answer cannot
tell "withheld" from "not there". Each pair test compares against the real 404/409 path
of ``dav._check_write``. No ``patch_untagged`` here: the guard requests are mocked through
``guard_routes``. The fork has no base64 chunk upload (fork olivia): a binary file goes
through an upload link, whose guard is tested in test_olivia_exclusion_links.py.
"""

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
SECRET = "app-password-test"
HOME = f"{BASE}/remote.php/dav/files/{USER}"
CONTENT = "# Neue Notiz\n"

TAGGED_FOLDER = ("Projekt", "900", True)
TAGGED_FILE = ("Docs/geheim.txt", "901", False)


@pytest.fixture(autouse=True)
def _fresh_tag_cache() -> None:
    guard_routes.reset()


def _clients() -> NcClients:
    """One bundle per tool call, as ``deps.resolve_clients`` builds it: one guard each."""
    return NcClients(
        client=httpx.AsyncClient(follow_redirects=False),
        creds=Credentials(BASE, USER, SECRET),
    )


def _untagged(mock: respx.MockRouter) -> respx.Route:
    """The untagged state after an active one: drop the cached tag ids first.

    Otherwise the ids of the previous scenario would send a REPORT without a listing.
    """
    guard_routes.reset()
    return guard_routes.untagged(mock)


def _tuple(err: ToolError) -> tuple[str, str, str]:
    return (err.message, err.hint, err.reason)


class _Writes:
    """The write route of the text upload for one destination, answering ``status``."""

    def __init__(self, mock: respx.MockRouter, path: str, status: int = 201) -> None:
        self.put = mock.route(method="PUT", url=f"{HOME}{path}").mock(
            return_value=httpx.Response(status)
        )

    @property
    def count(self) -> int:
        return self.put.call_count


async def _text(path: str, **kwargs: Any) -> ToolError:
    with pytest.raises(ToolError) as caught:
        await files_tools.upload(_clients(), path=path, content=CONTENT, **kwargs)
    return caught.value


def _mock() -> respx.MockRouter:
    return respx.mock(assert_all_mocked=True, assert_all_called=False)


@pytest.mark.anyio
async def test_upload_into_a_tagged_folder_reads_like_a_missing_parent() -> None:
    path = "/Projekt/neu.txt"
    with _mock() as mock:
        _, report = guard_routes.active(mock, TAGGED_FOLDER)
        writes = _Writes(mock, path)
        tagged = await _text(path)
        assert report.call_count == 1

    with _mock() as mock:
        _untagged(mock)
        _Writes(mock, path, status=409)
        missing = await _text(path)

    assert writes.count == 0, "no write request before the refusal"
    assert _tuple(tagged) == _tuple(missing)
    assert _tuple(tagged) == _tuple(dav.parent_missing(path))


@pytest.mark.anyio
async def test_upload_onto_a_tagged_file_under_a_visible_parent_gets_the_same_sentence() -> None:
    """The documented edge case of D-27-01: "already exists" would confirm the file."""
    path = "/Docs/geheim.txt"
    with _mock() as mock:
        guard_routes.active(mock, TAGGED_FILE)
        writes = _Writes(mock, path)
        tagged = await _text(path)

    with _mock() as mock:
        _untagged(mock)
        _Writes(mock, path, status=409)
        missing = await _text(path)

    assert writes.count == 0
    assert "already exists" not in tagged.message
    assert _tuple(tagged) == _tuple(missing)


@pytest.mark.anyio
async def test_unverifiable_refuses_every_upload_alike_without_writing() -> None:
    refusals: list[ToolError] = []
    counts: list[int] = []
    for path in ("/Docs/notes.txt", "/Fehlt/neu.txt"):
        with _mock() as mock:
            guard_routes.unverifiable(mock)
            writes = _Writes(mock, path)
            refusals.append(await _text(path))
        counts.append(writes.count)

    expected = _tuple(withhold.unavailable_error())
    assert all(_tuple(refusal) == expected for refusal in refusals)
    assert counts == [0, 0], "fail-closed: no PUT"


@pytest.mark.anyio
async def test_untagged_uploads_as_before_and_sends_no_report() -> None:
    path = "/Docs/new-note.md"
    with _mock() as mock:
        listing = _untagged(mock)
        report = mock.route(method="REPORT", url=guard_routes.HOME)
        writes = _Writes(mock, path)
        text = await files_tools.upload(_clients(), path=path, content=CONTENT)

    assert text == {"path": path, "etag": "", "created": True}
    assert writes.put.call_count == 1
    assert listing.call_count == 1, "one guard per tool call"
    assert report.call_count == 0


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("path", "kwargs"),
    [
        ("/Docs/", {}),
        ("/../etc/passwd", {}),
        ("/Docs/a.md", {"content_type": "text/plain\r\nX: y"}),
    ],
)
async def test_input_errors_still_come_before_any_request(
    path: str, kwargs: dict[str, Any]
) -> None:
    with _mock() as mock:
        await _text(path, **kwargs)
        assert mock.calls.call_count == 0
