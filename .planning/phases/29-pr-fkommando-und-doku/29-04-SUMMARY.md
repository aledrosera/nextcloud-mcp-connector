---
phase: 29-pr-fkommando-und-doku
plan: 04
subsystem: exclusion
tags: [occ, exapp, systemtags, kein-ki, appapi, tdd]

requires:
  - phase: 29-pr-fkommando-und-doku
    provides: audit() aus 29-02, list_tag_details/count_tag_objects/confirm_admin aus 29-03, ENTSCHEIDE aus 29-01
provides:
  - src/mcp_connector/exapp/exclusion_check.py (exclusion_check_routes, EXCLUSION_CHECK_PATH, ADMIN_OPTION, JSON_OPTION, MAX_UID_LENGTH)
  - tests/unit/test_exapp_exclusion_check.py (37 Testfunktionen, 840 Zeilen)
affects: [29-05, 29-06]

tech-stack:
  added: []
  patterns:
    - "occ-Handler als Strukturkopie von exchange_check (Guard, Body-Grenze, immer 200), keine gemeinsame Abstraktion"
    - "uid nur im AppAPI-Token, nie in URL, Text, JSON oder Log"

key-files:
  created:
    - src/mcp_connector/exapp/exclusion_check.py
    - tests/unit/test_exapp_exclusion_check.py
  modified:
    - vulture_whitelist.py

key-decisions:
  - "JSON mode ist null bei checked=false, damit ein Ausfall nie als 'kein Tag' (mode none) lesbar ist"
  - "JSON trägt zusätzlich reason (Satz oder null); Frühabbrüche (ungültige uid, Deploy-Umgebung) liefern nur checked/passed/reason"
  - "confirm_admin None: Lesen als genanntes Konto ohne oc:groups, admin_checked false, Satz 'administrator could not be confirmed ...'"
  - "Ohne --admin jeder Nicht-207-Status und jeder Lesefehler zählt als ein Versuch (29-01: auch deaktivierte Konten antworten 207)"
  - "Gezählt werden nur exact und variant; similar/other nie"

requirements-completed: []

duration: 35min
completed: 2026-10-01
---

# Phase 29 Plan 04: Handler exclusion:check Summary

**occ-Handler /exclusion-check: Admin-Nachweis vor oc:groups, Lesekonto-Rückfall ohne --admin, Urteil aus audit(), Text mit sieben Schrittzeilen und Sätzen oder JSON mit passed, immer 200, nur PROPFIND/GET, keine Konten, Pfade oder Ids**

## Performance

- **Duration:** ca. 35 min
- **Completed:** 2026-10-01
- **Tasks:** 2/2
- **Files:** 2 erstellt, 1 geändert

## Accomplishments

- Vertrag für 29-05 steht: `EXCLUSION_CHECK_PATH = "/exclusion-check"`, `ADMIN_OPTION = "admin"`, `JSON_OPTION = "json"`, `MAX_UID_LENGTH = 64`, `exclusion_check_routes(env=None, *, client_provider=None)`
- Guard, `_set_in`, `_is_set`, `_value`, `_given`, `_text` aus exchange_check übernommen; `MAX_BODY_BYTES = 4096` wie audit_verify (Gleichheitstest)
- Texte: Kopfzeile, sieben Schrittzeilen (Spalte 12), Hinweis no_tag bzw. no_visible_tag jeweils mit `php occ tag:add kein-ki public`, Betriebsart-Satz (self_service, organisation mit gids, only administrators, Gruppen nicht gelesen), Zählung, `Items tagged '<name>' are NOT excluded: <n>`, ähnliche Namen, Satz zu nicht geprüften Teilen, LIMIT_SENTENCE zuletzt
- Benannte Ergebnisse statt Ausnahmen: Body nicht gelesen, ungültige uid (Länge, Kategorie C), Deploy-Umgebung unvollständig, kein Admin, Listing 401/500/Timeout/unlesbar, Nutzerliste unlesbar, fünf Fehlversuche; Ausnahme nur mit Typname
- Logzeilen: genau drei Aufrufe im Modul (info je Lauf mit passed/mode/assigned/admin_checked, error mit Typname, warning für den Body); Sichtprüfung: keine enthält uid, user oder name als Argument
- vulture: Abschnitte "verdict of plan 29-02" (AuditResult.checked) und "audit reads of plan 29-03" (list_tag_details, count_tag_objects, confirm_admin) entfernt, die Namen haben jetzt Aufrufer im Handler. Für den Handler selbst war kein Eintrag nötig (vulture zählt `__all__`)

## Task Commits

1. **Task 1 RED** - `4b2507c` (test), Lauf rot per ImportError
2. **Task 2 GREEN** - `1155b04` (feat)

REFACTOR nicht nötig.

## Gates

ruff check, ruff format --check, pyright latest (0 Fehler), vulture (src scripts vulture_whitelist.py), PYTHONUTF8=1 pytest tests/unit tests/contract (Exit 0): grün vor dem GREEN-Commit. RED-Commit: ruff und format grün, pytest und pyright erwartungsgemäß rot (Modul fehlte).

Akzeptanz: `def exclusion_check_routes` 1, PATH-Zeile 1, Schreibmethoden-Literale 0, 37 Testfunktionen (mind. 20), 840 Zeilen (mind. 250), keine U+2013/U+2014.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Test-Bug] Zwei Testfehler im RED-Stand, im GREEN-Commit korrigiert**
- Sortierung: `audit()` sortiert Tags nach Name, "kein-kai" steht vor "kein-ki"; der Test prüft jetzt per Name statt per Position
- `ToolError` verlangt `hint`; der Deploy-Test baute ihn ohne und lief in TypeError
- Keine Aufweichung: Aussagen unverändert
- **Commit:** 1155b04

**2. Plantext vs. 29-02:** "nie mode none" bei Ausfällen. `audit()` liefert für nicht geprüfte Läufe `mode=none`; der Handler gibt im JSON bei `checked=false` daher `mode: null` aus, der Text nennt nie den no_tag-Satz.

**3. Fall "Rückfallweg Kandidat a" entfällt**, weil 29-01 Kandidat b gewählt hat (im Plan so vorgesehen).

**4. Deploy-Test:** Der Guard selbst ruft `exapp_settings`, eine fehlende Variable endet dort schon mit 401. Der Test ersetzt deshalb `_guard` und `config.exapp_settings` per monkeypatch, um den Zweig im Handler zu erreichen.

**5. requirements mark-complete ausgelassen:** OPS-01 ist erst mit Verdrahtung (29-05) und Live-Beweis (29-06) erfüllt.

## Hinweise für 29-05

- `exclusion_check_routes(env)` in entry_exapp einhängen, occ-Kommando mit Optionen `admin` (optional, Wert) und `json` (mode none) registrieren
- `docs/exclusion.md` wird von LIMIT_SENTENCE genannt, existiert noch nicht
- Die Nutzerliste liest `existing_users` immer über `shared_client`, nicht über `client_provider`

## Known Stubs

Keine.

## Self-Check: PASSED

- src/mcp_connector/exapp/exclusion_check.py und tests/unit/test_exapp_exclusion_check.py vorhanden
- Commits 4b2507c, 1155b04 vorhanden
