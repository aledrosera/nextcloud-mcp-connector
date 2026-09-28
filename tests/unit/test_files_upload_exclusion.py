"""The ``kein-ki`` guard on uploads: the write oracle is closed (D-27-01, D-27-02).

An upload into a tagged folder, or onto a tagged file, is refused before any write with
exactly the refusal Nextcloud gives for a missing parent folder, so the answer cannot
tell "withheld" from "not there". Each pair test compares against the real 404/409 path
of ``dav._check_write`` and ``dav._check_chunk_response``. No ``patch_untagged`` here:
the guard requests are mocked through ``guard_routes``.
"""

import base64
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
UPLOAD_ID = "upload-test"
CONTENT = "# Neue Notiz\n"
PDF = b"%PDF-1.7\nscan\n"

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


def _folder_url(path: str) -> str:
    return dav.uploads_url(Credentials(BASE, USER, SECRET), UPLOAD_ID, path=path)


class _Writes:
    """Every write route of both upload tools for one destination, all answering ``status``."""

    def __init__(self, mock: respx.MockRouter, path: str, status: int = 201) -> None:
        folder = _folder_url(path)
        self.put = mock.route(method="PUT", url=f"{HOME}{path}").mock(
            return_value=httpx.Response(status)
        )
        self.mkcol = mock.route(method="MKCOL", url=folder).mock(
            return_value=httpx.Response(status)
        )
        self.chunk = mock.route(method="PUT", url__startswith=f"{folder}/0").mock(
            return_value=httpx.Response(status)
        )
        self.move = mock.route(method="MOVE", url=f"{folder}/.file").mock(
            return_value=httpx.Response(status)
        )

    @property
    def count(self) -> int:
        return sum(r.call_count for r in (self.put, self.mkcol, self.chunk, self.move))


async def _text(path: str, **kwargs: Any) -> ToolError:
    with pytest.raises(ToolError) as caught:
        await files_tools.upload(_clients(), path=path, content=CONTENT, **kwargs)
    return caught.value


async def _binary(path: str, **kwargs: Any) -> ToolError:
    args: dict[str, Any] = {
        "content_base64": base64.b64encode(PDF).decode("ascii"),
        "total_bytes": len(PDF),
        "upload_id": UPLOAD_ID,
        "final": True,
        "content_type": "application/pdf",
    }
    args.update(kwargs)
    with pytest.raises(ToolError) as caught:
        await files_tools.upload_binary(_clients(), path=path, **args)
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
@pytest.mark.parametrize("path", ["/Projekt/scan.pdf", "/Docs/geheim.txt"])
async def test_binary_one_chunk_upload_is_refused_before_any_write(path: str) -> None:
    with _mock() as mock:
        guard_routes.active(mock, TAGGED_FOLDER, TAGGED_FILE)
        writes = _Writes(mock, path)
        tagged = await _binary(path)

    with _mock() as mock:
        _untagged(mock)
        _Writes(mock, path, status=409)
        missing = await _binary(path)

    assert writes.count == 0, "no MKCOL, no chunk PUT, no MOVE"
    assert _tuple(tagged) == _tuple(missing)
    assert _tuple(tagged) == _tuple(dav.parent_missing(path))


@pytest.mark.anyio
async def test_binary_empty_file_is_refused_before_the_put() -> None:
    path = "/Projekt/leer.bin"
    with _mock() as mock:
        guard_routes.active(mock, TAGGED_FOLDER)
        writes = _Writes(mock, path)
        tagged = await _binary(path, content_base64="", total_bytes=0)

    with _mock() as mock:
        _untagged(mock)
        _Writes(mock, path, status=409)
        missing = await _binary(path, content_base64="", total_bytes=0)

    assert writes.count == 0
    assert _tuple(tagged) == _tuple(missing)


@pytest.mark.anyio
async def test_a_tag_set_between_two_chunks_stops_the_final_call() -> None:
    path = "/Projekt/gross.bin"
    first = b"x" * files_tools.MIN_UPLOAD_CHUNK_BYTES
    rest = b"tail"
    total = len(first) + len(rest)

    with _mock() as mock:
        _untagged(mock)
        writes = _Writes(mock, path)
        started = await files_tools.upload_binary(
            _clients(),
            path=path,
            content_base64=base64.b64encode(first).decode("ascii"),
            total_bytes=total,
            upload_id=UPLOAD_ID,
            final=False,
        )
    assert started["next_chunk"] == 2
    assert (writes.mkcol.call_count, writes.chunk.call_count) == (1, 1)

    with _mock() as mock:
        guard_routes.active(mock, TAGGED_FOLDER)
        writes = _Writes(mock, path)
        refused = await _binary(
            path,
            content_base64=base64.b64encode(rest).decode("ascii"),
            total_bytes=total,
            chunk_index=2,
            final=True,
            content_type="application/octet-stream",
        )

    assert writes.count == 0, "neither the second chunk nor the MOVE goes out"
    assert writes.move.call_count == 0
    assert _tuple(refused) == _tuple(dav.parent_missing(path))


