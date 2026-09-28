---
phase: 28-gates-und-beweise
plan: 06
subsystem: files
tags: [exclusion, kein-ki, oracle, files_search, files_upload, GATE-03]
requires:
  - phase: 28-01
    provides: "Live-Messung B5/B6 auf nc35 (raw/28-01-live-questions.txt)"
  - phase: 28-02
    provides: "tool_classes.PAIR_CASES / NAMED_EXCEPTIONS"
provides:
  - "files_search(folder=getaggt) antwortet wie ein erfundener Ordner (dav.not_found(search_scope))"
  - "Paartest Chunk 1 in getaggten vs. erfundenen Ordner (B6, kein Befund)"
affects: [28-08 Paarmatrix, Phase 29 Doku/Aufräum-Merker]
tech-stack:
  added: []
  patterns: ["getaggte Suchwurzel wird vor dem Lesen des SEARCH-Ergebnisses mit derselben Fabrik abgewiesen wie der SEARCH-404"]
key-files:
  created: []
  modified:
    - src/mcp_connector/tools/files.py
    - tests/unit/test_files_exclusion.py
    - tests/unit/test_files_upload_exclusion.py
key-decisions:
  - "B5 (D-28-19 Fixen): tags.excludes(path=target_folder) -> raise dav.not_found(search_scope), nach dem unverifiable-Zweig, vor raise first; kein Zusatzrequest"
  - "B6 (D-28-20 Kein Befund): kein Code, kein NAMED_EXCEPTIONS-Eintrag, nur Paartest; kein DELETE im Upload-Bereich"
requirements-completed: [GATE-03]
duration: ~25min
completed: 2026-09-28
---

# Phase 28 Plan 06: B5-Fix und B6-Paartest Summary

files_search mit einem `kein-ki`-getaggten Ordner als Suchwurzel antwortet jetzt byte-gleich wie ein erfundener Ordner (`File not found: /files/<user>/<Ordner>.`), der erste Binär-Chunk ist per Paartest als gleich festgehalten.

## Ausgeführte Zweige

- **B5, D-28-19 = Fix.** Owner-Wortlaut: "Fixen (Empfohlen)": getaggter/ausgeschlossener Ordner in files_search antwortet vorab mit genau dem Fehler des erfundenen Ordners (dav.not_found(search_scope), gleicher Scope-Pfad-Wortlaut).
- **B6, D-28-20 = kein Befund.** Owner-Wortlaut: "Kein Befund, Staging als Merker (Empfohlen)": nur Paartest; der liegen gebliebene Staging-Ordner uploads/<user>/nc-mcp-<sha256> ist kein Orakel und wird Aufräum-Merker für Backlog/Phase 29, kein Fix in 28.

## Tasks

| Task | Name | Commits | Dateien |
|------|------|---------|---------|
| 1 | B5 nach D-28-19 (Fix) | eb3dd8f (test, RED), 55d385a (fix, GREEN) | src/mcp_connector/tools/files.py, tests/unit/test_files_exclusion.py |
| 2 | B6 nach D-28-20 (kein Befund) | 2596eef (test) | tests/unit/test_files_upload_exclusion.py |

## Umsetzung

- `files.search`: nach dem `unverifiable`-Zweig und vor `raise first` wirft `tags.excludes(path=target_folder)` jetzt `dav.not_found(search_scope)`. Die eine SEARCH geht wie bisher parallel zum Guard raus, ihre Antwort wird für den getaggten Ordner nicht gelesen; kein PROPFIND, kein zweiter Request. Docstring nennt D-28-19.
- Neue B5-Tests (Mocks = gemessene nc35-Antworten aus A3: getaggt 207 leer, erfunden Sabre-404):
  - Paartest gleicher Pfad, getaggt vs. erfunden, für `/Projekt` und `/Projekt/Unter`: gleiches Tripel, gleich `dav.not_found("/files/alice<Ordner>")`, je genau 1 SEARCH.
  - Paartest verschiedener Pfade, gleich nach Ersetzen der Ordnerpfade.
  - Sichtbarer Geschwisterordner `/Projekt2` wird nicht abgewiesen (Präfix-Falle).
  - `unverifiable`: getaggter und erfundener Ordner antworten gleich (leer, ein `degraded`).
- B6-Test: Chunk 1 (5 MiB, `final=False`) in `/Projekt` (getaggt) und `/erfunden-1` (MKCOL 201, Chunk-PUT 404 bzw. 409, wie in 28-01 beobachtet: Nextcloud weist den fehlenden Zielordner erst nach dem MKCOL ab). Gleiches Tripel bis auf den Pfad, gleich `dav.parent_missing`; getaggtes Ziel: 0 MKCOL, 0 PUT.

## Akzeptanz

- `grep -n "excludes(path=target_folder)" src/mcp_connector/tools/files.py`: ein Treffer.
- `tests/contract/tool_classes.py` unverändert (kein Ausnahmeeintrag in beiden Zweigen).
- `git diff -- src/mcp_connector/server/` leer; `test_files_upload.py` ohne Diff grün; kein DELETE im Upload-Bereich.
- Gates: pytest tests/unit tests/contract 4945 passed, 33 skipped (Exit 0); ruff check, ruff format --check, pyright latest (0 errors), vulture, check_tool_budget (17233/18000) grün.

## Deviations from Plan

None - plan executed exactly as written.

Hinweis TDD: B6 ist Zweig "kein Befund", der Paartest ist daher von Anfang an grün (kein RED möglich, kein feat-Commit); das ist der vom Owner gewählte Zweig, kein übersprungenes Gate. Kein Live-Lauf gegen nc35 in diesem Plan (nicht verlangt; 28-07 nutzt nc35 parallel).

## TDD Gate Compliance

- B5: RED `eb3dd8f` (3 Fälle scheiterten mit "DID NOT RAISE"), GREEN `55d385a` (Commit-Typ `fix`, da Orakel-Behebung).
- B6: nur `test`-Commit, Zweig kein Befund.

## Merker (nicht Teil dieses Plans)

- Staging-Ordner `uploads/<user>/nc-mcp-<sha256>` bleibt beim Chunk-1-Fehlschlag in einen erfundenen Ordner liegen: Aufräum-Merker für Backlog/Phase 29 (D-28-20).
- Der Fehlertext von files_search nennt den internen Scope `/files/<user>/<Ordner>` statt des angegebenen Ordners; bewusst beibehalten, weil D-28-19 genau diesen Wortlaut verlangt.

## Self-Check: PASSED

- FOUND: src/mcp_connector/tools/files.py, tests/unit/test_files_exclusion.py, tests/unit/test_files_upload_exclusion.py
- FOUND: eb3dd8f, 55d385a, 2596eef
