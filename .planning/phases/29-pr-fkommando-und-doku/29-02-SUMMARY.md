---
phase: 29-pr-fkommando-und-doku
plan: 02
subsystem: exclusion
tags: [systemtags, kein-ki, occ, verdict, tdd]

requires:
  - phase: 29-pr-fkommando-und-doku
    provides: Messbefunde 29-01 (Groß/Klein abgelehnt, Zählung instanzweit inkl. Papierkorb)
provides:
  - src/mcp_connector/nextcloud/exclusion_audit.py (reine Urteilsfunktion audit, TagFacts, AuditStep, AuditResult, tag_skeleton, kind_of, access_of)
  - tests/unit/test_exclusion_audit.py (49 Fälle)
affects: [29-03, 29-04, 29-05, 29-06]

tech-stack:
  added: []
  patterns:
    - "Urteil als reine Funktion, Handler liefert nur TagFacts"
    - "Normalform NFKC + casefold + nur L/N, Gleichheit statt Teilstring"

key-files:
  created:
    - src/mcp_connector/nextcloud/exclusion_audit.py
    - tests/unit/test_exclusion_audit.py
  modified:
    - vulture_whitelist.py

key-decisions:
  - "Outcome 'note' für no_tag, variant_beside_exact, mixed_access, admins_only; 'passed' mit Notiz für similar_name und groups_not_checked"
  - "passed = kein Schritt failed; skipped kippt das Urteil hier nicht (D-29-03 verlangt grün bei fehlendem Tag)"
  - "Ohne Admin-Sicht bleibt tag_visible immer not_checked, auch im Fall no_visible_tag"
  - "Unbekannte Zählung auf Variante oder exaktem Tag macht assignment_count failed"
  - "Nicht geprüfte Läufe (admin_failed, listing_ok=False) melden mode=none, assigned/unprotected=None, tags leer"

requirements-completed: []

duration: 20min
completed: 2026-10-01
---

# Phase 29 Plan 02: Reine Urteilslogik exclusion:check Summary

**audit() als I/O-freie Funktion: exakt nur über is_exclude_name, Varianten per Normalform-Gleichheit, ähnliche Namen per OSA-Abstand 1 als Hinweis, Betriebsart und ungeschützte Zahl, immer sieben Schritte**

## Performance

- **Duration:** ca. 20 min
- **Completed:** 2026-10-01
- **Tasks:** 2/2
- **Files:** 2 erstellt, 1 geändert

## Accomplishments

- Vertrag aus dem interfaces-Block exakt umgesetzt (Konstanten, Dataclasses, `__all__`), Outcome-Wörter aus `oauth/exchange_dryrun` importiert (Test prüft Identität)
- `_SKELETON` aus `tag_skeleton(EXCLUDE_TAG)` abgeleitet, nicht getippt
- Modul-Docstring nennt Pitfall P3, Gleichheit statt Teilstring, similar nur Hinweis, Homoglyphen-Grenze (T-29-07) und den 29-01-Befund: Zahlen sind Zuordnungen instanzweit inkl. Papierkorb; Groß/Klein-Varianten nur aus Altbestand, trotzdem exakt
- 49 Testfälle (25 Testfunktionen), alle Urteilsfälle des feature-Blocks inklusive no_visible_tag, T-29-05 (unlesbare Liste, unbekannte Zählung) und T-29-06 (keine Id-Felder)

## Task Commits

1. **Task 1: RED** - `55c3a19` (test), Lauf rot per ImportError
2. **Task 2: GREEN** - `ce80946` (feat)

REFACTOR nicht nötig.

## Gates

ruff check, ruff format --check, pyright latest (0 Fehler), vulture (src scripts vulture_whitelist.py), pytest tests/unit tests/contract: alle grün.

## Deviations from Plan

**1. [Rule 3 - Gate] vulture-Whitelist-Eintrag schon hier statt in 29-05**
- **Issue:** Plan sah vor, vulture in 29-02 nicht zu fahren; die Orchestrator-Vorgabe verlangt vulture vor jedem Commit. `AuditResult.checked` meldete 60 % unbenutzt.
- **Fix:** Abschnitt "verdict of plan 29-02" in `vulture_whitelist.py` mit einem Namen; 29-05 leert ihn, sobald die Konsole aus 29-04 `checked` liest.
- **Commit:** ce80946

**2. Interpretationen, die der Plan offen ließ** (in Tests festgenagelt): ohne Admin bei restricted ohne gelesene Gruppen `operating_mode=passed` mit Notiz `groups_not_checked`; im Fall "nur Variante" ist `tag_visible` bei Admin `skipped` und `operating_mode` `skipped`; ein unsichtbares Tag, das ohne Admin-Sicht trotzdem ankommt, wird ignoriert.

**3. requirements mark-complete ausgelassen:** OPS-01 erfüllt erst der Handler (29-04) und der Live-Beweis (29-06).

## Known Stubs

Keine.

## Self-Check: PASSED

- src/mcp_connector/nextcloud/exclusion_audit.py und tests/unit/test_exclusion_audit.py vorhanden
- Commits 55c3a19, ce80946 vorhanden
- Akzeptanz-Greps: is_exclude_name 3, `casefold() == ` 0, Outcome-Literale 0, httpx/await 0, keine U+2013/U+2014
