"""The measuring run of phase 25: what does a tag query cost and what does it return.

The design of phases 26 to 28 rests on one WebDAV call, ``REPORT oc:filter-files`` with an
``oc:systemtag`` rule, asked once per answer. Before anything is derived from it, its
behaviour is measured against a running Nextcloud and not read out of the server source:
which id a note carries compared to the fileid of its file, whether the REPORT answers the
same under AppAPI impersonation as under an app password, what an unknown, a deleted, an
invisible or a same-named tag does, whether the target path of the REPORT filters, where
the share boundary lies, and what switching the ``systemtags`` app off changes.

Run it against the Nextcloud 35 topology of ``compose.nc35.yml``::

    uv run --no-sync python scripts/tag_spike.py --env-file .env.nc35 --block <name> --out <file>

The blocks are ``controls`` (topology, baseline inventory, the impersonation controls),
``findings`` (the single findings on nc35, each rolled back in a ``finally``) and
``secret-scan`` (the gate over every protocol of the phase folder before a commit).

**No secret reaches a protocol.** The values of the environment file, every password and
token generated during a run and the ``AUTHORIZATION-APP-API`` header name are scanned for
before a protocol is written; a hit aborts the write. Passwords travel to ``occ`` through
stdin only, never as an argument (WR-06).
"""

import argparse
import asyncio
import base64
import json
import re
import secrets
import statistics
import subprocess
import sys
import time
from collections.abc import Callable, Coroutine, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote, urlsplit

import httpx
from lxml import etree

from mcp_connector.errors import ToolError
from mcp_connector.nextcloud.clients import notes, ocs, xml
from mcp_connector.nextcloud.credentials import MODE_APPAPI, MODE_BASIC, Credentials
from mcp_connector.nextcloud.http import NoCookieJar

#: The containers of the Nextcloud 35 topology this run measures against.
NC_CONTAINER = "nc35-nc"
EXAPP_CONTAINER = "nc_app_mcp_connector"
TOPOLOGY_CONTAINERS = (NC_CONTAINER, EXAPP_CONTAINER, "nc35-harp", "nc35-caddy")
BASE_URL = "http://127.0.0.1:8082"

#: The throwaway instance of ``compose.spike-tags.yml`` (plan 25-03).
SPIKE_CONTAINER = "nc-spike-tags"
SPIKE_BASE_URL = "http://127.0.0.1:8083"
SPIKE_COMPOSE = "compose.spike-tags.yml"

#: Every tag this run creates starts with this prefix, never the bare production name: a
#: forgotten tag of that exact name would falsify the canary tests of phases 26 to 28.
TAG_PREFIX = "kein-ki-spike25"
#: Every file and folder this run creates lives below this directory of the test user.
SPIKE_DIR = "spike25"

#: D-25-04: above this median the derivation stops and the owner decides.
THRESHOLD_SECONDS = 1.0
WARMUP = 3
RUNS_WARM = 15
RUNS_COLD = 3

#: The phase folder the protocols live in (D-25-06: internal, nothing goes to docs/).
REPO_ROOT = Path(__file__).resolve().parents[1]
PHASE_DIR = REPO_ROOT / ".planning" / "phases" / "25-mess-spike-tag-abfrage"
RAW_DIR = PHASE_DIR / "raw"
REPORT_FILE = PHASE_DIR / "25-MESSBERICHT.md"

#: The header name whose value is base64 of ``user:APP_SECRET``; never in a protocol.
APPAPI_HEADER = "AUTHORIZATION-APP-API"

#: Environment names whose values are secrets, whatever else the file carries.
_SECRET_NAME = re.compile(r"(SECRET|PASSWORD|TOKEN|_KEY)")

SABRE = "http://sabredav.org/ns"
DAV_FILES = "/remote.php/dav/files/"
TIMEOUT = httpx.Timeout(60.0)

BLOCKS = ("controls", "findings", "secret-scan")

# --- PHP one shot snippets ------------------------------------------------------------------
# Handed to ``php --`` through stdin, arguments behind the ``--``; nothing of them lands in
# the repository as a .php file. They bootstrap Nextcloud the way occ does.

_PHP_BOOT = "<?php\nrequire_once '/var/www/html/lib/base.php';\n"

#: Set the complete object set of one tag in one transaction (ISystemTagObjectMapper, NC 31+).
#: Arguments: tag id, count, folder below the user's home, user. Picks ``count`` files spread
#: evenly over the folder, walked recursively, and prints the count and the first ids.
PHP_SET_TAG_OBJECTS = (
    _PHP_BOOT
    + r"""
[, $tagId, $count, $sub, $user] = $argv;
$folder = \OCP\Server::get(\OCP\Files\IRootFolder::class)->getUserFolder($user)->get($sub);
$ids = [];
$walk = function ($node) use (&$walk, &$ids) {
    if ($node instanceof \OCP\Files\Folder) {
        foreach ($node->getDirectoryListing() as $child) { $walk($child); }
    } else {
        $ids[] = (string)$node->getId();
    }
};
$walk($folder);
sort($ids, SORT_NUMERIC);
$n = max(0, (int)$count);
$step = max(1, intdiv(count($ids), max(1, $n)));
$pick = [];
foreach ($ids as $k => $id) {
    if ($k % $step === 0 && count($pick) < $n) { $pick[] = $id; }
}
\OCP\Server::get(\OCP\SystemTag\ISystemTagObjectMapper::class)
    ->setObjectIdsForTag($tagId, 'files', $pick);
echo count($pick), ' ', implode(',', array_slice($pick, 0, 5)), "\n";
"""
)

#: Insert a tag row directly, the way an old instance may still carry one: ``createTag``
#: refuses same-named tags case-insensitively since 32, the unique index of the table only
#: covers ``(name, visibility, editable)``. Arguments: name, visibility, editable.
PHP_INSERT_VARIANT = (
    _PHP_BOOT
    + r"""
[, $name, $visibility, $editable] = $argv;
$db = \OCP\Server::get(\OCP\IDBConnection::class);
$qb = $db->getQueryBuilder();
$int = \OCP\DB\QueryBuilder\IQueryBuilder::PARAM_INT;
$qb->insert('systemtag')->values([
    'name' => $qb->createNamedParameter($name),
    'visibility' => $qb->createNamedParameter((int)$visibility, $int),
    'editable' => $qb->createNamedParameter((int)$editable, $int),
    'etag' => $qb->createNamedParameter(md5($name . $visibility . $editable . microtime())),
])->executeStatement();
echo $qb->getLastInsertId(), "\n";
"""
)

