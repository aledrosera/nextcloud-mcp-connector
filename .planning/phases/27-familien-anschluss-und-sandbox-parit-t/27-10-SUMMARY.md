---
phase: 27-familien-anschluss-und-sandbox-parit-t
plan: 10
subsystem: prepare_context / fetch / notes
tags: [wanduhr, prepare_context, notes, fileid, batch, exclusion, kein-ki, nc35, gap-closure]
requires:
  - "27-09: entries_of_fileids, file_entries, eine Lookup-Task je Bündel"
  - "Owner-Entscheid 27.09. 'Zweiter Lückenplan'"
provides:
  - "chatgpt.file_entries(kinds=...): Notiz-Ids in derselben SEARCH"
  - "chatgpt.fetch(note_batch=...) und notes.read(batch=...): Python-only, keine Wire-Änderung"
  - "notes._check_note_path mit Sammel-Eintrag, Einzelweg bei fehlender Id oder Fehlschlag"
  - "context._excerpts: Notiz-Ausschnitte warten nur bei Pfadbedarf auf die geteilte Task"
  - "raw/27-10-prepare-context.txt, raw/27-10-exclusion-live.txt, 27-LIVE-BEWEIS.md fortgeschrieben"
affects:
  - "Owner-Checkpoint 27-10 (Wiedervorlage 27-09)"
tech-stack:
  added: []
  patterns:
    - "Paritätsbeweis über eine Naht (note_batch verwerfen, kinds verwerfen) statt Codekopie"
    - "Kontrollmessung des Codes vor dem Plan abwechselnd mit den Läufen danach (git archive, nicht committet)"
key-files:
  created:
    - .planning/phases/27-familien-anschluss-und-sandbox-parit-t/raw/27-10-prepare-context.txt
    - .planning/phases/27-familien-anschluss-und-sandbox-parit-t/raw/27-10-exclusion-live.txt
  modified:
    - src/mcp_connector/tools/notes.py
    - src/mcp_connector/tools/chatgpt.py
    - src/mcp_connector/tools/context.py
    - tests/unit/test_excerpt_batch.py
    - tests/unit/test_tools_context.py
    - tests/integration/test_ctx_bundle.py
    - .planning/phases/27-familien-anschluss-und-sandbox-parit-t/27-LIVE-BEWEIS.md
decisions:
  - "Notiz-Ausschnitte bekommen ein Aufrufbares über asyncio.shield(lookup), kein Ergebnis: notes.read wartet nur hinter needs_paths(scope), nach unverifiable und excludes(fileid)"
  - "Die Sammel-SEARCH startet nur mit mindestens einem Datei-Ausschnitt; ein reines Notiz-Bündel geht den Einzelweg"
  - "notes.py hält die Fehlerklassen als eigenes Tupel _LOOKUP_FAILURES (kein Import von chatgpt.py, Zyklus)"
  - "Messung unter starker Host-Drift nicht getunt und nicht weggelassen, sondern mit fünf Kontrollen und einer Diagnose dem Owner vorgelegt"
metrics:
  duration: "ca. 60 min"
  completed: 2026-09-27
  tasks: "2 von 3 (Task 3 = Owner-Checkpoint offen)"
  files: 9
---

# Phase 27 Plan 10: Notiz-Pfadprüfung in der Sammel-SEARCH Summary

Die Notiz-Ausschnitte eines `prepare_context`-Bündels mit Datei-Ausschnitt prüfen ihren Pfad jetzt in derselben einen SEARCH, die die Datei-fileids auflöst; die Antworten sind byte-gleich zum Weg vor 27-10 (Paarvergleich), `_note_not_found` ist unverändert, kein Notizpfad erreicht das Bündel. Request-Seite gegen nc35 belegt: B full `files-search` 3 auf 2. **Die Wanduhr ist in dieser Sitzung nicht entscheidungsfähig:** der Host war stark gedriftet, der maßgebliche Messlauf liegt in allen vier Zeilen über der Schwelle (B full 2,163 s), die Kontrollen mit dem Code vor 27-10 genauso.

**Status: CHECKPOINT OFFEN.** Task 3 (Owner-Abnahme) ist nicht erledigt; unter "## Abnahme" in 27-LIVE-BEWEIS.md steht "Owner-Entscheid zu 27-10: Ausstehend".

