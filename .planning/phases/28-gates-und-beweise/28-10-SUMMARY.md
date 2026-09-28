---
phase: 28-gates-und-beweise
plan: 10
subsystem: tests/integration (Kanarie GATE-02) + tools/search (talk-conversations)
tags: [gate-02, live, nc35, canary, befund, d-28-21]
status: complete
requires:
  - 28-02 (result_shapes, tool_classes)
  - 28-07 (canary_world)
provides:
  - tests/integration/test_canary.py (vier Modi, 22 Werkzeuge) für den CI-Schritt in 28-11
  - talk-conversations-Treffer in unified_search gegen die Gesprächsliste geprüft (D-28-21)
affects: [28-11, 29]
tech-stack:
  added: []
  patterns: [Scan inklusive dekodierter Paging-Cursors, Marker-Fenster im Befund, Datei-Raum-Regel talk.room_fileid in zwei Familien]
key-files:
  created:
    - tests/integration/test_canary.py
    - .planning/phases/28-gates-und-beweise/raw/28-10-canary.txt
    - .planning/phases/28-gates-und-beweise/raw/28-10-befund-diagnose.txt
  modified:
    - src/mcp_connector/tools/search.py
    - src/mcp_connector/tools/talk.py
    - tests/unit/test_search_exclusion.py
    - .planning/phases/28-gates-und-beweise/28-CONTEXT.md
    - pyproject.toml
decisions:
  - "D-28-21 (Owner 28.09., 'Gegen Raumliste prüfen (Empfohlen)'): talk-conversations-Treffer in unified_search werden gegen die Gesprächsliste geprüft wie in talk_browse; getaggter Datei-Raum still weg, im Ausfall Datei-Räume zurückgehalten mit einem degraded-Eintrag, Räume ohne Datei bleiben, Raumliste nur bei solchen Treffern"
  - "Ein Treffer, dessen Token nicht in der Gesprächsliste steht, gilt als Datei-Raum mit Id '-' und ist zurückgehalten, sobald etwas getaggt ist (fail-closed wie room_fileid)"
  - "Nicht lesbare Gesprächsliste: talk-conversations-Treffer zurückgehalten, degraded-Eintrag unter dem Provider-Namen"
  - "talk_browse-Ebene heißt conversations (Literal der Registry), nicht rooms wie im Plan"
metrics:
  duration: ca. 75 min
  completed: 2026-09-28
---

# Phase 28 Plan 10: Kanarie GATE-02 Summary

Die Kanarie ruft alle 22 Werkzeuge über `Client(mcp)` in vier Modi auf, fand gegen nc35 einen echten Abfluss des getaggten Dateinamens über den Talk-Datei-Raum im Suchprovider `talk-conversations` und ist nach dem Owner-Fix D-28-21 gegen nc35 in allen vier Modi grün: 4 passed, je 22 von 22.

## Tasks

| Task | Name | Commit | Status |
| ---- | ---- | ------ | ------ |
| 1 | Aufrufplan, Scan, Blättern, Kontroll-Marker (Normalbetrieb) | 91388d6 | erledigt |
| 2 | Drei Ausfallformen und Lauf gegen nc35 | 91388d6 (Code), 0b4f152 (Befund), dieser Commit (Beweislauf) | erledigt |
| Checkpoint | Owner-Entscheid D-28-21 umgesetzt | 19b6132 (RED), f9f8773 (GREEN) | erledigt |

## Befund vor dem Fix (raw/28-10-befund-diagnose.txt)

- `unified_search` (Provider `talk-conversations`), `prepare_context` full und short sowie `search` nannten den Datei-Raum der getaggten Datei mit Titel `<stamm>-<marker>.txt`, im Normalbetrieb und im Ausfall timeout; die anderen 18 Werkzeuge waren sauber.
- Ursache: `tools/search.py:_screen` behandelte den Treffer als nicht dateitragend; `talk_browse` hält Datei-Räume über `room_fileid` zurück, der Suchweg nicht.

