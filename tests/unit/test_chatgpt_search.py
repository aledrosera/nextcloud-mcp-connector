"""Unit tests for the ChatGPT profile tool ``search``, all paths.

Four of these tests are not about finding anything. They are about the contract: the field
names OpenAI reads, a non-empty url in every single hit (without it ChatGPT renders no
citation at all), an unresolvable hit that stays in the answer instead of disappearing, and
the double encoding of the payload as ``structured_content`` plus ``content``.

The fifth property is negative: this tool must not contain a second search. Every test here
mocks exactly the OCS routes of the unified search, so a hand rolled provider call inside
``chatgpt.search`` would fail with an unmocked request instead of passing quietly.
"""

import json
from pathlib import Path
from typing import Any

import guard_routes
import httpx
import pytest
import respx
from mcp import Client
from mcp.types import TextContent

from mcp_connector.errors import ToolError
from mcp_connector.nextcloud import NcClients
from mcp_connector.nextcloud.credentials import Credentials
from mcp_connector.server import mcp
from mcp_connector.tools import chatgpt

BASE = "http://nc.test"
USER = "alice"
SECRET = "app-password-test"

PROVIDERS_URL = f"{BASE}/ocs/v2.php/search/providers"

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"

NOTE_ENTRY = {
    "title": "Protokoll 2026-08-14",
    "subline": "Anwesend: Anja, Khaled",
    "resourceUrl": f"{BASE}/index.php/apps/notes/note/12",
    "attributes": [],
}
CARD_ENTRY = {
    "title": "Übergabe vorbereiten",
    "subline": "Board Projekt",
    "resourceUrl": f"{BASE}/index.php/apps/deck/card/57",
    "attributes": [],
}
TALK_ENTRY = {
    "title": "Khaled",
    "subline": "Budget passt",
    "resourceUrl": f"{BASE}/index.php/call/abc123#message_42",
    "attributes": [],
}


@pytest.fixture(autouse=True)
def _no_kein_ki_tag(monkeypatch: pytest.MonkeyPatch) -> None:
    """Existing tests assert the behaviour without any kein-ki tag; the guard states are
    tested in the *_exclusion test modules."""
    guard_routes.patch_untagged(monkeypatch)


def fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def envelope(data: Any) -> dict[str, Any]:
    return {"ocs": {"meta": {"status": "ok", "statuscode": 200, "message": "OK"}, "data": data}}


def search_url(provider_id: str) -> str:
    return f"{PROVIDERS_URL}/{provider_id}/search"


def provider_list(*ids: str) -> dict[str, Any]:
    payload = fixture("ocs_providers.json")
    if ids:
        return envelope([item for item in payload["ocs"]["data"] if item["id"] in ids])
    return payload


def hits(name: str, entries: list[dict[str, Any]]) -> dict[str, Any]:
    return envelope({"name": name, "isPaginated": False, "entries": entries, "cursor": None})


@pytest.fixture
def clients() -> NcClients:
    return NcClients(
        client=httpx.AsyncClient(follow_redirects=False),
        creds=Credentials(BASE, USER, SECRET),
    )


@pytest.fixture
def stdio_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """The environment an in-memory client call resolves its credentials from."""
    monkeypatch.setenv("NC_MCP_URL", BASE)
    monkeypatch.setenv("NC_MCP_USER", USER)
    monkeypatch.setenv("NC_MCP_APP_PASSWORD", SECRET)
    monkeypatch.delenv("NC_MCP_STATIC_BEARER", raising=False)


@pytest.mark.anyio
async def test_every_hit_carries_exactly_the_four_openai_fields(clients: NcClients) -> None:
    """id, title, url and text, and nothing else: the answer is a contract, not a shape."""
    with respx.mock(assert_all_called=True) as mock:
        mock.get(PROVIDERS_URL).mock(
            return_value=httpx.Response(200, json=provider_list("files", "notes"))
        )
        mock.get(search_url("files")).mock(
            return_value=httpx.Response(200, json=fixture("ocs_search_files.json"))
        )
        mock.get(search_url("notes")).mock(
            return_value=httpx.Response(200, json=hits("Notes", [NOTE_ENTRY]))
        )

        results = await chatgpt.search(clients, query="budget")

    assert [set(hit) for hit in results] == [{"id", "title", "url", "text"}] * 3
    by_id = {hit["id"]: hit for hit in results}
    assert by_id["file:4711"] == {
        "id": "file:4711",
        "title": "Budget 2026.md",
        "url": f"{BASE}/index.php/f/4711",
        "text": "in Dokumente",
    }
    assert by_id["note:12"]["text"] == "Anwesend: Anja, Khaled", "the subline is the excerpt"


