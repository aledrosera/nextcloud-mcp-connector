"""The Talk family behind the ``kein-ki`` guard (EXCL-06, D-27-06), in all three states.

No ``patch_untagged`` here: every test mocks the real guard requests through
``guard_routes`` and counts them, because the cheap path (a window without a file costs no
guard request at all, pitfall 8) is part of the contract and not an optimisation.

The one rule of this family: a placeholder of a withheld file stays in the text exactly as
it came, ``{file}``, the same way an unknown placeholder does. The message itself stays, and
neither the name nor the path of the file leaves the answer on any other way.
"""

import json
from typing import Any

import guard_routes
import httpx
import pytest
import respx

from mcp_connector.errors import ToolError
from mcp_connector.nextcloud import NcClients, capabilities
from mcp_connector.nextcloud.clients import xml as davxml
from mcp_connector.nextcloud.credentials import Credentials
from mcp_connector.tools import talk as talk_tools
from mcp_connector.tools import withhold

BASE = guard_routes.BASE
USER = guard_routes.USER
CAPABILITIES_URL = f"{BASE}/ocs/v2.php/cloud/capabilities"
ROOM_URL = f"{BASE}/ocs/v2.php/apps/spreed/api/v4/room"
CHAT_BASE = f"{BASE}/ocs/v2.php/apps/spreed/api/v1/chat"
TOKEN = "abcd1234"
CHAT_URL = f"{CHAT_BASE}/{TOKEN}"
DAV_SEARCH = f"{BASE}/remote.php/dav/"
DEGRADED = [{"source": "exclusion", "reason": withhold.EXCLUSION_UNAVAILABLE}]

SPREED = {"features": ["chat-v2"], "config": {"chat": {"max-length": 32000}}}

SECRET_NAME = "geheim.txt"
SECRET_PATH = "Docs/geheim.txt"


@pytest.fixture(autouse=True)
def _fresh_tag_cache() -> None:
    guard_routes.reset()
    capabilities.clear_cache()


def fresh() -> NcClients:
    """One NcClients per tool call, so every call has its own guard."""
    return NcClients(
        client=httpx.AsyncClient(follow_redirects=False),
        creds=Credentials(BASE, USER, "app-password-test"),
    )


def envelope(data: Any) -> dict[str, Any]:
    return {"ocs": {"meta": {"status": "ok", "statuscode": 200, "message": "OK"}, "data": data}}


def file_param(fileid: str, name: str, path: str | None) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "type": "file",
        "id": fileid,
        "name": name,
        "link": f"{BASE}/index.php/f/{fileid}",
        "mimetype": "text/plain",
    }
    if path is not None:
        entry["path"] = path
    return entry


def chat(message_id: int, text: str, parameters: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "id": message_id,
        "token": TOKEN,
        "actorType": "users",
        "actorId": "bob",
        "actorDisplayName": "Bob Beispiel",
        "timestamp": 1755180000 + message_id,
        "message": text,
        "messageParameters": parameters or {},
        "messageType": "comment",
    }


def secret_message(message_id: int = 42) -> dict[str, Any]:
    return chat(
        message_id,
        "Siehe {file}",
        {"file": file_param("901", SECRET_NAME, SECRET_PATH)},
    )


def room(token: str = TOKEN, **overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "token": token,
        "type": 2,
        "displayName": "Baustelle Süd",
        "permissions": 254,
        "readOnly": 0,
        "objectType": "",
        "objectId": "",
        "isArchived": False,
        "unreadMessages": 0,
        "lastActivity": 1755180000,
    }
    return {**base, **overrides}


def mock_talk(
    mock: respx.MockRouter, rooms: list[dict[str, Any]], messages: list[dict[str, Any]] | None
) -> None:
    mock.get(CAPABILITIES_URL).mock(
        return_value=httpx.Response(200, json=envelope({"capabilities": {"spreed": SPREED}}))
    )
    mock.get(ROOM_URL).mock(return_value=httpx.Response(200, json=envelope(rooms)))
    if messages is not None:
        mock.get(CHAT_URL).mock(return_value=httpx.Response(200, json=envelope(messages)))


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


