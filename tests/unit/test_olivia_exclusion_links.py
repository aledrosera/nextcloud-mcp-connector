"""kein-ki on the fork's own paths (fork olivia): links answer a tagged file like a missing one.

Upstream 0.4.0 guards files_read, files_upload and fetch. The fork hands out and redeems
file content on paths of its own: the download link of files_download and fetch, the /dl
route that redeems it, the upload link of files_upload and the /ul route behind it, and the
Nextcloud files a mail draft attaches. Every one of them asks the same guard through
upstream's own checks (``files._visible_stat`` for a read, ``files._writable`` for a write),
so a tagged item, or one below a tagged folder, answers exactly like a missing one, and a
check that cannot be answered fails closed. Mail attachment links stay outside the guard,
as upstream documents mail as not covered.

The guard requests are mocked for real through ``guard_routes``, as in the upstream
``*_exclusion`` modules.
"""

import asyncio
from typing import Any

import guard_routes
import httpx
import pytest
import respx
from starlette.applications import Starlette
from starlette.testclient import TestClient

from mcp_connector import config
from mcp_connector.deps import TicketOwner
from mcp_connector.downloads import issue, mail_attachment, upload, upload_route
from mcp_connector.downloads import route as dl_route
from mcp_connector.downloads import store as dl_store
from mcp_connector.errors import ToolError
from mcp_connector.nextcloud import NcClients
from mcp_connector.nextcloud.clients import dav
from mcp_connector.nextcloud.credentials import Credentials
from mcp_connector.oauth import store as oauth_store_module
from mcp_connector.tools import chatgpt, drafts, withhold

BASE = guard_routes.BASE
USER = guard_routes.USER
HOME = f"{BASE}/remote.php/dav/files/{USER}"
OWNER = TicketOwner("auth-1", USER)
LINK_ENV = {config.ENV_PUBLIC_URL: "https://cloud.example/exapps/mcp_connector"}
ROUTE_ENV = {
    config.ENV_APP_ID: "mcp_connector",
    config.ENV_APP_SECRET: "app-secret-test",
    config.ENV_APP_VERSION: "0.4.0",
    config.ENV_NEXTCLOUD_URL: BASE,
}
KEY = bytes(range(32))

TAGGED_FILE = ("Docs/geheim.pdf", "901", False)
TAGGED_FOLDER = ("Projekt", "900", True)
#: (path, fileid) of a tagged file and of a file below a tagged folder.
WITHHELD = (("/Docs/geheim.pdf", "901"), ("/Projekt/a.pdf", "905"))
MISSING = "/Docs/fehlt.pdf"


@pytest.fixture(autouse=True)
def _fresh_tag_cache() -> None:
    guard_routes.reset()


def _clients() -> NcClients:
    """One bundle per tool call, as ``deps.resolve_clients`` builds it: one guard each."""
    return NcClients(httpx.AsyncClient(), Credentials(BASE, USER, "app-password-test"))


def _tuple(err: ToolError) -> tuple[str, str, str]:
    return (err.message, err.hint, err.reason)


def _stat_body(path: str, fileid: str, content_type: str = "application/pdf") -> str:
    return (
        '<?xml version="1.0"?><d:multistatus xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns">'
        f"<d:response><d:href>/remote.php/dav/files/{USER}{path}</d:href><d:propstat><d:prop>"
        f"<d:getcontentlength>5</d:getcontentlength><d:getcontenttype>{content_type}"
        f"</d:getcontenttype><d:resourcetype/><oc:fileid>{fileid}</oc:fileid></d:prop>"
        "<d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response></d:multistatus>"
    )


def _existing(mock: respx.MockRouter, path: str, fileid: str) -> respx.Route:
    return mock.route(method="PROPFIND", url=f"{HOME}{path}").mock(
        return_value=httpx.Response(207, text=_stat_body(path, fileid))
    )


def _missing(mock: respx.MockRouter, path: str) -> respx.Route:
    return mock.route(method="PROPFIND", url=f"{HOME}{path}").mock(return_value=httpx.Response(404))


def _mock() -> respx.MockRouter:
    return respx.mock(assert_all_mocked=True, assert_all_called=False)


# --- the download link: files_download -------------------------------------------------------


async def _link_refusal(path: str, tickets: dl_store.TicketStore) -> ToolError:
    with pytest.raises(ToolError) as caught:
        await issue.issue_link(_clients(), OWNER, path, env=LINK_ENV, tickets=tickets)
    return caught.value


