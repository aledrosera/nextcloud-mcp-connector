"""The three open live questions of the phase 28 research, measured before any fix (plan 28-01).

A1: what ``GET .../tables/{id}/rows/simple`` really sends for a link cell that points at a
Nextcloud file, and what ``tables_browse`` makes of it today. A3/B5: whether ``files_search``
answers a tagged folder the way it answers an invented one. A4/B6: whether the first chunk
of a binary upload into a tagged folder is refused the way one into an invented folder is.

These are measurements, not gates: nothing here asserts that a pair is equal. What is
asserted is the scaffolding (every created entry answers PROPFIND 207, ``occ tag:list``
knows ``kein-ki``) and the cleanup, whose every line is read back from the instance. Each
finding goes into ``.planning/phases/28-gates-und-beweise/raw/28-01-live-questions.txt`` as
a ``BEFUND`` line next to the raw answers it is based on. The owner decides on them before
plans 28-05 and 28-06 write code.

The search term is always the stem of the run, never the marker (D-28-06). The raw protocol
carries the marker of the run on purpose: it is random per run and names nothing real.

Run it against nc35 with the environment of ``.env.nc35`` plus the six ``NC_MCP_E2E_*``
exports of ``topology.py``::

    .venv/Scripts/python.exe -m pytest tests/integration/test_live_questions_28.py \
        -m integration -s
"""

import dataclasses
import json
import subprocess
import time
from collections.abc import Iterator
from typing import Any

import canary_world as cw
import pytest
import topology

from mcp_connector.nextcloud.clients import dav

pytestmark = [pytest.mark.integration, pytest.mark.anyio]

RAW = cw.RAW_DIR / "28-01-live-questions.txt"


def log(line: str) -> None:
    cw.record(RAW, line)


def dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def normalized(value: str, *concrete: str) -> str:
    """``value`` with every concrete path or id replaced by ``<ID>``, the longest first."""
    for item in sorted(concrete, key=len, reverse=True):
        value = value.replace(item, "<ID>")
    return value


def git_head() -> str:
    finished = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    return finished.stdout.strip() or "unbekannt"


@dataclasses.dataclass
class World:
    env: cw.LiveEnv
    harness: cw.Harness
    cleanup: cw.Cleanup
    stem: str
    marker: str
    h: str
    root: str
    locked: str
    locked_file: str
    tagged_file: str
    invented: str
    fileids: dict[str, str] = dataclasses.field(default_factory=dict)


@pytest.fixture(scope="module")
def world() -> Iterator[World]:
    env = cw.live_env()
    harness = cw.Harness(env)
    cleanup = cw.Cleanup()
    stem, marker = cw.run_id()
    h = stem.removeprefix("kanarie28x")
    root = f"/{stem}"
    state = World(
        env=env,
        harness=harness,
        cleanup=cleanup,
        stem=stem,
        marker=marker,
        h=h,
        root=root,
        locked=f"{root}/Gesperrt-{h}",
        locked_file=f"{root}/Gesperrt-{h}/inhalt-{h}.txt",
        tagged_file=f"{root}/{stem}-{marker}.txt",
        invented=f"{root}/erfunden-{h}",
    )
    version = harness.request("GET", f"{env.url}/status.php").json().get("versionstring")
    log("")
    log(f"# 28-01 live run {time.strftime('%Y-%m-%d %H:%M:%S %z')}")
    log(f"# nextcloud={version} container={topology.NC_CONTAINER} head={git_head()}")
    log(f"# user={env.user} tree={root} marker={marker}")
    try:
        harness.mkcol(root)
        cleanup.add_path(harness, root)
        harness.mkcol(state.locked)
        harness.put(state.locked_file, f"gesperrt {marker}\n".encode())
        harness.put(state.tagged_file, f"getaggt {marker}\n".encode())
        for key, path in (
            ("root", root),
            ("locked", state.locked),
            ("locked_file", state.locked_file),
            ("tagged_file", state.tagged_file),
        ):
            state.fileids[key] = harness.fileid(path)
        log(f"# aufbau PROPFIND 207: {sorted(state.fileids)}")

        tag_id, created = cw.ensure_tag()
        tagged: list[str] = []
        cleanup.add_tag(tag_id, created, tagged)
        for key in ("locked", "tagged_file"):
            cw.tag(state.fileids[key])
            tagged.append(state.fileids[key])
        listed = cw.tag_ids()
        assert listed, "occ tag:list knows no kein-ki after tagging"
        log(
            f"# getaggt per occ tag:files:add: Gesperrt-{h}/ und {stem}-<marker>.txt "
            f"(tag {tag_id} {'angelegt' if created else 'vorbestehend'}, tag:list {listed})"
        )
        yield state
    finally:
        lines = cleanup.run()
        for line in lines:
            log(line)
        harness.close()
        cw.fresh_guard()
    assert lines, "the cleanup registered nothing"
    assert all(cw.cleanup_ok(line) for line in lines), lines


# --- A1: the wire form of a Tables link cell ------------------------------------------


def _cell_form(cell: Any) -> str:
    if isinstance(cell, dict):
        return "objekt"
    if isinstance(cell, str):
        try:
            decoded = json.loads(cell)
        except ValueError:
            return "nur-url" if cell.startswith(("http://", "https://", "/")) else "text"
        return "json-string" if isinstance(decoded, dict) else f"json-{type(decoded).__name__}"
    return type(cell).__name__


