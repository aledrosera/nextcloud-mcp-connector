---
phase: 29-pr-fkommando-und-doku
reviewed: 2026-10-01T10:31:48Z
depth: standard
files_reviewed: 22
files_reviewed_list:
  - src/mcp_connector/nextcloud/exclusion_audit.py
  - src/mcp_connector/nextcloud/clients/systemtags.py
  - src/mcp_connector/exapp/exclusion_check.py
  - src/mcp_connector/exapp/occ.py
  - src/mcp_connector/entry_exapp.py
  - appinfo/info.xml
  - scripts/exclusion_evidence.py
  - .github/workflows/ci.yml
  - vulture_whitelist.py
  - tests/contract/test_no_destructive_calls.py
  - tests/integration/test_exclusion_check_live.py
  - tests/unit/test_docs_exclusion_truth.py
  - tests/unit/test_exapp_entry.py
  - tests/unit/test_exapp_exclusion_check.py
  - tests/unit/test_exapp_lifecycle.py
  - tests/unit/test_store_texts_frozen.py
  - tests/unit/test_systemtags_details.py
  - docs/exclusion.md
  - docs/exclusion.de.md
  - docs/exclusion.fr.md
  - README.md
  - README.de.md
findings:
  critical: 0
  warning: 5
  info: 8
  total: 13
status: issues_found
---

# Phase 29: Code Review Report

**Reviewed:** 2026-10-01T10:31:48Z
**Depth:** standard
**Files Reviewed:** 22 (plus README.fr.md, gleicher Abschnitt wie README.de.md)
**Status:** issues_found

## Summary

Geprüft: Commits der Phase 29 (`git log --grep="(29"`, plus f016f8f). PR #14 nicht im Umfang.

Gehalten hat:
- **Nur Lesen:** systemtags.py baut nur PROPFIND, plus GET auf `cloud/groups/admin/users`. Der Contract-Test pinnt die Formen als Multimenge (doppeltes Listing-Tupel ist Absicht). Kein Audit-Eintrag.
- **AppAPI-Guard:** wörtlich wie bei exchange:check: `x-origin-ip` gibt 404, ein fehlender oder falscher Header 401, keine `<url>` im Manifest. Alles getestet.
- **Admin-Spoofing:** nicht möglich. Mit `--admin=<nicht-admin>` liefert Nextcloud selbst keine unsichtbaren Tags, und der Handler filtert ohne bestätigten Admin zusätzlich auf `visible`. `oc:groups` wird nur nach `confirm_admin() is True` angefragt.
- **Ausfall ist nie "kein Tag":** Listing-Fehler, Transportfehler und ein unlesbares Multi-Status-Dokument führen zu `passed=false`. Ein unbekannter Zähler lässt `assignment_count` scheitern (fail-closed).
- **Privatsphäre:** in Text, JSON und Log keine uid, kein Pfad, keine fileid. Der Test prüft Klartext und Token.

Kein Blocker. Die Warnungen betreffen:
- irreführende Admin-Diagnose (WR-01, WR-02)
- ungefilterte Steuerzeichen aus nutzererzeugten Tag-Namen im Konsolentext (WR-03)
- einen Nachweis "ändert nichts", der schmaler ist als die Doku-Aussage (WR-04)
- einen Rohbeleg, der nach f016f8f veraltet ist (WR-05)

## Warnings

### WR-01: Benannter, aber nicht bestätigter Admin erscheint als "admin_not_named"

**File:** `src/mcp_connector/nextcloud/exclusion_audit.py:232-235`, `src/mcp_connector/exapp/exclusion_check.py:312-318`
**Issue:** `confirm_admin` liefert `None`, also "nicht entscheidbar". Danach rufen alle Pfade `audit(..., admin_checked=False)` auf, und `_identity_step` schreibt fest `not_checked (admin_not_named)`, obwohl `--admin` gesetzt war. Ablauf bei einem Tippfehler in `--admin=amdin`:
1. AppAPI kennt den Nutzer nicht und antwortet 401. `confirm_admin` gibt `None` zurück.
2. Das Listing als `amdin` antwortet ebenfalls 401, also `_stopped(...)`.
3. Die Ausgabe lautet `not_checked  the named account is an administrator (admin_not_named)` und `the tag listing could not be read: Nextcloud answered 401`.

