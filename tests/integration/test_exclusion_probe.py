"""Live probe of two search providers before the exclusion guard is wired (plan 27-03).

Open question 3 of the phase research: does the ``talk-message`` provider carry the file
name of a file shared into a conversation in ``title`` or ``subline``, and what shape does
a ``comments`` hit have? Both decide how ``unified_search`` classifies these providers, and
neither can be answered from a fixture, so they are measured against the running nc35
instance before any code builds on them.

The tests write the raw answers into
``.planning/phases/27-familien-anschluss-und-sandbox-parit-t/raw/27-03-provider-probe.txt``
and assert only that the measurement took place (entries were read), never its result.

Everything this harness writes is its own scaffolding on a test instance: one probe file,
one share into the test conversation, one text message and one comment. The share and the
file are removed in ``finally`` (the comment goes with the file), and the removal is
checked with a PROPFIND that has to answer 404.

Run it with::

    set -a && . ./.env.nc35 && set +a
    .venv/Scripts/python.exe -m pytest tests/integration/test_exclusion_probe.py -m integration -s
"""

import asyncio
import json
import os
import time
import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx
import pytest

from mcp_connector import provider_map
from mcp_connector.config import normalize_base_url
from mcp_connector.nextcloud import NcClients, capabilities
from mcp_connector.nextcloud.clients import ocs
from mcp_connector.nextcloud.clients import talk as talk_client
from mcp_connector.nextcloud.credentials import Credentials
from mcp_connector.tools import withhold

pytestmark = [pytest.mark.integration, pytest.mark.anyio]

RAW = (
    Path(__file__).resolve().parents[2]
    / ".planning"
    / "phases"
    / "27-familien-anschluss-und-sandbox-parit-t"
    / "raw"
    / "27-03-provider-probe.txt"
)
COMMAND = (
    "set -a && . ./.env.nc35 && set +a && .venv/Scripts/python.exe -m pytest "
    "tests/integration/test_exclusion_probe.py -m integration -s"
)
SHARES = "/apps/files_sharing/api/v1/shares"
TALK_PROVIDERS = ("talk-message", "talk-message-current")
COMMENTS_MARK = "=== comments ==="
ATTEMPTS = 5


@pytest.fixture
def probe_env() -> dict[str, str]:
    values = {
        "NC_MCP_URL": (os.environ.get("NC_MCP_URL") or "").strip(),
        "NC_MCP_TEST_USER": (os.environ.get("NC_MCP_TEST_USER") or "").strip(),
        "NC_MCP_TEST_APP_PASSWORD": (os.environ.get("NC_MCP_TEST_APP_PASSWORD") or "").strip(),
        "NC_MCP_TEST_TALK_ROOM": (os.environ.get("NC_MCP_TEST_TALK_ROOM") or "").strip(),
    }
    missing = [name for name, value in values.items() if not value]
    if missing:
        pytest.skip(f"no nc35 probe configured (missing: {', '.join(missing)})")
    assert values["NC_MCP_TEST_USER"] != "admin", "the probe runs as a normal user"
    return values


@pytest.fixture
async def clients(probe_env: dict[str, str]) -> AsyncIterator[NcClients]:
    capabilities.clear_cache()
    nc_clients = NcClients(
        client=httpx.AsyncClient(follow_redirects=False, timeout=30.0),
        creds=Credentials(
            base_url=normalize_base_url(probe_env["NC_MCP_URL"]),
            user=probe_env["NC_MCP_TEST_USER"],
            secret=probe_env["NC_MCP_TEST_APP_PASSWORD"],
        ),
    )
    async with nc_clients.client:
        yield nc_clients


def _file_url(clients: NcClients, name: str) -> str:
    creds = clients.creds
    return f"{creds.base_url}/remote.php/dav/files/{quote(creds.user)}/{quote(name)}"


async def _put_probe(clients: NcClients, name: str) -> str:
    """Create the probe file and return its file id."""
    url = _file_url(clients, name)
    put = await clients.client.put(url, content=b"probe 27-03\n", auth=clients.creds.auth())
    assert put.status_code in (201, 204), f"PUT {name}: {put.status_code}"
    body = (
        '<?xml version="1.0"?><d:propfind xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns">'
        "<d:prop><oc:fileid/></d:prop></d:propfind>"
    )
    found = await clients.client.request(
        "PROPFIND",
        url,
        headers={"Depth": "0", "Content-Type": "application/xml"},
        content=body,
        auth=clients.creds.auth(),
    )
    assert found.status_code == 207, f"PROPFIND {name}: {found.status_code}"
    text = found.text
    start = text.index("<oc:fileid>") + len("<oc:fileid>")
    return text[start : text.index("</oc:fileid>", start)].strip()


