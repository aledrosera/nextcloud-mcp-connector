---
phase: 27-familien-anschluss-und-sandbox-parit-t
plan: 04
subsystem: notes-familie
tags: [exclusion, kein-ki, sandbox, notes, orakel]
requires:
  - "27-01: withhold.py, dav.paths_of_fileids, dav.parent_missing, dav.in_files_root, NcClients.exclusion, guard_routes"
provides:
  - "notes_search/notes_read/notes_create an Guard und NC_MCP_FILES_ROOT (EXCL-05, SBX-02)"
  - "tools.notes._note_not_found (ein Satz für jeden Nicht-Treffer von notes_read)"
  - "clients.notes.get_settings (notesPath, fileSuffix)"
affects:
  - "fetch(note:<id>) in chatgpt.py erbt Guard und Satz über notes_tools.read (unverändert)"
  - "27-07 Live-Beweis Erfolgskriterium 3"
  - "Phase 29: Restorakel Titel-Sanitisierung bei notes_create"
tech-stack:
  added: []
  patterns:
    - "asyncio.gather(scope, Fachanfrage, return_exceptions=True), danach feste Prüfreihenfolge"
    - "Degraded-Idiom withhold.degraded_entry(\"source\") in der Notes-Suche"
key-files:
  created:
    - tests/unit/test_notes_exclusion.py
    - .planning/phases/27-familien-anschluss-und-sandbox-parit-t/raw/27-04-notes-settings.txt
  modified:
    - src/mcp_connector/tools/notes.py
    - src/mcp_connector/nextcloud/clients/notes.py
    - tests/unit/test_notes_tools.py
decisions:
  - "Settings-Fehler jeder Art (auch 401/500) in notes_create werden zu withhold.unavailable_error(), wie im Plan verlangt (fail-closed)"
  - "Kategorie wird für die Prüfung an beiden Enden von / befreit (\"/Geheim/\" prüft wie \"Geheim\"); an create_note geht sie wie bisher nur whitespace-getrimmt"
  - "skipped aus unbrauchbaren resourceUrls bleibt auch im degraded-Zweig der Suche erhalten (sagt nichts über ein Tag)"
metrics:
  duration: "ca. 35 min"
  completed: 2026-09-27
  tasks: 2
  files: 6
---

# Phase 27 Plan 04: Notes an Guard und Sandbox Summary

notes_search filtert getaggte Notizen lautlos und zählt Sandbox-Drops in `skipped`, notes_read antwortet für fünf Nicht-Treffer-Fälle mit einem byte-gleichen Fehler ohne den Fremdtext der Notes-App, und notes_create prüft Ablage und Kandidatdatei (aus `GET /settings`) vor jedem POST.

## Was gebaut wurde

**Task 1 (search, read):**
- `search`: Guard und Provider-Anfrage parallel; `unverifiable` ergibt `{count: 0, results: [], degraded: [degraded_entry("source")]}`. Nur wenn `withhold.needs_paths(scope)` (getaggter Ordner oder Root nicht `/`) ein `dav.paths_of_fileids` für alle Treffer-Ids; scheitert es, derselbe degraded-Zweig. Fehlende Id = Sandbox-Drop (`skipped +1`), `scope.excludes(path, fileid)` = lautloser Tag-Drop. Bei Root `/` ohne getaggten Ordner kein fileid-SEARCH (E3).
- `read`: `asyncio.gather(scope, get_note)`; Reihenfolge scope-Exception, unverifiable (`unavailable_error`), `excludes(fileid)`, Notes-404/998 (`_note_not_found`), andere Fehler, dann Pfadprüfung über `_check_note_path` (Lookup-Fehler = `unavailable_error`, fehlend oder ausgeschlossen = `_note_not_found`). Die geholte Notiz verlässt die Funktion in keinem Abweisungszweig.
- `_note_not_found(note_id)`: "Nextcloud did not find the note {id}." mit dem bisherigen Hint und `REASON_UNKNOWN_ID`.

