---
phase: 25-mess-spike-tag-abfrage
plan: 04
subsystem: messbericht / Owner-Checkpoint D-25-05
tags: [spike, messbericht, checkpoint, systemtags, notes, fail-closed, latenz]
requires:
  - 25-01 (raw/nc35-befunde.txt, raw/nc35-prepare-context-baseline.txt)
  - 25-02 (raw/nc35-latenz.txt, raw/nc35-prepare-context-mit-daten.txt)
  - 25-03 (raw/matrix-32.txt, raw/matrix-33.txt, raw/matrix-34.txt)
provides:
  - 25-MESSBERICHT.md (Befundtabelle K1 bis K5, Rohauszüge, Grenzen, Nebenbefunde, Owner-Entscheid, Ableitungen)
affects: [25-05, 26, 27, 29]
tech-stack:
  added: []
  patterns:
    - "Messbericht nach docs/exchange-evidence.md: Kopfblock, je Befund Kommando, Rohwert, Deutung, Rohdatei"
key-files:
  created:
    - .planning/phases/25-mess-spike-tag-abfrage/25-MESSBERICHT.md
  modified: []
decisions:
  - "2026-09-26 D-25-05 E1: EXCL-05 wird in Phase 27 gebaut (Notiz-Id = fileid belegt), Anschluss über Notiz-fileid plus Pfadprüfung notesPath/category"
  - "2026-09-26 D-25-05 E2: Fail-closed-Auslöser ist der REPORT-Ausgang (207 = Menge ermittelt, 412 = Tag-Id einmal neu auflösen, alles andere = nicht prüfbar); die systemtags-Capability wird nicht befragt"
  - "2026-09-26 D-25-05 E3: Batch-Entscheid vertagt bis Zusatzplan 25-05; 'ein REPORT je Antwort' ist nicht bestätigt (Median warm bei 5000 = 8,848 s über Schwelle 1,0 s)"
  - "2026-09-26 D-25-05 E4: PostgreSQL-Gegenmessung als Zusatzplan 25-05 vor Phase 26 (Stufen 1/100/5000 auf PostgreSQL, Stufe 1+100 mit 145k-Ballast, PROPFIND-Weg mit nc:system-tags an Antwortknoten plus Vorfahren); D-25-02 erweitert, Phase 25 nicht abgeschlossen"
metrics:
  duration: "ca. 20 min"
  completed: 2026-09-26
  tasks: 2
  files: 1
---

# Phase 25 Plan 04: Messbericht und Owner-Checkpoint Summary

Messbericht `25-MESSBERICHT.md` aus den sieben Rohprotokollen geschrieben. Am Checkpoint D-25-05 hat der Owner "Empfehlungen übernehmen" geantwortet: Notes wird gebaut, Fail-closed hängt am REPORT-Ausgang, der Batch-Entscheid wartet auf die Zusatzmessung 25-05.

## Kernbefunde (Belege im Messbericht)

- K1 App aus: REPORT auf 32.0.15, 33.0.9, 34.0.4 und 35.0.0 unverändert 207 mit Treffern; Capability und Suchprovider verschwinden auf 32 bis 34 erst nach Neustart (APCu), auf 35 sofort; `tag:files:*` fehlen überall.
- K2 Impersonation: gleiche fileid-Menge Basic, AppAPI und Produktionsweg; Kontrollen a/b/c bestanden.
- K3 Kosten: 59 / 243 / 8.848 ms (Stufe 1/100/5000, warm), kalt 8.563 ms, mit 145.000 Zuordnungen Ballast 249,6 s; prepare_context 0,72 / 0,82 s. Schwelle D-25-04 gerissen.
- K4 Notiz-Id gleich fileid: ja.
- K5 412 auf allen Versionen gleich, unsichtbares Tag 412 für Nicht-Admins, Varianten nur bei gleicher Schreibung vereint, Zielpfad filtert nicht, Tag auf Vorfahr beim Eigentümer für Freigabe-Empfänger unsichtbar.

## Owner-Entscheid (2026-09-26)

| Entscheid | Owner-Antwort | Option |
|---|---|---|
| E1 Notes-Weg | "Empfehlungen übernehmen" | empfehlung (EXCL-05 bauen) |
| E2 Fail-closed-Auslöser | "Empfehlungen übernehmen" | empfehlung (REPORT-Ausgang, keine Capability) |
| E3 Batch-Strategie | "Empfehlungen übernehmen" | vertagt bis 25-05 |
| E4 PostgreSQL-Gegenmessung | "Empfehlungen übernehmen" | postgres-gegenmessung |

**Für den Orchestrator:** Weil die Option postgres-gegenmessung gewählt ist, ist ein zusätzlicher Plan 25-05 nötig. Phase 25 darf nicht abgeschlossen werden, bevor 25-05 gelaufen ist und der Owner E3 entschieden hat.

## Tasks

| Task | Commit | Inhalt |
|---|---|---|
| 1 | fb707d9 | Messbericht mit Befundtabelle, Rohauszügen, Grenzen, Nebenbefunden, Empfehlungen E1 bis E4 |
| 2 | a16752b | Owner-Entscheid und Ableitungen für Phase 26 und 27 eingetragen |

## Deviations from Plan

- Der Plan sieht bei E3 nur die Optionen `empfehlung` und `batch-alternative` vor. Die Messung schließt die Alternative "engerer Zielpfad" aus (Zielpfad filtert nicht), deshalb enthielt die Empfehlung eine neue, noch nicht gemessene Alternative (Tag-Prüfung an Antwortknoten plus Vorfahren). Der Owner hat E3 vertagt, keine Option ist gewählt.
- Plan-Kommando `uv run --no-sync ...` ersetzt durch das Python der venv des Hauptcheckouts mit `PYTHONPATH=src` und `--env-file ../../../.env.nc35` (wie in 25-01 bis 25-03, uv sync im Worktree blockiert). secret-scan jeweils 8 Dateien, 0 Funde, Exit 0.
- Die Owner-Antwort kam über den Orchestrator. Im Bericht ist sie als vom Orchestrator wörtlich übermittelt gekennzeichnet.

## Known Stubs

Keine. Der offene Batch-Entscheid ist im Bericht unter "Offen bis 25-05" benannt.

## Threat Flags

Keine. T-25-17 (secret-scan nach Task 1 und Task 2, Exit 0), T-25-18 (Bericht nur im Phasenordner, nichts unter docs/, kein Push), T-25-19 (Owner-Antwort mit Datum und Option-Id im Bericht und hier).

## Self-Check: PASSED

- Datei vorhanden: .planning/phases/25-mess-spike-tag-abfrage/25-MESSBERICHT.md
- Commits vorhanden: fb707d9, a16752b
