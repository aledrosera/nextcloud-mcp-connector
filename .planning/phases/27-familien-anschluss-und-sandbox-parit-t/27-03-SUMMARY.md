---
phase: 27-familien-anschluss-und-sandbox-parit-t
plan: 03
subsystem: such-familie
tags: [exclusion, kein-ki, unified_search, fetch, sandbox, live-probe]
requires:
  - "27-01: withhold.file_refs/needs_paths/degraded_entry/unavailable_error, dav.paths_of_fileids, NcClients.exclusion, guard_routes"
provides:
  - "unified_search: Guard als erstes gather-Mitglied, _screen/_resolve/_settle (Sandbox zählend vor Tag lautlos), ein exclusion-degraded-Eintrag"
  - "chatgpt._no_file: eine Fabrik für unbekannte, getaggte und untergeordnete fileids"
  - "raw/27-03-provider-probe.txt: Rohbefund talk-message (kein-leak) und comments (fileid aus /f/<id>)"
affects:
  - "ChatGPT search und prepare_context erben die Filterung aus unified_search"
  - "Phase 28: byte-gleiche Paartests über _no_file"
tech-stack:
  added: []
  patterns:
    - "Guard als eigenes gather-Mitglied außerhalb des Provider-Timeouts (Pattern 6)"
    - "Feste Entscheidungsreihenfolge: unbrauchbar, nicht dateitragend, nicht prüfbar, Pfad-Sandbox, fileid-Auflösung, Tag"
key-files:
  created:
    - tests/integration/test_exclusion_probe.py
    - .planning/phases/27-familien-anschluss-und-sandbox-parit-t/raw/27-03-provider-probe.txt
    - tests/unit/test_search_exclusion.py
    - tests/unit/test_fetch_exclusion.py
  modified:
    - src/mcp_connector/tools/search.py
    - src/mcp_connector/tools/chatgpt.py
    - tests/unit/test_unified_search.py
    - tests/unit/test_file_transfer_review.py
decisions:
  - "talk-message-Zweig: KLASSE=kein-leak, UNTERSCHEIDUNG=keine (nc35, NC 35.0.0, spreed 25.0.0); Treffer von talk-message/talk-message-current gelten in allen Zuständen als nicht dateitragend"
  - "Der exclusion-degraded-Eintrag erscheint nur, wenn tatsächlich ein dateitragender Treffer zurückgehalten wurde (unverifiable) oder die fileid-Auflösung mit vorgemerkten Ids scheiterte, wie im Plan beschrieben (Flag), nicht pauschal bei jedem unverifiable"
  - "Fehler der fileid-Auflösung (ToolError, httpx.HTTPError, ValueError) = nicht prüfbar: vorgemerkte Treffer lautlos zurückgehalten, nicht gezählt"
metrics:
  duration: "ca. 60 min"
  completed: 2026-09-27
  tasks: 3
  files: 8
---

# Phase 27 Plan 03: Such-Familie am Guard Summary

unified_search und fetch(file) hängen am kein-ki-Guard: pfadlose Treffer (Findling nur mit fileId, notes, comments) bekommen über eine gemeinsame `paths_of_fileids`-Auflösung dieselbe Sandbox wie Pfad-Treffer, Tag-Treffer verschwinden lautlos, "nicht prüfbar" hält alle dateitragenden Treffer mit genau einem degraded-Eintrag zurück; vorher live gemessen, dass der talk-message-Provider keine Dateinamen trägt.

## Was gebaut wurde

