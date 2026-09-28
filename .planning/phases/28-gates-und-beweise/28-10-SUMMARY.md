---
phase: 28-gates-und-beweise
plan: 10
subsystem: tests/integration (Kanarie GATE-02)
tags: [gate-02, live, nc35, canary, befund]
status: checkpoint
requires:
  - 28-02 (result_shapes, tool_classes)
  - 28-07 (canary_world)
provides:
  - tests/integration/test_canary.py (vier Modi, 22 Werkzeuge)
  - Rohbefund talk-conversations in raw/28-10-canary.txt und raw/28-10-befund-diagnose.txt
affects: [28-11]
tech-stack:
  added: []
  patterns: [Scan inklusive dekodierter Paging-Cursors, Marker-Fenster statt Anfangsauszug im Befund, Diagnose-Durchlauf mit protokollierendem check]
key-files:
  created:
    - tests/integration/test_canary.py
    - .planning/phases/28-gates-und-beweise/raw/28-10-canary.txt
    - .planning/phases/28-gates-und-beweise/raw/28-10-befund-diagnose.txt
  modified:
    - pyproject.toml
decisions:
  - "Kein Fix in src/: der Leck-Befund über talk-conversations ist durch keine Entscheidung in 28-CONTEXT.md gedeckt, Owner entscheidet (Checkpoint)"
  - "talk_browse-Ebene heißt conversations (Literal der Registry), nicht rooms wie im Plan"
metrics:
  duration: ca. 45 min
  completed: 2026-09-28
---

# Phase 28 Plan 10: Kanarie GATE-02 Summary

Die Kanarie ruft alle 22 Werkzeuge der Registry über `Client(mcp)` in vier Modi auf und findet gegen nc35 einen echten Abfluss: `unified_search` (Provider `talk-conversations`), `prepare_context` (full und short) und `search` nennen den Datei-Raum der getaggten Datei mit ihrem Namen samt Marker, im Normalbetrieb und im Ausfall. Plan gestoppt, Owner-Entscheid nötig.

## Tasks

| Task | Name | Commit | Status |
| ---- | ---- | ------ | ------ |
| 1 | Aufrufplan, Scan, Blättern, Kontroll-Marker (Normalbetrieb) | 91388d6 | Code fertig, live rot (Befund) |
| 2 | Drei Ausfallformen und Lauf gegen nc35 | 91388d6 (Code), 0b4f152 (Rohbefund) | gestoppt am Befund |

## Befund (roh)

- Lauf: `PYTHONUTF8=1 .venv/Scripts/python.exe -m pytest tests/integration/test_canary.py -m integration -s -k normal`, Env aus `.env.nc35` in Python geladen, sechs `NC_MCP_E2E_*`-Exporte, `PYTHONPATH=<worktree>/src`; Ergebnis 1 failed.
- raw/28-10-canary.txt Zeile 81: `GATE-02 unified_search normal {"limit": 100, "query": "kanarie28x53683f9c"} seite 1: nein (@1555: ...{"id":"url:http://127.0.0.1:8082/call/6nzewyoh","title":"kanarie28x53683f9c-mkd96c55ed220a499e9068e4545671bda9.txt",...,"provider":"talk-conversations","kind":"url"...)`
- Diagnose-Durchlauf (raw/28-10-befund-diagnose.txt, `check` protokolliert nur): Normalbetrieb und Ausfall timeout je `KANARIE geprüft 22 von 22`; `: nein` genau bei unified_search, prepare_context full, prepare_context short, search, in beiden Modi. Alle anderen 18 Werkzeuge sauber, alle KONTROLLE-Zeilen `ja`, `AUSFALL timeout report-route call_count=24`, alle CLEANUP-Zeilen gelesen ok.
- Ursache: Der Unified-Search-Provider `talk-conversations` antwortet mit dem Datei-Raum (Talk-Raum einer Datei, `displayName` = Dateiname). `tools/search.py:_screen` behandelt den Treffer als nicht dateitragend (`withhold.file_refs` liefert `file_bearing=False`, Provider nicht in `_FILE_SHARE_PROVIDERS`) und behält ihn. `talk_browse` hält Datei-Räume über `_room_fileid` (`tools/talk.py:874-887`, objectType `file`) zurück, der Suchweg nicht. `prepare_context` und `search` erben das über unified_search.

## Optionen für den Owner

1. talk-conversations-Treffer in `unified_search` gegen die Raumliste prüfen (objectType `file` und objectId getaggt, im Ausfall fail-closed wie talk_browse). Genauester Weg, ein Raum-Lookup mehr.
2. talk-conversations-Treffer in `unified_search` ganz zurückhalten (provider_map sagt schon: ein Gespräch ist kein Dokument, talk_browse ist der Weg). Kleinster Eingriff, verliert Raum-Treffer ohne Datei.
3. Als Grenze dokumentieren. Widerspricht GATE-02 und dem Kernversprechen, nicht empfohlen.

Nach dem Entscheid: Fix in src/ (eigener Plan oder Nachtrag), dann raw/28-10-canary.txt für den Beweislauf neu beginnen und `tests/integration/test_canary.py` ohne Änderung laufen lassen (erwartet 4 passed).

## Deviations from Plan

**1. [Rule 3 - Blockierend] pyright fand `result_shapes` nicht**
- pytest hat `tests/contract` im `pythonpath`, pyright nicht. `extraPaths` in `[tool.pyright]` spiegelt die pytest-Pfade. Commit 91388d6.

**2. [Auslegung] talk_browse-Ebene `conversations` statt `rooms`**
- Die Registry kennt nur `conversations` und `messages`.

**3. [Ergänzung] Scan auch über dekodierte Paging-Cursors und Marker-Fenster im Befund**
- `next` und Provider-`cursors` werden roh und per `paging.decode_cursor` gescannt; der Befundtext zeigt ein Fenster um den Marker statt der ersten 200 Zeichen (sonst war die Fundstelle unsichtbar).

**4. [Reihenfolge] Code beider Tasks in einem Commit**
- Die Ausfall-Parametrisierung entstand mit Task 1 zusammen; Task 2 blieb am Befund stehen.

## Offene Akzeptanzkriterien (wegen Checkpoint)

- raw/28-10-canary.txt enthält die zwei roten Normalläufe (`: nein`), noch keine vier grünen `geprüft 22 von 22`-Zeilen.
- pytest gegen nc35 noch nicht 4 passed.
- `git diff -- src/` leer (erfüllt), Qualitätsgates grün (ruff, format, pyright latest 0 Fehler, vulture, Budget, unit+contract Exit 0).

## Known Stubs

Keine.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: information-disclosure | src/mcp_connector/tools/search.py | talk-conversations-Treffer nennen den Namen einer getaggten Datei (Datei-Raum), auch in prepare_context und search; T-28-100 live rot |

## Self-Check: PASSED

- FOUND: tests/integration/test_canary.py, raw/28-10-canary.txt, raw/28-10-befund-diagnose.txt
- FOUND: 91388d6, 0b4f152
