"""``occ mcp_connector:exclusion:check``: the handler of the kein-ki audit (OPS-01, plan 29-04).

The verdict itself is measured in ``tests/unit/test_exclusion_audit.py`` and the reads in
``tests/unit/test_systemtags_details.py``. What is under test here is the handler between
them and the console of an administrator, with these decisions of phase 29 as the sources:

* **D-29-01** the answer names the operating mode with a sentence, the delegated group ids,
  the number of assignments and a warning per variant.
* **D-29-02 / D-29-10** it never names an object id, a path or an account: neither the uid
  handed to ``--admin`` nor the account it read as without one.
* **D-29-03** a missing kein-ki tag is a hint with ``passed`` true, also with ``--admin`` and
  also when the administrator could not be confirmed, and it carries the create command.
* **D-29-04** the answer is always HTTP 200: text with one line per step (all seven), or
  JSON with the key ``passed`` behind ``--json``.
* **D-29-09** with ``--admin=<uid>`` the handler proves that account is an administrator
  before it judges; without it only visible tags are read, and the answer says so.

Threats: **T-29-12** (reached from outside: ``x-origin-ip`` is 404, no AppAPI header is 401,
no ``<url>`` in the manifest), **T-29-13** (only PROPFIND and GET leave this handler),
**T-29-14** (no account, path, id or header value in text, JSON or log, base64 form included),
**T-29-15** (``--admin`` is stripped, bounded and free of control characters, and never put
into a URL).

Every Nextcloud answer comes from respx; the bodies follow the nc35 measurements of plan
29-01 (raw/29-01-messungen.txt, run 2). The uids are chosen so that none of them collides
with a word the answer has to contain, such as "admin" or "administrators".
"""

import base64
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from lxml import etree
from starlette.applications import Starlette
from starlette.testclient import TestClient

from mcp_connector import config
from mcp_connector.errors import ToolError
from mcp_connector.exapp import audit_verify, exclusion_check
from mcp_connector.nextcloud import exclusion_audit
from mcp_connector.nextcloud.clients.xml import DAV, NC, OC, hardened_parser

APP_ID = "mcp_connector"
APP_SECRET = "app-secret-test"
APP_VERSION = "0.1.0"
BASE = "http://nc.test"

ENV = {
    config.ENV_APP_ID: APP_ID,
    config.ENV_APP_SECRET: APP_SECRET,
    config.ENV_APP_VERSION: APP_VERSION,
    config.ENV_AA_VERSION: "35.0.0",
    config.ENV_NEXTCLOUD_URL: BASE,
}

TAGS = f"{BASE}/remote.php/dav/systemtags/"
ADMIN_USERS = f"{BASE}/ocs/v2.php/cloud/groups/admin/users"
USERS = f"{BASE}/ocs/v2.php/apps/app_api/api/v1/users"
MANIFEST = Path(__file__).resolve().parents[2] / "appinfo" / "info.xml"

ADMIN_UID = "chk-adm-7f3"
PLAIN_UID = "chk-usr-2b9"
READER_UID = "chk-rdr-5c1"
OFF_UID = "chk-off-9d4"
UIDS = (ADMIN_UID, PLAIN_UID, READER_UID, OFF_UID)

#: The running ``nc:id`` values of the count fixture: distinct enough to be searched for.
OBJECT_IDS = ("880011", "880012", "880013", "880014", "880015")

CREATE_COMMAND = "php occ tag:add kein-ki public"
NO_TAG = "no kein-ki tag exists, the connector filters nothing"
NO_VISIBLE_TAG = "no visible kein-ki tag exists"
NOT_CHECKED = "invisible tags and delegation groups were not checked"
RUN_AGAIN = "run again with --admin=<uid>"
UNCONFIRMED = "administrator could not be confirmed; " + NOT_CHECKED

#: Read off the verdict module, so a new outcome there reaches this file as a failure.
OUTCOMES = frozenset(
    {
        exclusion_audit.OUTCOME_PASSED,
        exclusion_audit.OUTCOME_FAILED,
        exclusion_audit.OUTCOME_SKIPPED,
        exclusion_audit.OUTCOME_NOT_CHECKED,
        exclusion_audit.OUTCOME_NOTE,
    }
)

