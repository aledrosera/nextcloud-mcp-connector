"""Live proof of ``occ mcp_connector:exclusion:check`` against a real Nextcloud (plan 29-06).

Success criteria 1 and 2 of phase 29 ask for a measurement, not a unit test: the command
names every step with its outcome on a real instance, misconfigurations included, and it
changes nothing. This module builds each case with ``occ`` and WebDAV (the harness only;
``src/`` never writes a tag, EXCL-07), runs the command once as text and once with
``--json``, and around every single invocation dumps the four tables a tag lives in:
``systemtag``, ``systemtag_object_mapping``, ``systemtag_group`` and the ``appconfig`` rows
of the ``systemtags`` app, plus the account state an impersonated read could touch:
``preferences`` (last seen, last login), ``storages``, ``mounts`` and ``filecache``
(29-REVIEW WR-04; without ``--admin`` the reads run as real accounts of the instance). Each
dump carries the row count and a SHA-256 of the sorted rows; a difference is written as a
unified diff and fails the case (T-29-21).

The command runs without a user session: it is plain ``occ`` inside
:data:`topology.NC_CONTAINER`, no login, no app password. The module creates its own
administrator ``chkadm<hex8>`` with a random password (passed through the environment of
``docker exec``, never through an argument and never into the protocol) and deletes it in
``finally``, reading the removal back (T-29-22). So the run depends on no administrator of
the instance and on no administrator password variable.

The full output of every invocation goes into
``.planning/phases/29-pr-fkommando-und-doku/raw/29-06-live-beweis.txt`` verbatim: those
lines are the raw evidence the documentation of plan 29-07 quotes (D-29-08).

Run it against the nc35 topology with::

    set -a && . ./.env.nc35 && set +a
    export NC_MCP_E2E_COMPOSE_FILE=compose.nc35.yml NC_MCP_E2E_PROJECT=nc-mcp-nc35 ...
    PYTHONUTF8=1 uv run pytest tests/integration/test_exclusion_check_live.py -m integration -s
"""

import difflib
import json
import os
import re
import secrets
import subprocess
import time
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import canary_world as cw
import pytest
import topology

from mcp_connector.nextcloud import exclusion_audit

pytestmark = [pytest.mark.integration]

RAW_DIR = (
    Path(__file__).resolve().parents[2]
    / ".planning"
    / "phases"
    / "29-pr-fkommando-und-doku"
    / "raw"
)

#: Appended, never overwritten. ``NC_MCP_EXCLUSION_LIVE_RAW`` names another file in the raw
#: directory, so a later run (29-REVIEW WR-05) leaves the evidence of an earlier one as it was.
RAW = RAW_DIR / (os.environ.get("NC_MCP_EXCLUSION_LIVE_RAW", "").strip() or "29-06-live-beweis.txt")
COMMAND = "mcp_connector:exclusion:check"
TAG = exclusion_audit.EXCLUDE_TAG
TABLES = (
    "systemtag",
    "systemtag_object_mapping",
    "systemtag_group",
    "appconfig",
    "preferences",
    "storages",
    "mounts",
    "filecache",
)

#: Reads the eight tables through the query builder and prints one JSON document: per table
#: the row count, a SHA-256 over the rows sorted by all columns, and the rows themselves.
#: Bootstraps Nextcloud the way ``scripts/tag_spike.py`` does (``_PHP_BOOT``, copied).
PHP_DUMP_TABLES = r"""<?php
require_once '/var/www/html/lib/base.php';
$db = \OCP\Server::get(\OCP\IDBConnection::class);
$out = [];
foreach (['systemtag', 'systemtag_object_mapping', 'systemtag_group', 'appconfig',
          'preferences', 'storages', 'mounts', 'filecache'] as $t) {
    $qb = $db->getQueryBuilder();
    $qb->select('*')->from($t);
    if ($t === 'appconfig') {
        $qb->where($qb->expr()->eq('appid', $qb->createNamedParameter('systemtags')));
    }
    $rows = [];
    $result = $qb->executeQuery();
    while ($row = $result->fetch()) {
        ksort($row);
        $rows[] = array_map(fn ($v) => $v === null ? null : (string)$v, $row);
    }
    $result->closeCursor();
    usort($rows, fn ($a, $b) => strcmp(json_encode($a), json_encode($b)));
    $out[$t] = [
        'rows' => count($rows),
        'sha256' => hash('sha256', json_encode($rows)),
        'dump' => $rows,
    ];
}
echo "\n", json_encode($out), "\n";
"""


