---
phase: 27-familien-anschluss-und-sandbox-parit-t
plan: 01
subsystem: guard-fundament
tags: [exclusion, kein-ki, dav, sandbox, test-infrastruktur]
requires:
  - "Phase 26: nextcloud/exclusion.py (TagScope, ExclusionGuard), clients/systemtags.py"
provides:
  - "dav.not_found / dav.parent_missing (einzige Quelle beider Sätze)"
  - "dav.paths_of_fileids / dav.build_fileids_body / dav.FILEID_BLOCK"
  - "NcClients.exclusion (frischer Guard je Bündel)"
  - "TagScope.has_folders"
  - "provider_map.file_id / provider_map.last_numeric_segment (öffentlich)"
  - "tools/withhold.py: EXCLUSION_UNAVAILABLE, DEGRADED_NAME, UNAVAILABLE_HINT, unavailable_error, degraded_entry, FileRef, file_refs, needs_paths"
  - "tests/unit/guard_routes.py: untagged, active, unverifiable, patch_untagged, reset, tag_list, report_207, listed"
affects:
  - "Pläne 27-02 bis 27-06 (Familien-Verdrahtung)"
  - "Phase 28 (byte-gleiche Paartests über die Fabriken)"
tech-stack:
  added: []
  patterns:
    - "Fehlerfabrik statt f-String-Kopie für Existenz-Sätze"
    - "TYPE_CHECKING-Import gegen Importzyklus Paket <-> Guard"
    - "autouse-Fixture patch_untagged als Schutz der Bestandstests"
key-files:
  created:
    - src/mcp_connector/tools/withhold.py
    - tests/unit/guard_routes.py
    - tests/unit/test_guard_routes.py
    - tests/unit/test_withhold.py
    - tests/unit/test_dav_fileid_paths.py
  modified:
    - src/mcp_connector/nextcloud/clients/dav.py
    - src/mcp_connector/nextcloud/exclusion.py
    - src/mcp_connector/nextcloud/__init__.py
    - src/mcp_connector/provider_map.py
    - pyproject.toml
    - vulture_whitelist.py
    - tests/unit/test_dav_home_entries.py
    - tests/unit/test_exclusion.py
    - tests/unit/test_provider_map.py
    - "tests/unit/test_{files_read,files_list,files_search,files_upload,file_transfer_review,unified_search,chatgpt_fetch,chatgpt_search,tools_context,notes_tools,talk_tools}.py"
decisions:
  - "IN-02: href wird segmentweise decodiert und gegen das decodierte Home-Präfix verglichen; ein Segment, das zu / oder NUL decodiert, ergibt None (statt Vergleich roh gegen kodiertes Präfix, robust gegen %2f/%2F und abweichende Kodierung von Sonderzeichen im User)"
  - "withhold._plain_home_path prüft strenger als der Plan (zusätzlich Punktsegment und Backslash), gleiche Regel wie dav._plain_path; ein nicht-plain Pfad wird None und die fileid entscheidet"
  - "build_fileids_body wirft ValueError (nicht ToolError) für nicht-ziffrige Ids; die Modell-Grenze bleibt build_fileid_body mit ToolError"
  - "Lokale Variable file_id in provider_map.extract_id zu fileid umbenannt, sonst verschattet sie die jetzt öffentliche Funktion file_id"
metrics:
  duration: "ca. 45 min"
  completed: 2026-09-27
  tasks: 3
  files: 27
---

# Phase 27 Plan 01: Guard-Fundament Summary

Segmentweises href-Decoding (IN-01/02/03), zwei Fehlerfabriken als einzige Quelle der Not-found- und Parent-missing-Sätze, blockweise fileid-zu-Pfad-Auflösung im Sandbox-Scope, ein frischer ExclusionGuard je NcClients ohne Importzyklus, `TagScope.has_folders`, das Helfermodul `tools/withhold.py` mit dem einen Wortlaut (D-27-05) und die Testinfrastruktur, die 284 Bestandstests beim ersten verdrahteten Guard grün hält.

## Was gebaut wurde

