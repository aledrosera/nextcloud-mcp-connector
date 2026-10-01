---
phase: 27-familien-anschluss-und-sandbox-parit-t
verified: 2026-09-28T12:00:00Z
status: passed
score: 12/12 must-haves verified (1 davon PASSED per Owner-Abnahme, SBX-01 per CI-Lauf 36861555478)
overrides_applied: 1
overrides:
  - must_have: "Die Wanduhr von prepare_context liegt gemessen im Rahmen der Phase-25-Referenz (Roadmap-Erfolgskriterium 2; Median ≤ 0,88 s short / ≤ 0,97 s full, je 5 Läufe, frisches NcClients je Aufruf)"
    reason: "Owner-Entscheid 28.09.2026 wörtlich 'ok weiter' auf die Vorlage (a) 'Abnahme mit Begründung': der Code nach 27-10 ist gegen die abwechselnd gefahrene Kontrolle mit dem Code vor 27-10 nicht messbar langsamer, die Kontrolle lag selbst in allen fünf Läufen über 0,97 s, Messung 1 im ruhigsten Fenster liegt in allen vier Zeilen innerhalb (B full 0,937 s), die Streuung zwischen Nachbarläufen (bis 0,4 s) übersteigt die Auflösung der 0,05-s-Rauschreserve. Schwellen unverändert dokumentiert, Request-Seite (files-search 3 auf 2) belegt."
    accepted_by: "Owner (street1983nk)"
    accepted_at: "2026-09-28T11:05:05+02:00"
re_verification:
  previous_status: gaps_found
  previous_score: "5/6 Muss-Kriterien (1 Blocker-Gap Wanduhr plus fehlende Owner-Abnahme, 1 Human-Verification SBX-01)"
  gaps_closed:
    - "Wanduhr prepare_context (Roadmap-SC2, Plan 27-08 must_have): nach 27-09 und 27-10 im ruhigen Fenster neu gemessen, abwechselnd mit Kontrolle, vom Owner am 28.09.2026 mit Begründung abgenommen"
    - "Owner-Abnahme des Live-Beweises (Checkpoint 27-08, Wiedervorlage 27-09 und 27-10): unter '## Abnahme' mit Datum und Wortlaut eingetragen (Commit e15af1b)"
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "Beim nächsten Push den CI-Job 'exapp' beobachten und bestätigen, dass der Schritt 'Findling hits run through sandbox and exclusion (SBX-01)' (tests/integration/test_findling_sandbox.py) tatsächlich grün durchläuft und nicht übersprungen wird"
    expected: "Der Schritt meldet PASSED für beide Teilfälle: Root-Sandbox-Fall mit skipped>=1 plus Gegenprobe, Tag-Fall mit unverändertem skipped gegenüber der Gegenprobe"
    why_human: "nc35 hat keinen Findling-Provider, lokal läuft der Test nur als SKIPPED mit benanntem Grund. main steht 171 Commits vor origin/main (letzter Push 26.09.), der CI-Schritt ist also seit der Erstverifikation nie gelaufen. Der Findling-Teil von Erfolgskriterium 3 ist bis dahin nur durch den strukturgleichen comments-Fall (pfadlos, nur fileid, live auf nc35) indirekt gedeckt."
---

# Phase 27: Familien-Anschluss und Sandbox-Parität Verification Report

**Phase Goal:** Was `kein-ki` trägt oder unter einem getaggten Ordner liegt, erscheint in keiner Antwort eines dateitragenden Werkzeugs mehr, weder als Treffer noch als Inhalt, Ausschnitt, Digest oder eingesetzter Dateiname; Findling-Treffer ohne Pfad und Notes laufen durch dieselbe Sandbox- und Ausschlussprüfung wie Pfad-Treffer.

**Verified:** 2026-09-28
**Status:** human_needed
**Re-verification:** Ja, nach den Lückenplänen 27-09 und 27-10, der Neumessung im ruhigen Fenster (28.09.) und der Owner-Abnahme (Commits 07c970f, e15af1b)
**Geprüfter Stand:** main e15af1b; seit dem gemessenen Code 656af9d nur Doku-Änderungen (`git diff 656af9d HEAD --stat`: 27-LIVE-BEWEIS.md und raw/27-10-prepare-context-2026-09-28.txt, kein Quellcode)

## Goal Achievement

