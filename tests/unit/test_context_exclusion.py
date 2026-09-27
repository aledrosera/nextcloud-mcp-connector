"""prepare_context behind the ``kein-ki`` guard (EXCL-03, D-27-03, D-27-05, Merker (c)).

No ``patch_untagged`` here: the search and the Talk legs run against real routes and the
real guard, the calendar and the mail legs are faked as in ``test_tools_context.py``,
because neither of them carries file content. A fresh ``NcClients`` per bundle, so every
bundle has its own guard.

Three properties are proven here and nowhere else:

*   The flight belongs to ``prepare_context`` itself: a leg with a short budget (Talk, 5 s)
    that runs into its ceiling while the REPORT is still out must not cancel the flight the
    other legs wait on, so the REPORT goes out once.
*   One bundle costs one REPORT, also at ``detail="full"`` where the excerpts read files
    through ``fetch``.
*   "Could not check" is one entry under ``degraded``, however many legs reported it.
"""

import asyncio
import json
from typing import Any

import guard_routes
import httpx
import pytest
import respx

from mcp_connector.nextcloud import NcClients, capabilities
from mcp_connector.nextcloud.credentials import Credentials
from mcp_connector.tools import calendar as calendar_tools
from mcp_connector.tools import context as context_tools
from mcp_connector.tools import mail as mail_tools
from mcp_connector.tools import withhold

BASE = guard_routes.BASE
USER = guard_routes.USER
PROVIDERS_URL = f"{BASE}/ocs/v2.php/search/providers"
CAPABILITIES_URL = f"{BASE}/ocs/v2.php/cloud/capabilities"
ROOM_URL = f"{BASE}/ocs/v2.php/apps/spreed/api/v4/room"
DAV_ROOT = f"{BASE}/remote.php/dav/"
FILES_ROOT = f"{BASE}/remote.php/dav/files/{USER}"
SPREED = {"features": ["chat-v2"], "config": {"chat": {"max-length": 32000}}}
EXCLUSION = {"source": "exclusion", "reason": withhold.EXCLUSION_UNAVAILABLE}
WINDOW = ("2026-09-27T10:00:00+00:00", "2026-10-04T10:00:00+00:00")
CONTENT = b"Offener Text fuer den Ausschnitt.\n"

SECRET_NAME = "geheim.txt"
SECRET_PATH = "Docs/geheim.txt"


@pytest.fixture(autouse=True)
def _fresh_caches(monkeypatch: pytest.MonkeyPatch) -> None:
    guard_routes.reset()
    capabilities.clear_cache()
    monkeypatch.setattr(context_tools, "_window", lambda: WINDOW)