# --- messages level ---------------------------------------------------------------------


@pytest.mark.anyio
async def test_a_window_without_a_file_costs_no_guard_request() -> None:
    messages = [chat(42, "{actor} war da", {"actor": {"type": "user", "id": "bob", "name": "Bob"}})]
    with respx.mock(assert_all_called=False) as mock:
        mock_talk(mock, [room()], messages)
        listing, report = guard_routes.active(mock, ("Docs/geheim.txt", "901", False))
        answer = await talk_tools.browse(fresh(), level="messages", token=TOKEN)

    assert listing.call_count == 0
    assert report.call_count == 0
    assert answer["results"][0]["message"] == "Bob war da"
    assert "degraded" not in answer


@pytest.mark.anyio
async def test_untagged_resolves_the_file_name_as_before() -> None:
    with respx.mock(assert_all_called=False) as mock:
        mock_talk(mock, [room()], [secret_message()])
        listing = guard_routes.untagged(mock)
        answer = await talk_tools.browse(fresh(), level="messages", token=TOKEN)

    assert listing.call_count == 1
    assert answer["results"][0]["message"] == "Siehe geheim.txt"
    assert "degraded" not in answer


@pytest.mark.anyio
async def test_a_tagged_file_keeps_its_placeholder_and_the_other_one_is_resolved() -> None:
    message = chat(
        42,
        "Siehe {file} und {file2}",
        {
            "file": file_param("901", SECRET_NAME, SECRET_PATH),
            "file2": file_param("902", "offen.txt", "Docs/offen.txt"),
        },
    )
    with respx.mock(assert_all_called=False) as mock:
        mock_talk(mock, [room()], [message])
        _, report = guard_routes.active(mock, ("Docs/geheim.txt", "901", False))
        answer = await talk_tools.browse(fresh(), level="messages", token=TOKEN)

    assert report.call_count == 1
    assert answer["results"][0]["message"] == "Siehe {file} und offen.txt"
    assert "degraded" not in answer


@pytest.mark.anyio
async def test_json_dumps_of_the_answer_carries_neither_the_name_nor_the_path() -> None:
    with respx.mock(assert_all_called=False) as mock:
        mock_talk(mock, [room()], [secret_message()])
        guard_routes.active(mock, ("Docs/geheim.txt", "901", False))
        answer = await talk_tools.browse(fresh(), level="messages", token=TOKEN)

    dumped = json.dumps(answer, ensure_ascii=False)
    assert answer["results"][0]["message"] == "Siehe {file}"
    assert SECRET_NAME not in dumped
    assert SECRET_PATH not in dumped


@pytest.mark.anyio
async def test_a_path_below_a_tagged_folder_stays_raw() -> None:
    message = chat(42, "Siehe {file}", {"file": file_param("906", "b.pdf", "Projekt/a/b.pdf")})
    with respx.mock(assert_all_called=False) as mock:
        mock_talk(mock, [room()], [message])
        guard_routes.active(mock, ("Projekt", "900", True))
        lookup = mock.route(method="SEARCH", url=DAV_SEARCH)
        answer = await talk_tools.browse(fresh(), level="messages", token=TOKEN)

    assert answer["results"][0]["message"] == "Siehe {file}"
    assert lookup.call_count == 0, "a parameter with a path needs no lookup"


@pytest.mark.anyio
async def test_a_pathless_file_resolved_below_a_tagged_folder_stays_raw() -> None:
    message = chat(42, "Siehe {file}", {"file": file_param("905", "c.pdf", None)})
    with respx.mock(assert_all_called=False) as mock:
        mock_talk(mock, [room()], [message])
        guard_routes.active(mock, ("Projekt", "900", True))
        lookup = mock.route(method="SEARCH", url=DAV_SEARCH).mock(
            return_value=dav_answer(("Projekt/a/c.pdf", "905"))
        )
        answer = await talk_tools.browse(fresh(), level="messages", token=TOKEN)

    assert lookup.call_count == 1
    assert answer["results"][0]["message"] == "Siehe {file}"


