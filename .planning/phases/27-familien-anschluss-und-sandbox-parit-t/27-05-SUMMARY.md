---
phase: 27-familien-anschluss-und-sandbox-parit-t
plan: 05
subsystem: talk-familie
tags: [exclusion, kein-ki, talk, fetch, live-probe]
requires:
  - "27-01: withhold.degraded_entry/unavailable_error/EXCLUSION_UNAVAILABLE, dav.paths_of_fileids, TagScope.has_folders, guard_routes"
  - "27-03: chatgpt.py im Stand nach fetch(file)"
provides:
  - "talk.FileScreen, talk.NO_SCREEN, talk.param_key, talk.file_screen (öffentlich, Aufrufer chatgpt._fetch_message)"
  - "_resolve mit Prädikat: verborgene Datei-Platzhalter bleiben roh wie unbekannte (D-27-06)"
  - "Datei-Konversationen getaggter Dateien fehlen in der Liste und antworten wie unbekannte Tokens (_unknown_token)"
  - "fetch(message) mit file_screen und metadata[degraded]"
  - "raw/27-05-file-conversation-probe.txt"
affects:
  - "talk_browse (beide Ebenen), talk_send (über one_room), fetch(message)"
  - "Phase 28: byte-gleiche Paartests über _unknown_token; Klassifikations-Freeze"
tech-stack:
  added: []
  patterns:
    - "Guard nur bei Datei-Bezug (Pitfall 8): Fenster ohne type-file-Parameter und ohne Datei-Raum kostet null Requests"
    - "Keyword-only-Parameter ohne Default (one_message(screen=...)), damit kein Aufrufer ungefiltert bleibt"
key-files:
  created:
    - tests/unit/test_talk_exclusion.py
    - tests/unit/test_fetch_message_exclusion.py
    - .planning/phases/27-familien-anschluss-und-sandbox-parit-t/raw/27-05-file-conversation-probe.txt
  modified:
    - src/mcp_connector/tools/talk.py
    - src/mcp_connector/tools/chatgpt.py
    - tests/integration/test_exclusion_probe.py
    - vulture_whitelist.py
decisions:
  - "Live-Befund nc35 (NC 35.0.0, spreed 25.0.0): OBJECT_TYPE=file, OBJECT_ID_IST_FILEID=ja, NAME_IST_DATEINAME=ja; Datei-Räume werden über objectId als fileid entschieden"
  - "Die Datei-Raum-Route ist /apps/spreed/api/v1/file/{fileId}, nicht api/v4 (v4 antwortet 404/998); im Rohbefund dokumentiert"
  - "Gast-Form path = name (ohne /) gilt als pfadlos und wird bei getaggtem Ordner über die fileid aufgelöst, sonst käme eine Gast-Datei unter einem getaggten Ordner durch"
  - "Nicht-plain Pfade (Punktsegment, //, Backslash, Steuerzeichen) gelten als pfadlos, gleiche Regel wie withhold._plain_home_path"
  - "fetch(message) screent nur die gewünschte Nachricht, nicht das ganze Kontextfenster: ein Nachbar mit Datei wird nie gezeigt und darf weder einen Guard-Request kosten noch die Antwort degraded markieren"
  - "Datei-Raum mit nicht-ziffriger objectId bekommt die Pseudo-id '-': verborgen, sobald irgendetwas getaggt ist (fail-closed), sichtbar nur bei untagged"
metrics:
  duration: "ca. 55 min"
  completed: 2026-09-27
  tasks: 3
  files: 8
---

# Phase 27 Plan 05: Talk-Familie am Guard Summary

Die eine Ersetzungsstelle `_resolve` lässt Platzhalter getaggter Dateien exakt als `{file}` stehen (gleicher Pfad wie ein unbekannter Platzhalter), Datei-Konversationen getaggter Dateien verschwinden aus der Liste und antworten auf browse, send und fetch byte-gleich zum unbekannten Token; der Befund `objectId = fileid` ist live auf nc35 gemessen, und fetch(message) trägt bei nicht prüfbar `metadata["degraded"]`.

## Was gebaut wurde

