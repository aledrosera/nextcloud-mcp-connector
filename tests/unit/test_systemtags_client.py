"""The policy-free tag query client: request shapes, one rule per REPORT, outcomes as values."""

import httpx
import pytest
import respx
from lxml import etree

from mcp_connector import config
from mcp_connector.errors import ToolError
from mcp_connector.nextcloud.clients import systemtags
from mcp_connector.nextcloud.clients import xml as davxml
from mcp_connector.nextcloud.credentials import Credentials

BASE = "http://nc.test"
USER = "alice"
SECRET = "app-password-test"

HOME = f"{BASE}/remote.php/dav/files/alice/"
TAGS = f"{BASE}/remote.php/dav/systemtags/"
CAPABILITIES = f"{BASE}/ocs/v2.php/cloud/capabilities"

XML_HEADERS = {"Content-Type": "application/xml; charset=utf-8"}


@pytest.fixture
def creds() -> Credentials:
    return Credentials(BASE, USER, SECRET)


@pytest.fixture
def client() -> httpx.AsyncClient:
    return httpx.AsyncClient(follow_redirects=False)


def multistatus(*responses: str) -> bytes:
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        f'<d:multistatus xmlns:d="DAV:" xmlns:oc="{davxml.OC}">'
        f"{''.join(responses)}</d:multistatus>"
    ).encode()


def response(href: str, props: str) -> str:
    return (
        f"<d:response><d:href>{href}</d:href><d:propstat><d:prop>{props}</d:prop>"
        "<d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response>"
    )


def node(href: str, fileid: str | None, *, folder: bool = False) -> str:
    props = "" if fileid is None else f"<oc:fileid>{fileid}</oc:fileid>"
    kind = "<d:collection/>" if folder else ""
    return response(href, f"{props}<d:resourcetype>{kind}</d:resourcetype>")


def tag(tag_id: str | None, name: str) -> str:
    props = "" if tag_id is None else f"<oc:id>{tag_id}</oc:id>"
    href = f"/remote.php/dav/systemtags/{tag_id or ''}"
    return response(href, f"{props}<oc:display-name>{name}</oc:display-name>")


def parsed(content: bytes) -> etree._Element:
    return etree.fromstring(content, parser=davxml.hardened_parser())


# --- the REPORT body -------------------------------------------------------------------


def test_the_filter_body_carries_exactly_one_tag_rule() -> None:
    body = parsed(systemtags.filter_files_body("64"))

    assert body.tag == f"{{{davxml.OC}}}filter-files"
    prop = body.find(f"{{{davxml.DAV}}}prop")
    assert prop is not None
    asked = {str(element.tag) for element in prop}
    assert asked == {f"{{{davxml.OC}}}fileid", f"{{{davxml.DAV}}}resourcetype"}
    rules = list(body.iter(f"{{{davxml.OC}}}systemtag"))
    assert len(rules) == 1
    assert rules[0].text == "64"


@pytest.mark.parametrize("tag_id", ["²", "", "6 4", "64<"])
def test_the_filter_body_refuses_anything_but_ascii_digits(tag_id: str) -> None:
    with pytest.raises(ValueError, match="ASCII digits"):
        systemtags.filter_files_body(tag_id)


# --- tagged_nodes ----------------------------------------------------------------------