### Observable Truths (Roadmap-Erfolgskriterien 1 bis 5 plus Plan-Must-Haves 27-01 bis 27-10)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | SC1: Getaggte Datei/Ordner fehlen in files_list/files_search/files_read/files_download; Upload verrät nichts | VERIFIED (Regression ok) | 27-LIVE-BEWEIS.md SC1, 24/24 "ja"; nach 27-09 und 27-10 je erneut gelaufen: raw/27-09-exclusion-live.txt und raw/27-10-exclusion-live.txt je 10 passed, 57 Zeilen ": ja", 0 ": nein" |
| 2a | SC2 ohne Wanduhr: unified_search, ChatGPT-search, fetch (auch vorher bekannte fileid), systemtags-Provider, prepare_context ohne getaggten Treffer/Ausschnitt/Digest | VERIFIED (Regression ok) | wie Erstverifikation, 10/10 "ja"; nach 27-10 erneut grün (raw/27-10-exclusion-live.txt) |
| 2b | SC2 Wanduhr: prepare_context im Rahmen der Phase-25-Referenz (Median short ≤ 0,88 s, full ≤ 0,97 s, 2 Szenarien) | PASSED (override, Owner-Abnahme) | Neumessung 28.09. (raw/27-10-prepare-context-2026-09-28.txt): Messung 1 alle vier Zeilen innerhalb (A short 0,768, A full 0,898, B short 0,813, B full 0,937 s); über 6 Messungen B full Median der Mediane 1,139 s gegen Kontrolle (Code 43c5a9d) 1,048 s, Kontrolle in 5/5 Läufen über 0,97 s. Schwelle damit nicht stabil gehalten, aber vom Owner am 28.09.2026 mit Begründung abgenommen ("ok weiter" auf Vorlage (a) "Abnahme mit Begründung"), Schwellen unverändert. Tabelle gegen Rohdatei geprüft, siehe unten |
| 3a | SC3: pfadlose Treffer (comments, nur fileid) außerhalb der Root/getaggt verschwinden; Notizen außerhalb der Root, getaggte Notizen/Kategorien verschwinden | VERIFIED (Regression ok) | 27-LIVE-BEWEIS.md SC3, 8/8 "ja"; nach 27-10 (Notizpfad in der Sammel-SEARCH) erneut grün |
| 3b | SC3 Findling-Teil: fileId-only-Treffer verschwindet wie Pfad-Treffer (SBX-01) | UNCERTAIN (Human) | Test und CI-Schritt unverändert vorhanden (`.github/workflows/ci.yml` Zeile 128 `uv run pytest tests/integration/test_findling_sandbox.py -m integration`); main 171 Commits vor origin/main, also nie in CI gelaufen |
| 4 | SC4: talk_browse setzt keinen Dateinamen einer getaggten Datei ein | VERIFIED (Regression ok) | SC4 6/6 "ja", in den Wiederholungsläufen 27-09/27-10 grün |
| 5 | SC5: nicht beantwortbare Prüfung hält zurück und benennt die Degradation einmalig; Schweigen im Erfolgsfall | VERIFIED (Regression ok) | SC5 9/9 "ja", in den Wiederholungsläufen grün |
| 6 | Request-Kosten des Guards gemessen und verankert (Pitfall 7) | VERIFIED | Neumessung 28.09.: `REQUESTS cold total=23`, `warm total=20` wie am 27.09.; jede B-Zeile `exclusion-report=1` |
| 7 | 27-09: eine Sammel-SEARCH für die Datei-Ausschnitte eines Bündels, kein stat-PROPFIND, Guard wird trotzdem gefragt | VERIFIED | `dav.entries_of_fileids` (dav.py:496), `files_tools.read(..., known=entry)` (chatgpt.py:345), `_visible_stat` fragt mit `known` weiter `clients.exclusion.scope` und `excludes(path, fileid)` (files.py:744 bis 750); Rohzeilen A full `files-search=1 propfind=0` |
| 8 | 27-10: Notiz-Ausschnitte prüfen ihren Pfad in derselben Sammel-SEARCH, nur mit Datei-Ausschnitt, byte-gleich zum Einzelweg; notes_read/fetch(note) eigenständig unverändert | VERIFIED | context.py:776 `file_entries(clients, batch_ids, kinds=("file", "note"))` (1 Treffer), context.py:829 bis 833 `note_batch` über `asyncio.shield(shared)`; notes.py:335 bis 368 `_check_note_path` mit identischem Entscheid, Einzelweg `paths_of_fileids` bleibt; `git diff 43c5a9d` leer für dav.py, server/, test_notes_exclusion.py, test_notes_tools.py; die sieben namentlich geforderten Tests in tests/unit/test_excerpt_batch.py (Zeilen 918 bis 1071) vorhanden und grün |
| 9 | 27-10 Request-Seite: B full `file,file,note` mit files-search ≤ 2 statt 3 | VERIFIED | Rohdatei 28.09.: alle sechs B-full-LAUF-Zeilen des Kopfs `files-search=2 propfind=0 exclusion-report=1 requests=25`; Anhang 1 vermerkt 6/6 `files-search=2` je Messung und 6/6 `files-search=3` je Kontrolle |
| 10 | Ein REPORT je Antwort, Sammelauflösung lebt nur im Aufruf (E3) | VERIFIED | `_settle(lookup)` im `finally` von `_excerpts` (context.py:790), keine Modul-Variable; test_two_bundles_resolve_twice (test_excerpt_batch.py:819) grün |
| 11 | Owner hat die Messung gesehen und unter '## Abnahme' mit Datum entschieden (Checkpoint 27-08, Wiedervorlagen 27-09 und 27-10) | VERIFIED | 27-LIVE-BEWEIS.md "## Abnahme": 27.09. "Lückenplan", 27.09. "Zweiter Lückenplan", 27.09. "Neumessung ruhiges Fenster", 28.09. "ok weiter" mit ausformulierter Begründung (Commit e15af1b, 28.09.2026 11:05 +0200) |

