"""unified_search against the real guard: sandbox for pathless hits, silent tag filter, degraded.

No ``patch_untagged`` here: every test mocks the real guard requests for one of the three
states through ``guard_routes``, and a fresh ``NcClients`` per call, so the wiring is proven
against the guard the tool actually asks.

The entry shapes are the real ones: a Findling hit carries ``attributes.fileId`` and the
``/index.php/f/<id>`` route (``nextcloud-search/php/lib/Search/Provider.php``), a comments hit
carries its file id only in ``resourceUrl`` ``/f/<id>`` and ``attributes`` as an empty list,
and a talk-message hit carries conversation and message id
(``raw/27-03-provider-probe.txt``, measured on nc35).
"""

import asyncio
import json
from typing import Any

import guard_routes
import httpx
import pytest
import respx

from mcp_connector import config
from mcp_connector.nextcloud import NcClients
from mcp_connector.nextcloud.clients import xml as davxml
from mcp_connector.nextcloud.credentials import Credentials
from mcp_connector.tools import search as search_tools
from mcp_connector.tools import withhold

BASE = guard_routes.BASE
USER = guard_routes.USER
PROVIDERS_URL = f"{BASE}/ocs/v2.php/search/providers"
DAV_SEARCH = f"{BASE}/remote.php/dav/"
EXCLUSION = {"provider": "exclusion", "reason": withhold.EXCLUSION_UNAVAILABLE}


@pytest.fixture(autouse=True)
def _fresh_tag_cache() -> None:
    guard_routes.reset()


def fresh() -> NcClients:
    """One NcClients per tool call, so every call has its own guard (Pattern 7)."""
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


def answer(entries: list[Any], cursor: Any = None) -> httpx.Response:
    return httpx.Response(
        200,
        json=envelope(
            {"name": "x", "isPaginated": cursor is not None, "entries": entries, "cursor": cursor}
        ),
    )


def search_url(provider_id: str) -> str:
    return f"{PROVIDERS_URL}/{provider_id}/search"


def dav_answer(*entries: tuple[str, str]) -> httpx.Response:
    """A 207 SEARCH answer of paths_of_fileids; each entry is (suffix below the home, fileid)."""
    responses = "".join(
        f"<d:response><d:href>/remote.php/dav/files/{USER}/{suffix}</d:href><d:propstat>"
        f"<d:prop><oc:fileid>{fileid}</oc:fileid><d:resourcetype/></d:prop>"
        "<d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response>"
        for suffix, fileid in entries
    )
    body = (
        '<?xml version="1.0" encoding="utf-8"?>'
        f'<d:multistatus xmlns:d="DAV:" xmlns:oc="{davxml.OC}">{responses}</d:multistatus>'
    ).encode()
    return guard_routes.listed(body)


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
    """The shape of Provider.php toEntries: fileId attribute, relative showFile route."""
    return {
        "thumbnailUrl": "",
        "title": title,
        "subline": "... die Kuendigungsfrist betraegt drei Monate ...",
        "resourceUrl": f"/index.php/f/{fileid}",
        "icon": "icon-search",
        "rounded": False,
        "attributes": {"fileId": fileid},
    }


def notes_entry(note_id: str) -> dict[str, Any]:
    return {
        "title": "Protokoll",
        "subline": "Anwesend: Anja",
        "resourceUrl": f"{BASE}/index.php/apps/notes/note/{note_id}",
        "attributes": [],
    }


def comments_entry(fileid: str, path: str) -> dict[str, Any]:
    """The shape measured on nc35: file id only in ``/f/<id>``, attributes an empty list."""
    return {
        "thumbnailUrl": f"{BASE}/avatar/alice/42",
        "title": "alice",
        "subline": f"/alice/files/{path}",
        "resourceUrl": f"/f/{fileid}",
        "icon": "",
        "rounded": True,
        "attributes": [],
    }


