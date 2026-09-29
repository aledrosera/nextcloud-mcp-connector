import pytest

from mcp_connector import provider_map
from mcp_connector.deps import TicketOwner
from mcp_connector.tools import chatgpt

pytestmark = pytest.mark.anyio


def test_findling_hits_become_file_ids():
    entry = {"resourceUrl": "/index.php/f/9917", "attributes": []}
    result = provider_map.extract_id("findling", entry, "https://cloud.example")
    assert result == ("file", "file:9917", True)


async def test_fetch_of_a_pdf_returns_a_download_link(monkeypatch):
    async def fake_find(client, creds, fileid):
        return {
            "path": "/Docs/scan.pdf",
            "name": "scan.pdf",
            "size": 1234,
            "content_type": "application/pdf",
        }

    async def fake_issue(clients, owner, path):
        return {
            "download_url": "https://x/dl/tok",
            "expires_at": "2026-09-29T10:10:00+00:00",
            "size": 1234,
            "content_type": "application/pdf",
            "name": "scan.pdf",
        }

    monkeypatch.setattr(chatgpt.dav_client, "find_by_fileid", fake_find)
    monkeypatch.setattr(chatgpt.issue, "issue_link", fake_issue)
    clients = type(
        "C", (), {"client": None, "creds": type("K", (), {"base_url": "https://cloud.example"})()}
    )()
    result = await chatgpt._fetch_file(
        clients,  # pyright: ignore[reportArgumentType]
        "4711",
        owner=TicketOwner("a", "alice"),
    )
    assert result["url"] == "https://x/dl/tok"
    assert result["metadata"]["download_url"] == "https://x/dl/tok"
    assert "web_fetch" in result["text"]
    assert all(isinstance(v, str) for v in result["metadata"].values())


async def test_fetch_of_a_pdf_without_owner_keeps_the_old_refusal(monkeypatch):
    from mcp_connector.errors import ToolError

    async def fake_find(client, creds, fileid):
        return {
            "path": "/Docs/scan.pdf",
            "name": "scan.pdf",
            "size": 1,
            "content_type": "application/pdf",
        }

    async def fake_read(clients, path, max_bytes):
        raise ToolError(message="/Docs/scan.pdf is application/pdf and not text.", hint="h")

    monkeypatch.setattr(chatgpt.dav_client, "find_by_fileid", fake_find)
    monkeypatch.setattr(chatgpt.files_tools, "read", fake_read)
    clients = type("C", (), {"client": None, "creds": type("K", (), {"base_url": "x"})()})()
    with pytest.raises(ToolError):
        await chatgpt._fetch_file(clients, "4711")  # pyright: ignore[reportArgumentType]