**Nachtrag 28.09.2026:** Checkpoint erledigt. Owner-Entscheid 27.09. "Neumessung ruhiges Fenster", Neumessung 28.09. gelaufen, Owner-Abnahme 28.09. "ok weiter" (Empfehlung a, Abnahme mit Begründung), wörtlich in 27-LIVE-BEWEIS.md, "## Abnahme".

## Was gebaut wurde

**Task 1 (RED 0d204ab, GREEN e9e022f):**
- `chatgpt.file_entries(clients, ids, *, kinds=("file",))`: nimmt Ids, deren Art in `kinds` liegt und deren Teil Ziffern sind; Deduplizierung wie bisher, also eine Ziffern-Id als Datei und Notiz nur einmal. Ohne `kinds` unverändert.
- `chatgpt.fetch(..., note_batch=...)` keyword-only, nur an `_fetch_note`, das `notes_tools.read(clients, note_id, batch=note_batch)` ruft.
- `notes.read(..., *, batch=None)`: Reihenfolge Zeile für Zeile gleich, `batch` geht nur an `_check_note_path` hinter `needs_paths(scope)`. Dort: Sammel-Eintrag vorhanden, dann derselbe Entscheid `path is None or scope.excludes(path=..., fileid=...)`; Eintrag `None` ergibt `_note_not_found`; Id fehlt oder die Sammel-SEARCH scheitert (`ToolError`, `httpx.HTTPError`, `ValueError`), dann der bisherige Einzelweg `paths_of_fileids` mit den bisherigen Sätzen.
- `context._excerpts`: `batch_ids` aus Datei- und Notiz-Treffern, die Task startet nur mit Datei-Ausschnitt (`kinds=("file", "note")`); `_excerpt(..., kind)` gibt Notizen ein `note_batch`, das `asyncio.shield(lookup)` erwartet; das Budget `EXCERPT_TIMEOUT` umschließt das Warten.
- `server/`, `dav.py`, `test_notes_exclusion.py`, `test_notes_tools.py` ohne Diff gegen 43c5a9d; check_tool_budget Exit 0.

**Task 2 (0b4de31, f842143):** `test_ctx_bundle.py` schreibt nach `raw/27-10-prepare-context.txt`; Schranke: mit Datei-Ausschnitt 1 Sammel-SEARCH (Notizen kosten keine eigene), ohne Datei-Ausschnitt 1 je Notiz in B, plus 1 Guard-SEARCH in B. Messlauf (ganze Datei, 10 passed), vier Wiederholungen, Messlauf 2 (ganze Datei, 10 passed), fünf Kontrollen mit dem Code vor 27-10, Live-Beweise 27-07 erneut, Live-Beweis fortgeschrieben.

## Messwerte (raw/27-10-prepare-context.txt)

Maßgeblicher Messlauf 15:44:28 +0200:

| Szenario | detail | Median nach 27-10 | Schwelle | Urteil |
|---|---|---|---|---|
| A | short | 1,620 s | 0,88 s | überschritten |
| A | full | 1,772 s | 0,97 s | überschritten |
| B | short | 2,471 s | 0,88 s | überschritten |
| B | full | 2,163 s | 0,97 s | **überschritten** |

Alle Läufe dieser Sitzung (Mediane in s, A short / A full / B short / B full):

| Lauf | Zeit | Werte |
|---|---|---|
| Kontrolle 1 (vor) | 15:42 | 1,288 / 2,185 / 2,140 / 2,151 |
| Messlauf (nach) | 15:44 | 1,620 / 1,772 / 2,471 / 2,163 |
| Wiederholung 1 | 15:46 | 1,311 / 1,568 / 1,201 / 2,917 |
| Kontrolle 2 | 15:47 | 1,767 / 1,926 / 1,746 / 1,971 |
| Wiederholung 2 | 15:48 | 1,527 / 1,600 / 1,629 / 1,759 |
| Kontrolle 3 | 15:51 | 0,929 / 1,039 / 0,911 / 1,769 |
| Wiederholung 3 | 15:52 | 0,863 / 0,967 / 0,799 / **0,963** (alle vier innerhalb) |
| Kontrolle 4 | 15:52 | 0,887 / 0,894 / 0,849 / 0,981 |
| Messlauf 2 (ganze Datei) | 15:53 | 0,928 / 1,125 / 1,008 / 1,039 |
| Kontrolle 5 | 15:54 | 1,442 / 1,749 / 1,310 / 1,130 |
| Wiederholung 4 | 15:55 | 1,159 / 1,082 / 1,198 / 1,383 |

