"""Tag details, object counts and the admin proof of exclusion:check (plan 29-03).

The fixtures are the response bodies measured on nc35 in plan 29-01 (run 2, blocks M1b,
M2, M2b and M3 of raw/29-01-messungen.txt), copied verbatim.
"""

import dataclasses

import httpx
import pytest
import respx
from lxml import etree

from mcp_connector.errors import ToolError
from mcp_connector.nextcloud.clients import systemtags
from mcp_connector.nextcloud.clients import xml as davxml
from mcp_connector.nextcloud.credentials import Credentials

BASE = "http://nc.test"
TAGS = f"{BASE}/remote.php/dav/systemtags/"
XML_HEADERS = {"Content-Type": "application/xml; charset=utf-8"}

# --- measured bodies (29-01, run 2) ------------------------------------------------------

#: M2, PROPFIND Depth 1 with oc:groups as the impersonated admin: status 207.
M2_ADMIN = (
    b'<?xml version="1.0"?>\n'
    b'<d:multistatus xmlns:d="DAV:" xmlns:s="http://sabredav.org/ns" '
    b'xmlns:oc="http://owncloud.org/ns" xmlns:nc="http://nextcloud.org/ns"><d:response>'
    b"<d:href>/remote.php/dav/systemtags/</d:href><d:propstat><d:prop><oc:id/>"
    b"<oc:display-name/><oc:user-visible/><oc:user-assignable/><oc:groups/></d:prop>"
    b"<d:status>HTTP/1.1 404 Not Found</d:status></d:propstat></d:response><d:response>"
    b"<d:href>/remote.php/dav/systemtags/193/</d:href><d:propstat><d:prop><oc:id>193</oc:id>"
    b"<oc:display-name>kein-ki-m2</oc:display-name><oc:user-visible>false</oc:user-visible>"
    b"<oc:user-assignable>false</oc:user-assignable><oc:groups></oc:groups></d:prop>"
    b"<d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response><d:response>"
    b"<d:href>/remote.php/dav/systemtags/194/</d:href><d:propstat><d:prop><oc:id>194</oc:id>"
    b"<oc:display-name>kein-ki-m2r</oc:display-name><oc:user-visible>true</oc:user-visible>"
    b"<oc:user-assignable>false</oc:user-assignable><oc:groups>ki-m2</oc:groups></d:prop>"
    b"<d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response></d:multistatus>"
)

#: M2, the same PROPFIND with oc:groups as alice (no admin): the whole answer is 403.
M2_ALICE = (
    b'<?xml version="1.0" encoding="utf-8"?>\n'
    b'<d:error xmlns:d="DAV:" xmlns:s="http://sabredav.org/ns">\n'
    b"  <s:exception>Sabre\\DAV\\Exception\\Forbidden</s:exception>\n"
    b"  <s:message/>\n"
    b"</d:error>"
)

#: M1b, PROPFIND Depth 1 without oc:groups as alice: status 207.
M1B_ALICE = (
    b'<?xml version="1.0"?>\n'
    b'<d:multistatus xmlns:d="DAV:" xmlns:s="http://sabredav.org/ns" '
    b'xmlns:oc="http://owncloud.org/ns" xmlns:nc="http://nextcloud.org/ns"><d:response>'
    b"<d:href>/remote.php/dav/systemtags/</d:href><d:propstat><d:prop><oc:id/>"
    b"<oc:display-name/><oc:user-visible/><oc:user-assignable/></d:prop>"
    b"<d:status>HTTP/1.1 404 Not Found</d:status></d:propstat></d:response><d:response>"
    b"<d:href>/remote.php/dav/systemtags/194/</d:href><d:propstat><d:prop><oc:id>194</oc:id>"
    b"<oc:display-name>kein-ki-m2r</oc:display-name><oc:user-visible>true</oc:user-visible>"
    b"<oc:user-assignable>false</oc:user-assignable></d:prop>"
    b"<d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response><d:response>"
    b"<d:href>/remote.php/dav/systemtags/195/</d:href><d:propstat><d:prop><oc:id>195</oc:id>"
    b"<oc:display-name>kein-ki-m3</oc:display-name><oc:user-visible>true</oc:user-visible>"
    b"<oc:user-assignable>true</oc:user-assignable></d:prop>"
    b"<d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response></d:multistatus>"
)