@pytest.mark.anyio
@pytest.mark.parametrize(("path", "fileid"), WITHHELD)
async def test_no_download_link_for_a_tagged_file(path: str, fileid: str, tmp_path: Any) -> None:
    tickets = dl_store.TicketStore(tmp_path / dl_store.TICKETS_FILENAME)
    with _mock() as mock:
        guard_routes.active(mock, TAGGED_FILE, TAGGED_FOLDER)
        _existing(mock, path, fileid)
        tagged = await _link_refusal(path, tickets)

    with _mock() as mock:
        guard_routes.active(mock, TAGGED_FILE, TAGGED_FOLDER)
        _missing(mock, path)
        missing = await _link_refusal(path, tickets)

    assert _tuple(tagged) == _tuple(missing) == _tuple(dav.not_found(path))


@pytest.mark.anyio
async def test_no_download_link_while_the_check_cannot_be_answered(tmp_path: Any) -> None:
    tickets = dl_store.TicketStore(tmp_path / dl_store.TICKETS_FILENAME)
    with _mock() as mock:
        guard_routes.unverifiable(mock)
        _existing(mock, "/Docs/frei.pdf", "11")
        existing = await _link_refusal("/Docs/frei.pdf", tickets)

    with _mock() as mock:
        guard_routes.unverifiable(mock)
        _missing(mock, MISSING)
        missing = await _link_refusal(MISSING, tickets)

    assert _tuple(existing) == _tuple(missing) == _tuple(withhold.unavailable_error())


# --- the download link of fetch(file) --------------------------------------------------------


