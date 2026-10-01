"""files_read_as_markdown: stat, cap, download, convert, slice. respx mocks the DAV layer."""

from pathlib import Path

import guard_routes
import httpx
import pytest
import respx

from mcp_connector import documents
from mcp_connector.errors import REASON_GUARD_TRIPPED, ToolError
from mcp_connector.nextcloud import NcClients
from mcp_connector.nextcloud.credentials import Credentials
from mcp_connector.tools import files as files_tools

BASE = "http://nc.test"
USER = "alice"
FILES_ROOT = f"{BASE}/remote.php/dav/files/{USER}"
DOC_URL = f"{FILES_ROOT}/Docs/sample.docx"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "documents" / "sample.docx"


def _propfind(*, length: int, content_type: str, collection: bool = False) -> str:
    resource = (
        "<d:resourcetype><d:collection/></d:resourcetype>" if collection else "<d:resourcetype/>"
    )
    return f"""<?xml version="1.0"?>
<d:multistatus xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns">
  <d:response>
    <d:href>/remote.php/dav/files/alice/Docs/sample.docx</d:href>
    <d:propstat>
      <d:prop>
        <d:getcontentlength>{length}</d:getcontentlength>
        <d:getcontenttype>{content_type}</d:getcontenttype>
        <d:getlastmodified>Thu, 14 Aug 2026 10:00:00 GMT</d:getlastmodified>
        <d:getetag>&quot;etag-1&quot;</d:getetag>
        {resource}
        <oc:fileid>4711</oc:fileid>
        <oc:permissions>RGDNVW</oc:permissions>
      </d:prop>
      <d:status>HTTP/1.1 200 OK</d:status>
    </d:propstat>
  </d:response>
</d:multistatus>
"""


@pytest.fixture(autouse=True)
def _no_kein_ki_tag(monkeypatch: pytest.MonkeyPatch) -> None:
    """These tests cover the tool without any kein-ki tag; the guard states are tested in
    test_files_exclusion.py and test_pair_equality_files.py."""
    guard_routes.patch_untagged(monkeypatch)


@pytest.fixture
def clients() -> NcClients:
    return NcClients(
        client=httpx.AsyncClient(follow_redirects=False),
        creds=Credentials(BASE, USER, "app-password-test"),
    )


@pytest.mark.anyio
async def test_happy_path_returns_markdown_and_stable_fields(clients: NcClients) -> None:
    body = FIXTURE.read_bytes()
    with respx.mock(assert_all_called=True) as mock:
        mock.route(method="PROPFIND", url=DOC_URL).mock(
            return_value=httpx.Response(207, text=_propfind(length=len(body), content_type=DOCX))
        )
        mock.route(method="GET", url=DOC_URL).mock(return_value=httpx.Response(200, content=body))
        result = await files_tools.read_as_markdown(clients, path="/Docs/sample.docx")

    assert result["path"] == "/Docs/sample.docx"
    assert result["content"].startswith("# Quarterly Report")
    assert result["content_type"] == DOCX
    assert result["format"] == "docx"
    assert result["size"] == len(body)
    assert result["markdown_length"] == len(result["content"])
    assert result["truncated"] is False
    assert "next_offset" not in result


@pytest.mark.anyio
async def test_slices_continue_by_character_offset(clients: NcClients) -> None:
    body = FIXTURE.read_bytes()
    with respx.mock as mock:
        mock.route(method="PROPFIND", url=DOC_URL).mock(
            return_value=httpx.Response(207, text=_propfind(length=len(body), content_type=DOCX))
        )
        mock.route(method="GET", url=DOC_URL).mock(return_value=httpx.Response(200, content=body))
        whole = (await files_tools.read_as_markdown(clients, path="/Docs/sample.docx"))["content"]
        first = await files_tools.read_as_markdown(clients, path="/Docs/sample.docx", max_chars=10)
        second = await files_tools.read_as_markdown(
            clients, path="/Docs/sample.docx", offset=first["next_offset"], max_chars=10_000
        )

    assert first["truncated"] is True
    assert first["next_offset"] == 10
    assert len(first["content"]) == 10
    assert first["content"] + second["content"] == whole
    assert second["truncated"] is False


@pytest.mark.anyio
async def test_a_folder_is_refused_with_a_pointer_to_files_list(clients: NcClients) -> None:
    with respx.mock as mock:
        mock.route(method="PROPFIND", url=DOC_URL).mock(
            return_value=httpx.Response(
                207, text=_propfind(length=0, content_type="", collection=True)
            )
        )
        with pytest.raises(ToolError) as info:
            await files_tools.read_as_markdown(clients, path="/Docs/sample.docx")
    assert "folder" in info.value.message
    assert "files_list" in info.value.hint


@pytest.mark.anyio
async def test_a_text_file_is_refused_with_a_pointer_to_files_read(clients: NcClients) -> None:
    with respx.mock as mock:
        mock.route(method="PROPFIND", url=DOC_URL).mock(
            return_value=httpx.Response(207, text=_propfind(length=5, content_type="text/markdown"))
        )
        with pytest.raises(ToolError) as info:
            await files_tools.read_as_markdown(clients, path="/Docs/sample.docx")
    assert "files_read" in info.value.hint