**Task 1 (talk.py):**
- `FileScreen` (frozen, slots) mit `hides(entry)` und `hides_room(fileid)`, Konstante `NO_SCREEN`, `param_key(entry)`.
- `file_screen(clients, messages, room_fileids=())`: sammelt type-file-Parameter und Datei-Raum-ids; nichts gesammelt -> `NO_SCREEN` ohne Guard; untagged -> `NO_SCREEN`; unverifiable -> alles verborgen plus `unavailable`; active -> Pfad und fileid über `scope.excludes`, pfadlose ids bei `has_folders` mit genau einem `dav.paths_of_fileids`-Aufruf (nicht aufgelöst = verborgen, Fehler = alles verborgen plus unavailable).
- `_resolve(message, parameters, screen)`: `if screen.hides(entry): return match.group(0)` direkt nach der dict-Prüfung; Docstring mit dem D-27-06-Satz.
- `_message`, `_preview`, `_conversation` nehmen den Screen; `one_message(window, message_id, *, screen)` keyword-only ohne Default.
- `_messages` und `_conversations`: ein Screen je Antwort, bei `unavailable` genau ein `degraded: [{"source": "exclusion", "reason": EXCLUSION_UNAVAILABLE}]`.

**Task 2 (Live-Probe + Datei-Räume):**
- `test_file_conversation_probe`: Probe-Datei als alice, Share an NC_MCP_TEST_USER2 (shareType 0), Raum über die file-Route, Join/Leave der Session, Raumliste lesen, Rohbefund schreiben; finally: Teilnahme verlassen, Share löschen, Datei löschen (PROPFIND danach 404).
- `_room_fileid(room)`, `_unknown_token(token)` (einzige Stelle des Satzes), Filter in `_conversations` vor dem Schnitt (total/truncated aus der gefilterten Liste), `one_room` prüft nur Datei-Räume (unverifiable -> `withhold.unavailable_error()`, verborgen -> `_unknown_token`).

**Task 3 (chatgpt.py + Whitelist):**
- `_fetch_message`: `screen = await talk_tools.file_screen(clients, [gewünschte Nachricht])`, `one_message(..., screen=screen)`, bei `screen.unavailable` `metadata["degraded"] = withhold.EXCLUSION_UNAVAILABLE`. Datei-Räume erbt fetch über `one_room`; one_room und file_screen teilen den Guard (ein REPORT je fetch, getestet).
- `vulture_whitelist.py`: Abschnitt "The withholding helpers of plan 27-01" geleert ("Empty again, as announced"); alle sechs Namen haben jetzt Aufrufer in src, kein Eintrag wartet auf 27-06.

## Verifikation

- Live-Probe gegen nc35: 1 passed, Rohbefund committet (`OBJECT_ID_IST_FILEID=ja`).
- `ruff check .`, `ruff format --check .`: grün; pyright (latest): 0 errors; vulture: grün; `pytest tests/unit tests/contract`: 4808 passed, 33 skipped; `check_tool_budget.py`: exit 0.
- Akzeptanz-Greps: `async def file_screen|class FileScreen|^NO_SCREEN|def param_key` = 4; `screen.hides(entry)` = 1; `def _unknown_token|def _room_fileid` = 2; Unbekannt-Satz außerhalb von Kommentaren = 1; `talk_tools.file_screen` in chatgpt.py = 1; `screen=screen` = 1; `_.excludes` in der Whitelist = 0.
- Pflichttests: `test_a_window_without_a_file_costs_no_guard_request`, `test_json_dumps_of_the_answer_carries_neither_the_name_nor_the_path`, Paartests `test_the_history_of_a_tagged_file_conversation_answers_like_an_unknown_token` und `test_sending_into_a_tagged_file_conversation_answers_like_an_unknown_token` (POST call_count 0), `test_fetch_in_a_tagged_file_conversation_answers_like_an_unknown_token`, `test_one_report_per_browse_however_many_file_parameters`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] one_message-Aufruf in chatgpt.py schon in Task 1 angepasst**
- **Found during:** Task 1
- **Issue:** Die neue keyword-only-Signatur hätte fetch(message) bis Task 3 gebrochen.
- **Fix:** Zwischenstand `screen=talk_tools.NO_SCREEN` in Task 1, in Task 3 durch den echten Screen ersetzt.
- **Commit:** 5cb56fd, bdfadbd

**2. [Rule 1 - Bug] Gast-Form path = name**
- **Issue:** Mit dem Plan-Wortlaut (path nutzen, wenn nicht leer) wäre `path = "c.pdf"` eines Gastes als `/c.pdf` geprüft worden und eine Datei unter einem getaggten Ordner durchgekommen.
- **Fix:** Pfad ohne `/`, der dem Namen gleicht, gilt als pfadlos und wird über die fileid aufgelöst; Test `test_a_guest_path_equal_to_the_name_is_resolved_by_its_id_below_a_folder`.
- **Commit:** 5cb56fd