def log(line: str) -> None:
    cw.record(RAW, line)


def git_head() -> str:
    finished = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    return finished.stdout.strip() or "unbekannt"


def _json_of(output: str) -> Any:
    start = min((i for i in (output.find("{"), output.find("[")) if i >= 0), default=-1)
    assert start >= 0, f"no JSON in: {output[:300]}"
    return json.loads(output[start:])


# --- tables -----------------------------------------------------------------------------


def dump_tables() -> dict[str, Any]:
    """The eight tables as :data:`PHP_DUMP_TABLES` prints them."""
    finished = subprocess.run(  # noqa: S603 - fixed argv, test harness
        [  # noqa: S607
            "docker",
            "exec",
            "-i",
            "-u",
            "www-data",
            "-w",
            "/var/www/html",
            topology.NC_CONTAINER,
            "php",
            "--",
        ],
        input=PHP_DUMP_TABLES,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=False,
    )
    lines = [line for line in (finished.stdout or "").splitlines() if line.startswith("{")]
    assert finished.returncode == 0, f"table dump failed: {(finished.stderr or '')[:300]}"
    assert lines, f"table dump printed no JSON: {(finished.stdout or '')[:300]}"
    data = json.loads(lines[-1])
    assert set(data) == set(TABLES), sorted(data)
    return data


def compare(case: str, before: dict[str, Any], after: dict[str, Any]) -> None:
    """One ``TABELLE`` line per table; a unified diff and a failure when one differs."""
    unequal: list[str] = []
    for name in TABLES:
        old, new = before[name], after[name]
        same = old["sha256"] == new["sha256"] and old["rows"] == new["rows"]
        log(
            f"TABELLE {name} vorher={old['rows']}/{old['sha256'][:12]} "
            f"nachher={new['rows']}/{new['sha256'][:12]} gleich={'ja' if same else 'nein'}"
        )
        if not same:
            unequal.append(name)
            diff = difflib.unified_diff(
                [json.dumps(row, sort_keys=True) for row in old["dump"]],
                [json.dumps(row, sort_keys=True) for row in new["dump"]],
                fromfile=f"{name} vorher",
                tofile=f"{name} nachher",
                lineterm="",
            )
            for line in diff:
                log(f"  {line}")
    assert not unequal, f"case {case}: exclusion:check changed {unequal}"


# --- the command ------------------------------------------------------------------------


def run_check(*options: str) -> str:
    """One invocation; the command line and the complete output go into the protocol."""
    output = cw.occ(COMMAND, *options)
    log(f"$ php occ {' '.join([COMMAND, *options])}")
    for line in output.splitlines():
        log(f"  {line}")
    return output


@dataclass(frozen=True)
class Answer:
    """Text and JSON of the same check, each taken between two table dumps."""

    text: str
    doc: dict[str, Any]


def checked(case: str, forbidden: list[str], *options: str) -> Answer:
    """Text and ``--json`` of one option set, each between two dumps, compared, scanned."""
    before = dump_tables()
    text = run_check(*options)
    compare(case, before, dump_tables())
    before = dump_tables()
    raw_json = run_check(*options, "--json")
    compare(case, before, dump_tables())
    doc = _json_of(raw_json)
    assert isinstance(doc, dict), raw_json[:300]
    for value in forbidden:
        pattern = re.compile(rf"(?<![0-9A-Za-z]){re.escape(value)}(?![0-9A-Za-z])")
        found = bool(pattern.search(text) or pattern.search(raw_json))
        cw.check(RAW, "T-29-23", "exclusion:check", case, not found, "Text und JSON")
    return Answer(text=text, doc=doc)


