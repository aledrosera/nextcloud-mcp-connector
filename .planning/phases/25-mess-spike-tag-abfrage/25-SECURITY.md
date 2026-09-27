---
phase: 25
slug: mess-spike-tag-abfrage
status: verified
threats_open: 0
asvs_level: 1
created: 2026-09-27
---

# Phase 25: Security

> Sicherheitsvertrag dieser Phase: Bedrohungsregister, akzeptierte Risiken, Prüfspur.

Besonderheit dieser Phase: Phase 25 war ein Mess-Spike ohne Produktionscode. Geschrieben
wurden das Messskript `scripts/tag_spike.py` (mit `tests/unit/test_tag_spike.py`), zwei
Wegwerf-Compose-Dateien (`compose.spike-tags.yml`, `compose.spike-tags-pg.yml`), neun
Rohprotokolle unter `raw/` und der Bericht `25-MESSBERICHT.md`. `git diff --stat 2b4a9a4^ HEAD
-- src appinfo pyproject.toml uv.lock` ist leer (vom Auditor ausgeführt). Die Wegwerf-Instanzen
sind abgebaut; die Belege für Abbau, Baseline und Unberührtheit stehen in den Rohprotokollen.
Geprüft wurde am Code (Datei:Zeile) und, wo die Mitigation ein Laufergebnis ist, an der
Protokollzeile.

---

## Trust Boundaries

| Grenze | Beschreibung | Was sie überquert |
|--------|--------------|-------------------|
| Messskript zu docker/occ | Testnutzer, Temp-Admin, App-Passwörter | Passwörter nur über stdin bzw. env des Unterprozesses |
| Messskript zu Rohprotokoll (Git) | Antworten und Kommandos werden versioniert | Nur nach `scan_for_secrets` |
| Messskript zu nc35 (Langzeitstrecke) | Tags, Dateien, Shares, Temp-Admin, App-Zustand | Rückbau im `finally`, Baseline-Vergleich |
| Host-Loopback zu Wegwerf-Instanz | Bruteforce-Schutz aus | Nur `127.0.0.1:8083`, DB ohne Port |
| Docker Hub zu lokalen Images | `nextcloud:<patch>-apache`, `postgres:17-alpine` | Offizielle Images, Digest im Protokoll |
| Rohprotokolle zu Messbericht | Auszüge wandern in ein versioniertes Dokument | secret-scan, nur Phasenordner |

---

## Threat Register

