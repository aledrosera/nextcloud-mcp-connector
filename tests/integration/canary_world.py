"""Live harness of phase 28; a helper module, not a test module.

The measurements of plan 28-01, the canary of plan 28-10 and the live pairs of plan 28-11 all
need the same scaffolding against a running Nextcloud: WebDAV and OCS writes as the test
account, a Tables table with a link column, ``kein-ki`` tagging through ``occ``, a tool call
through the in-memory ``Client(mcp)`` exactly as a client makes it, an injected outage of the
tag REPORT, and a cleanup that reads every removal back instead of trusting it.

Why a module and not ``conftest.py``: a fixture in ``tests/integration/conftest.py`` would
reach every integration test, including the ones of the CI job that has no ExApp topology,
and the helpers here reach into a container. This module is imported by name;
``pyproject.toml`` puts ``tests/integration`` on the import path for it.

``occ`` runs in :data:`topology.NC_CONTAINER` and nowhere else. The live module of plan 27-07
spelled its container out, which is the trap ``topology.py`` describes: a run against another
topology would tag one instance and assert against a second one.

Nothing here logs a header, a password or an environment value; :func:`record` only ever
receives tool results and raw answers of the instance (T-28-04).
"""

import contextlib
import dataclasses
import json
import os
import shutil
import subprocess
import uuid
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx
import pytest
import respx
import topology
from lxml import etree
from mcp import Client
from mcp.types import CallToolResult

from mcp_connector.config import normalize_base_url
from mcp_connector.nextcloud import capabilities, exclusion
from mcp_connector.nextcloud.clients import dav
from mcp_connector.nextcloud.clients import systemtags as systemtags_client
from mcp_connector.nextcloud.clients import tables as tables_client
from mcp_connector.nextcloud.credentials import Credentials
from mcp_connector.server import mcp

__all__ = [
    "RAW_DIR",
    "TAG",
    "Cleanup",
    "Harness",
    "LiveEnv",
    "call",
    "check",
    "credentials",
    "ensure_tag",
    "fresh_guard",
    "guard_outage",
    "live_env",
    "mcp_env",
    "occ",
    "record",
    "run_id",
    "tag",
    "tag_ids",
    "untag",
]

RAW_DIR = (
    Path(__file__).resolve().parents[2] / ".planning" / "phases" / "28-gates-und-beweise" / "raw"
)
TAG = exclusion.EXCLUDE_TAG
REQUIRED_ENV = ("NC_MCP_URL", "NC_MCP_TEST_USER", "NC_MCP_TEST_APP_PASSWORD")

_DAV = "{DAV:}"
_OC = "{http://owncloud.org/ns}"
_PROPFIND = (
    b'<?xml version="1.0"?><d:propfind xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns">'
    b"<d:prop><oc:fileid/><d:getetag/></d:prop></d:propfind>"
)
_OCS_HEADERS = {"OCS-APIRequest": "true", "Accept": "application/json"}


# --- protocol -------------------------------------------------------------------------


def record(raw: Path, line: str) -> None:
    """Append one line to a raw protocol."""
    raw.parent.mkdir(parents=True, exist_ok=True)
    with raw.open("a", encoding="utf-8") as fh:
        fh.write(line.rstrip("\n") + "\n")


def short(value: str, limit: int = 240) -> str:
    """``value`` cut to ``limit`` characters, marked when it was cut."""
    return value if len(value) <= limit else value[: limit - 3] + "..."


def check(raw: Path, criterion: str, tool: str, case: str, ok: bool, raw_value: str) -> None:
    """Record ``<criterion> <tool> <case>: <ja|nein> (<raw>)`` first, then assert ``ok``."""
    cut = short(raw_value)
    record(raw, f"{criterion} {tool} {case}: {'ja' if ok else 'nein'} ({cut})")
    assert ok, f"{criterion} {tool} {case}: {cut}"


# --- environment ----------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class LiveEnv:
    """The account a live run acts as, read from the environment once."""

    url: str
    user: str
    app_password: str
    user2: str | None = None


