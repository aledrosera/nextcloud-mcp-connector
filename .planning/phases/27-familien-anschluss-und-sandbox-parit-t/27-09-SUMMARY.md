---
phase: 27-familien-anschluss-und-sandbox-parit-t
plan: 09
subsystem: prepare_context / fetch / files
tags: [wanduhr, prepare_context, fileid, batch, exclusion, kein-ki, nc35, gap-closure]
requires:
  - "27-08: Wanduhr-Messung, Owner-Entscheid 'Lückenplan'"
provides:
  - "dav.entries_of_fileids: eine SEARCH je Block, volle Einträge, erster Eintrag gewinnt"
  - "chatgpt.file_entries + fetch(resolved=...): Python-only, keine Wire-Änderung"
  - "files.read(known=...): SEARCH-Eintrag ersetzt stat-PROPFIND, Guard unverändert"
  - "context._excerpts: eine geteilte Lookup-Task je Bündel, Einzelweg bei Fehler"
  - "raw/27-09-prepare-context.txt, raw/27-09-exclusion-live.txt, 27-LIVE-BEWEIS.md fortgeschrieben"
affects:
  - "Owner-Checkpoint 27-09 (Wiedervorlage 27-08)"
  - "Phase 29: Notiz-Ausschnitt als verbleibende serielle Kette in Szenario B"
tech-stack:
  added: []
  patterns:
    - "Paritätsbeweis alter gegen neuer Weg über zwei Nähte (Batch abschalten, known verwerfen) statt Codekopie"
    - "Kontrollmessung des Codes vor dem Plan in derselben Sitzung, vor und nach dem Messlauf (git archive, nicht committet)"
key-files:
  created:
    - tests/unit/test_excerpt_batch.py
    - .planning/phases/27-familien-anschluss-und-sandbox-parit-t/raw/27-09-prepare-context.txt
    - .planning/phases/27-familien-anschluss-und-sandbox-parit-t/raw/27-09-exclusion-live.txt
  modified:
    - src/mcp_connector/nextcloud/clients/dav.py
    - src/mcp_connector/tools/files.py
    - src/mcp_connector/tools/chatgpt.py
    - src/mcp_connector/tools/context.py
    - tests/unit/test_tools_context.py
    - tests/unit/test_chatgpt_fetch.py
    - tests/unit/test_files_exclusion.py
    - tests/integration/test_ctx_bundle.py
    - .planning/phases/27-familien-anschluss-und-sandbox-parit-t/27-LIVE-BEWEIS.md
decisions:
  - "entries_of_fileids kennt drei Zustände je Id (Eintrag, None, fehlt): eine Id, die ein voller Block (nresults erreicht) verdrängt haben kann, geht den Einzelweg statt als 'unbekannt' zu antworten"
  - "Fehlerklassen des Sammel-Lookups liegen als chatgpt.LOOKUP_FAILURES in chatgpt.py, damit context.py httpx weiter nur zum Klassifizieren kennt (Bestandstest)"
  - "Die Integrations-Assertion für B full zählt die Pfadprüfung des Notiz-Ausschnitts mit (Plan-Annahme 'files-search <= 2' ging von drei Datei-Ausschnitten aus)"
  - "Überschreitung B full (0,992 s gegen 0,97 s) nicht getunt, sondern mit Wiederholung und drei Kontrollen dem Owner vorgelegt"
metrics:
  duration: "ca. 45 min"
  completed: 2026-09-27
  tasks: "2 von 3 (Task 3 = Owner-Checkpoint offen)"
  files: 12
---

# Phase 27 Plan 09: Eine fileid-Auflösung je Bündel Summary

Die Datei-Ausschnitte eines `prepare_context`-Bündels lösen ihre fileids jetzt mit einer gemeinsamen SEARCH auf und lesen ohne zweiten stat-PROPFIND; die Antworten sind byte-gleich zum Weg vor 27-09 (Paarvergleich), der Guard wird in keinem Zweig übersprungen. Gegen nc35: A full 0,919 s und A short, B short innerhalb, **B full 0,992 s weiterhin über 0,97 s (um 0,022 s, vorher 0,077 s)**.

