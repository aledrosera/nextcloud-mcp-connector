---
phase: 28-gates-und-beweise
plan: 05
subsystem: tools/tables, tools/chatgpt
tags: [exclusion, kein-ki, tables, fetch, fail-closed]
requires: [28-01 (Messung A1, D-28-18), 28-04]
provides:
  - "tables.screen_links(clients, payload) -> LinkScreenResult"
  - "tables_browse level=rows und fetch(table:) halten Datei-Link-Zellen getaggter Dateien zurück"
affects: [28-10 Kanarie (Tables-Verweis-Kanarie), Phase 29 Doku (keine Sandbox für Tables)]
tech-stack:
  added: []
  patterns: ["Guard nur fragen, wenn es etwas zu fragen gibt (wie talk.file_screen)", "Zurückgehalten = Leerwert der App (null)"]
key-files:
  created:
    - tests/unit/test_tables_exclusion.py
  modified:
    - src/mcp_connector/tools/tables.py
    - src/mcp_connector/tools/chatgpt.py
decisions:
  - "Zurückgehaltene Link-Zelle wird None (null) statt \"\": die App liefert eine leere Link-Zelle als null (Messung 28-01), nur so ist das Paar getaggt/leer byte-gleich (D-28-18 'Zelle wie null')"
  - "Datei-Link (providerId files) ohne lesbare fileid wird bei aktivem Tag zurückgehalten (fail-closed)"
  - "Tables bekommt wie Talk nur den Tag, keine Sandbox; NC_MCP_FILES_ROOT wirkt nur über die Pfadauflösung bei getaggtem Ordner; Merker Phase 29"
metrics:
  duration: "ca. 25 min"
  completed: 2026-09-28
  tasks: 2
  files: 3
---

# Phase 28 Plan 05: Tables-Link-Zellen hinter dem kein-ki-Guard Summary

`tables.screen_links` dekodiert die in 28-01 gemessene Link-Zellform (JSON-String, `providerId: "files"`, fileid aus `/f/<id>` via `provider_map.file_id`, PHP-escapte Slashes) und setzt Zellen getaggter Dateien auf `null`; `tables_browse` level=rows und `fetch(table:)` nutzen denselben Screen, fail-closed mit dem degraded-Idiom der jeweiligen Familie.

## Tasks

| Task | Name | Commits | Dateien |
|------|------|---------|---------|
| 1 | screen_links in tables.py und Anschluss in _rows | 72b962e (test, RED), b42225f (fix, GREEN) | tables.py, test_tables_exclusion.py |
| 2 | fetch(table:) durch denselben Screen | 537bcc5 (test, RED), dc6e337 (fix, GREEN) | chatgpt.py, test_tables_exclusion.py |

## Verhalten

- Keine Datei-Link-Zelle im Fenster: kein Guard-Request (PROPFIND und REPORT je 0 Aufrufe).
- `untagged`: jede Zelle unverändert.
- `active`: getaggte fileid wird `null`; mit getaggtem Ordner ein `dav.paths_of_fileids` für alle Kandidaten, nicht auflösbar wird `null`, Pfad außerhalb bleibt.
- Lookup-Fehler oder `unverifiable` (500, stale, timeout): alle Datei-Link-Zellen `null`; `tables_browse` trägt `degraded == [withhold.degraded_entry("source")]`, `fetch(table:)` trägt `metadata["degraded"] == withhold.EXCLUSION_UNAVAILABLE`.
- Fremdtext mit `/f/123`, rohe URL und Links anderer Provider (`providerId: "url"`) sind keine Datei-Links und bleiben unverändert.
- Mehrere Link-Zellen: genau ein REPORT je Aufruf.
- Paar-Beweis: `test_a_tagged_link_cell_answers_like_an_empty_one` (tables_browse) und `test_fetch_table_withholds_a_tagged_link_like_an_empty_cell` (fetch) vergleichen `json.dumps(sort_keys=True)` getaggt gegen leer: gleich.
- Eine Zeile nur mit zurückgehaltener Link-Zelle zählt weiter als Zeile (`rows_shown` 1).

## Verifikation

- `pytest tests/unit tests/contract`: 4957 passed, 33 skipped
- ruff check, ruff format --check, vulture: grün; pyright (latest): 0 errors
- `scripts/check_tool_budget.py`: exit 0, 17233 bytes, 22 tools (unverändert)
- test_tables_tools.py und test_chatgpt_fetch.py ohne Diff grün; `src/mcp_connector/server/` ohne Diff
- vulture_whitelist.py unverändert (kein Befund)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Korrektheit] Leerwert null statt ""**
- **Found during:** Task 1
- **Issue:** Der Plan sagt "Zelle \"\"", die Messung 28-01 (D-28-18) zeigt aber, dass eine leere Link-Zelle als `null` kommt. Mit `""` wäre das Paar getaggt gegen leer nicht byte-gleich, also ein Orakel.
- **Fix:** Zurückgehaltene Zellen werden `None`; D-28-18 sagt ausdrücklich "getaggt -> Zelle wie null".
- **Files modified:** src/mcp_connector/tools/tables.py
- **Commit:** b42225f

**2. [Rule 1 - Testtreue] Escape nur auf Drahtebene**
- **Found during:** Task 2
- **Issue:** Die erste Test-Hilfe escapte die Slashes in der Zelle und nochmals auf dem Draht, dekodiert also `\/` im inneren String; gemessen ist Escape nur auf Drahtebene.
- **Fix:** `link()` liefert die Zelle mit normalen Slashes, `mock_tables` escapet den Draht wie PHP; die inner-escapte Variante hat einen eigenen Test (`test_a_link_cell_with_escaped_slashes_inside_is_read_as_well`).
- **Commit:** 537bcc5

## Threat Flags

Keine neue Angriffsfläche. T-28-40, T-28-41, T-28-42, T-28-45 umgesetzt; T-28-43 (Fremdtext) und T-28-44 (keine Sandbox für Tables) bleiben akzeptiert, Docstring von `screen_links` benennt den Merker für Phase 29.

## Known Stubs

Keine.

## TDD Gate Compliance

RED/GREEN je Task in der Reihenfolge test(28-05) vor fix(28-05) vorhanden (72b962e -> b42225f, 537bcc5 -> dc6e337). Kein Refactor-Commit nötig.

## Self-Check: PASSED

- FOUND: tests/unit/test_tables_exclusion.py, src/mcp_connector/tools/tables.py, src/mcp_connector/tools/chatgpt.py
- FOUND: 72b962e, b42225f, 537bcc5, dc6e337