def talk_message_entry() -> dict[str, Any]:
    """The shape measured on nc35 for a plain text message."""
    return {
        "thumbnailUrl": f"{BASE}/avatar/alice/512",
        "title": "alice in MCP-Talk",
        "subline": "Textvergleich probewort",
        "resourceUrl": f"{BASE}/call/2uqkjpn2#message_49",
        "icon": "icon-talk",
        "rounded": True,
        "attributes": {
            "conversation": "2uqkjpn2",
            "messageId": "49",
            "actorType": "users",
            "actorId": "alice",
            "timestamp": "1790504091",
        },
    }


CALENDAR_ENTRY = {
    "title": "Budgetrunde",
    "subline": "Morgen 10:00",
    "resourceUrl": f"{BASE}/index.php/apps/calendar/dayGridMonth/2026-09-28",
    "attributes": [],
}
CARD_ENTRY = {
    "title": "Übergabe",
    "subline": "Board Projekt",
    "resourceUrl": f"{BASE}/index.php/apps/deck/card/57",
    "attributes": [],
}
TAG_ENTRY = {
    "title": "All tagged kein-ki ...",
    "subline": "",
    "resourceUrl": f"{BASE}/index.php/apps/files/tags?dir=/64",
    "attributes": [],
}
BROKEN = {"title": "kaputt", "subline": "", "attributes": []}


def ids_of(result: dict[str, Any]) -> list[str]:
    return [hit["id"] for hit in result["results"]]


# --- sandbox parity for pathless hits (SBX-01, SBX-02) -------------------------------------


@pytest.mark.anyio
async def test_a_findling_hit_with_only_a_fileid_outside_the_sandbox_is_skipped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(config.ENV_FILES_ROOT, "/rtc/mth/knsk")
    with respx.mock(assert_all_called=True) as mock:
        guard_routes.untagged(mock)
        mock.get(PROVIDERS_URL).mock(return_value=providers("findling"))
        mock.get(search_url("findling")).mock(return_value=answer([findling_entry("5002")]))
        lookup = mock.route(method="SEARCH", url=DAV_SEARCH).mock(return_value=dav_answer())

        result = await search_tools.unified_search(fresh(), query="vertrag")

    assert result["results"] == []
    assert result["skipped"] == 1
    assert lookup.call_count == 1
    assert "degraded" not in result