#: The number of rows in the tag mapping table, for the baseline inventory.
PHP_COUNT_MAPPINGS = (
    _PHP_BOOT
    + r"""
$db = \OCP\Server::get(\OCP\IDBConnection::class);
$qb = $db->getQueryBuilder();
$qb->select($qb->func()->count('*', 'n'))->from('systemtag_object_mapping');
echo $qb->executeQuery()->fetchOne(), "\n";
"""
)


class RunFailed(RuntimeError):
    """A step did not answer the way a measuring run needs it to."""


@dataclass(frozen=True, slots=True)
class DavResult:
    """One measured DAV request: status, body size, wall clock and the body itself."""

    status: int
    size: int
    seconds: float
    body: bytes


# --- protocol -------------------------------------------------------------------------------

_protocol: list[str] = []
_secrets: dict[str, str] = {}


def now_stamp() -> str:
    """The moment a line was measured, in UTC."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def note(line: str) -> None:
    """One protocol line, printed and kept for the scanned write at the end."""
    print(line)
    _protocol.append(line)


def section(title: str) -> None:
    """One heading per measured block, so the raw output can be quoted by the block."""
    note(f"\n== {title} ==")


def row(block: str, command: str, status: int | str, raw: str, seconds: float | None = None) -> str:
    """Timestamp | block | command | HTTP status | ms | raw excerpt (at most 300 chars)."""
    timing = "" if seconds is None else f" | {seconds * 1000:.0f} ms"
    excerpt = raw.replace("\r", "").replace("\n", " ")[:300]
    line = f"{now_stamp()} | {block} | {command} | HTTP {status}{timing} | {excerpt}"
    note(line)
    return line


def remember_secret(name: str, value: str) -> None:
    """Register a value the protocol must never contain."""
    if value.strip():
        _secrets[name] = value


def scan_for_secrets(texts: Mapping[str, str], secrets: Mapping[str, str]) -> list[str]:
    """Every line of ``texts`` that carries a secret value or the AppAPI header name.

    A finding names the text, the line number and the *name* of the secret, never the value,
    so the report of a hit is itself safe to print. Empty values are ignored: an unset
    variable would otherwise match every line.
    """
    wanted = [(name, value) for name, value in secrets.items() if value.strip()]
    findings: list[str] = []
    for label, text in texts.items():
        for number, line in enumerate(text.splitlines(), start=1):
            findings.extend(f"{label}:{number}: {name}" for name, value in wanted if value in line)
            if APPAPI_HEADER in line:
                findings.append(f"{label}:{number}: {APPAPI_HEADER}")
    return findings


def write_protocol(out: Path, header: str) -> None:
    """Append this run to ``out``, but only after the secret scan came back clean."""
    text = "\n".join([header, *_protocol]) + "\n"
    findings = scan_for_secrets({"protocol": text}, _secrets)
    if findings:
        raise RunFailed(f"protocol NOT written, secret values found at: {', '.join(findings)}")
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


# --- processes ------------------------------------------------------------------------------


def run(argv: Sequence[str], *, stdin: str | None = None, check: bool = True) -> str:
    """One external command, no shell, fixed argument list, output as text."""
    finished = subprocess.run(  # noqa: S603 - a fixed argument list, never a shell
        list(argv),
        input=stdin,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if check and finished.returncode != 0:
        raise RunFailed(
            f"{' '.join(argv[:6])} exited {finished.returncode}: "
            f"{(finished.stderr or finished.stdout).strip()[:400]}"
        )
    return ((finished.stdout or "") + (finished.stderr or "")).replace("\r", "")


def docker(*argv: str, stdin: str | None = None, check: bool = True) -> str:
    """One docker call. ``docker`` is on PATH by contract, as in every script here."""
    return run(["docker", *argv], stdin=stdin, check=check)


def occ(container: str, *argv: str, check: bool = True) -> str:
    """One ``occ`` call inside ``container``, output stripped of carriage returns."""
    return docker("exec", "-u", "www-data", container, "php", "occ", *argv, check=check).strip()


def occ_pw(container: str, password: str, *argv: str, check: bool = True) -> str:
    """One ``occ`` call that needs a password: it travels through stdin as ``OC_PASS``."""
    snippet = 'OC_PASS="$(cat)"; export OC_PASS; exec php occ "$@"'
    return docker(
        "exec",
        "-i",
        "-u",
        "www-data",
        container,
        "sh",
        "-c",
        snippet,
        "sh",
        *argv,
        stdin=password,
        check=check,
    ).strip()


def php(container: str, snippet: str, *args: str) -> str:
    """Run one PHP snippet through stdin; returns the last non-empty output line."""
    output = docker(
        "exec",
        "-i",
        "-u",
        "www-data",
        "-w",
        "/var/www/html",
        container,
        "php",
        "--",
        *args,
        stdin=snippet,
    )
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    return lines[-1] if lines else ""


def wait_for_install(container: str) -> None:
    """Poll ``occ status`` until the installation finished (60 x 5 s)."""
    for attempt in range(1, 61):
        if "installed: true" in occ(container, "status", check=False):
            note(f"{container}: installed (attempt {attempt})")
            return
        time.sleep(5)
    raise RunFailed(f"{container} is still not installed after five minutes")


def read_env_file(path: Path) -> dict[str, str]:
    """The values ``scripts/bootstrap_exapp.sh`` wrote, as a mapping. Never printed."""
    if not path.is_file():
        raise RunFailed(f"{path} is not there; run scripts/bootstrap_exapp.sh --nc35 first")
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, _, value = stripped.partition("=")
        values[name.strip()] = value.strip().strip('"').strip("'")
    return values


def remember_env_secrets(env: Mapping[str, str]) -> None:
    """Every secret-like value of the environment file, plus the derived AppAPI token."""
    for name, value in env.items():
        if _SECRET_NAME.search(name):
            remember_secret(name, value)
    user = env.get("NC_MCP_TEST_USER", "")
    secret = env.get("APP_SECRET", "")
    if user and secret:
        token = base64.b64encode(f"{user}:{secret}".encode()).decode()
        remember_secret("APPAPI_TOKEN", token)


def access_lines(container: str, since: str, needles: Iterable[str]) -> list[str]:
    """The Apache access log of ``container`` since ``since``, filtered to ``needles``."""
    wanted = tuple(needles)
    return [
        line.strip()
        for line in docker("logs", "--since", since, container, check=False).splitlines()
        if any(needle in line for needle in wanted)
    ]


def impersonation_lines(container: str, since: str) -> list[str]:
    """REPORT lines of alice in ``data/exapp_impersonation.log`` written since ``since``."""
    log = docker(
        "exec",
        container,
        "tail",
        "-n",
        "400",
        "/var/www/html/data/exapp_impersonation.log",
        check=False,
    )
    hits = []
    for line in log.splitlines():
        if '"method":"REPORT"' in line and '"user":"alice"' in line:
            hits.append(line.strip())
    return [line for line in hits if _log_time(line) >= since]


def _log_time(line: str) -> str:
    """The ISO timestamp of one JSON log line, normalised to ``YYYY-MM-DDTHH:MM:SSZ``."""
    try:
        record = json.loads(line)
    except json.JSONDecodeError:
        return ""
    raw = str(record.get("time") or record.get("timestamp") or "")
    try:
        moment = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return raw
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def topology(container: str = NC_CONTAINER) -> None:
    """What this run measured against, named container by container."""
    section(f"topology, {now_stamp()}")
    note(
        docker(
            "ps",
            "--format",
            "{{.Names}}  {{.Image}}  {{.Status}}",
            *[arg for name in TOPOLOGY_CONTAINERS for arg in ("--filter", f"name=^{name}$")],
            check=False,
        ).strip()
    )
    note(occ(container, "status", check=False))
    note(f"dbtype: {occ(container, 'config:system:get', 'dbtype', check=False)}")
    note(
        docker(
            "stats",
            "--no-stream",
            "--format",
            "{{.Name}}  mem {{.MemUsage}}  cpu {{.CPUPerc}}",
            check=False,
        ).strip()
    )


# --- baseline -------------------------------------------------------------------------------


def baseline(container: str, user: str) -> dict[str, str]:
    """The inventory a run has to leave behind unchanged."""
    raw_tags = occ(container, "tag:list", "--output=json", check=False)
    try:
        tags = json.dumps(json.loads(raw_tags or "[]"), sort_keys=True)
    except json.JSONDecodeError:
        tags = raw_tags
    files = docker(
        "exec",
        "-u",
        "www-data",
        container,
        "sh",
        "-c",
        'find "$1" -type f | wc -l',
        "sh",
        f"/var/www/html/data/{user}/files",
        check=False,
    ).strip()
    trash = docker(
        "exec",
        "-u",
        "www-data",
        container,
        "sh",
        "-c",
        'if [ -d "$1" ]; then find "$1" -mindepth 1 -maxdepth 1 | wc -l; else echo 0; fi',
        "sh",
        f"/var/www/html/data/{user}/files_trashbin/files",
        check=False,
    ).strip()
    mappings = php(container, PHP_COUNT_MAPPINGS)
    return {"tags": tags, "dateien": files, "papierkorb": trash, "mappings": mappings}


def compare_baseline(before: Mapping[str, str], after: Mapping[str, str]) -> list[str]:
    """One line per field: before, after and whether both are the same."""
    lines = []
    for field, value in before.items():
        other = after.get(field, "")
        same = "ja" if value == other else "nein"
        lines.append(f"BASELINE {field} vorher={value} nachher={other} gleich={same}")
    return lines


# --- pure helpers ---------------------------------------------------------------------------


def report_body(tag_id: str) -> bytes:
    """The REPORT ``oc:filter-files`` body for one system tag id, built with lxml.

    Only ASCII digits pass: the id goes into an XML text node of a request that decides what
    a user sees, and ``str.isdigit`` would also accept full-width and superscript digits.
    """
    if not re.fullmatch(r"[0-9]+", tag_id):
        raise ValueError(f"a tag id must be ASCII digits only (got {tag_id!r})")
    root = etree.Element(
        f"{{{xml.OC}}}filter-files", nsmap={"d": xml.DAV, "oc": xml.OC, "nc": xml.NC}
    )
    prop = etree.SubElement(root, f"{{{xml.DAV}}}prop")
    etree.SubElement(prop, f"{{{xml.OC}}}fileid")
    etree.SubElement(prop, f"{{{xml.DAV}}}resourcetype")
    rules = etree.SubElement(root, f"{{{xml.OC}}}filter-rules")
    etree.SubElement(rules, f"{{{xml.OC}}}systemtag").text = tag_id
    return etree.tostring(root, xml_declaration=True, encoding="utf-8")


def propfind_body(props: Sequence[str]) -> bytes:
    """A PROPFIND body for the given Clark-notation property names, built with lxml."""
    root = etree.Element(f"{{{xml.DAV}}}propfind", nsmap={"d": xml.DAV, "oc": xml.OC, "nc": xml.NC})
    prop = etree.SubElement(root, f"{{{xml.DAV}}}prop")
    for name in props:
        etree.SubElement(prop, name)
    return etree.tostring(root, xml_declaration=True, encoding="utf-8")


def home_url(creds: Credentials, sub: str = "/") -> str:
    """The WebDAV URL below the user's home.

    Deliberately not ``dav.files_url``: that one maps the path into ``NC_MCP_FILES_ROOT``,
    and this run measures Nextcloud, not the sandbox of the connector.
    """
    return f"{creds.base_url}{DAV_FILES}{quote(creds.user, safe='')}{quote(sub, safe='/')}"


def home_of(creds: Credentials) -> str:
    """The href prefix of the user's home, as Nextcloud writes it into a Multi-Status."""
    return f"{urlsplit(creds.base_url).path.rstrip('/')}{DAV_FILES}{creds.user}"


