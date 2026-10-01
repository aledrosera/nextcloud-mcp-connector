---
phase: 29-pr-fkommando-und-doku
plan: 08
subsystem: docs
tags: [docs, exclusion, kein-ki, readme, doc-03, french]

requires:
  - phase: 29-pr-fkommando-und-doku
    provides: docs/exclusion.md, docs/exclusion.de.md, tests/unit/test_docs_exclusion_truth.py (29-07), raw/29-01-messungen.txt (M9)
provides:
  - docs/exclusion.fr.md (FR operator page, 21 anchors)
  - kein-ki section in README.md, README.de.md, README.fr.md
affects: [29-09]

tech-stack:
  added: []
  patterns:
    - "README-Abschnitt als Faktenliste: vier Zeilen (Wirkung, Prüfkommando, Freigabe-Grenze, Link), direkt vor der Sicherheits-Überschrift"

key-files:
  created:
    - docs/exclusion.fr.md
  modified:
    - README.md
    - README.de.md
    - README.fr.md

key-decisions:
  - "FR-Menüpfad aus M9 (zweiter Lauf, vollständig): Paramètres d'administration > Paramètres de base > Étiquettes collaboratives"
  - "Französische Typografie mit normalem Leerzeichen vor Doppelpunkt und Semikolon, wie in README.fr.md (kein geschütztes Leerzeichen)"
  - "DOC-03 nicht abgehakt: 29-09 führt die Anforderung ebenfalls, Abschluss dort"

requirements-completed: []

duration: 12min
completed: 2026-10-01
---

# Phase 29 Plan 08: Französische Betreiberseite und README-Abschnitte Summary

**docs/exclusion.fr.md deckungsgleich mit der EN-Seite (21 Anker, unveränderte Codeblöcke und Quellen, FR-Menüpfad aus M9) und je ein vierzeiliger kein-ki-Abschnitt in den drei READMEs; Doku-Wahrheitstest vollständig grün (39 Fälle)**

## Performance

- **Duration:** ca. 12 min (07:18Z bis 07:30Z)
- **Completed:** 2026-10-01
- **Tasks:** 2/2
- **Files:** 1 erstellt, 3 geändert

## Accomplishments

- docs/exclusion.fr.md: gleiche 21 Anker in gleicher Reihenfolge, alle occ/curl-Zeilen und Beispielausgaben byte-gleich zur EN-Seite, gleiche Befundlinks, Sprachumschalter auf exclusion.md und exclusion.de.md, Absatz "Code de sortie" mit 0
- README.md, README.de.md, README.fr.md: je ein Abschnitt direkt vor Security / Sicherheit / Sécurité, vier Textzeilen, nur Einfügungen (numstat gegenüber ca157b4: 7/0 je Datei)
- appinfo/info.xml unberührt

## Task Commits

1. **Task 1: docs/exclusion.fr.md** - `9efea6a` (docs)
2. **Task 2: README-Abschnitte** - `8d87eba` (docs)

## Gates

Vor Commit 8d87eba: ruff check . grün, ruff format --check . grün (327 Dateien), pyright latest 0 Fehler, vulture (src scripts vulture_whitelist.py) grün, PYTHONUTF8=1 pytest tests/unit tests/contract Exit 0 (vollständig grün). tests/unit/test_docs_exclusion_truth.py: alle 39 Fälle grün, die 16 bis 29-07 planmäßig roten Fälle (lang_fr, readme_*, Umlaut-Test README.de) eingeschlossen.

## Deviations from Plan

None - plan executed exactly as written.

Hinweis: Die READMEs liegen im Arbeitsbaum mit CRLF (core.autocrlf=true, Index LF); der Einfüge-Schritt hat das Zeilenende der Datei übernommen, der Diff zeigt daher nur die sieben neuen Zeilen je README.

## Known Stubs

Keine.

## Self-Check: PASSED

- docs/exclusion.fr.md vorhanden, 21 Anker wie docs/exclusion.md
- Commits 9efea6a, 8d87eba vorhanden