@pytest.mark.anyio
async def test_a_pathless_file_that_does_not_resolve_stays_raw() -> None:
    """Fail-closed: an id the lookup does not find cannot be shown to lie outside the folder."""
    message = chat(42, "Siehe {file}", {"file": file_param("905", "c.pdf", None)})
    with respx.mock(assert_all_called=False) as mock:
        mock_talk(mock, [room()], [message])
        guard_routes.active(mock, ("Projekt", "900", True))
        mock.route(method="SEARCH", url=DAV_SEARCH).mock(return_value=dav_answer())
        answer = await talk_tools.browse(fresh(), level="messages", token=TOKEN)

    assert answer["results"][0]["message"] == "Siehe {file}"


@pytest.mark.anyio
async def test_a_pathless_file_resolved_outside_the_tagged_folder_is_resolved() -> None:
    message = chat(42, "Siehe {file}", {"file": file_param("905", "c.pdf", None)})
    with respx.mock(assert_all_called=False) as mock:
        mock_talk(mock, [room()], [message])
        guard_routes.active(mock, ("Projekt", "900", True))
        mock.route(method="SEARCH", url=DAV_SEARCH).mock(
            return_value=dav_answer(("Anderes/c.pdf", "905"))
        )
        answer = await talk_tools.browse(fresh(), level="messages", token=TOKEN)

    assert answer["results"][0]["message"] == "Siehe c.pdf"


@pytest.mark.anyio
async def test_a_guest_path_equal_to_the_name_is_resolved_by_its_id_below_a_folder() -> None:
    """Guests get path = name; that is no home path and must not pass a tagged folder."""
    message = chat(42, "Siehe {file}", {"file": file_param("905", "c.pdf", "c.pdf")})
    with respx.mock(assert_all_called=False) as mock:
        mock_talk(mock, [room()], [message])
        guard_routes.active(mock, ("Projekt", "900", True))
        lookup = mock.route(method="SEARCH", url=DAV_SEARCH).mock(
            return_value=dav_answer(("Projekt/c.pdf", "905"))
        )
        answer = await talk_tools.browse(fresh(), level="messages", token=TOKEN)

    assert lookup.call_count == 1
    assert answer["results"][0]["message"] == "Siehe {file}"


@pytest.mark.anyio
async def test_only_tagged_files_decide_by_id_without_a_lookup() -> None:
    message = chat(42, "Siehe {file}", {"file": file_param("901", SECRET_NAME, None)})
    with respx.mock(assert_all_called=False) as mock:
        mock_talk(mock, [room()], [message])
        guard_routes.active(mock, ("Docs/geheim.txt", "901", False))
        lookup = mock.route(method="SEARCH", url=DAV_SEARCH)
        answer = await talk_tools.browse(fresh(), level="messages", token=TOKEN)

    assert lookup.call_count == 0
    assert answer["results"][0]["message"] == "Siehe {file}"


@pytest.mark.anyio
async def test_a_failing_lookup_keeps_every_file_placeholder_raw_with_degraded() -> None:
    message = chat(
        42,
        "{file} und {file2}",
        {
            "file": file_param("905", "c.pdf", None),
            "file2": file_param("907", "d.pdf", "Anderes/d.pdf"),
        },
    )
    with respx.mock(assert_all_called=False) as mock:
        mock_talk(mock, [room()], [message])
        guard_routes.active(mock, ("Projekt", "900", True))
        mock.route(method="SEARCH", url=DAV_SEARCH).mock(return_value=httpx.Response(500))
        answer = await talk_tools.browse(fresh(), level="messages", token=TOKEN)

    assert answer["results"][0]["message"] == "{file} und {file2}"
    assert answer["degraded"] == DEGRADED


