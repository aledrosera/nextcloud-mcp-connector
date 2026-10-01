---
phase: 27-familien-anschluss-und-sandbox-parit-t
plan: 02
subsystem: files-familie
tags: [exclusion, kein-ki, files, upload-orakel, EXCL-01]
requires:
  - "27-01: dav.not_found / dav.parent_missing, NcClients.exclusion, tools/withhold.py, tests/unit/guard_routes.py"
provides:
  - "files.read/download/list_dir/search/upload/upload_binary fragen den Guard"
  - "files._visible_stat, files._visible_hits, files._writable, files._withheld"
  - "Degraded-Idiom der Datei-Familie: withhold.degraded_entry(\"source\")"
affects:
  - "27-07 (Live-Beweis Erfolgskriterium 1)"
  - "Phase 28 (Paartests byte-gleich), Phase 29 (Doku Restorakel Upload-Grenzfall)"
tech-stack:
  added: []
  patterns:
    - "asyncio.gather(scope, primär, return_exceptions=True) mit fester Entscheidungsreihenfolge"
    - "Filtern vor sort/Fenster; Nachladen mit verdoppeltem SEARCH-Limit"
    - "Prüfpunkt vor jedem Schreib-Request, ohne vorheriges stat"
key-files:
  created:
    - tests/unit/test_files_exclusion.py
    - tests/unit/test_files_upload_exclusion.py
  modified:
    - src/mcp_connector/tools/files.py
decisions:
  - "Grenzfall D-27-01 (direkt getaggte Datei unter sichtbarem Elternordner) bekommt dav.parent_missing(target); Begründung im Docstring von _writable, Restorakel für Phase 29"
  - "Paartests vergleichen getaggt gegen denselben Pfad als echten 404/409, nicht gegen einen anderen Pfad: der Satz enthält den Pfad, nur so ist die Tupelgleichheit aussagekräftig"
  - "search im Zustand unverifiable wertet auch einen SEARCH-Fehler nicht aus (gleiches Prinzip wie list_dir), Antwort trägt query, folder, note und degraded"
  - "_visible_hits bekommt die erste SEARCH-Antwort als Parameter first, damit der erste SEARCH parallel zum Guard läuft"
metrics:
  duration: "ca. 40 min"
  completed: 2026-09-27
  tasks: 3
  files: 3
---

# Phase 27 Plan 02: Datei-Familie am Guard Summary

Alle sechs Datei-Einstiege fragen den `kein-ki`-Guard: getaggte Einträge (direkt, darunter, per fileid bei abweichender Schreibweise) antworten wie nicht existent, Listen filtern vor dem Schnitt und laden bei Bedarf nach, Uploads werden vor jedem Schreib-Request mit dem echten Parent-missing-Satz abgewiesen; "nicht prüfbar" ergibt einen uniformen Fehler bzw. leere Liste mit genau einem degraded-Eintrag.

## Was gebaut wurde

**Task 1 (read/download):** `_visible_stat` bündelt `gather(scope, stat)` und die feste Reihenfolge: Guard-Exception, unverifiable (vor dem stat-Ergebnis, auch vor dessen 404), stat-Fehler, `excludes(path, fileid)` -> `dav.not_found(target)`, danach erst die Formprüfungen (Ordner, Nicht-Text, Offset). Eingabeprüfungen bleiben davor.

**Task 2 (list/search):** `list_dir` prüft das Ziel selbst vor der is-a-file-Prüfung, filtert Kinder vor `sort`/Fenster; unverifiable ergibt `{path, count: 0, items: [], degraded: [...]}` ohne Auswertung des PROPFIND. `search` nutzt `_visible_hits`: filtert, lädt mit verdoppeltem Limit nach (bis genug sichtbar, Rohliste kürzer als angefordert oder `MAX_SEARCH_FETCH`), Offsets und `truncated`/`next` beziehen sich auf die gefilterte Liste; untagged genau ein SEARCH wie bisher; der Cap-Zweig (`SEARCH_CAP_NOTE`) hängt am zweiten Rückgabewert.

**Task 3 (upload):** `_writable` vor `put_new_file` (upload und upload_binary leer), `start_chunked_upload`, `put_upload_chunk` und `finish_chunked_upload`; Zielpfad, nie die Upload-Session-URL; kein stat. Ein zwischen zwei Chunk-Aufrufen gesetztes Tag stoppt den nächsten Aufruf, MOVE call_count 0.

## Verifikation

- `ruff check .`, `ruff format --check .`: grün
- `pyright` (PYRIGHT_PYTHON_FORCE_VERSION=latest, `--pythonpath` auf die Hauptrepo-venv): 0 errors
- `vulture src scripts vulture_whitelist.py`: grün (Whitelist nicht angefasst)
- `pytest tests/unit tests/contract`: 4721 passed, 33 skipped
- `scripts/check_tool_budget.py`: exit 0, 17233/18000 Bytes, unverändert

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] KeyError bei stat-Ersatz ohne fileid**
- **Found during:** Task 3 (volle Suite)
- **Issue:** `test_file_transfer_review.py` ersetzt `dav.stat` durch ein Dict ohne `fileid`; `info["fileid"]` warf KeyError auch im Zustand untagged.
- **Fix:** `str(info.get("fileid") or "") or None`.
- **Files modified:** src/mcp_connector/tools/files.py
- **Commit:** f3fd6aa

**2. [Rule 3 - Blocking] Tag-Id-Cache zwischen Testszenarien**
- **Found during:** Task 3
- **Issue:** Nach einem active-Szenario ist die Tag-Id 60 s gecacht; ein folgendes untagged-Mock im selben Test schickte dann einen REPORT ohne Listing.
- **Fix:** Helfer `_untagged(mock)` in test_files_upload_exclusion.py ruft vorher `guard_routes.reset()`.
- **Commit:** f3fd6aa

**3. Paartests gegen denselben Pfad**
- Der Plan nennt z. B. "/Docs/fehlt.txt" bzw. "/Fehlt/neu.txt" als Vergleich; da `not_found`/`parent_missing` den Pfad in der Meldung tragen, wäre die Tupelgleichheit dort nie erfüllbar. Verglichen wird getaggt gegen denselben Pfad als echter 404 (PROPFIND) bzw. 409 (PUT/MKCOL), zusätzlich gegen die Fabrik. Für unverifiable (Meldung ohne Pfad) werden verschiedene Pfade verglichen.

### Ausführungsumgebung

- Worktree-Base war abweichend (7a93585) und wurde laut Auftrag per `git reset --hard f5efe94` korrigiert.
- pytest wie in 27-01 mit `-o "pythonpath=src tests/integration tests/unit"` über `../../../.venv`.

## TDD Gate Compliance

Tests und Implementierung je Task im selben feat-Commit; keine separaten RED-Commits (Warnung). Die Paartests für getaggte Pfade wären ohne Verdrahtung rot (Formfehler bzw. 201 statt Abweisung).

## Known Stubs

Keine.

## Threat Flags

Keine neue Angriffsfläche außerhalb des Threat-Modells. T-27-10 bis T-27-14 umgesetzt; T-27-15 (Zeitkanal) und T-27-16 (Upload-Grenzfall) wie geplant akzeptiert, Doku in Phase 29.

## Commits

- 8b48c90 feat(27-02): wire kein-ki guard into files_read and files_download
- 08dc34b feat(27-02): filter files_list and files_search before the window
- f3fd6aa feat(27-02): close the upload oracle for kein-ki destinations

## Self-Check: PASSED
