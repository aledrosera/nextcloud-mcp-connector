"""fetch(file:<id>) against the real guard (EXCL-03, success criterion 2).

A file id is the one handle a model keeps from an old answer, also from the time before a
file was tagged. After the tag it has to answer exactly like an id that belongs to no file:
the same message, the same hint, the same reason, byte for byte, and without a single read
of the content. When the check cannot be answered, every id gets the one uniform refusal.

No ``patch_untagged`` here; a fresh ``NcClients`` per call, so each call has its own guard.
"""

import guard_routes
import httpx
import pytest
import respx

from mcp_connector.errors import ToolError
from mcp_connector.nextcloud import NcClients, capabilities
from mcp_connector.nextcloud.credentials import Credentials
from mcp_connector.tools import chatgpt, withhold

BASE = guard_routes.BASE
USER = guard_routes.USER
DAV_ROOT = f"{BASE}/remote.php/dav/"
FILES_ROOT = f"{BASE}/remote.php/dav/files/{USER}"
CAPABILITIES_URL = f"{BASE}/ocs/v2.php/cloud/capabilities"
CONTENT = b"streng vertraulich\n"


@pytest.fixture(autouse=True)
def _fresh_caches() -> None:
    guard_routes.reset()
    capabilities.clear_cache()


def fresh() -> NcClients:
    return NcClients(
        client=httpx.AsyncClient(follow_redirects=False),
        creds=Credentials(BASE, USER, "app-password-test"),
    )


def found(fileid: str, path: str) -> httpx.Response:
    href = f"/remote.php/dav/files/{USER}{path}"
    body = f"""<?xml version="1.0"?>
<d:multistatus xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns">
  <d:response><d:href>{href}</d:href><d:propstat><d:prop>
    <d:displayname>{path.rsplit("/", 1)[-1]}</d:displayname>
    <d:getcontenttype>text/plain</d:getcontenttype>
    <d:getcontentlength>{len(CONTENT)}</d:getcontentlength>
    <d:resourcetype/><oc:fileid>{fileid}</oc:fileid>
  </d:prop><d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response>
</d:multistatus>"""
    return httpx.Response(207, text=body)


def nothing() -> httpx.Response:
    return httpx.Response(
        207,
        text='<?xml version="1.0"?><d:multistatus xmlns:d="DAV:" '
        'xmlns:oc="http://owncloud.org/ns"></d:multistatus>',
    )


def stat(fileid: str, path: str) -> httpx.Response:
    href = f"/remote.php/dav/files/{USER}{path}"
    body = f"""<?xml version="1.0"?>
<d:multistatus xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns">
  <d:response><d:href>{href}</d:href><d:propstat><d:prop>
    <d:getcontentlength>{len(CONTENT)}</d:getcontentlength>
    <d:getcontenttype>text/plain</d:getcontenttype>
    <d:getlastmodified>Thu, 14 Aug 2026 10:00:00 GMT</d:getlastmodified>
    <d:getetag>&quot;etag-1&quot;</d:getetag>
    <d:resourcetype/><oc:fileid>{fileid}</oc:fileid><oc:permissions>RGDNVW</oc:permissions>
  </d:prop><d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response>
</d:multistatus>"""
    return httpx.Response(207, text=body)


def mock_readable(mock: respx.MockRouter, fileid: str, path: str) -> respx.Route:
    """Lookup, stat and content of one file; returns the GET route to count reads."""
    mock.route(method="SEARCH", url=DAV_ROOT).mock(return_value=found(fileid, path))
    mock.route(method="PROPFIND", url=f"{FILES_ROOT}{path}").mock(return_value=stat(fileid, path))
    return mock.route(method="GET", url=f"{FILES_ROOT}{path}").mock(
        return_value=httpx.Response(200, content=CONTENT)
    )


def triple(error: ToolError) -> tuple[str, str, str]:
    return (error.message, error.hint, error.reason)


async def refusal(resource_id: str) -> tuple[str, str, str]:
    with pytest.raises(ToolError) as excinfo:
        await chatgpt.fetch(fresh(), resource_id)
    return triple(excinfo.value)


async def unknown(fileid: str) -> tuple[str, str, str]:
    """The answer for an id that belongs to no file, with nothing tagged."""
    with respx.mock(assert_all_called=False) as mock:
        guard_routes.untagged(mock)
        mock.route(method="SEARCH", url=DAV_ROOT).mock(return_value=nothing())
        return await refusal(f"file:{fileid}")