**Task 1 (dav.py):**
- `_home_prefix(creds)` ersetzt die zwei Kopien in `parse_entries` und `home_entries` (IN-01).
- `_home_path_of` decodiert jedes Segment einzeln; `A%2Fkein`, `A%2fkein`, `A%00B` werden None (IN-02). Der Review-Vorschlag `"/".join(unquote(seg) ...)` wurde bewusst nicht übernommen.
- `_plain_path` lehnt `//` als Stringprüfung ab, `/` bleibt gültig (IN-03).
- `not_found(path)` und `parent_missing(path)`; `_check` (404), `_check_write` und `_check_chunk_response` (404/409) werfen genau diese Objekte. Je Satz nur noch ein f-String im Modul.
- `FILEID_BLOCK = 50`, `build_fileids_body` (lxml, `d:or` über `d:eq`, eine Id delegiert an `build_fileid_body`), `paths_of_fileids` (ASCII-Ziffern-Prüfung vor jedem Request, Deduplizierung, Blöcke per `asyncio.gather`, Ergebnis nur für angefragte Ids, Sandbox über Scope und `parse_entries`).

**Task 2:**
- `exclusion.py`: `NcClients` nur noch unter `TYPE_CHECKING`, Annotationen als Strings; `TagScope.has_folders`, gesetzt in `_active` aus `node.is_collection` (Merker (e) erledigt).
- `NcClients.exclusion = field(default_factory=ExclusionGuard, compare=False, repr=False)`; `deps.resolve_clients` unverändert.
- `provider_map.file_id` und `provider_map.last_numeric_segment` öffentlich.
- `tools/withhold.py` mit allen im Plan genannten Namen, reine Funktionen, keine Modulzustände.

**Task 3:**
- `tests/unit/guard_routes.py` mit `untagged`, `active`, `unverifiable`, `patch_untagged`, `reset` sowie `tag_list`, `report_207`, `listed`; `test_guard_routes.py` beweist die drei Zustände über den echten Guard eines frischen NcClients und null Requests bei `patch_untagged`.
- `pyproject.toml`: `pythonpath = ["tests/integration", "tests/unit"]`.
- Vulture: `_.is_collection` entfernt (wird gelesen), Phase-26-Abschnitt "Empty again", neuer Abschnitt für 27-01 mit genau den sechs Namen, die vulture meldete: `excludes`, `paths_of_fileids`, `unavailable_error`, `degraded_entry`, `file_refs`, `needs_paths`. Die Konstanten und FileRef-Felder meldete vulture nicht, daher kein Eintrag.

## Messverfahren autouse-Fixture

Temporär (unkommittiert) am Anfang von files.search, list_dir, read, download, upload, upload_binary, search.unified_search, notes.search, read, create, talk.browse, send, chatgpt.fetch und context.prepare_context `await clients.exclusion.scope(clients)` eingefügt.

- **Ohne Fixture: 284 Tests rot** von 4709 gesammelten, verteilt auf:

| Modul | rot |
|-------|-----|
| test_talk_tools.py | 90 |
| test_chatgpt_fetch.py | 62 |
| test_files_read.py | 29 |
| test_files_upload.py | 25 |
| test_unified_search.py | 17 |
| test_notes_tools.py | 17 |
| test_files_search.py | 15 |
| test_files_list.py | 12 |
| test_file_transfer_review.py | 10 (nicht in der Planliste, zusätzlich gefunden) |
| test_chatgpt_search.py | 6 |
| test_errors_reason.py | 1 (siehe unten) |

- Die Fixture `_no_kein_ki_tag` steckt jetzt in 11 Modulen: die zehn aus der Planliste (darunter test_tools_context.py, das in der Messung grün blieb, als Vorsorge für die context-Verdrahtung) plus test_file_transfer_review.py.
- **Mit Fixture und temporärer Verdrahtung:** alles grün bis auf `test_errors_reason.py::test_the_talk_send_switch_says_a_guard_stopped_the_call`. Dieser Test ruft `talk.send(None, ...)` und beweist, dass der TALK-04-Schalter vor jedem Client-Zugriff greift. Das ist ein Artefakt der Messung (Guard vor dem Schalter), keine Lücke der Fixture: eine echte Verdrahtung darf in `send` nichts vor den Schalter setzen. Keine Fixture dort eingefügt.
- Verdrahtung per `git checkout` der sechs Tool-Dateien zurückgenommen; `git diff --stat -- src/mcp_connector/tools/files.py ... context.py` leer.

