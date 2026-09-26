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
import statistics
import subprocess
import sys
import time
from collections.abc import Coroutine, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote, urlsplit

import httpx
from lxml import etree

from mcp_connector.errors import ToolError
from mcp_connector.nextcloud.clients import ocs, xml
from mcp_connector.nextcloud.credentials import MODE_APPAPI, MODE_BASIC, Credentials

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


def row(block: str, command: str, status: int, raw: str, seconds: float | None = None) -> str:
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
    return httpx.AsyncClient(follow_redirects=False, timeout=TIMEOUT)


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


async def findings(env: Mapping[str, str]) -> None:
    """The single findings on nc35 (plan 25-01 task 2)."""
    raise RunFailed(f"the findings block is not built yet (env with {len(env)} names)")


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
