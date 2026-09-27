---
phase: 27-familien-anschluss-und-sandbox-parit-t
plan: 08
subsystem: live-beweise
tags: [exclusion, kein-ki, wanduhr, prepare_context, findling, sandbox, nc35, ci]
requires:
  - "27-07: Live-Beweise SC1 bis SC5, A1, Rohprotokoll 27-07-live.txt"
provides:
  - "tests/integration/test_ctx_bundle.py: frischer Guard je Aufruf, RUNS=5, Messung 1b (Szenarien A/B), Guard-Kategorien in der Request-Zählung"
  - "tests/integration/test_findling_sandbox.py: SBX-01 mit echtem Findling (CI)"
  - "raw/27-08-prepare-context.txt: WANDUHR-Zeilen, Vorlauf, Kontrolle mit Code vor Phase 27"
  - "27-LIVE-BEWEIS.md: Messbericht der Phase 27"
affects:
  - "Phase 28: Klassifikations-Freeze (talk_send, notes_create betroffen), ChatGPT-search ohne degraded"
  - "Phase 29: Restorakel-Doku, Referenz-Regel für Wanduhr-Schwellen"
tech-stack:
  added: []
  patterns:
    - "fresh(clients): dataclasses.replace(clients, exclusion=ExclusionGuard()) je Tool-Aufruf in Testdateien mit langlebigem NcClients"
    - "Kontrollmessung mit dem Code vor dem Feature (git archive in ein temporäres Verzeichnis) trennt Host-Drift von Feature-Kosten"
key-files:
  created:
    - tests/integration/test_findling_sandbox.py
    - .planning/phases/27-familien-anschluss-und-sandbox-parit-t/raw/27-08-prepare-context.txt
    - .planning/phases/27-familien-anschluss-und-sandbox-parit-t/27-LIVE-BEWEIS.md
  modified:
    - tests/integration/test_ctx_bundle.py
    - .github/workflows/ci.yml
decisions:
  - "Szenario A und B laufen auf denselben Testdaten (vor A angelegt, erst vor B getaggt); die Namen tragen das Suchwort, damit der Guard in B wirklich Treffer zurückhält"
  - "Überschreitung B full wird nicht getunt, sondern mit einer Kontrollmessung des Codes vor Phase 27 (2f03242) eingeordnet und dem Owner vorgelegt"
  - "files-search zählt jede SEARCH auf die DAV-Wurzel; in full stammen 3 davon aus den Ausschnitt-fetches, nicht vom Guard (im Bericht getrennt ausgewiesen)"
metrics:
  duration: "ca. 55 min"
  completed: 2026-09-27
  tasks: "2 von 3 (Task 3 = Owner-Checkpoint offen)"
  files: 5
---

# Phase 27 Plan 08: Wanduhr, Findling-CI-Fall und Messbericht Summary

prepare_context ist gegen nc35 mit frischem Guard je Aufruf in zwei Szenarien gemessen (drei von vier Medianen innerhalb der Schwelle, B full mit 1,047 s um 0,077 s darüber, eingeordnet durch eine Kontrolle mit dem Code vor Phase 27, die heute schon 0,99 bis 1,07 s misst), die Request-Kosten sind mit eigenen Guard-Kategorien neu verankert, der Findling-Fall SBX-01 ist als CI-Test verdrahtet, und 27-LIVE-BEWEIS.md fasst die Phase aus den Rohdateien zusammen.

**Status: CHECKPOINT OFFEN.** Task 3 (Owner-Abnahme) ist nicht erledigt; der Abschnitt "## Abnahme" in 27-LIVE-BEWEIS.md steht auf "Ausstehend".

## Was gebaut wurde

**Task 1 (fcb69f9):** `fresh(clients)` im Modul, alle Tool-Aufrufe über die Fixtures `alice`/`counted` laufen mit eigenem ExclusionGuard. `RUNS = 5`. `leg_of(path, method)` kennt vor der calendar-dav-Regel `exclusion-tags`, `exclusion-report`, `files-search`, `files-read`. Neuer Test `test_the_wall_clock_against_the_phase_25_reference`: Testordner und Testdatei (Name mit "Abnahme") per WebDAV mit App-Passwort, Szenario A ohne kein-ki, Szenario B mit kein-ki per occ auf Datei und Ordner, je detail 1 Aufwärmlauf plus 5 Läufe, je Lauf eine LAUF-Zeile mit Guard-Kategorien, je Szenario/detail eine WANDUHR-Zeile; Schwelle wird nicht assertet, CALENDAR_BUDGET schon; Aufräumen im finally mit PROPFIND 404 und Tag-Liste 0 als Assert. Request-Kosten-Test neu verankert (ohne Tag: genau 1 Tag-Liste kalt und warm, 0 REPORT, 0 SEARCH).

**Task 2 (d90b1e4):** `test_findling_sandbox.py` (Skip ohne Provider `findling`, Upload zweier Dokumente mit Inhaltsmarker, Cron-Anstoß wie in test_content_hit_fidelity.py, Root-Fall mit skipped >= 1 und Gegenprobe, Tag-Fall mit unverändertem skipped, Aufräumen im finally). CI-Schritt im Job exapp nach dem Content-hit-Schritt. 27-LIVE-BEWEIS.md. vulture_whitelist.py geprüft: der Abschnitt "The withholding helpers of plan 27-01" trägt keinen Namen mehr, keine Änderung nötig.