@pytest.mark.anyio
async def test_the_report_goes_to_the_home_root_even_inside_a_sandbox(
    client: httpx.AsyncClient, creds: Credentials, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(config.ENV_FILES_ROOT, "/Docs")
    with respx.mock(assert_all_mocked=True) as mock:
        route = mock.route(method="REPORT", url=HOME).mock(
            return_value=httpx.Response(207, content=multistatus(), headers=XML_HEADERS)
        )
        result = await systemtags.tagged_nodes(client, creds, "64")

    assert result == systemtags.TaggedSet(status=207, nodes=())
    assert route.call_count == 1
    request = route.calls[0].request
    assert str(request.url) == HOME
    assert request.headers["Content-Type"] == "application/xml"
    assert request.headers["Authorization"].startswith("Basic ")
    rules = list(parsed(request.content).iter(f"{{{davxml.OC}}}systemtag"))
    assert [rule.text for rule in rules] == ["64"]


@pytest.mark.parametrize(
    ("user", "segment"),
    [("alice smith", "alice%20smith"), ("alice@example.org", "alice%40example.org")],
)
def test_the_home_url_encodes_the_user_as_one_segment(user: str, segment: str) -> None:
    url = systemtags.home_url(Credentials(BASE, user, SECRET))

    assert url == f"{BASE}/remote.php/dav/files/{segment}/"


@pytest.mark.anyio
async def test_tagged_nodes_maps_every_response(
    client: httpx.AsyncClient, creds: Credentials
) -> None:
    body = multistatus(
        node("/remote.php/dav/files/alice/Shared/", "12", folder=True),
        node("/remote.php/dav/files/alice/Docs/a.md", "13"),
        node("/other/remote.php/dav/files/alice/x", "14"),
    )
    with respx.mock(assert_all_mocked=True) as mock:
        mock.route(method="REPORT", url=HOME).mock(
            return_value=httpx.Response(207, content=body, headers=XML_HEADERS)
        )
        result = await systemtags.tagged_nodes(client, creds, "64")

    assert result.status == 207
    assert result.nodes == (
        systemtags.TaggedNode(path="/Shared", fileid="12", is_collection=True),
        systemtags.TaggedNode(path="/Docs/a.md", fileid="13", is_collection=False),
        systemtags.TaggedNode(path=None, fileid="14", is_collection=False),
    )


@pytest.mark.anyio
@pytest.mark.parametrize("fileid", [None, "²", "12a", ""])
async def test_tagged_nodes_refuses_a_missing_or_odd_fileid(
    client: httpx.AsyncClient, creds: Credentials, fileid: str | None
) -> None:
    body = multistatus(node("/remote.php/dav/files/alice/Docs/a.md", fileid))
    with respx.mock(assert_all_mocked=True) as mock:
        mock.route(method="REPORT", url=HOME).mock(
            return_value=httpx.Response(207, content=body, headers=XML_HEADERS)
        )
        with pytest.raises(ValueError, match="file id"):
            await systemtags.tagged_nodes(client, creds, "64")


@pytest.mark.anyio
@pytest.mark.parametrize("status", [412, 401, 403, 500, 301])
async def test_tagged_nodes_returns_any_other_status_as_a_value(
    client: httpx.AsyncClient, creds: Credentials, status: int
) -> None:
    with respx.mock(assert_all_mocked=True) as mock:
        route = mock.route(method="REPORT", url=HOME).mock(
            return_value=httpx.Response(status, headers={"Location": f"{BASE}/login"})
        )
        result = await systemtags.tagged_nodes(client, creds, "64")

    assert result == systemtags.TaggedSet(status=status, nodes=())
    assert route.call_count == 1


@pytest.mark.anyio
async def test_tagged_nodes_lets_an_unparsable_body_raise(
    client: httpx.AsyncClient, creds: Credentials
) -> None:
    with respx.mock(assert_all_mocked=True) as mock:
        mock.route(method="REPORT", url=HOME).mock(
            return_value=httpx.Response(207, content=b"<html>login", headers=XML_HEADERS)
        )
        with pytest.raises(ToolError):
            await systemtags.tagged_nodes(client, creds, "64")


@pytest.mark.anyio
async def test_an_invalid_tag_id_never_reaches_the_network(
    client: httpx.AsyncClient, creds: Credentials
) -> None:
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as mock:
        route = mock.route(method="REPORT", url=HOME)
        with pytest.raises(ValueError, match="ASCII digits"):
            await systemtags.tagged_nodes(client, creds, "6 4")

    assert route.call_count == 0


# --- list_tags -------------------------------------------------------------------------


@pytest.mark.anyio
async def test_list_tags_asks_for_id_and_display_name(
    client: httpx.AsyncClient, creds: Credentials
) -> None:
    body = multistatus(
        tag(None, ""),
        tag("64", "kein-ki"),
        tag("65", "Kein-KI"),
    )
    with respx.mock(assert_all_mocked=True) as mock:
        route = mock.route(method="PROPFIND", url=TAGS).mock(
            return_value=httpx.Response(207, content=body, headers=XML_HEADERS)
        )
        listing = await systemtags.list_tags(client, creds)

    assert listing == systemtags.TagListing(
        status=207,
        tags=(systemtags.Tag(id="64", name="kein-ki"), systemtags.Tag(id="65", name="Kein-KI")),
    )
    request = route.calls[0].request
    assert request.headers["Depth"] == "1"
    assert request.headers["Content-Type"] == "application/xml"
    asked = {str(element.tag) for element in parsed(request.content).iter()}
    assert f"{{{davxml.OC}}}id" in asked
    assert f"{{{davxml.OC}}}display-name" in asked


@pytest.mark.anyio
@pytest.mark.parametrize("tag_id", ["²", "6a"])
async def test_list_tags_refuses_an_id_that_is_not_ascii_digits(
    client: httpx.AsyncClient, creds: Credentials, tag_id: str
) -> None:
    with respx.mock(assert_all_mocked=True) as mock:
        mock.route(method="PROPFIND", url=TAGS).mock(
            return_value=httpx.Response(
                207, content=multistatus(tag(tag_id, "kein-ki")), headers=XML_HEADERS
            )
        )
        with pytest.raises(ValueError, match="tag id"):
            await systemtags.list_tags(client, creds)


@pytest.mark.anyio
async def test_list_tags_returns_another_status_as_a_value(
    client: httpx.AsyncClient, creds: Credentials
) -> None:
    with respx.mock(assert_all_mocked=True) as mock:
        route = mock.route(method="PROPFIND", url=TAGS).mock(return_value=httpx.Response(500))
        listing = await systemtags.list_tags(client, creds)

    assert listing == systemtags.TagListing(status=500, tags=())
    assert route.call_count == 1


# --- no capability probe ---------------------------------------------------------------


@pytest.mark.anyio
async def test_the_client_never_asks_for_capabilities(
    client: httpx.AsyncClient, creds: Credentials
) -> None:
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as mock:
        capabilities = mock.get(CAPABILITIES).mock(return_value=httpx.Response(200, json={}))
        mock.route(method="PROPFIND", url=TAGS).mock(
            return_value=httpx.Response(
                207, content=multistatus(tag("64", "kein-ki")), headers=XML_HEADERS
            )
        )
        mock.route(method="REPORT", url=HOME).mock(
            return_value=httpx.Response(207, content=multistatus(), headers=XML_HEADERS)
        )
        await systemtags.list_tags(client, creds)
        await systemtags.tagged_nodes(client, creds, "64")

    assert capabilities.call_count == 0
