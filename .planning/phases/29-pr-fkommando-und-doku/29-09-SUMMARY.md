---
phase: 29-pr-fkommando-und-doku
plan: 09
subsystem: docs
tags: [store-texts, sha256, exclusion, doc-03, owner-approval]

requires:
  - phase: 29-pr-fkommando-und-doku
    provides: docs/exclusion*.md, README-Abschnitte, Doku-Wahrheitstest (29-07, 29-08), info.xml-Kommentar (29-05)
provides:
  - tests/unit/test_store_texts_frozen.py (SHA-256-Pin der sechs Store-Texte, Stand ca157b4)
  - raw/29-09-store-diff.txt (Rohbeleg, DIFF LEER)
  - Owner-freigegebener Wortlaut der drei Betreiberseiten und drei README-Abschnitte
affects: [verify-phase 29, secure-phase 29, nächstes Release]

tech-stack:
  added: []
  patterns:
    - "Store-Texte per Hash der extrahierten direkten Kinder festnageln statt git show (flacher CI-Checkout)"

key-files:
  created:
    - tests/unit/test_store_texts_frozen.py
    - .planning/phases/29-pr-fkommando-und-doku/raw/29-09-store-diff.txt
  modified:
    - docs/exclusion.md
    - docs/exclusion.de.md
    - docs/exclusion.fr.md

key-decisions:
  - "Store-Texte per SHA-256 über '<tag>|<lang>|<text>' der sechs direkten Kinder von info gepinnt; Erneuerung nur mit Owner-Entscheid zum nächsten Release"
  - "Owner-Wortlautänderungen: Jargon durch Klartext, Abschnitt ohne --admin in drei Sätzen, SQLite als Messung samt 15-s-Budget, Hinweis auf englische Ausgabe in DE/FR"
  - "Linktexte der Quellen (Owner-Entscheid E3, Owner decisions) und fail-closed unverändert, weil nicht erbeten"

requirements-completed: [OPS-01, DOC-03]

duration: 60min
completed: 2026-10-01
---

# Phase 29 Plan 09: Store-Pin, Gates und Owner-Abnahme Summary

**Store-Texte doppelt als unverändert seit ca157b4 belegt (SHA-256-Pin im CI-Job unit plus leerer Rohdiff), alle Gates grün, Doku-Wortlaut nach vier Owner-Korrekturen am 2026-10-01 freigegeben**

## Performance

- **Duration:** ca. 60 min inklusive Wartezeit auf den Owner
- **Completed:** 2026-10-01
- **Tasks:** 3/3
- **Files:** 2 erstellt, 3 geändert

## Accomplishments

- `tests/unit/test_store_texts_frozen.py`: `FROZEN_AT = "ca157b4"`, `EXPECTED_SHA256 = "cddc87fd...c1ba47"`, `EXPECTED_COUNT = 6`, zweiter Test hält die Reihenfolge en/de/fr; Gegenprobe mit einem zusätzlichen Leerzeichen ändert den Hash
- `raw/29-09-store-diff.txt`: Skript wörtlich, `diff-zeilen=0`, `DIFF LEER summary/description en de fr: ca157b4 gegen cef6e98`, `git diff ca157b4 --stat -- appinfo/info.xml` = 10 Einfügungen (nur Kommentar aus 29-05)
- Owner-Korrekturen in allen drei Sprachen eingearbeitet (a9ec7ad)

## Owner-Abnahme

Erste Antwort (2026-10-01): nicht freigegeben, vier Änderungen erbeten. Eingearbeitet in a9ec7ad, je in docs/exclusion.md, docs/exclusion.de.md, docs/exclusion.fr.md:

1. (2) Jargon: "akzeptiertes Risiko" zu "eine bekannte, bewusst hingenommene Grenze" (Antwortzeit), "akzeptiert" zu "bewusst hingenommen" (notes_create), "fail-open, Owner-Entscheid" zu "lässt der Connector ihn im Zweifel durch, bewusst so entschieden" (Drittanbieter-Suchprovider); EN und FR sinngleich
2. (4) Abschnitt "Ohne --admin" auf drei Sätze gekürzt (liest wie ein gewöhnliches Konto, nur sichtbare Tags, unsichtbare Tags und Delegationsgruppen nicht prüfbar und die Ausgabe sagt das, vollständig mit `--admin=<uid>`)
3. (5) SQLite als Messung: "Gemessen: ... bei 140.005 Zuordnungen rund 240 s ...", dazu das 15-s-Budget (`TAG_BUDGET` in exclusion.py) als Begründung für "nicht beantwortbar"
4. (7) DE und FR: Satz vor den Beispielausgaben, dass das Kommando englisch antwortet und "See docs/exclusion.md" auf die englische Seite zeigt

Zweite Antwort, wörtlich: **"approved" (2026-10-01)** für den Wortlaut wie in a9ec7ad, einschließlich der notes_create-Ersetzung; keine weiteren Änderungen. Owner approved 2026-10-01.

## Task Commits

1. **Task 1: Store-Pin** - `d266efd` (test)
2. **Task 1: Rohbeleg** - `10dc022` (docs)
3. **Task 3: Owner-Korrekturen** - `a9ec7ad` (docs)

## Gates

Vor a9ec7ad und erneut zum Abschluss, PYTHONUTF8=1: ruff check grün, ruff format --check grün (328 Dateien), pyright latest 0 Fehler, vulture (src scripts vulture_whitelist.py) grün, pytest tests/unit tests/contract **5276 passed, 33 skipped, 0 failed**; Doku-Wahrheitstest plus Store-Pin 41 passed; keine U+2013/U+2014 in Seiten und READMEs.

## Deviations from Plan

1. **[Rule 3] lxml mit hardened_parser statt xml.etree:** Gleiches Muster wie tests/unit/test_exapp_env_setup.py, vermeidet einen unsicheren XML-Parser im Repo.
2. **SQLite-Satz mit 15-s-Budget statt "endete als nicht beantwortbar":** Gemessen wurde die rohe Tag-Abfrage, nicht die Connector-Prüfung; das Budget aus dem Code macht die Folgerung belegbar. Vom Owner mit a9ec7ad freigegeben.
3. **`uv run vulture` mit Pfaden:** wie in 29-04 bis 29-08.

## Known Stubs

Keine.

## Self-Check: PASSED

- tests/unit/test_store_texts_frozen.py und raw/29-09-store-diff.txt vorhanden
- Commits d266efd, 10dc022, a9ec7ad vorhanden