## Verifikation

- `ruff check .`, `ruff format --check .`: grün
- `pyright` (PYRIGHT_PYTHON_FORCE_VERSION=latest): 0 errors
- `vulture src scripts vulture_whitelist.py`: grün
- `pytest tests/unit tests/contract`: 4676 passed, 33 skipped
- `scripts/check_tool_budget.py`: exit 0, unverändert

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Verschattung in provider_map.extract_id**
- **Found during:** Task 2
- **Issue:** `extract_id` hatte die lokale Variable `file_id`; nach der Umbenennung von `_file_id` in `file_id` hätte `file_id = file_id(...)` einen UnboundLocalError ausgelöst.
- **Fix:** Lokale Variable in `fileid` umbenannt.
- **Files modified:** src/mcp_connector/provider_map.py
- **Commit:** 1d98b22

**2. [Rule 3 - Blocking] Docstring der Fixture umbrochen**
- **Found during:** Task 3
- **Issue:** Der im Plan vorgegebene Docstring ist in einer Zeile länger als 100 Zeichen (E501).
- **Fix:** Wortgleich, auf zwei Zeilen umbrochen.
- **Commit:** 7521441

**3. [Rule 2] Strengere Pfadprüfung in withhold.file_refs**
- Zusätzlich zu `..`, `//` und Steuerzeichen werden auch `.`-Segmente und Backslashes abgelehnt (gleiche Regel wie `dav._plain_path`, wie in RESEARCH verlangt). Folge nur: `path=None`, die fileid entscheidet, Eintrag bleibt dateitragend.

### Ausführungsumgebung

- Der Worktree hat keine eigene `.venv`; genutzt wurde `../../../.venv` des Hauptrepos. Diese venv importiert per Editable-Install den Hauptrepo-Baum, daher liefen alle pytest-Aufrufe mit `-o "pythonpath=src tests/integration tests/unit"` (per Probe bestätigt: `src` des Worktrees steht dann vorn). Der Import-Test in test_exclusion.py setzt `PYTHONPATH` für den Subprozess auf das `src` neben der Testdatei und ist damit in Worktree und Hauptrepo korrekt.
- Worktree-Base war abweichend und wurde laut Auftrag per `git reset --hard 2f03242` korrigiert.

## TDD Gate Compliance

- Task 1: RED-Commit `86ef4ed` (test), GREEN-Commit `a85a810` (feat), in dieser Reihenfolge.
- Task 2: Tests und Implementierung im selben feat-Commit `1d98b22`; kein separater RED-Commit (Warnung). Der Import-Zyklus-Test hätte vor der TYPE_CHECKING-Umstellung rot sein müssen, wurde aber nicht einzeln rot committet.
- Task 3: kein tdd-Task.

## Known Stubs

Keine. Die sechs Vulture-Einträge sind bewusst geparkte öffentliche Helfer ohne Aufrufer; sie bekommen ihre Aufrufer in 27-02 bis 27-06.

## Threat Flags

Keine neue Angriffsfläche außerhalb des Threat-Modells. T-27-01 bis T-27-06 umgesetzt wie geplant (segmentweises Decoding, `//`-Ablehnung, Fabriken, Ziffernprüfung plus lxml plus Blöcke zu 50, konstante Meldung ohne Pfad/Id, frischer Guard je Konstruktion ohne Modul-Cache).

## Commits

- 86ef4ed test(27-01): add failing tests for href decoding, error factories and paths_of_fileids
- a85a810 feat(27-01): fix href decoding, add error factories and batch fileid lookup
- 1d98b22 feat(27-01): add guard field to NcClients, has_folders and withhold helpers
- 7521441 test(27-01): add guard mock helpers and untagged autouse fixture

## Self-Check: PASSED