**Task 2 (create):**
- Live-Messung der Settings-Route gegen nc35 (Notes 6.1.0): `{"notesPath":"Notes","fileSuffix":".md",...}`; Form wie angenommen, keine Anpassung nötig. Rohbefund in `raw/27-04-notes-settings.txt` (ohne App-Passwort).
- `clients.notes.get_settings`.
- `create`: `asyncio.gather(scope, get_settings)`; unverifiable, Settings-Fehler oder unbrauchbares `notesPath` (fehlt, kein str, leer, `/`) = `unavailable_error`. Ablage `"/" + notesPath [+ "/" + Kategorie]`, Kandidat `Ablage/Titel + fileSuffix` (Fallback `.md`). Ablage außerhalb der Sandbox (auch `..`-Kategorien) = eigener Satz "Notes are stored in {folder}, outside the folder this server may access." mit Hint auf NC_MCP_FILES_ROOT; `scope.excludes(path=candidate)` = `raise dav.parent_missing(candidate)`. Erst danach der POST.

## Tests

- `tests/unit/test_notes_exclusion.py` (neu, ohne patch_untagged, 36 Tests): drei Zustände für search, Paartest read (a) bis (e) mit identischem Tupel und ohne "Nextcloud says", unverifiable für Id 933 und 999, Pfad-Lookup-Fehler, `card:1` vor jedem Guard-/Notes-Request, alle create-Abweisungen mit POST call_count 0.
- `tests/unit/test_notes_tools.py`: 404-Test bewusst auf den neuen Satz umgestellt und umbenannt (`..._without_the_notes_detail_text`); create-Tests mit Settings-Route ergänzt.

## Verifikation

- ruff check, ruff format --check: grün
- pyright (latest, `--pythonpath` auf die Hauptrepo-venv): 0 errors
- vulture: grün (kein neuer Whitelist-Eintrag nötig)
- pytest tests/unit tests/contract: 4712 passed, 33 skipped
- check_tool_budget.py: exit 0 (17233 von 18000 Bytes, unverändert)

## Deviations from Plan

Keine inhaltlichen. Hinweise:
- Der RED-Commit enthält die Tests beider Tasks in einer Datei (ein test-Commit vor beiden feat-Commits), statt je Task einen eigenen RED-Commit.
- Ausführungsumgebung wie in 27-01: venv des Hauptrepos (`../../../.venv`), pytest mit `-o "pythonpath=src tests/integration tests/unit"`, pyright mit `--pythonpath`. Worktree-Base war abweichend und wurde per `git reset --hard f5efe94` korrigiert.
- vulture_whitelist.py und chatgpt.py nicht angefasst (wie verlangt).

## TDD Gate Compliance

- RED `ee01a88`: test-Commit vor beiden feat-Commits, Tests liefen vor der Implementierung rot.
- GREEN: Task 1 `89da240`, Task 2 `a944d28`.

## Merker für Phase 29 (Restorakel, T-27-35 accept)

- Die Notes-App sanitisiert Titel zu Dateinamen; der Kandidatpfad kann vom echten Namen abweichen, sodass eine Kollision mit einer getaggten Notiz unter anderem Dateinamen nicht erkannt wird.
- Jede Abweisung (parent_missing, Sandbox-Satz) unterscheidet sich vom Erfolg; ein Modell kann per Probeschreiben erfahren, dass unter einer Kategorie etwas ausgeschlossen ist.
- Ein Titel mit `/` oder `..` wird nicht gegen die Sandbox geprüft (nur die Ablage); die Notes-App entfernt solche Zeichen nach bisherigem Wissen, live nicht gemessen.
- Unter `unverifiable` geht der Notes-GET von notes_read trotzdem raus (parallel); die Antwort wird verworfen.

## Known Stubs

Keine.

## Threat Flags

Keine neue Angriffsfläche außerhalb des Threat-Modells. T-27-30 bis T-27-34 umgesetzt, T-27-35 als Merker oben.

## Commits

- ee01a88 test(27-04): add failing tests for the notes guard and sandbox
- 89da240 feat(27-04): guard and sandbox for notes_search and notes_read
- a944d28 feat(27-04): notes_create never writes into excluded or sandbox-foreign folders

## Self-Check: PASSED

- Dateien vorhanden: tools/notes.py, clients/notes.py, test_notes_exclusion.py, test_notes_tools.py, raw/27-04-notes-settings.txt
- Commits vorhanden: ee01a88, 89da240, a944d28