**Status: CHECKPOINT OFFEN.** Task 3 (Owner-Abnahme) ist nicht erledigt; unter "## Abnahme" in 27-LIVE-BEWEIS.md steht "Owner-Entscheid zu 27-09: Ausstehend".

## Was gebaut wurde

**Task 1 (RED f13f9fc, GREEN 4c7d85f):**
- `dav.entries_of_fileids` + `_search_fileid_entries`: Ziffernprüfung vor jedem Request, Deduplizierung, Blöcke zu 50, Scope wie `find_by_fileid`, erster Eintrag je fileid gewinnt, Sandbox-Prüfung je Eintrag. `paths_of_fileids` unverändert (Diff gegen ac479c6 zeigt keine Zeile in seinem Rumpf).
- `files.read(..., known=...)`: nur bei `known.path == safe_path(path)` und nicht leerer fileid; dann nur `clients.exclusion.scope(clients)`, Reihenfolge unverifiable, excludes(path, fileid) wie beim stat-Weg. Sonst stat wie bisher.
- `chatgpt.file_entries(clients, identifiers)` und `fetch(..., resolved=...)`: `_fetch_file` überspringt `find_by_fileid` nur für Ids in `resolved`, Entscheidungsreihenfolge Zeile für Zeile gleich; `read(..., known=entry)` in beiden Zweigen, also spart auch das eigenständige `fetch(file)` den PROPFIND.
- `context._excerpts`: eine `asyncio.Task` über `file_entries` vor dem gather, Datei-Ausschnitte warten per `asyncio.shield` innerhalb ihres unveränderten Budgets; bei `LOOKUP_FAILURES` Einzelweg mit den bisherigen Sätzen; Notizen und Karten warten nie; nach dem gather wird die Task abgebrochen und abgeholt (`_settle`).
- `reg_chatgpt.py`, `reg_files.py` unangetastet (grep known/resolved = 0), check_tool_budget Exit 0.

**Task 2 (4fddaed, 2e73af7):** `test_ctx_bundle.py` schreibt nach `raw/27-09-prepare-context.txt`, LAUF-Zeilen tragen `propfind=` und `ausschnitte=`, full-Läufe asserten die SEARCH-Zahl und höchstens einen REPORT. Messlauf gegen nc35 (ganze Datei, 10 passed), Wiederholung, drei Kontrollen mit dem Code vor 27-09, Live-Beweis fortgeschrieben.

## Messwerte (raw/27-09-prepare-context.txt)

| Szenario | detail | Median nach 27-09 | Schwelle | Urteil |
|---|---|---|---|---|
| A | short | 0,776 s | 0,88 s | innerhalb |
| A | full | 0,919 s | 0,97 s | innerhalb |
| B | short | 0,827 s | 0,88 s | innerhalb |
| B | full | 0,992 s | 0,97 s | **überschritten** (0,022 s) |

- Wiederholung nach 27-09: 0,795 / 0,919 / 0,811 / 1,028 s (B full überschritten).
- Kontrollen vor 27-09, gleiche Sitzung: B full 1,059 / 1,020 / 1,035 s, A full 0,991 / 0,994 / 1,095 s.
- Einsparung: A full etwa 0,07 s (drei Datei-Ausschnitte); B full 0,043 s (Messlauf) bzw. 0,007 s (Wiederholung) gegen den Kontroll-Median 1,035 s; gegen 27-08 (1,047 s) 0,055 s.
- Requests: A full 28 auf 23 (files-search 3 auf 1), B full 28-29 auf 25-26 (files-search 4 auf 3), `propfind=0` in allen full-Läufen, `exclusion-report=1` in jeder LAUF-Zeile B.
- Grund für die kleinere Einsparung in B: die Ausschnitte sind dort `file,file,note`; der Notiz-Ausschnitt prüft seinen Pfad mit eigener fileid-SEARCH (27-04) und bleibt eine serielle Kette. Vermutung aus der Request-Zählung, nicht je Bein gemessen.