def home_path_of(href: str, home: str) -> str | None:
    """The path inside ``home``, or ``None`` when the href belongs somewhere else."""
    raw = unquote(urlsplit(href).path)
    if not raw.startswith(home):
        return None
    rest = raw[len(home) :]
    if rest and not rest.startswith("/"):
        # "alicexyz" starts with "alice" but is a different account.
        return None
    return rest.rstrip("/") or "/"


def read_report(body: bytes) -> list[tuple[str, str, bool]]:
    """``(href, fileid, is_collection)`` for every response, none of them dropped.

    Unlike ``dav.parse_entries`` nothing outside a home prefix is discarded: an entry the
    connector would skip is exactly what a measurement has to see.
    """
    root = xml.parse_root(body)
    entries: list[tuple[str, str, bool]] = []
    for response in root.findall(f"{{{xml.DAV}}}response"):
        href_el = response.find(f"{{{xml.DAV}}}href")
        href = (href_el.text or "").strip() if href_el is not None else ""
        fileid_el = response.find(f".//{{{xml.OC}}}fileid")
        fileid = (fileid_el.text or "").strip() if fileid_el is not None else ""
        collection = response.find(f".//{{{xml.DAV}}}resourcetype/{{{xml.DAV}}}collection")
        entries.append((href, fileid, collection is not None))
    return entries


