---
phase: 28-gates-und-beweise
plan: 12
subsystem: Live-Beweis, Gates, Regression Phase 27
tags: [gate-01, gate-02, gate-03, excl-07, live, nc35, abnahme]
status: checkpoint-open
requires:
  - 28-03 (EXCL-07 Nadeln)
  - 28-08, 28-09 (GATE-03 Unit)
  - 28-10 (Kanarie, D-28-21)
  - 28-11 (Live-Paare, CI-Schritt)
provides:
  - .planning/phases/28-gates-und-beweise/28-LIVE-BEWEIS.md (wartet auf Owner-Abnahme)
  - raw/28-12-gates.txt, raw/28-12-exclusion-live.txt
affects: [29]
tech-stack:
  added: []
  patterns: [Rohdatei-Kernzeilen eines Wiederholungslaufs, danach git checkout der Plan-Rohdateien]
key-files:
  created:
    - .planning/phases/28-gates-und-beweise/28-LIVE-BEWEIS.md
    - .planning/phases/28-gates-und-beweise/raw/28-12-gates.txt
    - .planning/phases/28-gates-und-beweise/raw/28-12-exclusion-live.txt
  modified:
    - tests/integration/test_exclusion_live.py
decisions:
  - "test_exclusion_live.py nimmt den Container aus topology.NC_CONTAINER; keine Erwartung umgestellt, weil kein Fall das Verhalten vor D-28-15/D-28-17 festhielt"
  - "Budget-Referenz 16412 (2026-09-20) ist älter als Phase 27; Phase 28 hat das Budget nicht verändert (17233 Bytes am Phasenanfang 372db35 und heute)"
  - "Die Phase-28-Integrationsdateien hängen an die Plan-Rohdateien 28-01/07/10/11 an; Kernzeilen des gemeinsamen Laufs stehen in raw/28-12-gates.txt, die vier Dateien sind zurückgesetzt"
metrics:
  duration: ca. 45 min
  completed: 2026-09-28
---

# Phase 28 Plan 12: Gate-Lauf, Regression und Live-Beweis Summary

Voller Gate-Lauf grün (5049 passed, ruff, format, pyright latest, vulture, Budget 17233 Bytes), Phase-27-Live-Beweise nach allen Fixes 10 passed ohne Urteil nein, alle vier Phase-28-Integrationsdateien gemeinsam 14 passed gegen nc35. Der Live-Beweis 28-LIVE-BEWEIS.md liegt vor. **Checkpoint Task 3 (Owner-Abnahme) ist offen.**

## Tasks

| Task | Name | Commit | Status |
| ---- | ---- | ------ | ------ |
| 1 | Voller Gate-Lauf und Regressionslauf der Phase-27-Live-Beweise | 77904d1 | erledigt |
| 2 | 28-LIVE-BEWEIS.md schreiben | d066a0b | erledigt |
| 3 | Owner-Abnahme Phase 28 (checkpoint:human-verify, blocking) | offen | wartet auf Owner |

## Ergebnisse

- Gate-Lauf (raw/28-12-gates.txt, Kopf mit Datum und HEAD 6fd4526): `5049 passed, 33 skipped`, `All checks passed!`, `311 files already formatted`, `0 errors, 0 warnings, 0 informations`, vulture Exit 0, `tools/list: 17233 bytes, 22 tools, budget 18000`; 61 PASSED-Zeilen aus test_tool_classes.py und test_no_destructive_calls.py als Testnamen-Beleg für GATE-01 und EXCL-07; Paar-Unit 39 und 40 passed; Unit-Dateien der Fixes 184 passed.
- Regression (raw/28-12-exclusion-live.txt): `10 passed in 57.68s`, 57 Befundzeilen ja, 0 nein; raw/27-07-live.txt ohne Diff.
- Gemeinsamer Lauf der vier Phase-28-Integrationsdateien: `14 passed in 210.60s`; darin nach den Fixes `BEFUND B5 gleich` und `marker_in_tables_browse=nein` (vor den Fixes: B5 ungleich, Marker in tables_browse).
- nc35 aufgeräumt und gelesen: Papierkorb-Einträge der Läufe von 28-12 (9) per WebDAV gelöscht (204, danach 404), `occ tag:list` = `[]`, kein Testbaum und kein Upload-Staging übrig.

## Deviations from Plan

**1. [Rule 3 - Blockierend] pytest ohne zusätzliches -q**
- `addopts` enthält bereits `-q`; mit dem Plan-Kommando (`-q`) fehlt die Zählzeile. Gate 1 und der gemeinsame Integrationslauf liefen deshalb ohne zusätzliches `-q`. Der erste gemeinsame Lauf mit `-q` (14 Punkte, Exit 0, ohne Zählzeile) wurde wiederholt; beides steht in der Rohdatei.

**2. [Rule 3] Worktree-Isolation**
- Binaries der venv des Haupt-Checkouts statt `uv run`; Env aus `.env.nc35` per Python-Lader (nicht kopiert). Hilfsskripte lagen im ignorierten `build/`.

**3. [Rule 2] Plan-Rohdateien geschützt**
- Der gemeinsame Lauf hängt an raw/28-01, 28-07, 28-10 und 28-11 an. Die Kernzeilen stehen in raw/28-12-gates.txt, die vier Dateien sind per `git checkout --` zurückgesetzt (wie 27-07-live.txt).

**4. [Rule 2] Papierkorb-Rest**
- test_exclusion_live.py und test_live_questions_28.py hinterlassen ihre gelöschten Bäume im Papierkorb. Die Einträge dieses Plans wurden gelöscht und zurückgelesen; ältere Einträge früherer Pläne blieben unangetastet (in der Rohdatei vermerkt).

**5. [Auslegung] Budget-Referenz**
- Der Plan vergleicht mit 16412 Bytes (2026-09-20). Gemessen: 17233 Bytes heute und am Phasenanfang (372db35, per git archive). Gegen 16412 gewachsen, aber nicht durch Phase 28; so im Bericht benannt.

## Known Stubs

Keine.

## Threat Flags

Keine neue Oberfläche. T-28-120 (Zahlen wörtlich aus raw/), T-28-121 (27-07-live.txt ohne Diff), T-28-122 (Abschnitt "Offen": CI erst nach Push) und T-28-123 (Merker mit Entscheidungs-Ids) sind umgesetzt.

## Checkpoint offen

Task 3 wartet auf den Owner-Entscheid unter "## Abnahme" in 28-LIVE-BEWEIS.md ("Owner-Entscheid zu Phase 28: Ausstehend"). Zur Bestätigung stehen dort außerdem die zwei konservativen Regeln zu D-28-21 (unbekanntes Token zurückgehalten, sobald etwas getaggt ist; nicht lesbare Gesprächsliste hält alle talk-conversations-Treffer mit einem degraded-Eintrag unter dem Provider-Namen zurück).

## Self-Check: PASSED

- FOUND: .planning/phases/28-gates-und-beweise/28-LIVE-BEWEIS.md, raw/28-12-gates.txt, raw/28-12-exclusion-live.txt
- FOUND: 77904d1, d066a0b