ADMIN_YES = {"ocs": {"meta": {"status": "ok", "statuscode": 200, "message": "OK"}, "data": {}}}
ADMIN_NO = {"ocs": {"meta": {"status": "failure", "statuscode": 403, "message": ""}, "data": []}}

WRITE_METHODS = ("PROPPATCH", "POST", "PUT", "DELETE", "MKCOL", "MOVE", "COPY", "REPORT")


# --- fixtures and helpers -----------------------------------------------------------------


def token_of(user: str) -> str:
    """The value of ``AUTHORIZATION-APP-API`` for ``user``: base64 of ``user:secret``."""
    return base64.b64encode(f"{user}:{APP_SECRET}".encode()).decode()


def appapi_headers(user: str = "", secret: str = APP_SECRET) -> dict[str, str]:
    """What AppAPI puts on an internal call; the user is empty, this is the app context."""
    return {
        "EX-APP-ID": APP_ID,
        "EX-APP-VERSION": APP_VERSION,
        "AUTHORIZATION-APP-API": base64.b64encode(f"{user}:{secret}".encode()).decode(),
    }


def user_of(request: httpx.Request) -> str:
    """The impersonated account of one outgoing request, read out of the AppAPI token."""
    raw = base64.b64decode(request.headers["AUTHORIZATION-APP-API"]).decode()
    return raw.split(":", 1)[0]


def tag(
    tag_id: str,
    name: str,
    *,
    visible: bool = True,
    assignable: bool = True,
    groups: str | None = None,
) -> str:
    """One ``d:response`` of the detail listing; ``groups`` only when the caller asked."""
    props = (
        f"<oc:id>{tag_id}</oc:id><oc:display-name>{name}</oc:display-name>"
        f"<oc:user-visible>{str(visible).lower()}</oc:user-visible>"
        f"<oc:user-assignable>{str(assignable).lower()}</oc:user-assignable>"
    )
    if groups is not None:
        props += f"<oc:groups>{groups}</oc:groups>"
    return (
        f"<d:response><d:href>/remote.php/dav/systemtags/{tag_id}/</d:href><d:propstat>"
        f"<d:prop>{props}</d:prop><d:status>HTTP/1.1 200 OK</d:status></d:propstat>"
        "</d:response>"
    )


def listing(*responses: str) -> bytes:
    """The Multi-Status of the detail listing, with the collection entry first (as measured)."""
    collection = (
        "<d:response><d:href>/remote.php/dav/systemtags/</d:href><d:propstat><d:prop><oc:id/>"
        "<oc:display-name/><oc:user-visible/><oc:user-assignable/></d:prop>"
        "<d:status>HTTP/1.1 404 Not Found</d:status></d:propstat></d:response>"
    )
    return (
        '<?xml version="1.0"?>\n'
        f'<d:multistatus xmlns:d="{DAV}" xmlns:s="http://sabredav.org/ns" '
        f'xmlns:oc="{OC}" xmlns:nc="{NC}">{collection}{"".join(responses)}</d:multistatus>'
    ).encode()


def counted(tag_id: str, files: int) -> bytes:
    """The Depth 0 answer on one tag: ``files`` inner ``nc:object-ids`` of type files."""
    inner = "".join(
        f"<nc:object-ids><nc:id>{OBJECT_IDS[i]}</nc:id><nc:type>files</nc:type></nc:object-ids>"
        for i in range(files)
    )
    return (
        '<?xml version="1.0"?>\n'
        f'<d:multistatus xmlns:d="{DAV}" xmlns:oc="{OC}" xmlns:nc="{NC}"><d:response>'
        f"<d:href>/remote.php/dav/systemtags/{tag_id}/</d:href><d:propstat><d:prop>"
        f"<nc:object-ids>{inner}</nc:object-ids></d:prop>"
        "<d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response></d:multistatus>"
    ).encode()


def users_answer(*uids: str) -> dict[str, Any]:
    return {
        "ocs": {"meta": {"status": "ok", "statuscode": 200, "message": "OK"}, "data": list(uids)}
    }


def multistatus(body: bytes) -> httpx.Response:
    return httpx.Response(207, content=body, headers={"Content-Type": "application/xml"})


@pytest.fixture
def router() -> Iterator[respx.MockRouter]:
    """respx for every Nextcloud call, and the method gate on every call it saw (T-29-13)."""
    with respx.mock(assert_all_called=False) as mock:
        yield mock
        for call_ in mock.calls:
            method = call_.request.method
            assert method in {"PROPFIND", "GET"}, f"the handler sent {method}"
            assert method not in WRITE_METHODS


