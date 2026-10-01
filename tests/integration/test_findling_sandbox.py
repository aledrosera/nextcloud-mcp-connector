"""Findling hits that carry only a file id, through the sandbox and the exclusion (SBX-01).

Findling answers from the inside of documents, and its entries carry a ``fileId`` in their
attributes instead of a path. Those are exactly the hits the sandbox check of phase 27 has to
resolve before it can decide them: a hit whose file lies outside ``NC_MCP_FILES_ROOT``, or
whose file is tagged ``kein-ki``, has to disappear from ``unified_search`` together with its
excerpt, although nothing in the hit itself names a path (T-27-70).

The steps, in one test because the indexed state is expensive to build and the order is the
argument:

1. alice uploads two documents, one under ``/findling27-in-<hex>/`` and one under
   ``/findling27-out-<hex>/``, each with its own marker that exists only in the content.
2. The background jobs are driven until Findling answers both markers without a root
   (positive control: without it, every empty answer below would also pass on a broken index).
3. With ``NC_MCP_FILES_ROOT`` on the in-folder: the out-marker finds nothing and counts at
   least one ``skipped``; the in-marker still finds its document (the counter-check).
4. Without a root, the in-document is tagged ``kein-ki`` by ``occ`` (the harness only; ``src/``
   never writes a tag, EXCL-07): the in-marker finds nothing, and ``skipped`` is unchanged
   against the counter-check of step 3, because a ``kein-ki`` drop leaves no trace.

Everything is removed in a ``finally``: both folders and, when this run created it, the tag.

The file skips, with the reason named, when the ``findling`` provider is missing on the test
instance, so a local run without Findling is a skip and never a faked green. CI installs
Findling in the exapp job (``scripts/install_findling.sh``) and runs this file right after the
content-hit fidelity step::

    set -a && . ./.env.exapp && set +a
    uv run pytest tests/integration/test_findling_sandbox.py -m integration
"""

import dataclasses
import json
import os
import shutil
import subprocess
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import quote

import anyio
import httpx
import pytest
from lxml import etree
from topology import COMPOSE

from mcp_connector import config
from mcp_connector.config import normalize_base_url
from mcp_connector.nextcloud import NcClients, capabilities
from mcp_connector.nextcloud import exclusion as exclusion_core
from mcp_connector.nextcloud.clients import ocs
from mcp_connector.nextcloud.credentials import Credentials
from mcp_connector.nextcloud.exclusion import ExclusionGuard
from mcp_connector.tools import search as search_tools

pytestmark = [pytest.mark.integration, pytest.mark.anyio]

#: Findling's provider id, from its PHP half (SearchProvider::getId), as in
#: ``test_content_hit_fidelity.py``.
FINDLING_PROVIDER = "findling"

#: How long indexing may take; the same budget and the same variable as the fidelity file.
INDEX_DEADLINE_SECONDS = float(os.environ.get("NC_MCP_FINDLING_DEADLINE") or "300")
_POLL_PAUSE_SECONDS = 5.0

TAG = exclusion_core.EXCLUDE_TAG