@pytest.mark.anyio
@pytest.mark.parametrize(("path", "fileid"), WITHHELD)
async def test_fetch_hands_out_no_link_for_a_tagged_binary_file(
    path: str, fileid: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def found(_client: object, _creds: object, wanted: str) -> dict[str, Any]:
        return {"path": path, "fileid": wanted, "content_type": "application/pdf", "size": 5}

    async def no_link(*_args: object, **_kwargs: object) -> dict[str, Any]:
        raise AssertionError("a link was issued for a withheld file")

    monkeypatch.setattr(chatgpt.dav_client, "find_by_fileid", found)
    monkeypatch.setattr(chatgpt.issue, "issue_link", no_link)
    with _mock() as mock:
        guard_routes.active(mock, TAGGED_FILE, TAGGED_FOLDER)
        with pytest.raises(ToolError) as caught:
            await chatgpt._fetch_file(_clients(), fileid, owner=OWNER)

    assert _tuple(caught.value) == _tuple(chatgpt._no_file(fileid))


@pytest.mark.anyio
async def test_fetch_hands_out_no_link_while_the_check_cannot_be_answered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def found(_client: object, _creds: object, wanted: str) -> dict[str, Any]:
        return {"path": "/Docs/frei.pdf", "fileid": wanted, "content_type": "application/pdf"}

    async def no_link(*_args: object, **_kwargs: object) -> dict[str, Any]:
        raise AssertionError("a link was issued while the check could not be answered")

    monkeypatch.setattr(chatgpt.dav_client, "find_by_fileid", found)
    monkeypatch.setattr(chatgpt.issue, "issue_link", no_link)
    with _mock() as mock:
        guard_routes.unverifiable(mock)
        with pytest.raises(ToolError) as caught:
            await chatgpt._fetch_file(_clients(), "11", owner=OWNER)

    assert _tuple(caught.value) == _tuple(withhold.unavailable_error())


# --- the /dl route: a tag set after the link was issued -------------------------------------


def run(work: Any) -> Any:
    return asyncio.run(work)


@pytest.fixture
def oauth(tmp_path: Any) -> oauth_store_module.OAuthStore:
    store = oauth_store_module.OAuthStore(tmp_path / oauth_store_module.STORE_FILENAME, KEY)
    run(store.save_client("client-1", metadata_json='{"client_id": "client-1"}'))
    run(
        store.create_authorization(
            "auth-1",
            client_id="client-1",
            nc_user=USER,
            nc_account_id=USER,
            app_password="app-password-test",
            scopes="nextcloud",
            resource="https://nc.example/exapps/x/mcp",
        )
    )
    return store


@pytest.fixture
def tickets(tmp_path: Any) -> dl_store.TicketStore:
    return dl_store.TicketStore(tmp_path / dl_store.TICKETS_FILENAME)


def _client(routes: list[Any]) -> TestClient:
    return TestClient(Starlette(routes=routes))


def _download_client(oauth: Any, tickets: dl_store.TicketStore) -> TestClient:
    async def provider() -> Any:
        return oauth

    return _client(dl_route.download_routes(ROUTE_ENV, oauth_store=provider, tickets=tickets))


def _ticket(tickets: dl_store.TicketStore, path: str) -> str:
    token, _ = run(
        tickets.issue(
            auth_id="auth-1",
            nc_user=USER,
            path=path,
            name=path.rsplit("/", 1)[-1],
            content_type="application/pdf",
            size=5,
            ttl_seconds=600,
        )
    )
    return token


@pytest.mark.parametrize(("path", "fileid"), WITHHELD)
def test_the_download_route_answers_a_tagged_file_like_a_missing_one(
    path: str, fileid: str, oauth: Any, tickets: dl_store.TicketStore
) -> None:
    client = _download_client(oauth, tickets)
    tagged_token, missing_token = _ticket(tickets, path), _ticket(tickets, MISSING)
    with _mock() as mock:
        guard_routes.active(mock, TAGGED_FILE, TAGGED_FOLDER)
        _existing(mock, path, fileid)
        _missing(mock, MISSING)
        get = mock.get(f"{HOME}{path}").mock(return_value=httpx.Response(200, content=b"%PDF-"))
        mock.get(f"{HOME}{MISSING}").mock(return_value=httpx.Response(404))
        tagged = client.get(f"/dl/{tagged_token}")
        missing = client.get(f"/dl/{missing_token}")

    assert (tagged.status_code, tagged.text) == (missing.status_code, missing.text)
    assert (tagged.status_code, tagged.text) == (404, "Not found")
    assert get.call_count == 0, "no byte of a withheld file leaves Nextcloud"
    assert run(tickets.peek(tagged_token)) is not None, "released like a missing file"


def test_the_download_route_fails_closed_while_the_check_cannot_be_answered(
    oauth: Any, tickets: dl_store.TicketStore
) -> None:
    client = _download_client(oauth, tickets)
    token = _ticket(tickets, "/Docs/frei.pdf")
    with _mock() as mock:
        guard_routes.unverifiable(mock)
        _existing(mock, "/Docs/frei.pdf", "11")
        get = mock.get(f"{HOME}/Docs/frei.pdf").mock(return_value=httpx.Response(200))
        answer = client.get(f"/dl/{token}")

    assert (answer.status_code, answer.text) == (503, withhold.EXCLUSION_UNAVAILABLE)
    assert get.call_count == 0
    assert run(tickets.peek(token)) is not None, "the link stays usable for a retry"


def test_mail_attachment_links_stay_outside_the_guard(
    oauth: Any, tickets: dl_store.TicketStore
) -> None:
    """Upstream documents mail as not covered; the route asks no guard for an attachment."""
    client = _download_client(oauth, tickets)
    token = _ticket(tickets, mail_attachment.ticket_path("21", "2"))
    with _mock() as mock:
        listing, _ = guard_routes.unverifiable(mock)
        mock.get(f"{BASE}/index.php/apps/mail/api/messages/21/attachment/2").mock(
            return_value=httpx.Response(200, content=b"%PDF-")
        )
        answer = client.get(f"/dl/{token}")

    assert (answer.status_code, answer.content) == (200, b"%PDF-")
    assert listing.call_count == 0


# --- the upload link: files_upload without content -------------------------------------------


async def _upload_refusal(path: str, tickets: dl_store.TicketStore) -> ToolError:
    with pytest.raises(ToolError) as caught:
        await upload.issue_upload_link(_clients(), OWNER, path, env=LINK_ENV, tickets=tickets)
    return caught.value


@pytest.mark.anyio
@pytest.mark.parametrize("path", ["/Projekt/neu.pdf", "/Projekt/Unter/neu.pdf", "/Docs/geheim.pdf"])
async def test_no_upload_link_into_or_onto_what_is_tagged(
    path: str, tickets: dl_store.TicketStore
) -> None:
    """Upstream's write refusal, also for a tagged file under a visible parent (D-27-01)."""
    with _mock() as mock:
        guard_routes.active(mock, TAGGED_FILE, TAGGED_FOLDER)
        stat = _existing(mock, path, "901")
        refused = await _upload_refusal(path, tickets)

    assert _tuple(refused) == _tuple(dav.parent_missing(path))
    assert "already exists" not in refused.message
    assert stat.call_count == 0, "no PROPFIND before the check: it would tell existing apart"


@pytest.mark.anyio
async def test_no_upload_link_while_the_check_cannot_be_answered(
    tickets: dl_store.TicketStore,
) -> None:
    with _mock() as mock:
        guard_routes.unverifiable(mock)
        stat = _missing(mock, "/Docs/neu.pdf")
        refused = await _upload_refusal("/Docs/neu.pdf", tickets)

    assert _tuple(refused) == _tuple(withhold.unavailable_error())
    assert stat.call_count == 0


# --- the /ul route: a tag set after the link was issued -------------------------------------


def _upload_client(oauth: Any, tickets: dl_store.TicketStore) -> TestClient:
    async def provider() -> Any:
        return oauth

    return _client(upload_route.upload_routes(ROUTE_ENV, oauth_store=provider, tickets=tickets))


def _upload_ticket(tickets: dl_store.TicketStore, path: str) -> str:
    token, _ = run(
        tickets.issue(
            auth_id="auth-1",
            nc_user=USER,
            path=upload.upload_ticket_path(path),
            name=path.rsplit("/", 1)[-1],
            content_type="",
            size=0,
            ttl_seconds=1800,
        )
    )
    return token


def _writes(mock: respx.MockRouter) -> list[respx.Route]:
    return [
        mock.route(method="MKCOL", url__startswith=HOME).mock(return_value=httpx.Response(201)),
        mock.route(method="PUT", url__startswith=HOME).mock(return_value=httpx.Response(201)),
    ]


@pytest.mark.parametrize("path", ["/Projekt/neu.pdf", "/Projekt/Unter/neu.pdf"])
def test_the_upload_route_writes_nothing_into_a_tagged_folder(
    path: str, oauth: Any, tickets: dl_store.TicketStore
) -> None:
    client = _upload_client(oauth, tickets)
    token = _upload_ticket(tickets, path)
    with _mock() as mock:
        guard_routes.active(mock, TAGGED_FOLDER)
        writes = _writes(mock)
        answer = client.put(f"/ul/{token}", content=b"%PDF-1.7")

    assert answer.status_code == 409
    assert answer.json() == {"error": "conflict", "path": path}
    assert [route.call_count for route in writes] == [0, 0], "no MKCOL, no PUT"
    assert run(tickets.peek(token)) is None, "spent, like a missing parent folder"


def test_the_upload_route_fails_closed_while_the_check_cannot_be_answered(
    oauth: Any, tickets: dl_store.TicketStore
) -> None:
    client = _upload_client(oauth, tickets)
    token = _upload_ticket(tickets, "/Docs/neu.pdf")
    with _mock() as mock:
        guard_routes.unverifiable(mock)
        writes = _writes(mock)
        answer = client.put(f"/ul/{token}", content=b"%PDF-1.7")

    assert (answer.status_code, answer.text) == (503, withhold.EXCLUSION_UNAVAILABLE)
    assert [route.call_count for route in writes] == [0, 0]
    assert run(tickets.peek(token)) is not None, "the link stays usable for a retry"


# --- mail_draft: Nextcloud files attached to a draft -----------------------------------------


async def _attachment_refusal(path: str) -> ToolError:
    with pytest.raises(ToolError) as caught:
        await drafts._checked_attachments(_clients(), [path])
    return caught.value


@pytest.mark.anyio
@pytest.mark.parametrize(("path", "fileid"), WITHHELD)
async def test_a_tagged_file_is_not_attached_to_a_draft(path: str, fileid: str) -> None:
    """A draft is readable through fetch(mail) and its attachment links, so it is a way out."""
    with _mock() as mock:
        guard_routes.active(mock, TAGGED_FILE, TAGGED_FOLDER)
        _existing(mock, path, fileid)
        tagged = await _attachment_refusal(path)

    with _mock() as mock:
        guard_routes.active(mock, TAGGED_FILE, TAGGED_FOLDER)
        _missing(mock, path)
        missing = await _attachment_refusal(path)

    assert _tuple(tagged) == _tuple(missing)
    assert dav.not_found(path).message in tagged.message


@pytest.mark.anyio
async def test_no_attachment_while_the_check_cannot_be_answered() -> None:
    with _mock() as mock:
        guard_routes.unverifiable(mock)
        _existing(mock, "/Docs/frei.pdf", "11")
        refused = await _attachment_refusal("/Docs/frei.pdf")

    assert withhold.EXCLUSION_UNAVAILABLE in refused.message
    assert refused.hint == withhold.UNAVAILABLE_HINT