def admin_proof(
    router: respx.MockRouter, answer: dict[str, Any] | None, status: int = 200
) -> respx.Route:
    route = router.get(ADMIN_USERS)
    if answer is None:
        return route
    return route.mock(return_value=httpx.Response(status, json=answer))


def tag_listing(router: respx.MockRouter, body: bytes) -> respx.Route:
    return router.route(method="PROPFIND", url=TAGS).mock(return_value=multistatus(body))


def tag_count(router: respx.MockRouter, tag_id: str, files: int) -> respx.Route:
    return router.route(method="PROPFIND", url=f"{TAGS}{tag_id}").mock(
        return_value=multistatus(counted(tag_id, files))
    )


def client_for(env: dict[str, str] = ENV) -> TestClient:
    """One process of this application with nothing on it but the check route."""
    return TestClient(Starlette(routes=exclusion_check.exclusion_check_routes(env)))


def call(
    *,
    admin: str | None = None,
    as_json: bool = False,
    body: object | None = None,
    headers: dict[str, str] | None = None,
    env: dict[str, str] = ENV,
    content: bytes | None = None,
) -> Any:
    """One occ invocation, as AppAPI delivers it: a POST with the options in the body.

    ``Any`` for the reason ``tests/unit/test_exapp_exchange_check.py`` gives: the Starlette
    test client answers with the response type of another httpx distribution.
    """
    options: dict[str, Any] = {}
    if admin is not None:
        options[exclusion_check.ADMIN_OPTION] = admin
    if as_json:
        options[exclusion_check.JSON_OPTION] = True
    payload = body if body is not None else {"occ": {"arguments": None, "options": options}}
    client = client_for(env)
    sent_headers = appapi_headers() if headers is None else headers
    if content is not None:
        return client.post(
            exclusion_check.EXCLUSION_CHECK_PATH, content=content, headers=sent_headers
        )
    return client.post(exclusion_check.EXCLUSION_CHECK_PATH, json=payload, headers=sent_headers)


def step_lines(text: str) -> list[str]:
    """The lines of the text answer that report a step, told apart by their first word."""
    return [line for line in text.splitlines() if line.split(" ", 1)[0] in OUTCOMES]


def outcome_of(payload: dict[str, Any], step: str) -> str:
    return next(entry["outcome"] for entry in payload["steps"] if entry["step"] == step)


# --- who may reach the handler at all: T-29-12 ---------------------------------------------


def test_a_call_over_the_php_proxy_is_not_found(router: respx.MockRouter) -> None:
    response = call(headers={**appapi_headers(), "x-origin-ip": "1.2.3.4"})

    assert response.status_code == 404
    assert not router.calls


def test_a_call_without_the_appapi_headers_is_unauthorized(router: respx.MockRouter) -> None:
    assert call(headers={}).status_code == 401
    assert call(headers=appapi_headers(secret="wrong")).status_code == 401
    assert not router.calls


def test_the_path_is_declared_in_no_route_of_the_manifest() -> None:
    root = etree.parse(str(MANIFEST), hardened_parser()).getroot()
    urls = [(element.text or "").strip() for element in root.iter("url")]

    assert urls, "with no url at all this test would prove nothing"
    bare = exclusion_check.EXCLUSION_CHECK_PATH.strip("/")
    for url in urls:
        assert bare not in url


def test_the_spellings_this_module_copies_stay_equal_to_the_ones_it_copied() -> None:
    assert exclusion_check.HEADER_ORIGIN_IP == audit_verify.HEADER_ORIGIN_IP == "x-origin-ip"
    assert exclusion_check.TRUE_WORDS == audit_verify.TRUE_WORDS
    assert exclusion_check.JSON_OPTION == audit_verify.JSON_OPTION
    assert exclusion_check.OCC_ENVELOPE == audit_verify.OCC_ENVELOPE
    assert exclusion_check.MAX_ANNOUNCED_DIGITS == audit_verify.MAX_ANNOUNCED_DIGITS
    assert exclusion_check.MAX_BODY_BYTES == audit_verify.MAX_BODY_BYTES == 4096


