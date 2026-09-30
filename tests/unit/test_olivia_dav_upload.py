import httpx
import pytest
import respx

from mcp_connector.nextcloud.clients import dav
from mcp_connector.nextcloud.credentials import Credentials

pytestmark = pytest.mark.anyio
BASE = "http://nc.test"
CREDS = Credentials(BASE, "alice", "pw")
ROOT = f"{BASE}/remote.php/dav/files/alice"


async def chunks(*parts: bytes):
    for part in parts:
        yield part


async def test_ensure_folders_creates_top_down_and_accepts_existing():
    with respx.mock:
        a = respx.route(method="MKCOL", url=f"{ROOT}/Clienti").mock(
            return_value=httpx.Response(405)
        )
        b = respx.route(method="MKCOL", url=f"{ROOT}/Clienti/Rossi%20%C3%A0").mock(
            return_value=httpx.Response(201)
        )
        async with httpx.AsyncClient() as client:
            assert await dav.ensure_folders(client, CREDS, "/Clienti/Rossi à") is None
    assert a.called
    assert b.called


async def test_ensure_folders_reports_the_first_failure():
    with respx.mock:
        respx.route(method="MKCOL", url=f"{ROOT}/Clienti").mock(return_value=httpx.Response(403))
        async with httpx.AsyncClient() as client:
            assert await dav.ensure_folders(client, CREDS, "/Clienti/Rossi") == 403


async def test_put_new_stream_sends_the_precondition_and_the_body():
    with respx.mock:
        route = respx.put(f"{ROOT}/Docs/a.pdf").mock(return_value=httpx.Response(201))
        async with httpx.AsyncClient() as client:
            status = await dav.put_new_stream(client, CREDS, "/Docs/a.pdf", chunks(b"ab", b"cd"))
    assert status == 201
    request = route.calls.last.request
    assert request.headers["If-None-Match"] == "*"
    assert request.content == b"abcd"


async def test_put_new_stream_returns_the_refusal_status():
    with respx.mock:
        respx.put(f"{ROOT}/Docs/a.pdf").mock(return_value=httpx.Response(412))
        async with httpx.AsyncClient() as client:
            assert await dav.put_new_stream(client, CREDS, "/Docs/a.pdf", chunks(b"x")) == 412