## Verifikation

- `pytest tests/unit tests/contract`: 4853 passed, 33 skipped (4814 aus 27-06 plus 39 neue).
- ruff check, ruff format --check (300 Dateien), pyright latest 0 Fehler, vulture grün, check_tool_budget Exit 0.
- `test_ctx_bundle.py -m integration` gegen nc35: 10 passed.
- `test_exclusion_live.py` gegen nc35 nach Task 1: 10 passed, 57 Zeilen `: ja`, 0 `: nein` (raw/27-09-exclusion-live.txt).
- Acceptance-Greps: entries_of_fileids 1, def file_entries 1, known=entry 1, file_entries( in context.py 1, asyncio.shield 2, exclusion.scope(clients) in files.py 5 (vorher 4).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Parität] Verdrängte Ids gehen den Einzelweg**
- **Found during:** Task 1
- **Issue:** Die Sammel-SEARCH hat `nresults` gleich der Id-Zahl; ein doppelter Eintrag einer Id könnte eine andere verdrängen, die der Einzelweg (nresults 1) gefunden hätte. Als `None` hätte sie fälschlich "keine Datei" geantwortet.
- **Fix:** `entries_of_fileids` liest die Antwort Response für Response (eigener Helfer `_search_fileid_entries` statt `_search_fileids`); None nur, wenn der Block weniger Antworten als `nresults` hatte oder der erste Eintrag außerhalb der Sandbox liegt; sonst fehlt die Id und `fetch` löst sie einzeln auf. Test `test_entries_of_fileids_leaves_out_ids_a_full_answer_may_have_crowded_out`.
- **Commit:** 4c7d85f

**2. [Rule 3] httpx-Bestandstest in context.py**
- **Issue:** `test_this_module_reads_no_content_of_its_own` erlaubt httpx in context.py nur zum Klassifizieren; `except (ToolError, httpx.HTTPError, ValueError)` brach ihn.
- **Fix:** `chatgpt.LOOKUP_FAILURES`, context.py fängt `chatgpt_tools.LOOKUP_FAILURES`.
- **Commit:** 4c7d85f

**3. [Rule 3] pyright-Typ in test_files_exclusion.py**
- `kwargs: dict[str, int]` passte nach dem neuen Parameter `known` nicht mehr zu `**kwargs`; auf `dict[str, Any]` gesetzt.
- **Commit:** 4c7d85f

**4. [Rule 1 - Plan-Annahme] Assertion B full `files-search <= 2`**
- **Found during:** Task 2, erster Messlauf rot mit `files-search=3`
- **Issue:** Die Plan-Grenze ging von drei Datei-Ausschnitten aus; auf nc35 liest B `file,file,note`, und `notes.read` prüft den Pfad der Notiz mit eigener SEARCH (27-04). Das war auch in 27-08 schon so (4 = 1 Guard + 2 Datei + 1 Notiz, im Live-Beweis jetzt korrigiert gedeutet).
- **Fix:** Grenze aus den tatsächlich gelesenen Arten: 1 Sammel-SEARCH (falls Datei-Ausschnitt) plus in B 1 Guard plus 1 je Notiz-Ausschnitt; `ausschnitte=` in der LAUF-Zeile macht das prüfbar.
- **Commit:** 4fddaed

**5. [Test] test_chatgpt_fetch.py: stat-Routen durch Größe im SEARCH-Eintrag ersetzt**
- Sechs Stellen routeten einen stat-PROPFIND mit der Dateigröße, `search_body` hatte eine feste Länge 27. Jetzt `search_body(length=...)`, keine PROPFIND-Route, Kommentar "27-09: the entry of the file id SEARCH replaces the stat"; `stat_body` war danach unbenutzt und ist entfernt. Keine Assertion geändert.

### Zusätzlich, nicht im Plan

