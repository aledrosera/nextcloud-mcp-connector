---
phase: 26-guard-kern
verified: 2026-09-27T02:37:08Z
status: passed
score: 8/8 must-haves verified
overrides_applied: 0
---

# Phase 26: Guard-Kern Verifikation

**Phase-Ziel:** Eine policy-freie Tag-Abfrage und ein request-gebundener Guard stehen unabhängig testbar bereit, beantworten je Tool-Aufruf mit genau einem Roundtrip, ob ein Pfad oder eine fileid ausgeschlossen ist, und unterscheiden "nichts getaggt" hart von "nicht prüfbar".
**Verifiziert:** 2026-09-27T02:37:08Z
**Status:** passed
**Re-Verifikation:** Nein, Erstverifikation

## Vorgehen

Nicht nur die SUMMARY.md-Aussagen übernommen, sondern: beide Implementierungsdateien (`exclusion.py`, `clients/systemtags.py`, relevante Ausschnitte von `clients/dav.py`) vollständig gelesen, alle vier zugesagten Commits (WR-01..04) im Git-Log verifiziert, die Testmatrix in `tests/unit/test_exclusion.py` (77 Tests), `tests/unit/test_systemtags_client.py` (26 Tests) und `tests/unit/test_dav_home_entries.py` (16 Tests) selbst ausgeführt (nicht nur die SUMMARY-Zahl geglaubt), sowie ruff, pyright und vulture selbst laufen lassen.

## Goal Achievement

### Erfolgskriterien aus ROADMAP.md

| # | Kriterium | Status | Beleg |
|---|-----------|--------|-------|
| 1 | Drei Zustände je mit Test (untagged/active/unverifiable), Capability nie befragt | VERIFIED | `TagScope` mit `state: Literal["untagged","active","unverifiable"]`, `excludes()` wirft im Zustand `unverifiable`, liefert `False` unconditional bei `untagged` (exclusion.py:156-189). Tests: `test_an_untagged_scope_excludes_nothing_and_leaves_no_trace` (json.dumps-Gleichheit geprüft), `test_an_unverifiable_scope_refuses_to_answer`, `test_the_capability_is_never_asked_even_when_it_says_systemtags_is_off` (Capabilities-Route gemockt, call_count 0, Zustand active). Kein Capability-Zugriff im Code: `grep -nE "capabilities" exclusion.py systemtags.py` liefert nichts. |
| 2 | Genau ein REPORT je Tool-Aufruf auch bei parallelen Teilaufrufen (Single-Flight), zweiter Aufruf holt neu, Name-zu-Id prozessweit gecacht, 412 löst genau einmal neu auf | VERIFIED | `ExclusionGuard.scope()` mit Lock im Konstruktor + Re-Check unter Lock (exclusion.py:305-351). Test `test_twenty_concurrent_scope_calls_cost_one_listing_and_one_report`: 20 parallele `guard.scope()`-Aufrufe ergeben `report.call_count == 1`, `listing.call_count == 1`, alle Ergebnisse `is` dasselbe Objekt. `test_a_second_tool_call_fetches_the_set_anew_from_the_warm_name_cache`: zweite Guard-Instanz → REPORT 2, PROPFIND 1. 412-Automat (`_flight`) mit sechs Varianten getestet (Tag weg, neue Id, zweimal 412 warm/kalt, gemischter Status), inkl. `test_a_412_twice_with_a_warm_cache_is_unverifiable` und `test_a_412_twice_with_a_cold_cache_lists_exactly_once_more`. |
| 3 | Subtree-Segmentregel (/A/kein deckt /A/kein/x, nicht /A/keine); getaggter Vorfahr oberhalb NC_MCP_FILES_ROOT wirkt | VERIFIED | `dav.within()` ist die einzige Schreibweise der Segmentregel (`grep -c 'startswith(root + "/")' dav.py` = 1), `exclusion.ancestors()` per parametrisiertem Äquivalenztest gegen `dav.within` bewiesen (`test_ancestors_draws_the_same_boundary_as_the_segment_rule`, 18 Fallkombinationen inkl. /A/kein gegen /A/keine). `home_entries()` filtert nicht durch die Sandbox (kein `in_files_root`-Aufruf); Test `test_a_tagged_ancestor_above_the_sandbox_takes_effect`: NC_MCP_FILES_ROOT=/Shared/KI, getaggter Vorfahr /Shared deckt /Shared/KI/doc.md. |
| 4 | Alle kein-ki-Varianten vereinigt (drei Schreibweisen unterschiedlicher Sichtbarkeit) | VERIFIED | `test_spelling_variants_cost_one_report_each_and_are_united`: alice sieht 64 "kein-ki", 65 "kein-ki" (Duplikat, wird nicht separat abgefragt), 67 "Kein-KI"; unsichtbare 63 "KEIN-KI" fehlt in ihrer Liste. Ergebnis: genau 2 REPORTs (64, 67), Vereinigung der Pfade/fileids. Admin sieht zusätzlich 63 → 3 REPORTs. `exclude_tag_ids()` gruppiert nach exaktem Namen, niedrigste Id je Schreibweise. |