@pytest.mark.anyio
@pytest.mark.parametrize("chunk_status", [404, 409])
async def test_first_binary_chunk_into_a_tagged_folder_answers_like_an_invented_folder(
    chunk_status: int,
) -> None:
    """B6, D-28-20 (no finding): chunk 1 of a multi-chunk upload, measured on nc35 in 28-01.

    Into an invented folder Nextcloud accepts the MKCOL of the staging folder and refuses
    the missing destination at the first chunk PUT; the connector turns that into the
    missing-parent sentence. The tagged folder gets the same sentence before any write,
    so the two answer alike except for the path. The staging folder the invented case
    leaves behind is no oracle (no tool reads the upload area) and is a cleanup note for
    phase 29, not part of this pin.
    """
    chunk = b"x" * files_tools.MIN_UPLOAD_CHUNK_BYTES
    args: dict[str, Any] = {
        "content_base64": base64.b64encode(chunk).decode("ascii"),
        "total_bytes": len(chunk) + 4,
        "final": False,
    }
    tagged_path = "/Projekt/neu.bin"
    invented_path = "/erfunden-1/neu.bin"

    with _mock() as mock:
        guard_routes.active(mock, TAGGED_FOLDER)
        tagged_writes = _Writes(mock, tagged_path)
        tagged = await _binary(tagged_path, **args)

    with _mock() as mock:
        guard_routes.reset()
        guard_routes.active(mock, TAGGED_FOLDER)
        invented_writes = _Writes(mock, invented_path)
        invented_writes.chunk.mock(return_value=httpx.Response(chunk_status))
        invented = await _binary(invented_path, **args)

    assert tagged_writes.count == 0, "no MKCOL, no chunk PUT for the tagged target"
    assert (invented_writes.mkcol.call_count, invented_writes.chunk.call_count) == (1, 1)
    assert tagged.message.replace("/Projekt", "<F>") == invented.message.replace(
        "/erfunden-1", "<F>"
    )
    assert (tagged.hint, tagged.reason) == (invented.hint, invented.reason)
    assert _tuple(tagged) == _tuple(dav.parent_missing(tagged_path))


@pytest.mark.anyio
async def test_unverifiable_refuses_every_upload_alike_without_writing() -> None:
    refusals: list[ToolError] = []
    counts: list[int] = []
    for path in ("/Docs/notes.txt", "/Fehlt/neu.txt"):
        with _mock() as mock:
            guard_routes.unverifiable(mock)
            writes = _Writes(mock, path)
            refusals.append(await _text(path))
            refusals.append(await _binary(path))
            refusals.append(await _binary(path, content_base64="", total_bytes=0))
        counts.append(writes.count)

    expected = _tuple(withhold.unavailable_error())
    assert all(_tuple(refusal) == expected for refusal in refusals)
    assert counts == [0, 0], "fail-closed: no PUT, MKCOL or MOVE"


@pytest.mark.anyio
async def test_untagged_uploads_as_before_and_sends_no_report() -> None:
    path = "/Docs/new-note.md"
    with _mock() as mock:
        listing = _untagged(mock)
        report = mock.route(method="REPORT", url=guard_routes.HOME)
        writes = _Writes(mock, path)
        text = await files_tools.upload(_clients(), path=path, content=CONTENT)
        binary = await files_tools.upload_binary(
            _clients(),
            path=path,
            content_base64=base64.b64encode(PDF).decode("ascii"),
            total_bytes=len(PDF),
            upload_id=UPLOAD_ID,
            final=True,
        )

    assert text == {"path": path, "etag": "", "created": True}
    assert binary["completed"] is True
    assert (writes.put.call_count, writes.mkcol.call_count) == (1, 1)
    assert (writes.chunk.call_count, writes.move.call_count) == (1, 1)
    assert listing.call_count == 2, "one guard per tool call"
    assert report.call_count == 0


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("tool", "path", "kwargs"),
    [
        ("text", "/Docs/", {}),
        ("text", "/../etc/passwd", {}),
        ("text", "/Docs/a.md", {"content_type": "text/plain\r\nX: y"}),
        ("binary", "/Docs/a.bin", {"content_base64": "***"}),
        ("binary", "/Docs/a.bin", {"total_bytes": -1}),
        ("binary", "/Docs/a.bin", {"chunk_index": 2, "upload_id": ""}),
    ],
)
async def test_input_errors_still_come_before_any_request(
    tool: str, path: str, kwargs: dict[str, Any]
) -> None:
    with _mock() as mock:
        if tool == "text":
            await _text(path, **kwargs)
        else:
            await _binary(path, **kwargs)
        assert mock.calls.call_count == 0