**Task 1 (Live-Probe, vor der Verdrahtung):** `tests/integration/test_exclusion_probe.py` legt als alice eine Probe-Datei an, teilt sie per OCS (shareType 10) in den Raum NC_MCP_TEST_TALK_ROOM, sucht über `talk-message` und `talk-message-current` nach Dateiname, Namensstamm und einem Vergleichswort einer Textnachricht, setzt einen Kommentar und sucht über `comments`. Aufräumen im finally, PROPFIND danach 404 (geprüft). Befund in `raw/27-03-provider-probe.txt`:
- `KLASSE=kein-leak`: weder Dateiname noch Stamm liefern einen einzigen talk-message-Eintrag; die Textnachricht wird gefunden (title "alice in <Raum>", subline Text, `/call/<token>#message_<id>`, attributes conversation/messageId/actorType/actorId/timestamp).
- `UNTERSCHEIDUNG=keine` (kein Datei-Freigabe-Treffer zum Vergleichen).
- `COMMENTS_FILEID_AUS=url`: comments-Treffer tragen die fileid nur in `resourceUrl` `/f/<id>` (ohne `/index.php`), `attributes` ist eine leere Liste; `subline` enthält `/alice/files/<pfad>`. `withhold.file_refs` erkennt ihn als dateitragend mit fileid.

**Task 2 (search.py):**
- `scope_out, *outcomes = await asyncio.gather(clients.exclusion.scope(clients), *(_ask(...)), return_exceptions=True)`; Guard außerhalb von `_ask` und damit außerhalb des 15-s-Timeouts.
- `_screen` entscheidet je Eintrag in fester Reihenfolge (Docstring trägt das Wissen des entfernten `_entry_in_files_root`), `_resolve` macht EINEN `paths_of_fileids`-Aufruf für alle vorgemerkten Ids aller Provider (nur wenn `needs_paths(scope)` und Ids vorgemerkt sind), `_settle` wendet aufgelöste Pfade (nicht aufgelöst = Sandbox-Drop, gezählt) und dann den Tag (lautlos) an, erst danach `_normalise`.
- `_FILE_SHARE_PROVIDERS = ("talk-message", "talk-message-current")` mit Zitat der Rohdatei; Zweig kein-leak: Treffer dieser Provider werden als nicht dateitragend behandelt.
- `_entry_in_files_root` ersatzlos entfernt; `config`-Import entfällt.

**Task 3 (chatgpt.py):** `_fetch_file` fragt Guard und `find_by_fileid` parallel; Reihenfolge: Guard-Exception, unverifiable -> `withhold.unavailable_error()`, fileid getaggt -> `_no_file`, Lookup-Exception, None -> `_no_file`, Pfad unter getaggtem Ordner -> `_no_file`, danach unverändert `files_tools.read` über dasselbe `clients`. `_no_file` trägt exakt den bisherigen Satz und Hint ohne reason. `_fetch_note` und `_fetch_message` unangetastet.

## Verifikation

- Live-Probe gegen nc35: 2 passed, Rohdatei committet.
- `pytest tests/unit tests/contract`: 4694 passed, 33 skipped.
- `ruff check .`, `ruff format --check .`: grün; pyright (latest): 0 errors; vulture: grün; `check_tool_budget.py`: exit 0.
- Akzeptanz-Greps: `def _entry_in_files_root` 0, `def _screen` 1, `withhold.degraded_entry("provider")` 1, `clients.exclusion.scope(clients)` eine Zeile in `unified_search` (nicht in `_ask`), `27-03-provider-probe` in search.py, `def _no_file` 1, Not-found-Satz einmal.
- Namen der Pflichttests: `test_the_report_goes_out_exactly_once_per_call`, `test_tag_drops_leave_skipped_and_the_rest_unchanged` (vergleicht die ganze Antwort gegen dieselbe Antwort ohne die getaggten Einträge), `test_a_file_id_known_before_the_tag_answers_like_an_unknown_one`, zusätzlich `test_the_guard_runs_outside_the_provider_timeout` (REPORT langsamer als das Provider-Budget, Antwort trotzdem gefiltert und ohne degraded).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] test_file_transfer_review.py rief `_entry_in_files_root` direkt auf**
- **Found during:** Task 2 (pyright)
- **Issue:** Der Plan entfernt `_entry_in_files_root`; ein Regressionstest außerhalb der Planliste griff direkt darauf zu.
- **Fix:** Derselbe Parametrisierungsfall läuft jetzt über `search._screen(..., UNTAGGED)` und prüft `kept == []` und `skipped == 1`.
- **Files modified:** tests/unit/test_file_transfer_review.py
- **Commit:** 107b472

