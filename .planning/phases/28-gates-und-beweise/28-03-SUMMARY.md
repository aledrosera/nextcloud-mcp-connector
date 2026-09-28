---
phase: 28-gates-und-beweise
plan: 03
subsystem: contract-gates
tags: [excl-07, systemtags, kein-ki, ast-gate, destructive-calls]
requires: []
provides:
  - "FORBIDDEN-Nadeln systemtags-relations, tag:files, /apps/files/api/v1/files mit Beweiszeilen (SYSTEMTAGS_ROUTES)"
  - "tag_writes() und systemtags_module_writes() als AST-Prüfungen"
  - "ALLOWED_SYSTEMTAGS_FORMS als eingefrorene Positivliste der zwei echten Formen"
affects: [tests/contract/test_no_destructive_calls.py]
tech-stack:
  added: []
  patterns: ["AST-Prüfung über ganze Call-Knoten statt Zeilen-Nadel", "Gegenprobe über dieselbe Prüffunktion wie das Gate"]
key-files:
  created: []
  modified: [tests/contract/test_no_destructive_calls.py]
decisions:
  - "Alte Datei-Tags: keine eigene PROPPATCH-Nadel, Beweis über die globale Nadel (parametrisiert oc:tags / oc:favorite)"
  - "ALLOWED_SYSTEMTAGS_FORMS wird sortiert verglichen, Verb aus ast.unparse ohne Anführungszeichen"
metrics:
  duration: "ca. 15 min"
  completed: 2026-09-28
  tasks: 2
  files: 1
---

# Phase 28 Plan 03: EXCL-07 Tag-Schreibpfade im Destruktiv-Gate Summary

Der Connector kann `kein-ki` konstruktionsbedingt weder setzen noch entfernen: drei Routen-Nadeln mit Beweiszeile und Zähltest, eine AST-Prüfung, die jeden systemtags-Aufruf in `src/` als PROPFIND/REPORT belegt (auch mehrzeilig), eine Modulregel für `clients/systemtags.py` und die zwei echten Formen als Tupel.

## Tasks

| Task | Name | Commit |
| ---- | ---- | ------ |
| 1 | Zeilen-Nadeln mit Beweiszeilen und Zähltest | 50c0d6e |
| 2 | AST-Methodenprüfung, Modulregel, erlaubte Formen | 8ca2a43 |

## Umsetzung

- `FORBIDDEN` um `systemtags-relations`, `tag:files`, `/apps/files/api/v1/files` erweitert (Kommentarblock EXCL-07).
- `SYSTEMTAGS_NEEDLES` / `SYSTEMTAGS_ROUTES`; Tests: parametrisierte Nadelprobe (3 Fälle), Mengen-Zähltest, Legacy-PROPPATCH-Probe (oc:tags, oc:favorite gegen dav.py).
- `READ_METHODS`, `CALL_ATTRS`, `SYSTEMTAGS_MODULE`, `_mentions_tags`, `_is_a_read_request`, `_http_calls`, `tag_writes`, `systemtags_module_writes`, `_systemtags_request_forms`, `ALLOWED_SYSTEMTAGS_FORMS`.
- Tests: `test_no_module_writes_on_systemtags`, `test_the_systemtags_check_would_notice_a_multiline_write_in_real_code` (4 Fälle), `test_the_systemtags_client_only_reads` (2 Fälle), `test_the_two_forms_the_systemtags_client_really_builds_stay_allowed`.
- Nicht-Vakuität geprüft: im echten Modul erkennt `_mentions_tags` den PROPFIND-Aufruf (Z. 126), der REPORT auf `home_url` wird nur von der Modulregel gesehen.

## Verifikation

- `pytest tests/unit tests/contract` grün; `test_no_destructive_calls.py` 54 Tests grün.
- ruff check, ruff format --check, pyright latest (0 errors, mit `--pythonpath` auf die Haupt-venv), vulture, check_tool_budget: alle Exit 0.
- `git diff -- src/` leer; `grep` nach `systemtags-relations|tag:files|apps/files/api/v1` in `src/` ohne Treffer.

## Deviations from Plan

- **TDD-RED nicht separat committet:** Task 1 wurde nachweislich rot gefahren (4 Fehlschläge vor den FORBIDDEN-Einträgen), aber nicht als roter Commit festgehalten, weil die Orchestrator-Vorgabe grüne Unit- und Contract-Tests vor jedem Commit verlangt. In Task 2 wurden Funktionen und Tests zusammen geschrieben; die Gegenproben verlangen nicht-leere Befunde und wären bei einer leeren Prüffunktion rot.
- **Legacy-PROPPATCH-Probe parametrisiert** statt zwei Zeilen in einer Funktion (gleiche Aussage, getrennte Befunde).
- **pyright** im Worktree braucht `--pythonpath <Haupt-venv>`, sonst werden die Importe nicht aufgelöst (reine Umgebungsfrage, kein Code-Befund).

## TDD Gate Compliance

Kein separater `test(...)`-RED-Commit vor einem `feat(...)`-Commit: der Plan ist rein testseitig (beide Commits `test(28-03)`), und die Vorgabe "grün vor jedem Commit" hat Vorrang.

## Self-Check: PASSED

- tests/contract/test_no_destructive_calls.py vorhanden, Commits 50c0d6e und 8ca2a43 im Log.