#: M3, PROPFIND Depth 0 on kein-ki-m3 as admin: two files assignments.
M3_ADMIN = (
    b'<?xml version="1.0"?>\n'
    b'<d:multistatus xmlns:d="DAV:" xmlns:s="http://sabredav.org/ns" '
    b'xmlns:oc="http://owncloud.org/ns" xmlns:nc="http://nextcloud.org/ns"><d:response>'
    b"<d:href>/remote.php/dav/systemtags/195/</d:href><d:propstat><d:prop>"
    b"<oc:display-name>kein-ki-m3</oc:display-name><nc:object-ids><nc:object-ids>"
    b"<nc:id>0</nc:id><nc:type>files</nc:type></nc:object-ids><nc:object-ids><nc:id>1</nc:id>"
    b"<nc:type>files</nc:type></nc:object-ids></nc:object-ids></d:prop>"
    b"<d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response></d:multistatus>"
)


@pytest.fixture
def creds() -> Credentials:
    return Credentials(BASE, "admin", "app-password-test")


@pytest.fixture
def client() -> httpx.AsyncClient:
    return httpx.AsyncClient(follow_redirects=False)


def parsed(content: bytes) -> etree._Element:
    return etree.fromstring(content, parser=davxml.hardened_parser())


def asked_props(content: bytes) -> set[str]:
    prop = parsed(content).find(f"{{{davxml.DAV}}}prop")
    assert prop is not None
    return {str(element.tag) for element in prop}


def object_ids(*types: str) -> bytes:
    inner = "".join(
        f"<nc:object-ids><nc:id>{index}</nc:id><nc:type>{kind}</nc:type></nc:object-ids>"
        for index, kind in enumerate(types)
    )
    return (
        '<?xml version="1.0"?><d:multistatus xmlns:d="DAV:" '
        f'xmlns:oc="{davxml.OC}" xmlns:nc="{davxml.NC}"><d:response>'
        "<d:href>/remote.php/dav/systemtags/7/</d:href><d:propstat><d:prop>"
        f"<nc:object-ids>{inner}</nc:object-ids></d:prop>"
        "<d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response></d:multistatus>"
    ).encode()


def tag_listing(*responses: str) -> bytes:
    return (
        '<?xml version="1.0"?><d:multistatus xmlns:d="DAV:" '
        f'xmlns:oc="{davxml.OC}">{"".join(responses)}</d:multistatus>'
    ).encode()


def tag_response(href: str, props: str, status: str = "HTTP/1.1 200 OK") -> str:
    return (
        f"<d:response><d:href>{href}</d:href><d:propstat><d:prop>{props}</d:prop>"
        f"<d:status>{status}</d:status></d:propstat></d:response>"
    )


# --- list_tag_details --------------------------------------------------------------------


@pytest.mark.anyio
async def test_details_without_groups_never_ask_for_groups(
    client: httpx.AsyncClient, creds: Credentials
) -> None:
    with respx.mock(assert_all_mocked=True) as mock:
        route = mock.route(method="PROPFIND", url=TAGS).mock(
            return_value=httpx.Response(207, content=M1B_ALICE, headers=XML_HEADERS)
        )
        result = await systemtags.list_tag_details(client, creds, with_groups=False)

    request = route.calls[0].request
    assert request.headers["Depth"] == "1"
    assert asked_props(request.content) == {
        f"{{{davxml.OC}}}id",
        f"{{{davxml.OC}}}display-name",
        f"{{{davxml.OC}}}user-visible",
        f"{{{davxml.OC}}}user-assignable",
    }
    assert result == systemtags.TagDetailListing(
        status=207,
        tags=(
            systemtags.TagDetail("194", "kein-ki-m2r", True, False, None, None),
            systemtags.TagDetail("195", "kein-ki-m3", True, True, None, None),
        ),
    )