@pytest.mark.anyio
async def test_no_hit_ever_carries_an_empty_url(clients: NcClients) -> None:
    """An empty url turns off ChatGPT's citations for that hit; there must be none."""
    with respx.mock(assert_all_called=True) as mock:
        mock.get(PROVIDERS_URL).mock(return_value=httpx.Response(200, json=provider_list()))
        mock.get(search_url("files")).mock(
            return_value=httpx.Response(200, json=fixture("ocs_search_files.json"))
        )
        mock.get(search_url("notes")).mock(
            return_value=httpx.Response(200, json=hits("Notes", [NOTE_ENTRY]))
        )
        mock.get(search_url("search-deck-card-board")).mock(
            return_value=httpx.Response(200, json=hits("Deck", [CARD_ENTRY]))
        )
        mock.get(search_url("spreed")).mock(
            return_value=httpx.Response(200, json=hits("Talk", [TALK_ENTRY]))
        )

        results = await chatgpt.search(clients, query="budget")

    assert len(results) == 5
    for hit in results:
        assert hit["url"].startswith(BASE), f"a foreign or empty url in {hit}"


@pytest.mark.anyio
async def test_a_hit_without_a_resolvable_id_stays_in_the_result(clients: NcClients) -> None:
    """A Talk message cannot be fetched, but it is still an answer to the question."""
    with respx.mock(assert_all_called=True) as mock:
        mock.get(PROVIDERS_URL).mock(return_value=httpx.Response(200, json=provider_list("spreed")))
        mock.get(search_url("spreed")).mock(
            return_value=httpx.Response(200, json=hits("Talk", [TALK_ENTRY]))
        )

        results = await chatgpt.search(clients, query="budget")

    assert len(results) == 1
    assert results[0]["id"] == f"url:{BASE}/index.php/call/abc123#message_42"
    assert results[0]["url"] == f"{BASE}/index.php/call/abc123#message_42"


@pytest.mark.anyio
async def test_an_empty_query_is_refused_with_a_hint_and_never_reaches_nextcloud(
    clients: NcClients,
) -> None:
    with respx.mock(assert_all_called=False) as mock:
        providers = mock.get(PROVIDERS_URL)

        with pytest.raises(ToolError, match="empty") as excinfo:
            await chatgpt.search(clients, query="   ")

    assert providers.call_count == 0
    assert excinfo.value.hint


@pytest.mark.anyio
async def test_a_search_without_a_hit_is_an_empty_list(clients: NcClients) -> None:
    with respx.mock(assert_all_called=True) as mock:
        mock.get(PROVIDERS_URL).mock(return_value=httpx.Response(200, json=provider_list("files")))
        mock.get(search_url("files")).mock(return_value=httpx.Response(200, json=hits("Files", [])))

        assert await chatgpt.search(clients, query="gibtesnicht") == []


@pytest.mark.anyio
async def test_the_registered_tool_carries_an_output_schema_and_only_a_query() -> None:
    """The deliberate exception to the schema diet: ChatGPT reads this structure (D-14)."""
    async with Client(mcp, raise_exceptions=True) as client:
        tools = {tool.name: tool for tool in (await client.list_tools()).tools}

    assert "search" in tools, "the ChatGPT profile needs a tool named exactly search"
    tool = tools["search"]

    assert tool.output_schema is not None, "ChatGPT expects structured output here"
    assert set(tool.output_schema.get("properties", {})) == {"results"}

    schema = tool.input_schema
    assert set(schema.get("properties", {})) == {"query"}, "the parameter name is contract"
    assert set(schema.get("required", [])) == {"query"}

    annotations = tool.annotations
    assert annotations is not None
    assert annotations.read_only_hint is True


@pytest.mark.anyio
@pytest.mark.usefixtures("stdio_env")
async def test_a_call_answers_with_structured_content_and_the_same_json_as_text() -> None:
    """OpenAI reads both halves of the answer, so both have to carry the same object."""
    with respx.mock(assert_all_called=True) as mock:
        mock.get(PROVIDERS_URL).mock(return_value=httpx.Response(200, json=provider_list("notes")))
        mock.get(search_url("notes")).mock(
            return_value=httpx.Response(200, json=hits("Notes", [NOTE_ENTRY]))
        )

        async with Client(mcp, raise_exceptions=True) as client:
            result = await client.call_tool("search", {"query": "protokoll"})

    assert result.is_error is not True
    assert result.structured_content == {
        "results": [
            {
                "id": "note:12",
                "title": "Protokoll 2026-08-14",
                "url": f"{BASE}/index.php/apps/notes/note/12",
                "text": "Anwesend: Anja, Khaled",
            }
        ]
    }

    texts = [block.text for block in result.content if isinstance(block, TextContent)]
    assert json.loads("\n".join(texts)) == result.structured_content
