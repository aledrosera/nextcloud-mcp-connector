"""Upload the DOCX fixture through WebDAV and read it back through the tool (opt-in).

Run it the way test_files_roundtrip.py describes. Without ``NC_MCP_URL`` the fixture skips.
The converters need the extra: ``uv sync --extra documents``.
"""

import time
import uuid
from pathlib import Path

import httpx
import pytest

from mcp_connector.config import normalize_base_url
from mcp_connector.nextcloud import NcClients
from mcp_connector.nextcloud.clients import dav
from mcp_connector.nextcloud.credentials import Credentials
from mcp_connector.tools import files as files_tools

pytestmark = [pytest.mark.integration, pytest.mark.anyio]

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "documents" / "sample.docx"
DOCX_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@pytest.fixture
def clients(live_env: dict[str, str | None]) -> NcClients:
    missing = [name for name, value in live_env.items() if not value]
    if missing:
        pytest.skip(f"no test Nextcloud configured (missing: {', '.join(sorted(missing))})")

    user = live_env["user"]
    assert user != "admin", "integration tests run as a normal user, never as admin"

    return NcClients(
        client=httpx.AsyncClient(follow_redirects=False, timeout=30.0),
        creds=Credentials(
            base_url=normalize_base_url(str(live_env["base_url"])),
            user=str(user),
            secret=str(live_env["secret"]),
        ),
    )


async def test_a_docx_uploaded_over_webdav_comes_back_as_markdown(clients: NcClients) -> None:
    path = f"/mcp-connector-test-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}.docx"
    await dav.put_new_file(clients.client, clients.creds, path, FIXTURE.read_bytes(), DOCX_TYPE)

    result = await files_tools.read_as_markdown(clients, path=path)

    assert "# Quarterly Report" in result["content"]
    assert "| Servers | 12 |" in result["content"]
