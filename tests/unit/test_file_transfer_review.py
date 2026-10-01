"""Regression checks for transfer bounds and directory isolation."""

import guard_routes
import httpx
import pytest
import respx

from mcp_connector import config
from mcp_connector.errors import ToolError
from mcp_connector.nextcloud import NcClients
from mcp_connector.nextcloud.clients import dav
from mcp_connector.nextcloud.credentials import Credentials
from mcp_connector.nextcloud.exclusion import UNTAGGED
from mcp_connector.tools import files, search

CREDS = Credentials("https://nc.test", "alice", "test-password")


@pytest.fixture(autouse=True)
def _no_kein_ki_tag(monkeypatch: pytest.MonkeyPatch) -> None:
    """Existing tests assert the behaviour without any kein-ki tag; the guard states are
    tested in the *_exclusion test modules."""
    guard_routes.patch_untagged(monkeypatch)


class LargeStream(httpx.AsyncByteStream):
    def __init__(self) -> None:
        self.reads = 0
        self.closed = False

    async def __aiter__(self):
        for _ in range(1000):
            self.reads += 1
            yield b"x" * 65536

    async def aclose(self) -> None:
        self.closed = True


@pytest.mark.anyio
async def test_empty_text_response_cannot_produce_a_nonadvancing_cursor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def nonempty_stat(*args, **kwargs):
        return {"is_collection": False, "size": 10, "content_type": "text/plain"}

    monkeypatch.setattr(dav, "stat", nonempty_stat)
    async with httpx.AsyncClient() as client:
        with respx.mock as mock:
            mock.get(dav.files_url(CREDS, "/a.txt")).respond(200, content=b"")
            with pytest.raises(ToolError, match="empty chunk"):
                await files.read(NcClients(client, CREDS), "/a.txt")


@pytest.mark.anyio
async def test_ignored_range_stops_reading_and_closes_the_stream() -> None:
    stream = LargeStream()
    async with httpx.AsyncClient() as client:
        with respx.mock as mock:
            mock.get(dav.files_url(CREDS, "/large.pdf")).respond(200, stream=stream)
            result = await dav.get_range(client, CREDS, "/large.pdf", offset=65536, limit=10)
    assert result == b"x" * 10
    assert stream.reads == 2
    assert stream.closed


@pytest.mark.parametrize("path", ["/Docs2/secret", "/Docs/../secret", "/Other/secret"])
def test_search_metadata_cannot_escape_root(path: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(config.ENV_FILES_ROOT, "/Docs")
    clients = NcClients(httpx.AsyncClient(), CREDS)
    screened = search._screen(clients, "files", [{"attributes": {"path": path}}], UNTAGGED)
    assert screened.kept == []
    assert screened.skipped == 1


def test_dav_filters_returned_paths_and_supports_subpath_installations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(config.ENV_FILES_ROOT, "/Docs")
    creds = Credentials("https://nc.test/cloud", "alice", "test-password")
    body = b"""<d:multistatus xmlns:d="DAV:">
      <d:response><d:href>/cloud/remote.php/dav/files/alice/Docs/ok.pdf</d:href>
        <d:propstat><d:prop/><d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response>
      <d:response><d:href>/cloud/remote.php/dav/files/alice/Other/secret.pdf</d:href>
        <d:propstat><d:prop/><d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response>
      <d:response><d:href>/cloud/remote.php/dav/files/alice/Docs/%2e%2e/secret.pdf</d:href>
        <d:propstat><d:prop/><d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response>
    </d:multistatus>"""
    assert [entry["path"] for entry in dav.parse_entries(body, creds)] == ["/Docs/ok.pdf"]


@pytest.mark.anyio
async def test_upload_cannot_replace_bound_root(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(config.ENV_FILES_ROOT, "/Docs")
    async with httpx.AsyncClient() as client:
        clients = NcClients(client=client, creds=CREDS)
        with respx.mock as mock:
            with pytest.raises(ToolError, match="root folder"):
                await files.upload(clients, "/Docs", "")
            assert not mock.calls


@pytest.mark.anyio
@pytest.mark.parametrize("header", ["bytes 0-9/100", "bytes 10-99/100", "bad"])
async def test_wrong_content_range_is_rejected(header: str) -> None:
    async with httpx.AsyncClient() as client:
        with respx.mock as mock:
            mock.get(dav.files_url(CREDS, "/a.pdf")).respond(
                206, content=b"0123456789", headers={"Content-Range": header}
            )
            with pytest.raises(ToolError, match="different byte range"):
                await dav.get_range(client, CREDS, "/a.pdf", offset=10, limit=10)


@pytest.mark.anyio
async def test_empty_files_never_trigger_unbounded_get(monkeypatch: pytest.MonkeyPatch) -> None:
    """The binary case moved with the download path itself (fork olivia, task 7):
    ``files.download`` is gone, and its successor ``downloads.issue.issue_link`` never
    issues a GET at all (it stats and mints a ticket), so it cannot trigger an unbounded
    one either. Only the text read path still has a GET to guard here.
    """

    async def empty_stat(*args, **kwargs):
        return {"is_collection": False, "size": 0, "content_type": "text/plain"}

    monkeypatch.setattr(dav, "stat", empty_stat)
    async with httpx.AsyncClient() as client:
        with respx.mock as mock:
            result = await files.read(NcClients(client, CREDS), "/empty.txt")
            assert result["content"] == ""
            assert result["truncated"] is False
            assert not mock.calls


@pytest.mark.anyio
async def test_mime_type_cannot_end_in_newline() -> None:
    async with httpx.AsyncClient() as client:
        clients = NcClients(client, CREDS)
        with respx.mock as mock:
            with pytest.raises(ToolError, match="mimetype"):
                await files.upload(clients, "/a.txt", "a", content_type="text/plain\n")
            assert not mock.calls
