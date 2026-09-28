"""Live proofs of the ``kein-ki`` exclusion against the nc35 instance (plan 27-07).

The roadmap asks for measurements against a real Nextcloud for success criteria 1, 2 and 4;
unit tests alone do not count. This module builds its own test tree, tags parts of it with
``occ`` (the harness only: ``src/`` never writes a tag, EXCL-07), calls the tool functions
exactly as the server does and writes one finding line per check into
``.planning/phases/27-familien-anschluss-und-sandbox-parit-t/raw/27-07-live.txt``:
``SC<n> <tool> <case>: <ja|nein> (<short raw value>)``. A check records its line first and
asserts afterwards, so a failing run leaves its ``nein`` in the protocol.

Every tool call gets a fresh ``NcClients`` (pattern 7): a guard lives for one call, so each
check pays its own flight and sees a tag that was set a moment ago. :class:`Fresh` refuses to
hand out a guard twice (T-27-62).

Everything the harness writes is its own scaffolding on the test instance: one folder tree
below ``/live27-<hex8>``, one file outside it, three notes in two categories of their own,
two comments, shares into the test conversation, one share with the second account and the
file conversation that comes with it. The tag is created by this run when it does not exist
and deleted afterwards; the tree, the notes and the shares are removed in ``finally``, and
the teardown proves the removal (PROPFIND 404, no ``kein-ki`` left in ``occ tag:list``).

Run it with::

    set -a && . ./.env.nc35 && set +a
    .venv/Scripts/python.exe -m pytest tests/integration/test_exclusion_live.py -m integration -s
"""

import asyncio
import dataclasses
import json
import os
import re
import shutil
import statistics
import subprocess
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Iterator
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx
import pytest
import respx
from lxml import etree
from topology import NC_CONTAINER

from mcp_connector import config, ids
from mcp_connector.config import normalize_base_url
from mcp_connector.errors import ToolError
from mcp_connector.nextcloud import NcClients, capabilities
from mcp_connector.nextcloud import exclusion as exclusion_core
from mcp_connector.nextcloud.clients import dav
from mcp_connector.nextcloud.clients import systemtags as systemtags_client
from mcp_connector.nextcloud.clients import talk as talk_client
from mcp_connector.nextcloud.credentials import Credentials
from mcp_connector.nextcloud.exclusion import ExclusionGuard
from mcp_connector.tools import chatgpt as chatgpt_tools
from mcp_connector.tools import context as context_tools
from mcp_connector.tools import files as files_tools
from mcp_connector.tools import notes as notes_tools
from mcp_connector.tools import search as search_tools
from mcp_connector.tools import talk as talk_tools
from mcp_connector.tools import withhold

pytestmark = [pytest.mark.integration, pytest.mark.anyio]

RAW = (
    Path(__file__).resolve().parents[2]
    / ".planning"
    / "phases"
    / "27-familien-anschluss-und-sandbox-parit-t"
    / "raw"
    / "27-07-live.txt"
)
COMMAND = (
    "set -a && . ./.env.nc35 && set +a && .venv/Scripts/python.exe -m pytest "
    "tests/integration/test_exclusion_live.py -m integration -s"
)
# The Nextcloud container comes from the topology (NC_MCP_E2E_NEXTCLOUD), so occ never runs
# in the wrong instance (28-12, harness trap from 27-10).
CONTAINER = NC_CONTAINER
TAG = exclusion_core.EXCLUDE_TAG
ENV_NAMES = (
    "NC_MCP_URL",
    "NC_MCP_TEST_USER",
    "NC_MCP_TEST_APP_PASSWORD",
    "NC_MCP_TEST_USER2",
    "NC_MCP_TEST_TALK_ROOM",
)
NOTES_API = "/index.php/apps/notes/api/v1"
UNKNOWN_FILEID = "999999999"
ATTEMPTS = 5

_DAV = "{DAV:}"
_OC = "{http://owncloud.org/ns}"
_PROPFIND = (
    b'<?xml version="1.0"?><d:propfind xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns">'
    b"<d:prop><oc:fileid/><d:getetag/></d:prop></d:propfind>"
)
# A minimal PDF byte pattern: enough for Nextcloud to store it as application/pdf.
_PDF = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"


# --- protocol -------------------------------------------------------------------------


def record(line: str) -> None:
    """Append one line to the raw protocol of this plan."""
    RAW.parent.mkdir(parents=True, exist_ok=True)
    with RAW.open("a", encoding="utf-8") as fh:
        fh.write(line.rstrip("\n") + "\n")


def check(criterion: str, tool: str, case: str, ok: bool, raw: str) -> None:
    """Record ``SC<n> <tool> <case>: <ja|nein> (<raw>)`` and then assert ``ok``."""
    short = raw if len(raw) <= 240 else raw[:237] + "..."
    record(f"{criterion} {tool} {case}: {'ja' if ok else 'nein'} ({short})")
    assert ok, f"{criterion} {tool} {case}: {short}"


def shape(exc: ToolError, *substitutions: tuple[str, str]) -> tuple[str, str, str, str]:
    """The comparable form of an error, with concrete values replaced by placeholders.

    The not-found sentences carry the path or the id that was asked for, so a withheld
    entry and a truly missing one can only be compared once both concrete values are
    swapped for the same placeholder; everything else (class, sentence, hint, reason) has
    to be identical.
    """
    message, hint = exc.message, exc.hint
    for value, placeholder in substitutions:
        message = message.replace(value, placeholder)
        hint = hint.replace(value, placeholder)
    return (type(exc).__name__, message, hint, exc.reason)


def exact(exc: ToolError) -> tuple[str, str, str, str]:
    return (type(exc).__name__, exc.message, exc.hint, exc.reason)


async def refusal(call: Awaitable[Any]) -> ToolError:
    """The ToolError a call raises; a call that answers fails the check."""
    try:
        answer = await call
    except ToolError as exc:
        return exc
    raise AssertionError(f"expected a refusal, got an answer: {str(answer)[:200]}")


def dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


# --- harness --------------------------------------------------------------------------