async def _delete_probe(clients: NcClients, name: str) -> int:
    """Delete the probe file (harness only) and return the status of a PROPFIND after it."""
    url = _file_url(clients, name)
    await clients.client.request("DELETE", url, auth=clients.creds.auth())
    after = await clients.client.request(
        "PROPFIND", url, headers={"Depth": "0"}, auth=clients.creds.auth()
    )
    return after.status_code


async def _versions(clients: NcClients) -> str:
    response = await ocs.ocs_get(clients.client, clients.creds, capabilities.CAPABILITIES_PATH)
    payload = ocs.parse_ocs(response, what="the capabilities")
    version = payload.get("version", {}) if isinstance(payload, dict) else {}
    caps = payload.get("capabilities", {}) if isinstance(payload, dict) else {}
    spreed = caps.get("spreed", {}) if isinstance(caps, dict) else {}
    return f"nextcloud={version.get('string')} spreed={spreed.get('version')}"


async def _search(clients: NcClients, provider_id: str, term: str) -> list[dict[str, Any]]:
    """Ask one provider up to ATTEMPTS times until it answers entries (index lag)."""
    entries: list[dict[str, Any]] = []
    for attempt in range(ATTEMPTS):
        try:
            payload = await ocs.provider_search(
                clients.client, clients.creds, provider_id, term, 10
            )
        except Exception as exc:  # the probe records whatever happened
            return [{"__error__": f"{type(exc).__name__}: {exc}"}]
        raw = payload.get("entries")
        entries = [e for e in raw if isinstance(e, dict)] if isinstance(raw, list) else []
        if entries:
            return entries
        if attempt < ATTEMPTS - 1:
            await asyncio.sleep(1)
    return entries


def _dump(label: str, entries: list[dict[str, Any]]) -> list[str]:
    return [
        f"--- {label} ({len(entries)} entries)",
        json.dumps(entries, indent=2, ensure_ascii=False),
    ]


def _carries(entry: dict[str, Any], needle: str) -> bool:
    return needle in str(entry.get("title") or "") or needle in str(entry.get("subline") or "")


def _first_difference(share: dict[str, Any], text: dict[str, Any]) -> str:
    """The first field in which a file share hit differs in kind from a text hit."""
    for field in ("icon", "thumbnailUrl", "attributes", "resourceUrl", "rounded"):
        if _shape(share.get(field)) != _shape(text.get(field)):
            return field
    return "keine"


def _shape(value: Any) -> str:
    if isinstance(value, dict):
        return "dict:" + ",".join(sorted(value))
    if isinstance(value, list):
        return f"list:{len(value)}"
    if isinstance(value, str):
        # Compare the form, not the concrete ids inside the URL.
        return "str:" + "".join("9" if c.isdigit() else c for c in value.split("?")[0])[:80]
    return type(value).__name__


async def _room_token(clients: NcClients, name: str) -> str:
    rooms = await talk_client.get_rooms(clients.client, clients.creds, include_last_message=False)
    for room in rooms:
        if str(room.get("displayName") or "") == name:
            return str(room["token"])
    pytest.skip(f"the conversation {name!r} does not exist for this account")