@pytest.mark.anyio
async def test_details_with_groups_read_the_measured_admin_answer(
    client: httpx.AsyncClient, creds: Credentials
) -> None:
    with respx.mock(assert_all_mocked=True) as mock:
        route = mock.route(method="PROPFIND", url=TAGS).mock(
            return_value=httpx.Response(207, content=M2_ADMIN, headers=XML_HEADERS)
        )
        result = await systemtags.list_tag_details(client, creds, with_groups=True)

    assert f"{{{davxml.OC}}}groups" in asked_props(route.calls[0].request.content)
    assert result == systemtags.TagDetailListing(
        status=207,
        tags=(
            systemtags.TagDetail("193", "kein-ki-m2", False, False, (), 200),
            systemtags.TagDetail("194", "kein-ki-m2r", True, False, ("ki-m2",), 200),
        ),
    )


@pytest.mark.anyio
async def test_groups_as_a_non_admin_turn_the_whole_answer_into_403(
    client: httpx.AsyncClient, creds: Credentials
) -> None:
    """M2: Nextcloud does not answer a 403 propstat, it refuses the whole PROPFIND."""
    with respx.mock(assert_all_mocked=True) as mock:
        mock.route(method="PROPFIND", url=TAGS).mock(
            return_value=httpx.Response(403, content=M2_ALICE, headers=XML_HEADERS)
        )
        result = await systemtags.list_tag_details(client, creds, with_groups=True)

    assert result == systemtags.TagDetailListing(status=403, tags=())


@pytest.mark.anyio
async def test_a_forbidden_groups_propstat_keeps_its_status(
    client: httpx.AsyncClient, creds: Credentials
) -> None:
    body = (
        '<?xml version="1.0"?><d:multistatus xmlns:d="DAV:" '
        f'xmlns:oc="{davxml.OC}"><d:response><d:href>/remote.php/dav/systemtags/5/</d:href>'
        "<d:propstat><d:prop><oc:id>5</oc:id><oc:display-name>kein-ki</oc:display-name>"
        "<oc:user-visible>1</oc:user-visible><oc:user-assignable>0</oc:user-assignable>"
        "</d:prop><d:status>HTTP/1.1 200 OK</d:status></d:propstat>"
        "<d:propstat><d:prop><oc:groups/></d:prop>"
        "<d:status>HTTP/1.1 403 Forbidden</d:status></d:propstat></d:response></d:multistatus>"
    ).encode()
    with respx.mock(assert_all_mocked=True) as mock:
        mock.route(method="PROPFIND", url=TAGS).mock(
            return_value=httpx.Response(207, content=body, headers=XML_HEADERS)
        )
        result = await systemtags.list_tag_details(client, creds, with_groups=True)

    assert result.tags == (systemtags.TagDetail("5", "kein-ki", True, False, None, 403),)


@pytest.mark.anyio
async def test_several_groups_are_split_on_the_pipe(
    client: httpx.AsyncClient, creds: Credentials
) -> None:
    body = tag_listing(
        tag_response(
            "/remote.php/dav/systemtags/5/",
            "<oc:id>5</oc:id><oc:display-name>kein-ki</oc:display-name>"
            "<oc:user-visible>true</oc:user-visible><oc:user-assignable>false</oc:user-assignable>"
            "<oc:groups>ki-verantwortung|admin</oc:groups>",
        )
    )
    with respx.mock(assert_all_mocked=True) as mock:
        mock.route(method="PROPFIND", url=TAGS).mock(
            return_value=httpx.Response(207, content=body, headers=XML_HEADERS)
        )
        result = await systemtags.list_tag_details(client, creds, with_groups=True)

    assert result.tags[0].groups == ("ki-verantwortung", "admin")