- B full: Median der sechs Mediane nach 27-10 1,571 s, der fünf Kontrollen 1,769 s; Streuung benachbarter Läufe bis 1,2 s, die erwartete Einsparung 0,03 bis 0,06 s. Nicht entscheidungsfähig.
- Drift-Diagnose (Anhang 3): Notes-Provider der Suche einzeln per curl 0,64 bis 1,06 s (25 Proben), status.php 0,03 s, Datei-Provider 0,07 bis 0,14 s, PHP-Schleife im Container unauffällig; Windows-Defender mit 4:11 h CPU-Zeit. 27-09 am selben Tag um 15:04 lag bei A short 0,776 s.
- Requests: B full 24 bis 25 (vorher 25 bis 26), `files-search=2` in allen 36 LAUF-Zeilen B full nach 27-10, `files-search=3` in allen 30 Kontrollzeilen; `propfind=0`, `exclusion-report=1` in jeder LAUF-Zeile B. A full unverändert 23, `files-search=1`.

## Verifikation

- `pytest tests/unit tests/contract`: 4888 passed, 33 skipped (4853 aus 27-09 plus 35 neue).
- ruff check, ruff format --check, pyright latest 0 Fehler, vulture grün, check_tool_budget Exit 0.
- `test_ctx_bundle.py -m integration` gegen nc35: zweimal 10 passed.
- `test_exclusion_live.py` gegen nc35 nach Task 1: 10 passed, 57 Zeilen `: ja`, 0 `: nein` (raw/27-10-exclusion-live.txt); raw/27-07-live.txt und raw/27-09-prepare-context.txt ohne Diff.
- Acceptance-Greps: `kinds=("file", "note")` 1, `note_batch=` 1, `file_entries(` 1 in context.py; `batch=note_batch` 1 in chatgpt.py; `paths_of_fileids(` in notes.py 2 wie vorher; Rumpf von `_note_not_found` ohne Diff.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Test] Zwei RED-Erwartungen an die Bündelform korrigiert**
- **Found during:** Task 1 GREEN
- **Issue:** `test_a_failed_batch_leaves_the_note_its_own_sentences[fail_all]` und `test_a_note_without_path_check_never_waits_for_the_batch[unverifiable]` erwarteten `withhold.unavailable_error()` als Eintrag je Ausschnitt; das Bündel fasst diesen Satz aber einmal als `{"source": "exclusion", ...}` zusammen (Bestand vor 27-10, die Paarvergleiche waren in beiden Fällen gleich).
- **Fix:** Erwartung auf den einen `exclusion`-Eintrag gesetzt, keine Codeänderung.
- **Commit:** e9e022f

**2. [Rule 3] Naht des 27-09-Referenzwegs nimmt `kinds` an**
- `force_old_route.no_batch` und der Fake in `test_notes_and_cards_never_wait_for_the_batch` nehmen `**kwargs`; die Aussage "only file ids go into the batch" auf "file and note ids" präzisiert, mit Kommentar "27-10: a note that checks its path joins the batch". Karten bleiben draußen, der Test ist sonst unverändert grün.

**3. [Rule 1 - Rohdatei] Kopfzeile von raw/27-10-exclusion-live.txt**
- Die nach 27-09-Muster geschriebene Kopfzeile `0 Zeilen ": nein"` traf selbst das Prüfmuster `: nein` der Plan-Verifikation; umformuliert ("keine Zeile mit dem Urteil nein").

### Zusätzlich, nicht im Plan

- **Mehr Läufe als geplant:** Wegen der Host-Drift lief der Code nach 27-10 sechsmal (zwei ganze Dateien, vier Wiederholungen) und der Code vor 27-10 fünfmal, streng abwechselnd; alle Zahlen stehen in der Rohdatei, keine weggelassen. Maßgeblich bleibt nach Plan der erste Messlauf.
- **Drift-Diagnose** als Anhang 3 der Rohdatei (Einzelaufrufe per curl, CPU-Probe im Container).

### Ausführungsumgebung und Herstellung der Kontrolle

