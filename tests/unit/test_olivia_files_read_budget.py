import pytest

from mcp_connector.server import reg_files
from mcp_connector.tools import files as files_tools

pytestmark = pytest.mark.anyio


def test_default_chunk_is_64_kib():
    assert files_tools.DEFAULT_MAX_BYTES == 64 * 1024


async def test_inflated_text_is_read_in_smaller_chunks(monkeypatch):
    calls = []

    async def fake_read(clients, path, offset=0, max_bytes=files_tools.DEFAULT_MAX_BYTES):
        calls.append(max_bytes)
        content = "\x01" * max_bytes  # each char becomes \u0001 in JSON
        return {
            "path": path,
            "content": content,
            "size": 10**6,
            "content_type": "text/plain",
            "truncated": True,
            "next_offset": offset + max_bytes,
        }

    monkeypatch.setattr(reg_files.files_tools, "read", fake_read)
    text = await reg_files.read_within_budget(None, "/big.txt", 0)
    assert len(text) <= reg_files.TOOL_RESULT_CHAR_LIMIT
    assert calls[0] == 64 * 1024
    assert calls[-1] < calls[0]


async def test_plain_text_keeps_the_default_chunk(monkeypatch):
    async def fake_read(clients, path, offset=0, max_bytes=files_tools.DEFAULT_MAX_BYTES):
        return {
            "path": path,
            "content": "a" * max_bytes,
            "size": 10**6,
            "content_type": "text/plain",
            "truncated": True,
            "next_offset": offset + max_bytes,
        }

    monkeypatch.setattr(reg_files.files_tools, "read", fake_read)
    text = await reg_files.read_within_budget(None, "/big.txt", 0)
    assert '"next_offset":65536' in text