@pytest.fixture(autouse=True)
def _quiet_legs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Calendar and mail carry no file content; they answer empty without a request."""

    async def no_events(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        return {"range": {"start": "", "end": "", "timezone": "UTC"}, "count": 0, "events": []}

    async def no_accounts(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        return {"level": "accounts", "count": 0, "results": []}

    monkeypatch.setattr(calendar_tools, "list_events", no_events)
    monkeypatch.setattr(mail_tools, "browse", no_accounts)


def fresh() -> NcClients:
    """One NcClients per bundle, so every bundle has its own guard."""
    return NcClients(
        client=httpx.AsyncClient(follow_redirects=False),
        creds=Credentials(BASE, USER, "app-password-test"),
    )


def envelope(data: Any) -> dict[str, Any]:
    return {"ocs": {"meta": {"status": "ok", "statuscode": 200, "message": "OK"}, "data": data}}


def providers(*ids: str) -> httpx.Response:
    return httpx.Response(
        200, json=envelope([{"id": pid, "name": pid, "order": n} for n, pid in enumerate(ids)])
    )


def answer(entries: list[Any]) -> httpx.Response:
    return httpx.Response(
        200,
        json=envelope({"name": "x", "isPaginated": False, "entries": entries, "cursor": None}),
    )


def search_url(provider_id: str) -> str:
    return f"{PROVIDERS_URL}/{provider_id}/search"


def files_entry(fileid: str, path: str) -> dict[str, Any]:
    return {
        "thumbnailUrl": "",
        "title": path.rsplit("/", 1)[-1],
        "subline": "in " + (path.rsplit("/", 1)[0] or "/"),
        "resourceUrl": f"{BASE}/index.php/f/{fileid}",
        "icon": "icon-file",
        "attributes": {"fileId": fileid, "path": path},
    }


def findling_entry(fileid: str, title: str = "Vertrag.pdf") -> dict[str, Any]:
    return {
        "thumbnailUrl": "",
        "title": title,
        "subline": "... ein Satz aus dem Dokument ...",
        "resourceUrl": f"/index.php/f/{fileid}",
        "icon": "icon-search",
        "rounded": False,
        "attributes": {"fileId": fileid},
    }


def file_param(fileid: str, name: str, path: str) -> dict[str, Any]:
    return {
        "type": "file",
        "id": fileid,
        "name": name,
        "path": path,
        "link": f"{BASE}/index.php/f/{fileid}",
        "mimetype": "text/plain",
    }


def secret_last_message() -> dict[str, Any]:
    return {
        "id": 42,
        "token": "abcd1234",
        "actorType": "users",
        "actorId": "bob",
        "actorDisplayName": "Bob Beispiel",
        "timestamp": 1755180042,
        "message": "Siehe {file}",
        "messageParameters": {"file": file_param("901", SECRET_NAME, SECRET_PATH)},
        "messageType": "object_shared",
    }


def waiting_room() -> dict[str, Any]:
    """One conversation with something unread whose last message shares the tagged file."""
    return {
        "token": "abcd1234",
        "type": 2,
        "displayName": "Baustelle Süd",
        "permissions": 254,
        "readOnly": 0,
        "objectType": "",
        "objectId": "",
        "isArchived": False,
        "unreadMessages": 2,
        "lastActivity": 1755180042,
        "lastMessage": secret_last_message(),
    }


def mock_talk(mock: respx.MockRouter, rooms: list[dict[str, Any]]) -> None:
    mock.get(CAPABILITIES_URL).mock(
        return_value=httpx.Response(200, json=envelope({"capabilities": {"spreed": SPREED}}))
    )
    mock.get(ROOM_URL).mock(return_value=httpx.Response(200, json=envelope(rooms)))


# --- the flight belongs to the bundle (Merker (c), Pattern 6) -------------------------------


@pytest.mark.anyio
async def test_a_talk_leg_that_runs_out_of_budget_does_not_cancel_the_flight(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The REPORT is slower than the Talk budget; it still goes out exactly once.

    The providers list is delayed on purpose, so the Talk leg reaches the guard before the
    search does: without a flight holder of its own the Talk leg would start the flight and
    cancel it at its ceiling, and the search would have to ask a second time.

    The REPORTs are counted when they start: respx records a call only once its side effect
    returned, so a REPORT cancelled in flight would not show up in ``call_count``.
    """
    monkeypatch.setattr(context_tools, "TALK_BUDGET", 0.05)
    body = guard_routes.report_207((SECRET_PATH, "901", False))
    started: list[str] = []

    async def slow_report(request: httpx.Request) -> httpx.Response:
        started.append(str(request.url))
        await asyncio.sleep(0.2)
        return guard_routes.listed(body)

    async def late_providers(_request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(0.02)
        return providers("files")

    with respx.mock(assert_all_called=False) as mock:
        listing = mock.route(method="PROPFIND", url=guard_routes.TAGS).mock(
            return_value=guard_routes.listed(
                guard_routes.tag_list(guard_routes.KEIN_KI, guard_routes.OTHER_TAG)
            )
        )
        report = mock.route(method="REPORT", url=guard_routes.HOME).mock(side_effect=slow_report)
        mock.get(PROVIDERS_URL).mock(side_effect=late_providers)
        mock.get(search_url("files")).mock(
            return_value=answer(
                [files_entry("901", SECRET_PATH), files_entry("903", "Docs/offen.txt")]
            )
        )
        mock_talk(mock, [waiting_room()])

        result = await context_tools.prepare_context(fresh(), "docs")

    assert len(started) == 1, "one REPORT started, none cancelled and asked again"
    assert report.call_count == 1
    assert listing.call_count == 1
    assert [hit["id"] for hit in result["results"]["file"]] == ["file:903"]
    assert result["talk"] == []
    assert result["degraded"] == [
        {"source": "talk", "reason": "The talk did not answer within 0.05 seconds."}
    ]
    assert SECRET_NAME not in json.dumps(result, ensure_ascii=False)


# --- one entry for "could not check" (D-27-03, D-27-05) -----------------------------------


@pytest.mark.anyio
async def test_unverifiable_is_one_degraded_entry_however_many_legs_report_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def stalled(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        raise TimeoutError

    monkeypatch.setattr(calendar_tools, "list_events", stalled)
    with respx.mock(assert_all_called=False) as mock:
        _, report = guard_routes.unverifiable(mock)
        mock.get(PROVIDERS_URL).mock(return_value=providers("files", "findling"))
        mock.get(search_url("files")).mock(return_value=answer([files_entry("901", SECRET_PATH)]))
        mock.get(search_url("findling")).mock(return_value=answer([findling_entry("903")]))
        mock_talk(mock, [waiting_room()])

        result = await context_tools.prepare_context(fresh(), "docs")

    assert report.call_count == 1
    unavailable = [
        entry
        for entry in result["degraded"]
        if entry["reason"] == withhold.EXCLUSION_UNAVAILABLE
    ]
    assert unavailable == [EXCLUSION]
    assert result["degraded"] == [
        EXCLUSION,
        {"source": "calendar", "reason": "The calendar did not answer within 10 seconds."},
    ]
    assert result["results"]["file"] == []
    dumped = json.dumps(result, ensure_ascii=False)
    assert SECRET_NAME not in dumped
    assert "901" not in dumped


def test_one_exclusion_entry_keeps_the_rest_in_order() -> None:
    degraded = [
        {"source": "calendar", "reason": "The calendar did not answer within 10 seconds."},
        {"provider": "exclusion", "reason": withhold.EXCLUSION_UNAVAILABLE},
        {"source": "file", "reason": "Only the first 5 of 7 hits are listed."},
        {"source": "exclusion", "reason": withhold.EXCLUSION_UNAVAILABLE},
        {"source": "file:903", "reason": withhold.EXCLUSION_UNAVAILABLE},
        {"source": "mail", "reason": "The mail could not be reached."},
    ]

    assert context_tools._one_exclusion_entry(degraded) == [
        degraded[0],
        EXCLUSION,
        degraded[2],
        degraded[5],
    ]
    assert context_tools._one_exclusion_entry(degraded[:1]) == degraded[:1]
    assert context_tools._one_exclusion_entry([]) == []


# --- untagged stays exactly as it was -------------------------------------------------------


@pytest.mark.anyio
async def test_untagged_answers_exactly_as_without_the_guard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def bundle() -> tuple[dict[str, Any], int]:
        with respx.mock(assert_all_called=False) as mock:
            guard_routes.untagged(mock)
            report = mock.route(method="REPORT", url=guard_routes.HOME)
            mock.get(PROVIDERS_URL).mock(return_value=providers("files", "findling"))
            mock.get(search_url("files")).mock(
                return_value=answer([files_entry("901", SECRET_PATH)])
            )
            mock.get(search_url("findling")).mock(return_value=answer([findling_entry("903")]))
            mock_talk(mock, [waiting_room()])
            result = await context_tools.prepare_context(fresh(), "docs")
        return result, report.call_count

    wired, reports = await bundle()
    assert reports == 0
    guard_routes.patch_untagged(monkeypatch)
    capabilities.clear_cache()
    before, _ = await bundle()

    assert json.dumps(wired, sort_keys=True) == json.dumps(before, sort_keys=True)
    assert wired["talk"][0]["last_message"] == "Siehe geheim.txt"
    assert "degraded" not in wired