def occ(*argv: str, check_status: bool = True) -> str:
    """One ``occ`` call through compose, the way the CI job addresses its Nextcloud."""
    finished = subprocess.run(  # noqa: S603 - fixed argv, test harness
        [*COMPOSE, "exec", "-T", "--user", "www-data", "nextcloud", "php", "occ", *argv],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    output = ((finished.stdout or "") + (finished.stderr or "")).replace("\r", "").strip()
    if check_status and finished.returncode != 0:
        raise AssertionError(f"occ {' '.join(argv)} failed: {output[:300]}")
    return output


def exclude_tag_ids() -> list[str]:
    """The ids of every tag ``occ tag:list`` knows under a spelling of ``kein-ki``."""
    output = occ("tag:list", "--output=json", check_status=False)
    start = min((i for i in (output.find("{"), output.find("[")) if i >= 0), default=-1)
    try:
        data = json.loads(output[start:]) if start >= 0 else []
    except json.JSONDecodeError:
        return []
    items: list[tuple[str, str]] = []
    if isinstance(data, dict):
        items = [(str(k), str(v.get("name", ""))) for k, v in data.items() if isinstance(v, dict)]
    elif isinstance(data, list):
        items = [
            (str(v.get("id", "")), str(v.get("name", ""))) for v in data if isinstance(v, dict)
        ]
    return [tag_id for tag_id, name in items if exclusion_core.is_exclude_name(name)]


def _env() -> dict[str, str]:
    required = {
        "base": "NC_MCP_URL",
        "alice": "NC_MCP_TEST_USER",
        "alice_pw": "NC_MCP_TEST_APP_PASSWORD",
    }
    values = {key: (os.environ.get(name) or "").strip() for key, name in required.items()}
    missing = sorted(required[key] for key, value in values.items() if not value)
    if missing:
        pytest.skip(f"no ExApp topology configured (missing: {', '.join(missing)})")
    assert values["alice"] != "admin", "the sandbox test runs as a normal user, never as admin"
    return values


@asynccontextmanager
async def _clients(creds: Credentials) -> AsyncIterator[NcClients]:
    capabilities.clear_cache()
    async with httpx.AsyncClient(follow_redirects=False, timeout=60.0) as client:
        yield NcClients(client=client, creds=creds)


def fresh(clients: NcClients) -> NcClients:
    """One guard per tool call, as in production (Pattern 7)."""
    return dataclasses.replace(clients, exclusion=ExclusionGuard())


async def _findling(clients: NcClients, marker: str) -> dict[str, Any]:
    return await search_tools.unified_search(fresh(clients), marker, providers=[FINDLING_PROVIDER])


def _beyond_query(answer: dict[str, Any]) -> str:
    """The serialised answer without the echo of the query, which carries the marker itself."""
    return json.dumps(
        {key: value for key, value in answer.items() if key != "query"},
        ensure_ascii=False,
        default=str,
    )


def _findling_degradation(answer: dict[str, Any]) -> str | None:
    for entry in answer.get("degraded") or []:
        if entry.get("provider") == FINDLING_PROVIDER:
            return str(entry.get("reason") or "an unnamed degradation")
    return None


class Harness:
    """Synchronous writes of alice's test data with her app password, never a session cookie."""

    def __init__(self, base: str, user: str, password: str) -> None:
        self.base = base
        self.user = user
        self.http = httpx.Client(auth=(user, password), timeout=30.0, follow_redirects=False)

    def request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        self.http.cookies.clear()
        url = f"{self.base}/remote.php/dav/files/{quote(self.user)}{quote(path)}"
        return self.http.request(method, url, **kwargs)

    def fileid(self, path: str) -> str:
        response = self.request(
            "PROPFIND",
            path,
            headers={"Depth": "0", "Content-Type": "application/xml"},
            content=(
                b'<?xml version="1.0"?><d:propfind xmlns:d="DAV:" '
                b'xmlns:oc="http://owncloud.org/ns"><d:prop><oc:fileid/></d:prop></d:propfind>'
            ),
        )
        assert response.status_code == 207, f"PROPFIND {path}: {response.status_code}"
        fileid = etree.fromstring(response.content).findtext(".//{http://owncloud.org/ns}fileid")
        assert fileid, f"no fileid for {path}"
        return fileid.strip()

    def status(self, path: str) -> int:
        return self.request("PROPFIND", path, headers={"Depth": "0"}).status_code

    def drive_cron(self) -> None:
        """One round of background jobs, the way webcron drives them (Findling indexes there)."""
        answer = httpx.get(f"{self.base}/cron.php", timeout=120.0)
        assert answer.status_code == 200, (
            f"the cron endpoint answered {answer.status_code}; without background jobs "
            "Findling never indexes and this test would time out for the wrong reason"
        )


async def test_findling_hits_run_through_sandbox_and_exclusion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SBX-01: a fileId-only Findling hit outside the root or tagged kein-ki disappears."""
    values = _env()
    creds = Credentials(
        base_url=normalize_base_url(values["base"]),
        user=values["alice"],
        secret=values["alice_pw"],
    )
    monkeypatch.delenv(config.ENV_FILES_ROOT, raising=False)

    # Skip guard before any content exists: a missing provider is a topology property.
    async with _clients(creds) as clients:
        providers = await ocs.list_search_providers(clients.client, clients.creds)
    if FINDLING_PROVIDER not in {str(p.get("id")) for p in providers}:
        pytest.skip(
            f"the {FINDLING_PROVIDER} provider is not installed on this instance; "
            "CI installs it with scripts/install_findling.sh"
        )
    if shutil.which("docker") is None:
        pytest.skip("docker is not on PATH, occ cannot tag")

    hexid = uuid.uuid4().hex[:8]
    inside, outside = f"/findling27-in-{hexid}", f"/findling27-out-{hexid}"
    in_marker, out_marker = f"innenmarker{hexid}", f"aussenmarker{hexid}"
    in_file, out_file = f"{inside}/protokoll-{hexid}.md", f"{outside}/protokoll-{hexid}.md"
    for path in (in_file, out_file):
        assert in_marker not in path, "a marker leaked into a name"
        assert out_marker not in path, "a marker leaked into a name"

    harness = Harness(creds.base_url, creds.user, values["alice_pw"])
    created_tag: str | None = None
    tagged: str | None = None
    try:
        for folder, path, marker in ((inside, in_file, in_marker), (outside, out_file, out_marker)):
            assert harness.request("MKCOL", folder).status_code == 201, folder
            body = f"Protokoll.\n\nDer Inhalt traegt die Kennung {marker}.\n".encode()
            assert harness.request("PUT", path, content=body).status_code in (201, 204), path

        # Positive control: both markers reach alice without a root.
        async with _clients(creds) as clients:
            for marker in (in_marker, out_marker):
                deadline = time.monotonic() + INDEX_DEADLINE_SECONDS
                while True:
                    harness.drive_cron()
                    answer = await _findling(clients, marker)
                    assert _findling_degradation(answer) is None, answer
                    if answer["count"] >= 1:
                        break
                    if time.monotonic() >= deadline:
                        pytest.fail(
                            f"the content hit for {marker} did not arrive within "
                            f"{INDEX_DEADLINE_SECONDS:g}s; last answer: {answer!r}"
                        )
                    await anyio.sleep(_POLL_PAUSE_SECONDS)

        # (1) The sandbox: the out-document vanishes, the in-document stays.
        monkeypatch.setenv(config.ENV_FILES_ROOT, inside)
        async with _clients(creds) as clients:
            out_answer = await _findling(clients, out_marker)
            in_answer = await _findling(clients, in_marker)
        assert _findling_degradation(out_answer) is None, out_answer
        assert out_answer["results"] == [], f"a hit outside the root survived: {out_answer!r}"
        assert out_answer.get("skipped", 0) >= 1, (
            f"the sandbox drop was not counted: {out_answer!r}"
        )
        assert out_marker not in _beyond_query(out_answer), out_answer
        assert in_answer["count"] >= 1, f"the counter-check inside the root failed: {in_answer!r}"
        baseline_skipped = in_answer.get("skipped", 0)

        # (2) The exclusion: without a root, the tagged in-document vanishes silently.
        monkeypatch.delenv(config.ENV_FILES_ROOT, raising=False)
        if not exclude_tag_ids():
            output = occ("tag:add", TAG, "public", "--output=json")
            start = output.find("{")
            created_tag = str((json.loads(output[start:]) if start >= 0 else {}).get("id") or "")
            assert created_tag.isdigit(), f"occ tag:add gave no id: {output[:200]}"
        tagged = harness.fileid(in_file)
        occ("tag:files:add", tagged, TAG, "public")
        exclusion_core.clear_cache()
        async with _clients(creds) as clients:
            tagged_answer = await _findling(clients, in_marker)
        assert _findling_degradation(tagged_answer) is None, tagged_answer
        assert tagged_answer["results"] == [], f"a tagged hit survived: {tagged_answer!r}"
        assert in_marker not in _beyond_query(tagged_answer), tagged_answer
        assert tagged_answer.get("skipped", 0) == baseline_skipped, (
            f"a kein-ki drop changed skipped ({baseline_skipped} -> "
            f"{tagged_answer.get('skipped', 0)}): {tagged_answer!r}"
        )
    finally:
        if created_tag:
            occ("tag:delete", created_tag, check_status=False)
        elif tagged:
            occ("tag:files:delete", tagged, TAG, "public", check_status=False)
        for folder in (inside, outside):
            harness.request("DELETE", folder)
        left = {folder: harness.status(folder) for folder in (inside, outside)}
        harness.http.close()
        exclusion_core.clear_cache()
    assert all(status == 404 for status in left.values()), f"test data left behind: {left}"
