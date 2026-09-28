---
phase: 28-gates-und-beweise
plan: 04
subsystem: exclusion-guard
tags: [kein-ki, guard, talk, fetch, notes, oracle, GATE-03]
requires: []
provides:
  - "talk.one_room: Einheitsfehler für jedes nicht sichtbare Token im Guard-Ausfall"
  - "chatgpt._fetch_file und notes.read: Nachbar-Fehler vor Tag-Entscheid"
  - "guard_routes.stale(mock), guard_routes.timeout(mock)"
affects: [28-08, 28-09]
tech-stack:
  added: []
  patterns: ["Reihenfolge wie files._visible_stat: Guard-Exception, unverifiable, Nachbar-Fehler, Tag"]
key-files:
  created: []
  modified:
    - src/mcp_connector/tools/talk.py
    - src/mcp_connector/tools/chatgpt.py
    - src/mcp_connector/tools/notes.py
    - tests/unit/guard_routes.py
    - tests/unit/test_guard_routes.py
    - tests/unit/test_talk_exclusion.py
    - tests/unit/test_fetch_message_exclusion.py
    - tests/unit/test_fetch_exclusion.py
    - tests/unit/test_notes_exclusion.py
decisions:
  - "D-28-15 umgesetzt: one_room fragt den Guard nur auf dem Fehlerpfad (vor dem letzten _unknown_token); sichtbare normale Räume kosten weiter keinen Guard-Request"
  - "D-28-17 umgesetzt: fetch(file:) und notes_read lesen den Fehler des Nachbar-Requests vor dem Tag, Notes-404/998 bleibt _note_not_found"
  - "guard_routes.stale/timeout liefern wie unverifiable ein Tupel (listing, report) statt einer einzelnen Route, damit Tests beide Zähler prüfen können"
metrics:
  duration: "ca. 35 min"
  completed: 2026-09-28
  tasks: 2
  files: 9
---

# Phase 28 Plan 04: Talk-Ausfall und Nachbar-Fehler-Reihenfolge Summary

Zwei Existenz-Orakel geschlossen: erfundene Talk-Tokens bekommen im Guard-Ausfall denselben `withhold.unavailable_error()` wie ein Datei-Raum, und `fetch(file:)` sowie `notes_read` antworten bei 5xx des Nachbar-Requests für getaggte und erfundene Ids gleich.

## Tasks

| Task | Name | Commits | Dateien |
|------|------|---------|---------|
| 1 | Talk-Ausfall angleichen (D-28-15) + Guard-Ausfallformen | 486703b (RED), 4c96a2f (GREEN) | talk.py, guard_routes.py, test_guard_routes.py, test_talk_exclusion.py, test_fetch_message_exclusion.py |
| 2 | Reihenfolge fetch(file:) und notes_read (D-28-17) | 5af65b8 (RED), 08715a0 (GREEN) | chatgpt.py, notes.py, test_fetch_exclusion.py, test_notes_exclusion.py |

## Belege aus dem Code

`one_room` (talk.py Z. 849-863), Guard-Frage nur zwischen Schleife und letztem `raise`:

```python
        return room
    scope = await clients.exclusion.scope(clients)
    if scope.state == "unverifiable":
        raise withhold.unavailable_error()
    raise _unknown_token(token)
```

Reihenfolge per `grep -n`:
- chatgpt.py: Z. 337 `if isinstance(entry, BaseException):` vor Z. 339 `if scope.excludes(fileid=fileid):`
- notes.py: Z. 196 `if isinstance(fetched, BaseException):` vor Z. 198 `if scope.excludes(fileid=raw):`
- `_note_not_found` unverändert; `git diff -- src/mcp_connector/server/` leer; check_tool_budget exit 0 (17233/18000 Bytes).
- `grep -c "def stale\|def timeout" tests/unit/guard_routes.py` = 2.

## Neue Beweise

- test_guard_routes: `stale` landet in unverifiable/stale_twice (Liste und REPORT je 2x), `timeout` in unverifiable/timeout.
- test_talk_exclusion: erfundenes Token im Ausfall (500, 412 zweimal, Timeout) über browse(messages), send und one_room = `unavailable_error`, gleich dem Datei-Raum-Tripel; bei untagged und active weiter `_unknown_token`.
- test_fetch_message_exclusion: fetch(message:) mit erfundenem Token in allen drei Ausfallformen = Datei-Raum-Tripel.
- test_fetch_exclusion: SEARCH 500/503 gibt getaggter 901 und erfundener 999999999 dasselbe Tripel (bis auf die eigene Id); unverifiable weiter vorn.
- test_notes_exclusion: Notes-GET 500/503 für 933 (getaggt) und 999 gleich; Notes-404 bei getaggter Id bleibt `_note_not_found`; unverifiable weiter vorn.
- Bestandstest "normaler Raum kostet keinen Guard-Request" ohne Diff grün.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Guard-Mock in drei Bestandstests ergänzt**
- **Found during:** Task 1
- **Issue:** Die "unbekanntes Token"-Hälfte der Paartests (test_talk_exclusion: history und send, test_fetch_message_exclusion: fetch in Datei-Raum) mockte keinen Guard. Mit der neuen Guard-Frage auf dem Fehlerpfad lief dort ein ungemockter PROPFIND.
- **Fix:** Je eine Zeile `guard_routes.untagged(mock)`; die Assertions bleiben unverändert (Normalbetrieb = `_unknown_token`).
- **Commits:** 486703b, 4c96a2f

**2. [Signatur] guard_routes.stale/timeout geben (listing, report) zurück**
- Der Plan nannte `-> respx.Route`; das Tupel folgt dem Nachbarn `unverifiable` und erlaubt den geforderten Zähler-Test (Liste 2x, REPORT 2x). 28-08 nutzt die Rückgabe nicht.

Ein Bestandstest "getaggt plus 5xx = nicht gefunden" existierte nicht, daher keine Umstellung nötig.

## Gates

pytest tests/unit tests/contract grün; ruff check, ruff format --check, pyright latest (0 errors), vulture, check_tool_budget grün.

## Self-Check: PASSED

- Commits 486703b, 4c96a2f, 5af65b8, 08715a0 vorhanden (git log).
- Alle geänderten Dateien vorhanden; STATE.md/ROADMAP.md nicht angefasst.