def test_the_contract_29_05_builds_on() -> None:
    assert exclusion_check.EXCLUSION_CHECK_PATH == "/exclusion-check"
    assert exclusion_check.ADMIN_OPTION == "admin"
    assert exclusion_check.JSON_OPTION == "json"
    assert exclusion_check.MAX_UID_LENGTH == 64


def test_every_step_has_a_name_an_administrator_reads() -> None:
    assert set(exclusion_check.STEP_NAMES) == set(exclusion_audit.STEPS)


# --- the body: always 200 ------------------------------------------------------------------


def test_a_body_above_the_bound_is_a_named_result(router: respx.MockRouter) -> None:
    padding = "x" * (exclusion_check.MAX_BODY_BYTES + 1)
    response = call(body={"occ": {"options": {"admin": ADMIN_UID, "pad": padding}}})

    assert response.status_code == 200
    assert exclusion_check.OUTCOME_BODY_NOT_READ in response.text
    assert not router.calls


def test_an_announced_body_above_the_bound_is_refused_the_same_way(
    router: respx.MockRouter,
) -> None:
    headers = {**appapi_headers(), "content-length": str(10 * exclusion_check.MAX_BODY_BYTES)}
    response = client_for().post(
        exclusion_check.EXCLUSION_CHECK_PATH, content=b"{}", headers=headers
    )

    assert response.status_code == 200
    assert exclusion_check.OUTCOME_BODY_NOT_READ in response.text
    assert not router.calls


def test_a_body_that_is_not_json_is_a_named_result(router: respx.MockRouter) -> None:
    response = call(content=b"not json")

    assert response.status_code == 200
    assert exclusion_check.OUTCOME_BODY_NOT_READ in response.text
    assert not router.calls


# --- with --admin: the verdicts of D-29-01 and D-29-03 -------------------------------------


def test_a_public_tag_is_self_service_with_its_count(router: respx.MockRouter) -> None:
    admin_proof(router, ADMIN_YES)
    tag_listing(router, listing(tag("195", "kein-ki", groups=""), tag("196", "Projekt", groups="")))
    tag_count(router, "195", 3)

    text = call(admin=ADMIN_UID).text
    lines = step_lines(text)

    assert len(lines) == len(exclusion_audit.STEPS) == 7
    for step, line in zip(exclusion_audit.STEPS, lines, strict=True):
        assert exclusion_check.STEP_NAMES[step] in line
    assert text.splitlines()[0] == exclusion_check.HEAD_LINE
    assert exclusion_check.MODE_SENTENCES[exclusion_audit.MODE_SELF_SERVICE] in text
    assert "3" in text
    assert "Projekt" not in text
    assert text.rstrip("\n").endswith(exclusion_check.LIMIT_SENTENCE)


def test_the_same_run_as_json(router: respx.MockRouter) -> None:
    admin_proof(router, ADMIN_YES)
    tag_listing(router, listing(tag("195", "kein-ki", groups="")))
    tag_count(router, "195", 3)

    response = call(admin=ADMIN_UID, as_json=True)
    payload = response.json()

    assert response.status_code == 200
    assert payload["checked"] is True
    assert payload["passed"] is True
    assert payload["mode"] == "self_service"
    assert payload["assigned"] == 3
    assert payload["unprotected"] == 0
    assert payload["admin_checked"] is True
    assert [entry["step"] for entry in payload["steps"]] == list(exclusion_audit.STEPS)
    assert set(payload["steps"][0]) == {"step", "name", "outcome", "note"}
    assert payload["tags"] == [
        {"name": "kein-ki", "access": "public", "groups": [], "assigned": 3, "kind": "exact"}
    ]
    assert payload["limit"] == exclusion_check.LIMIT_SENTENCE


def test_a_restricted_tag_with_a_group_is_organisation_mode(router: respx.MockRouter) -> None:
    admin_proof(router, ADMIN_YES)
    tag_listing(router, listing(tag("194", "kein-ki", assignable=False, groups="ki-verantwortung")))
    tag_count(router, "194", 2)

    text = call(admin=ADMIN_UID).text
    payload = call(admin=ADMIN_UID, as_json=True).json()

    assert "Organisation mode" in text
    assert "ki-verantwortung" in text
    assert payload["mode"] == "organisation"
    assert payload["tags"][0]["groups"] == ["ki-verantwortung"]
    assert payload["tags"][0]["access"] == "restricted"