| Threat ID | Kategorie | Komponente | Disposition | Mitigation und Beleg | Status |
|-----------|-----------|------------|-------------|----------------------|--------|
| T-25-01 | Information Disclosure | occ_pw, user:add, user:auth-tokens:add | mitigate | `run()` mit fester Liste, kein `shell=True` (`scripts/tag_spike.py:336-345`); `occ_pw` reicht das Passwort als stdin, `OC_PASS="$(cat)"` (`:364-380`); alle Passwort-Aufrufe über `occ_pw` mit `--password-from-env` (`:1268-1272`, `:1295`, `:2548`, `:3102`). Kein Passwort in argv oder Fehlermeldung (`:347-350` zeigt nur `argv[:6]` = docker/exec/-i/-u/www-data/Container) | closed |
| T-25-02 | Information Disclosure | Rohprotokolle `raw/` | mitigate | `row()` nimmt nur einen Rohauszug, kein Header-Zugriff im ganzen Skript (Grep `.headers` ohne Treffer) (`:277-283`); `write_protocol` scannt vor dem Schreiben und wirft sonst `RunFailed` (`:309-317`), aufgerufen im `finally` von `main` (`:3253-3254`); Env-Secrets und AppAPI-Token registriert (`:426-435`), Header-Name `AUTHORIZATION-APP-API` im Scan (`:304-305`); Gate `--block secret-scan` (`:3166-3183`), vom Auditor am 27.09. ausgeführt: `secret-scan: 11 files, 0 findings`, Exit 0 | closed |
| T-25-03 | Information Disclosure | ExApp-Container-Lauf | mitigate | Programm liest `os.environ["APP_SECRET"]` im Container (`:1127`) und druckt nur Status, Anzahl, fileids (`:1145`); Aufruf per stdin, Argumente nur Nutzer und Tag-Id (`:1186-1196`) | closed |
| T-25-04 | Tampering | nc35-Testbasis | mitigate | Präfix `kein-ki-spike25`, Pfad `spike25` (`:94-98`); Baseline vorher (`:1772-1774`); Rückbau im `finally` inkl. `app:enable systemtags` (`:1714-1765`, `:1793-1796`), zusätzlich `app:enable` im `finally` von `block_app_aus` (`:1657-1659`); Protokoll: `BASELINE tags/dateien/papierkorb/mappings ... gleich=ja` (`raw/nc35-befunde.txt:219-222`) | closed |
| T-25-05 | Elevation of Privilege | Temp-Admin `spike25admin` | mitigate | `secrets.token_urlsafe(24)` + `remember_secret` (`:1293-1294`), nur stdin (`:1295`); `user:delete` im `finally` (`:1347-1350`) und nochmals im Rückbau mit `user:list`-Prüfung (`:1760-1765`); Protokoll `RUECKBAU spike25admin vorhanden: nein` (`raw/nc35-befunde.txt:218`) | closed |
| T-25-06 | Spoofing | Impersonations-Deutung | mitigate | Kontrolle a (`:794-805`), b mit falschem Secret (`:806-813`), c Serverlog (`:1179-1184`); Protokoll a `gleich=ja`, b `HTTP 401 abgelehnt=ja` (`raw/nc35-befunde.txt:45-46`), c `REPORT-Zeilen ... : 1` (`:107`); Client ohne Cookie-Jar gegen Identitätsübertrag (`scripts/tag_spike.py:740-748`) | closed |
| T-25-07 | Tampering | XML-Antworten | mitigate | Bodies per lxml (`:556-575`); Tag-Id nur `[0-9]+` (`:562-563`, `:901`, `:1370`); Antworten über `xml.parse_root`/`parse_multistatus` mit `hardened_parser` (`src/mcp_connector/nextcloud/clients/xml.py:28-62`), z.B. `scripts/tag_spike.py:616`, `:633`, `:1593`, `:2659`. Hinweis H-1 unten | closed |
| T-25-SC (25-01/02/03) | Tampering | Paketinstallationen | accept | Siehe A-25-1; `pyproject.toml`/`uv.lock` im Phasenzeitraum unverändert (letzte Änderung `9acbaea` 26.09. 14:40, erster Phasencommit `2b4a9a4` 19:10) | closed |
| T-25-08 | Tampering | nc35-Massendaten | mitigate | Nur `spike25` und Präfixe `kein-ki-spike25`/`spike25-fill-` (`:119`, `:2352-2354`); `teardown` idempotent, auch als eigener Block (`:2365-2403`, `:3242-3243`); Vorbedingung kein Altbestand (`:2336-2337`); Protokoll `RUECKBAU /spike25 vorhanden: nein`, `Spike-Tags vorhanden: keine`, viermal `gleich=ja` (`raw/nc35-latenz.txt:198-203`) | closed |
| T-25-09 | Denial of Service | Docker-VM 7,6 GiB | mitigate | Vorbedingung keine Wegwerf-Instanz (`:2334-2335`); `docker stats` im Kopf und vor dem Ballast (`:494-502`, `:1820-1830`, `:2211`); Ballast-Grenze 600 s (`:122`, `:2215-2219`); Protokoll `BALLAST abgebrochen nach 613 s` (`raw/nc35-latenz.txt:126`). Hinweis H-2 | closed |
| T-25-10 | Information Disclosure | `raw/nc35-latenz.txt`, `nc35-baseline.json` | mitigate | Protokoll über `write_protocol` (`:309-317`); Baseline-JSON nur Zähler (`:1850-1861`, Felder aus `:540`), nach Vergleich gelöscht (`:2402-2403`); Datei nicht vorhanden (Auditor-Prüfung), Protokoll `nach dem Vergleich gelöscht` (`raw/nc35-latenz.txt:204`) | closed |
| T-25-11 | Tampering | PHP-Snippet über stdin | accept | Siehe A-25-2; Snippets als feste Konstanten (`:168-238`), Übergabe `php --` per stdin, `-u www-data` (`:383-399`) | closed |
| T-25-12 | Elevation of Privilege | nc-spike-tags ohne Bruteforce | mitigate | Nur `127.0.0.1:8083:80` (`compose.spike-tags.yml:40`); Zufallspasswörter je Lauf (`scripts/tag_spike.py:2512-2515`); `down -v` im `finally` (`:2596-2602`); Protokoll `ABBAU Container/Volume vorhanden: nein` in `raw/matrix-32.txt:131-132`, `raw/matrix-33.txt:132-133`, `raw/matrix-34.txt:131-132` | closed |
| T-25-13 | Information Disclosure | NC_SPIKE_ADMIN_PASSWORD | mitigate | Nur im env des compose-Unterprozesses (`:2516`, `:2428-2437`, `:335`); Compose-Datei ohne festen Wert, Pflichtvariable (`compose.spike-tags.yml:44`); `remember_secret` vor Nutzung (`scripts/tag_spike.py:2514`). Rest (sichtbar in `docker inspect`) siehe A-25-3 | closed |
| T-25-14 | Tampering | falsche Zielinstanz | mitigate | `matrix` nutzt nur `SPIKE_CONTAINER`/`SPIKE_BASE_URL` (`:70-71`, `:2524-2575`); `Run.container=SPIKE_CONTAINER` (`:2575`), `tag_add`/`tag_files_add`/`block_412`/`block_app_aus`/`restart_container` arbeiten über `run.container` (`:931-945`, `:1244`, `:1648`, `:1658`, `:1686-1689`); `NC_CONTAINER` kommt in keinem Matrix-Pfad vor (Grep); Vorbedingung kein zweiter nc-spike-tags (`:2447-2458`) | closed |
| T-25-15 | Tampering | Volume-Wiederverwendung | mitigate | Vorbedingung Volume leer (`:2440-2458`); `down -v` im `finally` mit Abbau-Prüfung (`:2598-2602`); Protokoll `VORBEDINGUNG Volume ... vorhanden: nein` (`raw/matrix-3x.txt:8`) | closed |
| T-25-16 | Tampering | Docker-Images (Matrix) | accept | Siehe A-25-4; gepinnte Patch-Tags `MATRIX_TAGS` mit Whitelist (`scripts/tag_spike.py:77`, `:2409-2422`), Tag ohne Default (`compose.spike-tags.yml:35`) | closed |
| T-25-17 | Information Disclosure | `25-MESSBERICHT.md` | mitigate | `secret_scan` nimmt den Bericht auf (`scripts/tag_spike.py:3173-3174`), prüft APP_SECRET, beide App-Passwörter, AppAPI-Token und Header-Namen (`:426-435`, `:304`); Auditor-Lauf 27.09.: 11 Dateien (9 Rohprotokolle, Marker `raw/.claude-active`, Bericht), 0 Funde, Exit 0 | closed |
| T-25-18 | Information Disclosure | Veröffentlichung interner Befunde | mitigate | Bericht nur unter `.planning/phases/25-mess-spike-tag-abfrage/` (`:134-138`); Grep `Messbericht|Gegenmessung|spike25` in `docs/` ohne Treffer; `git status -sb`: `main...origin/main [ahead 60]`, also nicht gepusht | closed |
| T-25-19 | Repudiation | Owner-Entscheid D-25-05 | mitigate | Datum, wörtliche Antwort "Empfehlungen übernehmen" und Option-Id je E1 bis E4 (`25-MESSBERICHT.md:204-209`, `25-04-SUMMARY.md:49-52`) | closed |
| T-25-20 | Information Disclosure | Admin-, alice-, DB-Passwort | mitigate | `secrets.token_urlsafe(24)` + `remember_secret` für alle drei (`scripts/tag_spike.py:3054-3062`); compose nur env (`:3058`, `:3067`); occ nur stdin (`:3102`); psql über lokalen Socket ohne Passwort (`:3093-3095`); `write_protocol` scannt (`:3254`); Auditor-secret-scan Exit 0 | closed |
| T-25-21 | Spoofing / EoP | Wegwerf-Instanz ohne Bruteforce | mitigate | Nur `127.0.0.1:8083:80` (`compose.spike-tags-pg.yml:50`), Dienst `db` ohne `ports:` (`:27-43`); `down -v` im `finally` (`scripts/tag_spike.py:3148-3154`); Protokoll `ABBAU ... nein` (`raw/pg-latenz.txt:244-245`, `raw/sqlite35-kontrolle-latenz.txt:246-247`) | closed |
| T-25-22 | Denial of Service | Docker-VM 7,6 GiB | mitigate | RAM-Vorbedingung 3,5 GiB (`:92`, `:3011-3019`), Protokoll `frei=5.93`/`5.92 GiB` (`raw/pg-latenz.txt:40`, `raw/sqlite35-kontrolle-latenz.txt:40`); `mem_limit 1g`/`2g` (`compose.spike-tags-pg.yml:40`, `:69`); Filter `name=nc-spike-tags` leer vor `up` (`scripts/tag_spike.py:2990-3004`); Ballast 900 s (`:90`, `:2941`); `wait_until_idle` über NC und DB (`:1815-1817`, `:2851`). Hinweise H-2, H-3 | closed |
| T-25-23 | Tampering | nc35 und fremde Container | mitigate | In `gegenmessung` nur `docker inspect` auf `nc35-nc` (`:3052`, `:3155`), alle Blöcke über `lat.container`/`run.container` (`:3122-3131`); die einzigen `NC_CONTAINER`-Defaults (`:1833`, `:1948`, `:2152`) werden aus diesem Pfad nie ohne Container aufgerufen (`:2037`, `:2171`, `:2851`); kein `stop`/`rm` fremder Container; Protokoll `NC35 UNBERUEHRT ... gleich=ja` (`raw/pg-latenz.txt:246`, `raw/sqlite35-kontrolle-latenz.txt:248`) | closed |
| T-25-24 | Tampering | PHP-Snippets über stdin | accept | Siehe A-25-2 (gilt gleich für die Wegwerf-Instanz) | closed |
| T-25-25 | Repudiation | Owner-Entscheid E3 | mitigate | Datum 2026-09-27, wörtlich "ok machen wir wie die empfehlung", Option `empfehlung` = `report-je-antwort` (`25-MESSBERICHT.md:349-353`, `25-05-SUMMARY.md:32`); EXCL-02-Wortlaut in `REQUIREMENTS.md` im Phasendiff textgleich (nur Checkbox, siehe H-4) | closed |
| T-25-26 | Information Disclosure | interne Befunde | mitigate | Wie T-25-18: nichts unter `docs/`, nicht gepusht | closed |
| T-25-SC (25-05) | Tampering | `docker pull postgres:17-alpine` | mitigate | Docker Official Image (`compose.spike-tags-pg.yml:29`); Digest per `image inspect` protokolliert (`scripts/tag_spike.py:3096-3099`), Protokoll `postgres@sha256:b0f9560a2de0...` (`raw/pg-latenz.txt:60`); keine Paketinstallation (Lockfiles unverändert) | closed |

