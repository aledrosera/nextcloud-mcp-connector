---
phase: 29-pr-fkommando-und-doku
plan: 03
subsystem: exclusion
tags: [systemtags, webdav, ocs, propfind, admin-proof, tdd]

requires:
  - phase: 29-pr-fkommando-und-doku
    provides: Messbefunde und ENTSCHEID admin-nachweis=b aus 29-01 (M1b, M2, M2b, M3)
provides:
  - list_tag_details (PROPFIND Depth 1, Zugriffs-Flags, oc:groups nur auf Wunsch, Propstat-Status)
  - count_tag_objects (PROPFIND Depth 0 auf nc:object-ids, nur Zahl)
  - confirm_admin (GET cloud/groups/admin/users, True/False/None)
  - Datentypen TagDetail, TagDetailListing, ObjectCount
affects: [29-04, 29-05, 29-06]

tech-stack:
  added: []
  patterns:
    - "Eigener Multi-Status-Durchlauf über xml.parse_root, wenn der Propstat-Status Teil der Antwort ist"
    - "Zählung per sum() beim Durchlauf, keine Id-Sammlung, Ergebnis-Typ ohne Id-Feld"

key-files:
  created:
    - tests/unit/test_systemtags_details.py
  modified:
    - src/mcp_connector/nextcloud/clients/systemtags.py
    - tests/contract/test_no_destructive_calls.py
    - vulture_whitelist.py

key-decisions:
  - "Nur Kandidat b gebaut: confirm_admin True nur bei HTTP 200 + OCS 200, False nur bei HTTP 403 + OCS 403, sonst None (auch Timeout und Widerspruch HTTP/OCS)"
  - "Zählung über innere nc:object-ids mit nc:type=files (gemessen), nicht nc:object-id wie im Plantext"
  - "oc:groups wird am Pipe getrennt (SystemTagPlugin), leer ergibt ()"
  - "Unlesbarer Körper oder DTD: ToolError aus xml.parse_root, wie im restlichen Modul, statt ValueError"

requirements-completed: []

duration: 25min
completed: 2026-10-01
---

# Phase 29 Plan 03: Lesende Client-Funktionen für exclusion:check Summary

**list_tag_details, count_tag_objects und confirm_admin als policy-freie Lesezugriffe in systemtags.py, gegen die wörtlichen nc35-Antworten aus 29-01 getestet; Admin-Nachweis über cloud/groups/admin/users (200/403)**

## Performance

- **Duration:** ca. 25 min
- **Completed:** 2026-10-01
- **Tasks:** 2/2
- **Files:** 1 erstellt, 3 geändert

## Accomplishments

- Vertrag aus dem interfaces-Block exakt umgesetzt (TagDetail, TagDetailListing, ObjectCount, drei async-Funktionen)
- Eigener lxml-Durchlauf liest je Propstat den Status (`HTTP/1.1 403 Forbidden` -> 403); xml.parse_multistatus bleibt unangetastet
- oc:groups nur mit `with_groups=True` im Body; Nicht-207 (gemessen: 403 der ganzen Antwort bei Nicht-Admin) ergibt leere Liste mit Status
- Zählung: Depth 0, nur `nc:object-ids`, Summe der inneren Einträge vom Typ files; M3-Fixture ergibt 2; Id-Prüfung vor jedem Request
- confirm_admin über `ocs.ocs_get` (OCS-Header, Auth je Request); die Mitgliederliste der Admin-Gruppe verlässt die Funktion nie
- Docstrings nennen: policy-frei, nur lesend, warum nicht nc:files-assigned (P4), warum kein REPORT, ENTSCHEID samt Messdatum
- 36 Testfälle in tests/unit/test_systemtags_details.py (517 Zeilen), Methoden-Gates für beide Tasks

## Task Commits

1. **Task 1 RED** - `fa7b191` (test)
2. **Task 1 GREEN** - `b08e44c` (feat)
3. **Task 2 RED** - `8f0957d` (test)
4. **Task 2 GREEN** - `2f7b9e3` (feat)

REFACTOR nicht nötig.

## Gates

ruff check, ruff format --check, pyright latest (0 Fehler), vulture (src scripts vulture_whitelist.py), pytest tests/unit tests/contract (5187 passed, 33 skipped): alle grün vor den GREEN-Commits. RED-Commits waren erwartungsgemäß rot (pytest), Lint und Format grün.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Vertragstest der Systemtag-Anfrageformen**
- **Found during:** Task 1, Gate pytest tests/contract
- **Issue:** `test_the_two_forms_the_systemtags_client_really_builds_stay_allowed` erlaubt nur Listing und REPORT; die neue Depth-0-Form und das zweite Listing ließen ihn rot werden
- **Fix:** `ALLOWED_SYSTEMTAGS_FORMS` um `PROPFIND f'{creds.base_url}{TAGS_PATH}'` (zweites Mal) und `PROPFIND f'{creds.base_url}{TAGS_PATH}{tag_id}'` ergänzt, Kommentar nennt Plan 29-03; nur lesende Formen, die Schreibverbote bleiben unverändert
- **Commit:** b08e44c

**2. [Rule 3 - Gate] vulture-Whitelist**
- **Issue:** list_tag_details, count_tag_objects, confirm_admin haben bis 29-04 keinen Aufrufer (60 %)
- **Fix:** Abschnitt "audit reads of plan 29-03" in vulture_whitelist.py; 29-04 muss ihn leeren, sobald der Handler die Funktionen ruft
- **Commits:** b08e44c, 2f7b9e3

**3. Plantext vs. Messung:** Plan nennt `{NC}object-id`, gemessen ist das innere `{NC}object-ids` (29-01 Rule-1-Fix); gebaut nach Messung.

**4. DTD-Abweisung:** Der Plan erlaubt ValueError oder lxml-Fehler; gebaut ist der ToolError aus `xml.parse_root`, damit alle DAV-Antworten über denselben gehärteten Einstieg laufen.

**5. requirements mark-complete ausgelassen:** OPS-01 erfüllt erst der Handler (29-04) und der Live-Beweis (29-06).

## Hinweise für 29-04

- `confirm_admin` None heißt "keine Admin-Sicht", nie passed=false
- Nur nach `confirm_admin is True` darf `list_tag_details(with_groups=True)` laufen (sonst 403 der ganzen Antwort)
- `ObjectCount.files is None` bei 207 heißt: Eigenschaft fehlt oder nicht 200, für das Urteil eine unbekannte Zählung
- vulture-Abschnitt "audit reads of plan 29-03" entfernen

## Self-Check: PASSED

- src/mcp_connector/nextcloud/clients/systemtags.py und tests/unit/test_systemtags_details.py vorhanden
- Commits fa7b191, b08e44c, 8f0957d, 2f7b9e3 vorhanden
- Akzeptanz: 2x list/count-Definition, 1x confirm_admin, "REPORT" 1x (nur tagged_nodes), files-assigned nur im Docstring
