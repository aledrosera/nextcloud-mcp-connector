"""``fetch(message:...)`` behind the ``kein-ki`` guard (EXCL-03 message part, D-27-06).

A message is not a file: while the check cannot be answered the message stays readable, its
file placeholders stay raw and ``metadata["degraded"]`` carries the one sentence. A file
conversation of a withheld file answers exactly like a token that never existed. No
``patch_untagged`` here; the real guard requests are mocked and counted.
"""

import json
from typing import Any

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
CAPABILITIES_URL = f"{BASE}/ocs/v2.php/cloud/capabilities"
ROOM_URL = f"{BASE}/ocs/v2.php/apps/spreed/api/v4/room"
CHAT_BASE = f"{BASE}/ocs/v2.php/apps/spreed/api/v1/chat"
TOKEN = "abcd1234"
FILE_TOKEN = "fileroom1"
MESSAGE_ID = 42
SPREED = {"features": ["chat-v2"], "config": {"chat": {"max-length": 32000}}}
SECRET_NAME = "geheim.txt"
SECRET_PATH = "Docs/geheim.txt"


@pytest.fixture(autouse=True)
def _fresh_tag_cache() -> None:
    guard_routes.reset()
    capabilities.clear_cache()


def fresh() -> NcClients:
    return NcClients(
        client=httpx.AsyncClient(follow_redirects=False),
        creds=Credentials(BASE, USER, "app-password-test"),
    )


def envelope(data: Any) -> dict[str, Any]:
    return {"ocs": {"meta": {"status": "ok", "statuscode": 200, "message": "OK"}, "data": data}}


def room(token: str = TOKEN, **overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "token": token,
        "type": 2,
        "displayName": "Baustelle Süd",
        "permissions": 254,
        "readOnly": 0,
        "objectType": "",
        "objectId": "",
        "lastActivity": 1755180000,
    }
    return {**base, **overrides}


def file_room() -> dict[str, Any]:
    return room(FILE_TOKEN, type=3, displayName=SECRET_NAME, objectType="file", objectId="901")


def chat(message_id: int, text: str, parameters: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "id": message_id,
        "actorType": "users",
        "actorId": "bob",
        "actorDisplayName": "Bob Beispiel",
        "timestamp": 1755180000,
        "message": text,
        "messageParameters": parameters or {},
        "messageType": "comment",
    }


def secret_message() -> dict[str, Any]:
    return chat(
        MESSAGE_ID,
        "Siehe {file}",
        {
            "file": {
                "type": "file",
                "id": "901",
                "name": SECRET_NAME,
                "path": SECRET_PATH,
                "link": f"{BASE}/index.php/f/901",
                "mimetype": "text/plain",
            }
        },
    )


def mock_talk(
    mock: respx.MockRouter, rooms: list[dict[str, Any]], window: list[dict[str, Any]], token: str
) -> respx.Route:
    mock.get(CAPABILITIES_URL).mock(
        return_value=httpx.Response(200, json=envelope({"capabilities": {"spreed": SPREED}}))
    )
    mock.get(ROOM_URL).mock(return_value=httpx.Response(200, json=envelope(rooms)))
    return mock.get(f"{CHAT_BASE}/{token}/{MESSAGE_ID}/context").mock(
        return_value=httpx.Response(200, json=envelope(window))
    )


def refusal(error: BaseException) -> tuple[Any, ...]:
    return (
        type(error),
        getattr(error, "message", None),
        getattr(error, "hint", None),
        getattr(error, "reason", None),
    )


@pytest.mark.anyio
async def test_a_tagged_file_keeps_its_placeholder_in_fetch() -> None:
    with respx.mock(assert_all_called=False) as mock:
        mock_talk(mock, [room()], [secret_message()], TOKEN)
        _, report = guard_routes.active(mock, ("Docs/geheim.txt", "901", False))
        answer = await chatgpt.fetch(fresh(), f"message:{TOKEN}:{MESSAGE_ID}")

    assert report.call_count == 1
    assert "Siehe {file}" in answer["text"]
    dumped = json.dumps(answer, ensure_ascii=False)
    assert SECRET_NAME not in dumped
    assert SECRET_PATH not in dumped
    assert "degraded" not in answer["metadata"]