*Status: open, closed*
*Disposition: mitigate (Umsetzung nötig), accept (dokumentiertes Risiko), transfer (Dritter)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Begründung | Angenommen von | Datum |
|---------|------------|------------|----------------|-------|
| A-25-1 | T-25-SC (Pläne 25-01 bis 25-03) | Keine neuen Python-Pakete; lxml und httpx sind bestehende Abhängigkeiten; `pyproject.toml` und `uv.lock` im Phasenzeitraum unverändert | Pläne 25-01/02/03, bestätigt im Audit 27.09.2026 | 2026-09-26 |
| A-25-2 | T-25-11, T-25-24 | PHP-Snippets sind feste Repo-Konstanten; Argumente nur Ziffern (Tag-Id, Anzahl), feste Pfade und die Namen der Varianten-Tags aus dem Skript; Ausführung als `www-data` nur in Test- bzw. Wegwerf-Instanzen; DB-Zugriff über QueryBuilder mit Named Parameters | Pläne 25-02 und 25-05, bestätigt im Audit 27.09.2026 | 2026-09-26 |
| A-25-3 | T-25-13 (Teilaspekt) | Admin- und DB-Passwort der Wegwerf-Instanz sind über `docker inspect` lesbar. Lokal, Loopback, Lebensdauer ein Lauf, Wert stirbt mit `down -v` | Plan 25-03, bestätigt im Audit 27.09.2026 | 2026-09-26 |
| A-25-4 | T-25-16 | Offizielle Docker-Hub-Library-Images mit gepinntem Patch-Tag (32.0.15, 33.0.9, 34.0.4), Tags per Registry-API verifiziert (RESEARCH); kein Digest-Pin | Plan 25-03, bestätigt im Audit 27.09.2026 | 2026-09-26 |