def test_a_restricted_tag_without_groups_says_only_administrators(router: respx.MockRouter) -> None:
    admin_proof(router, ADMIN_YES)
    tag_listing(router, listing(tag("194", "kein-ki", assignable=False, groups="")))
    tag_count(router, "194", 0)

    text = call(admin=ADMIN_UID).text

    assert "only administrators" in text


def test_an_invisible_exact_tag_is_misconfigured(router: respx.MockRouter) -> None:
    admin_proof(router, ADMIN_YES)
    tag_listing(router, listing(tag("193", "kein-ki", visible=False, assignable=False, groups="")))
    tag_count(router, "193", 1)

    text = call(admin=ADMIN_UID).text
    payload = call(admin=ADMIN_UID, as_json=True).json()

    assert payload["passed"] is False
    assert payload["mode"] == "misconfigured"
    assert payload["tags"][0]["access"] == "invisible"
    assert exclusion_check.INVISIBLE_SENTENCE in text
    assert "does not work for users" in text


def test_only_a_variant_fails(router: respx.MockRouter) -> None:
    admin_proof(router, ADMIN_YES)
    tag_listing(router, listing(tag("201", "Kein KI", groups="")))
    tag_count(router, "201", 4)

    payload = call(admin=ADMIN_UID, as_json=True).json()
    text = call(admin=ADMIN_UID).text

    assert payload["passed"] is False
    assert payload["mode"] == "misconfigured"
    assert payload["unprotected"] == 4
    assert "Items tagged 'Kein KI' are NOT excluded: 4" in text


def test_an_exact_tag_beside_a_variant_passes_with_a_warning(router: respx.MockRouter) -> None:
    admin_proof(router, ADMIN_YES)
    tag_listing(router, listing(tag("195", "kein-ki", groups=""), tag("202", "keinki", groups="")))
    tag_count(router, "195", 3)
    tag_count(router, "202", 2)

    payload = call(admin=ADMIN_UID, as_json=True).json()
    text = call(admin=ADMIN_UID).text

    assert payload["passed"] is True
    assert payload["unprotected"] == 2
    assert "Items tagged 'keinki' are NOT excluded: 2" in text


def test_other_and_similar_tags_are_never_counted(router: respx.MockRouter) -> None:
    admin_proof(router, ADMIN_YES)
    tag_listing(
        router,
        listing(
            tag("195", "kein-ki", groups=""),
            tag("203", "kein-kai", groups=""),
            tag("204", "Urlaub", groups=""),
        ),
    )
    tag_count(router, "195", 1)
    similar = router.route(method="PROPFIND", url=f"{TAGS}203")
    other = router.route(method="PROPFIND", url=f"{TAGS}204")

    payload = call(admin=ADMIN_UID, as_json=True).json()

    assert not similar.called
    assert not other.called
    assert [entry["kind"] for entry in payload["tags"]] == ["exact", "similar"]
    assert payload["tags"][1]["assigned"] is None


def test_no_tag_with_a_confirmed_administrator_is_a_hint(router: respx.MockRouter) -> None:
    admin_proof(router, ADMIN_YES)
    tag_listing(router, listing(tag("196", "Projekt", groups="")))

    text = call(admin=ADMIN_UID).text
    payload = call(admin=ADMIN_UID, as_json=True).json()

    assert payload["passed"] is True
    assert payload["admin_checked"] is True
    assert NO_TAG in text
    assert CREATE_COMMAND in text
    assert NO_VISIBLE_TAG not in text


def test_no_tag_with_an_unconfirmable_administrator_stays_a_hint(router: respx.MockRouter) -> None:
    """D-29-03: confirm_admin None is the way without an admin view, never passed=false."""
    admin_proof(router, None).mock(return_value=httpx.Response(500, text="oops"))
    listed = tag_listing(router, listing(tag("196", "Projekt")))

    text = call(admin=ADMIN_UID).text
    payload = call(admin=ADMIN_UID, as_json=True).json()

    assert payload["passed"] is True
    assert payload["checked"] is True
    assert payload["admin_checked"] is False
    assert UNCONFIRMED in text
    assert NO_VISIBLE_TAG in text
    assert NO_TAG not in text
    assert CREATE_COMMAND in text
    request = listed.calls.last.request
    assert user_of(request) == ADMIN_UID
    assert b"groups" not in request.content