**Score:** 4/4 Erfolgskriterien verifiziert (ROADMAP), zusätzlich alle PLAN-Truths (siehe unten) verifiziert.

### Observable Truths (PLAN-Frontmatter, 26-01 und 26-02)

| # | Truth | Status | Beleg |
|---|-------|--------|-------|
| 1 | Segmentregel steht genau einmal im Code, von `in_files_root`/`safe_path` genutzt | VERIFIED | `dav.py:506-512` (`within`), `in_files_root` (Z.515-517) ruft `within`, `safe_path` (Z.120) ruft `within(requested, root)`. |
| 2 | REPORT geht immer an die Home-Wurzel, trägt genau eine oc:systemtag-Regel | VERIFIED | `systemtags.home_url()` + `filter_files_body()` (ein `oc:systemtag`-Element je Body, Signatur nimmt eine Id, kein Sequenztyp). Test zählt das Element. |
| 3 | Getaggter Knoten oberhalb NC_MCP_FILES_ROOT bleibt in der REPORT-Auswertung erhalten | VERIFIED | `home_entries()` ruft nie `in_files_root`; Sandbox-Test liefert `/Shared` bei gesetzter Root, `parse_entries` liefert für denselben Body `[]` (Kontrastbeweis). |
| 4 | Nicht abbildbarer href kommt als `None` an, verschwindet nicht still | VERIFIED | `home_entries()`: kein `continue`, jeder `d:response` erscheint; Test mit fremdem Präfix: Ergebnislänge == Anzahl d:response. `_active()` in exclusion.py macht aus jedem `path=None` `unverifiable("foreign_href")`, nie eine leere Menge. |
| 5 | Client liefert Ausgänge als Werte, wirft nie ToolError aus eigener Statusprüfung, befragt nie die Capability | VERIFIED | `TagListing`/`TaggedSet` als frozen Dataclasses; Statuscodes außer 207 werden als Wert zurückgegeben; kein Capability-Bezug im Modul. |
| 6 | Kein-kein-ki ergibt untagged: kein REPORT, excludes überall False, Beispielliste json.dumps-gleich, nie gecacht | VERIFIED | `_fresh_ids` liefert `UNTAGGED` wenn `exclude_tag_ids` leer ist, ohne `_store_ids`-Aufruf. Test `test_a_listing_without_the_tag_is_untagged_sends_no_report_and_caches_nothing` und `test_an_untagged_scope_excludes_nothing_and_leaves_no_trace`. |
| 7 | Liste mit kein-ki und alle REPORTs 207 ergibt active, Capability nie angefragt | VERIFIED | `test_a_tagged_folder_and_file_make_the_scope_active`, `test_the_capability_is_never_asked_even_when_it_says_systemtags_is_off`. |
| 8 | REPORT 500/401/403/3xx, Netzfehler, Timeout, unparsebarer Body, nicht abbildbarer href, Liste nicht 207, zweiter 412 → unverifiable; excludes wirft ValueError | VERIFIED | Elf einzelne Testfälle für die jeweiligen Grundcodes (`status`, `unreachable`, `timeout`, `unparsable`, `foreign_href`, `stale_twice`), alle in `test_exclusion.py` Zeilen 390-712 nachvollzogen und ausgeführt; `excludes()` wirft `ValueError` im Zustand `unverifiable` (getestet). |
| 9 | 20 parallele scope()-Aufrufe kosten genau ein REPORT, teilen dasselbe Zustandsobjekt; zweite Guard-Instanz holt neu; nur Name-zu-Id prozessweit gecacht; 412 löst genau einmal neu auf | VERIFIED | Wie Erfolgskriterium 2 oben. |
| 10 | Subtree-Segmentregel, getaggter Vorfahr oberhalb Root wirkt | VERIFIED | Wie Erfolgskriterium 3 oben. |
| 11 | Alle kein-ki-Varianten vereinigt | VERIFIED | Wie Erfolgskriterium 4 oben. |