**Score:** 11/12 Truths erfüllt (10 VERIFIED, 1 PASSED per Owner-Override), 1 UNCERTAIN (SBX-01 CI-Lauf)

### Konsistenz Abnahme-Tabelle gegen Rohdatei (raw/27-10-prepare-context-2026-09-28.txt)

- Alle 44 Zellwerte der Tabelle "Neumessung im ruhigen Fenster (28.09.)" (11 Läufe mal 4 Zeilen) stimmen mit den WANDUHR-Zeilen der Rohdatei überein (Kopf = Messung 1, Anhang 1 = Kontrollen 1 bis 5 und Messungen 2 bis 6).
- Median der Mediane nachgerechnet: Messung A short 0,7985 (Bericht 0,798), A full 0,8975 (0,897), B short 0,9135 (0,913), B full 1,1395 (1,139); Kontrolle 0,860 / 0,934 / 0,870 / 1,048. Stimmt.
- Paarweise Differenzen der Abnahme-Begründung: 0,990 minus 0,937 = 0,053; 1,075 minus 0,980 = 0,095; 0,979 minus 1,060 = minus 0,081. Stimmt.
- "Kontrolle in allen fünf Läufen über 0,97 s (0,979 bis 1,215 s)": stimmt.
- Hostruhe (status.php 0,016 bis 0,059 s, Notes-Provider 0,56 bis 0,67 s, Last 12 bis 22 %): stimmt mit Anhang 2.
- Abweichung (ohne Entscheidungsrelevanz): Der Satz "A short, A full und B short liegen in 7 bis 9 von 11 Läufen innerhalb, bei beiden Codeständen gleich" trifft nicht genau. Nachgezählt: A short 10/11, A full 8/11, B short 6/11 innerhalb. Das betrifft nicht B full und nicht die Begründung der Abnahme.
- Einordnung der Begründung: Die drei paarweisen Vergleiche stammen aus den ruhigen Nachbarfenstern; über alle Läufe liegt die Messung im Median der Mediane 0,091 s über der Kontrolle (1,139 gegen 1,048 s). Diese Zahl steht offen in der Tabelle, die dem Owner vorlag. Die Abnahme ist damit auf die dokumentierten Rohdaten gestützt und nicht auf eine geschönte Auswahl.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/mcp_connector/tools/notes.py` | read(..., batch=...), _check_note_path mit Sammel-Eintrag, Einzelweg bei Fehlschlag | VERIFIED | Zeilen 335 bis 368; `_note_not_found` unverändert, kein Import von chatgpt.py |
| `src/mcp_connector/tools/chatgpt.py` | file_entries(kinds=...), fetch(note_batch=...), _fetch_file mit known | VERIFIED | `batch=note_batch` 1 Treffer, `known=entry` Zeile 345 |
| `src/mcp_connector/tools/context.py` | eine Sammel-SEARCH je Bündel für Datei- und Notiz-Ausschnitte, Guard erstes gather-Mitglied | VERIFIED | Zeile 254 Guard in gather, Zeile 776 Sammel-Task, Zeile 790 `_settle` |
| `src/mcp_connector/nextcloud/clients/dav.py` | entries_of_fileids (27-09), in 27-10 unverändert | VERIFIED | Zeile 496; Diff gegen 43c5a9d leer |
| `tests/unit/test_excerpt_batch.py` | Paritäts-, Request- und E3-Tests 27-09/27-10 | VERIFIED | sieben 27-10-Tests plus test_two_bundles_resolve_twice vorhanden, grün |
| `tests/integration/test_ctx_bundle.py` | Wanduhr-Szenarien, RUNS=5, frischer Guard, Schranke files-search | VERIFIED | Neumessung 28.09. mit 10 passed (ganze Datei) |
| `tests/integration/test_findling_sandbox.py` + CI-Schritt | SBX-01 gegen echten Findling | VERIFIED (Code) / UNCERTAIN (Lauf) | unverändert seit Erstverifikation, nie in CI gelaufen |
| `raw/27-10-prepare-context-2026-09-28.txt` | Neumessung mit Kontrollen, Hostruhe, Harness-Hinweis | VERIFIED | 126 Zeilen, 44 WANDUHR-Zeilen, Schwellen 0.88/0.97 unverändert |
| `27-LIVE-BEWEIS.md` | Neumessung, Abnahme mit Datum und Wortlaut | VERIFIED | Abschnitt "Neumessung im ruhigen Fenster (28.09.)" und "## Abnahme" vorhanden |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| context.py `_excerpts` | `chatgpt_tools.file_entries(..., kinds=("file", "note"))` | geteilte asyncio.Task, nur mit Datei-Ausschnitt | WIRED | Zeile 776 |
| context.py `_excerpt` (Notiz-Zweig) | `chatgpt_tools.fetch(..., note_batch=...)` | lokale async-Funktion über `asyncio.shield(shared)` | WIRED | Zeilen 829 bis 833 |
| chatgpt.py `_fetch_note` | `notes_tools.read(..., batch=note_batch)` | keyword-only Durchreichen | WIRED | 1 Treffer `batch=note_batch` |
| notes.py `_check_note_path` | `scope.excludes(path, fileid)` und `_note_not_found` | gleicher Entscheid, andere Pfadquelle | WIRED | Zeilen 359 bis 360 und 367 bis 368 |
| chatgpt.py `_fetch_file` | `files_tools.read(..., known=entry)` | Eintrag ersetzt stat-PROPFIND | WIRED | Zeile 345 |
| files.py `_visible_stat` | `clients.exclusion.scope(clients)` | auch mit known | WIRED | Zeile 746 |
| `.github/workflows/ci.yml` | `tests/integration/test_findling_sandbox.py` | Schritt nach Content-hit-Schritt | WIRED | Zeile 128 |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Unit-Suite auf main e15af1b | `.venv/Scripts/python.exe -m pytest tests/unit -q` | Exit 0; 4798 passed, 33 skipped, 0 failed (aus der Fortschrittsanzeige gezählt) | PASS |
| 27-10-Akzeptanz-Greps | grep auf context.py, chatgpt.py, notes.py; `git diff 43c5a9d` auf dav.py, server/, Notes-Tests | 1 / 1 / 1 / 1 / 2; Diffs leer | PASS |
| Integrationstests gegen Live-Instanzen | nicht ausgeführt (Auftrag) | Beleg aus Rohdateien | SKIP |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|--------------|--------|----------|
| EXCL-01 | 27-01, 27-02, 27-07 | Getaggte Datei/Ordner in keiner Datei-Werkzeug-Antwort, Upload orakelfrei | SATISFIED | SC1 live, nach 27-10 erneut grün |
| EXCL-03 | 27-01, 27-03, 27-05, 27-06, 27-07, 27-09, 27-10 | unified_search/fetch/prepare_context ohne getaggten Treffer/Ausschnitt/Digest; Wanduhr im Rahmen | SATISFIED (Wanduhr per Owner-Abnahme) | SC2 10/10 "ja"; Wanduhr am 28.09. abgenommen |
| EXCL-05 | 27-04, 27-07 | Notes respektieren den Tag | SATISFIED | SC3 live; 27-10 byte-gleich laut Paartests |
| EXCL-06 | 27-05, 27-07 | talk_browse ohne Dateinamen getaggter Dateien | SATISFIED | SC4 live |
| SBX-01 | 27-03, 27-08 | Findling-Treffer nur mit fileId durch Sandbox/Ausschluss | NEEDS HUMAN | CI-Lauf gegen echten Findling steht aus |
| SBX-02 | 27-01, 27-03, 27-04, 27-07 | Notes durch Sandbox und Ausschluss | SATISFIED | `count=0 skipped=3` live |

Keine Waisen: REQUIREMENTS.md ordnet Phase 27 genau diese sechs IDs zu, alle sind in Plan-Frontmattern beansprucht. Die Traceability-Tabelle führt sie noch als "Pending"; das nachzuziehen ist Sache von phase.complete.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| src/mcp_connector/tools/{notes,chatgpt,context,files}.py, nextcloud/clients/dav.py, tests/unit/test_excerpt_batch.py, tests/integration/test_ctx_bundle.py | | TBD/FIXME/XXX | keiner gefunden | |
| 27-LIVE-BEWEIS.md | 37 | SC2-Tabellenzeile "prepare_context Wanduhr" endet mit "Owner-Entscheid offen" | Info | veraltet seit e15af1b; "## Abnahme" ist maßgeblich und korrekt |
| 27-LIVE-BEWEIS.md | 250 | "7 bis 9 von 11 Läufen" | Info | nachgezählt 10 / 8 / 6; ohne Einfluss auf B full und die Abnahme |
| 27-09-SUMMARY.md, 27-10-SUMMARY.md | | "Status: CHECKPOINT OFFEN" | Info | nicht nachgeführt nach den Owner-Entscheiden; Code und Live-Beweis sind maßgeblich |
| raw/27-10-prepare-context-2026-09-28.txt | 2 | Kopfzeilen-Kommando ohne `NC_MCP_E2E_*`-Exporte | Info | in Anhang 3 und im Live-Beweis offen benannt, betrifft nur den Harness |

### Human Verification Required

#### 1. SBX-01 im CI-Job exapp

**Test:** Beim nächsten Push den CI-Job 'exapp' beobachten, Schritt "Findling hits run through sandbox and exclusion (SBX-01)".
**Expected:** PASSED für Root-Sandbox-Fall (skipped>=1 plus Gegenprobe) und Tag-Fall (skipped unverändert gegenüber der Gegenprobe), kein Skip.
**Why human:** nc35 hat keinen Findling-Provider; main ist seit dem 26.09. nicht gepusht (171 Commits voraus), der Schritt lief also noch nie.

### Gaps Summary

Die Blocker-Lücke der Erstverifikation ist geschlossen. Die Lückenpläne 27-09 (eine Sammel-SEARCH für Datei-Ausschnitte, kein stat-PROPFIND) und 27-10 (Pfadprüfung der Notiz-Ausschnitte in derselben SEARCH) sind im Code auf main vorhanden, verdrahtet und durch Paritätstests abgesichert; die Request-Seite ist in der Rohdatei belegt (B full files-search 4 auf 3 auf 2, ein REPORT je Antwort, propfind 0). Die Wanduhr hält die Schwelle 0,97 s für B full nicht stabil (6 Messungen, nur Messung 1 mit 0,937 s darunter, Median der Mediane 1,139 s), der alte Code in der abwechselnden Kontrolle aber ebenso wenig (5/5 darüber). Der Owner hat das am 28.09.2026 mit dokumentierter Begründung abgenommen; die Zahlen im Live-Beweis stimmen mit der Rohdatei überein, einzig ein Nebensatz zur Zahl der innerhalb liegenden Läufe der übrigen drei Zeilen ist ungenau. Diese Abnahme ist hier als Override geführt.

Alle früher verifizierten Kriterien halten auf main: die Unit-Suite ist grün (4798 passed, 33 skipped), die Live-Beweise 27-07 liefen nach beiden Lückenplänen erneut ohne eine Zeile ": nein", und seit dem gemessenen Stand 656af9d hat sich nur Dokumentation geändert.

Offen bleibt allein der CI-Nachweis für den Findling-Teil (SBX-01), deshalb human_needed statt passed.

---

_Verified: 2026-09-28_
_Verifier: Claude (gsd-verifier)_

## Nachtrag 2026-10-01

Offener Punkt erledigt: CI-Lauf 36861555478 auf 5a89219 (Push nach Owner-Freigabe), Job `exapp`, Schritt "Findling hits run through sandbox and exclusion (SBX-01)" success, pytest meldet `1 passed in 13.15s`, kein Skip. Damit ist SBX-01 auch im Findling-Teil gegen einen echten Findling belegt. Status human_needed -> passed.
