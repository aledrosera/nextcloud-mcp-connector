---
phase: 28-gates-und-beweise
plan: 08
subsystem: files
tags: [GATE-03, pair-test, kein-ki, oracle, files]
requires:
  - phase: 28-02
    provides: "tool_classes.PAIR_CASES / NAMED_EXCEPTIONS, result_shapes.normalised"
  - phase: 28-04
    provides: "guard_routes.stale / guard_routes.timeout"
  - phase: 28-06
    provides: "B5-Fix (D-28-19), B6 kein Befund (D-28-20), gemessene SEARCH-/Chunk-Mocks"
provides:
  - "GATE-03 Unit für die Familie files: 7 Paarfälle x 5 Guard-Zustände über Client(mcp)"
affects: [28-09, 28-10, Phase 29 Doku]
tech-stack:
  added: []
  patterns:
    - "Paarharness: je Seite eigener respx.mock, Catch-all-Route sammelt unerwartete Requests"
    - "Jeder Paarvergleich prüft zusätzlich die Ablehnung des Guard-Zustands (kein gemeinsamer Eingabefehler)"
key-files:
  created:
    - tests/unit/test_pair_equality_files.py
  modified: []
key-decisions:
  - "files_search: Scope-Schreibweise /files/<user><Ordner> zählt als zweite Form der angefragten Id (D-28-19-Wortlaut, Wortgrenze von normalised greift sonst nicht)"
  - "Imports aus tests/contract mit pyright-ignore reportMissingImports statt pyproject-Änderung (Konfliktfreiheit mit 28-09/28-10)"
requirements-completed: [GATE-03]
duration: ~30min
completed: 2026-09-28
---

# Phase 28 Plan 08: GATE-03 Unit, Familie files Summary

Alle sieben files-Paarfälle aus `PAIR_CASES` sind über die echte Registry (`Client(mcp)`) in fünf Guard-Zuständen (aktiv, 412 einmal, 412 zweimal, Timeout, 5xx) als byte-gleicher ganzer `CallToolResult` belegt; kein Befund in `src/`.

## Tasks

| Task | Name | Commit | Dateien |
|------|------|--------|---------|
| 1 | Paarharness, files_read/download/list, fetch(file:) + D-28-17 | 518dc02 | tests/unit/test_pair_equality_files.py |
| 2 | files_search(folder), files_upload text und Chunk 1, Abdeckung, Zeit | e3fc6a0 | tests/unit/test_pair_equality_files.py |

## Umsetzung

- `pair()` ruft beide Seiten je in eigenem `respx.mock` auf, dazwischen `guard_routes.reset()` und `capabilities.clear_cache()`; Vergleich `normalised(result, angefragte Id)`.
- `arm_guard`: active -> `guard_routes.active`; stale_once -> REPORT erst 412, danach 207 mit den getaggten Knoten (Seiteneffekt-Funktion, übersteht auch weitere REPORTs); stale_twice -> `stale`; timeout -> `timeout`; server_error -> `unverifiable`.
- Catch-all-Route als letzte Route jeder Seite: unerwartete Requests landen in einer Liste, die Fixture `unexpected` lässt den Test scheitern. So können zwei Seiten nicht gleich sein, weil beide auf denselben ungemockten Request laufen.
- Zusatzanker: jede Paarprüfung verlangt im aktiven Zustand das Fragment der erwarteten Ablehnung (`File not found: <ID>.`, `of <ID> does not exist.`, `This account has no file with the id <ID>.`) und im nicht beantwortbaren Zustand `could not be answered`. Damit fällt ein gemeinsamer Eingabefehler auf beiden Seiten auf.
- Leser prüfen je Modus zwei getaggte Ziele (getaggte Datei, Datei unter getaggtem Ordner) bzw. zwei Ordner (`/Projekt`, `/Projekt/Unter`) in einem Testfall, damit die Parametrisierung je Werkzeug genau 5 Fälle ergibt.
- Upload text: getaggter Ordner und getaggte Datei unter sichtbarem Elternordner gegen `/erfunden-1/neu.txt` (PUT 409). Chunk 1: 5 MiB, `final=False`, erfundenes Ziel MKCOL 201 und Chunk-PUT 404 wie in 28-01 gemessen.
- `test_the_files_family_covers_exactly_its_pair_cases`: `COVERED` gleich der files-Teilmenge von `PAIR_CASES`; `NAMED_HERE` (leer) gleich den files-Einträgen in `NAMED_EXCEPTIONS`, so dass ein künftiger Ausnahmeeintrag ohne eigenen Test auffällt.
- `test_time_is_not_part_of_the_comparison`: schnelle und um 0,2 s verzögerte Antwort derselben Ablehnung ergeben denselben String (D-28-12).

## Akzeptanz

- 39 Fälle grün; je 5 für files_read, files_download, files_list, files_search, fetch(file:), files_upload text, files_upload Chunk 1; 2 für D-28-17 (SEARCH 500/503).
- `grep -c raise_exceptions` = 0, `grep -c pytest.skip` = 0, `git diff -- src/` leer.
- Gates: pytest tests/unit tests/contract 5003 passed, 33 skipped (Exit 0); ruff check, ruff format --check, pyright latest 0 errors, vulture, check_tool_budget (17233/18000) grün.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] pyright findet tests/contract nicht**
- **Found during:** Task 1
- **Issue:** `from result_shapes import ...` aus tests/unit: pytest hat `tests/contract` im Pfad (pyproject), pyright nicht (reportMissingImports).
- **Fix:** `# pyright: ignore[reportMissingImports]` an den beiden Import-Zeilen, Begründung im Modul-Docstring. Bewusst keine `extraPaths`-Änderung in pyproject.toml, um mit den parallelen Plänen 28-09/28-10 nicht zu kollidieren. Merker: später zentral `extraPaths = ["tests/unit", "tests/contract", "tests/integration"]` setzen und die Ignores entfernen.
- **Commit:** 518dc02

**2. [Rule 1 - Test-Harness] files_search nennt den Ordner als Scope `/files/<user><Ordner>`**
- **Found during:** Task 2
- **Issue:** Die Wortgrenze in `normalised` ersetzt `/Projekt` nicht hinter `/files/alice` (Zeichen davor ist ein Buchstabe). Beide Antworten sind inhaltlich gleich, nur der Ordner blieb unersetzt. Kein Befund in `src/`: genau dieser Wortlaut ist durch D-28-19 festgelegt (28-06 Merker).
- **Fix:** `pair()` nimmt je Seite optional ein Tupel angefragter Werte; für files_search wird zusätzlich `/files/<user><Ordner>` ersetzt. Alles andere bleibt byte-gleich verglichen.
- **Commit:** e3fc6a0

## Known Stubs

Keine.

## Self-Check: PASSED

- FOUND: tests/unit/test_pair_equality_files.py
- FOUND: 518dc02, e3fc6a0