`UNCONFIRMED_SENTENCE` erscheint nicht, weil `_report` es nur bei `result.checked` anhängt. Das JSON hat kein Feld, das "benannt, aber unbestätigt" von "nicht benannt" trennt. Monitoring und Admin lesen also "keine Option gesetzt" und suchen den Fehler am Listing statt an der uid.
**Fix:** einen eigenen Zustand durchreichen:
```python
def _identity_step(*, admin_checked: bool, admin_named: bool = False) -> AuditStep:
    if admin_checked:
        return AuditStep(STEP_ADMIN_IDENTITY, OUTCOME_PASSED)
    note = "admin_unconfirmed" if admin_named else "admin_not_named"
    return AuditStep(STEP_ADMIN_IDENTITY, OUTCOME_NOT_CHECKED, note)
```
Zusätzlich `confirm_admin` bei HTTP 401 als eigenes Ergebnis "Konto unbekannt" behandeln, mit `passed=false` und `reason`.

### WR-02: `confirm_admin` bestätigt jeden, der die Mitglieder der Gruppe admin lesen darf, nicht nur Admins

**File:** `src/mcp_connector/nextcloud/clients/systemtags.py` (`confirm_admin`, `ADMIN_USERS_PATH`), `src/mcp_connector/exapp/exclusion_check.py:308-314`
**Issue:** Der Nachweis setzt "200 auf `/cloud/groups/admin/users`" mit "ist Administrator" gleich. Gemessen (M2b) sind nur Admin und Normalnutzer. Nach Erinnerung an den Nextcloud-Quellcode lässt `GroupsController::getGroupUsers` auch Konten mit delegierten Admin-Rechten für den Bereich Users durch (`isDelegatedAdmin`). Ab NC 31/32 vergibt das die App "Administration privileges". Das ist nicht gegen den Quellcode geprüft. Folge für so ein Konto:
1. `admin_identity` zeigt `passed` ("the named account is an administrator"). Das ist falsch.
2. Das PROPFIND mit `oc:groups` bekommt 403 für das ganze Listing (M2).
3. Das Ergebnis ist `passed=false` mit "Nextcloud answered 403".

Es leakt nichts, weil der Fehler fail-closed ist. Die Diagnose zeigt aber in die falsche Richtung, und die Doku-Aussage "the account named with --admin is an administrator" stimmt dann nicht.
**Fix:** einen Delegations-Admin gegen nc35 messen, das Ergebnis als M-Block nachtragen. Falls er 200 bekommt: ein 403 auf das Listing mit Gruppen nach `proven is True` auf "Admin nicht bestätigt" abbilden statt auf "Listing nicht lesbar", oder die Mitgliedschaft prüfen (`GET /cloud/users/<uid>/groups` enthält `admin`).

### WR-03: Nutzererzeugte Tag-Namen landen ungefiltert im Konsolentext (Steuerzeichen, ANSI)

**File:** `src/mcp_connector/exapp/exclusion_check.py:459-464` (`VARIANT_WARNING`, `SIMILAR_SENTENCE`), `:479` (Gruppen)
**Issue:** Ohne `restrict_creation_to_admin` darf jedes Konto Tags anlegen. Das ist der Standard, docs/exclusion.md:36-39 sagt es selbst. `tag_skeleton` wirft alles weg, was kein Buchstabe und keine Ziffer ist. Ein Name wie `"kein\r-ki"` oder `"kein-ki\x1b[@"` zählt also als `variant`. Ein Name mit genau einem zusätzlichen Buchstaben, etwa `"keinki\x1b[F"`, zählt als `similar`. Der Name geht roh in den Text, den AppAPI auf das Terminal des Admins schreibt. Folge: Mit einigen solchen Tags überschreibt ein Normalnutzer per Cursor-zurück plus CR plus Leerzeichen Zeilen wie `failed ... tag_exists` oder `Items tagged '...' are NOT excluded`. Der Admin sieht eine scheinbar saubere Ausgabe. Das JSON ist sicher, weil `json.dumps` escaped. Nicht gemessen ist, ob Nextcloud Steuerzeichen in Tag-Namen ablehnt.
**Fix:** Namen vor dem Einsetzen in Text sichtbar machen:
```python
def _shown(name: str) -> str:
    return "".join(
        ch if not unicodedata.category(ch).startswith("C") else f"\\u{ord(ch):04x}"
        for ch in name
    )
# VARIANT_WARNING.format(name=_shown(tag.name), ...), SIMILAR_SENTENCE.format(name=_shown(tag.name))
```
Dazu ein Unit-Test mit `"kein\r-ki"` und `"\x1b"` im Namen.