@pytest.mark.anyio
async def test_a_file_id_known_before_the_tag_answers_like_an_unknown_one() -> None:
    with respx.mock(assert_all_called=False) as mock:
        guard_routes.untagged(mock)
        mock_readable(mock, "901", "/Docs/geheim.txt")
        before = await chatgpt.fetch(fresh(), "file:901")
    assert before["text"] == CONTENT.decode()

    guard_routes.reset()
    with respx.mock(assert_all_called=False) as mock:
        guard_routes.active(mock, ("Docs/geheim.txt", "901", False))
        reads = mock_readable(mock, "901", "/Docs/geheim.txt")
        tagged = await refusal("file:901")
    assert reads.call_count == 0, "not one byte of a tagged file is read"

    guard_routes.reset()
    assert tagged == await unknown("901")
    guard_routes.reset()
    other = await unknown("999")
    assert tagged == tuple(part.replace("999", "901") for part in other)
    assert "geheim" not in "".join(tagged)


@pytest.mark.anyio
async def test_a_file_below_a_tagged_folder_answers_like_an_unknown_one() -> None:
    with respx.mock(assert_all_called=False) as mock:
        guard_routes.active(mock, ("Projekt", "900", True))
        reads = mock_readable(mock, "905", "/Projekt/a.txt")
        below = await refusal("file:905")
    assert reads.call_count == 0

    guard_routes.reset()
    assert below == await unknown("905")


@pytest.mark.anyio
async def test_unverifiable_refuses_every_id_with_the_one_uniform_error() -> None:
    expected = triple(withhold.unavailable_error())

    with respx.mock(assert_all_called=False) as mock:
        guard_routes.unverifiable(mock)
        reads = mock_readable(mock, "901", "/Docs/geheim.txt")
        existing = await refusal("file:901")
    assert reads.call_count == 0

    guard_routes.reset()
    with respx.mock(assert_all_called=False) as mock:
        guard_routes.unverifiable(mock)
        mock.route(method="SEARCH", url=DAV_ROOT).mock(return_value=nothing())
        missing = await refusal("file:999")

    assert existing == missing == expected


@pytest.mark.anyio
@pytest.mark.parametrize("status", [500, 503])
async def test_a_failing_lookup_answers_a_tagged_id_and_an_unknown_one_alike(status: int) -> None:
    """D-28-17: the error of the lookup answers before the tag, like files._visible_stat."""
    with respx.mock(assert_all_called=False) as mock:
        guard_routes.active(mock, ("Docs/geheim.txt", "901", False))
        mock.route(method="SEARCH", url=DAV_ROOT).mock(return_value=httpx.Response(status))
        tagged = await refusal("file:901")

    guard_routes.reset()
    with respx.mock(assert_all_called=False) as mock:
        guard_routes.active(mock, ("Docs/geheim.txt", "901", False))
        mock.route(method="SEARCH", url=DAV_ROOT).mock(return_value=httpx.Response(status))
        invented = await refusal("file:999999999")

    assert tagged == tuple(part.replace("999999999", "901") for part in invented)
    assert "geheim" not in "".join(tagged)
    guard_routes.reset()
    assert tagged != await unknown("901")


@pytest.mark.anyio
async def test_unverifiable_still_answers_before_a_failing_lookup() -> None:
    with respx.mock(assert_all_called=False) as mock:
        guard_routes.unverifiable(mock)
        mock.route(method="SEARCH", url=DAV_ROOT).mock(return_value=httpx.Response(500))
        tagged = await refusal("file:901")

    assert tagged == triple(withhold.unavailable_error())


@pytest.mark.anyio
async def test_one_fetch_sends_exactly_one_report() -> None:
    """files_tools.read asks the same guard again; the fast path answers, no second REPORT."""
    with respx.mock(assert_all_called=False) as mock:
        listing, report = guard_routes.active(mock, ("Docs/geheim.txt", "901", False))
        mock_readable(mock, "4711", "/Docs/frei.txt")

        result = await chatgpt.fetch(fresh(), "file:4711")

    assert result["text"] == CONTENT.decode()
    assert listing.call_count == 1
    assert report.call_count == 1


@pytest.mark.anyio
async def test_url_and_card_ids_never_ask_the_guard() -> None:
    with respx.mock(assert_all_called=False) as mock:
        listing = guard_routes.untagged(mock)
        mock.get(CAPABILITIES_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "ocs": {
                        "meta": {"status": "ok", "statuscode": 200, "message": "OK"},
                        "data": {"capabilities": {"core": {}}},
                    }
                },
            )
        )
        with pytest.raises(ToolError):
            await chatgpt.fetch(fresh(), f"url:{BASE}/index.php/apps/calendar")
        with pytest.raises(ToolError):
            await chatgpt.fetch(fresh(), "card:57")

    assert listing.call_count == 0