@pytest.mark.anyio
async def test_unverifiable_keeps_every_file_placeholder_raw_with_one_degraded_entry() -> None:
    messages = [
        secret_message(43),
        chat(42, "Und {file}", {"file": file_param("902", "offen.txt", "Docs/offen.txt")}),
        chat(41, "{actor} war da", {"actor": {"type": "user", "id": "bob", "name": "Bob"}}),
    ]
    with respx.mock(assert_all_called=False) as mock:
        mock_talk(mock, [room()], messages)
        guard_routes.unverifiable(mock)
        answer = await talk_tools.browse(fresh(), level="messages", token=TOKEN)

    texts = [entry["message"] for entry in answer["results"]]
    assert texts == ["Siehe {file}", "Und {file}", "Bob war da"]
    assert answer["degraded"] == DEGRADED
    dumped = json.dumps(answer, ensure_ascii=False)
    assert SECRET_NAME not in dumped
    assert "offen.txt" not in dumped


@pytest.mark.anyio
async def test_unverifiable_without_a_file_in_the_window_says_nothing() -> None:
    messages = [chat(41, "Nur Text")]
    with respx.mock(assert_all_called=False) as mock:
        mock_talk(mock, [room()], messages)
        listing, report = guard_routes.unverifiable(mock)
        answer = await talk_tools.browse(fresh(), level="messages", token=TOKEN)

    assert listing.call_count == 0
    assert report.call_count == 0
    assert "degraded" not in answer


@pytest.mark.anyio
async def test_one_report_per_browse_however_many_file_parameters() -> None:
    messages = [
        chat(
            50 + n,
            "Siehe {file}",
            {"file": file_param(str(910 + n), f"f{n}.txt", f"Docs/f{n}.txt")},
        )
        for n in range(10)
    ]
    with respx.mock(assert_all_called=False) as mock:
        mock_talk(mock, [room()], messages)
        listing, report = guard_routes.active(mock, ("Docs/f3.txt", "913", False))
        answer = await talk_tools.browse(fresh(), level="messages", token=TOKEN)

    assert listing.call_count == 1
    assert report.call_count == 1
    assert answer["results"][3]["message"] == "Siehe {file}"
    assert answer["results"][2]["message"] == "Siehe f2.txt"


@pytest.mark.anyio
async def test_mentions_and_the_actor_stay_unchanged_beside_a_tagged_file() -> None:
    message = chat(
        42,
        "{actor} schickt {mention-user1} {file}",
        {
            "actor": {"type": "user", "id": "bob", "name": "Bob"},
            "mention-user1": {"type": "user", "id": "carla", "name": "Carla", "mention-id": "c"},
            "file": file_param("901", SECRET_NAME, SECRET_PATH),
        },
    )
    with respx.mock(assert_all_called=False) as mock:
        mock_talk(mock, [room()], [message])
        guard_routes.active(mock, ("Docs/geheim.txt", "901", False))
        answer = await talk_tools.browse(fresh(), level="messages", token=TOKEN)

    assert answer["results"][0]["message"] == "Bob schickt @Carla {file}"


# --- conversations level ------------------------------------------------------------------


def last(message: dict[str, Any]) -> dict[str, Any]:
    return {**message, "messageType": "object_shared"}


@pytest.mark.anyio
async def test_the_last_message_of_a_conversation_keeps_a_tagged_placeholder_raw() -> None:
    rooms = [
        room(TOKEN, lastMessage=last(secret_message())),
        room("efgh5678", lastMessage=chat(7, "Nur Text"), lastActivity=1755170000),
    ]
    with respx.mock(assert_all_called=False) as mock:
        mock_talk(mock, rooms, None)
        _, report = guard_routes.active(mock, ("Docs/geheim.txt", "901", False))
        answer = await talk_tools.browse(fresh())

    assert report.call_count == 1
    assert answer["results"][0]["last_message"] == "Siehe {file}"
    assert answer["results"][1]["last_message"] == "Nur Text"
    dumped = json.dumps(answer, ensure_ascii=False)
    assert SECRET_NAME not in dumped
    assert SECRET_PATH not in dumped
    assert "degraded" not in answer


@pytest.mark.anyio
async def test_a_conversation_list_without_file_parameters_costs_no_guard_request() -> None:
    rooms = [room(TOKEN, lastMessage=chat(7, "Nur Text"))]
    with respx.mock(assert_all_called=False) as mock:
        mock_talk(mock, rooms, None)
        listing, report = guard_routes.unverifiable(mock)
        answer = await talk_tools.browse(fresh())

    assert listing.call_count == 0
    assert report.call_count == 0
    assert "degraded" not in answer