def test_a_timeout_of_the_admin_proof_is_the_same_way(router: respx.MockRouter) -> None:
    admin_proof(router, None).mock(side_effect=httpx.ReadTimeout("slow"))
    tag_listing(router, listing())

    payload = call(admin=ADMIN_UID, as_json=True).json()

    assert payload["passed"] is True
    assert payload["admin_checked"] is False


def test_a_named_account_that_is_no_administrator_ends_the_run(router: respx.MockRouter) -> None:
    proof = admin_proof(router, ADMIN_NO, status=403)
    listed = router.route(method="PROPFIND")

    payload = call(admin=PLAIN_UID, as_json=True).json()
    text = call(admin=PLAIN_UID).text

    assert payload["checked"] is False
    assert payload["passed"] is False
    assert payload["mode"] is None
    assert outcome_of(payload, exclusion_audit.STEP_ADMIN_IDENTITY) == "failed"
    assert exclusion_check.NOT_ADMIN_SENTENCE in text
    assert proof.call_count == 2
    assert not listed.called
    assert len(router.calls) == 2


def test_the_admin_proof_and_the_listing_run_as_the_named_account(router: respx.MockRouter) -> None:
    proof = admin_proof(router, ADMIN_YES)
    listed = tag_listing(router, listing(tag("195", "kein-ki", groups="")))
    tag_count(router, "195", 1)

    call(admin=f"  {ADMIN_UID}\t")

    assert user_of(proof.calls.last.request) == ADMIN_UID
    assert user_of(listed.calls.last.request) == ADMIN_UID
    assert b"groups" in listed.calls.last.request.content
    for call_ in router.calls:
        assert ADMIN_UID not in str(call_.request.url)


@pytest.mark.parametrize("uid", ["a" * 65, "chk\x00adm", "chk\nadm", "chk​adm"])
def test_an_admin_value_that_is_no_uid_is_refused_unsent(
    router: respx.MockRouter, uid: str
) -> None:
    response = call(admin=uid)
    payload = call(admin=uid, as_json=True).json()

    assert response.status_code == 200
    assert exclusion_check.BAD_UID_SENTENCE in response.text
    assert payload["checked"] is False
    assert payload["passed"] is False
    assert not router.calls


def test_a_uid_of_exactly_the_bound_is_accepted(router: respx.MockRouter) -> None:
    uid = "b" * exclusion_check.MAX_UID_LENGTH
    proof = admin_proof(router, ADMIN_YES)
    tag_listing(router, listing())

    call(admin=uid)

    assert user_of(proof.calls.last.request) == uid


# --- without --admin: the reading account of 29-01 -----------------------------------------


def test_without_admin_the_first_account_that_reads_is_used(router: respx.MockRouter) -> None:
    router.get(USERS).mock(return_value=httpx.Response(200, json=users_answer(READER_UID, OFF_UID)))
    proof = admin_proof(router, ADMIN_YES)
    readers: list[str] = []

    def answer(request: httpx.Request) -> httpx.Response:
        readers.append(user_of(request))
        assert b"groups" not in request.content
        if user_of(request) == OFF_UID:
            return httpx.Response(401)
        return multistatus(
            listing(
                tag("195", "kein-ki"),
                tag("193", "kein-ki-hidden", visible=False, assignable=False),
                tag("197", "kein-ki", visible=False, assignable=False),
            )
        )

    router.route(method="PROPFIND", url=TAGS).mock(side_effect=answer)
    counts = tag_count(router, "195", 2)

    payload = call(as_json=True).json()

    assert readers == [OFF_UID, READER_UID]
    assert user_of(counts.calls.last.request) == READER_UID
    assert not proof.called
    assert payload["passed"] is True
    assert payload["admin_checked"] is False
    assert payload["mode"] == "self_service"
    assert [entry["access"] for entry in payload["tags"]] == ["public"]
    assert payload["assigned"] == 2


def test_without_admin_the_answer_says_what_was_not_checked(router: respx.MockRouter) -> None:
    router.get(USERS).mock(return_value=httpx.Response(200, json=users_answer(READER_UID)))
    listed = tag_listing(router, listing(tag("195", "kein-ki")))
    tag_count(router, "195", 1)

    text = call().text

    assert f"{NOT_CHECKED}; {RUN_AGAIN}" in text
    assert b"groups" not in listed.calls.last.request.content


