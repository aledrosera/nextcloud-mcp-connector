---
phase: 26-guard-kern
plan: 01
subsystem: nextcloud-clients
tags: [systemtags, webdav, exclusion, segment-rule]
requires: []
provides:
  - "dav.within(path, root): einzige Segmentregel (Sandbox + EXCL-02)"
  - "dav.home_entries(body, creds): ungefilterte href-Abbildung, None statt Drop"
  - "systemtags.list_tags / systemtags.tagged_nodes: policy-freier Tag-Client, Ausgänge als Werte"
affects: [26-02]
tech-stack:
  added: []
  patterns: ["Ausgänge als Werte (TagListing/TaggedSet) statt ToolError", "eine oc:systemtag-Regel je REPORT"]
key-files:
  created:
    - src/mcp_connector/nextcloud/clients/systemtags.py
    - tests/unit/test_systemtags_client.py
    - tests/unit/test_dav_home_entries.py
  modified:
    - src/mcp_connector/nextcloud/clients/dav.py
    - vulture_whitelist.py
decisions:
  - "systemtags.py nutzt ein modul-eigenes _DIGITS statt dav._DIGITS (Projektkonvention wie mail.py/ids.py, kein privater Fremdzugriff)"
  - "vulture meldet nur tagged_nodes und _.is_collection; list_tags hat über scripts/tag_spike.py schon einen gleichnamigen Leser"
metrics:
  duration: "ca. 25 min"
  completed: 2026-09-27
  tasks: 2
  files: 5
---

# Phase 26 Plan 01: Tag-Client und Segmentregel Summary

Policy-freier System-Tag-Client (PROPFIND-Tag-Liste, REPORT oc:filter-files mit genau einer Regel an die Home-Wurzel, Status als Wert) plus `dav.within` als einzige Segmentregel und `dav.home_entries` ohne Sandbox-Drop.

## Tasks

| Task | Name | Commits | Dateien |
|------|------|---------|---------|
| 1 | within() und home_entries() in dav.py | 6b8cc97 (RED), 42af572 (GREEN) | dav.py, test_dav_home_entries.py |
| 2 | Client systemtags.py | 02b01f8 (RED), d362c58 (GREEN) | systemtags.py, test_systemtags_client.py, vulture_whitelist.py |

## Ergebnis

- `within` steht einmal im Code (`grep -c 'startswith(root + "/")'` = 1), `safe_path` und `in_files_root` rufen es; Pfadprüfung nach `_plain_path` ausgelagert, Verhalten unverändert.
- `home_entries` liefert je `d:response` genau ein Paar; fremdes Präfix, `alicexyz`, `..`/`.`, Backslash, Steuerzeichen werden `None`. Sandbox-Test: `/Shared` bei `NC_MCP_FILES_ROOT=/Shared/KI`, `parse_entries` liefert für denselben Body `[]`.
- `tagged_nodes`: Body vor dem Request gebaut (ungültige Id -> ValueError ohne Netzverkehr), URL immer `/remote.php/dav/files/<user>/` (auch bei `NC_MCP_FILES_ROOT=/Docs`), genau ein `oc:systemtag` im Body; 412/401/403/500/301 als `TaggedSet(status, ())` mit `call_count == 1`; fehlende oder nicht-ASCII-fileid -> ValueError; unparsebarer Body -> ToolError.
- `list_tags`: PROPFIND Depth 1 auf `/remote.php/dav/systemtags/` mit `oc:id` + `oc:display-name`, Collection ohne Id übersprungen, Name unverändert, Nicht-Ziffern-Id -> ValueError, 500 -> `TagListing(500, ())`.
- Capabilities-Route gemockt, `call_count == 0`.

## Gates

- ruff check, ruff format --check: grün
- pyright (PYRIGHT_PYTHON_FORCE_VERSION=latest): 0 Fehler
- vulture src scripts vulture_whitelist.py: grün
- pytest tests/unit tests/contract: 4533 passed, 33 skipped
- Kein Werkzeug hängt am Client (`grep systemtags` in tools/, deps.py, nextcloud/__init__.py leer)

## Deviations from Plan

1. **[Konvention] Modul-eigenes `_DIGITS` in systemtags.py** statt `dav._DIGITS`: identische Regel `[0-9]+`, wie in mail.py, ids.py und provider_map.py; vermeidet privaten Fremdzugriff mit `noqa: SLF001`. PATTERNS.md erlaubt beide Varianten.
2. **[Rule 1 - Test] pyright reportOptionalIterable** im neuen Test (`body.find(...)` kann None sein): `assert prop is not None` ergänzt, vor dem GREEN-Commit.
3. **Umgebung:** Worktree ohne eigene `.venv`, `uv sync` gesperrt. Gates liefen mit der venv des Hauptrepos und `PYTHONPATH=src` (Import aus dem Worktree geprüft: `mcp_connector.__file__` zeigt in den Worktree).

## TDD Gate Compliance

Beide Tasks: `test(26-01)`-Commit (RED, Tests schlugen fehl bzw. Collection-Error wegen fehlendem Modul) vor `feat(26-01)`-Commit (GREEN). Kein Refactor-Commit nötig.

## Known Stubs

Keine. `tagged_nodes` und `TaggedNode.is_collection` sind bis Plan 26-02 in `vulture_whitelist.py` geparkt (Abschnitt "The tag query client of plan 26-01").

## Self-Check: PASSED

- FOUND: src/mcp_connector/nextcloud/clients/systemtags.py, tests/unit/test_systemtags_client.py, tests/unit/test_dav_home_entries.py
- FOUND: 6b8cc97, 42af572, 02b01f8, d362c58