async def test_talk_message_provider_probe(clients: NcClients, probe_env: dict[str, str]) -> None:
    stem = f"probe27-{uuid.uuid4().hex[:10]}"
    name = f"{stem}.txt"
    word = f"probewort{uuid.uuid4().hex[:10]}"
    token = await _room_token(clients, probe_env["NC_MCP_TEST_TALK_ROOM"])
    share_id: str | None = None
    lines: list[str] = []
    after_status = 0
    try:
        fileid = await _put_probe(clients, name)
        shared = await ocs.ocs_post(
            clients.client,
            clients.creds,
            SHARES,
            {"path": f"/{name}", "shareType": 10, "shareWith": token},
        )
        share_data = ocs.parse_ocs(shared, what="the probe share")
        share_id = str(share_data.get("id"))
        await talk_client.send_message(
            clients.client, clients.creds, token, message=f"Textvergleich {word}"
        )

        by_name: dict[str, list[dict[str, Any]]] = {}
        by_stem: dict[str, list[dict[str, Any]]] = {}
        by_word: dict[str, list[dict[str, Any]]] = {}
        for provider_id in TALK_PROVIDERS:
            by_name[provider_id] = await _search(clients, provider_id, name)
            by_stem[provider_id] = await _search(clients, provider_id, stem)
            by_word[provider_id] = await _search(clients, provider_id, word)

        share_hits = [
            e for p in TALK_PROVIDERS for e in by_name[p] + by_stem[p] if "__error__" not in e
        ]
        text_hits = [e for p in TALK_PROVIDERS for e in by_word[p] if "__error__" not in e]
        leak = any(_carries(e, name) or _carries(e, stem) for e in share_hits)
        difference = (
            _first_difference(share_hits[0], text_hits[0]) if share_hits and text_hits else "keine"
        )

        lines += [
            f"# 27-03 provider probe, {time.strftime('%Y-%m-%d %H:%M:%S %z')}",
            f"# command: {COMMAND}",
            f"# {await _versions(clients)}",
            f"# probe file: /{name} (fileid {fileid}), shared into the test conversation",
            f"# text message word: {word}",
            "",
            "=== talk-message ===",
            f"KLASSE={'leak' if leak else 'kein-leak'}",
            f"UNTERSCHEIDUNG={difference}",
        ]
        for provider_id in TALK_PROVIDERS:
            lines += _dump(f"{provider_id} term=<file name>", by_name[provider_id])
            lines += _dump(f"{provider_id} term=<name stem>", by_stem[provider_id])
            lines += _dump(f"{provider_id} term=<text word>", by_word[provider_id])
        assert text_hits or share_hits or any(by_word.values()), "no provider answer was read"
    finally:
        if share_id:
            await clients.client.delete(
                ocs.ocs_url(clients.creds, f"{SHARES}/{share_id}"),
                headers=dict(ocs.OCS_HEADERS),
                auth=clients.creds.auth(),
            )
        after_status = await _delete_probe(clients, name)
    lines += ["", f"# cleanup: PROPFIND after DELETE answered {after_status}"]
    RAW.parent.mkdir(parents=True, exist_ok=True)
    RAW.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert after_status == 404, f"the probe file survived the cleanup: {after_status}"


async def test_comments_provider_probe(clients: NcClients) -> None:
    name = f"probe27-{uuid.uuid4().hex[:10]}.txt"
    word = f"kommentarwort{uuid.uuid4().hex[:10]}"
    lines: list[str] = []
    after_status = 0
    try:
        fileid = await _put_probe(clients, name)
        posted = await clients.client.post(
            f"{clients.creds.base_url}/remote.php/dav/comments/files/{fileid}",
            json={"actorType": "users", "verb": "comment", "message": f"Kommentar {word}"},
            auth=clients.creds.auth(),
        )
        assert posted.status_code == 201, f"comment POST: {posted.status_code}"
        entries = await _search(clients, "comments", word)
        refs = [
            withhold.file_refs(clients.creds.base_url, "comments", e)
            for e in entries
            if "__error__" not in e
        ]
        source = "keins"
        for entry in entries:
            attributes = entry.get("attributes")
            if isinstance(attributes, dict) and attributes.get("fileId"):
                source = "attributes"
                break
            url = provider_map.absolute_url(clients.creds.base_url, entry.get("resourceUrl"))
            if provider_map.file_id({}, url):
                source = "url"
                break
        lines += [
            COMMENTS_MARK,
            f"# probe file: /{name} (fileid {fileid}), comment word: {word}",
            f"COMMENTS_FILEID_AUS={source}",
            f"# withhold.file_refs: {[(r.fileid, r.path, r.file_bearing) for r in refs]}",
            *_dump("comments term=<comment word>", entries),
        ]
        assert entries, "the comments provider answered nothing, nothing was measured"
    finally:
        after_status = await _delete_probe(clients, name)
    lines += [f"# cleanup: PROPFIND after DELETE answered {after_status}"]
    existing = RAW.read_text(encoding="utf-8") if RAW.exists() else ""
    kept = existing.split(COMMENTS_MARK)[0].rstrip("\n")
    RAW.parent.mkdir(parents=True, exist_ok=True)
    RAW.write_text((kept + "\n\n" if kept else "") + "\n".join(lines) + "\n", encoding="utf-8")
    assert after_status == 404, f"the probe file survived the cleanup: {after_status}"


#: Plan 27-05, resolution open question 2: what a file conversation looks like in the list.
RAW_FILE_ROOM = RAW.with_name("27-05-file-conversation-probe.txt")
FILE_ROOM_COMMAND = (
    "set -a && . ./.env.nc35 && set +a && .venv/Scripts/python.exe -m pytest "
    "tests/integration/test_exclusion_probe.py -m integration -s -k file_conversation"
)
#: The two spellings of the file conversation route; the probe records which one answers.
FILE_ROOM_ROUTES = ("/apps/spreed/api/v1/file/{fileid}", "/apps/spreed/api/v4/file/{fileid}")
ROOM_FIELDS = ("token", "type", "name", "displayName", "objectType", "objectId")


