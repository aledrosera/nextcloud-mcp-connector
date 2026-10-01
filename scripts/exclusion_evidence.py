"""The measuring run behind plan 29-01: how Nextcloud answers the exclusion check's questions.

``occ mcp_connector:exclusion:check`` and its documentation depend on a handful of Nextcloud
behaviours that the source code suggests but no run has shown under AppAPI impersonation
(29-RESEARCH.md, "Live-Messungen gegen nc35", assumptions A1 to A8). This script measures
them against the Nextcloud 35 topology of ``compose.nc35.yml`` before any production code is
written, and appends one raw protocol per run.

Run it with the environment of the topology loaded::

    set -a && . ./.env.nc35 && set +a && PYTHONUTF8=1 \\
        uv run python scripts/exclusion_evidence.py measure

**What the run writes on the test instance.** Tags, two groups, a handful of files and the
app config key ``systemtags restrict_creation_to_admin``. Everything is removed again in a
``finally`` block and read back; each removal ends in one ``CLEANUP`` line. A tag or group
that already carries one of the names of this run stops the run before the first change
(exit 2), so data the run did not create is never touched.

**What the protocol never carries.** Request headers, the APP_SECRET of the ExApp and any
password. Programs that run inside the ExApp container print the status and the response
body only. The admin password in the verbatim curl lines is replaced by ``<passwort>``.
"""

import argparse
import base64
import contextlib
import json
import os
import re
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import httpx
from lxml import etree

NC_CONTAINER = "nc35-nc"
EXAPP_CONTAINER = "nc_app_mcp_connector"
BASE_URL = "http://127.0.0.1:8082"
ADMIN = "admin"
RAW_FILE = Path(".planning/phases/29-pr-fkommando-und-doku/raw/29-01-messungen.txt")
COMPOSE_FILE = Path("compose.nc35.yml")

#: The header name whose value is base64 of ``user:APP_SECRET``; never in a protocol.
APPAPI_HEADER = "AUTHORIZATION-APP-API"

DAV = "DAV:"
OC = "http://owncloud.org/ns"
NC = "http://nextcloud.org/ns"
NSMAP = {"d": DAV, "oc": OC, "nc": NC}

DASH_EN = chr(0x2013)
TIMEOUT = httpx.Timeout(60.0)

#: Every tag name this run may create. A pre-existing one stops the run (exit 2).
TAG_M2_INVISIBLE = "kein-ki-m2"
TAG_M2_RESTRICTED = "kein-ki-m2r"
TAG_M3 = "kein-ki-m3"
TAG_M6_SPACE = "Kein KI"
TAG_M6_JOINED = "keinki"
TAG_M6_DASH = "kein" + DASH_EN + "ki"
TAG_M6_BASE = "kein-ki-m6"
TAG_M6_UPPER = "KEIN-KI-M6"
TAG_GUIDE = "kein-ki"
TAG_M8_POST = "kein-ki-m8b"
TAG_M8_BOB_BEFORE = "kein-ki-m8c"
TAG_M8_BOB_AFTER = "kein-ki-m8d"
RUN_TAGS = (
    TAG_M2_INVISIBLE,
    TAG_M2_RESTRICTED,
    TAG_M3,
    TAG_M6_SPACE,
    TAG_M6_JOINED,
    TAG_M6_DASH,
    TAG_M6_BASE,
    TAG_GUIDE,
    TAG_M8_POST,
    TAG_M8_BOB_BEFORE,
    TAG_M8_BOB_AFTER,
)
GROUP_M2 = "ki-m2"
GROUP_GUIDE = "ki-verantwortung"
RUN_GROUPS = (GROUP_M2, GROUP_GUIDE)
FOLDER_GUIDE = "KI-frei"
CONFIG_KEY = ("systemtags", "restrict_creation_to_admin")

#: The DAV request from inside the ExApp container, the production way (http://caddy). The
#: request spec arrives as base64 JSON in argv[1]: method, path, user ("" = app context),
#: optional depth, optional base64 body, content type and OCS flag. Reads APP_SECRET from
#: its own environment; prints the status on the first line and the body after it, never a
#: header (T-29-02).
EXAPP_DAV_PROGRAM = r"""
import base64, json, os, sys
import httpx

spec = json.loads(base64.b64decode(sys.argv[1]).decode())
token = base64.b64encode(
    ("%s:%s" % (spec["user"], os.environ["APP_SECRET"])).encode()
).decode()
headers = {
    "AA-VERSION": os.environ.get("AA_VERSION", ""),
    "EX-APP-ID": os.environ.get("APP_ID", ""),
    "EX-APP-VERSION": os.environ.get("APP_VERSION", ""),
    "AUTHORIZATION-APP-API": token,
}
if spec.get("depth") is not None:
    headers["Depth"] = str(spec["depth"])
if spec.get("ctype"):
    headers["Content-Type"] = spec["ctype"]
if spec.get("ocs"):
    headers["OCS-APIRequest"] = "true"
    headers["Accept"] = "application/json"
body = base64.b64decode(spec["body"]) if spec.get("body") else None
base = os.environ.get("NEXTCLOUD_URL", "http://caddy").rstrip("/")
response = httpx.request(
    spec["method"], base + spec["path"], headers=headers, content=body, timeout=60.0
)
print(response.status_code)
print(response.text)
"""