### WR-04: "Ändert nichts" ist nur für die Tag-Tabellen belegt, impersoniert werden aber bis zu fünf echte Konten

**File:** `docs/exclusion.md:135-139` (DE :138 ff., FR :142 ff.), `src/mcp_connector/exapp/exclusion_check.py:355-373`, `tests/integration/test_exclusion_check_live.py:61-70`
**Issue:** Doku und occ-Beschreibung sagen "only reads, changes nothing". Der Live-Diff deckt aber nur `systemtag`, `systemtag_object_mapping`, `systemtag_group` und die appconfig-Zeilen von `systemtags` ab. Ohne `--admin` schickt der Handler PROPFINDs unter der Identität der ersten fünf Konten (sortiert), darunter möglicherweise deaktivierte oder nie angemeldete. Ob eine AppAPI-Impersonation über DAV für ein nie angemeldetes Konto `setupFS` auslöst (Home-Ordner, `oc_storages`/`oc_filecache`-Zeilen) oder `oc_preferences` (lastSeen/lastLogin) berührt, ist weder gemessen noch im Diff. Die Testtopologie hat nur bereits benutzte Konten. Die Aussage geht also weiter als der Beleg.
**Fix:** `oc_preferences`, `oc_storages` und `oc_filecache` (Zeilenzahl plus Hash) in `PHP_DUMP_TABLES` aufnehmen und einen Fall mit einem frisch angelegten, nie angemeldeten Konto als erstem sortiertem Konto ergänzen. Alternativ die Doku auf "ändert keine Tag-Daten und keine Zuordnungen" eingrenzen.

### WR-05: Rohbeleg und Live-Test nach f016f8f nicht neu gelaufen

**File:** `.planning/phases/29-pr-fkommando-und-doku/raw/29-06-live-beweis.txt:67,212`, `tests/integration/test_exclusion_check_live.py:388-389`
**Issue:** Der Rohbeleg stammt von HEAD 2a3529b. f016f8f änderte danach `NO_VISIBLE_TAG_SENTENCE` und fügte im Live-Test eine neue Reihenfolge-Assertion hinzu (`to also check invisible tags` vor `tag:add`). Die neue Assertion lief nie gegen eine echte Instanz, und der Rohbeleg zeigt einen Wortlaut, den der Code nicht mehr ausgibt (`... Create it with: php occ tag:add kein-ki public`). docs/exclusion.md:12-16 sagt, jede Ausgabe sei so gemessen. Der CI-Schritt läuft erst nach dem nächsten Push (A-28-09-Muster), bis dahin ist die Abweichung unbelegt.
**Fix:** `test_exclusion_check_live.py` gegen nc35 erneut fahren, den Rohbeleg ersetzen oder anhängen (mit HEAD ab f016f8f) und in der SUMMARY vermerken.

## Info

### IN-01: Uneinheitliches JSON-Schema über die Fehlerpfade

**File:** `src/mcp_connector/exapp/exclusion_check.py:270-272, 400-402`
**Issue:** `_refusal` (ungültige uid, Deploy-Umgebung) und der Ausnahme-Pfad liefern nur `checked/passed/reason` bzw. `error`. Es fehlen `steps`, `mode`, `admin_checked`, `tags` und `limit`. Ein Monitoring, das `doc["mode"]` liest, bekommt einen KeyError statt `null`.
**Fix:** Beide Pfade über `_machine_readable(_stopped(...))` bauen oder fehlende Schlüssel mit `None` füllen.

### IN-02: Warnsatz für ein unsichtbares exaktes Tag widerspricht der Doku