async def test_file_conversation_probe(clients: NcClients) -> None:
    """Create a file conversation for a shared probe file and record its raw list entry.

    The file is shared with the second test account (shareType 0), because Talk only opens a
    conversation for a file that is shared. Joining the conversation makes this account a
    participant, which is what puts it into the conversation list at all; the session is
    left again right away. Removed in ``finally``: the participation, the share and the file.
    """
    user2 = (os.environ.get("NC_MCP_TEST_USER2") or "").strip()
    if not user2:
        pytest.skip("no second test account configured (NC_MCP_TEST_USER2)")
    name = f"probe27-05-{uuid.uuid4().hex[:10]}.txt"
    share_id: str | None = None
    token = ""
    lines: list[str] = []
    after_status = 0
    try:
        fileid = await _put_probe(clients, name)
        shared = await ocs.ocs_post(
            clients.client,
            clients.creds,
            SHARES,
            {"path": f"/{name}", "shareType": 0, "shareWith": user2},
        )
        share_id = str(ocs.parse_ocs(shared, what="the probe share").get("id"))

        route_lines: list[str] = []
        for template in FILE_ROOM_ROUTES:
            route = template.format(fileid=fileid)
            response = await ocs.ocs_get(clients.client, clients.creds, route)
            route_lines.append(f"# GET {route}: HTTP {response.status_code} {response.text[:300]}")
            if response.status_code == 200 and not token:
                payload = ocs.parse_ocs(response, what="the file conversation")
                token = str(payload.get("token") or "") if isinstance(payload, dict) else ""
        assert token, "no route answered with a conversation token:\n" + "\n".join(route_lines)

        joined = await clients.client.post(
            ocs.ocs_url(clients.creds, f"/apps/spreed/api/v4/room/{token}/participants/active"),
            headers=dict(ocs.OCS_HEADERS),
            auth=clients.creds.auth(),
        )
        route_lines.append(f"# POST .../room/<token>/participants/active: HTTP {joined.status_code}")
        left = await clients.client.delete(
            ocs.ocs_url(clients.creds, f"/apps/spreed/api/v4/room/{token}/participants/active"),
            headers=dict(ocs.OCS_HEADERS),
            auth=clients.creds.auth(),
        )
        route_lines.append(f"# DELETE .../room/<token>/participants/active: HTTP {left.status_code}")

        rooms = await talk_client.get_rooms(
            clients.client, clients.creds, include_last_message=True
        )
        found = [room for room in rooms if str(room.get("token") or "") == token]
        raw_room = {field: found[0].get(field) for field in ROOM_FIELDS} if found else {}
        object_id = str(raw_room.get("objectId") or "")
        lines += [
            f"# 27-05 file conversation probe, {time.strftime('%Y-%m-%d %H:%M:%S %z')}",
            f"# command: {FILE_ROOM_COMMAND}",
            f"# {await _versions(clients)}",
            f"# probe file: /{name} (fileid {fileid}), shared with the second test account",
            *route_lines,
            f"# conversation in the list of this account: {'ja' if found else 'nein'}",
            "",
            f"OBJECT_TYPE={raw_room.get('objectType', '<fehlt>')}",
            f"OBJECT_ID_IST_FILEID={'ja' if object_id == fileid else 'nein'}",
            f"NAME_IST_DATEINAME={'ja' if raw_room.get('displayName') == name else 'nein'}",
            "",
            "--- raw list entry (selected fields)",
            json.dumps(raw_room, indent=2, ensure_ascii=False),
            "--- raw list entry (all fields)",
            json.dumps(found[0] if found else {}, indent=2, ensure_ascii=False),
        ]
        assert found, "the file conversation is not in the conversation list of this account"
    finally:
        if token:
            await clients.client.delete(
                ocs.ocs_url(clients.creds, f"/apps/spreed/api/v4/room/{token}/participants/self"),
                headers=dict(ocs.OCS_HEADERS),
                auth=clients.creds.auth(),
            )
        if share_id:
            await clients.client.delete(
                ocs.ocs_url(clients.creds, f"{SHARES}/{share_id}"),
                headers=dict(ocs.OCS_HEADERS),
                auth=clients.creds.auth(),
            )
        after_status = await _delete_probe(clients, name)
    lines += ["", f"# cleanup: participation left, share removed, PROPFIND after DELETE {after_status}"]
    RAW_FILE_ROOM.parent.mkdir(parents=True, exist_ok=True)
    RAW_FILE_ROOM.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert after_status == 404, f"the probe file survived the cleanup: {after_status}"