def test_without_admin_and_without_a_visible_tag_the_hint_says_visible(
    router: respx.MockRouter,
) -> None:
    router.get(USERS).mock(return_value=httpx.Response(200, json=users_answer(READER_UID)))
    tag_listing(router, listing(tag("196", "Projekt")))

    text = call().text
    payload = call(as_json=True).json()

    assert NO_VISIBLE_TAG in text
    assert NO_TAG not in text
    assert CREATE_COMMAND in text
    assert payload["passed"] is True
    assert payload["admin_checked"] is False


def test_without_admin_five_failed_accounts_end_the_run(router: respx.MockRouter) -> None:
    accounts = [f"chk-acc-{n}x" for n in range(7)]
    router.get(USERS).mock(return_value=httpx.Response(200, json=users_answer(*accounts)))
    listed = router.route(method="PROPFIND", url=TAGS).mock(return_value=httpx.Response(401))

    payload = call(as_json=True).json()

    assert listed.call_count == exclusion_check.MAX_READ_ATTEMPTS == 5
    assert payload["checked"] is False
    assert payload["passed"] is False
    assert payload["mode"] is None
    assert payload["reason"] == exclusion_check.REASON_NO_READER


@pytest.mark.parametrize("answer", [httpx.Response(500), httpx.Response(200, json={"ocs": {}})])
def test_without_admin_an_unreadable_account_list_is_a_named_result(
    router: respx.MockRouter, answer: httpx.Response
) -> None:
    router.get(USERS).mock(return_value=answer)
    listed = router.route(method="PROPFIND")

    payload = call(as_json=True).json()

    assert payload["checked"] is False
    assert payload["passed"] is False
    assert payload["reason"] == exclusion_check.REASON_NO_ACCOUNTS
    assert not listed.called


# --- every failure is a named result, never "no tag": T-29-16 ------------------------------


@pytest.mark.parametrize(
    ("response", "reason"),
    [
        (httpx.Response(401), "Nextcloud answered 401"),
        (httpx.Response(500), "Nextcloud answered 500"),
        (httpx.ReadTimeout("slow"), "ReadTimeout"),
        (httpx.Response(207, content=b"<not xml"), "unreadable answer"),
    ],
)
def test_a_listing_that_fails_is_a_named_result(
    router: respx.MockRouter, response: httpx.Response | Exception, reason: str
) -> None:
    admin_proof(router, ADMIN_YES)
    route = router.route(method="PROPFIND", url=TAGS)
    if isinstance(response, Exception):
        route.mock(side_effect=response)
    else:
        route.mock(return_value=response)

    payload = call(admin=ADMIN_UID, as_json=True).json()
    text = call(admin=ADMIN_UID).text

    assert payload["checked"] is False
    assert payload["passed"] is False
    assert payload["mode"] is None
    assert reason in payload["reason"]
    assert reason in text
    assert outcome_of(payload, exclusion_audit.STEP_TAG_LISTING_READABLE) == "failed"
    assert NO_TAG not in text
    assert NO_VISIBLE_TAG not in text


def test_a_count_that_fails_fails_the_count_step(router: respx.MockRouter) -> None:
    admin_proof(router, ADMIN_YES)
    tag_listing(router, listing(tag("195", "kein-ki", groups="")))
    router.route(method="PROPFIND", url=f"{TAGS}195").mock(return_value=httpx.Response(500))

    payload = call(admin=ADMIN_UID, as_json=True).json()

    assert payload["passed"] is False
    assert payload["assigned"] is None
    assert outcome_of(payload, exclusion_audit.STEP_ASSIGNMENT_COUNT) == "failed"


def test_an_exception_is_reported_by_type_and_never_by_message(
    router: respx.MockRouter, caplog: pytest.LogCaptureFixture
) -> None:
    admin_proof(router, None).mock(side_effect=RuntimeError("geheim"))

    with caplog.at_level("DEBUG"):
        response = call(admin=ADMIN_UID)
        payload = call(admin=ADMIN_UID, as_json=True).json()

    assert response.status_code == 200
    assert "RuntimeError" in response.text
    assert payload == {"checked": False, "passed": False, "error": "RuntimeError"}
    for body in (response.text, json.dumps(payload), caplog.text):
        assert "geheim" not in body