### Nach dem Code-Review behobene Warnungen (selbst nachvollzogen, nicht nur SUMMARY geglaubt)

| ID | Befund | Fix-Commit im Git-Log gefunden | Code-Stelle geprüft | Test dazu ausgeführt |
|----|--------|----------------------------------|----------------------|------------------------|
| WR-01 | `list_tags` überspringt Einträge ohne oc:id still (Fail-open) | f80f42b ✓ | `systemtags.py:117-145`: Collection wird am href erkannt, jede andere Response ohne Id wirft `ValueError` | `test_list_tags_refuses_a_tag_entry_without_an_id`, `test_a_listing_entry_without_an_id_is_unverifiable` beide grün |
| WR-02 | `ExclusionGuard` bindet Scope nicht an (base_url, user) | b3bd94b ✓ | `exclusion.py:322-339`: `_key` in `__slots__`, Identitätsprüfung vor Fastpath, kein await dazwischen | `test_a_guard_refuses_a_second_identity_instead_of_serving_a_foreign_scope` grün |
| WR-03 | `excludes` erlaubt Fehlbedienung still (beide Argumente None, relativer Pfad) | 43c3b21 ✓ | `exclusion.py:183-186`: beide Prüfungen vor dem Match | `test_an_active_scope_refuses_to_be_asked_about_nothing`, `test_an_active_scope_refuses_a_relative_path` grün |
| WR-04 | Counter-Proof des Gate-Tests tautologisch | 4e0f43e ✓ | `test_no_destructive_calls.py`: Beweiszeile läuft jetzt durch `_violations` | Contract-Suite (40 Tests) grün |

Alle vier Fix-Commits existieren im Git-Log (`git log --oneline -1 <hash>` erfolgreich für alle vier), nicht nur in der REVIEW.md behauptet.

### Required Artifacts