**3. [Rule 1 - Bug] fetch(message) screent nur die gewünschte Nachricht**
- **Issue:** `file_screen(clients, window)` laut Plan hätte eine Datei im Nachbarn der gewünschten Nachricht zu einem Guard-Request und bei nicht prüfbar zu `metadata["degraded"]` geführt, obwohl die Antwort den Nachbarn nie zeigt (widerspricht "Nachricht ohne Datei-Parameter -> kein degraded, kein Guard-Request").
- **Fix:** Nur die Nachricht mit der gewünschten id geht in den Screen; Test `test_a_message_without_a_file_costs_no_guard_request_and_says_nothing` mit Datei-Nachbarn.
- **Commit:** bdfadbd

**4. [Rule 3 - Blocking] Datei-Raum-Route ist api/v1**
- Die im Plan genannte Route `api/v4/file/{fileId}` antwortet auf spreed 25.0.0 mit 404/998; `api/v1/file/{fileId}` liefert den Token. Die Probe fragt beide und protokolliert beide Antworten.
- Zusätzlich nötig: Join der Session (`participants/active`), sonst steht der Raum nicht in der Liste des Kontos.

**5. [Rule 3 - Blocking] Capabilities-Cache in den neuen Testmodulen**
- In der gemeinsamen Ausführung mit test_chatgpt_fetch.py leckte ein Capabilities-Cache ohne spreed in die neuen Module (AppMissingError). Beide neuen Module leeren den Cache jetzt je Test.
- **Commit:** bdfadbd

### Ausführungsumgebung

- Wie in 27-01/27-03: venv des Hauptrepos (`../../../.venv`), pytest mit `-o "pythonpath=src tests/integration tests/unit"`, pyright mit `--pythonpath ../../../.venv/Scripts/python.exe`.
- `.env.nc35` per kurzem `python -c`-Lader eingelesen, pytest als Subprozess; das Kommando in der Rohdatei ist das geplante.
- Worktree-Base war abweichend und wurde laut Auftrag per `git reset --hard 759d6c7` korrigiert.

## Merker für Phase 28

- **talk_send ist durch one_room betroffen:** ein Token eines Datei-Raums einer getaggten Datei wird vor dem POST mit `_unknown_token` abgewiesen, bei nicht prüfbar mit `withhold.unavailable_error()`. Für den Klassifikations-Freeze zählt talk_send damit zu den betroffenen Werkzeugen.
- **ChatGPT-search trägt kein degraded-Feld** (Befund aus 27-03, gilt weiter); fetch(message) dagegen trägt `metadata["degraded"]`.
- Byte-gleiche Paartests laufen über `_unknown_token` (browse, send, fetch).

## Merker für Phase 29

- Mit gesetztem `NC_MCP_FILES_ROOT` und getaggtem Ordner bleiben pfadlose Datei-Verweise außerhalb der Root roh (sie lösen im Sandbox-Scope von `paths_of_fileids` nicht auf). Talk hat keine eigene Sandbox für Dateinamen (T-27-46 accept).

## TDD Gate Compliance

- Task 1: RED `6d95c99`, GREEN `5cb56fd`.
- Task 2: Probe `8d31432`, RED `de6b576`, GREEN `944ec1f`.
- Task 3: RED `3870961`, GREEN `bdfadbd`.

## Known Stubs

Keine.

## Threat Flags

Keine neue Angriffsfläche außerhalb des Threat-Modells. T-27-40 bis T-27-45 umgesetzt wie geplant; T-27-46 bewusst akzeptiert (Merker Phase 29). Die Probe schreibt auf nc35 nur eigene Probe-Datei, Share und Teilnahme und räumt sie im finally auf.

## Commits

- 6d95c99 test(27-05): add failing tests for talk placeholders behind the guard
- 5cb56fd feat(27-05): keep placeholders of tagged files raw in talk_browse
- 8d31432 test(27-05): live probe of a file conversation on nc35
- de6b576 test(27-05): add failing tests for file conversations behind the guard
- 944ec1f feat(27-05): hide file conversations of tagged files like unknown tokens
- 3870961 test(27-05): add failing tests for fetch(message) behind the guard
- bdfadbd feat(27-05): screen fetch(message) and empty the parked whitelist section

## Self-Check: PASSED