async def test_a1_tables_link_cell_wire_form(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    harness, env = world.harness, world.env
    cw.mcp_env(monkeypatch, env)
    table_id = harness.create_table(f"{world.stem}-t")
    world.cleanup.add_table(harness, table_id)
    column_id = harness.create_link_column(table_id, "Verweis")
    log(f"A1 tabelle {table_id} spalte {column_id} (text/link, textAllowedPattern url,files)")

    name = world.tagged_file.rsplit("/", 1)[-1]
    fileid = world.fileids["tagged_file"]
    cell = json.dumps(
        {"title": name, "value": f"{env.url}/f/{fileid}", "providerId": "files"},
        ensure_ascii=False,
    )
    log(f"A1 gesendet zeile 1: data={dumps({column_id: cell})}")
    created = harness.create_row(table_id, {column_id: cell})
    log(f"A1 antwort zeile 1: {dumps(created)}")
    try:
        empty = harness.create_row(table_id, {column_id: ""})
        log(f"A1 antwort zeile 2 (leer): {dumps(empty)}")
    except AssertionError as exc:
        log(f"A1 zeile 2 (leer) abgelehnt: {exc}")

    status, raw = harness.rows_simple_raw(table_id)
    log(f"A1 rows/simple status: {status}")
    log(f"A1 rows/simple roh: {raw}")

    cw.fresh_guard()
    result = await cw.call("tables_browse", {"level": "rows", "table_id": table_id})
    browsed = dumps(cw.dump(result))
    log(f"A1 tables_browse rows: {browsed}")

    try:
        rows = json.loads(raw)
    except ValueError:
        rows = []
    wire_cell = rows[1][0] if isinstance(rows, list) and len(rows) > 1 and rows[1] else None
    # PHP escapes every slash in its JSON (``http:\/\/...\/f\/22515``), so the raw text is
    # compared with the escape undone; the decoded cell is the same string without it.
    wire = raw.replace("\\/", "/")
    log(
        f"BEFUND A1 zellform={_cell_form(wire_cell)} "
        f"title_im_draht={'ja' if name in wire else 'nein'} "
        f"fileid_im_draht={'ja' if f'/f/{fileid}' in wire else 'nein'} "
        f"marker_in_tables_browse={'ja' if world.marker in browsed else 'nein'}"
    )


# --- A3/B5: files_search with a tagged against an invented folder ---------------------


async def test_a3_b5_files_search_folder_pair(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    harness, env = world.harness, world.env
    cw.mcp_env(monkeypatch, env)
    creds = cw.credentials(env)
    for label, folder in (("erfunden", world.invented), ("getaggt", world.locked)):
        scope = dav.search_scope(creds, folder)
        response = harness.search_raw(scope, world.stem)
        log(
            f"B5 roh-SEARCH {label} scope={scope}: {response.status_code} "
            f"{cw.short(response.text.replace(chr(10), ' '), 400)}"
        )

    answers: dict[str, str] = {}
    for label, folder in (("getaggt", world.locked), ("erfunden", world.invented)):
        cw.fresh_guard()
        result = await cw.call("files_search", {"query": world.stem, "folder": folder})
        answers[label] = dumps(cw.dump(result))
        log(f"B5 files_search {label} folder={folder}: {answers[label]}")

    tagged = normalized(answers["getaggt"], world.locked, world.invented)
    invented = normalized(answers["erfunden"], world.locked, world.invented)
    same = tagged == invented
    log(f"B5 normiert getaggt: {tagged}")
    log(f"B5 normiert erfunden: {invented}")
    log(f"BEFUND B5 {'gleich' if same else 'ungleich'}")


# --- A4/B6: the first chunk of a binary upload ----------------------------------------


async def _upload_pair(
    world: World, label: str, name: str, args: dict[str, Any], ids: tuple[str, str] | None
) -> tuple[str, str]:
    """Run one upload into the tagged and one into the invented folder; both dumps back."""
    answers: list[str] = []
    for case, folder, upload_id in (
        ("getaggt", world.locked, ids[0] if ids else None),
        ("erfunden", world.invented, ids[1] if ids else None),
    ):
        call_args = {**args, "path": f"{folder}/{name}"}
        if upload_id:
            call_args["upload_id"] = upload_id
        cw.fresh_guard()
        result = await cw.call("files_upload", call_args)
        answer = dumps(cw.dump(result))
        answers.append(answer)
        log(f"{label} files_upload {case} path={call_args['path']}: {answer}")
    return answers[0], answers[1]


async def test_a4_b6_first_binary_chunk_pair(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    # The olivia fork has no base64 chunk upload (a binary file goes through an upload link),
    # so only the text half of this measurement applies to it.
    cw.mcp_env(monkeypatch, world.env)
    concrete = (world.locked, world.invented)
    a, b = await _upload_pair(world, "B6-text", "neu.txt", {"content": "x"}, None)
    same_text = normalized(a, *concrete) == normalized(b, *concrete)
    log(f"BEFUND B6-text {'gleich' if same_text else 'ungleich'}")