| Artifact | Erwartet | Status | Details |
|----------|----------|--------|---------|
| `src/mcp_connector/nextcloud/clients/systemtags.py` | Policy-freier Client, `list_tags`, `tagged_nodes` | VERIFIED | 177 Zeilen, substantiell, `async def tagged_nodes` gefunden, kein `capabilities`-Bezug |
| `src/mcp_connector/nextcloud/clients/dav.py` (within, home_entries) | Segmentregel + ungefilterte href-Normalisierung | VERIFIED | `within` einmal, `home_entries` ohne Sandbox-Drop, bestehende Funktionen (`in_files_root`, `safe_path`, `parse_entries`) unverändert im Verhalten (Regressionstests grün) |
| `src/mcp_connector/nextcloud/exclusion.py` | TagScope, ExclusionGuard, load_scope, Cache | VERIFIED | 351 Zeilen, `class ExclusionGuard` gefunden, alle geforderten Namen vorhanden |
| `tests/unit/test_systemtags_client.py` | respx-Tests | VERIFIED | 26 Tests, alle grün, `method="REPORT"` gefunden |
| `tests/unit/test_dav_home_entries.py` | within/home_entries-Tests | VERIFIED | 16 Tests, alle grün |
| `tests/unit/test_exclusion.py` | Testmatrix zu allen vier Erfolgskriterien | VERIFIED | 77 Tests, 946 Zeilen, `call_count` mehrfach genutzt |
| `tests/contract/test_no_destructive_calls.py` | Dritter dokumentierter Modul-Cache | VERIFIED | `("nextcloud/exclusion.py", "_tag_ids")` gefunden, `len(ALLOWED_MODULE_STATE) == 3` |
| `.planning/phases/26-guard-kern/deferred-items.md` | Merker für Phase 27/29 | VERIFIED | 6 Punkte (a-f), "Obergrenze" und "Phase 29" mehrfach vorhanden, keine Em-Dashes (Unicode-Prüfung: 0 Treffer) |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `systemtags.py` | `dav.py` | `dav.home_entries` für REPORT-Antwort | WIRED | `tagged_nodes()` ruft `dav.home_entries(response.content, creds)`, nutzt nicht `parse_entries`/`files_url`/`_check` (grep bestätigt leer) |
| `dav.py` | `dav.within` | `in_files_root`/`safe_path` rufen `within` | WIRED | Beide Aufrufer bestätigt im Quelltext |
| `exclusion.py` | `systemtags.py` | `list_tags`/`tagged_nodes` per `asyncio.gather` | WIRED | `_fresh_ids` ruft `list_tags`, `_report_all` ruft `tagged_nodes` je Id via `asyncio.gather` |
| `exclusion.py` | `dav.within` (Äquivalenz) | `ancestors` gegen `within` | WIRED | Parametrisierter Äquivalenztest grün |
| `test_no_destructive_calls.py` | `exclusion.py` | `_tag_ids`-Eintrag | WIRED | Gate-Eintrag gefunden und Zähltest auf 3 angepasst |

Kein Werkzeug hängt am neuen Code (bewusst, Phase-Grenze): `grep -rnE "exclusion|ExclusionGuard|systemtags" src/mcp_connector/tools src/mcp_connector/nextcloud/__init__.py src/mcp_connector/deps.py` liefert nichts. Das ist laut Phasenziel korrekt (Familien-Anschluss ist Phase 27).

### Gates (selbst ausgeführt, nicht nur SUMMARY geglaubt)

| Gate | Kommando | Ergebnis |
|------|----------|----------|
| Fokus-Tests | `pytest tests/unit/test_exclusion.py tests/unit/test_systemtags_client.py tests/unit/test_dav_home_entries.py tests/contract/test_no_destructive_calls.py -q` | Exit 0, 159 Tests gesammelt und grün |
| Volle Suite | `pytest tests/unit tests/contract -q` | Exit 0 |
| ruff check | `ruff check <geänderte Dateien>` | All checks passed |
| pyright | `PYRIGHT_PYTHON_FORCE_VERSION=latest pyright <geänderte Dateien>` | 0 errors, 0 warnings |
| vulture | `vulture src scripts vulture_whitelist.py` | Kein Fund (leere Ausgabe) |
| Debt-Marker | grep TBD/FIXME/XXX/TODO/HACK/PLACEHOLDER über alle Phase-26-Dateien | Kein Treffer |

### Requirements Coverage