def describe_error(body: bytes) -> str:
    """The ``s:message`` of a Sabre ``d:error`` body, or a short note what the body was."""
    if not body.strip():
        return "(no body)"
    try:
        root = xml.parse_root(body)
    except ToolError:
        return "(not XML)"
    message = root.find(f"{{{SABRE}}}message")
    if message is not None:
        return (message.text or "").strip()
    return f"(root {root.tag})"


def summarize(values: Sequence[float]) -> dict[str, float]:
    """min, median, the second largest value and max of one series.

    With 15 runs the 95th percentile is not a measured value, so the key says what it is:
    the second largest one. Fewer than two values carry no spread at all.
    """
    if len(values) < 2:
        raise ValueError("a series needs at least two values")
    ordered = sorted(values)
    return {
        "min": ordered[0],
        "median": statistics.median(ordered),
        "p95_second_largest": ordered[-2],
        "max": ordered[-1],
    }


# --- HTTP -----------------------------------------------------------------------------------


def basic_creds(env: Mapping[str, str], user: str, password: str) -> Credentials:
    """App password credentials of one test user."""
    return Credentials(base_url=_base_url(env), user=user, secret=password, mode=MODE_BASIC)


def appapi_creds(env: Mapping[str, str], user: str, secret: str | None = None) -> Credentials:
    """AppAPI impersonation credentials: ``APP_SECRET`` is the only secret in play."""
    return Credentials(
        base_url=_base_url(env),
        user=user,
        secret=env["APP_SECRET"] if secret is None else secret,
        mode=MODE_APPAPI,
        app_id=env.get("APP_ID", ""),
        app_version=env.get("APP_VERSION", ""),
        aa_version=env.get("AA_VERSION", ""),
    )


def _base_url(env: Mapping[str, str]) -> str:
    return (env.get("NC_MCP_URL") or BASE_URL).rstrip("/")


def new_client() -> httpx.AsyncClient:
    """One client per block, with the production posture of ``nextcloud/http.py``.

    ``NoCookieJar`` is load bearing here, not a copy of habit: this run speaks as alice, bob,
    a temporary admin and as the impersonated alice through one client, and a session cookie
    Nextcloud set for one of them would carry the next request under the wrong identity
    (measured on 26.09.: the admin's PUT rode alice's session and got a 403).
    """
    return httpx.AsyncClient(follow_redirects=False, timeout=TIMEOUT, cookies=NoCookieJar())


async def dav_request(
    client: httpx.AsyncClient,
    creds: Credentials,
    method: str,
    url: str,
    *,
    depth: str | None = None,
    body: bytes | None = None,
) -> DavResult:
    """One DAV request, timed; a 4xx is returned, never raised (a 412 is no empty hit list)."""
    headers: dict[str, str] = {}
    if depth is not None:
        headers["Depth"] = depth
    if body is not None:
        headers["Content-Type"] = "application/xml; charset=utf-8"
    started = time.perf_counter()
    response = await client.request(method, url, headers=headers, content=body, auth=creds.auth())
    seconds = time.perf_counter() - started
    return DavResult(response.status_code, len(response.content), seconds, response.content)


# --- blocks ---------------------------------------------------------------------------------


async def guarded(name: str, work: Coroutine[Any, Any, None]) -> None:
    """One block, and its failure reported as a measured outcome instead of an abort."""
    try:
        await work
    except Exception as failure:
        note(f"BLOCK FAILED | {name} | {type(failure).__name__}: {str(failure)[:300]}")


async def controls(env: Mapping[str, str]) -> None:
    """Topology, baseline, and the two identity controls every later row depends on."""
    topology()
    user = env["NC_MCP_TEST_USER"]
    section("baseline")
    for field, value in baseline(NC_CONTAINER, user).items():
        note(f"BASELINE-START {field}={value}")

    section("controls")
    async with new_client() as client:
        creds = appapi_creds(env, user)
        response = await ocs.ocs_get(client, creds, "/cloud/user")
        if response.status_code == 401:
            row("controls", "a: GET /ocs/v2.php/cloud/user (AppAPI)", 401, "refused")
            raise RunFailed("APP_SECRET stale, ask the owner before bootstrap_exapp.sh")
        data = ocs.parse_ocs(response, what="the impersonated user")
        seen = str(data.get("id") or "") if isinstance(data, dict) else ""
        row(
            "controls",
            "a: GET /ocs/v2.php/cloud/user (AppAPI)",
            response.status_code,
            f"id={seen} erwartet={user} gleich={'ja' if seen == user else 'nein'}",
        )
        wrong = appapi_creds(env, user, secret="0" * 64)
        refused = await ocs.ocs_get(client, wrong, "/cloud/user")
        row(
            "controls",
            "b: GET /ocs/v2.php/cloud/user (AppAPI, wrong APP_SECRET)",
            refused.status_code,
            f"abgelehnt={'ja' if refused.status_code != 200 else 'nein'}",
        )


# --- findings on nc35 -----------------------------------------------------------------------

#: The sub blocks of ``findings``, in the order they run and are reported.
FINDINGS_BLOCKS = (
    "notes",
    "impersonation",
    "412",
    "unsichtbar",
    "varianten",
    "zielpfad",
    "freigabe",
    "app-aus-35",
)

SHARES_PATH = "/apps/files_sharing/api/v1/shares"
TEMP_ADMIN = "spike25admin"


@dataclass
class Run:
    """Everything one findings run creates, so the ``finally`` can take all of it back."""

    env: Mapping[str, str]
    client: httpx.AsyncClient
    alice: Credentials
    bob: Credentials
    note_ids: list[str]
    share_ids: list[str]
    tag_ids: list[str]
    notes_path: str = ""
    admin_created: bool = False


async def ensure_dir(run: Run, creds: Credentials, path: str) -> None:
    """MKCOL every segment of ``path`` below the home; an existing folder is fine (405)."""
    current = ""
    for segment in [part for part in path.split("/") if part]:
        current = f"{current}/{segment}"
        result = await dav_request(run.client, creds, "MKCOL", home_url(creds, current + "/"))
        if result.status not in (201, 405):
            raise RunFailed(f"MKCOL {current} answered {result.status}")