def step_outcome(doc: dict[str, Any], step: str) -> str:
    for entry in doc.get("steps") or []:
        if entry.get("step") == step:
            return str(entry.get("outcome"))
    return "fehlt"


def fall(case: str, doc: dict[str, Any]) -> None:
    log(f"FALL {case} passed={doc.get('passed')} mode={doc.get('mode')} diff=leer")


# --- scaffolding ------------------------------------------------------------------------


def tag_names() -> dict[str, str]:
    """``{id: name}`` of every tag ``occ tag:list`` knows."""
    data = _json_of(cw.occ("tag:list", "--output=json") or "[]")
    if isinstance(data, dict):
        return {str(k): str(v.get("name", "")) for k, v in data.items() if isinstance(v, dict)}
    return {}


def add_tag(cleanup: cw.Cleanup, name: str, access: str) -> str:
    created = _json_of(cw.occ("tag:add", name, access, "--output=json"))
    tag_id = str(created.get("id") or "")
    assert tag_id.isdigit(), f"occ tag:add gave no id: {created}"
    cleanup.add(
        f"tag {name}",
        lambda: cw.occ("tag:delete", tag_id, check_status=False),
        lambda: "entfernt" if tag_id not in tag_names() else "noch da",
    )
    return tag_id


def add_file(cleanup: cw.Cleanup, harness: cw.Harness, name: str) -> str:
    """A file of the test account below its home; returns the ``occ`` path form."""
    cleanup.add(
        f"papierkorb {name}",
        lambda: harness.purge_trash(name),
        lambda: "leer" if not harness.trash_entries(name) else "noch da",
    )
    path = f"/{name}"
    harness.put(path, b"exclusion check live proof\n")
    cleanup.add_path(harness, path)
    return f"{harness.user}/files/{name}"


def assign(occ_path: str, name: str) -> None:
    cw.occ("tag:files:add", occ_path, name, "public")


def finish(cleanup: cw.Cleanup) -> None:
    lines = cleanup.run()
    for line in lines:
        log(line)
    bad = [line for line in lines if not cw.cleanup_ok(line)]
    assert not bad, bad


def account_gone(uid: str) -> str:
    output = cw.occ("user:info", uid, check_status=False)
    return "entfernt" if "not found" in output.lower() else "noch da"


def group_gone(gid: str) -> str:
    groups = _json_of(cw.occ("group:list", "--output=json") or "{}")
    return "entfernt" if gid not in groups else "noch da"


# --- fixtures ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Admin:
    uid: str
    password: str


@pytest.fixture(scope="module")
def env() -> cw.LiveEnv:
    live = cw.live_env()
    listing = cw.occ("list", "mcp_connector", check_status=False)
    if COMMAND not in listing:
        cw.skip_or_fail(f"{COMMAND} is not registered; ExApp aus aktuellem Quellstand neu bauen")
    relevant = (exclusion_audit.KIND_EXACT, exclusion_audit.KIND_VARIANT)
    names = [name for name in tag_names().values() if exclusion_audit.kind_of(name) in relevant]
    if names:
        cw.skip_or_fail(f"the instance is not clean, it carries {names}")
    version = next(
        (line.strip() for line in cw.occ("status").splitlines() if "versionstring" in line),
        "versionstring: unbekannt",
    )
    log("")
    log(
        f"# 29-06 exclusion:check live {time.strftime('%Y-%m-%d %H:%M:%S %z')} "
        f"head={git_head()} container={topology.NC_CONTAINER} {version}"
    )
    return live


