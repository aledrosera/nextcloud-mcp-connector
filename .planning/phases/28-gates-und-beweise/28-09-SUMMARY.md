---
phase: 28-gates-und-beweise
plan: 09
subsystem: tests
tags: [gate-03, pair-equality, kein-ki, notes, talk, tables]
requires:
  - tests/contract/tool_classes.py (PAIR_CASES, NAMED_EXCEPTIONS, 28-02)
  - tests/contract/result_shapes.py (normalised, requested_forms, 28-02)
  - tests/unit/guard_routes.py (stale, timeout, 28-04)
  - Fixes D-28-15 (talk), D-28-17 (notes order), D-28-18 (tables links, 28-05)
provides:
  - GATE-03 Unit, Familie apps, über Client(mcp) in fünf Guard-Zuständen
  - Pin-Test der benannten Ausnahme notes_create/category (D-28-16)
affects:
  - pyproject.toml ([tool.pyright] extraPaths)
tech-stack:
  added: []
  patterns:
    - "Paar über die echte Registry: je Seite eigener respx.mock, Guard- und Cache-Reset, normalised() des ganzen CallToolResult"
key-files:
  created:
    - tests/unit/test_pair_equality_apps.py
  modified:
    - pyproject.toml
decisions:
  - "Beide Seiten eines Paars laufen gegen dieselbe gemockte Instanz (gleiche Welt, anderes Argument); nur bei fetch(table:) unterscheidet sich die Tabelle selbst, wie im Plan verlangt"
  - "stale_once zählt zu den beantworteten Zuständen (neu gelistet, dann aktiv): fetch(table:) Normalfall und der notes_create-Pin laufen über active und stale_once, die Ausfallpaare über stale_twice, timeout, server_error; so deckt jeder Fall alle fünf Zustände ab"
  - "pyright extraPaths spiegeln den pytest-pythonpath, damit tests/unit result_shapes und tool_classes aus tests/contract auflöst"
metrics:
  duration: "ca. 25 min"
  completed: 2026-09-28
  tasks: 2
  files: 2
---

# Phase 28 Plan 09: Paargleichheit Familie apps Summary

GATE-03 auf Unit-Ebene für die Familie apps: 40 Fälle über `Client(mcp)` belegen, dass notes_read, fetch(note:), talk_browse(messages), talk_send, fetch(message:) und fetch(table:) für getaggte und erfundene Ziele byte-gleich antworten, in fünf Guard-Zuständen. notes_create/category ist als einzige benannte Ausnahme (D-28-16) gepinnt.

## Was gebaut wurde

**Task 1 (108e6fa):** Harness mit `GUARD_MODES` (active, stale_once, stale_twice, timeout, server_error), `arm_guard`, `side()` und `assert_alike`.
- notes_read, fetch(note:): getaggte Notiz 933 gegen erfundene 999 (Notes-404), je 5 Fälle. Im beantworteten Zustand trägt die Antwort "did not find the note <ID>.", im Ausfall die Einheitsablehnung.
- `test_note_reads_answer_a_failing_notes_app_alike`: Notes-GET 500 und 503 bei Guard active, für beide Werkzeuge (D-28-17).
- talk_browse, talk_send, fetch(message:): Datei-Raum der getaggten Datei 901 gegen erfundenes Token, je 5 Fälle. Im Ausfall tragen beide Seiten `withhold.EXCLUSION_UNAVAILABLE` (D-28-15). Die Chat-POST-Route hat in jedem talk_send-Fall call_count 0.

**Task 2 (99371b0):**
- fetch(table:): active und stale_once: getaggte Link-Zelle gegen leere Zelle. stale_twice, timeout, server_error: getaggter gegen ungetaggten Link, beide mit `metadata.degraded`. Der getaggte Dateiname kommt im Roh-JSON nicht vor.
- `test_notes_create_is_a_named_residual_oracle` (active, stale_once): getaggte Kategorie liefert is_error mit dem Text von `dav.parent_missing("/Notes/Geheim/Plan.md")` und POST 0. Erfundene Kategorie liefert Erfolg (note:960) und POST 1. Der Test prüft außerdem, dass der Eintrag in NAMED_EXCEPTIONS steht.
- notes_create im Ausfall: echtes Paar, Einheitsablehnung, POST 0 auf beiden Seiten.
- `test_the_apps_family_covers_exactly_its_pair_cases`: COVERED ist gleich der apps-Teilmenge von PAIR_CASES, und die einzige benannte Ausnahme ist notes_create/category.

## Befund zu src/

Kein Paar hat eine Ungleichheit in src/ gezeigt. Einziger Unterschied ist die benannte Ausnahme D-28-16. `git diff -- src/` ist leer.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] pyright konnte `result_shapes` aus tests/unit nicht auflösen**
- **Gefunden in:** Task 1
- **Problem:** pytest findet tests/contract über `pythonpath`, pyright nicht. Ergebnis war `reportMissingImports` und damit ein rotes Gate.
- **Fix:** Unter `[tool.pyright]` steht jetzt `extraPaths = ["tests/integration", "tests/unit", "tests/contract"]`, derselbe Pfad wie bei pytest.
- **Dateien:** pyproject.toml
- **Commit:** 108e6fa
- **Hinweis für den Merge:** 28-08 (test_pair_equality_files.py) und 28-10 (test_canary.py) importieren dieselben Hilfsmodule und stoßen wahrscheinlich auf dasselbe Problem. Hat ein paralleler Plan dieselbe Zeile anders ergänzt, reicht beim Merge eine der beiden Fassungen.

Sonst lief der Plan wie geschrieben.

## Gates

- pytest tests/unit tests/contract: Exit 0 (neues Modul: 40 passed)
- ruff check, ruff format --check: grün
- pyright (latest): 0 errors
- vulture: grün
- check_tool_budget: grün
- `raise_exceptions`, `pytest.skip`, U+2013/U+2014 im neuen Modul: 0

## Self-Check: PASSED

- FOUND: tests/unit/test_pair_equality_apps.py
- FOUND: 108e6fa, 99371b0
