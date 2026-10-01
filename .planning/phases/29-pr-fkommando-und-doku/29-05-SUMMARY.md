---
phase: 29-pr-fkommando-und-doku
plan: 05
subsystem: exclusion
tags: [occ, exapp, appapi, manifest]

requires:
  - phase: 29-pr-fkommando-und-doku
    provides: exclusion_check_routes, EXCLUSION_CHECK_PATH, ADMIN_OPTION, JSON_OPTION aus 29-04
provides:
  - Fünftes occ-Kommando mcp_connector:exclusion:check (Schema in exapp/occ.py)
  - Route POST /exclusion-check in der gebauten ExApp-App
  - Achter Eintrag "deliberately absent path" in appinfo/info.xml
affects: [29-06]

tech-stack:
  added: []
  patterns:
    - "Handler aus Pfadkonstante abgeleitet (removeprefix), Name genau einmal als Literal"

key-files:
  created: []
  modified:
    - src/mcp_connector/exapp/occ.py
    - src/mcp_connector/entry_exapp.py
    - appinfo/info.xml
    - tests/unit/test_exapp_lifecycle.py
    - tests/unit/test_exapp_entry.py

key-decisions:
  - "occ.py nutzt das vorhandene JSON_OPTION aus audit_verify (gleiche Schreibweise 'json'), kein Alias; der Schema-Test hält exclusion_check.JSON_OPTION dagegen"
  - "Routentest 200 ohne Netz: --admin mit 65 Zeichen endet vor jedem Nextcloud-Aufruf (checked false)"

requirements-completed: []

duration: 15min
completed: 2026-10-01
---

# Phase 29 Plan 05: exclusion:check verdrahten Summary

**Fünftes occ-Kommando mcp_connector:exclusion:check mit --admin (optional, default None) und --json (none), Route /exclusion-check in der ExApp-App, info.xml nur im Kommentar ergänzt, Store-Texte byte-gleich mit ca157b4**

## Accomplishments

- occ.py: `OCC_EXCLUSION_CHECK_COMMAND_NAME`, `_HANDLER` (= `EXCLUSION_CHECK_PATH.removeprefix("/")`), `_DESCRIPTION`, `_JSON_DESCRIPTION`, `_ADMIN_DESCRIPTION`, alle in `__all__`; fünfter Schema-Eintrag; Modul-Docstring "Five of them since plan 29-05"
- entry_exapp.py: `*exclusion_check_routes(env),` direkt nach der exchange-Zeile
- Tests: `len(schemes) == 5`, neuer Test Schema Nr. 5 (Name, Handler, Optionen, default, Beschreibungslängen), drei Routentests (Route vorhanden, 200, Proxy 404)
- info.xml: Zeilen 260 bis 269 neu (achter Eintrag), sonst nichts; `git diff ca157b4 --stat` = 10 Einfügungen, CRLF beibehalten
- grep nach "Four of them / four occ / four commands": kein Treffer, der die Kommandozahl meint, nichts nachzuziehen. Der Kommentar in info.xml nennt keine Zahl fehlender Pfade

## Task Commits

1. **Task 1** - `c8a397c` (feat)
2. **Task 2** - `9919c1d` (chore)

## Gates

Vor jedem Commit grün: ruff check, ruff format --check, pyright latest (0 Fehler), vulture (src scripts vulture_whitelist.py), PYTHONUTF8=1 pytest tests/unit tests/contract (Exit 0). Byte-Vergleich summary/description (6 Elemente, en/de/fr) gegen ca157b4: Exit 0. `<url>`-Treffer für exclusion-check: 0.

## Deviations from Plan

1. **vulture_whitelist.py unverändert:** vulture meldete nichts.
2. **verify `-k url` wählt keinen Test:** Der Manifest-Test aus 29-04 heißt `test_the_path_is_declared_in_no_route_of_the_manifest`; stattdessen mit `-k "manifest or proxy"` gelaufen, beide grün.
3. **`uv run vulture` ohne Pfade** bricht mit "Please pass at least one file or directory" ab; wie in 29-04 mit `src scripts vulture_whitelist.py` gefahren.
4. **requirements mark-complete ausgelassen:** OPS-01 erst mit Live-Beweis (29-06).

## Known Stubs

Keine.

## Self-Check: PASSED

- Commits c8a397c, 9919c1d vorhanden
- Alle fünf geänderten Dateien vorhanden