class RunFailed(RuntimeError):
    """A step did not answer the way a measuring run needs it to."""


@dataclass
class Settings:
    """The topology names and credentials of one run. Passwords are never recorded."""

    nc: str
    exapp: str
    base: str
    admin: str
    admin_password: str
    user: str
    user_password: str
    user2: str
    user2_password: str
    raw: Path


@dataclass
class Ledger:
    """What this run created, so the ``finally`` block removes exactly that."""

    tags: dict[str, str] = field(default_factory=dict)
    groups: list[str] = field(default_factory=list)
    files: list[tuple[str, str]] = field(default_factory=list)
    trash_users: set[str] = field(default_factory=set)
    disabled: list[str] = field(default_factory=list)
    config_set: bool = False


@dataclass
class Dav:
    """One DAV or OCS answer: status and the body text."""

    status: int
    body: str


_RAW: list[Path] = []


def now_stamp() -> str:
    """The moment of the run, in the shape the protocols of this project carry."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _dash_free(text: str) -> str:
    """Escape the dash code points U+2010 to U+2015 so the protocol stays free of them."""
    return "".join(f"\\u{ord(c):04x}" if 0x2010 <= ord(c) <= 0x2015 else c for c in text)


def record(line: str = "") -> None:
    """Print one protocol line and append it to the raw file."""
    text = _dash_free(line)
    print(text)
    if _RAW:
        with _RAW[0].open("a", encoding="utf-8") as handle:
            handle.write(text + "\n")


def section(title: str) -> None:
    """One heading per measured block."""
    record()
    record(title)


def run(argv: Sequence[str], *, stdin: str | None = None) -> tuple[int, str]:
    """One external command, no shell, fixed argument list; exit code and combined output."""
    finished = subprocess.run(  # noqa: S603 - a fixed argument list, never a shell
        list(argv),
        input=stdin,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return finished.returncode, (finished.stdout or "") + (finished.stderr or "")


def docker(*argv: str, stdin: str | None = None) -> tuple[int, str]:
    """One docker call; ``docker`` is on PATH by contract, as in every script here."""
    return run(["docker", *argv], stdin=stdin)


def occ(cfg: Settings, *argv: str, log: bool = True) -> tuple[int, str]:
    """One ``occ`` call inside the Nextcloud container, recorded with its verbatim output."""
    code, output = docker("exec", "-u", "www-data", cfg.nc, "php", "occ", *argv)
    output = output.strip()
    if log:
        shown = " ".join(_quote(a) for a in argv)
        record(f"$ php occ {shown}")
        for line in output.splitlines():
            record(f"  {line}")
        record(f"  [exit {code}]")
    return code, output


def _quote(arg: str) -> str:
    """Show an argv element the way a shell user would type it."""
    if arg and re.fullmatch(r"[A-Za-z0-9_./:=@,+-]+", arg):
        return arg
    return '"' + arg.replace('"', '\\"') + '"'


def php(cfg: Settings, snippet: str, *args: str) -> str:
    """Run one PHP snippet through stdin inside the Nextcloud container."""
    _code, output = docker(
        "exec",
        "-i",
        "-u",
        "www-data",
        "-w",
        "/var/www/html",
        cfg.nc,
        "php",
        "--",
        *args,
        stdin=snippet,
    )
    return output.strip()


def read_env_file(path: Path) -> dict[str, str]:
    """``KEY=value`` lines of an env file as a mapping. Never printed."""
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, _, value = stripped.partition("=")
        values[name.strip()] = value.strip()
    return values


def admin_password_from_compose(path: Path) -> str:
    """The admin password of the throwaway topology, read from the compose file."""
    if not path.is_file():
        return ""
    match = re.search(r"NEXTCLOUD_ADMIN_PASSWORD:\s*(\S+)", path.read_text(encoding="utf-8"))
    return match.group(1) if match else ""


# --- requests --------------------------------------------------------------------------------


def exapp(
    cfg: Settings,
    method: str,
    path: str,
    user: str,
    *,
    depth: int | None = None,
    body: bytes | None = None,
    ctype: str = "",
    ocs: bool = False,
) -> Dav:
    """One request from inside the ExApp container under the AppAPI header of ``user``."""
    spec = {
        "method": method,
        "path": path,
        "user": user,
        "depth": depth,
        "body": base64.b64encode(body).decode() if body else "",
        "ctype": ctype,
        "ocs": ocs,
    }
    arg = base64.b64encode(json.dumps(spec).encode()).decode()
    code, output = docker(
        "exec", "-i", cfg.exapp, "/app/.venv/bin/python", "-", arg, stdin=EXAPP_DAV_PROGRAM
    )
    first, _, rest = output.partition("\n")
    if code != 0 or not first.strip().isdigit():
        raise RunFailed(f"ExApp request {method} {path} failed: {output.strip()[:400]}")
    return Dav(int(first.strip()), rest.strip())


def basic(
    cfg: Settings,
    method: str,
    path: str,
    user: str,
    password: str,
    *,
    content: bytes | None = None,
    headers: dict[str, str] | None = None,
) -> Dav:
    """One request from the host with Basic-Auth of a test account."""
    response = httpx.request(
        method,
        cfg.base + path,
        auth=(user, password),
        content=content,
        headers=headers or {},
        timeout=TIMEOUT,
    )
    return Dav(response.status_code, response.text)


def curl(cfg: Settings, shown: str, argv: Sequence[str]) -> Dav:
    """The real curl program, recorded verbatim with the password replaced."""
    record(f"$ {shown}")
    code, output = run(["curl", "-s", "-w", "\n%{http_code}", *argv])
    body, _, status = output.rstrip().rpartition("\n")
    record(f"  status {status.strip()} [curl exit {code}]")
    for line in body.strip().splitlines():
        record(f"  {line}")
    if not status.strip().isdigit():
        raise RunFailed(f"curl gave no status: {output[:200]}")
    return Dav(int(status.strip()), body)


def record_dav(label: str, answer: Dav) -> None:
    """Status and body of one answer into the protocol."""
    record(f"{label}: status {answer.status}")
    for line in answer.body.splitlines():
        if line.strip():
            record(f"  {line}")


# --- XML ------------------------------------------------------------------------------------


def propfind_body(names: Sequence[tuple[str, str]]) -> bytes:
    """A PROPFIND body asking for the given ``(namespace, local)`` properties."""
    root = etree.Element(f"{{{DAV}}}propfind", nsmap=NSMAP)
    prop = etree.SubElement(root, f"{{{DAV}}}prop")
    for namespace, local in names:
        etree.SubElement(prop, f"{{{namespace}}}{local}")
    return etree.tostring(root, xml_declaration=True, encoding="utf-8")


LISTING_PROPS = (
    (OC, "id"),
    (OC, "display-name"),
    (OC, "user-visible"),
    (OC, "user-assignable"),
)
GROUPS_PROP = (OC, "groups")


@dataclass
class TagRow:
    """One tag of a listing, with the propstat status of each property."""

    name: str
    props: dict[str, str]
    status: dict[str, str]


def parse_listing(body: str) -> list[TagRow]:
    """The tags of a multistatus answer; property values and their propstat status."""
    rows: list[TagRow] = []
    if not body.strip().startswith("<"):
        return rows
    parser = etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False)
    tree = etree.fromstring(body.encode("utf-8"), parser=parser)
    for response in tree.iter(f"{{{DAV}}}response"):
        props: dict[str, str] = {}
        status: dict[str, str] = {}
        for propstat in response.iter(f"{{{DAV}}}propstat"):
            code = (propstat.findtext(f"{{{DAV}}}status") or "").strip()
            prop = propstat.find(f"{{{DAV}}}prop")
            if prop is None:
                continue
            for child in prop:
                local = etree.QName(child).localname
                props[local] = (child.text or "").strip()
                status[local] = code
        name = props.get("display-name", "")
        if name:
            rows.append(TagRow(name, props, status))
    return rows


def count_files(body: str) -> int | None:
    """Number of ``nc:object-id`` entries of type files in a Depth 0 answer."""
    if not body.strip().startswith("<"):
        return None
    parser = etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False)
    tree = etree.fromstring(body.encode("utf-8"), parser=parser)
    return sum(
        1
        for obj in tree.iter(f"{{{NC}}}object-id")
        if (obj.findtext(f"{{{NC}}}type") or "").strip() == "files"
    )


def find(rows: Sequence[TagRow], name: str) -> TagRow | None:
    """The row of one tag name, or None."""
    return next((row for row in rows if row.name == name), None)


# --- occ helpers ----------------------------------------------------------------------------


def tag_list(cfg: Settings) -> dict[str, str]:
    """All tags as ``name -> id``, read with ``occ tag:list --output=json`` (admin view)."""
    _code, output = occ(cfg, "tag:list", "--output=json", log=False)
    start = output.find("[") if output.find("[") != -1 else 0
    brace = output.find("{")
    if brace != -1 and (output.find("[") == -1 or brace < output.find("[")):
        start = brace
    try:
        data = json.loads(output[start:] or "[]")
    except json.JSONDecodeError:
        return {}
    result: dict[str, str] = {}
    items = data.items() if isinstance(data, dict) else enumerate(data)
    for key, value in items:
        if isinstance(value, dict):
            name = str(value.get("name", ""))
            result[name] = str(value.get("id", key))
    return result


def tag_add(cfg: Settings, ledger: Ledger, name: str, access: str) -> str | None:
    """``occ tag:add <name> <access> --output=json``; records the id for the cleanup."""
    _code, output = occ(cfg, "tag:add", name, access, "--output=json")
    match = re.search(r'"id"\s*:\s*"?(\d+)', output)
    if match:
        ledger.tags[name] = match.group(1)
        return match.group(1)
    return None


def fileid(cfg: Settings, user: str, password: str, path: str) -> str:
    """The fileid of one node of ``user``, read with PROPFIND Depth 0 under Basic-Auth."""
    answer = basic(
        cfg,
        "PROPFIND",
        f"/remote.php/dav/files/{user}/{path}",
        user,
        password,
        content=propfind_body([(OC, "fileid")]),
        headers={"Depth": "0", "Content-Type": "application/xml"},
    )
    match = re.search(r"<oc:fileid>(\d+)</oc:fileid>", answer.body)
    return match.group(1) if match else ""


def count_as(cfg: Settings, tag_id: str, user: str, label: str) -> Dav:
    """PROPFIND Depth 0 with ``nc:object-ids`` on one tag, impersonated as ``user``."""
    answer = exapp(
        cfg,
        "PROPFIND",
        f"/remote.php/dav/systemtags/{tag_id}",
        user,
        depth=0,
        body=propfind_body([(OC, "display-name"), (NC, "object-ids")]),
        ctype="application/xml",
    )
    record_dav(label, answer)
    return answer


def listing_as(cfg: Settings, user: str, label: str, *, groups: bool) -> tuple[Dav, list[TagRow]]:
    """PROPFIND Depth 1 on the tag collection impersonated as ``user`` (``""`` = app)."""
    props = [*LISTING_PROPS, GROUPS_PROP] if groups else list(LISTING_PROPS)
    answer = exapp(
        cfg,
        "PROPFIND",
        "/remote.php/dav/systemtags/",
        user,
        depth=1,
        body=propfind_body(props),
        ctype="application/xml",
    )
    record_dav(label, answer)
    rows = parse_listing(answer.body) if answer.status == 207 else []
    for row in rows:
        record(
            f"  TAG {row.name!a} visible={row.props.get('user-visible', '?')} "
            f"assignable={row.props.get('user-assignable', '?')} "
            f"groups={row.props.get('groups', '-')!r} "
            f"groups-status={row.status.get('groups', '-')!r}"
        )
    return answer, rows


# --- blocks ---------------------------------------------------------------------------------


def m1(cfg: Settings, _ledger: Ledger) -> None:
    section("== M1 ==")
    answer, _rows = listing_as(cfg, "", "PROPFIND Depth 1 /systemtags/ leerer Nutzer", groups=False)
    record(f"BEFUND M1 leerer AppAPI-Nutzer: status={answer.status}")


def m1b(cfg: Settings, _ledger: Ledger) -> None:
    section("== M1b ==")
    users = exapp(cfg, "GET", "/ocs/v2.php/apps/app_api/api/v1/users", "", ocs=True)
    record_dav("GET app_api users (leerer Nutzer)", users)
    count: int | str = "?"
    try:
        data = json.loads(users.body).get("ocs", {}).get("data", [])
        count = len(data)
    except (json.JSONDecodeError, AttributeError):
        pass
    _answer, rows = listing_as(cfg, cfg.user, f"PROPFIND Depth 1 als {cfg.user}", groups=False)
    seen = ",".join(sorted(ascii(r.name) for r in rows)) or "-"
    record(
        f"BEFUND M1b nutzerliste status={users.status} anzahl={count}; "
        f"liste als {cfg.user} status={_answer.status} tags={seen}"
    )


def m1c(cfg: Settings, ledger: Ledger) -> None:
    section("== M1c ==")
    occ(cfg, "user:disable", cfg.user2)
    ledger.disabled.append(cfg.user2)
    answer, _rows = listing_as(
        cfg, cfg.user2, f"PROPFIND Depth 1 als deaktiviertes {cfg.user2}", groups=False
    )
    occ(cfg, "user:enable", cfg.user2)
    _code, info = occ(cfg, "user:info", cfg.user2)
    if re.search(r"enabled:\s*true", info):
        ledger.disabled.remove(cfg.user2)
        record("CLEANUP konto-m1c: reaktiviert")
    record(f"BEFUND M1c deaktiviertes Konto impersoniert: status={answer.status}")


def m2(cfg: Settings, ledger: Ledger) -> None:
    section("== M2 ==")
    tag_add(cfg, ledger, TAG_M2_INVISIBLE, "invisible")
    rid = tag_add(cfg, ledger, TAG_M2_RESTRICTED, "restricted")
    occ(cfg, "group:add", GROUP_M2)
    ledger.groups.append(GROUP_M2)
    patch = (
        '<?xml version="1.0"?><d:propertyupdate xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns">'
        f"<d:set><d:prop><oc:groups>{GROUP_M2}</oc:groups></d:prop></d:set></d:propertyupdate>"
    )
    answer = basic(
        cfg,
        "PROPPATCH",
        f"/remote.php/dav/systemtags/{rid}",
        cfg.admin,
        cfg.admin_password,
        content=patch.encode(),
        headers={"Content-Type": "application/xml"},
    )
    record_dav(f"PROPPATCH oc:groups={GROUP_M2} auf {TAG_M2_RESTRICTED} (Basic admin)", answer)
    a_answer, a_rows = listing_as(cfg, cfg.admin, "PROPFIND Depth 1 als admin", groups=True)
    u_answer, u_rows = listing_as(cfg, cfg.user, f"PROPFIND Depth 1 als {cfg.user}", groups=True)
    a_inv = find(a_rows, TAG_M2_INVISIBLE)
    a_res = find(a_rows, TAG_M2_RESTRICTED)
    u_inv = find(u_rows, TAG_M2_INVISIBLE)
    u_res = find(u_rows, TAG_M2_RESTRICTED)
    admin_sees = "ja" if a_inv else "nein"
    admin_gids = "ja" if a_res and GROUP_M2 in a_res.props.get("groups", "") else "nein"
    user_gstatus = u_res.status.get("groups", "-") if u_res else "-"
    record(
        f"BEFUND M2 admin status={a_answer.status} sieht-unsichtbar={admin_sees} "
        f"gids={admin_gids} ({a_res.props.get('groups', '-') if a_res else '-'!r}); "
        f"{cfg.user} status={u_answer.status} unsichtbar-gelistet={'ja' if u_inv else 'nein'} "
        f"groups-propstat={user_gstatus!r}"
    )


def m2b(cfg: Settings, _ledger: Ledger) -> None:
    section("== M2b ==")
    path = "/ocs/v2.php/cloud/groups/admin/users"
    results: list[str] = []
    for user in (cfg.admin, cfg.user):
        answer = exapp(cfg, "GET", path, user, ocs=True)
        record_dav(f"GET {path} als {user}", answer)
        meta = "?"
        with contextlib.suppress(json.JSONDecodeError, KeyError, TypeError):
            meta = str(json.loads(answer.body)["ocs"]["meta"]["statuscode"])
        results.append(f"{user} status={answer.status} ocs={meta}")
    record("BEFUND M2b " + "; ".join(results))


def _put_file(cfg: Settings, ledger: Ledger, user: str, password: str, name: str) -> Dav:
    answer = basic(
        cfg,
        "PUT",
        f"/remote.php/dav/files/{user}/{name}",
        user,
        password,
        content=b"Testdatei 29-01, ohne Inhalt von Belang.\n",
    )
    record(f"PUT /remote.php/dav/files/{user}/{name} (Basic {user}): status {answer.status}")
    if answer.status in (201, 204):
        ledger.files.append((user, name))
    return answer


def m3(cfg: Settings, ledger: Ledger) -> None:
    section("== M3 ==")
    files = {cfg.user: f"m3-{cfg.user}.txt", cfg.user2: f"m3-{cfg.user2}.txt"}
    _put_file(cfg, ledger, cfg.user, cfg.user_password, files[cfg.user])
    _put_file(cfg, ledger, cfg.user2, cfg.user2_password, files[cfg.user2])
    tid = tag_add(cfg, ledger, TAG_M3, "public")
    path_forms: list[str] = []
    for user, name in files.items():
        code, _out = occ(cfg, "tag:files:add", f"{user}/files/{name}", TAG_M3, "public")
        form = "user/files/pfad"
        if code != 0:
            code, _out = occ(cfg, "tag:files:add", f"/{user}/files/{name}", TAG_M3, "public")
            form = "/user/files/pfad"
        path_forms.append(f"{user}:{form}:exit{code}")
    answer = count_as(cfg, str(tid), cfg.admin, f"PROPFIND Depth 0 {TAG_M3} als admin")
    record(
        f"BEFUND M3 files-object-ids als admin={count_files(answer.body)} "
        f"status={answer.status} pfadform={','.join(path_forms)}"
    )


def m3b(cfg: Settings, ledger: Ledger) -> None:
    section("== M3b ==")
    tid = ledger.tags.get(TAG_M3, "")
    answer = count_as(cfg, tid, cfg.user, f"PROPFIND Depth 0 {TAG_M3} als {cfg.user}")
    record(f"BEFUND M3b als {cfg.user} status={answer.status} files={count_files(answer.body)}")


def m4(cfg: Settings, ledger: Ledger) -> None:
    section("== M4 ==")
    tid = ledger.tags.get(TAG_M3, "")
    name = f"m3-{cfg.user}.txt"
    before = count_files(count_as(cfg, tid, cfg.admin, "vor dem Löschen").body)
    answer = basic(
        cfg, "DELETE", f"/remote.php/dav/files/{cfg.user}/{name}", cfg.user, cfg.user_password
    )
    record(f"DELETE /remote.php/dav/files/{cfg.user}/{name} (Basic): status {answer.status}")
    ledger.trash_users.add(cfg.user)
    if answer.status in (204, 200):
        ledger.files.remove((cfg.user, name))
    trashed = count_files(count_as(cfg, tid, cfg.admin, "im Papierkorb").body)
    occ(cfg, "trashbin:cleanup", cfg.user)
    after = count_files(count_as(cfg, tid, cfg.admin, "nach trashbin:cleanup").body)
    record(f"BEFUND M4 vor={before} papierkorb={trashed} endgültig-gelöscht={after}")


def m6(cfg: Settings, ledger: Ledger) -> None:
    section("== M6 ==")
    created: dict[str, str] = {}
    for name in (TAG_M6_SPACE, TAG_M6_JOINED, TAG_M6_DASH, TAG_M6_BASE):
        created[name] = "ja" if tag_add(cfg, ledger, name, "public") else "nein"
    upper = tag_add(cfg, ledger, TAG_M6_UPPER, "public")
    created[TAG_M6_UPPER] = "ja" if upper else "nein"
    _code, _output = occ(cfg, "tag:list", "--output=json")
    stored = tag_list(cfg)
    parts: list[str] = []
    for name, made in created.items():
        tid = ledger.tags.get(name, "")
        match = next((n for n, i in stored.items() if i == tid), None) if tid else None
        parts.append(f"{name!a} angelegt={made} gespeichert={ascii(match) if match else '-'}")
    record("BEFUND M6 " + "; ".join(parts))


def m7(cfg: Settings, ledger: Ledger) -> None:
    section("== M7 ==")
    tid = tag_add(cfg, ledger, TAG_GUIDE, "public")
    answer = basic(
        cfg,
        "MKCOL",
        f"/remote.php/dav/files/{cfg.user}/{FOLDER_GUIDE}",
        cfg.user,
        cfg.user_password,
    )
    record(f"MKCOL /remote.php/dav/files/{cfg.user}/{FOLDER_GUIDE} (Basic): status {answer.status}")
    if answer.status == 201:
        ledger.files.append((cfg.user, FOLDER_GUIDE))
    code, output = occ(
        cfg, "tag:files:add", f"{cfg.user}/files/{FOLDER_GUIDE}", TAG_GUIDE, "public"
    )
    added = next((ln.strip() for ln in output.splitlines() if "added" in ln.lower()), "-")
    check = basic(
        cfg,
        "PROPFIND",
        f"/remote.php/dav/files/{cfg.user}/{FOLDER_GUIDE}",
        cfg.user,
        cfg.user_password,
        content=propfind_body([(NC, "system-tags")]),
        headers={"Depth": "0", "Content-Type": "application/xml"},
    )
    record_dav(f"PROPFIND nc:system-tags auf {FOLDER_GUIDE} (Basic {cfg.user})", check)
    visible = "ja" if f">{TAG_GUIDE}<" in check.body else "nein"
    record(
        f"BEFUND M7 id={tid} tag:files:add exit={code} ausgabe={added!r} "
        f"tag-am-ordner-sichtbar={visible}"
    )
    if tid:
        occ(cfg, "tag:delete", tid)
        if TAG_GUIDE not in tag_list(cfg):
            ledger.tags.pop(TAG_GUIDE, None)


def m8(cfg: Settings, ledger: Ledger) -> None:
    section("== M8 ==")
    steps: list[str] = []
    code, _o = occ(cfg, "group:add", GROUP_GUIDE)
    ledger.groups.append(GROUP_GUIDE)
    steps.append(f"group:add exit={code}")
    code, _o = occ(cfg, "group:adduser", GROUP_GUIDE, cfg.user)
    steps.append(f"group:adduser exit={code}")
    tid = tag_add(cfg, ledger, TAG_GUIDE, "restricted")
    steps.append(f"tag:add restricted id={tid}")

    pw = cfg.admin_password
    patch = (
        '<?xml version="1.0"?><d:propertyupdate xmlns:d="DAV:" '
        'xmlns:oc="http://owncloud.org/ns"><d:set><d:prop>'
        f"<oc:groups>{GROUP_GUIDE}</oc:groups></d:prop></d:set></d:propertyupdate>"
    )
    url = f"{cfg.base}/remote.php/dav/systemtags/{tid}"
    shown = (
        f'curl -u {cfg.admin}:<passwort> -X PROPPATCH "{url}" '
        f"-H \"Content-Type: application/xml\" --data '{patch}'"
    )
    answer = curl(
        cfg,
        shown,
        [
            "-u",
            f"{cfg.admin}:{pw}",
            "-X",
            "PROPPATCH",
            url,
            "-H",
            "Content-Type: application/xml",
            "--data",
            patch,
        ],
    )
    steps.append(f"PROPPATCH={answer.status}")

    payload = json.dumps(
        {"name": TAG_M8_POST, "userVisible": True, "userAssignable": False, "groups": GROUP_GUIDE},
        separators=(",", ":"),
    )
    url = f"{cfg.base}/remote.php/dav/systemtags/"
    shown = (
        f'curl -u {cfg.admin}:<passwort> -X POST "{url}" '
        f"-H \"Content-Type: application/json\" -d '{payload}'"
    )
    answer = curl(
        cfg,
        shown,
        [
            "-u",
            f"{cfg.admin}:{pw}",
            "-X",
            "POST",
            url,
            "-H",
            "Content-Type: application/json",
            "-d",
            payload,
        ],
    )
    steps.append(f"POST={answer.status}")
    post_id = tag_list(cfg).get(TAG_M8_POST)
    if post_id:
        ledger.tags[TAG_M8_POST] = post_id

    _a, rows = listing_as(cfg, cfg.admin, "PROPFIND Depth 1 als admin (Rücklesen)", groups=True)
    for name in (TAG_GUIDE, TAG_M8_POST):
        row = find(rows, name)
        steps.append(f"gids[{name}]={row.props.get('groups', '-') if row else '-'!r}")

    alice_id = fileid(cfg, cfg.user, cfg.user_password, FOLDER_GUIDE)
    bob_id = fileid(cfg, cfg.user2, cfg.user2_password, f"m3-{cfg.user2}.txt")
    for user, password, obj in (
        (cfg.user, cfg.user_password, alice_id),
        (cfg.user2, cfg.user2_password, bob_id),
    ):
        answer = basic(
            cfg, "PUT", f"/remote.php/dav/systemtags-relations/files/{obj}/{tid}", user, password
        )
        record_dav(f"PUT systemtags-relations/files/<fileid>/{tid} als {user}", answer)
        steps.append(f"zuweisen[{user}]={answer.status}")

    def create_as_user2(name: str, label: str) -> int:
        body = json.dumps({"name": name, "userVisible": True, "userAssignable": True})
        answer = basic(
            cfg,
            "POST",
            "/remote.php/dav/systemtags/",
            cfg.user2,
            cfg.user2_password,
            content=body.encode(),
            headers={"Content-Type": "application/json"},
        )
        record_dav(f"POST /systemtags/ {name} als {cfg.user2} ({label})", answer)
        made = tag_list(cfg).get(name)
        if made:
            ledger.tags[name] = made
        return answer.status

    steps.append(f"anlegen[{cfg.user2},ohne-schalter]={create_as_user2(TAG_M8_BOB_BEFORE, 'vor')}")
    code, _o = occ(
        cfg,
        "config:app:set",
        *CONFIG_KEY,
        "--value=true",
        "--type=boolean",
    )
    if code != 0:
        code, _o = occ(cfg, "config:app:set", *CONFIG_KEY, "--value=true")
    ledger.config_set = True
    steps.append(f"config:app:set exit={code}")
    occ(cfg, "config:app:get", *CONFIG_KEY)
    steps.append(f"anlegen[{cfg.user2},mit-schalter]={create_as_user2(TAG_M8_BOB_AFTER, 'nach')}")
    occ(cfg, "config:app:delete", *CONFIG_KEY)
    code, _o = occ(cfg, "config:app:get", *CONFIG_KEY)
    if code != 0:
        ledger.config_set = False
        record("CLEANUP config restrict_creation_to_admin: entfernt")
    steps.append(f"config:app:get-nach-delete exit={code}")
    record("BEFUND M8 " + "; ".join(steps))


def m9(cfg: Settings, _ledger: Ledger) -> None:
    section("== M9 ==")
    _c, info = docker(
        "exec", cfg.nc, "grep", "-n", "-A2", "<admin>", "apps/systemtags/appinfo/info.xml"
    )
    record("$ grep -n -A2 '<admin>' apps/systemtags/appinfo/info.xml")
    for line in info.strip().splitlines():
        record(f"  {line}")
    _c, section_src = docker(
        "exec", cfg.nc, "grep", "-n", "-A2", "getSection", "apps/systemtags/lib/Settings/Admin.php"
    )
    record("$ grep -n -A2 getSection apps/systemtags/lib/Settings/Admin.php")
    for line in section_src.strip().splitlines():
        record(f"  {line}")
    labels: dict[str, dict[str, str]] = {}
    for lang in ("de", "de_DE", "fr"):
        labels[lang] = {}
        for key, path in (
            ("Collaborative tags", f"apps/systemtags/l10n/{lang}.json"),
            ("Basic settings", f"lib/l10n/{lang}.json"),
            ("Administration settings", f"lib/l10n/{lang}.json"),
            ("Administration settings", f"core/l10n/{lang}.json"),
        ):
            _c, raw = docker("exec", cfg.nc, "cat", path)
            try:
                value = json.loads(raw)["translations"].get(key)
            except (json.JSONDecodeError, KeyError):
                value = None
            record(f"$ l10n {path} [{key!r}] -> {value!r}")
            if value and key not in labels[lang]:
                labels[lang][key] = value
        _c, groups = docker(
            "exec",
            cfg.nc,
            "grep",
            "-o",
            '"[^"]*[Gg]roup[^"]*" *: *"[^"]*"',
            f"apps/systemtags/l10n/{lang}.json",
        )
        for line in groups.strip().splitlines():
            record(f"  {lang} systemtags l10n: {line}")

    def path_for(lang: str) -> str:
        got = labels.get(lang, {})
        return " > ".join(
            got.get(k, "?")
            for k in ("Administration settings", "Basic settings", "Collaborative tags")
        )

    record(
        "BEFUND M9 menüpfad EN='Administration settings > Basic settings > Collaborative tags'; "
        f"DE='{path_for('de')}'; DE_Sie='{path_for('de_DE')}'; FR='{path_for('fr')}'"
    )


BLOCKS: tuple[tuple[str, Callable[[Settings, Ledger], None]], ...] = (
    ("M1", m1),
    ("M1b", m1b),
    ("M1c", m1c),
    ("M2", m2),
    ("M2b", m2b),
    ("M3", m3),
    ("M3b", m3b),
    ("M4", m4),
    ("M6", m6),
    ("M7", m7),
    ("M8", m8),
    ("M9", m9),
)


# --- cleanup --------------------------------------------------------------------------------


def cleanup(cfg: Settings, ledger: Ledger) -> None:
    """Remove what the run created and read each removal back."""
    section("== CLEANUP ==")
    for user in list(ledger.disabled):
        occ(cfg, "user:enable", user)
        _c, info = occ(cfg, "user:info", user)
        if re.search(r"enabled:\s*true", info):
            record(f"CLEANUP konto {user}: reaktiviert")
    if ledger.config_set:
        occ(cfg, "config:app:delete", *CONFIG_KEY)
        code, _o = occ(cfg, "config:app:get", *CONFIG_KEY)
        if code != 0:
            record("CLEANUP config restrict_creation_to_admin: entfernt")
    for tid in list(ledger.tags.values()):
        occ(cfg, "tag:delete", tid)
    remaining = tag_list(cfg)
    occ(cfg, "tag:list", "--output=json")
    for name in ledger.tags:
        if name not in remaining:
            record(f"CLEANUP tag {name!a}: entfernt")
        else:
            record(f"FEHLER tag {name!a} noch vorhanden")
    for group in ledger.groups:
        occ(cfg, "group:delete", group)
        _c, listing = occ(cfg, "group:list", "--output=json", log=False)
        try:
            present = group in json.loads(listing)
        except json.JSONDecodeError:
            present = True
        record(f"CLEANUP gruppe {group}: entfernt" if not present else f"FEHLER gruppe {group}")
    passwords = {cfg.user: cfg.user_password, cfg.user2: cfg.user2_password}
    for user, name in ledger.files:
        answer = basic(cfg, "DELETE", f"/remote.php/dav/files/{user}/{name}", user, passwords[user])
        ledger.trash_users.add(user)
        record(f"DELETE /remote.php/dav/files/{user}/{name}: status {answer.status}")
    for user in sorted(ledger.trash_users):
        occ(cfg, "trashbin:cleanup", user)
    for user, name in ledger.files:
        back = basic(
            cfg,
            "PROPFIND",
            f"/remote.php/dav/files/{user}/{name}",
            user,
            passwords[user],
            headers={"Depth": "0"},
        )
        if back.status == 404:
            record(f"CLEANUP datei {user}/{name}: 404")
        else:
            record(f"FEHLER datei {user}/{name} status {back.status}")


# --- entry ----------------------------------------------------------------------------------


def preflight(cfg: Settings) -> list[str]:
    """Names of this run that already exist on the instance (stop condition)."""
    clash: list[str] = []
    tags = tag_list(cfg)
    clash.extend(f"tag {n!a}" for n in RUN_TAGS if n in tags)
    clash.extend(f"tag {n!a}" for n in tags if n.casefold() == TAG_M6_UPPER.casefold())
    _c, listing = occ(cfg, "group:list", "--output=json", log=False)
    try:
        groups = json.loads(listing)
    except json.JSONDecodeError:
        groups = {}
    clash.extend(f"gruppe {g}" for g in RUN_GROUPS if g in groups)
    return clash


def measure(args: argparse.Namespace) -> int:
    """Measure M1 to M9 (without M5) and append the raw protocol."""
    env = {**read_env_file(Path(".env.nc35")), **os.environ}
    cfg = Settings(
        nc=args.nc_container,
        exapp=args.exapp_container,
        base=args.base_url.rstrip("/"),
        admin=args.admin,
        admin_password=env.get("NC35_ADMIN_PASSWORD") or admin_password_from_compose(COMPOSE_FILE),
        user=env.get("NC_MCP_TEST_USER", ""),
        user_password=env.get("NC_MCP_TEST_APP_PASSWORD", ""),
        user2=env.get("NC_MCP_TEST_USER2", ""),
        user2_password=env.get("NC_MCP_TEST_APP_PASSWORD2", ""),
        raw=Path(args.raw),
    )
    missing = [
        n
        for n, v in (
            ("admin password", cfg.admin_password),
            ("NC_MCP_TEST_USER", cfg.user),
            ("NC_MCP_TEST_APP_PASSWORD", cfg.user_password),
            ("NC_MCP_TEST_USER2", cfg.user2),
            ("NC_MCP_TEST_APP_PASSWORD2", cfg.user2_password),
        )
        if not v
    ]
    if missing:
        print(f"missing configuration: {', '.join(missing)}", file=sys.stderr)
        return 2
    cfg.raw.parent.mkdir(parents=True, exist_ok=True)
    _RAW.append(cfg.raw)

    record()
    record("=" * 78)
    record(f"LAUF 29-01 exclusion_evidence measure {now_stamp()}")
    _c, head = run(["git", "rev-parse", "--short", "HEAD"])
    record(f"git HEAD {head.strip()}")
    record(f"konten: admin={cfg.admin} nutzer={cfg.user} nutzer2={cfg.user2}")
    occ(cfg, "status")

    clash = preflight(cfg)
    if clash:
        record(f"ABBRUCH vorbestehend: {', '.join(clash)} (keine Änderung vorgenommen)")
        return 2

    ledger = Ledger()
    failed: list[str] = []
    try:
        for name, block in BLOCKS:
            try:
                block(cfg, ledger)
            except (RunFailed, httpx.HTTPError, etree.XMLSyntaxError) as exc:
                record(f"FEHLER {name}: {type(exc).__name__}: {exc}")
                failed.append(name)
    finally:
        cleanup(cfg, ledger)
    record(f"ENDE LAUF 29-01 {now_stamp()} fehlgeschlagen={','.join(failed) or '-'}")
    return 1 if failed else 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    sub = parser.add_subparsers(dest="command", required=True)
    cmd = sub.add_parser("measure", help="measure M1 to M9 (without M5) against nc35")
    cmd.add_argument("--nc-container", default=NC_CONTAINER)
    cmd.add_argument("--exapp-container", default=EXAPP_CONTAINER)
    cmd.add_argument("--base-url", default=BASE_URL)
    cmd.add_argument("--admin", default=ADMIN)
    cmd.add_argument("--raw", default=str(RAW_FILE), help="appended, never overwritten")
    cmd.set_defaults(func=measure)
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