- **Wiederholung und zwei zusätzliche Kontrollen:** Wegen der Streuung (Kontrolle 1 hatte selbst A short überschritten) lief der Code nach 27-09 ein zweites Mal und der Code vor 27-09 insgesamt dreimal, abwechselnd; alle Zahlen stehen in der Rohdatei, keine wurde weggelassen.
- **raw/27-09-exclusion-live.txt:** Der Live-Test hängt an raw/27-07-live.txt an; der neue Lauf wurde in eine eigene Datei gezogen und 27-07-live.txt wiederhergestellt, damit der dort maßgebliche Lauf unverändert bleibt.

### Ausführungsumgebung und Herstellung der Kontrolle

- Worktree-Base war 7a93585 und wurde laut Auftrag per `git reset --hard fc57ae2` korrigiert.
- `.env.nc35` und die nc35-Topologienamen per temporärem Python-Lader (nicht committet, gelöscht), `PYTHONIOENCODING=utf-8`, `PYTHONPATH=src` auf den Worktree; pytest und pyright über die Hauptrepo-venv.
- Kontrolle 1: im Worktree auf dem unveränderten Stand fc57ae2 (Code gleich ac479c6) vor dem ersten 27-09-Commit; die dabei überschriebene raw/27-08-prepare-context.txt per `git checkout -- <datei>` wiederhergestellt.
- Kontrollen 2 und 3: `git archive -o <tar> ac479c6`, in ein Verzeichnis im Worktree entpackt, dort nur der Wanduhr-Test per `-k` mit `PYTHONPATH` auf dessen `src` (Lauf zeigte files-search 3/4, also wirklich der alte Code), Verzeichnis danach gelöscht. Der Worktree-Branch wurde nie bewegt.

## Offener Checkpoint (Task 3)

Der Owner entscheidet über die Messung nach 27-09: B full 0,992 s gegen 0,97 s (Wiederholung 1,028 s; Kontrollen vor 27-09 1,020 bis 1,059 s). Optionen laut Plan: abnehmen, Schwelle mit Begründung akzeptieren, oder weiterer Lückenplan (Ansatz wäre die Pfadprüfung des Notiz-Ausschnitts in dieselbe Sammel-SEARCH zu holen, die Notiz-Id ist die fileid; das hat dieser Plan ausdrücklich ausgeschlossen). Die Antwort wird wörtlich mit Datum unter "## Abnahme" eingetragen.

## Known Stubs

Keine. "Owner-Entscheid zu 27-09: Ausstehend" steht bewusst bis zur Antwort des Owners.

## Threat Flags

Keine neue Angriffsfläche. T-27-90 (Paritätstests, Einzelweg bei Fehler, gleicher Timeout-Satz), T-27-91 (keine Modul-Variable, Task abgebrochen, `test_two_bundles_resolve_twice`), T-27-92 (`test_a_known_entry_never_skips_the_guard`), T-27-93 (`test_a_file_outside_the_files_root_answers_like_before`), T-27-96 (reg-Dateien unverändert, Budget grün), T-27-97 (Rohzeilen, Wiederholung, Kontrollen, Schwellen unverändert) umgesetzt.

## Commits

- f13f9fc test(27-09): add failing tests for one file id lookup per bundle
- 4c7d85f feat(27-09): resolve the file excerpts of one bundle with one SEARCH
- 4fddaed test(27-09): measure the wall clock after the batched file id lookup
- 2e73af7 docs(27-09): wall clock after the gap plan in the live proof

## TDD Gate Compliance

RED f13f9fc (36 von 39 Tests rot) vor GREEN 4c7d85f; kein REFACTOR-Commit nötig.

## Self-Check: PASSED

- FOUND: tests/unit/test_excerpt_batch.py, raw/27-09-prepare-context.txt, raw/27-09-exclusion-live.txt, 27-LIVE-BEWEIS.md
- FOUND: f13f9fc, 4c7d85f, 4fddaed, 2e73af7
