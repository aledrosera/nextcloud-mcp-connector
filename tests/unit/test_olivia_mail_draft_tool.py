import json

import pytest
from mcp import Client

from mcp_connector.server import mcp, reg_mail

pytestmark = pytest.mark.anyio


async def test_the_tool_passes_everything_to_drafts_create(monkeypatch):
    seen = {}

    async def fake_create(clients, **kwargs):
        seen.update(kwargs)
        return {"draft_id": 7}

    monkeypatch.setattr(reg_mail.deps, "resolve_clients", lambda ctx: "clients")
    monkeypatch.setattr(reg_mail.drafts, "create", fake_create)
    tool = getattr(reg_mail.mail_draft, "__wrapped__", reg_mail.mail_draft)
    text = await tool(
        to=["a@b.it"],
        subject="s",
        body="b",
        reply_to="mail:1",
        attachments=["/Docs/a.pdf"],
        ctx=None,
    )
    assert json.loads(text) == {"draft_id": 7}
    assert seen["attachments"] == ["/Docs/a.pdf"]
    assert seen["reply_to"] == "mail:1"


async def test_the_tool_is_create_only_and_says_it_never_sends():
    async with Client(mcp, raise_exceptions=True) as client:
        tools = {tool.name: tool for tool in (await client.list_tools()).tools}
    tool = tools["mail_draft"]
    assert tool.annotations is not None
    assert tool.annotations.read_only_hint is False
    assert tool.annotations.destructive_hint is False
    assert "never sent" in (tool.description or "")