---

## Summary-Zusatz 25-03: OCS-Rückfall `getapppassword`

`ocs_app_password` (`scripts/tag_spike.py:2484-2503`) bleibt im Rahmen von T-25-12, T-25-13
und T-25-20: Ziel fest `SPIKE_BASE_URL` (`:71`, `:2491`), also nur Loopback gegen die
Wegwerf-Instanz; das Login-Passwort ist das je Lauf erzeugte Zufallspasswort und geht nur im
Basic-Header dieser einen Anfrage, nie in argv; das Token wird vor jeder Protokollzeile per
`remember_secret` registriert (`:2501`), die Protokollzeile nennt nur den Status (`:2502`).
Genutzt in `matrix` (`:2563`, belegt `raw/matrix-33.txt:60-61`) und `gegenmessung`
(`:3109`). Kein `unregistered_flag`.

## Threat Flags aus den Summaries

| Flag | Quelle | Zuordnung |
|------|--------|-----------|
| Keine neue Angriffsfläche | 25-01, 25-02, 25-04, 25-05 | informativ |
| OCS-Rückfall `getapppassword` | 25-03 | T-25-12, T-25-13, T-25-20 (siehe oben) |

Unregistered Flags: keine.

## Hinweise (keine offenen Threats)

- **H-1 (T-25-07):** Das ExApp-Programm parst im Container mit eigenem `etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False)` (`scripts/tag_spike.py:1142-1143`) statt über `xml.parse_root`. Die XXE-Flags sind gleichwertig, nur die DTD-Ablehnung von `parse_root` fehlt; ausgegeben werden nur fileids. Kein Handlungsbedarf für den abgeschlossenen Spike.
- **H-2 (T-25-09, T-25-22):** Die Ballast-Grenze wird vor jedem Füll-Tag geprüft, ein laufender Schritt wird nicht abgebrochen: 613 s statt 600 s (`raw/nc35-latenz.txt:126`), 926 s statt 900 s (`raw/pg-latenz.txt:196`). So geplant, Überschreitung höchstens ein Schritt.
- **H-3 (T-25-22):** `mem_limit` gilt nur für das PostgreSQL-Paar. Der SQLite-Kontrolllauf nutzt laut Plan 25-05 (A) bewusst unverändert `compose.spike-tags.yml` ohne `mem_limit`; RAM-Vorbedingung und Ein-Instanz-Regel griffen auch dort (`raw/sqlite35-kontrolle-latenz.txt:7-8`, `:40`).
- **H-4 (Nachverfolgung, nicht sicherheitsrelevant):** Der Phasenabschluss hat EXCL-02, EXCL-04 und EXCL-05 in `REQUIREMENTS.md` auf `[x]`/Complete gesetzt, obwohl sie laut Traceability zu Phase 26/27 gehören. Der Wortlaut ist unverändert (T-25-25 erfüllt), der Status sollte von Hand zurückgestellt werden.

## Security Audit 2026-09-27

| Kennzahl | Wert |
|----------|------|
| Threats gesamt | 29 Einträge (26 IDs, T-25-SC dreifach je Plan geführt, hier zweizeilig) |
| Closed | alle |
| Open | 0 |
| secret-scan (Auditor-Lauf) | 11 Dateien, 0 Funde, Exit 0 |
| Produktionsbaum-Diff | leer (`src`, `appinfo`, `pyproject.toml`, `uv.lock`) |

Prüfspur: Threat-Register aus `25-01-PLAN.md` bis `25-05-PLAN.md`, Code in
`scripts/tag_spike.py`, `compose.spike-tags.yml`, `compose.spike-tags-pg.yml`,
`src/mcp_connector/nextcloud/clients/xml.py`, Stichproben in `raw/`, `25-MESSBERICHT.md`
und den fünf Summaries. Keine Implementierungsdatei verändert.