@pytest.mark.anyio
async def test_unverifiable_conversation_list_with_a_file_carries_one_degraded_entry() -> None:
    rooms = [
        room(TOKEN, lastMessage=last(secret_message())),
        room("efgh5678", lastMessage=last(secret_message(43)), lastActivity=1755170000),
    ]
    with respx.mock(assert_all_called=False) as mock:
        mock_talk(mock, rooms, None)
        guard_routes.unverifiable(mock)
        answer = await talk_tools.browse(fresh())

    assert [entry["last_message"] for entry in answer["results"]] == ["Siehe {file}"] * 2
    assert answer["degraded"] == DEGRADED
    assert SECRET_NAME not in json.dumps(answer, ensure_ascii=False)


def test_one_message_takes_the_screen_as_a_keyword_without_default() -> None:
    window = [secret_message()]
    entry = talk_tools.one_message(window, "42", screen=talk_tools.NO_SCREEN)
    assert entry is not None
    assert entry["message"] == "Siehe geheim.txt"
    with pytest.raises(TypeError):
        talk_tools.one_message(window, "42")  # type: ignore[call-arg]


# --- file conversations (objectType "file", raw/27-05-file-conversation-probe.txt) --------

FILE_TOKEN = "fileroom1"


def file_room(fileid: str = "901", name: str = SECRET_NAME) -> dict[str, Any]:
    """A file conversation as nc35 lists it: objectId is the file id, the name is the file."""
    return room(
        FILE_TOKEN,
        type=3,
        displayName=name,
        objectType="file",
        objectId=fileid,
        lastActivity=1755190000,
    )


def refusal(error: BaseException) -> tuple[Any, ...]:
    return (
        type(error),
        getattr(error, "message", None),
        getattr(error, "hint", None),
        getattr(error, "reason", None),
    )


@pytest.mark.anyio
async def test_a_tagged_file_conversation_is_missing_from_the_list_and_the_count() -> None:
    rooms = [
        file_room(),
        room(TOKEN, lastMessage=chat(7, "Nur Text")),
        room("efgh5678", lastMessage=chat(8, "Auch Text"), lastActivity=1755170000),
    ]
    with respx.mock(assert_all_called=False) as mock:
        mock_talk(mock, rooms, None)
        _, report = guard_routes.active(mock, ("Docs/geheim.txt", "901", False))
        answer = await talk_tools.browse(fresh(), limit=1)

    assert report.call_count == 1
    assert [entry["token"] for entry in answer["results"]] == [TOKEN]
    assert answer["truncated"] is True
    assert answer["total"] == 2
    assert SECRET_NAME not in json.dumps(answer, ensure_ascii=False)
    assert "degraded" not in answer


@pytest.mark.anyio
async def test_an_untagged_file_conversation_is_listed_as_before() -> None:
    rooms = [file_room(), room(TOKEN, lastMessage=chat(7, "Nur Text"))]
    with respx.mock(assert_all_called=False) as mock:
        mock_talk(mock, rooms, None)
        guard_routes.untagged(mock)
        answer = await talk_tools.browse(fresh())

    assert [entry["token"] for entry in answer["results"]] == [FILE_TOKEN, TOKEN]


@pytest.mark.anyio
async def test_a_file_conversation_below_a_tagged_folder_is_missing() -> None:
    rooms = [file_room("905", "c.pdf"), room(TOKEN, lastMessage=chat(7, "Nur Text"))]
    with respx.mock(assert_all_called=False) as mock:
        mock_talk(mock, rooms, None)
        guard_routes.active(mock, ("Projekt", "900", True))
        lookup = mock.route(method="SEARCH", url=DAV_SEARCH).mock(
            return_value=dav_answer(("Projekt/c.pdf", "905"))
        )
        answer = await talk_tools.browse(fresh())

    assert lookup.call_count == 1
    assert [entry["token"] for entry in answer["results"]] == [TOKEN]