def occ(*argv: str, check_status: bool = True) -> str:
    """One ``occ`` call inside the nc35 container (harness only, EXCL-07)."""
    finished = subprocess.run(  # noqa: S603 - fixed argv, test harness
        ["docker", "exec", "-u", "www-data", CONTAINER, "php", "occ", *argv],  # noqa: S607
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    output = ((finished.stdout or "") + (finished.stderr or "")).replace("\r", "").strip()
    if check_status and finished.returncode != 0:
        raise AssertionError(f"occ {' '.join(argv)} failed: {output[:300]}")
    return output


def tag_ids() -> list[str]:
    """The ids of every tag ``occ tag:list`` knows under a spelling of ``kein-ki``."""
    raw = occ("tag:list", "--output=json", check_status=False)
    start = min((i for i in (raw.find("{"), raw.find("[")) if i >= 0), default=-1)
    try:
        data = json.loads(raw[start:]) if start >= 0 else []
    except json.JSONDecodeError:
        return []
    items: list[tuple[str, str]] = []
    if isinstance(data, dict):
        items = [(str(k), str(v.get("name", ""))) for k, v in data.items() if isinstance(v, dict)]
    elif isinstance(data, list):
        items = [
            (str(v.get("id", "")), str(v.get("name", ""))) for v in data if isinstance(v, dict)
        ]
    return [tag_id for tag_id, tag_name in items if exclusion_core.is_exclude_name(tag_name)]


class Harness:
    """Synchronous writes of the test data as alice, never through the tools under test."""

    def __init__(self, base_url: str, user: str, secret: str) -> None:
        self.base_url = base_url
        self.user = user
        self.http = httpx.Client(auth=(user, secret), timeout=30.0, follow_redirects=False)

    def close(self) -> None:
        self.http.close()

    def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """One request with the app password alone, never with a session cookie.

        Measured on nc35: after the Notes API answered, the session cookie it set made every
        later WebDAV request of the same client answer 401, so the cleanup deleted nothing.
        """
        self.http.cookies.clear()
        return self.http.request(method, url, **kwargs)

    def dav_url(self, path: str) -> str:
        return f"{self.base_url}/remote.php/dav/files/{quote(self.user)}{quote(path)}"

    def mkcol(self, path: str) -> None:
        response = self.request("MKCOL", self.dav_url(path))
        assert response.status_code == 201, f"MKCOL {path}: {response.status_code}"

    def put(self, path: str, data: bytes) -> None:
        response = self.request("PUT", self.dav_url(path), content=data)
        assert response.status_code in (201, 204), f"PUT {path}: {response.status_code}"

    def delete(self, path: str) -> None:
        self.request("DELETE", self.dav_url(path))

    def stat(self, path: str) -> tuple[int, str, str]:
        """(status, fileid, etag) of one entry; status 404 for a missing one."""
        response = self.request(
            "PROPFIND",
            self.dav_url(path),
            headers={"Depth": "0", "Content-Type": "application/xml"},
            content=_PROPFIND,
        )
        if response.status_code != 207:
            return response.status_code, "", ""
        tree = etree.fromstring(response.content)
        fileid = tree.findtext(f".//{_OC}fileid") or ""
        etag = tree.findtext(f".//{_DAV}getetag") or ""
        return 207, fileid.strip(), etag.strip()

    def fileid(self, path: str) -> str:
        status, fileid, _ = self.stat(path)
        assert status == 207, f"no entry at {path}: {status}"
        assert fileid, f"no fileid for {path}"
        return fileid

    def ocs(self, method: str, path: str, data: dict[str, Any] | None = None) -> Any:
        response = self.request(
            method,
            f"{self.base_url}/ocs/v2.php{path}",
            headers={"OCS-APIRequest": "true", "Accept": "application/json"},
            data=data,
        )
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        return response.status_code, payload.get("ocs", {}).get("data") if payload else None

    def share(self, path: str, share_type: int, share_with: str) -> str:
        status, data = self.ocs(
            "POST",
            "/apps/files_sharing/api/v1/shares",
            {"path": path, "shareType": share_type, "shareWith": share_with},
        )
        assert status == 200, f"share {path}: {status} {data}"
        assert isinstance(data, dict), f"share {path}: {data}"
        return str(data["id"])

    def unshare(self, share_id: str) -> None:
        self.ocs("DELETE", f"/apps/files_sharing/api/v1/shares/{share_id}")

    def comment(self, fileid: str, message: str) -> None:
        response = self.request(
            "POST",
            f"{self.base_url}/remote.php/dav/comments/files/{fileid}",
            json={"actorType": "users", "verb": "comment", "message": message},
        )
        assert response.status_code == 201, f"comment on {fileid}: {response.status_code}"

    def notes(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        response = self.request(
            method,
            f"{self.base_url}{NOTES_API}{path}",
            headers={"OCS-APIRequest": "true", "Accept": "application/json"},
            json=body,
        )
        assert response.status_code < 300, f"notes {method} {path}: {response.status_code}"
        return response.json() if response.content else None

    def note_titles(self) -> dict[str, str]:
        """id -> title of every note of this account (a light listing without content)."""
        listing = self.notes("GET", "/notes?exclude=content")
        return {str(n["id"]): str(n.get("title") or "") for n in listing if isinstance(n, dict)}

    def provider_entries(self, provider_id: str, term: str) -> list[dict[str, Any]]:
        status, data = self.ocs(
            "GET", f"/search/providers/{provider_id}/search?term={quote(term)}&limit=10"
        )
        entries = data.get("entries") if status == 200 and isinstance(data, dict) else None
        return [e for e in entries if isinstance(e, dict)] if isinstance(entries, list) else []


@dataclasses.dataclass
class World:
    """The test tree of this run and what the harness knows about it."""

    hexid: str
    creds: Credentials
    harness: Harness
    user2: str
    talk_room: str
    paths: dict[str, str] = dataclasses.field(default_factory=dict)
    fileids: dict[str, str] = dataclasses.field(default_factory=dict)
    etags: dict[str, str] = dataclasses.field(default_factory=dict)
    notes: dict[str, str] = dataclasses.field(default_factory=dict)
    note_titles: dict[str, str] = dataclasses.field(default_factory=dict)
    categories: dict[str, str] = dataclasses.field(default_factory=dict)
    before_tag: str = ""
    comment_word: str = ""
    note_word: str = ""
    created_tag: str | None = None
    tagged_targets: list[str] = dataclasses.field(default_factory=list)

    @property
    def root(self) -> str:
        return self.paths["root"]

    def name(self, key: str) -> str:
        return self.paths[key].rsplit("/", 1)[-1]

    def tagged_fileids(self) -> set[str]:
        """Every file id the tag covers: the tagged nodes and what lies below them."""
        keys = ("geheim", "vorher", "projekt", "a", "scan", "unter", "b")
        found = {self.fileids[k] for k in keys}
        found |= {self.notes["geheim_b"], self.notes["geheim_g"], self.categories["geheim_id"]}
        return found

    def tagged_names(self) -> list[str]:
        return [self.name(k) for k in ("geheim", "vorher", "projekt", "a", "scan", "b")]


class Fresh:
    """Hands out one ``NcClients`` per tool call, each with a guard nobody saw before."""

    def __init__(self, base: NcClients) -> None:
        self.base = base
        self.guards: list[ExclusionGuard] = []

    def __call__(self) -> NcClients:
        guard = ExclusionGuard()
        assert all(guard is not seen for seen in self.guards), "a guard was handed out twice"
        self.guards.append(guard)
        return dataclasses.replace(self.base, exclusion=guard)


@asynccontextmanager
async def live(world: World) -> AsyncIterator[Fresh]:
    capabilities.clear_cache()
    async with httpx.AsyncClient(follow_redirects=False, timeout=30.0) as client:
        yield Fresh(NcClients(client=client, creds=world.creds))


def _env() -> dict[str, str]:
    values = {name: (os.environ.get(name) or "").strip() for name in ENV_NAMES}
    missing = [name for name, value in values.items() if not value]
    if missing:
        pytest.skip(f"no nc35 live run configured (missing: {', '.join(missing)})")
    assert values["NC_MCP_TEST_USER"] != "admin", "the live run acts as a normal user"
    if shutil.which("docker") is None:
        pytest.skip("docker is not on PATH, occ cannot tag")
    probe = subprocess.run(  # noqa: S603 - fixed argv, test harness
        ["docker", "inspect", "-f", "{{.State.Running}}", CONTAINER],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    if probe.returncode != 0 or "true" not in probe.stdout:
        pytest.skip(f"the container {CONTAINER} is not running")
    return values


def _build(world: World) -> None:
    """Create the tree, the notes and the comments of this run, all untagged."""
    h, harness = world.hexid, world.harness
    root = f"/live27-{h}"
    world.paths = {
        "root": root,
        "offen": f"{root}/offen-{h}.txt",
        "geheim": f"{root}/geheim-{h}.txt",
        "vorher": f"{root}/vorher-{h}.txt",
        "projekt": f"{root}/Projekt-{h}",
        "a": f"{root}/Projekt-{h}/a-{h}.txt",
        "scan": f"{root}/Projekt-{h}/scan-{h}.pdf",
        "unter": f"{root}/Projekt-{h}/Unter",
        "b": f"{root}/Projekt-{h}/Unter/b-{h}.txt",
        "out": f"/live27-out-{h}.txt",
    }
    harness.mkcol(root)
    harness.mkcol(world.paths["projekt"])
    harness.mkcol(world.paths["unter"])
    contents = {
        "offen": f"offen inhaltwort{h} sichtbar\n",
        "geheim": f"geheim inhaltwort{h} geheimwort{h}\n",
        "vorher": f"vorher inhaltwort{h} vorherwort{h}\n",
        "a": f"geheim a inhaltwort{h}\n",
        "b": f"geheim b inhaltwort{h}\n",
        "out": f"ausserhalb inhaltwort{h}\n",
    }
    for key, text in contents.items():
        harness.put(world.paths[key], text.encode("utf-8"))
    harness.put(world.paths["scan"], _PDF)
    for key, path in world.paths.items():
        status, fileid, etag = harness.stat(path)
        assert status == 207, f"stat {key}: {status}"
        assert fileid, f"no fileid for {key}"
        world.fileids[key] = fileid
        world.etags[key] = etag

    world.note_word = f"notizwort{h}"
    world.categories = {"offen": f"Live27Offen-{h}", "geheim": f"Live27Geheim-{h}"}
    planned = {
        "offen_a": (f"Live27 offen A {h}", world.categories["offen"]),
        "geheim_b": (f"Live27 geheim B {h}", world.categories["offen"]),
        "geheim_g": (f"Live27 geheim G {h}", world.categories["geheim"]),
    }
    for key, (title, category) in planned.items():
        note = harness.notes(
            "POST",
            "/notes",
            {"title": title, "content": f"{title} {world.note_word}", "category": category},
        )
        world.notes[key] = str(note["id"])
        world.note_titles[key] = str(note.get("title") or title)
    settings = harness.notes("GET", "/settings") or {}
    notes_root = "/" + str(settings.get("notesPath") or "Notes").strip("/")
    world.categories["notes_root"] = notes_root
    world.categories["geheim_path"] = f"{notes_root}/{world.categories['geheim']}"
    world.categories["offen_path"] = f"{notes_root}/{world.categories['offen']}"
    world.categories["geheim_id"] = harness.fileid(world.categories["geheim_path"])

    world.comment_word = f"kommentarwort{h}"
    harness.comment(world.fileids["offen"], f"Kommentar innen {world.comment_word}")
    harness.comment(world.fileids["out"], f"Kommentar aussen {world.comment_word}")


async def _read_before_tag(world: World) -> None:
    """Read vorher.txt once by its file id while nothing is tagged (success criterion 2)."""
    capabilities.clear_cache()
    async with httpx.AsyncClient(follow_redirects=False, timeout=30.0) as client:
        clients = NcClients(client=client, creds=world.creds)
        scope = await clients.exclusion.scope(clients)
        answer = await chatgpt_tools.fetch(
            dataclasses.replace(clients, exclusion=ExclusionGuard()),
            ids.encode_file(world.fileids["vorher"]),
        )
    world.before_tag = str(answer.get("text") or "")
    check(
        "SC2",
        "fetch",
        "vorher gelesen vor dem Taggen",
        scope.state == "untagged" and f"vorherwort{world.hexid}" in world.before_tag,
        f"scope={scope.state} text={world.before_tag.strip()!r}",
    )


def _tag(world: World) -> None:
    """Create ``kein-ki`` if missing and tag the protected parts (harness only)."""
    existing = tag_ids()
    if not existing:
        output = occ("tag:add", TAG, "public", "--output=json")
        start = output.find("{")
        created = json.loads(output[start:]) if start >= 0 else {}
        world.created_tag = str(created.get("id") or "")
        assert world.created_tag.isdigit(), f"occ tag:add gave no id: {output[:200]}"
    targets = [
        world.fileids["geheim"],
        world.fileids["projekt"],
        world.fileids["vorher"],
        world.notes["geheim_b"],
        world.categories["geheim_id"],
    ]
    for target in targets:
        occ("tag:files:add", target, TAG, "public")
        world.tagged_targets.append(target)
    record(
        f"# tagged by occ tag:files:add: geheim, Projekt/, vorher, note B, "
        f"{world.categories['geheim_path']} (tag {'created' if world.created_tag else 'existed'})"
    )


def _cleanup(world: World) -> list[str]:
    """Remove everything of this run and return the proof lines."""
    harness = world.harness
    if world.created_tag:
        occ("tag:delete", world.created_tag, check_status=False)
    else:
        for target in world.tagged_targets:
            occ("tag:files:delete", target, TAG, "public", check_status=False)
    for note_id in world.notes.values():
        harness.request("DELETE", f"{harness.base_url}{NOTES_API}/notes/{note_id}")
    for key in ("offen_path", "geheim_path"):
        if key in world.categories:
            harness.delete(world.categories[key])
    for key in ("root", "out"):
        if key in world.paths:
            harness.delete(world.paths[key])

    lines: list[str] = []
    for key in ("root", "out"):
        if key in world.paths:
            lines.append(f"CLEANUP PROPFIND {key}: {harness.stat(world.paths[key])[0]}")
    for key in ("offen_path", "geheim_path"):
        if key in world.categories:
            lines.append(f"CLEANUP PROPFIND {key}: {harness.stat(world.categories[key])[0]}")
    left = set(world.notes.values()) & set(harness.note_titles())
    lines.append(f"CLEANUP notes left: {len(left)}")
    lines.append(f"CLEANUP tag {TAG} listed: {len(tag_ids()) if world.created_tag else 'n/a'}")
    return lines


@pytest.fixture(scope="module")
def world() -> Iterator[World]:
    values = _env()
    creds = Credentials(
        base_url=normalize_base_url(values["NC_MCP_URL"]),
        user=values["NC_MCP_TEST_USER"],
        secret=values["NC_MCP_TEST_APP_PASSWORD"],
    )
    harness = Harness(creds.base_url, creds.user, values["NC_MCP_TEST_APP_PASSWORD"])
    state = World(
        hexid=uuid.uuid4().hex[:8],
        creds=creds,
        harness=harness,
        user2=values["NC_MCP_TEST_USER2"],
        talk_room=values["NC_MCP_TEST_TALK_ROOM"],
    )
    status = harness.request("GET", f"{creds.base_url}/status.php").json()
    exclusion_core.clear_cache()
    record("")
    record(f"# 27-07 live run {time.strftime('%Y-%m-%d %H:%M:%S %z')}")
    record(f"# command: {COMMAND}")
    record(f"# nextcloud={status.get('versionstring')} (status.php), user={creds.user}")
    record(f"# tree: /live27-{state.hexid}")
    try:
        _build(state)
        asyncio.run(_read_before_tag(state))
        _tag(state)
        yield state
    finally:
        lines = _cleanup(state)
        for line in lines:
            record(line)
        harness.close()
        exclusion_core.clear_cache()
    assert all(line.endswith(": 404") for line in lines if "PROPFIND" in line), lines
    assert "CLEANUP notes left: 0" in lines, lines
    assert f"CLEANUP tag {TAG} listed: 0" in lines or not state.created_tag, lines


# --- success criterion 1: the files family ----------------------------------------------


async def test_sc1_list_and_search(world: World) -> None:
    root = world.root
    async with live(world) as fresh:
        listing = await files_tools.list_dir(fresh(), root)
        names = sorted(item["name"] for item in listing["items"])
        check(
            "SC1",
            "files_list",
            "getaggte Datei und getaggter Ordner fehlen",
            names == [world.name("offen")],
            f"items={names}",
        )

        tagged = await refusal(files_tools.list_dir(fresh(), world.paths["projekt"]))
        missing_path = f"{root}/Fehlt"
        missing = await refusal(files_tools.list_dir(fresh(), missing_path))
        check(
            "SC1",
            "files_list",
            "getaggter Ordner wie fehlender Pfad",
            shape(tagged, (world.paths["projekt"], "<P>")) == shape(missing, (missing_path, "<P>"))
            and exact(tagged) == exact(dav.not_found(world.paths["projekt"])),
            f"{tagged.message!r} vs {missing.message!r}",
        )

        for key in ("geheim", "a", "b", "scan", "projekt"):
            hits = await files_tools.search(fresh(), world.name(key))
            check(
                "SC1",
                "files_search",
                f"{key} ohne Treffer",
                hits["count"] == 0 and not hits["items"] and "degraded" not in hits,
                f"term={world.name(key)} count={hits['count']}",
            )
        found = await files_tools.search(fresh(), world.name("offen"))
        check(
            "SC1",
            "files_search",
            "Gegenprobe offen gefunden",
            [item["path"] for item in found["items"]] == [world.paths["offen"]],
            f"items={[item['path'] for item in found['items']]}",
        )
        broad = await files_tools.search(fresh(), world.hexid)
        broad_names = {item["name"] for item in broad["items"]}
        check(
            "SC1",
            "files_search",
            "Laufkennung ohne getaggte Namen",
            world.name("offen") in broad_names and not broad_names & set(world.tagged_names()),
            f"names={sorted(broad_names)}",
        )


async def test_sc1_read_and_download(world: World) -> None:
    missing_path = f"{world.root}/erfunden-{world.hexid}.txt"
    async with live(world) as fresh:
        missing_read = await refusal(files_tools.read(fresh(), missing_path))
        missing_download = await refusal(files_tools.download(fresh(), missing_path))
        for key in ("geheim", "a", "b", "scan", "projekt"):
            path = world.paths[key]
            for tool, call, reference in (
                ("files_read", files_tools.read, missing_read),
                ("files_download", files_tools.download, missing_download),
            ):
                refused = await refusal(call(fresh(), path))
                check(
                    "SC1",
                    tool,
                    f"{key} wie erfundener Pfad",
                    shape(refused, (path, "<P>")) == shape(reference, (missing_path, "<P>"))
                    and exact(refused) == exact(dav.not_found(path))
                    and "not text" not in refused.message
                    and "is a folder" not in refused.message,
                    f"{refused.message!r}",
                )
        opened = await files_tools.read(fresh(), world.paths["offen"])
        check(
            "SC1",
            "files_read",
            "Gegenprobe offen liefert Inhalt",
            f"inhaltwort{world.hexid}" in opened["content"],
            f"content={opened['content'].strip()!r}",
        )


async def test_sc1_upload(world: World) -> None:
    missing_target = f"{world.root}/Fehlt/neu.txt"
    new_in_folder = f"{world.paths['projekt']}/neu.txt"
    async with live(world) as fresh:
        reference = await refusal(files_tools.upload(fresh(), missing_target, "x"))
        reference_shape = shape(reference, (missing_target, "<P>"), (f"{world.root}/Fehlt", "<D>"))
        for key, target in (("Projekt/neu.txt", new_in_folder), ("geheim", world.paths["geheim"])):
            refused = await refusal(files_tools.upload(fresh(), target, "x"))
            parent = target.rsplit("/", 1)[0]
            check(
                "SC1",
                "files_upload",
                f"{key} wie fehlender Elternordner",
                shape(refused, (target, "<P>"), (parent, "<D>")) == reference_shape
                and exact(refused) == exact(dav.parent_missing(target)),
                f"{refused.message!r}",
            )
    status_new = world.harness.stat(new_in_folder)[0]
    check(
        "SC1",
        "PROPFIND",
        "Projekt/neu.txt nicht geschrieben",
        status_new == 404,
        f"status={status_new}",
    )
    status, _, etag = world.harness.stat(world.paths["geheim"])
    check(
        "SC1",
        "PROPFIND",
        "geheim unverändert",
        status == 207 and etag == world.etags["geheim"],
        f"etag gleich={etag == world.etags['geheim']}",
    )


# --- success criterion 3: sandbox parity over comments, notes behind the guard ---------


def _wait_for_comments(world: World) -> int:
    """Wait until the comments provider indexes both comments (harness, no tool)."""
    entries: list[dict[str, Any]] = []
    for _ in range(ATTEMPTS):
        entries = world.harness.provider_entries("comments", world.comment_word)
        if len(entries) >= 2:
            break
        time.sleep(1)
    return len(entries)


async def test_sc3_comments_sandbox(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    raw_count = _wait_for_comments(world)
    inside = f"/f/{world.fileids['offen']}"
    outside = f"/f/{world.fileids['out']}"
    async with live(world) as fresh:
        monkeypatch.setenv(config.ENV_FILES_ROOT, world.root)
        bound = await search_tools.unified_search(
            fresh(), world.comment_word, providers=["comments"]
        )
        urls = [str(hit.get("url") or "") for hit in bound["results"]]
        check(
            "SC3",
            "unified_search",
            "comments ausserhalb der Root verschwindet und zählt",
            len(urls) == 1
            and urls[0].endswith(inside)
            and bound.get("skipped", 0) >= 1
            and outside not in dumps(bound),
            f"raw={raw_count} urls={urls} skipped={bound.get('skipped')}",
        )
        monkeypatch.delenv(config.ENV_FILES_ROOT)
        free = await search_tools.unified_search(
            fresh(), world.comment_word, providers=["comments"]
        )
        free_urls = sorted(str(hit.get("url") or "") for hit in free["results"])
        check(
            "SC3",
            "unified_search",
            "Gegenprobe comments ohne Root zeigt beide",
            len(free_urls) == 2 and "skipped" not in free,
            f"urls={free_urls}",
        )


async def test_sc3_notes(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    async with live(world) as fresh:
        monkeypatch.setenv(config.ENV_FILES_ROOT, world.root)
        bound = await notes_tools.search(fresh(), world.note_word)
        check(
            "SC3",
            "notes_search",
            "Notizen ausserhalb der Root verschwinden und zählen",
            bound["results"] == [] and bound.get("skipped", 0) >= 1,
            f"count={bound['count']} skipped={bound.get('skipped')}",
        )
        monkeypatch.delenv(config.ENV_FILES_ROOT)

        free = await notes_tools.search(fresh(), world.note_word)
        found = sorted(hit["id"] for hit in free["results"])
        check(
            "SC3",
            "notes_search",
            "nur die ungetaggte Notiz",
            found == [ids.encode_note(world.notes["offen_a"])]
            and "skipped" not in free
            and "geheim" not in dumps(free["results"]).lower(),
            f"ids={found}",
        )

        reference = await refusal(notes_tools.read(fresh(), UNKNOWN_FILEID))
        for key in ("geheim_b", "geheim_g"):
            note_id = world.notes[key]
            refused = await refusal(notes_tools.read(fresh(), note_id))
            check(
                "SC3",
                "notes_read",
                f"{key} wie unbekannte Id",
                shape(refused, (note_id, "<ID>")) == shape(reference, (UNKNOWN_FILEID, "<ID>")),
                f"{refused.message!r}",
            )
        opened = await notes_tools.read(fresh(), world.notes["offen_a"])
        check(
            "SC3",
            "notes_read",
            "Gegenprobe offene Notiz lesbar",
            world.note_word in opened["content"],
            f"title={opened['title']!r}",
        )

        title = f"Live27 neu {world.hexid}"
        candidate = f"{world.categories['geheim_path']}/{title}.md"
        before = world.harness.note_titles()
        refused = await refusal(
            notes_tools.create(fresh(), title, "x", category=world.categories["geheim"])
        )
        after = world.harness.note_titles()
        check(
            "SC3",
            "notes_create",
            "getaggte Kategorie wie fehlender Elternordner, nichts geschrieben",
            exact(refused) == exact(dav.parent_missing(candidate))
            and len(after) == len(before)
            and title not in after.values(),
            f"{refused.message!r} notes={len(before)}->{len(after)}",
        )


# --- success criterion 2: search, fetch by an old file id, systemtags, prepare_context ---

_DIGITS_AT_END = re.compile(r"(\d+)$")
_FILE_URL = re.compile(r"/f/(\d+)")


def _numbers_of(hit: dict[str, Any]) -> set[str]:
    """Every file or note id a normalised hit names, in its id and in its url."""
    found: set[str] = set()
    identifier = str(hit.get("id") or "")
    if identifier.startswith(("file:", "note:")) and (match := _DIGITS_AT_END.search(identifier)):
        found.add(match.group(1))
    found.update(_FILE_URL.findall(str(hit.get("url") or "")))
    return found


def _leaks(world: World, hits: list[dict[str, Any]]) -> list[str]:
    """The tagged ids among the hits, plus any hit text naming a tagged entry."""
    tagged = world.tagged_fileids()
    leaked = sorted({n for hit in hits for n in _numbers_of(hit)} & tagged)
    text = dumps(hits)
    leaked += [name for name in world.tagged_names() if name in text]
    leaked += [word for word in (f"geheimwort{world.hexid}", "Live27 geheim") if word in text]
    return leaked


def _bundle_hits(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    results = bundle.get("results")
    if not isinstance(results, dict):
        return []
    return [hit for group in results.values() if isinstance(group, list) for hit in group]


async def test_sc2_search_and_fetch(world: World) -> None:
    h = world.hexid
    async with live(world) as fresh:
        for label, term in (
            ("Laufkennung", h),
            ("geheim-Name", f"geheim-{h}"),
            ("Projekt-Name", f"Projekt-{h}"),
        ):
            answer = await search_tools.unified_search(fresh(), term)
            leaked = _leaks(world, answer["results"])
            providers = sorted({str(hit.get("provider")) for hit in answer["results"]})
            check(
                "SC2",
                "unified_search",
                f"{label} ohne getaggten Treffer",
                not leaked,
                f"count={answer['count']} providers={providers} leaks={leaked}",
            )
        visible = await search_tools.unified_search(fresh(), h)
        offen_seen = world.fileids["offen"] in {
            n for hit in visible["results"] for n in _numbers_of(hit)
        }
        check(
            "SC2",
            "unified_search",
            "Gegenprobe offen gefunden",
            offen_seen,
            f"count={visible['count']}",
        )

        for label, term in (("Laufkennung", h), ("geheim-Name", f"geheim-{h}")):
            hits = await chatgpt_tools.search(fresh(), term)
            leaked = _leaks(world, hits)
            check(
                "SC2",
                "chatgpt_search",
                f"{label} ohne getaggten Treffer",
                not leaked,
                f"count={len(hits)} leaks={leaked}",
            )

        vorher = world.fileids["vorher"]
        refused = await refusal(chatgpt_tools.fetch(fresh(), ids.encode_file(vorher)))
        reference = await refusal(chatgpt_tools.fetch(fresh(), ids.encode_file(UNKNOWN_FILEID)))
        check(
            "SC2",
            "fetch",
            "vor dem Taggen gelesene fileid danach wie unbekannte Id",
            bool(world.before_tag)
            and shape(refused, (vorher, "<ID>")) == shape(reference, (UNKNOWN_FILEID, "<ID>"))
            and f"vorherwort{h}" not in refused.message,
            f"vorher={len(world.before_tag)} Zeichen, danach {refused.message!r}",
        )

        raw_entries = world.harness.provider_entries("systemtags", TAG)
        raw_with_file = [
            e for e in raw_entries if isinstance(e.get("attributes"), dict) and e["attributes"]
        ]
        tags_answer = await search_tools.unified_search(fresh(), TAG, providers=["systemtags"])
        leaked = _leaks(world, tags_answer["results"])
        without_file = [hit for hit in tags_answer["results"] if not _numbers_of(hit)]
        check(
            "SC2",
            "unified_search",
            "systemtags-Provider nennt keine getaggte Datei",
            not leaked and "degraded" not in tags_answer,
            f"roh={len(raw_entries)} roh_mit_attributes={len(raw_with_file)} "
            f"antwort={tags_answer['count']} ohne_fileId={len(without_file)} leaks={leaked}",
        )

        bundle = await context_tools.prepare_context(fresh(), h, detail=context_tools.FULL)
        hits = _bundle_hits(bundle)
        excerpts = [str(hit.get("excerpt") or "") for hit in hits]
        text = dumps(bundle)
        check(
            "SC2",
            "prepare_context",
            "weder Treffer noch Ausschnitt noch Digest-Name getaggt",
            not _leaks(world, hits)
            and not any(f"geheimwort{h}" in excerpt for excerpt in excerpts)
            and f"geheim-{h}" not in text
            and f"geheimwort{h}" not in text,
            f"treffer={len(hits)} ausschnitte={sum(1 for e in excerpts if e)} "
            f"degraded={[d.get('source') for d in bundle.get('degraded', [])]}",
        )


# --- success criterion 4: Talk --------------------------------------------------------

INVENTED_TOKEN = "zz27nope"


async def _room_token(world: World) -> str:
    async with live(world) as fresh:
        clients = fresh()
        rooms = await talk_client.get_rooms(
            clients.client, clients.creds, include_last_message=False
        )
    for room in rooms:
        if str(room.get("displayName") or "") == world.talk_room:
            return str(room["token"])
    pytest.skip(f"the conversation {world.talk_room!r} does not exist for this account")


def _newest_placeholder(messages: dict[str, Any]) -> dict[str, Any] | None:
    placeholders = [m for m in messages["results"] if m.get("message") == "{file}"]
    return max(placeholders, key=lambda m: int(m["id"])) if placeholders else None


async def test_sc4_talk(world: World) -> None:
    harness = world.harness
    token = await _room_token(world)
    secret = world.name("geheim")
    share_ids: list[str] = []
    file_token = ""
    try:
        share_ids.append(harness.share(world.paths["geheim"], 10, token))
        async with live(world) as fresh:
            messages = await talk_tools.browse(fresh(), level="messages", token=token, limit=20)
            newest = _newest_placeholder(messages)
            text = dumps(messages)
            check(
                "SC4",
                "talk_browse",
                "messages zeigt die getaggte Freigabe nur als {file}",
                newest is not None and secret not in text and world.root not in text,
                f"platzhalter_id={newest and newest['id']} name_im_text={secret in text}",
            )
            conversations = await talk_tools.browse(
                fresh(), level="conversations", limit=talk_tools.MAX_LIMIT
            )
            room = [c for c in conversations["results"] if c.get("token") == token]
            check(
                "SC4",
                "talk_browse",
                "conversations last_message ohne den Namen",
                len(room) == 1 and secret not in dumps(room) and secret not in dumps(conversations),
                f"last_message={str(room[0].get('last_message') if room else None)[:80]!r}",
            )
            assert newest is not None
            fetched = await chatgpt_tools.fetch(fresh(), ids.encode_message(token, newest["id"]))
            check(
                "SC4",
                "fetch",
                "message ohne den Namen",
                "{file}" in str(fetched.get("text")) and secret not in dumps(fetched),
                f"text={str(fetched.get('text'))[:80]!r}",
            )

        share_ids.append(harness.share(world.paths["offen"], 10, token))
        async with live(world) as fresh:
            messages = await talk_tools.browse(fresh(), level="messages", token=token, limit=20)
            check(
                "SC4",
                "talk_browse",
                "Gegenprobe offene Freigabe zeigt den Namen",
                world.name("offen") in dumps(messages) and secret not in dumps(messages),
                f"offen_im_text={world.name('offen') in dumps(messages)}",
            )

        share_ids.append(harness.share(world.paths["geheim"], 0, world.user2))
        status, data = harness.ocs("GET", f"/apps/spreed/api/v1/file/{world.fileids['geheim']}")
        file_token = str((data or {}).get("token") or "") if isinstance(data, dict) else ""
        assert file_token, f"no file conversation: {status} {data}"
        harness.ocs("POST", f"/apps/spreed/api/v4/room/{file_token}/participants/active")
        harness.ocs("DELETE", f"/apps/spreed/api/v4/room/{file_token}/participants/active")
        _, raw_rooms = harness.ocs("GET", "/apps/spreed/api/v4/room")
        raw_tokens = [str(r.get("token")) for r in raw_rooms or [] if isinstance(r, dict)]
        async with live(world) as fresh:
            conversations = await talk_tools.browse(
                fresh(), level="conversations", limit=talk_tools.MAX_LIMIT
            )
            listed = dumps(conversations)
            check(
                "SC4",
                "talk_browse",
                "Datei-Raum fehlt in conversations",
                file_token in raw_tokens and file_token not in listed and secret not in listed,
                f"roh_in_liste={file_token in raw_tokens} antwort={file_token in listed}",
            )
            refused = await refusal(talk_tools.browse(fresh(), level="messages", token=file_token))
            reference = await refusal(
                talk_tools.browse(fresh(), level="messages", token=INVENTED_TOKEN)
            )
            check(
                "SC4",
                "talk_browse",
                "Datei-Raum messages wie erfundenes Token",
                shape(refused, (file_token, "<T>")) == shape(reference, (INVENTED_TOKEN, "<T>")),
                f"{shape(refused, (file_token, '<T>'))[1]!r}",
            )
    finally:
        if file_token:
            harness.ocs("DELETE", f"/apps/spreed/api/v4/room/{file_token}/participants/self")
        for share_id in share_ids:
            harness.unshare(share_id)
    _, left = harness.ocs("GET", "/apps/files_sharing/api/v1/shares")
    mine = [s for s in left or [] if isinstance(s, dict) and str(s.get("id")) in share_ids]
    _, rooms_after = harness.ocs("GET", "/apps/spreed/api/v4/room")
    still_in = file_token in [str(r.get("token")) for r in rooms_after or [] if isinstance(r, dict)]
    record(f"CLEANUP SC4 shares left: {len(mine)}, file conversation still listed: {still_in}")
    assert not mine, mine
    assert not still_in, "the file conversation is still in the list of this account"


# --- success criterion 5: degradation with an injected REPORT 500, silence on success ---


@contextmanager
def report_500(world: World) -> Iterator[respx.Route]:
    """Let the tag REPORT answer 500 and pass every other request through to nc35.

    Without a cached tag id the tag listing goes out first (passed through), then the
    REPORT (500), so the guard ends ``unverifiable`` exactly as on a broken instance.
    """
    home = systemtags_client.home_url(world.creds)
    with respx.mock(assert_all_called=False, assert_all_mocked=False) as router:
        failing = router.route(method="REPORT", url=home).mock(return_value=httpx.Response(500))
        router.route().pass_through()
        yield failing


_FILE_PROVIDERS = frozenset({"files", "comments", "notes", "systemtags"})


def _exclusion_entries(answer: dict[str, Any]) -> list[dict[str, Any]]:
    degraded = answer.get("degraded")
    if not isinstance(degraded, list):
        return []
    return [
        d
        for d in degraded
        if isinstance(d, dict) and d.get("reason") == withhold.EXCLUSION_UNAVAILABLE
    ]


async def test_sc5_unverifiable(world: World) -> None:
    h, harness = world.hexid, world.harness
    unavailable = exact(withhold.unavailable_error())
    one_source = [withhold.degraded_entry("source")]
    token = await _room_token(world)
    share_id = harness.share(world.paths["offen"], 10, token)
    try:
        with report_500(world) as failing:
            async with live(world) as fresh:
                listing = await files_tools.list_dir(fresh(), world.root)
                check(
                    "SC5",
                    "files_list",
                    "leer mit genau einem degraded-Eintrag",
                    listing["items"] == [] and listing.get("degraded") == one_source,
                    f"items={len(listing['items'])} degraded={listing.get('degraded')}",
                )

                opened = await refusal(files_tools.read(fresh(), world.paths["offen"]))
                invented = await refusal(files_tools.read(fresh(), f"{world.root}/erfunden.txt"))
                check(
                    "SC5",
                    "files_read",
                    "offen und erfundener Pfad identisch uniform",
                    exact(opened) == exact(invented) == unavailable,
                    f"{opened.message!r}",
                )

                target = f"{world.root}/neu-sc5-{h}.txt"
                refused = await refusal(files_tools.upload(fresh(), target, "x"))
                written = harness.stat(target)[0]
                check(
                    "SC5",
                    "files_upload",
                    "uniformer Fehler, nichts geschrieben",
                    exact(refused) == unavailable and written == 404,
                    f"{refused.message!r} PROPFIND={written}",
                )

                searched = await search_tools.unified_search(fresh(), h)
                file_hits = [
                    hit for hit in searched["results"] if hit.get("provider") in _FILE_PROVIDERS
                ]
                check(
                    "SC5",
                    "unified_search",
                    "keine dateitragenden Treffer, ein exclusion-degraded",
                    not file_hits
                    and _exclusion_entries(searched) == [withhold.degraded_entry("provider")],
                    f"treffer={searched['count']} datei={len(file_hits)} "
                    f"degraded={[d.get('provider') for d in searched.get('degraded', [])]}",
                )

                notes = await notes_tools.search(fresh(), world.note_word)
                check(
                    "SC5",
                    "notes_search",
                    "leer mit genau einem degraded-Eintrag",
                    notes["results"] == [] and notes.get("degraded") == one_source,
                    f"count={notes['count']} degraded={notes.get('degraded')}",
                )

                messages = await talk_tools.browse(fresh(), level="messages", token=token, limit=20)
                check(
                    "SC5",
                    "talk_browse",
                    "alle Dateien roh als {file}, ein degraded-Eintrag",
                    _newest_placeholder(messages) is not None
                    and world.name("offen") not in dumps(messages)
                    and messages.get("degraded") == one_source,
                    f"degraded={messages.get('degraded')}",
                )

                fetched = await refusal(
                    chatgpt_tools.fetch(fresh(), ids.encode_file(world.fileids["offen"]))
                )
                check(
                    "SC5",
                    "fetch",
                    "file offen uniformer Fehler",
                    exact(fetched) == unavailable,
                    f"{fetched.message!r}",
                )

                bundle = await context_tools.prepare_context(fresh(), h, detail=context_tools.FULL)
                entries = _exclusion_entries(bundle)
                check(
                    "SC5",
                    "prepare_context",
                    "genau ein degraded-Eintrag EXCLUSION_UNAVAILABLE",
                    entries == one_source and not _leaks(world, _bundle_hits(bundle)),
                    f"exclusion={len(entries)} "
                    f"degraded={[d.get('source') for d in bundle.get('degraded', [])]}",
                )
            record(f"# SC5 injected REPORT 500 answered {failing.call_count} times")
    finally:
        harness.unshare(share_id)


_TELLTALE_KEYS = frozenset({"withheld", "excluded", "hidden", "exclusion"})


def _keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return {str(k) for k in value} | {k for v in value.values() for k in _keys(v)}
    if isinstance(value, list):
        return {k for v in value for k in _keys(v)}
    return set()


async def test_sc5_silence_on_success(world: World) -> None:
    h = world.hexid
    token = await _room_token(world)
    share_id = world.harness.share(world.paths["geheim"], 10, token)
    answers: dict[str, Any] = {}
    try:
        async with live(world) as fresh:
            answers["files_list"] = await files_tools.list_dir(fresh(), world.root)
            answers["files_search"] = await files_tools.search(fresh(), h)
            answers["files_read"] = await files_tools.read(fresh(), world.paths["offen"])
            answers["files_download"] = await files_tools.download(fresh(), world.paths["offen"])
            answers["unified_search"] = await search_tools.unified_search(fresh(), h)
            answers["systemtags"] = await search_tools.unified_search(
                fresh(), TAG, providers=["systemtags"]
            )
            answers["chatgpt_search"] = await chatgpt_tools.search(fresh(), h)
            answers["fetch_file"] = await chatgpt_tools.fetch(
                fresh(), ids.encode_file(world.fileids["offen"])
            )
            answers["notes_search"] = await notes_tools.search(fresh(), world.note_word)
            answers["notes_read"] = await notes_tools.read(fresh(), world.notes["offen_a"])
            messages = await talk_tools.browse(fresh(), level="messages", token=token, limit=20)
            answers["talk_messages"] = messages
            answers["talk_conversations"] = await talk_tools.browse(
                fresh(), level="conversations", limit=talk_tools.MAX_LIMIT
            )
            newest = _newest_placeholder(messages)
            assert newest is not None, "the tagged share is not in the window"
            answers["fetch_message"] = await chatgpt_tools.fetch(
                fresh(), ids.encode_message(token, newest["id"])
            )
            answers["prepare_context"] = await context_tools.prepare_context(
                fresh(), h, detail=context_tools.FULL
            )
    finally:
        world.harness.unshare(share_id)

    loud: dict[str, list[str]] = {}
    for name, answer in answers.items():
        found = sorted(_keys(answer) & _TELLTALE_KEYS)
        if withhold.EXCLUSION_UNAVAILABLE in dumps(answer):
            found.append("EXCLUSION_UNAVAILABLE")
        if found:
            loud[name] = found
    check(
        "SC5",
        "alle Werkzeuge",
        "Schweigen im Erfolgsfall",
        not loud,
        f"{len(answers)} Antworten ohne Zähler/Hinweis, laut={loud}",
    )


# --- A1: cost of the file id resolution -------------------------------------------------


async def test_a1_paths_of_fileids_latency(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    """Median and maximum of ``dav.paths_of_fileids`` for 1, 25 and 50 ids (a measurement)."""
    monkeypatch.delenv(config.ENV_FILES_ROOT, raising=False)
    folder = f"{world.root}/A1"
    world.harness.mkcol(folder)
    fileids: list[str] = []
    for index in range(50):
        path = f"{folder}/f{index:02d}-{world.hexid}.txt"
        world.harness.put(path, f"a1 {index}\n".encode())
        fileids.append(world.harness.fileid(path))
    async with httpx.AsyncClient(follow_redirects=False, timeout=30.0) as client:
        for count in (1, 25, 50):
            wanted = fileids[:count]
            await dav.paths_of_fileids(client, world.creds, wanted)
            samples: list[float] = []
            for _ in range(5):
                started = time.perf_counter()
                found = await dav.paths_of_fileids(client, world.creds, wanted)
                samples.append((time.perf_counter() - started) * 1000)
                assert len(found) == count, f"n={count}: {len(found)} resolved"
            record(
                f"A1 paths_of_fileids n={count}: median={statistics.median(samples):.1f} "
                f"max={max(samples):.1f} (ms, 5 runs after 1 warm-up)"
            )