async def put_file(run: Run, creds: Credentials, path: str, content: str = "spike25\n") -> str:
    """Create one file (and its parents) and return its fileid."""
    parent = path.rsplit("/", 1)[0]
    if parent:
        await ensure_dir(run, creds, parent)
    response = await run.client.put(
        home_url(creds, path), content=content.encode(), auth=creds.auth()
    )
    if response.status_code not in (201, 204):
        detail = describe_error(response.content)
        raise RunFailed(f"PUT {path} answered {response.status_code}: {detail}")
    return await fileid_of(run, creds, path)


async def fileid_of(run: Run, creds: Credentials, path: str) -> str:
    """The ``oc:fileid`` of one entry, read with a PROPFIND Depth 0."""
    result = await dav_request(
        run.client,
        creds,
        "PROPFIND",
        home_url(creds, path),
        depth="0",
        body=propfind_body([f"{{{xml.OC}}}fileid"]),
    )
    if result.status != 207:
        raise RunFailed(f"PROPFIND {path} answered {result.status}")
    entries = read_report(result.body)
    if not entries or not entries[0][1]:
        raise RunFailed(f"PROPFIND {path} carried no fileid")
    return entries[0][1]


def parse_tag_id(output: str) -> str:
    """The id out of ``occ tag:add --output=json``."""
    start = output.find("{")
    try:
        data = json.loads(output[start:]) if start >= 0 else {}
    except json.JSONDecodeError:
        data = {}
    tag_id = str(data.get("id", "")) if isinstance(data, dict) else ""
    if not re.fullmatch(r"[0-9]+", tag_id):
        raise RunFailed(f"occ tag:add gave no id: {output[:200]}")
    return tag_id


def list_tags(container: str) -> list[tuple[str, str, str]]:
    """``(id, name, access)`` of every tag ``occ tag:list`` knows."""
    raw = occ(container, "tag:list", "--output=json", check=False)
    start = min((i for i in (raw.find("{"), raw.find("[")) if i >= 0), default=-1)
    try:
        data = json.loads(raw[start:]) if start >= 0 else []
    except json.JSONDecodeError:
        return []
    items: list[tuple[str, str, str]] = []
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, dict):
                items.append((str(key), str(value.get("name", "")), str(value.get("access", ""))))
    elif isinstance(data, list):
        items.extend(
            (str(value.get("id", "")), str(value.get("name", "")), str(value.get("access", "")))
            for value in data
            if isinstance(value, dict)
        )
    return items


def tag_add(run: Run, name: str, access: str) -> str:
    """Create one tag with occ and remember its id for the rollback."""
    tag_id = parse_tag_id(occ(NC_CONTAINER, "tag:add", name, access, "--output=json"))
    run.tag_ids.append(tag_id)
    note(f"occ tag:add {name} {access} -> id {tag_id}")
    return tag_id


def tag_files_add(run: Run, fileid: str, name: str, access: str) -> str:
    """Tag one node by fileid (creates the tag if missing) and return the tag id by name."""
    output = occ(NC_CONTAINER, "tag:files:add", fileid, name, access)
    note(f"occ tag:files:add {fileid} {name} {access} -> {output[:120]}")
    matches = [tag_id for tag_id, tag_name, _ in list_tags(NC_CONTAINER) if tag_name == name]
    if not matches:
        raise RunFailed(f"tag {name} not listed after tag:files:add")
    for tag_id in matches:
        if tag_id not in run.tag_ids:
            run.tag_ids.append(tag_id)
    return matches[-1]


async def report(run: Run, creds: Credentials, tag_id: str, sub: str = "/") -> DavResult:
    """One REPORT ``oc:filter-files`` below ``sub`` of the user's home."""
    return await dav_request(
        run.client, creds, "REPORT", home_url(creds, sub), body=report_body(tag_id)
    )


def describe_report(result: DavResult, creds: Credentials) -> str:
    """Hits with fileids and home relative paths, or the error text of a failed REPORT."""
    if result.status != 207:
        return f"fehler={describe_error(result.body)}"
    entries = read_report(result.body)
    home = home_of(creds)
    paths = [home_path_of(href, home) or f"FREMD:{href}" for href, _, _ in entries]
    fileids = sorted((fileid for _, fileid, _ in entries), key=_as_int)
    return f"treffer={len(entries)} fileids={fileids} pfade={paths}"


def report_fileids(result: DavResult) -> list[str]:
    """The sorted fileids of a 207 REPORT, empty for anything else."""
    if result.status != 207:
        return []
    return sorted((fileid for _, fileid, _ in read_report(result.body)), key=_as_int)


def _as_int(value: str) -> int:
    return int(value) if value.isdigit() else -1


async def log_report(
    run: Run, block: str, label: str, creds: Credentials, tag_id: str, sub: str = "/"
) -> DavResult:
    """REPORT, then one protocol row with status, wall clock and the hit list."""
    result = await report(run, creds, tag_id, sub)
    command = f"REPORT systemtag={tag_id} als {creds.user} ({creds.mode}) auf {sub} [{label}]"
    row(block, command, result.status, describe_report(result, creds), result.seconds)
    return result