@pytest.mark.anyio
@pytest.mark.parametrize("status", [401, 500])
async def test_details_return_the_status_and_no_tags_when_not_207(
    client: httpx.AsyncClient, creds: Credentials, status: int
) -> None:
    with respx.mock(assert_all_mocked=True) as mock:
        mock.route(method="PROPFIND", url=TAGS).mock(return_value=httpx.Response(status))
        result = await systemtags.list_tag_details(client, creds, with_groups=False)

    assert result == systemtags.TagDetailListing(status=status, tags=())


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("entry", "message"),
    [
        (
            tag_response(
                "/remote.php/dav/systemtags/9/", "<oc:display-name>kein-ki</oc:display-name>"
            ),
            "without an id",
        ),
        (
            tag_response(
                "/remote.php/dav/systemtags/9/",
                "<oc:id>9²</oc:id><oc:display-name>kein-ki</oc:display-name>",
            ),
            "ASCII digits",
        ),
    ],
)
async def test_details_refuse_a_tag_without_a_digit_id(
    client: httpx.AsyncClient, creds: Credentials, entry: str, message: str
) -> None:
    with respx.mock(assert_all_mocked=True) as mock:
        mock.route(method="PROPFIND", url=TAGS).mock(
            return_value=httpx.Response(207, content=tag_listing(entry), headers=XML_HEADERS)
        )
        with pytest.raises(ValueError, match=message):
            await systemtags.list_tag_details(client, creds, with_groups=False)


@pytest.mark.anyio
async def test_details_reject_a_document_type_declaration(
    client: httpx.AsyncClient, creds: Credentials
) -> None:
    body = (
        b'<?xml version="1.0"?><!DOCTYPE d:multistatus [<!ENTITY x "kein-ki">]>'
        b'<d:multistatus xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns"><d:response>'
        b"<d:href>/remote.php/dav/systemtags/5/</d:href><d:propstat><d:prop>"
        b"<oc:id>5</oc:id><oc:display-name>&x;</oc:display-name></d:prop>"
        b"<d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response></d:multistatus>"
    )
    with respx.mock(assert_all_mocked=True) as mock:
        mock.route(method="PROPFIND", url=TAGS).mock(
            return_value=httpx.Response(207, content=body, headers=XML_HEADERS)
        )
        with pytest.raises(ToolError):
            await systemtags.list_tag_details(client, creds, with_groups=False)


@pytest.mark.anyio
async def test_details_reject_a_body_that_is_no_multistatus(
    client: httpx.AsyncClient, creds: Credentials
) -> None:
    with respx.mock(assert_all_mocked=True) as mock:
        mock.route(method="PROPFIND", url=TAGS).mock(
            return_value=httpx.Response(207, content=M2_ALICE, headers=XML_HEADERS)
        )
        with pytest.raises(ToolError):
            await systemtags.list_tag_details(client, creds, with_groups=False)


# --- count_tag_objects -------------------------------------------------------------------


@pytest.mark.anyio
async def test_the_count_of_the_measured_answer_is_two(
    client: httpx.AsyncClient, creds: Credentials
) -> None:
    with respx.mock(assert_all_mocked=True) as mock:
        route = mock.route(method="PROPFIND", url=f"{TAGS}195").mock(
            return_value=httpx.Response(207, content=M3_ADMIN, headers=XML_HEADERS)
        )
        result = await systemtags.count_tag_objects(client, creds, "195")

    request = route.calls[0].request
    assert request.headers["Depth"] == "0"
    assert asked_props(request.content) == {f"{{{davxml.NC}}}object-ids"}
    assert result == systemtags.ObjectCount(status=207, files=2)


