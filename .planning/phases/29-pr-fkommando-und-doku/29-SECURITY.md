---
phase: 29
slug: pr-fkommando-und-doku
status: open
threats_open: 1
asvs_level: 1
block_on: high
register_authored_at_plan_time: true
created: 2026-10-01
audited_head: 2d4cf5d
---

# Phase 29: Security

> Sicherheitsvertrag je Phase: Bedrohungsregister, akzeptierte Risiken, Prüfspur.
> Register aus den `<threat_model>`-Blöcken von 29-01 bis 29-09 (31 Einträge, zur Planzeit verfasst).
> Geprüft gegen HEAD 2d4cf5d (nach allen 13 Review-Fixes). Implementierungsdateien unverändert.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Messskript -> nc35 (occ, WebDAV, OCS) | 29-01 schreibt Tags, Gruppen, Dateien, einen Konfigschlüssel auf die Testinstanz | Testdaten, Admin-/Testkonto-Passwörter |
| Messskript -> ExApp-Container | Programme laufen mit APP_SECRET der ExApp, dürfen jedes Konto impersonieren | APP_SECRET (hoch) |
| Tag-Namen der Instanz -> Klassifikation/Konsole | Tag-Namen sind ohne restrict_creation_to_admin von jedem Konto frei wählbar | nutzerkontrollierter Text |
| Nextcloud-Antwort -> XML-Parser | Multi-Status-XML wird geparst | nicht vertrauenswürdiges XML |
| AppAPI (occ) -> ExApp-Handler `/exclusion-check` | Optionen kommen als JSON-Body, `--admin` ist fremde Eingabe | uid, Flags |
| ExApp -> Nextcloud unter Impersonation | Lesen als genannter Admin bzw. als erstes lesendes Konto | Tag-Metadaten, Zuordnungszahlen |
| PHP-Proxy -> ExApp | deklarierte `<url>` wären von außen erreichbar | Orakel auf Tag-/Gruppennamen |
| Live-Test -> nc35/CI-Instanz | legt Tags, Gruppen, Dateien und ein eigenes Admin-Konto an | Zufallspasswort |
| Doku/README/Store -> Öffentlichkeit | Betreiber verlassen sich auf die Aussagen zum Schutzumfang | öffentlicher Text |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-29-01 | Tampering | Testinstanz-Zustand nach Messung | mitigate | `scripts/exclusion_evidence.py`: `preflight()` Z. 983-1008 (Tags, Gruppen, Config-Schlüssel, deaktiviertes Konto; IN-07), Abbruch `return 2` vor jeder Änderung Z. 1050-1053; `try/finally cleanup()` Z. 1057-1065; `cleanup()` Z. 928-975 mit Rückleseprobe und `CLEANUP`-Zeile je Objekt, `config:app:delete` + `config:app:get` | closed |
| T-29-02 | Information Disclosure | APP_SECRET/Passwörter im Rohprotokoll | mitigate | `EXAPP_DAV_PROGRAM` Z. 97-125 druckt nur `status_code` und `text`, nie Header; curl-Zugangsdaten per `--config -` über stdin (Z. 315-343, IN-08), Protokoll zeigt `<passwort>`; Gegenprobe: kein Wert aus `.env.nc35` (PASSWORD/SECRET) und nicht `NEXTCLOUD_ADMIN_PASSWORD` aus compose.nc35.yml in `raw/*` oder `docs/exclusion*.md`; kein `AUTHORIZATION-APP-API` in `raw/*` | closed |
| T-29-03 | Elevation of Privilege | Impersonation als admin im Messskript | accept | siehe Accepted Risks AR-29-01; Gegenprobe: alle `exapp(...)`-Aufrufe sind PROPFIND (Z. 483, 499) oder GET (Z. 531, 604) | closed |
| T-29-04 | Denial of Service | Lokale Maschine mit wenig RAM | mitigate | Nur als Arbeitsanweisung in 29-01-PLAN.md Task 2 (Z. 127); kein Beleg in 29-01-SUMMARY.md oder raw/29-01-messungen.txt, dass die RAM-Prüfung vor den Läufen stattfand | open |
| T-29-05 | Tampering | Grünes Fehlurteil bei unlesbarer Liste | mitigate | `exclusion_audit.py` Z. 286 (`if not listing_ok`), Z. 210 (`assigned is None` -> failed); Tests `test_unreadable_listing_is_never_no_tag` (Z. 264), `test_uncounted_exact_tag_fails` (Z. 308) | closed |
| T-29-06 | Information Disclosure | Objekt-Ids/Pfade im Ergebnis | mitigate | `TagFacts` Z. 122-132 nur id (Tag-Id), Name, Flags, gids, Zahl; `test_tag_facts_have_no_field_for_an_object_id` (Z. 344) über `dataclasses.fields` | closed |
| T-29-07 | Spoofing | Homoglyphen-Tag gilt nicht als Variante | accept | siehe AR-29-02; Modul-Docstring `exclusion_audit.py` Z. 21-22 benennt die Grenze | closed |
| T-29-08 | Tampering | XML-Parser (XXE, Entity-Expansion) | mitigate | `systemtags.py` parst nur über `xml.parse_root`/`xml.parse_multistatus` (Z. 198, 269); `clients/xml.py` Z. 31-32 `resolve_entities=False`, `no_network=True`; `test_details_reject_a_document_type_declaration` (Z. 293) | closed |
| T-29-09 | Elevation of Privilege | Schreibende Methode unter Admin-Impersonation | mitigate | neue Funktionen `list_tag_details` (Z. 355), `count_tag_objects` (Z. 391) PROPFIND, `confirm_admin` GET über `ocs.ocs_get` (Z. 470); `test_details_and_count_only_ever_send_propfind` (Z. 421), `test_the_admin_proof_sends_one_get_and_nothing_else` (Z. 552); Contract `ALLOWED_SYSTEMTAGS_FORMS` (test_no_destructive_calls.py Z. 235-240; REPORT stammt aus Phase 27/28 und wird vom Handler nicht aufgerufen) | closed |
| T-29-10 | Information Disclosure | Objekt-Ids der Zuordnungen | mitigate | `count_tag_objects` zählt per `sum(1 for ...)` ohne Sammeln (Z. 403-407); `ObjectCount` nur `status`, `files` (Z. 135-143); `test_an_object_count_has_no_field_that_could_carry_an_id` (Z. 409) | closed |
| T-29-11 | Spoofing | Admin-Fehlurteil | mitigate | `confirm_admin` Z. 444-482: True nur bei HTTP 200 + OCS 200 und uid selbst in `data.users` (WR-02, 5da76f3), False bei 403/403, sonst None; Tests Z. 441-552 inkl. `test_a_200_without_the_account_in_the_member_list_denies`, Timeout, Widerspruch | closed |
| T-29-12 | Information Disclosure | Orakel über den PHP-Proxy | mitigate | `exclusion_check._guard` Z. 591-602 (`x-origin-ip` -> 404, `require_appapi` -> 401); kein `<url>` mit `exclusion-check` in appinfo/info.xml; Tests Z. 292, 299, 305 | closed |
| T-29-13 | Elevation of Privilege | Missbrauch der Admin-Impersonation | mitigate | `_run` Z. 326-332: `confirm_admin` vor jedem Urteil, `oc:groups` nur bei `proven is True`, ohne Bestätigung Filter auf `visible` (Z. 349); Methoden-Gate in Fixture `router` (test_exapp_exclusion_check.py Z. 215-224) für jeden Test; erreichbar nur über occ (T-29-12) | closed |
| T-29-14 | Information Disclosure | Konten/Pfade/Ids in Ausgabe oder Log | mitigate | `_machine_readable` ohne id (Z. 549-586); Log nur passed/mode/assigned/admin_checked (Z. 278-284) bzw. Ausnahmetyp (Z. 288); `test_no_account_id_path_or_header_value_reaches_text_json_or_log` (Z. 932, inkl. base64-Token Z. 962), `test_one_log_line_per_run_without_names` (Z. 968) | closed |
| T-29-15 | Tampering | `--admin` als fremde Eingabe | mitigate | `_given` strip (Z. 654-658); `_acceptable_uid` Länge <= `MAX_UID_LENGTH` 64, keine Kategorie C (Z. 355-359), vor jedem Request (Z. 305-306); `MAX_BODY_BYTES` 4096 mit `bounded_body` (Z. 116, 661-694); uid nur im Impersonations-Token, URLs `TAGS_PATH`/`ADMIN_USERS_PATH` konstant; Tests Z. 698, 711, 338, 347 | closed |
| T-29-16 | Repudiation | Grünes Fehlurteil bei Ausfall | mitigate | `_read_listing` Z. 362-374 (HTTPError, ToolError, Nicht-207 -> None + Grund), `_first_reader` Z. 377-395, Ausnahmepfad Z. 286-293; JSON `mode` = None bei `checked=false` (Z. 564); Tests Z. 785, 800, 826, 849, 861, 881; Live-Beleg Fall H `mode:null` | closed |
| T-29-17 | Information Disclosure | Versehentlich deklarierte Route | mitigate | info.xml Z. 260-262 nur Kommentar; `test_the_path_is_declared_in_no_route_of_the_manifest` | closed |
| T-29-18 | Denial of Service | Registrierung scheitert an Beschreibungslänge | mitigate | `APPAPI_DESCRIPTION_LENGTH = 255` (occ.py Z. 110); test_exapp_lifecycle.py Z. 576-578 (Kommando + Optionen), test_exapp_purge.py Z. 1092 über alle `command_schemes()` | closed |
| T-29-19 | Tampering | Store-Text unbeabsichtigt geändert | mitigate | Eigene Gegenprobe (awk, nicht das Pin-Muster): SHA-256 aller summary/description-Blöcke ca157b4 = HEAD = 2fa82aa8...; `git diff ca157b4 HEAD -- appinfo/info.xml` nur 11 Einfügungen im XML-Kommentar | closed |
| T-29-20 | Tampering | Restzustand nach Live-Test | mitigate | Fixture `env` bricht bei vorhandener kein-ki-Schreibweise ab (test_exclusion_check_live.py Z. 305-311); `run_case` mit `finally: finish(cleanup)` und `cleanup_ok`-Assert (Z. 275-281, 380-386); ci.yml Schritt Z. 215 nach dem Kanarien-Schritt Z. 196 | closed |
| T-29-21 | Repudiation | "ändert nichts" nur behauptet | mitigate | `PHP_DUMP_TABLES` mit Zeilenzahl + SHA-256 über 8 Tabellen inkl. preferences/storages/mounts/filecache (Z. 72-102, WR-04); `checked()` dumpt vor/nach Text und JSON (Z. 207-216), `compare()` mit `unified_diff` und `assert not unequal` (Z. 163-183); Rohbeleg raw/29-REVIEW-FIX-live-beweis.txt 160x `gleich=ja`, 0x `gleich=nein` | closed |
| T-29-22 | Elevation of Privilege | Test-Admin bleibt zurück, Passwort im Protokoll | mitigate | `secrets.token_urlsafe(24)` (Z. 329), `-e OC_PASS` ohne Wert + Prozessumgebung, `--password-from-env` (Z. 330-350, nie im argv); `finally: user:delete` + `account_gone` per `user:info` als CLEANUP-Zeile mit Assert (Z. 356-360); Rohbeleg `CLEANUP admin-konto: entfernt`, kein `Chk-`-Passwort in raw/* | closed |
| T-29-23 | Information Disclosure | Datei-/Kontodaten in Kommandoausgabe | mitigate | `checked()` prüft je Fall alle `forbidden_values` (uids, Dateiname, occ-Pfad, fileid) in Text und JSON per `cw.check(..., "T-29-23", ...)`, das assertet (canary_world.py Z. 136-140) | closed |
| T-29-24 | Repudiation | Doku verspricht mehr Schutz als gemessen | mitigate | test_docs_exclusion_truth.py: Anker (Z. 221), Befundlink je Grenze (Z. 230, 242), Link-Auflösung (Z. 253), zitierte Ausgabe wörtlich im letzten Live-Lauf (Z. 350) | closed |
| T-29-25 | Information Disclosure | Echte Daten der Testinstanz in Beispielausgaben | mitigate | Beispielausgaben mit `--admin=<uid>`, curl mit `admin:<app-password>` und `cloud.example.com` (docs/exclusion.md Z. 105, 113); keine `chkadm*`-uid, kein Testpasswort in den drei Seiten. Hinweis: Einrichtungsbefehle nennen das Wegwerf-Testkonto `alice` (M8) als Beispiel, kein Geheimnis | closed |
| T-29-26 | Tampering | Doku driftet vom Code | mitigate | Test importiert `OCC_EXCLUSION_CHECK_COMMAND_NAME`, `ADMIN_OPTION`, `JSON_OPTION`, `STEPS`, `TAG_BUDGET`, `EXCLUDE_TAG` (Z. 50-58), prüft sie auf allen drei Seiten (Z. 271, 306) | closed |
| T-29-27 | Repudiation | README überzeichnet den Schutz | mitigate | `test_the_section_names_the_tag_and_the_share_boundary` je Sprache (Z. 444) | closed |
| T-29-28 | Tampering | Änderungen außerhalb des README-Abschnitts | mitigate | `git diff --numstat ca157b4 HEAD`: README.md, README.de.md, README.fr.md je 7 eingefügt, 0 gelöscht | closed |
| T-29-29 | Tampering | Store-Texte ändern sich vor Release | mitigate | tests/unit/test_store_texts_frozen.py `EXPECTED_SHA256`/`EXPECTED_COUNT` (Z. 35-37, 54-69), läuft im CI-Job `unit` (`pytest tests/unit tests/contract`, ci.yml Z. 36); Rohbeleg raw/29-09-store-diff.txt; lokal grün | closed |
| T-29-30 | Repudiation | Doku-Wortlaut ohne Owner-Freigabe veröffentlicht | mitigate | 29-09-SUMMARY.md "Owner-Abnahme": "approved" 2026-10-01 für a9ec7ad; kein Push: HEAD in keinem Remote-Branch, 56 Commits vor origin/main. Siehe Warnung W-29-01 | closed |
| T-29-31 | Tampering | Nicht erbetene Textänderungen | mitigate | 29-09-SUMMARY.md listet die vier Owner-Änderungen einzeln, a9ec7ad berührt nur die drei Doku-Seiten | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

### Offene Bedrohungen

| Threat ID | Schwere | Blockiert (block_on: high) | Erwartet | Gesucht in |
|-----------|---------|----------------------------|----------|------------|
| T-29-04 | niedrig | nein | Nachweis einer RAM-Prüfung vor den Messläufen von 29-01 (und 29-06) | 29-01-PLAN.md, 29-01-SUMMARY.md, 29-06-SUMMARY.md, raw/29-01-messungen.txt, scripts/exclusion_evidence.py |

Vorschlag: Owner akzeptiert T-29-04 als Restrisiko (reine Arbeitsplatz-Verfügbarkeit, Läufe sind abgeschlossen, Docker danach gestoppt) und trägt es in das Accepted Risks Log ein, oder künftige SUMMARYs protokollieren den freien Speicher vor schweren Läufen.

### Warnungen

- **W-29-01 (T-29-30):** Nach der Owner-Freigabe ("approved" für a9ec7ad) haben die Review-Fixes ef5dab1, 4aaee84, a462aeb und 5726e08 die drei Doku-Seiten erneut geändert (`git diff --stat a9ec7ad HEAD`: 36 Einfügungen, 11 Löschungen). Die Gegenmaßnahme "kein Push" hält, veröffentlicht ist nichts. Vor dem nächsten Push sollte der Owner diesen Nachtrag sehen.

### Unregistrierte Flags

Kein SUMMARY von 29-01 bis 29-09 hat einen Abschnitt "Threat Flags". Aus 29-REVIEW.md, ohne Registereintrag:

| Flag | Quelle | Bezug | Stand |
|------|--------|-------|-------|
| Steuerzeichen/ANSI aus nutzererzeugten Tag- und Gruppennamen im Konsolentext (Terminal-Täuschung) | 29-REVIEW WR-03 | keine T-29-Id | behoben in 96f4fc1: `_shown()` (exclusion_check.py Z. 526-538) maskiert Kategorie C; Tests Z. 492, 510 |

Informativ, mit Registerbezug: WR-02 (Delegations-Admin) -> T-29-11/T-29-13, behoben 5da76f3; WR-04 (Impersonation berührt Kontotabellen) -> T-29-21, behoben a462aeb.

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-29-01 | T-29-03 | Impersonation als admin nur im Messskript gegen die lokale Wegwerf-Instanz nc35, unter Impersonation nur lesend (PROPFIND/GET, im Code geprüft); Schreiben über occ bzw. Basic-Auth der Testkonten | Plan 29-01 Bedrohungsmodell (Planzeit) | 2026-10-01 |
| AR-29-02 | T-29-07 | Homoglyphen (z. B. kyrillisches i) überstehen NFKC; keine Confusables-Tabelle, bewusste Grenze (29-RESEARCH.md Frage 3, LOW), im Modul-Docstring benannt | Plan 29-02 Bedrohungsmodell (Planzeit) | 2026-10-01 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-10-01 | 31 | 30 | 1 (T-29-04, niedrig, nicht blockierend) | gsd-security-auditor |

Lokal ausgeführt (kein Docker, kein Live-Lauf): `pytest` über test_store_texts_frozen, test_exclusion_audit, test_systemtags_details, test_exapp_exclusion_check, test_docs_exclusion_truth, test_exapp_lifecycle, test_no_destructive_calls, alle grün.

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [ ] `threats_open: 0` confirmed
- [ ] `status: verified` set in frontmatter

**Approval:** pending (T-29-04 offen, W-29-01 vor dem Push klären)