async def block_notes(run: Run) -> None:
    """Pattern 5: does the id of a note equal the fileid of its file (D-25-05, EXCL-05)."""
    block = "notes"
    creds = run.alice
    headers = {"OCS-APIRequest": "true", "Accept": "application/json"}
    response = await run.client.get(
        notes.api_url(creds, "/settings"), headers=headers, auth=creds.auth()
    )
    settings = response.json() if response.status_code == 200 else {}
    run.notes_path = str(settings.get("notesPath") or "Notes").strip("/")
    row(block, "GET notes/api/v1/settings", response.status_code, f"notesPath={run.notes_path}")

    first = await notes.create_note(
        run.client, creds, title="spike25 Notiz", content="x", category=SPIKE_DIR
    )
    first_id = str(first.get("id", ""))
    run.note_ids.append(first_id)
    row(
        block,
        "POST notes/api/v1/notes title='spike25 Notiz' category=spike25",
        "2xx",
        f"id={first_id} title={first.get('title')} category={first.get('category')}",
    )

    folder = f"/{run.notes_path}/{SPIKE_DIR}"
    listing = await _list_folder(run, creds, folder)
    row(block, f"PROPFIND Depth 1 {folder}/", 207, f"eintraege={listing}")
    by_name = {name: fileid for name, fileid, _ in listing}
    first_fileid = by_name.get(f"{first.get('title')}.md", "")
    same_first = first_id == first_fileid
    note(
        f"NOTES id={first_id} fileid={first_fileid} datei={first.get('title')}.md "
        f"gleich={'ja' if same_first else 'nein'}"
    )

    fetched = await notes.get_note(run.client, creds, first_fileid or "0")
    same_fetch = str(fetched.get("id", "")) == first_id
    row(
        block,
        f"GET notes/api/v1/notes/{first_fileid}",
        "2xx",
        f"id={fetched.get('id')} title={fetched.get('title')} "
        f"dieselbe_notiz={'ja' if same_fetch else 'nein'}",
    )

    second = await notes.create_note(
        run.client, creds, title="spike25 Notiz", content="y", category=SPIKE_DIR
    )
    second_id = str(second.get("id", ""))
    run.note_ids.append(second_id)
    listing = await _list_folder(run, creds, folder)
    new_files = [(name, fileid) for name, fileid, _ in listing if name not in by_name]
    second_name, second_fileid = new_files[0] if len(new_files) == 1 else ("?", "")
    same_second = second_id == second_fileid
    row(
        block,
        "POST notes/api/v1/notes (same title again)",
        "2xx",
        f"id={second_id} title={second.get('title')} neue_dateien={new_files}",
    )
    note(
        f"NOTES id={second_id} fileid={second_fileid} datei={second_name} "
        f"gleich={'ja' if same_second else 'nein'}"
    )

    folder_id = await fileid_of(run, creds, folder)
    tag_id = tag_files_add(run, folder_id, f"{TAG_PREFIX}-notes", "public")
    result = await log_report(run, block, "Notes-Kategorieordner getaggt", creds, tag_id)
    hits = report_fileids(result)
    folder_hit = "ja" if folder_id in hits else "nein"
    note_hits = [i for i in (first_id, second_id) if i in hits]
    note(
        f"NOTES REPORT ordner_fileid={folder_id} im_treffer={folder_hit} "
        f"notiz_ids_im_treffer={note_hits}"
    )

    verdict = "ja" if same_first and same_second and same_fetch else "nein"
    note(f"NOTIZ-ID GLEICH FILEID: {verdict}")


async def _list_folder(run: Run, creds: Credentials, folder: str) -> list[tuple[str, str, bool]]:
    """``(displayname, fileid, is_collection)`` of the children of ``folder``."""
    result = await dav_request(
        run.client,
        creds,
        "PROPFIND",
        home_url(creds, folder + "/"),
        depth="1",
        body=propfind_body([f"{{{xml.OC}}}fileid", f"{{{xml.DAV}}}displayname"]),
    )
    if result.status != 207:
        raise RunFailed(f"PROPFIND {folder} answered {result.status}")
    children: list[tuple[str, str, bool]] = []
    home = home_of(creds)
    for href, props in xml.parse_multistatus(result.body):
        path = home_path_of(href, home)
        if path is None or path.rstrip("/") == folder.rstrip("/"):
            continue
        name = props.get(f"{{{xml.DAV}}}displayname") or path.rsplit("/", 1)[-1]
        is_dir = href.endswith("/")
        children.append((name, props.get(f"{{{xml.OC}}}fileid", ""), is_dir))
    return children


#: The REPORT from inside the ExApp container, the exact production way (http://caddy).
#: Fed to ``/app/.venv/bin/python -`` through stdin with the user and the tag id as
#: arguments. It reads APP_SECRET from its own environment and prints nothing but the
#: status, the number of hits and the sorted fileids (T-25-03).
EXAPP_REPORT_PROGRAM = r"""
import base64, os, sys
import httpx
from lxml import etree

user, tag = sys.argv[1], sys.argv[2]
DAV, OC = "DAV:", "http://owncloud.org/ns"
root = etree.Element("{%s}filter-files" % OC, nsmap={"d": DAV, "oc": OC})
prop = etree.SubElement(root, "{%s}prop" % DAV)
etree.SubElement(prop, "{%s}fileid" % OC)
rules = etree.SubElement(root, "{%s}filter-rules" % OC)
etree.SubElement(rules, "{%s}systemtag" % OC).text = tag
body = etree.tostring(root, xml_declaration=True, encoding="utf-8")
token = base64.b64encode(("%s:%s" % (user, os.environ["APP_SECRET"])).encode()).decode()
headers = {
    "AA-VERSION": os.environ.get("AA_VERSION", ""),
    "EX-APP-ID": os.environ.get("APP_ID", ""),
    "EX-APP-VERSION": os.environ.get("APP_VERSION", ""),
    "AUTHORIZATION-APP-API": token,
    "Content-Type": "application/xml",
}
base = os.environ.get("NEXTCLOUD_URL", "http://caddy").rstrip("/")
response = httpx.request(
    "REPORT", base + "/remote.php/dav/files/" + user + "/", headers=headers, content=body,
    timeout=60.0,
)
ids = []
if response.status_code == 207:
    parser = etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False)
    tree = etree.fromstring(response.content, parser=parser)
    ids = sorted((el.text or "") for el in tree.iter("{%s}fileid" % OC))
print(response.status_code, len(ids), ",".join(sorted(ids, key=lambda v: int(v or 0))))
"""


async def block_impersonation(run: Run) -> None:
    """Success criterion 2: the same REPORT under an app password and under AppAPI."""
    block = "impersonation"
    alice = run.alice
    base = f"/{SPIKE_DIR}/imp"
    first = await put_file(run, alice, f"{base}/a.txt")
    second = await put_file(run, alice, f"{base}/b.txt")
    await put_file(run, alice, f"{base}/dir/c.txt")
    folder = await fileid_of(run, alice, f"{base}/dir")
    name = f"{TAG_PREFIX}-imp"
    tag_id = ""
    for fileid in (first, second, folder):
        tag_id = tag_files_add(run, fileid, name, "public")
    note(f"getaggt: a.txt={first} b.txt={second} dir={folder} (dir enthaelt c.txt)")

    since = now_stamp()
    await asyncio.sleep(1)
    basic = await log_report(run, block, "App-Passwort", alice, tag_id)
    appapi = await log_report(run, block, "AppAPI", appapi_creds(run.env, alice.user), tag_id)
    ids_basic = report_fileids(basic)
    ids_appapi = report_fileids(appapi)
    same = ids_basic == ids_appapi and basic.status == appapi.status == 207
    note(
        f"IMPERSONATION fileids_basic={len(ids_basic)} fileids_appapi={len(ids_appapi)} "
        f"gleich={'ja' if same else 'nein'} | basic={ids_basic} appapi={ids_appapi}"
    )
    if not same:
        note(f"BEFUND Rohantwort basic: {basic.body.decode(errors='replace')[:2000]}")
        note(f"BEFUND Rohantwort appapi: {appapi.body.decode(errors='replace')[:2000]}")

    lines = impersonation_lines(NC_CONTAINER, since)
    note(
        f"KONTROLLE c: exapp_impersonation.log, REPORT-Zeilen von alice seit {since}: {len(lines)}"
    )
    for line in lines[-2:]:
        note(f"  {line[:300]}")

    output = docker(
        "exec",
        "-i",
        EXAPP_CONTAINER,
        "/app/.venv/bin/python",
        "-",
        alice.user,
        tag_id,
        stdin=EXAPP_REPORT_PROGRAM,
        check=False,
    ).strip()
    last = output.splitlines()[-1] if output else ""
    parts = last.split(" ")
    status = parts[0] if parts else "?"
    count = parts[1] if len(parts) > 1 else "?"
    ids = [value for value in (parts[2] if len(parts) > 2 else "").split(",") if value]
    row(block, "REPORT aus dem ExApp-Container gegen http://caddy (AppAPI)", status, last)
    note(
        f"IMPERSONATION produktionsweg fileids={count} "
        f"gleich_basic={'ja' if ids == ids_basic and status == '207' else 'nein'}"
    )