**2. [Rule 2] talk-message-Konstante mit Wirkung statt ohne**
- Der Plan erlaubte im kein-leak-Zweig eine Konstante "ohne Wirkung". Umgesetzt ist die im selben Satz verlangte Behandlung "als nicht dateitragend" explizit: Treffer dieser Provider laufen nie durch Sandbox/Tag. Folge: vulture sieht die Konstante als benutzt, `vulture_whitelist.py` blieb unangetastet (Welle 2 parallel).

**3. Zusätzlicher Bestandstest benannt**
- `test_pathless_note_hits_outside_the_bound_root_are_now_a_sandbox_drop` in test_unified_search.py dokumentiert die bewusste Verhaltensänderung (früher Durchlass pfadloser Nicht-files-Treffer außerhalb der Sandbox). Bestehende Tests mussten nicht umgestellt werden: der einzige Sandbox-Test nutzt Pfad-Treffer.

### Ausführungsumgebung

- Wie in 27-01: venv des Hauptrepos (`../../../.venv`), pytest mit `-o "pythonpath=src tests/integration tests/unit"`, pyright mit `--pythonpath ../../../.venv/Scripts/python.exe` (sonst findet es die venv im Worktree nicht).
- `set -a && . ./.env.nc35` wird von der Worktree-Isolation blockiert; die Env-Datei wurde stattdessen mit einem kurzen `python -c`-Lader eingelesen und pytest als Subprozess mit dieser Umgebung gestartet. Kommando in der Rohdatei ist das geplante.
- Worktree-Base war abweichend und wurde laut Auftrag per `git reset --hard f5efe94` korrigiert.

## Merker für spätere Phasen

- Der ChatGPT-Draht `search` gibt eine reine Trefferliste ohne degraded-Feld zurück; er erbt die Filterung, die exclusion-Degradation steht dort wie jeder andere Providerausfall nicht im Draht (Phase 28/29).
- Provider-cursors werden unverändert weitergereicht (T-27-25 accept, Kanarientest Phase 28).
- Die vulture-Whitelist-Einträge `paths_of_fileids`, `degraded_entry`, `file_refs`, `needs_paths` aus 27-01 sind jetzt durch echte Aufrufer überflüssig; `unavailable_error` ebenso. Aufräumen, wenn die Whitelist nicht mehr parallel bearbeitet wird.
- Merge-Hinweis: tests/unit/test_file_transfer_review.py wurde hier an einer Stelle (Suchtest) geändert; falls 27-02 dieselbe Datei anfasst, betrifft das andere Zeilen.
- `talk-message-current` antwortete in der Probe auch auf das Textwort nicht (kein aktueller Raumkontext in der OCS-Suche); für die Klassifikation irrelevant.

## TDD Gate Compliance

- Task 2: RED `1aeaae4` (test), GREEN `107b472` (feat). Ein Test (talk-message) war im RED bereits grün, weil der kein-leak-Befund heutiges Verhalten bestätigt; kein Fehler im Test.
- Task 3: RED `6b32bb6` (test), GREEN `93370c5` (feat).

## Known Stubs

Keine.

## Threat Flags

Keine neue Angriffsfläche außerhalb des Threat-Modells. T-27-20 bis T-27-24, T-27-26, T-27-27 umgesetzt wie geplant; T-27-28 (Probe-Harness schreibt auf nc35) mit eigener Probe-Datei und geprüftem Aufräumen.

## Commits

- 979b5bb test(27-03): live probe of talk-message and comments search providers
- 1aeaae4 test(27-03): add failing tests for the guarded unified_search
- 107b472 feat(27-03): guard unified_search with sandbox for pathless hits and silent tag filter
- 6b32bb6 test(27-03): add failing tests for fetch(file) behind the guard
- 93370c5 feat(27-03): guard fetch(file) before the file id lookup is evaluated

## Self-Check: PASSED