## Fix D-28-21

- `tools/search.py:_screen_conversations`: liest die Gesprächsliste nur, wenn `talk-conversations`-Treffer da sind und der Tag-Zustand nicht `untagged` ist; Token aus `/call/<token>`; Entscheidung über `talk.file_screen(..., room_fileids=...)` mit dem Scope des Aufrufs (ein REPORT je Antwort); `unavailable` setzt den einen `exclusion`-degraded-Eintrag.
- `tools/talk.py`: `_room_fileid` heißt jetzt `room_fileid` (öffentlich, das AST-Gate verbietet Privat-Durchgriffe).
- Sechs neue Unit-Tests in `tests/unit/test_search_exclusion.py`: getaggter Datei-Raum weg, ungetaggter Datei-Raum und normaler Raum bleiben, unbekanntes Token zurückgehalten, unverifiable mit genau `[EXCLUSION]`, keine Raumliste ohne Treffer bzw. ohne Tag, fehlerhafte Raumliste mit Provider-degraded.
- Kein neuer Parameter, `check_tool_budget.py` Exit 0.

## Beweislauf nc35 (raw/28-10-canary.txt, neu begonnen)

- Kommando: `PYTHONUTF8=1 .venv/Scripts/python.exe -m pytest tests/integration/test_canary.py -m integration -s`, Env aus `.env.nc35` in Python geladen, sechs `NC_MCP_E2E_*`-Exporte, `PYTHONPATH=<worktree>/src`, HEAD f9f8773, Container nc35-nc
- Ergebnis: **4 passed in 78.39s**; `test_canary.py` seit 91388d6 unverändert
- `KANARIE normal|ausfall-500|ausfall-412|ausfall-timeout geprüft 22 von 22` (4 Zeilen), 0 Zeilen `: nein`, 8 KONTROLLE-Zeilen `ja`
- CURSOR je Provider (circles 0, files 3, tables-search-tables 1, talk-message 0 Treffer, alle unter 100)
- AUSFALL: 500 call_count=24, 412 call_count=48 (Automat listet neu und fragt nochmal), timeout call_count=24; je 23 Antworten mit `EXCLUSION_UNAVAILABLE`
- CLEANUP: 64 Zeilen, alle gelesen ok, je Lauf 3 Werkzeug-Einträge (event 404, card gelöscht, row 404); files_upload, notes_create und talk_send wiesen ab (ABWEISUNG ja)

## Deviations from Plan

**1. [Owner-Entscheid, Rule 4] Neuer Fix in src/ (D-28-21)**
- Der Plan sah `git diff -- src/` leer vor. Der Kanarienbefund war durch keine Entscheidung gedeckt, Checkpoint, Owner wählte Option 1. Commits 19b6132 (Tests), f9f8773 (Fix), D-28-21 in 28-CONTEXT.md.

**2. [Rule 3 - Blockierend] pyright fand `result_shapes` nicht**
- `extraPaths` in `[tool.pyright]` spiegelt die pytest-`pythonpath`. Commit 91388d6.

**3. [Auslegung] talk_browse-Ebene `conversations` statt `rooms`**

**4. [Ergänzung] Scan über dekodierte Paging-Cursors, Marker-Fenster im Befund**

**5. [Reihenfolge] Code beider Tasks in einem Commit (91388d6)**

## Known Stubs

Keine.

## Threat Flags

Keine offenen; der Abfluss über talk-conversations (T-28-100) ist mit D-28-21 geschlossen und live belegt.

## Self-Check: PASSED

- FOUND: tests/integration/test_canary.py, raw/28-10-canary.txt, raw/28-10-befund-diagnose.txt, src/mcp_connector/tools/search.py
- FOUND: 91388d6, 0b4f152, cbee158, 19b6132, f9f8773