- Worktree-Base war 7a93585 und wurde laut Auftrag per `git reset --hard 17cbd96` korrigiert.
- `.env.nc35` und die nc35-Topologienamen per temporärem Python-Lader im Verzeichnis `.tmp-27-10` des Worktrees (nicht committet, gelöscht), `PYTHONIOENCODING=utf-8`, `PYTHONPATH` auf das jeweilige `src`; pytest, ruff, pyright und vulture über die Hauptrepo-venv.
- Kontrollen 1 bis 5: `git archive -o .tmp-27-10/control.tar 43c5a9d`, nach `.tmp-27-10/control` entpackt, dort nur der Wanduhr-Test per `-k test_the_wall_clock_against_the_phase_25_reference`; der Lauf schrieb seine Rohdatei ins entpackte Verzeichnis, die Zeilen wurden in Anhang 2 übernommen. `files-search=3` in jeder Kontroll-LAUF-Zeile B full zeigt, dass es der alte Code war. Verzeichnis danach gelöscht; die Worktree-Rohdateien früherer Pläne wurden dabei nie überschrieben. Der Live-Test hängte an raw/27-07-live.txt an; der Lauf steht in raw/27-10-exclusion-live.txt, 27-07-live.txt wurde per `git checkout --` wiederhergestellt. Der Worktree-Branch wurde nie bewegt.

## Offener Checkpoint (Task 3)

Der Owner entscheidet über die Messung nach 27-10. Stand: Request-Seite belegt (B full files-search 2 statt 3, ein REPORT je Antwort, propfind 0), Antworten byte-gleich laut Paartests; Wanduhr unter Host-Drift, maßgeblicher Messlauf B full 2,163 s gegen 0,97 s, Kontrollen gleich langsam, einziger ruhiger Lauf (Wiederholung 3) mit allen vier Zeilen innerhalb (B full 0,963 s) neben Kontrolle 4 mit B full 0,981 s. Optionen laut Plan: abnehmen, Schwelle mit Begründung akzeptieren, weiterer Lückenplan; naheliegend zusätzlich eine Neumessung in einem ruhigen Fenster. Die Antwort wird wörtlich mit Datum unter "## Abnahme" eingetragen.

## Known Stubs

Keine. "Owner-Entscheid zu 27-10: Ausstehend" steht bewusst bis zur Antwort des Owners.

## Threat Flags

Keine neue Angriffsfläche. T-27-100 (Paartests für lesbare Notiz, Notiz unter getaggter Kategorie, außerhalb der Root, direkt getaggte Notiz, unbekannte Id, verdrängte Id, 500, Zeitüberschreitung, nicht prüfbarer Guard; `_note_not_found` ohne Diff), T-27-101 (`test_no_note_path_reaches_the_bundle`), T-27-102 (`test_two_bundles_with_a_note_resolve_twice`, keine Modul-Variable, `_settle` unverändert), T-27-103 (`test_read_never_asks_the_batch_without_a_path_check`, `test_a_note_without_path_check_never_waits_for_the_batch`), T-27-105 (server/ ohne Diff, Budget grün), T-27-106 (Rohzeilen aller Läufe, Kontrollen, Schwellen unverändert) umgesetzt.

## Commits

- 0d204ab test(27-10): add failing tests for the note path check in the bundle batch
- e9e022f feat(27-10): check the path of note excerpts in the bundle batch SEARCH
- 0b4de31 test(27-10): measure the wall clock after the note path joined the batch
- f842143 docs(27-10): wall clock after the second gap plan in the live proof

## TDD Gate Compliance

RED 0d204ab (35 Tests rot: 34 der 35 neuen plus der angepasste 27-09-Test `test_notes_and_cards_never_wait_for_the_batch`; die zehn Fälle des Paarvergleichs prüfen zusätzlich, dass die Notiz-Id in der Sammel-SEARCH steht, und waren damit rot). Schon im RED grün war erwartungsgemäß `test_a_notes_only_bundle_sends_no_batch`, weil er gerade das unveränderte Verhalten eines reinen Notiz-Bündels festhält. GREEN e9e022f danach; kein REFACTOR-Commit nötig.

## Self-Check: PASSED

- FOUND: raw/27-10-prepare-context.txt (44 WANDUHR-Zeilen), raw/27-10-exclusion-live.txt, 27-LIVE-BEWEIS.md ("Nach dem Lückenplan 27-10", "Owner-Entscheid zu 27-10: Ausstehend")
- FOUND: 0d204ab, e9e022f, 0b4de31, f842143