| Requirement | Quelle | Beschreibung (gekürzt) | Status | Beleg |
|--------------|--------|------------------------|--------|-------|
| EXCL-02 | 26-01/26-02-PLAN | Subtree-Semantik, einmal je Antwort geholt, Segmentregel, nie über Aufruf hinaus gecacht, 412 löst einmal neu auf | SATISFIED (für den in dieser Phase gebauten Kern) | Guard-Kern implementiert und getestet wie oben; volle Erfüllung inkl. Werkzeug-Anschluss ist laut Phasengrenze Phase 27 |
| EXCL-04 | 26-01/26-02-PLAN | Fail-closed mit drei Zuständen, REPORT-Ausgang statt Capability maßgeblich | SATISFIED (für den in dieser Phase gebauten Kern) | `TagScope` mit drei hart getrennten Zuständen; Zurückhalten/Meldungsform ist laut CONTEXT.md explizit Phase 27 |

Anmerkung: `.planning/REQUIREMENTS.md` führt EXCL-02/EXCL-04 weiterhin als "Pending", weil die Traceability-Tabelle den vollständigen Requirement-Abschluss über beide Phasen (26 Kern + 27 Anschluss) verlangt (Formulierung "wird ... geprueft" impliziert den Werkzeug-Pfad). Das ist konsistent mit der CONTEXT.md-Phasengrenze ("Kein Werkzeug wird in dieser Phase angefasst") und keine Lücke dieser Phase.

Keine verwaisten Requirements: EXCL-02 und EXCL-04 sind die einzigen für Phase 26 deklarierten IDs, beide in beiden PLAN-Frontmatters vorhanden.

### Anti-Patterns Found

Keine Blocker, keine Warnungen im Sinne von Anti-Pattern-Mustern (kein TODO/FIXME/TBD/HACK/PLACEHOLDER, keine leeren Handler, kein `except Exception`, keine hartcodierten leeren Werte, die durchgereicht werden). Die vier verbliebenen REVIEW-Info-Punkte (IN-01 bis IN-04) sind Härtungsvorschläge ohne Fail-open-Charakter (doppelte Prefix-Berechnung, Unquote-Reihenfolge, Doppel-Slash-Segmente, TTL-Testpatch auf globalem time-Modul) und wurden im Review bewusst nicht in dieser Runde behoben; sie blockieren das Phasenziel nicht.

### Behavioral Spot-Checks

| Verhalten | Kommando | Ergebnis | Status |
|-----------|----------|----------|--------|
| Fokus-Testmatrix läuft echt durch (nicht nur SUMMARY-Zahl) | `pytest tests/unit/test_exclusion.py ... -q` | Exit 0, 159 Tests | PASS |
| Volle Unit+Contract-Suite grün | `pytest tests/unit tests/contract -q` | Exit 0 | PASS |
| Vier Fix-Commits existieren wirklich | `git log --oneline -1 <hash>` je Commit | Alle vier gefunden | PASS |
| Gates identisch zu CI | ruff/pyright/vulture einzeln ausgeführt | Alle grün | PASS |

### Human Verification Required

Keine. Alle Wahrheiten sind über Code, Tests und Gate-Läufe programmgestützt nachvollziehbar; es gibt keine visuellen, Echtzeit- oder externen Abhängigkeiten in dieser Phase (kein Werkzeug-Anschluss, keine UI, kein Netzverkehr gegen eine echte Nextcloud-Instanz nötig).

### Gaps Summary

Keine Lücken. Alle vier ROADMAP-Erfolgskriterien, alle PLAN-Truths, alle Artefakte und Key-Links sind mit echten, selbst ausgeführten Tests und Greps belegt, nicht nur mit SUMMARY-Behauptungen. Die vier offenen REVIEW-Info-Punkte sind dokumentierte, bewusst nicht in dieser Runde behobene Härtungsvorschläge ohne Bezug zum Phasenziel und blockieren nicht.

---

_Verified: 2026-09-27T02:37:08Z_
_Verifier: Claude (gsd-verifier)_