**File:** `src/mcp_connector/exapp/exclusion_check.py:441-445, 459-461`
**Issue:** Für ein unsichtbares `kein-ki` druckt der Handler `Items tagged 'kein-ki' are NOT excluded: n` (Rohbeleg Fall D). docs/exclusion.md:226-228 sagt dagegen richtig, dass es in Admin-Sitzungen filtert.
**Fix:** Für unsichtbare exakte Tags einen eigenen Satz verwenden ("NOT excluded for non-administrators").

### IN-03: Doku "liest wie ein gewöhnliches Konto" und info.xml "impersonating an administrator" sind ungenau

**File:** `docs/exclusion.md:159`, `docs/exclusion.de.md:165`, `docs/exclusion.fr.md:169`, `appinfo/info.xml:263`
**Issue:** Ohne `--admin` liest der Handler als erstes sortiertes Konto, auf vielen Instanzen also `admin`. Er filtert danach nur auf sichtbare Tags. Der Kommentar in info.xml behauptet, die Route lese immer als Admin.
**Fix:** "liest als das erste Konto der Nutzerliste und wertet nur sichtbare Tags aus"; in info.xml "while impersonating an account of the instance (an administrator with --admin)".

### IN-04: Hinweis "Run again with --admin" erscheint auch, wenn `--admin` gesetzt war

**File:** `src/mcp_connector/exapp/exclusion_check.py:157-161, 435-436`
**Issue:** Im Pfad "unbestätigter Admin" ohne sichtbares Tag stehen `NO_VISIBLE_TAG_SENTENCE` ("Run again with --admin=<uid>") und `UNCONFIRMED_SENTENCE` nebeneinander. Der Test zu f016f8f pinnt genau das.
**Fix:** Bei `unconfirmed` eine Variante ohne "Run again" verwenden.

### IN-05: Doku-Wahrheitstest pinnt keine zitierten Werte gegen den Code

**File:** `tests/unit/test_docs_exclusion_truth.py:253-266`
**Issue:** Der Test geht nur über Kommandoname, Optionen, `passed` und `kein-ki`. Folgende Stellen in der Doku hängen an keiner Konstante:
- `TAG_BUDGET` 15 s (docs/exclusion.md:297)
- die sieben Schritt-IDs (:143-149)
- der Wortlaut von `LIMIT_SENTENCE` und `STEP_NAMES` in den Ausgabeblöcken (:173-203)

Eine Wortlautänderung wie f016f8f bleibt so unbemerkt.
**Fix:** `TAG_BUDGET`, `STEPS` und `STEP_NAMES.values()` importieren und ihr Vorkommen auf allen drei Seiten prüfen.

### IN-06: `test_the_client_provider_is_the_one_used` beweist nicht, dass der Client benutzt wurde

**File:** `tests/unit/test_exapp_exclusion_check.py:825-843`
**Issue:** Der Test prüft nur, dass der Provider aufgerufen wurde (`assert provided`), nicht dass die Requests über diesen Client liefen. Der Client wird außerdem nie geschlossen.
**Fix:** Einen `httpx.AsyncClient(transport=MockTransport(...))` übergeben und die Requests am Transport zählen; danach `aclose()` aufrufen.

### IN-07: Messskript stellt den Vorzustand nicht wieder her

**File:** `scripts/exclusion_evidence.py:529-541, 816-830, 918-922`
**Issue:**
- `m1c` deaktiviert `user2` und aktiviert ihn danach immer wieder, auch wenn er vorher schon deaktiviert war.
- Die Bereinigung löscht `restrict_creation_to_admin`, auch wenn der Schlüssel vorher gesetzt war.
- `preflight` prüft nur Tags und Gruppen.

Auf einer Wegwerf-Topologie ist das harmlos. Auf einer gepflegten Instanz ändert es den Zustand.
**Fix:** Vorher `user:info` und `config:app:get` lesen und genau diesen Zustand zurückschreiben, oder abbrechen, wenn der Schlüssel schon existiert.

### IN-08: Admin-Passwort im argv von curl

**File:** `scripts/exclusion_evidence.py:314-325` (Aufrufer m8)
**Issue:** Der Beleg schreibt das Passwort korrekt als `<passwort>` auf, der echte `curl -u admin:<pw>` steht aber für die Laufzeit in der Prozessliste. Das betrifft nur die Testtopologie.
**Fix:** `curl --netrc-file` oder `-u` per `--config -` über stdin.

---

_Reviewed: 2026-10-01T10:31:48Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