def live_env() -> LiveEnv:
    """The live account, or a skip naming what is missing.

    The CI job ``integration`` has no ExApp variables and no container of this name, so every
    test built on this skips there instead of failing.
    """
    values = {name: (os.environ.get(name) or "").strip() for name in REQUIRED_ENV}
    missing = [name for name, value in values.items() if not value]
    if missing:
        pytest.skip(f"no live run configured (missing: {', '.join(missing)})")
    assert values["NC_MCP_TEST_USER"] != "admin", "the live run acts as a normal user"
    if shutil.which("docker") is None:
        pytest.skip("docker is not on PATH, occ cannot tag")
    probe = subprocess.run(  # noqa: S603 - fixed argv, test harness
        ["docker", "inspect", "-f", "{{.State.Running}}", topology.NC_CONTAINER],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    if probe.returncode != 0 or "true" not in probe.stdout:
        pytest.skip(f"the container {topology.NC_CONTAINER} is not running")
    return LiveEnv(
        url=normalize_base_url(values["NC_MCP_URL"]),
        user=values["NC_MCP_TEST_USER"],
        app_password=values["NC_MCP_TEST_APP_PASSWORD"],
        user2=(os.environ.get("NC_MCP_TEST_USER2") or "").strip() or None,
    )


def credentials(env: LiveEnv) -> Credentials:
    return Credentials(base_url=env.url, user=env.user, secret=env.app_password)


def mcp_env(monkeypatch: pytest.MonkeyPatch, env: LiveEnv) -> None:
    """The environment an in-memory client call resolves its credentials from."""
    monkeypatch.setenv("NC_MCP_URL", env.url)
    monkeypatch.setenv("NC_MCP_USER", env.user)
    monkeypatch.setenv("NC_MCP_APP_PASSWORD", env.app_password)
    monkeypatch.delenv("NC_MCP_STATIC_BEARER", raising=False)


# --- occ and tagging ------------------------------------------------------------------


def occ(*argv: str, check_status: bool = True) -> str:
    """One ``occ`` call inside :data:`topology.NC_CONTAINER` (harness only, EXCL-07)."""
    finished = subprocess.run(  # noqa: S603 - fixed argv, test harness
        ["docker", "exec", "-u", "www-data", topology.NC_CONTAINER, "php", "occ", *argv],  # noqa: S607
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
    return [tag_id for tag_id, tag_name in items if exclusion.is_exclude_name(tag_name)]


def ensure_tag() -> tuple[str, bool]:
    """``(id, created)`` of the ``kein-ki`` tag; created by this run when it was missing."""
    existing = tag_ids()
    if existing:
        return existing[0], False
    output = occ("tag:add", TAG, "public", "--output=json")
    start = output.find("{")
    created = json.loads(output[start:]) if start >= 0 else {}
    tag_id = str(created.get("id") or "")
    assert tag_id.isdigit(), f"occ tag:add gave no id: {output[:200]}"
    return tag_id, True


def tag(fileid: str) -> None:
    """Tag one node by its file id; the id form is the one the 27-07 run measured."""
    occ("tag:files:add", fileid, TAG, "public")


def untag(fileid: str) -> None:
    occ("tag:files:delete", fileid, TAG, "public", check_status=False)


# --- harness --------------------------------------------------------------------------


class Harness:
    """Synchronous writes of the test data as the test account, never through the tools."""

    def __init__(self, env: LiveEnv) -> None:
        self.base_url = env.url
        self.user = env.user
        self.http = httpx.Client(
            auth=(env.user, env.app_password), timeout=60.0, follow_redirects=False
        )

    def close(self) -> None:
        self.http.close()

    def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """One request with the app password alone, never with a session cookie.

        Measured on nc35 in plan 27-07: a session cookie set by an app API turned every later
        WebDAV request of the same client into a 401, so a cleanup deleted nothing.
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

    def delete(self, path: str) -> int:
        return self.request("DELETE", self.dav_url(path)).status_code

    def stat_url(self, url: str) -> tuple[int, str]:
        """(status, fileid) of one WebDAV URL; the status alone when it is not a 207."""
        response = self.request(
            "PROPFIND",
            url,
            headers={"Depth": "0", "Content-Type": "application/xml"},
            content=_PROPFIND,
        )
        if response.status_code != 207:
            return response.status_code, ""
        tree = etree.fromstring(response.content)
        return 207, (tree.findtext(f".//{_OC}fileid") or "").strip()

    def stat(self, path: str) -> tuple[int, str]:
        """(status, fileid) of one entry below the home; status 404 for a missing one."""
        return self.stat_url(self.dav_url(path))

    def fileid(self, path: str) -> str:
        status, fileid = self.stat(path)
        assert status == 207, f"no entry at {path}: {status}"
        assert fileid, f"no fileid for {path}"
        return fileid

    def search_raw(self, scope: str, term: str, limit: int = 10) -> httpx.Response:
        """The SEARCH ``dav.search`` sends, with the body it builds, answered raw."""
        return self.request(
            "SEARCH",
            f"{self.base_url}{dav.DAV_ROOT_PATH}",
            headers={"Content-Type": "text/xml"},
            content=dav.build_search_body(scope, term, limit),
        )

    def _ocs(self, method: str, path: str, body: dict[str, Any] | None = None) -> httpx.Response:
        return self.request(
            method, f"{self.base_url}/ocs/v2.php{path}", headers=_OCS_HEADERS, json=body
        )

    def ocs_get(self, path: str) -> httpx.Response:
        return self._ocs("GET", path)

    def ocs_post(self, path: str, body: dict[str, Any]) -> httpx.Response:
        return self._ocs("POST", path, body)

    def ocs_delete(self, path: str) -> httpx.Response:
        return self._ocs("DELETE", path)

    @staticmethod
    def ocs_data(response: httpx.Response, what: str) -> Any:
        assert response.status_code < 300, f"{what}: {response.status_code} {response.text[:300]}"
        return response.json()["ocs"]["data"]

    # Tables: scaffolding only, the connector itself never creates a table or a column.

    def create_table(self, title: str) -> str:
        response = self.ocs_post(
            f"{tables_client.V2_PREFIX}/tables", {"title": title, "template": "custom"}
        )
        return str(self.ocs_data(response, f"create table {title}")["id"])

    def create_link_column(self, table_id: str, title: str) -> str:
        """A text column of subtype ``link`` with the ``files`` provider allowed.

        ``textAllowedPattern`` is where the Tables column form stores the allowed link
        providers, comma separated; ``subtype`` is load bearing (``TextLinkBusiness``).
        """
        response = self.ocs_post(
            f"{tables_client.V2_PREFIX}/columns/text",
            {
                "baseNodeId": int(table_id),
                "baseNodeType": "table",
                "title": title,
                "subtype": "link",
                "textAllowedPattern": "url,files",
            },
        )
        return str(self.ocs_data(response, f"create link column {title}")["id"])

    def create_row(self, table_id: str, data: dict[str, Any]) -> dict[str, Any]:
        response = self.ocs_post(
            f"{tables_client.V2_PREFIX}/{tables_client.NODE_COLLECTION_TABLES}/{table_id}/rows",
            {"data": data},
        )
        return self.ocs_data(response, f"create row in table {table_id}")

    def rows_simple_raw(self, table_id: str) -> tuple[int, str]:
        response = self.request(
            "GET",
            f"{self.base_url}{tables_client.V1_PREFIX}/tables/{table_id}/rows/simple",
            params={"limit": 50, "offset": 0},
            headers=dict(tables_client.TABLES_HEADERS),
        )
        return response.status_code, response.text

    def table_status(self, table_id: str) -> int:
        response = self.request(
            "GET",
            f"{self.base_url}{tables_client.V1_PREFIX}/tables/{table_id}",
            headers=dict(tables_client.TABLES_HEADERS),
        )
        return response.status_code

    def delete_table(self, table_id: str) -> int:
        response = self.request(
            "DELETE",
            f"{self.base_url}{tables_client.V1_PREFIX}/tables/{table_id}",
            headers=dict(tables_client.TABLES_HEADERS),
        )
        return response.status_code


# --- cleanup --------------------------------------------------------------------------


@dataclasses.dataclass
class _Step:
    what: str
    undo: Callable[[], object]
    read: Callable[[], str]


class Cleanup:
    """Every side effect of a run with the call that removes it and the call that proves it.

    :meth:`run` removes in reverse order of registration and reads every raw value back
    afterwards, so a line says what the instance answers now and never what the harness
    intended. A failing removal does not stop the others.
    """

    def __init__(self) -> None:
        self.steps: list[_Step] = []

    def add(self, what: str, undo: Callable[[], object], read: Callable[[], str]) -> None:
        self.steps.append(_Step(what, undo, read))

    def add_path(self, harness: Harness, path: str) -> None:
        self.add(
            f"PROPFIND {path}", lambda: harness.delete(path), lambda: str(harness.stat(path)[0])
        )

    def add_upload(self, harness: Harness, label: str, url: str) -> None:
        def undo() -> object:
            status, _ = harness.stat_url(url)
            return harness.request("DELETE", url).status_code if status == 207 else status

        self.add(f"uploads/{label}", undo, lambda: str(harness.stat_url(url)[0]))

    def add_table(self, harness: Harness, table_id: str) -> None:
        self.add(
            f"table {table_id}",
            lambda: harness.delete_table(table_id),
            lambda: str(harness.table_status(table_id)),
        )

    def add_tag(self, tag_id: str, created: bool, fileids: list[str]) -> None:
        """A created tag is deleted; a tag that existed keeps living, without our nodes."""
        if created:
            self.add(
                f"tag {TAG}",
                lambda: occ("tag:delete", tag_id, check_status=False),
                lambda: "entfernt" if not tag_ids() else f"noch da {tag_ids()}",
            )
            return

        def undo() -> object:
            for fileid in fileids:
                untag(fileid)
            return None

        self.add(f"tag {TAG}", undo, lambda: "vorbestehend")

    def run(self) -> list[str]:
        for step in reversed(self.steps):
            with contextlib.suppress(Exception):
                step.undo()
        lines: list[str] = []
        for step in self.steps:
            try:
                value = step.read()
            except Exception as exc:
                value = f"lesefehler {type(exc).__name__}"
            lines.append(f"CLEANUP {step.what}: {value}")
        return lines


def cleanup_ok(line: str) -> bool:
    return line.endswith((": 404", ": entfernt", ": vorbestehend"))


# --- tool calls -----------------------------------------------------------------------


async def call(tool: str, args: dict[str, Any]) -> CallToolResult:
    """One tool call through the in-memory client, exactly as a client makes it.

    Errors are not raised into the caller: a tool error comes back as ``isError`` with its
    text, which is the form a model sees and therefore the form every comparison of phase 28
    is about.
    """
    async with Client(mcp) as client:
        return await client.call_tool(tool, args)


def dump(result: CallToolResult) -> dict[str, Any]:
    return result.model_dump(mode="json", by_alias=True, exclude_none=True)


def fresh_guard() -> None:
    """Forget cached tag ids and capabilities, so a call sees the tag state of now."""
    exclusion.clear_cache()
    capabilities.clear_cache()


@contextlib.contextmanager
def guard_outage(env: LiveEnv, mode: str) -> Iterator[respx.Route]:
    """Let the tag REPORT fail in ``mode`` and pass every other request through.

    ``mode`` is ``"500"``, ``"412"`` or ``"timeout"``. The route is yielded, so the caller can
    record ``call_count`` and prove the outage was actually hit.
    """
    home = systemtags_client.home_url(credentials(env))
    with respx.mock(assert_all_called=False, assert_all_mocked=False) as router:
        route = router.route(method="REPORT", url=home)
        if mode == "500":
            route.mock(return_value=httpx.Response(500))
        elif mode == "412":
            route.mock(return_value=httpx.Response(412))
        elif mode == "timeout":
            route.mock(side_effect=httpx.ReadTimeout("injected by guard_outage"))
        else:
            raise ValueError(f"unknown outage mode {mode!r}")
        router.route().pass_through()
        yield route


def run_id() -> tuple[str, str]:
    """``(stem, marker)`` of one run: lower case ASCII letters and digits only (pitfall 5)."""
    return f"kanarie28x{uuid.uuid4().hex[:8]}", f"mk{uuid.uuid4().hex}"