async def systemtag_listing(run: Run, creds: Credentials) -> tuple[DavResult, list[str]]:
    """PROPFIND Depth 1 on ``/remote.php/dav/systemtags/``: the tag ids this user sees."""
    result = await dav_request(
        run.client,
        creds,
        "PROPFIND",
        f"{creds.base_url}/remote.php/dav/systemtags/",
        depth="1",
        body=propfind_body([f"{{{xml.OC}}}id", f"{{{xml.OC}}}display-name"]),
    )
    ids: list[str] = []
    if result.status == 207:
        for _href, props in xml.parse_multistatus(result.body):
            tag_id = props.get(f"{{{xml.OC}}}id", "")
            if tag_id:
                ids.append(tag_id)
    return result, ids


async def block_412(run: Run) -> None:
    """412 for an unknown id, and for the id of a tag deleted and created again."""
    block = "412"
    alice = run.alice
    await log_report(run, block, "unbekannte Id", alice, "999999")

    name = f"{TAG_PREFIX}-412"
    first = tag_add(run, name, "public")
    fileid = await put_file(run, alice, f"/{SPIKE_DIR}/t412/x.txt")
    tag_files_add(run, fileid, name, "public")
    await log_report(run, block, f"Id A={first} vor dem Loeschen", alice, first)

    note(f"occ tag:delete {first} -> {occ(NC_CONTAINER, 'tag:delete', first)[:120]}")
    second = tag_add(run, name, "public")
    tag_files_add(run, fileid, name, "public")
    await log_report(run, block, f"Id A={first} nach Loeschen und Neuanlage", alice, first)
    await log_report(run, block, f"Id B={second} (gleicher Name, neu)", alice, second)

    listing, ids = await systemtag_listing(run, alice)
    row(
        block,
        "PROPFIND Depth 1 /remote.php/dav/systemtags/ als alice",
        listing.status,
        f"A={first} gelistet={'ja' if first in ids else 'nein'} "
        f"B={second} gelistet={'ja' if second in ids else 'nein'}",
        listing.seconds,
    )


async def create_temp_admin(run: Run) -> Credentials:
    """A throwaway admin with a random password and an app password, both via stdin only."""
    password = secrets.token_urlsafe(24)
    remember_secret("TEMP_ADMIN_PASSWORD", password)
    occ_pw(NC_CONTAINER, password, "user:add", "--password-from-env", TEMP_ADMIN)
    run.admin_created = True
    note(f"occ user:add --password-from-env {TEMP_ADMIN} (password via stdin)")
    added = occ(NC_CONTAINER, "group:adduser", "admin", TEMP_ADMIN)
    note(f"occ group:adduser admin {TEMP_ADMIN} -> {added[:80]}")
    raw = occ_pw(
        NC_CONTAINER,
        password,
        "user:auth-tokens:add",
        TEMP_ADMIN,
        "--password-from-env",
        "--name",
        "spike25",
    )
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    token = lines[-1] if lines else ""
    if len(token) < 20:
        raise RunFailed(f"no app password could be parsed for {TEMP_ADMIN}")
    remember_secret("TEMP_ADMIN_APP_PASSWORD", token)
    note(f"occ user:auth-tokens:add {TEMP_ADMIN} --password-from-env --name spike25 (token kept)")
    admin = basic_creds(run.env, TEMP_ADMIN, token)
    # The home of a fresh account is set up by its first authenticated DAV request; it is
    # asked for explicitly, so the PUT that follows does not depend on that side effect.
    home = await dav_request(
        run.client,
        admin,
        "PROPFIND",
        home_url(admin, "/"),
        depth="0",
        body=propfind_body([f"{{{xml.OC}}}fileid", f"{{{xml.OC}}}permissions"]),
    )
    row("unsichtbar", f"PROPFIND Depth 0 home of {TEMP_ADMIN}", home.status, "home set up")
    return admin


async def block_unsichtbar(run: Run) -> None:
    """An invisible tag: alice gets a 412, an admin gets an answer."""
    block = "unsichtbar"
    alice = run.alice
    name = f"{TAG_PREFIX}-inv"
    tag_id = tag_add(run, name, "invisible")
    fileid = await put_file(run, alice, f"/{SPIKE_DIR}/inv/y.txt")
    tag_files_add(run, fileid, name, "invisible")
    await log_report(run, block, "unsichtbares Tag, Nicht-Admin", alice, tag_id)
    listing, ids = await systemtag_listing(run, alice)
    row(
        block,
        "PROPFIND Depth 1 /remote.php/dav/systemtags/ als alice",
        listing.status,
        f"Tag {tag_id} in alices Liste={'ja' if tag_id in ids else 'nein'}",
        listing.seconds,
    )
    try:
        admin = await create_temp_admin(run)
        own = await put_file(run, admin, "/spike25-admin.txt")
        tag_files_add(run, own, name, "invisible")
        note(f"Gegenfall: {TEMP_ADMIN} taggt eigene Datei {own} mit demselben unsichtbaren Tag")
        await log_report(run, block, "unsichtbares Tag, Admin (Gegenfall)", admin, tag_id)
        listing, ids = await systemtag_listing(run, admin)
        row(
            block,
            f"PROPFIND Depth 1 /remote.php/dav/systemtags/ als {TEMP_ADMIN}",
            listing.status,
            f"Tag {tag_id} in der Admin-Liste={'ja' if tag_id in ids else 'nein'}",
            listing.seconds,
        )
    finally:
        output = occ(NC_CONTAINER, "user:delete", TEMP_ADMIN, check=False)
        note(f"occ user:delete {TEMP_ADMIN} -> {output[:120]}")
        run.admin_created = False


