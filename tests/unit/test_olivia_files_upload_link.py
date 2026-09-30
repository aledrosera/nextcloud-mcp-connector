import json

import pytest

from mcp_connector.deps import TicketOwner
from mcp_connector.server import reg_files

pytestmark = pytest.mark.anyio


def tool():
    return getattr(reg_files.files_upload, "__wrapped__", reg_files.files_upload)


async def test_without_content_the_tool_returns_an_upload_link(monkeypatch):
    seen = {}

    async def fake_issue(clients, owner, path):
        seen.update(owner=owner, path=path)
        return {"upload_url": "https://x/ul/tok", "method": "PUT"}

    monkeypatch.setattr(reg_files.deps, "resolve_clients", lambda ctx: "clients")
    monkeypatch.setattr(
        reg_files.deps, "resolve_ticket_owner", lambda ctx: TicketOwner("a", "alice")
    )
    monkeypatch.setattr(reg_files.upload, "issue_upload_link", fake_issue)
    text = await tool()(path="/Docs/new.docx", ctx=None)
    assert json.loads(text) == {"upload_url": "https://x/ul/tok", "method": "PUT"}
    assert seen == {"owner": TicketOwner("a", "alice"), "path": "/Docs/new.docx"}


async def test_with_content_the_text_path_is_unchanged(monkeypatch):
    async def fake_upload(clients, path, content):
        return {"path": path, "created": True}

    monkeypatch.setattr(reg_files.deps, "resolve_clients", lambda ctx: "clients")
    monkeypatch.setattr(reg_files.files_tools, "upload", fake_upload)
    text = await tool()(path="/Docs/n.md", content="ciao", ctx=None)
    assert json.loads(text) == {"path": "/Docs/n.md", "created": True}
