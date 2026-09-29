"""Unit tests for the ``open_download`` streaming function (fork olivia).

Tests the streaming GET of a whole file for the download route. respx mocks the httpx layer.
"""

import httpx
import pytest
import respx

from mcp_connector.errors import ToolError
from mcp_connector.nextcloud.clients import dav
from mcp_connector.nextcloud.credentials import Credentials

pytestmark = pytest.mark.anyio
BASE = "http://nc.test"
URL = f"{BASE}/remote.php/dav/files/alice/Docs/scan%20%C3%A0.pdf"


async def test_open_download_streams_the_whole_file():
    body = b"%PDF-" + b"x" * 200_000
    creds = Credentials(BASE, "alice", "app-password-test")
    async with httpx.AsyncClient() as client:
        with respx.mock(assert_all_called=True) as mock:
            route = mock.get(URL).mock(return_value=httpx.Response(200, content=body))
            response = await dav.open_download(client, creds, "/Docs/scan à.pdf")
            data = b"".join([chunk async for chunk in response.aiter_raw()])
            await response.aclose()
    assert data == body
    assert route.calls[0].request.headers["accept-encoding"] == "identity"
    assert "range" not in route.calls[0].request.headers


async def test_open_download_raises_and_closes_on_404():
    creds = Credentials(BASE, "alice", "app-password-test")
    async with httpx.AsyncClient() as client:
        with respx.mock:
            respx.get(URL).mock(return_value=httpx.Response(404))
            with pytest.raises(ToolError) as caught:
                await dav.open_download(client, creds, "/Docs/scan à.pdf")
    assert "File not found" in caught.value.message
