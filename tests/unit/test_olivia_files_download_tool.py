import json

import pytest

from mcp_connector.deps import TicketOwner
from mcp_connector.server import reg_files

pytestmark = pytest.mark.anyio


async def test_files_download_returns_the_link(monkeypatch):
    seen = {}

    async def fake_issue(clients, owner, path):
        seen.update(owner=owner, path=path)
        return {"download_url": "https://x/dl/tok", "single_use": True}

    monkeypatch.setattr(reg_files.deps, "resolve_clients", lambda ctx: "clients")
    monkeypatch.setattr(
        reg_files.deps, "resolve_ticket_owner", lambda ctx: TicketOwner("a", "alice")
    )
    monkeypatch.setattr(reg_files.issue, "issue_link", fake_issue)
    tool = getattr(reg_files.files_download, "__wrapped__", reg_files.files_download)
    text = await tool(path="/Docs/scan.pdf", ctx=None)
    assert json.loads(text) == {"download_url": "https://x/dl/tok", "single_use": True}
    assert seen == {"owner": TicketOwner("a", "alice"), "path": "/Docs/scan.pdf"}