@pytest.mark.anyio
async def test_a_findling_hit_that_resolves_inside_the_sandbox_is_kept(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(config.ENV_FILES_ROOT, "/rtc/mth/knsk")
    with respx.mock(assert_all_called=True) as mock:
        guard_routes.untagged(mock)
        mock.get(PROVIDERS_URL).mock(return_value=providers("findling"))
        mock.get(search_url("findling")).mock(return_value=answer([findling_entry("5002")]))
        mock.route(method="SEARCH", url=DAV_SEARCH).mock(
            return_value=dav_answer(("rtc/mth/knsk/Vertrag.pdf", "5002"))
        )

        result = await search_tools.unified_search(fresh(), query="vertrag")

    assert len(result["results"]) == 1
    assert result["results"][0]["provider"] == "findling"
    assert "skipped" not in result


@pytest.mark.anyio
async def test_notes_outside_and_comments_inside_the_sandbox_with_one_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(config.ENV_FILES_ROOT, "/rtc/mth/knsk")
    with respx.mock(assert_all_called=True) as mock:
        guard_routes.untagged(mock)
        mock.get(PROVIDERS_URL).mock(return_value=providers("notes", "comments"))
        mock.get(search_url("notes")).mock(return_value=answer([notes_entry("933")]))
        mock.get(search_url("comments")).mock(
            return_value=answer([comments_entry("5003", "rtc/mth/knsk/c.txt")])
        )
        lookup = mock.route(method="SEARCH", url=DAV_SEARCH).mock(
            return_value=dav_answer(("rtc/mth/knsk/c.txt", "5003"))
        )

        result = await search_tools.unified_search(fresh(), query="protokoll")

    assert [hit["provider"] for hit in result["results"]] == ["comments"]
    assert result["skipped"] == 1
    assert lookup.call_count == 1, "one lookup for the pathless hits of all providers"


@pytest.mark.anyio
async def test_the_whole_root_untagged_asks_no_lookup_and_answers_as_before(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entries = {
        "files": [files_entry("4711", "Docs/Budget.md"), BROKEN],
        "findling": [findling_entry("9917")],
        "notes": [notes_entry("12")],
        "comments": [comments_entry("5003", "c.txt")],
    }

    async def run() -> dict[str, Any]:
        with respx.mock(assert_all_called=False) as mock:
            listing = guard_routes.untagged(mock)
            report = mock.route(method="REPORT", url=guard_routes.HOME)
            lookup = mock.route(method="SEARCH", url=DAV_SEARCH)
            mock.get(PROVIDERS_URL).mock(return_value=providers(*entries))
            for pid, items in entries.items():
                mock.get(search_url(pid)).mock(return_value=answer(items))
            result = await search_tools.unified_search(fresh(), query="budget")
        assert lookup.call_count == 0
        assert report.call_count == 0
        result["_listing_calls"] = listing.call_count
        return result

    wired = await run()
    assert wired.pop("_listing_calls") == 1
    guard_routes.patch_untagged(monkeypatch)
    before = await run()
    before.pop("_listing_calls")
    assert json.dumps(wired, sort_keys=True) == json.dumps(before, sort_keys=True)


# --- silent tag filter (EXCL-03, D-27-04) --------------------------------------------------


@pytest.mark.anyio
async def test_tag_drops_leave_skipped_and_the_rest_unchanged() -> None:
    """A tagged file vanishes from files and Findling without a trace in any counter."""
    tagged = [files_entry("5001", "Docs/geheim.txt"), findling_entry("5001", "geheim.txt")]
    rest = {
        "files": [files_entry("4711", "Docs/Budget.md"), BROKEN],
        "findling": [findling_entry("9917")],
    }

    with respx.mock(assert_all_called=False) as mock:
        _, report = guard_routes.active(mock, ("Docs/geheim.txt", "5001", False))
        lookup = mock.route(method="SEARCH", url=DAV_SEARCH)
        mock.get(PROVIDERS_URL).mock(return_value=providers("files", "findling"))
        mock.get(search_url("files")).mock(return_value=answer([tagged[0], *rest["files"]]))
        mock.get(search_url("findling")).mock(return_value=answer([tagged[1], *rest["findling"]]))
        filtered = await search_tools.unified_search(fresh(), query="geheim")
    assert report.call_count == 1
    assert lookup.call_count == 0, "no tagged folder and no sandbox: the file id decides"

    guard_routes.reset()
    with respx.mock(assert_all_called=False) as mock:
        guard_routes.untagged(mock)
        mock.get(PROVIDERS_URL).mock(return_value=providers("files", "findling"))
        mock.get(search_url("files")).mock(return_value=answer(rest["files"]))
        mock.get(search_url("findling")).mock(return_value=answer(rest["findling"]))
        without = await search_tools.unified_search(fresh(), query="geheim")

    assert filtered == without
    assert filtered["skipped"] == 1
    dumped = json.dumps(filtered)
    assert "5001" not in dumped
    assert "geheim.txt" not in dumped


@pytest.mark.anyio
async def test_a_tagged_folder_covers_resolved_findling_hits_and_file_paths_silently() -> None:
    with respx.mock(assert_all_called=False) as mock:
        guard_routes.active(mock, ("Projekt", "900", True))
        lookup = mock.route(method="SEARCH", url=DAV_SEARCH).mock(
            return_value=dav_answer(("Projekt/a/b.pdf", "5004"), ("Frei/c.pdf", "5005"))
        )
        mock.get(PROVIDERS_URL).mock(return_value=providers("files", "findling"))
        mock.get(search_url("files")).mock(
            return_value=answer(
                [files_entry("5006", "Projekt/x.txt"), files_entry("4711", "Docs/a.md")]
            )
        )
        mock.get(search_url("findling")).mock(
            return_value=answer([findling_entry("5004"), findling_entry("5005")])
        )

        result = await search_tools.unified_search(fresh(), query="projekt")

    assert lookup.call_count == 1
    # Findling hits are files in the olivia fork (provider_map "findling": "file").
    assert sorted(ids_of(result)) == ["file:4711", "file:5005"]
    assert "skipped" not in result
    assert "degraded" not in result
    assert "Projekt" not in json.dumps(result)


@pytest.mark.anyio
async def test_systemtags_keeps_the_tag_entry_and_drops_the_tagged_file() -> None:
    with respx.mock(assert_all_called=False) as mock:
        guard_routes.active(mock, ("Docs/geheim.txt", "5001", False))
        mock.get(PROVIDERS_URL).mock(return_value=providers("systemtags"))
        mock.get(search_url("systemtags")).mock(
            return_value=answer([TAG_ENTRY, files_entry("5001", "Docs/geheim.txt")])
        )

        result = await search_tools.unified_search(fresh(), query="kein-ki")

    assert [hit["title"] for hit in result["results"]] == ["All tagged kein-ki ..."]
    assert "skipped" not in result


# --- could not check (D-27-03, D-27-05) ----------------------------------------------------


@pytest.mark.anyio
async def test_unverifiable_withholds_every_file_bearing_hit_with_one_degraded_entry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(config.ENV_FILES_ROOT, "/rtc/mth/knsk")
    answers = {
        "files": [files_entry("5001", "rtc/mth/knsk/a.txt")],
        "findling": [findling_entry("5002")],
        "notes": [notes_entry("933")],
        "comments": [comments_entry("5003", "rtc/mth/knsk/c.txt")],
        "systemtags": [TAG_ENTRY, files_entry("5004", "rtc/mth/knsk/d.txt")],
        "calendar": [CALENDAR_ENTRY],
        "search-deck-card-board": [CARD_ENTRY],
        "talk-message": [talk_message_entry()],
    }
    with respx.mock(assert_all_called=False) as mock:
        guard_routes.unverifiable(mock)
        lookup = mock.route(method="SEARCH", url=DAV_SEARCH)
        mock.get(ROOM_URL).mock(return_value=rooms_answer([room("2uqkjpn2", "MCP-Talk")]))
        mock.get(PROVIDERS_URL).mock(return_value=providers(*answers))
        for pid, items in answers.items():
            mock.get(search_url(pid)).mock(return_value=answer(items))

        result = await search_tools.unified_search(fresh(), query="budget")

    assert lookup.call_count == 0
    assert sorted(hit["provider"] for hit in result["results"]) == [
        "calendar",
        "search-deck-card-board",
        "systemtags",
        "talk-message",
    ]
    assert result["degraded"] == [EXCLUSION]
    assert "skipped" not in result
    for fileid in ("5001", "5002", "933", "5003", "5004"):
        assert fileid not in json.dumps(result)


@pytest.mark.anyio
async def test_a_failing_lookup_withholds_pathless_hits_and_keeps_path_hits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(config.ENV_FILES_ROOT, "/rtc/mth/knsk")
    with respx.mock(assert_all_called=True) as mock:
        guard_routes.untagged(mock)
        mock.route(method="SEARCH", url=DAV_SEARCH).mock(return_value=httpx.Response(500))
        mock.get(PROVIDERS_URL).mock(return_value=providers("files", "findling"))
        mock.get(search_url("files")).mock(
            return_value=answer(
                [files_entry("4711", "rtc/mth/knsk/a.md"), files_entry("4712", "Docs/b.md")]
            )
        )
        mock.get(search_url("findling")).mock(return_value=answer([findling_entry("5002")]))

        result = await search_tools.unified_search(fresh(), query="budget")

    assert ids_of(result) == ["file:4711"]
    assert result["skipped"] == 1, "the path hit outside the sandbox still counts"
    assert result["degraded"] == [EXCLUSION]


@pytest.mark.anyio
async def test_talk_message_hits_are_not_file_bearing_per_the_nc35_probe() -> None:
    """KLASSE=kein-leak (raw/27-03-provider-probe.txt): a message in a plain room stays."""
    with respx.mock(assert_all_called=False) as mock:
        guard_routes.active(mock, ("Docs/geheim.txt", "5001", False))
        mock.get(ROOM_URL).mock(return_value=rooms_answer([room("2uqkjpn2", "MCP-Talk")]))
        mock.get(PROVIDERS_URL).mock(return_value=providers("talk-message"))
        mock.get(search_url("talk-message")).mock(return_value=answer([talk_message_entry()]))

        result = await search_tools.unified_search(fresh(), query="probewort")

    assert [hit["provider"] for hit in result["results"]] == ["talk-message"]
    assert "degraded" not in result


# --- talk-conversations against the conversation list (D-28-21) ----------------------------

ROOM_URL = f"{BASE}/ocs/v2.php/apps/spreed/api/v4/room"


def conversation_entry(token: str, title: str) -> dict[str, Any]:
    """A talk-conversations hit: the room name as title and ``/call/<token>`` as link."""
    return {
        "thumbnailUrl": f"{BASE}/ocs/v2.php/apps/spreed/api/v1/room/{token}/avatar",
        "title": title,
        "subline": "",
        "resourceUrl": f"{BASE}/call/{token}",
        "icon": "",
        "rounded": True,
        "attributes": [],
    }


def room(token: str, name: str, fileid: str | None = None) -> dict[str, Any]:
    raw: dict[str, Any] = {"token": token, "displayName": name, "objectType": "", "objectId": ""}
    if fileid is not None:
        raw.update(objectType="file", objectId=fileid)
    return raw


ROOMS = [
    room("tagroom1", "geheim.txt", "5001"),
    room("freeroom", "frei.txt", "4711"),
    room("teamroom", "Team"),
]
CONVERSATION_HITS = [
    conversation_entry("tagroom1", "geheim.txt"),
    conversation_entry("freeroom", "frei.txt"),
    conversation_entry("teamroom", "Team"),
]


def rooms_answer(rooms: list[dict[str, Any]]) -> httpx.Response:
    return httpx.Response(200, json=envelope(rooms))


def call_ids(*tokens: str) -> list[str]:
    return [f"url:{BASE}/call/{token}" for token in tokens]


@pytest.mark.anyio
async def test_a_tagged_file_room_is_dropped_silently_and_the_others_stay() -> None:
    with respx.mock(assert_all_called=False) as mock:
        _, report = guard_routes.active(mock, ("Docs/geheim.txt", "5001", False))
        rooms = mock.get(ROOM_URL).mock(return_value=rooms_answer(ROOMS))
        mock.get(PROVIDERS_URL).mock(return_value=providers("talk-conversations"))
        mock.get(search_url("talk-conversations")).mock(return_value=answer(CONVERSATION_HITS))

        result = await search_tools.unified_search(fresh(), query="txt")

    assert ids_of(result) == call_ids("freeroom", "teamroom")
    assert rooms.call_count == 1
    assert report.call_count == 1, "one guard REPORT for the whole answer"
    assert "degraded" not in result
    assert "skipped" not in result
    dumped = json.dumps(result)
    assert "geheim" not in dumped
    assert "tagroom1" not in dumped


@pytest.mark.anyio
async def test_a_conversation_hit_missing_from_the_list_is_withheld_when_something_is_tagged() -> (
    None
):
    with respx.mock(assert_all_called=False) as mock:
        guard_routes.active(mock, ("Docs/geheim.txt", "5001", False))
        mock.get(ROOM_URL).mock(return_value=rooms_answer([room("teamroom", "Team")]))
        mock.get(PROVIDERS_URL).mock(return_value=providers("talk-conversations"))
        mock.get(search_url("talk-conversations")).mock(
            return_value=answer(
                [conversation_entry("ghostroom", "x.txt"), conversation_entry("teamroom", "Team")]
            )
        )

        result = await search_tools.unified_search(fresh(), query="x")

    assert ids_of(result) == call_ids("teamroom")
    assert "degraded" not in result


@pytest.mark.anyio
async def test_unverifiable_withholds_file_rooms_keeps_plain_rooms_and_says_so_once() -> None:
    with respx.mock(assert_all_called=False) as mock:
        guard_routes.unverifiable(mock)
        mock.get(ROOM_URL).mock(return_value=rooms_answer(ROOMS))
        mock.get(PROVIDERS_URL).mock(return_value=providers("talk-conversations", "files"))
        mock.get(search_url("talk-conversations")).mock(return_value=answer(CONVERSATION_HITS))
        mock.get(search_url("files")).mock(
            return_value=answer([files_entry("4711", "Docs/frei.txt")])
        )

        result = await search_tools.unified_search(fresh(), query="txt")

    assert ids_of(result) == call_ids("teamroom")
    assert result["degraded"] == [EXCLUSION]


@pytest.mark.anyio
async def test_without_conversation_hits_the_room_list_is_never_read() -> None:
    with respx.mock(assert_all_called=False) as mock:
        guard_routes.active(mock, ("Docs/geheim.txt", "5001", False))
        rooms = mock.get(ROOM_URL).mock(return_value=rooms_answer(ROOMS))
        mock.get(PROVIDERS_URL).mock(return_value=providers("talk-conversations", "files"))
        mock.get(search_url("talk-conversations")).mock(return_value=answer([]))
        mock.get(search_url("files")).mock(
            return_value=answer([files_entry("4711", "Docs/frei.txt")])
        )

        result = await search_tools.unified_search(fresh(), query="frei")

    assert rooms.call_count == 0
    assert ids_of(result) == ["file:4711"]


@pytest.mark.anyio
async def test_untagged_keeps_every_conversation_hit_without_reading_the_room_list() -> None:
    with respx.mock(assert_all_called=False) as mock:
        guard_routes.untagged(mock)
        rooms = mock.get(ROOM_URL).mock(return_value=rooms_answer(ROOMS))
        mock.get(PROVIDERS_URL).mock(return_value=providers("talk-conversations"))
        mock.get(search_url("talk-conversations")).mock(return_value=answer(CONVERSATION_HITS))

        result = await search_tools.unified_search(fresh(), query="txt")

    assert rooms.call_count == 0
    assert ids_of(result) == call_ids("tagroom1", "freeroom", "teamroom")


@pytest.mark.anyio
async def test_a_failing_room_list_withholds_the_conversation_hits_and_names_the_provider() -> None:
    with respx.mock(assert_all_called=False) as mock:
        guard_routes.active(mock, ("Docs/geheim.txt", "5001", False))
        mock.get(ROOM_URL).mock(return_value=httpx.Response(500))
        mock.get(PROVIDERS_URL).mock(return_value=providers("talk-conversations", "files"))
        mock.get(search_url("talk-conversations")).mock(return_value=answer(CONVERSATION_HITS))
        mock.get(search_url("files")).mock(
            return_value=answer([files_entry("4711", "Docs/frei.txt")])
        )

        result = await search_tools.unified_search(fresh(), query="txt")

    assert ids_of(result) == ["file:4711"]
    assert [entry["provider"] for entry in result["degraded"]] == ["talk-conversations"]
    assert "geheim" not in json.dumps(result)


# --- talk messages written in a file conversation (review CR-01 of phase 28) ---------------


def message_in(token: str, conversation: str, message_id: str) -> dict[str, Any]:
    """A talk-message hit written in ``conversation``: its name is in the title."""
    entry = talk_message_entry()
    entry["title"] = f"bob in {conversation}"
    entry["resourceUrl"] = f"{BASE}/call/{token}#message_{message_id}"
    entry["attributes"] = {**entry["attributes"], "conversation": token, "messageId": message_id}
    return entry


MESSAGE_HITS = [
    message_in("tagroom1", "geheim.txt", "71"),
    message_in("freeroom", "frei.txt", "72"),
    message_in("teamroom", "Team", "73"),
]


@pytest.mark.parametrize("provider_id", ["talk-message", "talk-message-current"])
@pytest.mark.anyio
async def test_a_message_in_a_tagged_file_room_is_dropped_silently(provider_id: str) -> None:
    with respx.mock(assert_all_called=False) as mock:
        _, report = guard_routes.active(mock, ("Docs/geheim.txt", "5001", False))
        rooms = mock.get(ROOM_URL).mock(return_value=rooms_answer(ROOMS))
        mock.get(PROVIDERS_URL).mock(return_value=providers(provider_id))
        mock.get(search_url(provider_id)).mock(return_value=answer(MESSAGE_HITS))

        result = await search_tools.unified_search(fresh(), query="prüfen")

    assert [hit["title"] for hit in result["results"]] == ["bob in frei.txt", "bob in Team"]
    assert rooms.call_count == 1
    assert report.call_count == 1
    assert "degraded" not in result
    assert "skipped" not in result
    dumped = json.dumps(result)
    assert "geheim" not in dumped
    assert "tagroom1" not in dumped


@pytest.mark.anyio
async def test_unverifiable_withholds_messages_of_file_rooms_and_keeps_plain_rooms() -> None:
    with respx.mock(assert_all_called=False) as mock:
        guard_routes.unverifiable(mock)
        mock.get(ROOM_URL).mock(return_value=rooms_answer(ROOMS))
        mock.get(PROVIDERS_URL).mock(return_value=providers("talk-message"))
        mock.get(search_url("talk-message")).mock(return_value=answer(MESSAGE_HITS))

        result = await search_tools.unified_search(fresh(), query="prüfen")

    assert [hit["title"] for hit in result["results"]] == ["bob in Team"]
    assert result["degraded"] == [EXCLUSION]
    assert "geheim" not in json.dumps(result)


@pytest.mark.anyio
async def test_a_failing_room_list_withholds_message_hits_under_their_provider() -> None:
    with respx.mock(assert_all_called=False) as mock:
        guard_routes.active(mock, ("Docs/geheim.txt", "5001", False))
        mock.get(ROOM_URL).mock(return_value=httpx.Response(500))
        mock.get(PROVIDERS_URL).mock(return_value=providers("talk-message", "talk-conversations"))
        mock.get(search_url("talk-message")).mock(return_value=answer(MESSAGE_HITS))
        mock.get(search_url("talk-conversations")).mock(return_value=answer([]))

        result = await search_tools.unified_search(fresh(), query="prüfen")

    assert result["results"] == []
    assert [entry["provider"] for entry in result["degraded"]] == ["talk-message"]
    assert "geheim" not in json.dumps(result)


# --- one flight per call, outside the provider timeout (E3, Merker (c)) --------------------


@pytest.mark.anyio
async def test_the_report_goes_out_exactly_once_per_call() -> None:
    with respx.mock(assert_all_called=False) as mock:
        listing, report = guard_routes.active(mock, ("Docs/geheim.txt", "5001", False))
        mock.get(PROVIDERS_URL).mock(return_value=providers("files", "findling", "comments"))
        mock.get(search_url("files")).mock(
            return_value=answer([files_entry("5001", "Docs/geheim.txt")])
        )
        mock.get(search_url("findling")).mock(return_value=answer([findling_entry("5001")]))
        mock.get(search_url("comments")).mock(
            return_value=answer([comments_entry("5001", "Docs/geheim.txt")])
        )

        result = await search_tools.unified_search(fresh(), query="geheim")

    assert listing.call_count == 1
    assert report.call_count == 1
    assert result["results"] == []


@pytest.mark.anyio
async def test_the_guard_runs_outside_the_provider_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A REPORT slower than one provider budget still answers: the guard is its own member."""
    monkeypatch.setattr(search_tools, "PER_PROVIDER_TIMEOUT", 0.05)
    body = guard_routes.report_207(("Docs/geheim.txt", "5001", False))

    async def slow_report(_request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(0.2)
        return guard_routes.listed(body)

    with respx.mock(assert_all_called=False) as mock:
        mock.route(method="PROPFIND", url=guard_routes.TAGS).mock(
            return_value=guard_routes.listed(
                guard_routes.tag_list(guard_routes.KEIN_KI, guard_routes.OTHER_TAG)
            )
        )
        mock.route(method="REPORT", url=guard_routes.HOME).mock(side_effect=slow_report)
        mock.get(PROVIDERS_URL).mock(return_value=providers("files"))
        mock.get(search_url("files")).mock(
            return_value=answer(
                [files_entry("5001", "Docs/geheim.txt"), files_entry("4711", "Docs/a.md")]
            )
        )

        result = await search_tools.unified_search(fresh(), query="docs")

    assert ids_of(result) == ["file:4711"]
    assert "degraded" not in result