@pytest.mark.anyio
async def test_an_oversize_source_is_refused_before_download(clients: NcClients) -> None:
    with respx.mock(assert_all_called=True) as mock:
        mock.route(method="PROPFIND", url=DOC_URL).mock(
            return_value=httpx.Response(
                207, text=_propfind(length=documents.MAX_SOURCE_BYTES + 1, content_type=DOCX)
            )
        )
        with pytest.raises(ToolError) as info:
            await files_tools.read_as_markdown(clients, path="/Docs/sample.docx")
    assert info.value.reason == REASON_GUARD_TRIPPED
    assert "files_download" in info.value.hint


@pytest.mark.anyio
async def test_an_unsupported_type_is_refused_before_download(clients: NcClients) -> None:
    with respx.mock(assert_all_called=True) as mock:
        mock.route(method="PROPFIND", url=DOC_URL).mock(
            return_value=httpx.Response(207, text=_propfind(length=5, content_type="image/png"))
        )
        with pytest.raises(ToolError) as info:
            await files_tools.read_as_markdown(clients, path="/Docs/sample.docx")
    assert "not supported" in info.value.message


@pytest.mark.anyio
async def test_an_offset_past_the_end_is_refused(clients: NcClients) -> None:
    body = FIXTURE.read_bytes()
    with respx.mock as mock:
        mock.route(method="PROPFIND", url=DOC_URL).mock(
            return_value=httpx.Response(207, text=_propfind(length=len(body), content_type=DOCX))
        )
        mock.route(method="GET", url=DOC_URL).mock(return_value=httpx.Response(200, content=body))
        with pytest.raises(ToolError) as info:
            await files_tools.read_as_markdown(clients, path="/Docs/sample.docx", offset=10_000_000)
    assert "offset" in info.value.message


@pytest.mark.anyio
async def test_negative_offset_and_bad_max_chars_are_refused(clients: NcClients) -> None:
    with pytest.raises(ToolError):
        await files_tools.read_as_markdown(clients, path="/Docs/sample.docx", offset=-1)
    with pytest.raises(ToolError):
        await files_tools.read_as_markdown(
            clients, path="/Docs/sample.docx", max_chars=files_tools.HARD_MAX_CHARS + 1
        )


@pytest.mark.anyio
async def test_files_read_points_a_docx_at_the_download_link(clients: NcClients) -> None:
    """The olivia fork does not offer files_read_as_markdown: Office goes out as a link."""
    with respx.mock as mock:
        mock.route(method="PROPFIND", url=DOC_URL).mock(
            return_value=httpx.Response(207, text=_propfind(length=5, content_type=DOCX))
        )
        with pytest.raises(ToolError) as info:
            await files_tools.read(clients, path="/Docs/sample.docx")
    assert "files_download" in info.value.hint
    assert "files_read_as_markdown" not in info.value.hint


@pytest.mark.anyio
async def test_files_read_keeps_the_download_hint_for_other_binaries(clients: NcClients) -> None:
    with respx.mock as mock:
        mock.route(method="PROPFIND", url=DOC_URL).mock(
            return_value=httpx.Response(207, text=_propfind(length=5, content_type="image/png"))
        )
        with pytest.raises(ToolError) as info:
            await files_tools.read(clients, path="/Docs/sample.docx")
    assert "files_download" in info.value.hint
    assert "files_read_as_markdown" not in info.value.hint


@pytest.mark.anyio
async def test_a_body_larger_than_the_stat_size_is_refused_after_download(
    clients: NcClients, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(documents, "MAX_SOURCE_BYTES", 100)
    with respx.mock(assert_all_called=True) as mock:
        mock.route(method="PROPFIND", url=DOC_URL).mock(
            return_value=httpx.Response(207, text=_propfind(length=10, content_type=DOCX))
        )
        get = mock.route(method="GET", url=DOC_URL).mock(
            return_value=httpx.Response(200, content=b"x" * 101)
        )
        with pytest.raises(ToolError) as info:
            await files_tools.read_as_markdown(clients, path="/Docs/sample.docx")

    assert get.calls.last.request.headers["Range"] == "bytes=0-100"
    assert info.value.reason == REASON_GUARD_TRIPPED
    assert "files_download" in info.value.hint


@pytest.mark.anyio
async def test_the_download_happens_inside_a_conversion_slot(
    clients: NcClients, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The slot bounds the bytes held for conversion, so it must be taken before the GET
    # and not only around the conversion.
    from contextlib import asynccontextmanager

    held = False
    seen_during_get: list[bool] = []

    @asynccontextmanager
    async def slot():
        nonlocal held
        held = True
        try:
            yield
        finally:
            held = False

    monkeypatch.setattr(documents, "slot", slot)
    body = FIXTURE.read_bytes()

    def on_get(_request: httpx.Request) -> httpx.Response:
        seen_during_get.append(held)
        return httpx.Response(200, content=body)

    with respx.mock as mock:
        mock.route(method="PROPFIND", url=DOC_URL).mock(
            return_value=httpx.Response(207, text=_propfind(length=len(body), content_type=DOCX))
        )
        mock.route(method="GET", url=DOC_URL).mock(side_effect=on_get)
        await files_tools.read_as_markdown(clients, path="/Docs/sample.docx")

    assert seen_during_get == [True]
    assert held is False