## Messwerte (raw/27-08-prepare-context.txt)

| Szenario | detail | Median | Schwelle | Urteil |
|---|---|---|---|---|
| A (kein Tag) | short | 0,786 s | 0,88 s | innerhalb |
| A (kein Tag) | full | 0,937 s | 0,97 s | innerhalb |
| B (Datei + Ordner getaggt) | short | 0,797 s | 0,88 s | innerhalb |
| B (Datei + Ordner getaggt) | full | 1,047 s | 0,97 s | **überschritten** |

- Vorlauf (gleicher Test, 3 Minuten früher): A full 1,033 und B full 1,072 überschritten, short beide innerhalb.
- Kontrolle Code vor Phase 27 (kein Guard), drei Läufe: short 0,78/0,85/0,82 s, full 0,99/1,05/1,07 s.
- Request-Kosten: ohne Tag 23 (kalt) bzw. 20 (warm) Requests, davon 1 Tag-Liste; B warm: 0 Tag-Liste, 1 REPORT, 1 fileid-SEARCH.

## Verifikation

- `test_ctx_bundle.py -m integration` gegen nc35: alle 9 Tests grün; 4 WANDUHR-Zeilen in der Rohdatei.
- `test_findling_sandbox.py` lokal: `SKIPPED [1] ... the findling provider is not installed on this instance; CI installs it with scripts/install_findling.sh`.
- `grep -c "ExclusionGuard()"` = 1, `grep -c "RUNS = 5"` = 1, `"exclusion-tags"|"exclusion-report"` = 5; ci.yml genau ein Schritt mit test_findling_sandbox; LIVE-BEWEIS ohne U+2013/U+2014.
- Gates: ruff check, ruff format --check (298 Dateien), pyright latest 0 Fehler, vulture grün, pytest tests/unit tests/contract Exit 0, check_tool_budget Exit 0.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug im neuen Test] query-Echo in der Leck-Prüfung**
- **Found during:** Task 2
- **Issue:** unified_search gibt `query` zurück; die Prüfung "Marker nicht im serialisierten Ergebnis" wäre immer rot gewesen.
- **Fix:** `_beyond_query()` serialisiert die Antwort ohne `query`.
- **Commit:** d90b1e4

**2. [Rule 2] Modul-Docstring von test_ctx_bundle.py korrigiert**
- "This file creates nothing" stimmte mit Messung 1b nicht mehr; der Absatz nennt jetzt die Testdaten und ihr geprüftes Aufräumen.
- **Commit:** fcb69f9

### Zusätzlich, nicht im Plan

- **Kontrollmessung mit dem Code vor Phase 27:** Weil auch A full im Vorlauf über der Schwelle lag, lief `test_ctx_bundle.py` aus Commit 2f03242 (per `git archive` in ein temporäres, nicht committetes Verzeichnis) dreimal auf demselben Host. Rohzeilen als Anhang 2 in der Rohdatei, das Verzeichnis ist gelöscht.
- **Vorlauf dokumentiert:** Der erste Lauf endete nur am Protokolltest mit `UnicodeEncodeError` (cp1252 der Windows-Konsole beim Druck von "Talk updates ✅"); danach `PYTHONIOENCODING=utf-8`. Seine vier WANDUHR-Zeilen stehen als Anhang 1 in der Rohdatei, weil der Messlauf die Datei überschrieb.

### Ausführungsumgebung

- Worktree-Base war abweichend (7a93585) und wurde laut Auftrag per `git reset --hard 71d6384` korrigiert.
- `.env.nc35` per temporärem Python-Lader (nicht committet, gelöscht), dazu die `NC_MCP_E2E_*`-Variablen der nc35-Topologie wie in Phase 25; pytest über die Hauptrepo-venv mit `-o pythonpath=...`.
- pyright braucht in der Worktree `--pythonpath` auf die Hauptrepo-venv (keine eigene .venv).

## Offener Checkpoint (Task 3)

Der Owner muss 27-LIVE-BEWEIS.md abnehmen und über die Überschreitung B full (1,047 s gegen 0,97 s) entscheiden: Schwelle mit Begründung akzeptieren (Host-Drift, belegt durch die Kontrolle ohne Guard bei 0,99 bis 1,07 s) oder Lückenplan (`/gsd:plan-phase 27 --gaps`). Die Antwort wird wörtlich mit Datum unter "## Abnahme" eingetragen.

## Known Stubs

Keine. Der Abschnitt "## Abnahme" steht bewusst auf "Ausstehend", bis der Owner antwortet.

## Threat Flags

Keine neue Angriffsfläche. T-27-70 (Findling-CI-Test), T-27-71 (frischer Guard, fünf Läufe, Rohzeilen), T-27-72 (Rohdatei ohne Secrets, test_no_measured_line_carries_the_app_secret grün) umgesetzt; T-27-73 (Überschreitung) wie geplant dem Owner vorgelegt.

## Commits

- fcb69f9 test(27-08): measure the prepare_context wall clock with a fresh guard per call
- d90b1e4 test(27-08): Findling fileId hits through sandbox and exclusion in CI, live proof report

## Self-Check: PASSED

- FOUND: tests/integration/test_findling_sandbox.py, tests/integration/test_ctx_bundle.py, raw/27-08-prepare-context.txt, 27-LIVE-BEWEIS.md
- FOUND: fcb69f9, d90b1e4