def test_an_incomplete_deploy_environment_is_a_named_result(
    router: respx.MockRouter, monkeypatch: pytest.MonkeyPatch
) -> None:
    def missing(env: object = None) -> object:
        raise ToolError(message="NEXTCLOUD_URL is not set.")

    monkeypatch.setattr(exclusion_check, "_guard", lambda request, env: "")
    monkeypatch.setattr(exclusion_check.config, "exapp_settings", missing)

    response = call(admin=ADMIN_UID)
    payload = call(admin=ADMIN_UID, as_json=True).json()

    assert response.status_code == 200
    assert "deploy environment incomplete" in response.text
    assert payload["checked"] is False
    assert payload["passed"] is False
    assert not router.calls


# --- privacy and side effects: T-29-14 and the audit log -----------------------------------


def test_no_account_id_path_or_header_value_reaches_text_json_or_log(
    router: respx.MockRouter, caplog: pytest.LogCaptureFixture
) -> None:
    router.get(USERS).mock(return_value=httpx.Response(200, json=users_answer(OFF_UID, READER_UID)))
    admin_proof(router, ADMIN_YES)

    def answer(request: httpx.Request) -> httpx.Response:
        if user_of(request) == OFF_UID:
            return httpx.Response(401)
        return multistatus(
            listing(
                tag("195", "kein-ki", groups="ki-verantwortung"), tag("202", "keinki", groups="")
            )
        )

    router.route(method="PROPFIND", url=TAGS).mock(side_effect=answer)
    tag_count(router, "195", 5)
    tag_count(router, "202", 2)

    with caplog.at_level("DEBUG"):
        bodies = [
            call(admin=ADMIN_UID).text,
            json.dumps(call(admin=ADMIN_UID, as_json=True).json()),
            call().text,
            json.dumps(call(as_json=True).json()),
            call(admin=PLAIN_UID).text,
        ]
    bodies.append(caplog.text)

    forbidden = [*UIDS, *OBJECT_IDS, *(token_of(uid) for uid in UIDS), APP_SECRET, "files/"]
    forbidden.append(base64.b64encode(f"{ADMIN_UID}:".encode()).decode().rstrip("="))
    for body in bodies:
        for value in forbidden:
            assert value not in body, f"{value!r} leaked"


def test_one_log_line_per_run_without_names(
    router: respx.MockRouter, caplog: pytest.LogCaptureFixture
) -> None:
    admin_proof(router, ADMIN_YES)
    tag_listing(router, listing(tag("195", "kein-ki", groups="")))
    tag_count(router, "195", 3)

    with caplog.at_level("INFO", logger="mcp_connector.exapp.exclusion_check"):
        call(admin=ADMIN_UID)

    records = [r for r in caplog.records if r.name == "mcp_connector.exapp.exclusion_check"]
    assert len(records) == 1
    message = records[0].getMessage()
    for word in ("passed=True", "mode=self_service", "assigned=3", "admin_checked=True"):
        assert word in message
    assert "kein-ki" not in message


def test_the_handler_writes_no_audit_entry(
    router: respx.MockRouter, monkeypatch: pytest.MonkeyPatch
) -> None:
    from mcp_connector.audit import record, store

    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("the exclusion check wrote an audit entry")

    monkeypatch.setattr(store.AuditStore, "append", refuse)
    monkeypatch.setattr(record, "note", refuse)
    admin_proof(router, ADMIN_YES)
    tag_listing(router, listing(tag("195", "kein-ki", groups="")))
    tag_count(router, "195", 1)

    payload = call(admin=ADMIN_UID, as_json=True).json()

    assert payload["checked"] is True
    source = Path(exclusion_check.__file__).read_text(encoding="utf-8")
    assert "audit.record" not in source
    assert "audit.store" not in source


def test_the_client_provider_is_the_one_used(router: respx.MockRouter) -> None:
    provided: list[httpx.AsyncClient] = []

    def provider() -> httpx.AsyncClient:
        client = httpx.AsyncClient()
        provided.append(client)
        return client

    admin_proof(router, ADMIN_YES)
    tag_listing(router, listing())
    routes = exclusion_check.exclusion_check_routes(ENV, client_provider=provider)
    payload = {"occ": {"options": {"admin": ADMIN_UID, "json": True}}}

    response = TestClient(Starlette(routes=routes)).post(
        exclusion_check.EXCLUSION_CHECK_PATH, json=payload, headers=appapi_headers()
    )

    assert response.json()["checked"] is True
    assert provided