@pytest.mark.anyio
async def test_untagged_fetch_resolves_the_file_name_as_before() -> None:
    with respx.mock(assert_all_called=False) as mock:
        mock_talk(mock, [room()], [secret_message()], TOKEN)
        guard_routes.untagged(mock)
        answer = await chatgpt.fetch(fresh(), f"message:{TOKEN}:{MESSAGE_ID}")

    assert "Siehe geheim.txt" in answer["text"]
    assert "degraded" not in answer["metadata"]


@pytest.mark.anyio
async def test_unverifiable_fetch_keeps_the_message_with_raw_placeholders_and_degraded() -> None:
    with respx.mock(assert_all_called=False) as mock:
        mock_talk(mock, [room()], [secret_message()], TOKEN)
        guard_routes.unverifiable(mock)
        answer = await chatgpt.fetch(fresh(), f"message:{TOKEN}:{MESSAGE_ID}")

    assert "Siehe {file}" in answer["text"]
    assert answer["metadata"]["degraded"] == withhold.EXCLUSION_UNAVAILABLE
    assert SECRET_NAME not in json.dumps(answer, ensure_ascii=False)


@pytest.mark.anyio
async def test_a_message_without_a_file_costs_no_guard_request_and_says_nothing() -> None:
    window = [
        chat(MESSAGE_ID + 1, "Neuer", secret_message()["messageParameters"]),
        chat(MESSAGE_ID, "Nur Text"),
    ]
    with respx.mock(assert_all_called=False) as mock:
        mock_talk(mock, [room()], window, TOKEN)
        listing, report = guard_routes.unverifiable(mock)
        answer = await chatgpt.fetch(fresh(), f"message:{TOKEN}:{MESSAGE_ID}")

    assert listing.call_count == 0, "a file beside the wanted message is not asked about"
    assert report.call_count == 0
    assert "Nur Text" in answer["text"]
    assert "degraded" not in answer["metadata"]


@pytest.mark.anyio
async def test_fetch_in_a_tagged_file_conversation_answers_like_an_unknown_token() -> None:
    with respx.mock(assert_all_called=False) as mock:
        context = mock_talk(mock, [file_room(), room()], [chat(MESSAGE_ID, "Hi")], FILE_TOKEN)
        guard_routes.active(mock, ("Docs/geheim.txt", "901", False))
        with pytest.raises(ToolError) as tagged:
            await chatgpt.fetch(fresh(), f"message:{FILE_TOKEN}:{MESSAGE_ID}")
    assert context.call_count == 0

    guard_routes.reset()
    with respx.mock(assert_all_called=False) as mock:
        mock_talk(mock, [room()], [chat(MESSAGE_ID, "Hi")], FILE_TOKEN)
        with pytest.raises(ToolError) as unknown:
            await chatgpt.fetch(fresh(), f"message:{FILE_TOKEN}:{MESSAGE_ID}")

    assert refusal(tagged.value) == refusal(unknown.value)


@pytest.mark.anyio
async def test_one_report_per_fetch_although_room_and_message_both_ask() -> None:
    window = [{**secret_message(), "token": FILE_TOKEN}]
    with respx.mock(assert_all_called=False) as mock:
        mock_talk(mock, [file_room(), room()], window, FILE_TOKEN)
        listing, report = guard_routes.active(mock, ("Docs/anderes.txt", "999", False))
        answer = await chatgpt.fetch(fresh(), f"message:{FILE_TOKEN}:{MESSAGE_ID}")

    assert listing.call_count == 1
    assert report.call_count == 1
    assert "Siehe geheim.txt" in answer["text"]