@pytest.mark.anyio
async def test_only_files_assignments_are_counted(
    client: httpx.AsyncClient, creds: Credentials
) -> None:
    with respx.mock(assert_all_mocked=True) as mock:
        mock.route(method="PROPFIND", url=f"{TAGS}7").mock(
            return_value=httpx.Response(
                207, content=object_ids("files", "calendar", " files "), headers=XML_HEADERS
            )
        )
        result = await systemtags.count_tag_objects(client, creds, "7")

    assert result == systemtags.ObjectCount(status=207, files=2)


@pytest.mark.anyio
async def test_an_untagged_tag_counts_zero(client: httpx.AsyncClient, creds: Credentials) -> None:
    with respx.mock(assert_all_mocked=True) as mock:
        mock.route(method="PROPFIND", url=f"{TAGS}7").mock(
            return_value=httpx.Response(207, content=object_ids(), headers=XML_HEADERS)
        )
        result = await systemtags.count_tag_objects(client, creds, "7")

    assert result == systemtags.ObjectCount(status=207, files=0)


@pytest.mark.anyio
async def test_a_missing_object_ids_property_is_an_unknown_count(
    client: httpx.AsyncClient, creds: Credentials
) -> None:
    body = tag_listing(
        tag_response("/remote.php/dav/systemtags/7/", "<oc:id/>", "HTTP/1.1 404 Not Found")
    )
    with respx.mock(assert_all_mocked=True) as mock:
        mock.route(method="PROPFIND", url=f"{TAGS}7").mock(
            return_value=httpx.Response(207, content=body, headers=XML_HEADERS)
        )
        result = await systemtags.count_tag_objects(client, creds, "7")

    assert result == systemtags.ObjectCount(status=207, files=None)


@pytest.mark.anyio
@pytest.mark.parametrize("status", [401, 404, 500])
async def test_the_count_is_none_when_not_207(
    client: httpx.AsyncClient, creds: Credentials, status: int
) -> None:
    with respx.mock(assert_all_mocked=True) as mock:
        mock.route(method="PROPFIND", url=f"{TAGS}7").mock(return_value=httpx.Response(status))
        result = await systemtags.count_tag_objects(client, creds, "7")

    assert result == systemtags.ObjectCount(status=status, files=None)


@pytest.mark.anyio
@pytest.mark.parametrize("tag_id", ["²", "", "7/../8", "7 "])
async def test_the_count_refuses_a_non_digit_id_before_any_request(
    client: httpx.AsyncClient, creds: Credentials, tag_id: str
) -> None:
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as mock:
        route = mock.route()
        with pytest.raises(ValueError, match="ASCII digits"):
            await systemtags.count_tag_objects(client, creds, tag_id)

    assert route.call_count == 0


def test_an_object_count_has_no_field_that_could_carry_an_id() -> None:
    assert [field.name for field in dataclasses.fields(systemtags.ObjectCount)] == [
        "status",
        "files",
    ]
    assert "0" not in repr(systemtags.ObjectCount(status=207, files=2)).replace("207", "")


# --- method gate (T-29-09) ---------------------------------------------------------------


@pytest.mark.anyio
async def test_details_and_count_only_ever_send_propfind(
    client: httpx.AsyncClient, creds: Credentials
) -> None:
    with respx.mock(assert_all_mocked=True) as mock:
        catch_all = mock.route().mock(
            return_value=httpx.Response(207, content=M3_ADMIN, headers=XML_HEADERS)
        )
        await systemtags.count_tag_objects(client, creds, "195")
        catch_all.mock(return_value=httpx.Response(207, content=M2_ADMIN, headers=XML_HEADERS))
        await systemtags.list_tag_details(client, creds, with_groups=True)
        await systemtags.list_tag_details(client, creds, with_groups=False)

    assert catch_all.call_count == 3
    assert {call.request.method for call in catch_all.calls} == {"PROPFIND"}