@pytest.mark.anyio
async def test_unverifiable_drops_every_file_conversation_with_one_degraded_entry() -> None:
    rooms = [
        file_room(),
        room(TOKEN, lastMessage=last(secret_message())),
    ]
    with respx.mock(assert_all_called=False) as mock:
        mock_talk(mock, rooms, None)
        guard_routes.unverifiable(mock)
        answer = await talk_tools.browse(fresh())

    assert [entry["token"] for entry in answer["results"]] == [TOKEN]
    assert answer["degraded"] == DEGRADED
    assert SECRET_NAME not in json.dumps(answer, ensure_ascii=False)


@pytest.mark.anyio
async def test_the_history_of_a_tagged_file_conversation_answers_like_an_unknown_token() -> None:
    with respx.mock(assert_all_called=False) as mock:
        mock_talk(mock, [file_room(), room()], None)
        guard_routes.active(mock, ("Docs/geheim.txt", "901", False))
        history = mock.get(f"{CHAT_BASE}/{FILE_TOKEN}")
        with pytest.raises(ToolError) as tagged:
            await talk_tools.browse(fresh(), level="messages", token=FILE_TOKEN)
    assert history.call_count == 0

    guard_routes.reset()
    with respx.mock(assert_all_called=False) as mock:
        mock_talk(mock, [room()], None)
        with pytest.raises(ToolError) as unknown:
            await talk_tools.browse(fresh(), level="messages", token=FILE_TOKEN)

    assert refusal(tagged.value) == refusal(unknown.value)


@pytest.mark.anyio
async def test_sending_into_a_tagged_file_conversation_answers_like_an_unknown_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("NC_MCP_TALK_SEND", raising=False)
    with respx.mock(assert_all_called=False) as mock:
        mock_talk(mock, [file_room(), room()], None)
        guard_routes.active(mock, ("Docs/geheim.txt", "901", False))
        post = mock.post(f"{CHAT_BASE}/{FILE_TOKEN}")
        with pytest.raises(ToolError) as tagged:
            await talk_tools.send(fresh(), FILE_TOKEN, "Hallo")
    assert post.call_count == 0

    guard_routes.reset()
    with respx.mock(assert_all_called=False) as mock:
        mock_talk(mock, [room()], None)
        with pytest.raises(ToolError) as unknown:
            await talk_tools.send(fresh(), FILE_TOKEN, "Hallo")

    assert refusal(tagged.value) == refusal(unknown.value)


@pytest.mark.anyio
async def test_unverifiable_refuses_a_file_conversation_but_not_a_normal_one() -> None:
    with respx.mock(assert_all_called=False) as mock:
        mock_talk(mock, [file_room(), room()], None)
        guard_routes.unverifiable(mock)
        with pytest.raises(ToolError) as refused:
            await talk_tools.browse(fresh(), level="messages", token=FILE_TOKEN)
    assert refusal(refused.value) == refusal(withhold.unavailable_error())

    guard_routes.reset()
    with respx.mock(assert_all_called=False) as mock:
        mock_talk(mock, [file_room(), room()], [chat(41, "Nur Text")])
        listing, report = guard_routes.unverifiable(mock)
        answer = await talk_tools.browse(fresh(), level="messages", token=TOKEN)

    assert listing.call_count == 0
    assert report.call_count == 0
    assert answer["results"][0]["message"] == "Nur Text"


@pytest.mark.anyio
async def test_an_untagged_file_conversation_stays_readable() -> None:
    with respx.mock(assert_all_called=False) as mock:
        mock_talk(mock, [file_room(), room()], None)
        mock.get(f"{CHAT_BASE}/{FILE_TOKEN}").mock(
            return_value=httpx.Response(200, json=envelope([chat(41, "Zur Datei")]))
        )
        guard_routes.active(mock, ("Docs/anderes.txt", "999", False))
        answer = await talk_tools.browse(fresh(), level="messages", token=FILE_TOKEN)

    assert answer["conversation"] == SECRET_NAME
    assert answer["results"][0]["message"] == "Zur Datei"