@pytest.fixture(scope="module")
def admin(env: cw.LiveEnv) -> Iterator[Admin]:
    """An administrator of this run only; its password never reaches an argv or the protocol."""
    del env
    uid = f"chkadm{uuid.uuid4().hex[:8]}"
    password = f"Chk-{secrets.token_urlsafe(24)}-9a"
    try:
        finished = subprocess.run(  # noqa: S603 - fixed argv, test harness
            [  # noqa: S607
                "docker",
                "exec",
                "-e",
                "OC_PASS",
                "-u",
                "www-data",
                topology.NC_CONTAINER,
                "php",
                "occ",
                "user:add",
                "--password-from-env",
                uid,
            ],
            env={**os.environ, "OC_PASS": password},
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        assert finished.returncode == 0, f"user:add failed: {(finished.stdout or '')[:200]}"
        cw.occ("group:adduser", "admin", uid)
        log("ADMIN-KONTO eigenes Konto angelegt, Gruppe admin, Passwort nicht protokolliert")
        yield Admin(uid=uid, password=password)
    finally:
        cw.occ("user:delete", uid, check_status=False)
        line = f"CLEANUP admin-konto: {account_gone(uid)}"
        log(line)
        assert cw.cleanup_ok(line), line


@pytest.fixture
def harness(env: cw.LiveEnv) -> Iterator[cw.Harness]:
    h = cw.Harness(env)
    try:
        yield h
    finally:
        h.close()


def forbidden_values(env: cw.LiveEnv, admin: Admin, *extra: str) -> list[str]:
    """What no output may carry: the accounts of the run and, per case, file traces."""
    values = [admin.uid, env.user, *extra]
    if env.user2:
        values.append(env.user2)
    return values


def run_case(case: str, body: Callable[[cw.Cleanup], None]) -> None:
    log(f"== FALL {case} ==")
    cleanup = cw.Cleanup()
    try:
        body(cleanup)
    finally:
        finish(cleanup)


# --- cases ------------------------------------------------------------------------------


def test_a_no_tag(env: cw.LiveEnv, admin: Admin) -> None:
    def body(_: cw.Cleanup) -> None:
        bad = forbidden_values(env, admin)
        named = checked("A", bad, f"--admin={admin.uid}")
        assert named.doc["passed"] is True, named.doc
        assert named.doc["mode"] == exclusion_audit.MODE_NONE, named.doc
        assert "tag:add kein-ki public" in named.text
        anonymous = checked("A", bad)
        assert anonymous.doc["passed"] is True, anonymous.doc
        assert anonymous.doc["admin_checked"] is False, anonymous.doc
        assert "no visible kein-ki tag" in anonymous.text
        assert "tag:add kein-ki public" in anonymous.text
        first = anonymous.text.index("to also check invisible tags")
        assert first < anonymous.text.index("tag:add kein-ki public")
        fall("A", named.doc)

    run_case("A", body)


def test_b_self_service_and_g_without_admin(
    env: cw.LiveEnv, admin: Admin, harness: cw.Harness
) -> None:
    stem = f"chk29b{uuid.uuid4().hex[:8]}"

    def body(cleanup: cw.Cleanup) -> None:
        add_tag(cleanup, TAG, "public")
        occ_path = add_file(cleanup, harness, f"{stem}.txt")
        fileid = harness.fileid(f"/{stem}.txt")
        assign(occ_path, TAG)
        bad = forbidden_values(env, admin, stem, occ_path, fileid)
        named = checked("B", bad, f"--admin={admin.uid}")
        assert named.doc["passed"] is True, named.doc
        assert named.doc["mode"] == exclusion_audit.MODE_SELF_SERVICE, named.doc
        assert named.doc["assigned"] == 1, named.doc
        fall("B", named.doc)
        anonymous = checked("G", bad)
        assert anonymous.doc["admin_checked"] is False, anonymous.doc
        assert anonymous.doc["passed"] is True, anonymous.doc
        assert "were not checked" in anonymous.text
        fall("G", anonymous.doc)

    run_case("B und G", body)


def test_c_organisation_mode(env: cw.LiveEnv, admin: Admin) -> None:
    gid = f"ki-verantwortung-{uuid.uuid4().hex[:6]}"

    def body(cleanup: cw.Cleanup) -> None:
        cw.occ("group:add", gid)
        cleanup.add(
            f"gruppe {gid}",
            lambda: cw.occ("group:delete", gid, check_status=False),
            lambda: group_gone(gid),
        )
        tag_id = add_tag(cleanup, TAG, "restricted")
        as_admin = cw.LiveEnv(url=env.url, user=admin.uid, app_password=admin.password)
        delegation = cw.Harness(as_admin)
        try:
            response = delegation.request(
                "PROPPATCH",
                f"{env.url}/remote.php/dav/systemtags/{tag_id}",
                headers={"Content-Type": "application/xml"},
                content=(
                    '<?xml version="1.0"?><d:propertyupdate xmlns:d="DAV:" '
                    'xmlns:oc="http://owncloud.org/ns"><d:set><d:prop>'
                    f"<oc:groups>{gid}</oc:groups></d:prop></d:set></d:propertyupdate>"
                ).encode(),
            )
        finally:
            delegation.close()
        log(f"PROPPATCH oc:groups={gid} (Basic eigenes Admin-Konto): status {response.status_code}")
        assert response.status_code == 207, response.status_code
        named = checked("C", forbidden_values(env, admin), f"--admin={admin.uid}")
        assert named.doc["passed"] is True, named.doc
        assert named.doc["mode"] == exclusion_audit.MODE_ORGANISATION, named.doc
        assert gid in named.text
        assert any(gid in (tag.get("groups") or []) for tag in named.doc["tags"]), named.doc
        fall("C", named.doc)

    run_case("C", body)


def test_d_invisible(env: cw.LiveEnv, admin: Admin) -> None:
    def body(cleanup: cw.Cleanup) -> None:
        add_tag(cleanup, TAG, "invisible")
        bad = forbidden_values(env, admin)
        named = checked("D", bad, f"--admin={admin.uid}")
        assert named.doc["passed"] is False, named.doc
        visible = step_outcome(named.doc, exclusion_audit.STEP_TAG_VISIBLE)
        assert visible == exclusion_audit.OUTCOME_FAILED, named.doc
        # 29-REVIEW IN-02: an invisible tag still filters for administrators.
        assert "are NOT excluded for users who are not administrators: 0" in named.text
        anonymous = checked("D", bad)
        assert anonymous.doc["admin_checked"] is False, anonymous.doc
        assert "invisible tags and delegation groups were not checked" in anonymous.text
        log(f"FALL D ohne --admin passed={anonymous.doc.get('passed')}")
        fall("D", named.doc)

    run_case("D", body)


def test_e_only_a_variant(env: cw.LiveEnv, admin: Admin) -> None:
    def body(cleanup: cw.Cleanup) -> None:
        add_tag(cleanup, "Kein KI", "public")
        named = checked("E", forbidden_values(env, admin), f"--admin={admin.uid}")
        assert named.doc["passed"] is False, named.doc
        variants = step_outcome(named.doc, exclusion_audit.STEP_NO_VARIANTS)
        assert variants == exclusion_audit.OUTCOME_FAILED, named.doc
        fall("E", named.doc)

    run_case("E", body)


def test_f_exact_and_variant(env: cw.LiveEnv, admin: Admin, harness: cw.Harness) -> None:
    stem = f"chk29f{uuid.uuid4().hex[:8]}"

    def body(cleanup: cw.Cleanup) -> None:
        add_tag(cleanup, TAG, "public")
        add_tag(cleanup, "keinki", "public")
        exact_path = add_file(cleanup, harness, f"{stem}a.txt")
        variant_path = add_file(cleanup, harness, f"{stem}b.txt")
        ids = [harness.fileid(f"/{stem}a.txt"), harness.fileid(f"/{stem}b.txt")]
        assign(exact_path, TAG)
        assign(variant_path, "keinki")
        bad = forbidden_values(env, admin, stem, exact_path, variant_path, *ids)
        named = checked("F", bad, f"--admin={admin.uid}")
        assert named.doc["passed"] is True, named.doc
        assert named.doc["unprotected"] == 1, named.doc
        assert "Items tagged 'keinki' are NOT excluded: 1" in named.text
        fall("F", named.doc)

    run_case("F", body)


def test_h_not_an_admin(env: cw.LiveEnv, admin: Admin) -> None:
    def body(_: cw.Cleanup) -> None:
        named = checked("H", forbidden_values(env, admin), f"--admin={env.user}")
        assert named.doc["checked"] is False, named.doc
        assert named.doc["passed"] is False, named.doc
        fall("H", named.doc)

    run_case("H", body)