_BLOCK_FUNCTIONS: dict[str, Callable[[Run], Coroutine[Any, Any, None]]] = {
    "notes": block_notes,
    "impersonation": block_impersonation,
    "412": block_412,
    "unsichtbar": block_unsichtbar,
}


async def rollback(run: Run, before: Mapping[str, str]) -> None:
    """Take back everything a findings run created, in the order of the plan."""
    section("rueckbau")
    note(
        f"occ app:enable systemtags -> {occ(NC_CONTAINER, 'app:enable', 'systemtags', check=False)}"
    )
    for share_id in list(run.share_ids):
        response = await run.client.delete(
            ocs.ocs_url(run.alice, f"{SHARES_PATH}/{share_id}"),
            headers=dict(ocs.OCS_HEADERS),
            auth=run.alice.auth(),
        )
        note(f"DELETE share {share_id} -> HTTP {response.status_code}")
        run.share_ids.remove(share_id)
    spike_tags = {
        tag_id for tag_id, name, _ in list_tags(NC_CONTAINER) if name.lower().startswith(TAG_PREFIX)
    }
    for tag_id in sorted(spike_tags | set(run.tag_ids), key=_as_int):
        output = occ(NC_CONTAINER, "tag:delete", tag_id, check=False)
        note(f"occ tag:delete {tag_id} -> {output[:120]}")
    for note_id in run.note_ids:
        response = await run.client.delete(
            notes.api_url(run.alice, f"/notes/{note_id}"),
            headers={"OCS-APIRequest": "true", "Accept": "application/json"},
            auth=run.alice.auth(),
        )
        note(f"DELETE note {note_id} -> HTTP {response.status_code}")
    user = run.alice.user
    output = occ(
        NC_CONTAINER,
        "files:delete",
        "--force",
        "--skip-trash",
        f"{user}/files/{SPIKE_DIR}",
        check=False,
    )
    note(f"occ files:delete --force --skip-trash {user}/files/{SPIKE_DIR} -> {output[:160]}")
    if run.notes_path:
        folder = f"/{run.notes_path}/{SPIKE_DIR}"
        result = await dav_request(run.client, run.alice, "DELETE", home_url(run.alice, folder))
        note(f"DELETE {folder} -> HTTP {result.status}")
    if before.get("papierkorb") == "0":
        output = occ(NC_CONTAINER, "trashbin:cleanup", user, check=False)
        note(f"occ trashbin:cleanup {user} -> {output[:160]}")
    else:
        note("trashbin:cleanup skipped: the trash was not empty before the run")
    if run.admin_created or TEMP_ADMIN in occ(NC_CONTAINER, "user:list", check=False):
        output = occ(NC_CONTAINER, "user:delete", TEMP_ADMIN, check=False)
        note(f"occ user:delete {TEMP_ADMIN} -> {output[:120]}")
    note(f"occ files:cleanup -> {occ(NC_CONTAINER, 'files:cleanup', check=False)[:160]}")
    listed = TEMP_ADMIN in occ(NC_CONTAINER, "user:list", check=False)
    note(f"RUECKBAU {TEMP_ADMIN} vorhanden: {'ja' if listed else 'nein'}")


async def findings(env: Mapping[str, str]) -> None:
    """The single findings on nc35, each in its own guarded block, all rolled back."""
    topology()
    user = env["NC_MCP_TEST_USER"]
    before = baseline(NC_CONTAINER, user)
    for field, value in before.items():
        note(f"BASELINE-START {field}={value}")
    async with new_client() as client:
        run = Run(
            env=env,
            client=client,
            alice=basic_creds(env, user, env["NC_MCP_TEST_APP_PASSWORD"]),
            bob=basic_creds(env, env["NC_MCP_TEST_USER2"], env["NC_MCP_TEST_APP_PASSWORD2"]),
            note_ids=[],
            share_ids=[],
            tag_ids=[],
        )
        try:
            for name in FINDINGS_BLOCKS:
                section(name)
                work = _BLOCK_FUNCTIONS.get(name)
                if work is None:
                    note(f"BLOCK MISSING | {name} | not built yet")
                    continue
                await guarded(name, work(run))
        finally:
            await rollback(run, before)
            for line in compare_baseline(before, baseline(NC_CONTAINER, user)):
                note(line)


def secret_scan(env_file: Path) -> int:
    """Scan every protocol of the phase folder for the secret values of ``env_file``."""
    env = read_env_file(env_file)
    remember_env_secrets(env)
    files = (
        sorted(path for path in RAW_DIR.rglob("*") if path.is_file()) if RAW_DIR.is_dir() else []
    )
    if REPORT_FILE.is_file():
        files.append(REPORT_FILE)
    texts = {
        str(path.relative_to(REPO_ROOT)): path.read_text(encoding="utf-8", errors="replace")
        for path in files
    }
    hits = scan_for_secrets(texts, _secrets)
    for hit in hits:
        print(f"SECRET FOUND | {hit}")
    print(f"secret-scan: {len(texts)} files, {len(hits)} findings")
    return 1 if hits else 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", default=".env.nc35", help="the file the bootstrap wrote")
    parser.add_argument("--block", required=True, choices=BLOCKS, help="the block to run")
    parser.add_argument("--out", help="the protocol file this run appends to")
    options = parser.parse_args(argv)

    if options.block == "secret-scan":
        return secret_scan(Path(options.env_file))
    if not options.out:
        parser.error("--out is required for a measuring block")

    out = Path(options.out)
    mode = "angehängt an bestehende Datei" if out.exists() else "neue Datei"
    header = f"\n# Lauf block={options.block} start={now_stamp()} ({mode})"
    env = read_env_file(Path(options.env_file))
    remember_env_secrets(env)
    code = 0
    try:
        if options.block == "controls":
            asyncio.run(controls(env))
        else:
            asyncio.run(findings(env))
    except (RunFailed, ToolError, httpx.HTTPError) as failure:
        note(f"RUN FAILED | {type(failure).__name__}: {str(failure)[:300]}")
        code = 1
    finally:
        write_protocol(out, header)
    return code


if __name__ == "__main__":
    sys.exit(main())
