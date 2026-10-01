# Phase 29: Prüfkommando und Doku - Research

**Researched:** 2026-10-01
**Domain:** AppAPI-occ-Kommando (ExApp-Handler) mit lesendem Systemtag-Zugriff über WebDAV, dreisprachige Betreiber-Doku
**Confidence:** MEDIUM-HIGH (Code-Muster und Nextcloud-Quelltext verifiziert; drei Verhaltenspunkte unter Impersonation müssen live gegen nc35 gemessen werden, siehe M1 bis M9)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Übernommen aus früheren Phasen (nicht neu verhandelt)
- **D-26-01:** Das `kein-ki`-Tag auf einem Ordner IST die Ausschlussliste; keine zweite, konfigurierbare Liste. Das Prüfkommando prüft also nur das Tag.
- **D-26-02:** Kein Admin-Schalter, kein konfigurierbarer Tag-Name (`EXCLUDE_TAG = "kein-ki"`, Vergleich ohne Groß/Klein, `src/mcp_connector/nextcloud/exclusion.py`). Damit ist der offene Roadmap-Punkt "hängt an den Entscheiden aus Phase 26" beantwortet.
- **Owner 30.09. (28-REVIEW.md, Owner decisions):** WR-02 bleibt zur Laufzeit fail-open und wird als Grenze dokumentiert; WR-03-Freitext und IN-02 kommen als Grenzen in die Doku.

#### Prüfkommando: Befunde
- **D-29-01:** Neben den Pflichtschritten (Tag existiert, ist sichtbar, gleichnamige Varianten / Tippfehler wie "Kein KI", "keinki") erkennt und meldet das Kommando die **Betriebsart**: Selbstbedienung (jeder darf zuweisen, kollaborativ) oder Organisationsmodus (eingeschränktes Tag, Zuweisung nur durch delegierte Gruppe(n), Gruppen werden genannt), jeweils mit einem Satz, was das für die Nutzer heißt.
- **D-29-02:** Das Kommando meldet die **Anzahl** der Objekte, denen `kein-ki` zugewiesen ist, ohne Namen, Pfade oder Konten. Keine Liste.
- **D-29-03:** Gibt es kein `kein-ki`-Tag, ist das ein **Hinweis, kein Fehler** (`passed` bleibt true): "kein Tag vorhanden, der Connector filtert nichts", plus wie man es anlegt. Fehlkonfigurationen (unsichtbares Tag, nur Tippfehler-Variante vorhanden) sind dagegen nicht bestanden.
- Erfolgskriterien der Roadmap bleiben: läuft ohne Sitzung, ändert nichts (Vorher-nachher-Vergleich der Tag- und Zuordnungstabellen leer), gegen eine echte Instanz für unsichtbares Tag und Tippfehler belegt.

#### Prüfkommando: Ausgabe
- **D-29-04:** Gleiches Muster wie `exchange:check` (`src/mcp_connector/exapp/exchange_check.py`): lesbarer Text je Prüfschritt, zusätzlich `--json` mit Schlüssel `passed`; der Exit-Code ist über AppAPI immer 0 und wird so dokumentiert, Monitoring liest `passed`.

#### Grenzen-Doku
- **D-29-05:** **Alle Grenzen einzeln**, je ein Satz Wirkung plus Verweis auf den Befund (Phase 25 Messbericht bzw. die Phase-26/27/28-Entscheide): Freigabe-Grenze (Tag oberhalb der Freigabe-Wurzel wirkt beim Empfänger nicht), unsichtbares Tag wirkt nicht, App-aus-Verhalten, Timing-Orakel (D-28-12), `search` im Ausfall (D-28-13), `notes_create`-Restorakel (D-28-16), Suchprovider von Drittanbieter-Apps (WR-02), Tables-Freitext mit `/f/<id>` (WR-03), Talk-Datei-Raum-Orakel bei ausfallender Pfadsuche (IN-02).

#### Doku-Aufbau und README
- **D-29-06:** Eine eigene Seite je Sprache: `docs/exclusion.md` (EN), `docs/exclusion.de.md`, `docs/exclusion.fr.md`, Inhalt: Einrichtung, Betriebsarten, Prüfkommando, Grenzen. Deutsch mit echten Umlauten, keine Gedankenstriche.
- **D-29-07:** README.md / README.de.md / README.fr.md bekommen je einen **kurzen Abschnitt** (3 bis 4 Zeilen): was das Tag tut, die wichtigste Grenze in einem Satz, Link auf die Doku-Seite der Sprache.
- **D-29-08:** Die Doku enthält eine **Schritt-für-Schritt-Anleitung mit occ-Befehlen** für beide Betriebsarten (Tag anlegen; eingeschränktes Tag mit Gruppen-Delegation; Kontrolle mit dem Prüfkommando), gegen nc35 nachgemessen, Befehle und Ausgaben als Rohbeleg.

### Claude's Discretion
- Wortlaut und Reihenfolge der Prüfschritte, Schlüsselnamen im `--json` (am exchange:check-Schema orientiert), Erkennung der Tippfehler-Varianten (Normalisierung von Leerzeichen, Bindestrich, Groß/Klein), technische Umsetzung der Zählung ohne Zustandsänderung.

### Folded Todos
- `.planning/todos/pending/2026-09-30-phase29-restliste-kein-ki.md` (Owner-Entscheid 30.09.): Drittanbieter-Provider, Tables-Freitext, IN-02 als Grenzen in die Doku (in D-29-05 aufgenommen).

### Deferred Ideas (OUT OF SCOPE)
- Admin-Option "strict" (unbekannte Suchprovider fail-closed), Standard aus: Kandidat für einen späteren Meilenstein, falls ein Kunde strikte Garantie braucht.
- Store-Texte zum Ausschluss-Tag (EXCL-F02): reisen mit dem nächsten Release.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| OPS-01 | `occ mcp_connector:exclusion:check` prüft Tag-Existenz, Sichtbarkeit und gleichnamige Varianten gegen die Instanz und benennt je Prüfschritt das Ergebnis, ohne Sitzung und ohne Nextcloud-Zustandsänderung (Muster exchange:check) | Abschnitte "Frage 1" (Verdrahtung), "Frage 2" (Nextcloud-APIs, Identität), "Frage 3" (Varianten), "Frage 4" (Nichts-ändern-Beweis) |
| DOC-03 | Dreisprachige Doku (docs/ + README-Erwähnung): Einrichtung, ehrliche Grenzen (Freigabe-Grenze, unsichtbares Tag, App-aus), Betriebsarten Selbstbedienung vs. Organisationsmodus | Abschnitt "Frage 5" (Befund-Inventar, occ-Befehle), Pitfalls P5 bis P8 |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- Python 3.13, uv als Toolchain (System-Python defekt); alle Befehle über `uv run`.
- Code/README Englisch, Projektkommunikation Deutsch; keine Em-Dashes (U+2014) und keine En-Dashes (U+2013); echte Umlaute in deutschen Texten (gilt für `docs/exclusion.de.md`, `README.de.md`).
- Security: der MCP darf nie mehr sehen als der angemeldete Nutzer; keine destruktiven Writes. Für das Prüfkommando heißt das: ausschließlich lesende Nextcloud-Aufrufe, keine Namen/Pfade/Konten in der Ausgabe (D-29-02).
- Qualitätsgates (Memory-Regel, CI-Job `unit`): `ruff check`, `ruff format --check`, pyright (lokal mit `PYRIGHT_PYTHON_FORCE_VERSION=latest`), vulture (neue Handler-Namen ggf. in `vulture_whitelist.py`), `pytest tests/unit tests/contract`.
- OSS-Commits als `street1983nk <k.cherif@outlook.de>`, keine Claude-Trailer.
- Store-Texte (`appinfo/info.xml` `<summary>`/`<description>` in drei Sprachen) bleiben in dieser Phase unverändert (EXCL-F02, Erfolgskriterium 4).

## Summary

Das neue Kommando ist strukturell eine Kopie von `exchange:check`: ein Schema-Eintrag in `exapp/occ.py:command_schemes()`, ein Handler-Modul `exapp/exclusion_check.py` mit einer Route-Fabrik, die in `entry_exapp.py:381` neben `exchange_check_routes` eingehängt wird, derselbe Doppel-Guard (`x-origin-ip` → 404, `require_appapi` → 401), immer HTTP 200, Text oder `--json` mit `passed`. Der Pfad kommt wie `/exchange-check` in KEIN `<url>` des Manifests, nur in den Kommentarblock "deliberately absent paths" von `appinfo/info.xml`.

Der wesentliche Unterschied und das eigentliche Risiko dieser Phase: `exchange:check` macht keinen einzigen Nextcloud-Aufruf, `exclusion:check` muss Systemtags lesen. AppAPI ruft den occ-Handler ohne Nutzer auf (`ExAppOccService::buildCommand` übergibt keinen userId), und mit leerem Nutzer im AppAPI-Header ist die Sitzung `null` (`AppAPIService::finalizeRequestToNC`), womit WebDAV nicht authentifiziert und unsichtbare Tags ohnehin nicht gelistet werden. Unsichtbare Tags und die Delegationsgruppen (`oc:groups`) sieht laut Nextcloud-Quelltext nur ein **Admin** (`SystemTagsByIdCollection::getChildren`, `SystemTagPlugin` Zeile 297 bis 307). Das Kommando muss also per AppAPI-Impersonation als ein Admin-Konto lesen. Empfehlung: Option `--admin=<uid>`, deren Admin-Eigenschaft der Handler selbst prüft, bevor er irgendetwas urteilt (Owner-Bestätigung nötig, Open Question O1).

Die Zählung (D-29-02) geht ohne Zustandsänderung und ohne REPORT über die WebDAV-Eigenschaft `nc:object-ids` auf `/remote.php/dav/systemtags/<id>` (Depth 0): Nextcloud liefert dort für einen `SystemTagNode` alle Objekt-Ids aller Typen instanzweit, ungefiltert nach Nutzer (`SystemTagPlugin.php` Zeile 319 bis 328, NC 32 bis 35 identisch). Der Handler zählt nur die Elemente vom Typ `files` und schreibt nie eine Id heraus. `nc:files-assigned` taugt dafür NICHT (auf `/systemtags/<id>` immer -1, nur in `systemtags-assigned` pro Nutzerordner gesetzt).

**Primary recommendation:** `exapp/exclusion_check.py` als Strukturkopie von `exapp/exchange_check.py` bauen; Nextcloud-Lesezugriffe in einen neuen, policy-freien Client (`nextcloud/clients/systemtags.py` erweitern um `list_tag_details` und `count_tag_objects`) mit eigenem lxml-Parser; Klassifikation (exakt/Variante/ähnlich, Betriebsart, Urteil) als reine Funktion ohne I/O, damit sie mit Unit-Tests voll abgedeckt ist; Live-Beleg und Tabellen-Diff als `scripts/exclusion_evidence.py` plus Integrationstest im CI-Job `canary-nc35`.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| occ-Kommando anbieten (`occ list`) | Nextcloud/AppAPI (PHP) | ExApp (Registrierung `exapp/occ.py`) | AppAPI baut den Symfony-Befehl aus dem registrierten Schema |
| Aufruf annehmen, Guard, Antwortform | ExApp-Handler (`exapp/exclusion_check.py`) | , | Muster exchange:check; Pfad nur über PublicFunctions erreichbar |
| Tags, Sichtbarkeit, Gruppen, Zählung lesen | ExApp-Client (`nextcloud/clients/systemtags.py`) | Nextcloud WebDAV `systemtags` | Policy-frei, nur PROPFIND; Muster des bestehenden Clients |
| Exakt/Variante/Betriebsart/Urteil | ExApp, reine Funktion (`nextcloud/exclusion.py` oder neues Modul) | , | Ohne I/O testbar; nutzt `is_exclude_name` des Guards als einzige Wahrheit für "exakt" |
| Tag/Gruppen anlegen (Doku-Anleitung) | Nextcloud occ / WebDAV als Admin | Web-UI | Das Kommando schreibt NIE; Schreiben ist Betreiberhandlung |
| Nichts-ändern-Beweis | Harness (Skript + Integrationstest) | Nextcloud DB über PHP-QueryBuilder | DB-agnostisch, Präfix automatisch, Muster `scripts/tag_spike.py` |

## Frage 1: Wie exchange:check verdrahtet ist und was exclusion:check nachbauen muss

| Baustein | Fundstelle exchange:check | Was exclusion:check braucht |
|---|---|---|
| Kommandoname, einmal als Literal | `exapp/occ.py:201` `OCC_EXCHANGE_CHECK_COMMAND_NAME` | `OCC_EXCLUSION_CHECK_COMMAND_NAME = "mcp_connector:exclusion:check"` (Name niemals später umbenennen: AppAPI `insertOrUpdate` keyt auf appid+name, `occ.py:197-200`) |
| Handler aus Pfadkonstante abgeleitet | `occ.py:205` `EXCHANGE_CHECK_PATH.removeprefix("/")` | `OCC_EXCLUSION_CHECK_HANDLER = EXCLUSION_CHECK_PATH.removeprefix("/")`, Pfad `"/exclusion-check"` |
| Beschreibung ≤ 255 Zeichen | `occ.py:97-102` `APPAPI_DESCRIPTION_LENGTH` (MariaDB 1406) | Beschreibung und Optionsbeschreibungen kurz halten; nennt: liest nur, ändert nichts, keine Namen/Pfade |
| Optionsmodi nur `required/optional/none`, keine Arguments, jede Wertoption mit `default` | `occ.py:285-302`, `:348-379` | `--json` (`none`), `--admin` (`optional`, `default: None`) falls O1 so entschieden; `arguments: []` |
| Schema-Eintrag | `occ.py:357-389` | fünfter Eintrag in `command_schemes()`; Modul-Docstring "Four of them" (`occ.py:3`) anpassen |
| Registrierung | `occ.py:393-444` (ein POST je Schema, eigener try) | nichts zu tun, Schleife registriert automatisch |
| Route-Fabrik | `exchange_check.py:228-292` `exchange_check_routes` → `[Route(PATH, handler, methods=["POST"])]` | `exclusion_check_routes(env, ...)`, Abhängigkeiten (ExApp-Settings, httpx-Client) injizierbar wie `purge_routes(env, nextcloud=...)` (`entry_exapp.py:378`) |
| Einhängen | `entry_exapp.py:39`, `:381` | `*exclusion_check_routes(env, ...)` direkt danach |
| Guard | `exchange_check.py:409-422` `_guard` (wörtlich aus `audit_verify.py:309`) | wörtlich übernehmen, `HEADER_ORIGIN_IP` erneut buchstabieren (Importzyklus `lifecycle → occ → handler`, `exchange_check.py:120-126`) und per Test gegen `audit_verify` gleichhalten |
| Body lesen, begrenzt | `exchange_check.py:_payload`, `MAX_BODY_BYTES` | hier gilt wieder die 4-KB-Grenze von `audit_verify.py:97` (kein Token im Body) |
| `--json` erkennen | `_set_in`, `_is_set`, `TRUE_WORDS` (`exchange_check.py:424-465`) | kopieren, `TRUE_WORDS` per Test gegen `audit_verify` gleichhalten |
| Optionswert lesen | `_value`, `_given` (`:468-498`) | für `--admin` kopieren |
| Immer 200, Exit-Code 0 | Docstring `exchange_check.py:23-29`; Ursache `ExAppOccService::buildCommand` verwirft den Body bei Status ≠ 200 | gleich; jeder Fehler wird zu einem benannten Ergebnis mit 200 |
| Text: Kopfzeile, eine Zeile je Schritt, Spaltenbreite | `HEAD_LINE`, `OUTCOME_WIDTH = 12`, `_report`, `_line` (`:184-195`, `:295-330`) | gleiche Form; Schritte stehen IMMER alle da, nicht erreichte als `skipped` (Pitfall 8 aus Phase 24: fehlende Zeile liest sich wie bestanden) |
| JSON | `_machine_readable` (`:333-361`): `checked`, `passed`, `steps[{step,name,outcome,reason,note}]`, `cost`, `limit` | gleiche Schlüssel plus `mode`, `assigned`, `tags` (Vorschlag unten) |
| Ausnahme im Lauf | `:278-290` Typname, nie Message | gleich |
| Manifest | `appinfo/info.xml:248-258` siebter "deliberately absent path" | achten Eintrag `/exclusion-check` in den Kommentar, KEIN `<url>` |
| Tests | `tests/unit/test_exapp_exchange_check.py` (Guard 404/401, nicht im Manifest, immer 200, JSON-Verdikt, Spellings gleich, Body-Grenzen), `tests/unit/test_exapp_lifecycle.py:526-553` (Schema Nr. 4, Handler abgeleitet, `len(schemes) == 4`), `tests/unit/test_exapp_entry.py:342-376` (Route im gebauten App, 200, Proxy 404) | je Test ein Pendant; `len(schemes) == 5`; Positivliste der Modi gilt automatisch |
| vulture | `vulture_whitelist.py:298` (Phase-24-Eintrag) | Route-Handler ggf. ergänzen |

**Unterschied, der Neues verlangt:** exchange:check hat keinen Nextcloud-Client. Die Vorlage für einen Handler, der Nextcloud ruft, ist `exapp/purge.py` (bekommt `NextcloudTarget` injiziert) und für AppAPI-Header im App-Kontext `exapp/occ.py:413-423` bzw. `audit/accounts.py:63` (`USERS_PATH`). Die Credentials für eine Impersonation baut `deps.py:331-340` (`Credentials(..., mode=MODE_APPAPI, user=<uid>, secret=app_secret, ...)`).

### Vorschlag Prüfschritte und JSON (Claude's Discretion)

Schritte in fester Reihenfolge, Outcome-Wörter aus `oauth/exchange_dryrun.py:148-154` (`passed`, `failed`, `skipped`, `not_checked`) plus `note` für Hinweise, die das Urteil nicht kippen:

1. `admin_identity`: das genannte Konto existiert und ist Admin (sonst kann Unsichtbarkeit nicht beurteilt werden → `checked: false`, `passed: false`, benanntes Ergebnis wie `OUTCOME_NOT_CONFIGURED`).
2. `tag_listing_readable`: PROPFIND `/systemtags/` 207.
3. `tag_exists`: mindestens ein Tag mit `is_exclude_name(name)`; sonst `note` + D-29-03-Satz + Anlegehinweis, `passed` bleibt true, Schritte 4 bis 7 `skipped`.
4. `tag_visible`: jede exakte Schreibung `user-visible=true`; ein unsichtbares exaktes Tag → `failed` (Satz: wirkt für Nutzer nicht, nur für Admins).
5. `no_variants`: keine Variante (Normalform gleich, siehe Frage 3); sonst `failed` mit Namen der Varianten (Tag-Namen sind keine Nutzerdaten im Sinne von D-29-02) und deren Zählung.
6. `operating_mode`: `self_service` (public) / `organisation` (restricted, Gruppen genannt; ohne Gruppen: "nur Administratoren") ; immer `passed` oder `note`, mit einem Satz Wirkung (D-29-01).
7. `assignment_count`: Zahl der `files`-Objekte auf den exakten sichtbaren Tags; getrennt die Zahl auf unsichtbaren exakten und auf Varianten ("diese N Objekte sind NICHT geschützt").

JSON-Vorschlag: `{"checked": true, "passed": bool, "mode": "none"|"self_service"|"organisation"|"misconfigured", "assigned": int|null, "steps": [...], "tags": [{"name", "access": "public|restricted|invisible", "groups": [gid...], "assigned": int, "kind": "exact|variant|similar"}], "limit": "<Grenzsatz>"}`. `limit` nennt ehrlich, was ein grünes Ergebnis NICHT heißt (Freigabe-Grenze, SQLite-Grenze), analog `LIMIT_SENTENCE` (`exchange_dryrun.py:166`).

## Frage 2: Welche Nextcloud-APIs ohne Sitzung und ohne Zustandsänderung, und was sieht die ExApp-Identität

### Was Nextcloud liefert (Quelltext verifiziert, stable35 = master für diese Stellen, stable32 gleich)

| Information | API | Wer sieht es | Beleg |
|---|---|---|---|
| Alle Tags inkl. unsichtbar | `PROPFIND Depth 1 /remote.php/dav/systemtags/` | Admin: alle (`visibilityFilter = null`); Nicht-Admin: nur `user-visible` (public + restricted) | `apps/dav/lib/SystemTag/SystemTagsByIdCollection.php:102-111` [CITED: github.com/nextcloud/server stable35] |
| `oc:user-visible`, `oc:user-assignable` | gleiche PROPFIND, Eigenschaften anfordern | jeder, der das Tag sieht | `SystemTagPlugin.php:279-286` [CITED] |
| `oc:can-assign` | gleiche PROPFIND | effektiv für den aktuellen Nutzer; für Admin immer true (wertlos für die Betriebsart) | `SystemTagPlugin.php:288-291`, `SystemTagManager::canUserAssignTag` [CITED] |
| `oc:groups` (Delegation, `|`-getrennte gids) | gleiche PROPFIND | NUR Admin; Nicht-Admin bekommt `Forbidden` für die Eigenschaft; leer, wenn Tag nicht "restricted" | `SystemTagPlugin.php:297-307` [CITED] |
| Anzahl zugewiesener Objekte instanzweit | `PROPFIND Depth 0 /remote.php/dav/systemtags/<id>` mit `nc:object-ids` | jeder, der das Tag sieht (für unsichtbare Tags also nur Admin); Wert ist NICHT nach Nutzer gefiltert | `SystemTagPlugin.php:319-328` (SystemTagNode-Zweig), `SystemTagObjectMapper::getObjectIdsForTags` (DISTINCT objectid, kein Limit) [CITED] |
| `nc:files-assigned` | , | auf `/systemtags/<id>` immer `-1`; nur in `/systemtags-assigned/` pro Nutzerordner gesetzt | `SystemTagNode.php:28`, `SystemTagsInUseCollection.php:59-82` [CITED] → nicht verwenden |
| Serialisierung `nc:object-ids` | `<nc:object-id><nc:id>…</nc:id><nc:type>files</nc:type></nc:object-id>` | , | `SystemTagsObjectList.php` [CITED] |

### Was die ExApp-Identität darf

- **Occ-Aufruf hat keinen Nutzer:** `ExAppOccService::buildCommand` ruft `exAppRequest(appid, handler, params: ['occ' => ...])` ohne userId [CITED: github.com/nextcloud/app_api main, `lib/Service/ExAppOccService.php`].
- **Leerer Nutzer = keine Sitzung:** `AppAPIService::finalizeRequestToNC` setzt bei `userId === ''` `userSession->setUser(null)` (`lib/Service/AppAPIService.php:339-350`) [CITED]. `DavPlugin::beforeMethod` setzt `DAV_AUTHENTICATED` auf `''`. Erwartung: WebDAV `/systemtags/` antwortet 401, und selbst bei Durchlass sähe `null` nur public-Tags (`canUserSeeTag` mit `null`). Das Projekt verbietet den App-Kontext für Lesezugriffe ohnehin (T-02-12, `deps.py:325-330`). **Muss gemessen werden (M1).**
- **Impersonation beliebiger existierender Konten:** `finalizeRequestToNC` akzeptiert jede existierende uid und schreibt `exapp_impersonation.log` (`AppAPIService.php:340-347`, Phase 25 K2 Kontrolle c: `25-MESSBERICHT.md` Zeile 32) [VERIFIED: Messbericht + Quelltext]. Mit einer Admin-uid gilt `groupManager->isAdmin` und damit volle Sicht.
- **Phase-25-Beleg für die Sichtbarkeit:** unsichtbares Tag 63 "in alices Liste=nein", "in der Admin-Liste=ja" (`raw/nc35-befunde.txt:128`, `:136`), allerdings mit Basic-Auth von `spike25admin`, nicht unter Impersonation [VERIFIED: Rohdatei]. Dass Impersonation dieselbe Menge liefert, ist für den REPORT gemessen (K2, Zeile 31), für die Tag-Liste als Admin NICHT (M2).
- **Admin finden ohne Admin geht nicht:** AppAPI bietet im App-Kontext nur die Liste aller uids (`GET /ocs/v2.php/apps/app_api/api/v1/users`, `OCSApiController::getNCUsersList`, im Projekt genutzt in `audit/accounts.py:63`), keine Gruppen. `cloud/groups/admin/users` verlangt einen Admin [ASSUMED, M2b]. Automatisches Durchprobieren aller uids wäre O(n) Impersonationen bei LDAP-Instanzen: verworfen.

### Empfehlung zur Identität (Open Question O1, Owner-Bestätigung)

`--admin=<uid>` als Option (`mode: optional`, `default: None`). Der Handler:
1. ohne Option: benanntes Ergebnis `admin_not_named` (`checked: false`, `passed: false`), Satz mit Beispielbefehl;
2. mit Option: Impersonation als `<uid>`, erster Aufruf ist der Admin-Nachweis (Kandidat a: `oc:groups` in der Listing-PROPFIND anfordern, 403-Propstat = kein Admin; Kandidat b: `GET /ocs/v2.php/cloud/groups/admin/users` 200 vs. 403). Welcher Kandidat sauber trennt, entscheidet M2; bei a ist zu messen, ob `Forbidden` im Property-Handler nur das Propstat oder die ganze Antwort kippt.
3. Nicht-Admin oder unbekannte uid: benanntes Ergebnis, kein Urteil über Unsichtbarkeit.

Sicherheitsbewertung: Der Pfad ist nur über PublicFunctions (occ auf dem Host) erreichbar; wer occ ausführen kann, ist bereits Vollverwalter. Die Impersonation liest nur (PROPFIND), wird von AppAPI protokolliert, und die Ausgabe enthält Tag-Namen, Zugriffsstufe, gids und Zahlen, keine Datei- oder Kontonamen.

### Live-Messungen gegen nc35 (Wave 0 oder erster Plan, Rohprotokoll unter `.planning/phases/29-pr-fkommando-und-doku/raw/`)

| # | Frage | Messung | Erwartung |
|---|---|---|---|
| M1 | Antwort bei leerem Nutzer | aus dem ExApp-Container (Weg wie K2 "Produktionsweg") PROPFIND `/systemtags/` mit AppAPI-Header `":"+secret` | 401 (dann ist O1 zwingend) |
| M2 | Impersonierter Admin sieht unsichtbare Tags, `oc:groups` | `occ tag:add kein-ki-m2 invisible`, `tag:add kein-ki-m2r restricted` + Gruppe; PROPFIND als impersonierter Admin und als impersonierte alice mit `oc:groups` | Admin: beide gelistet, `user-visible=false`, gids; alice: unsichtbares fehlt, `oc:groups` 403-Propstat ODER ganze Antwort 403 (protokollieren, welches) |
| M2b | Admin-Nachweis über OCS | `GET /ocs/v2.php/cloud/groups/admin/users` als impersonierter Admin und alice | 200 / 403 |
| M3 | Zählung instanzweit | Tag auf je eine Datei von alice und bob, PROPFIND Depth 0 `nc:object-ids` als Admin | 2 `object-id` vom Typ `files` |
| M4 | Zählung nach Papierkorb | getaggte Datei löschen (Papierkorb), erneut zählen; danach endgültig löschen | dokumentieren, ob die Zuordnung bleibt (Doku-Satz "zählt Zuordnungen, auch im Papierkorb") |
| M5 | Nichts geändert | Tabellen-Diff vor/nach `occ mcp_connector:exclusion:check` und `--json` (Frage 4) | leer |
| M6 | Tippfehler-Fälle real | `occ tag:add "Kein KI" public`, `tag:add keinki public`; Groß/Klein-Variante nur per PHP-Insert (`scripts/tag_spike.py` `PHP_INSERT_VARIANT`) | Kommando meldet Variante, `passed=false` |
| M7 | Anleitung Selbstbedienung | `occ tag:add kein-ki public --output=json`, `occ tag:files:add /alice/files/<Ordner> kein-ki public` | id, "added" |
| M8 | Anleitung Organisationsmodus | `occ group:add ki-verantwortung`, `occ group:adduser ki-verantwortung alice`, `occ tag:add kein-ki restricted --output=json`, Gruppen per PROPPATCH (unten); `occ config:app:set systemtags restrict_creation_to_admin --value=true --type=boolean` | gids im Prüfkommando sichtbar; bob kann nicht zuweisen (DAV 403) |
| M9 | UI-Ort der Delegation | Admin-Einstellungen, Bereich "Collaborative tags" | Menüpfad für die Doku festhalten (Screenshot optional) |

## Frage 3: Tippfehler- und Variantenerkennung

**Ausgangslage (verifiziert):**
- Der Guard zählt als "exakt", was `is_exclude_name` erfüllt: `name.strip().casefold() == "kein-ki"` (`nextcloud/exclusion.py:125-127`). "Kein-KI" ist also KEINE Variante, sondern wirkt. Das Kommando muss genau diese Funktion für "exakt" verwenden, nie eine eigene.
- Nextcloud ab 32 verweigert beim Anlegen nur Namen, die sich bloß in Groß/Klein unterscheiden (`SystemTagManager::createTag`, `mb_strtolower`-Vergleich, Zeilen 178-184) und normalisiert Leerraum/Steuerzeichen (`Util::sanitizeWordsAndEmojis`: entfernt `\p{C}`, fasst Leerraum zu einem Leerzeichen) [CITED]. "Kein KI", "keinki", "kein_ki", "kein" plus Halbgeviertstrich U+2013 plus "ki", "kein" plus U+2010 plus "ki" können also neben "kein-ki" existieren. Reine Groß/Klein-Varianten gibt es nur aus Altbeständen oder per DB (Phase 25 hat sie per PHP-Insert erzeugt).
- Messbericht K5/G4: andere Schreibung W ist ein eigenes Tag mit eigener Menge (`25-MESSBERICHT.md` Zeile 71, 305-306).

**Empfohlene Normalform (stdlib, kein Paket):**
```python
import unicodedata

def tag_skeleton(name: str) -> str:
    """NFKC, casefold, then keep letters and digits only (drops blanks, hyphens, dashes, _ . and format chars)."""
    folded = unicodedata.normalize("NFKC", name).casefold()
    return "".join(ch for ch in folded if unicodedata.category(ch)[0] in "LN")
```
Klassen: `exact` = `is_exclude_name(name)`; `variant` = nicht exakt und `tag_skeleton(name) == "keinki"`; `similar` (optional) = Damerau-Levenshtein-Abstand 1 zwischen `tag_skeleton(name)` und `"keinki"` (z. B. "kien-ki", "kein-kl", "keinkii"), ca. 15 Zeilen eigener Code, als `note` ohne Urteil.

**Falsch-positiv-Risiken:**
- Gleichheit statt Teilstring: "Kein KI-Training" oder "keine-ki-tools" werden nicht gemeldet (Normalform `keinkitraining` ≠ `keinki`). Teilstring-Suche würde solche legitimen Tags fälschlich melden: nicht verwenden.
- `similar` (Abstand 1) trifft bei 6 Zeichen auch fremde Wörter (z. B. "keiki"). Deshalb nur Hinweis, kein `failed`.
- Homoglyphen (kyrillisches "і" in "kein-kі") fängt NFKC nicht; bewusst nicht abgedeckt (Grenze, LOW). Keine Confusables-Bibliothek für diesen Randfall.
- MySQL/MariaDB-Kollation ist nicht gemessen (Annahme A3 aus Phase 25, `25-MESSBERICHT.md` Zeile 309): auf einer ci-Kollation könnte Nextcloud eine Groß/Klein-Variante anders behandeln; das betrifft den Guard, nicht die Normalform.

**Urteil (Owner-Bestätigung, O2):** D-29-03 legt nur "nur Variante vorhanden" als nicht bestanden fest. Empfehlung: eine Variante macht `passed=false` auch dann, wenn daneben das exakte Tag existiert, weil Nutzer, die "Kein KI" setzen, sich geschützt glauben; die Ausgabe nennt die Zahl der Objekte auf der Variante ("nicht geschützt").

## Frage 4: Beweis "ändert nichts"

**Tabellen** (QueryBuilder-Namen, Präfix setzt Nextcloud): `systemtag` (Tags), `systemtag_object_mapping` (Zuordnungen, `SystemTagObjectMapper::RELATION_TABLE`), `systemtag_group` (Delegation, `SystemTagManager::TAG_GROUP_TABLE`, Zeile 37) [CITED]. Zusätzlich sinnvoll: `appconfig` Zeilen mit `appid='systemtags'`.

**Mechanik (Muster vorhanden):** `scripts/tag_spike.py` führt PHP-Schnipsel per `docker exec -i -u www-data -w /var/www/html <nc> php --` mit `\OCP\Server::get(\OCP\IDBConnection::class)` aus (`tag_spike.py:216-238`, `php()` Zeile 383) und hat in Phase 25 genau so `mappings vorher=0 nachher=0 gleich=ja` belegt (`25-MESSBERICHT.md` Zeile 79). DB-agnostisch (SQLite in nc35 und CI, PostgreSQL in 25-05).

Empfohlenes Schnipsel: je Tabelle alle Zeilen sortiert lesen, als JSON ausgeben, Zeilenzahl plus SHA-256 drucken; das Harness vergleicht Vorher/Nachher und protokolliert `TABELLE systemtag vorher=<n>/<sha> nachher=<n>/<sha> gleich=ja` und einen leeren `diff` der beiden JSON-Dumps. Inhalte (Tag-Namen der Testinstanz) dürfen ins Rohprotokoll; Datei-Ids nicht nötig, nur Hashes.

**Ablauf live (nc35 lokal und CI-Job `canary-nc35`):**
1. Welt aufbauen per occ (Harness schreibt, `src/` nie, EXCL-07-Regel aus `test_exclusion_live.py:5`): Fall A kein Tag; Fall B `kein-ki` public + 1 Zuordnung; Fall C restricted + Gruppe; Fall D invisible; Fall E nur "Kein KI"; Fall F exakt + "keinki".
2. Je Fall: Dump vorher → `occ mcp_connector:exclusion:check --admin=admin` und `... --json` → Dump nachher → Vergleich, erwartetes `passed`/`mode` prüfen.
3. Aufräumen und Rückbau lesen, nicht annehmen (`occ tag:list --output=json` ohne `kein-ki`, Muster `test_exclusion_live.py:20`).

**Ergänzender Unit-/Contract-Beweis:** respx-Mock zählt alle ausgehenden Requests des Handlers und erwartet ausschließlich `PROPFIND` (ggf. `GET` für M2b), nie `PROPPATCH/POST/PUT/DELETE/MKCOL/MOVE/COPY/REPORT`. Und: kein Audit-Eintrag (Muster exchange:check "no audit log row").

**CI:** `canary-nc35` (`.github/workflows/ci.yml:160-214`) läuft auf `nextcloud:35.0.1-apache` mit dem ExApp aus dem aktuellen Quellstand; neuer Schritt "exclusion:check live (OPS-01)" mit `uv run pytest tests/integration/test_exclusion_check_live.py -m integration -s`. Es gibt bislang KEINEN Live-Test, der ein ExApp-occ-Kommando aufruft (alle `mcp_connector:*`-Tests sind Unit-Tests): der Test ist neu, das Rezept steht in `scripts/exchange_evidence.py:150-152` (`occ()` = `docker exec -u www-data <nc> php occ`). Wie A-28-09: CI läuft erst nach Push, lokaler nc35-Beweis steht im Rohprotokoll.

## Frage 5: Doku-Inventar

### Die neun Grenzen aus D-29-05 mit Befundquelle

| # | Grenze | Wirkung (ein Satz, Kern) | Befund (Datei, Stelle) |
|---|---|---|---|
| 1 | Freigabe-Grenze | Ein Tag auf einem Vorfahren beim Eigentümer ist für den Empfänger einer Unterordner-Freigabe unsichtbar, der Ordner erscheint dort ungeschützt; ein Tag auf dem geteilten Knoten selbst wirkt | `25-MESSBERICHT.md` Zeile 73 (K5 Freigabe-Grenze), Ableitung Zeile 227; Rohwert `raw/nc35-befunde.txt` ab Zeile 162 (`== freigabe ==`) |
| 2 | Unsichtbares Tag wirkt nicht | Für Nicht-Admins existiert ein unsichtbares Tag nicht (412, nicht gelistet), es filtert nur in Admin-Sitzungen | `25-MESSBERICHT.md` Zeile 70 (K5), Zeile 71 (Variante Z), Zeile 219; `raw/nc35-befunde.txt:124-136` |
| 3 | App-aus-Verhalten | Nach `app:disable systemtags` antwortet die Tag-Abfrage weiter mit Treffern, der Connector filtert weiter; weg sind Suchprovider, Capability (32 bis 34 erst nach Neustart, APCu) und `tag:files:*`, Nutzer können also keine Tags mehr setzen | `25-MESSBERICHT.md` Zeilen 22-25 (K1), Ableitung Zeile 217; `raw/nc35-befunde.txt` ab Zeile 175, `raw/matrix-3{2,3,4}.txt` |
| 4 | Timing-Orakel | Ein getaggtes Objekt kostet eine Tag-Abfrage mehr als ein fehlendes, die Antwortzeit kann das verraten; keine künstliche Verzögerung | `28-CONTEXT.md` Zeile 39 (D-28-12); `28-SECURITY.md` Zeile 161 (A-28-06); Test `tests/unit/test_pair_equality_files.py:584-588` |
| 5 | `search` im Ausfall | ChatGPT-`search` liefert bei nicht prüfbarem Tag weniger Treffer, ohne das zu melden; nichts Getaggtes kommt durch | `28-CONTEXT.md` Zeile 42 (D-28-13); `28-SECURITY.md` Zeile 163 (A-28-08) |
| 6 | `notes_create`-Restorakel | Eine nicht existente Kategorie wird angelegt, eine getaggte abgewiesen; daran ist die Existenz eines getaggten Ordners erkennbar | `28-CONTEXT.md` Zeile 47 (D-28-16); `28-SECURITY.md` Zeile 162 (A-28-07); Pin `tests/unit/test_pair_equality_apps.py:554-568`; verwandt `tools/notes.py:237-238` |
| 7 | Drittanbieter-Suchprovider | Ein Provider, der Dateien ohne fileId, Pfad oder `/f/<id>`-Link nennt, wird nicht geprüft (Laufzeit fail-open) | `28-REVIEW.md` Zeilen 137-143 (WR-02), 79, 224 (Owner decision); Gate `tests/contract/test_provider_classes.py` |
| 8 | Tables-Freitext `/f/<id>` | Freitextzellen mit `/f/<id>`-Adresse bleiben unberührt, nur Link-Objekte werden geprüft | `28-REVIEW.md` Zeilen 145-157 (WR-03), 81, 226; `28-CONTEXT.md` Zeile 53 (D-28-18); `28-SECURITY.md` Zeile 158 (A-28-03) |
| 9 | Talk-Datei-Raum-Orakel (IN-02) | Fällt die Pfadsuche aus, unterscheidet sich die Antwort für einen Datei-Raum von der für ein erfundenes Token | `28-REVIEW.md` Zeilen 204-208 (IN-02), 226 |

### Weitere Grenzen, die Code und Security-Audit ausdrücklich "Phase 29" zuweisen (nicht in D-29-05 aufgezählt)

D-29-05 sagt "alle Grenzen einzeln"; `28-SECURITY.md` H-4 (Zeile 184-186) verlangt, dass das Phase-29-Audit diese Punkte in der Doku nachweist. Empfehlung: aufnehmen (Open Question O3, kurze Owner-Bestätigung):

| Grenze | Quelle |
|---|---|
| SQLite mit vielen Tag-Zuordnungen: REPORT ~240 s schon bei einem Treffer, Guard praktisch immer "nicht prüfbar", Dateieinträge werden zurückgehalten (fail-closed) | `25-MESSBERICHT.md` Zeile 271, 341, 355 (Owner-Entscheid E3); `nextcloud/exclusion.py:39-40` |
| Upload-Restorakel bei direkt getaggter Datei (T-27-16) | `27-SECURITY.md` Zeile 62/127 (A-27-03); `tools/files.py:718-727` |
| Tables und Talk ohne eigene Sandbox, nur Tag | `28-SECURITY.md` Zeile 159 (A-28-04); `tools/tables.py:481-483`; `tools/talk.py:224-226` |
| Fremdtext mit Dateinamen (eingetippt, Rich-Text, Deck-Beschreibung) | `28-SECURITY.md` Zeile 158 (A-28-03) |
| Liegengebliebener Upload-Staging-Ordner (kein Orakel, Aufräum-Merker) | `28-CONTEXT.md` Zeile 55 (D-28-20); `tests/unit/test_files_upload_exclusion.py:230-237` |
| `talk-conversations`-Treffer: zwei Regeln (unbekanntes Token zurückgehalten, unlesbare Liste hält alle zurück) | `28-CONTEXT.md` Zeilen 56-57 (D-28-21) |
| Ein Wortlaut bei "nicht prüfbar" (`exclusion check unavailable`) | `27-CONTEXT.md` Zeile 23 (D-27-05) |
| Admin-Sitzungen sehen unsichtbare Tags, also filtert ein unsichtbares Tag nur für Admins | Folgerung aus Zeile 70 Messbericht + `SystemTagsByIdCollection.php:102-111` |
| MySQL/MariaDB nicht gemessen | `25-MESSBERICHT.md` Zeile 309, 327 |

**Verweisform:** `.planning/` ist im öffentlichen Repo versioniert (`git ls-files .planning` = 359 Dateien, Messbericht und `raw/` enthalten). D-25-06 (`25-CONTEXT.md` Zeile 28) sagt: Rohdaten bleiben intern, Nutzerrelevantes wandert in Phase 29 kuratiert nach docs/. Also: der Grenzsatz steht kuratiert in docs/, der Verweis ist ein relativer Link `../.planning/phases/25-mess-spike-tag-abfrage/25-MESSBERICHT.md` mit Befundname (z. B. "K5, Freigabe-Grenze"), keine Zeilennummern im Linktext (Zeilen verschieben sich).

### occ-Befehle für die Anleitung (NC 35, gegen Quelltext geprüft)

| Schritt | Befehl | Status |
|---|---|---|
| Tag public anlegen | `php occ tag:add kein-ki public --output=json` → `{"id":…,"name":"kein-ki","access":"public"}` | [VERIFIED: `core/Command/SystemTag/Add.php` stable35 + Projekt nutzt es in `tests/integration/canary_world.py:270`] |
| Tag restricted anlegen | `php occ tag:add kein-ki restricted --output=json` | [CITED: Add.php, `restricted` = visible, nicht assignable] |
| Zugriffsstufe nachträglich ändern | `php occ tag:edit <id> --access=restricted` (auch `--name`, `--color`) | [CITED: Edit.php] |
| Tags auflisten | `php occ tag:list --output=json` (Admin-Sicht inkl. unsichtbar; `--visibilityFilter=1`) | [CITED: ListCommand.php] |
| Ordner taggen | `php occ tag:files:add <fileid-oder-pfad> kein-ki public` | [CITED: `apps/systemtags/lib/Command/Files/Add.php`]; Pfadform (`/alice/files/Ordner`) live prüfen (M7); Falle: `access` muss zur Stufe des bestehenden Tags passen, sonst wirft `getTag` (P7) |
| Gruppe anlegen, Mitglied | `php occ group:add ki-verantwortung`, `php occ group:adduser ki-verantwortung alice` | [ASSUMED: Standard-occ, live in M8] |
| **Gruppen-Delegation** | **Es gibt kein occ-Kommando dafür** (NC 35 `core/Command/SystemTag/` hat nur Add, Delete, Edit, ListCommand; `tag:edit` kennt keine Gruppen) [VERIFIED: GitHub-API-Verzeichnisliste stable35]. Wege: Web-UI (Admin-Einstellungen, Collaborative tags, M9) oder WebDAV als Admin: |
| | `curl -u admin:<app-passwort> -X PROPPATCH "https://cloud.example.com/remote.php/dav/systemtags/<id>" -H "Content-Type: application/xml" --data '<?xml version="1.0"?><d:propertyupdate xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns"><d:set><d:prop><oc:groups>ki-verantwortung</oc:groups></d:prop></d:set></d:propertyupdate>'` (mehrere Gruppen mit `|`) | [CITED: `SystemTagPlugin.php` PROPPATCH `GROUPS_PROPERTYNAME`, `explode('|')`]; live M8 |
| | oder in einem Schritt: `curl -u admin:<app-passwort> -X POST "https://cloud.example.com/remote.php/dav/systemtags/" -H "Content-Type: application/json" -d '{"name":"kein-ki","userVisible":true,"userAssignable":false,"groups":"ki-verantwortung"}'` | [CITED: `SystemTagPlugin::createTag`, Gruppen nur für Admin]; live M8 |
| Tag-Anlage auf Admins beschränken (empfohlen im Organisationsmodus, verhindert Nutzer-Varianten wie "Kein KI") | `php occ config:app:set systemtags restrict_creation_to_admin --value=true --type=boolean` | Schlüssel [CITED: `SystemTagManager::canUserCreateTag` Zeile 397]; Syntax `--type=boolean` [ASSUMED], live M8 |
| Kontrolle | `php occ mcp_connector:exclusion:check --admin=<uid>` und `--json` | neu, Rohbeleg M5 |

Wirkung der Betriebsarten (für die Doku, Quelltext): public: jeder Nutzer, der die Datei sieht, darf `kein-ki` setzen UND entfernen (`canUserAssignTag` früher Rückgabewert true); restricted: nur Admins und Mitglieder der delegierten Gruppen (Schnittmenge `getUserGroupIds` ∩ `getTagGroups`); Umbenennen/Löschen eines Tags per WebDAV nur Admin (`SystemTagNode::update`/`delete`). Ohne `restrict_creation_to_admin` darf jeder Nutzer neue Tags anlegen, also auch Varianten.

## Standard Stack

Keine neuen Abhängigkeiten. Alles mit vorhandenen Bausteinen:

| Baustein | Version | Zweck |
|---|---|---|
| starlette Route/Request/Response | wie `exchange_check.py` | Handler |
| httpx (Projekt-Client `nextcloud/http.shared_client`) | 0.28.x | PROPFIND |
| lxml | vorhanden | PROPFIND-Body bauen und Antwort parsen (`oc:groups`-Propstat-Status, `nc:object-id`-Zählung) |
| `unicodedata` (stdlib) | 3.13 | Normalform |
| respx, pytest | vorhanden | Unit/Contract |

**Achtung Parser:** `xml.parse_multistatus` verwirft nicht-2xx-Propstats (`clients/xml.py:97-101`) und liefert für verschachtelte Eigenschaften nur Kind-Tag-Namen (`_value_of`, Zeile 104-109). Für "403 auf `oc:groups`" und "Anzahl `nc:object-id` vom Typ files" braucht der neue Client einen eigenen lxml-Durchlauf (kein Regex, kein Stringzählen).

## Package Legitimacy Audit

Die Phase installiert keine externen Pakete. slopcheck nicht erforderlich. **Packages removed:** none. **Packages flagged:** none.

## Architecture Patterns

### Datenfluss

```
Admin-Shell: php occ mcp_connector:exclusion:check --admin=<uid> [--json]
      │
      ▼
AppAPI (PHP) baut Symfony-Befehl ── POST /exclusion-check {"occ":{"options":{...}}} (ohne Nutzer, PublicFunctions)
      │
      ▼
ExApp Handler ── Guard: x-origin-ip? → 404 ; AppAPI-Header ungültig? → 401
      │
      ├─ kein --admin → benanntes Ergebnis admin_not_named (200)
      ▼
Impersonation <uid> ── Admin-Nachweis (M2) ── nein → benanntes Ergebnis (200)
      │
      ▼
PROPFIND Depth 1 /systemtags/ (id, display-name, user-visible, user-assignable, groups)
      │
      ▼
reine Klassifikation: exact (is_exclude_name) / variant (Normalform) / similar
      │
      ▼
je exaktem Tag und Variante: PROPFIND Depth 0 /systemtags/<id> nc:object-ids → nur Anzahl type=files
      │
      ▼
Urteil + Betriebsart → Text (Kopf, eine Zeile je Schritt, Grenzsatz) oder JSON {checked, passed, mode, ...} → immer 200
```

### Modulzuschnitt

```
src/mcp_connector/
├── exapp/exclusion_check.py        # Route, Guard, Payload, Text/JSON (Kopie exchange_check)
├── exapp/occ.py                    # 5. Schema, Konstanten
├── nextcloud/clients/systemtags.py # + list_tag_details(), count_tag_objects() (policy-frei)
└── nextcloud/exclusion_audit.py    # reine Funktion: classify(tags, counts) -> CheckResult (oder in exclusion.py)
tests/unit/test_exapp_exclusion_check.py
tests/unit/test_exclusion_audit.py
tests/integration/test_exclusion_check_live.py
scripts/exclusion_evidence.py       # Rohbeleg + Tabellen-Diff, Muster exchange_evidence.py
docs/exclusion.md, docs/exclusion.de.md, docs/exclusion.fr.md
tests/unit/test_docs_exclusion_truth.py
```

### Anti-Patterns
- **REPORT im Prüfkommando:** zählt nur die Dateien des impersonierten Kontos und ist auf SQLite mit vielen Zuordnungen minutenlang (`25-MESSBERICHT.md` Zeile 271). `nc:object-ids` nehmen.
- **Depth-1-PROPFIND mit `nc:object-ids` über alle Tags:** berechnet die Ids jedes Tags der Instanz (Ballast-Tags mit 10.000 Zuordnungen). Nur Depth 0 je relevanter Id.
- **Eigene "exakt"-Regel:** würde vom Guard abdriften; immer `is_exclude_name`.
- **Ids, Pfade oder Konten in Ausgabe oder Log:** D-29-02; Log-Zeile nur `passed`, `mode`, Zahlen.
- **Exit-Code oder HTTP-Status als Verdikt:** AppAPI verwirft Nicht-200-Bodies.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---|---|---|---|
| Guard, Body, Flags | neue Logik | wörtliche Kopie aus `exchange_check.py` + Gleichheitstest | gemessen gegen app_api 34.0.3/35.0.0 |
| XML bauen/parsen | Strings, Regex | lxml wie `systemtags.py:89-114` | T-01-11 |
| Admin-Erkennung | Gruppenlisten selbst auswerten | Nextclouds eigene Admin-Prüfung über `oc:groups`-Zugriff oder `cloud/groups/admin/users` (M2) | genau das Prädikat, das die Tag-Sichtbarkeit steuert |
| DB-Diff | sqlite3-CLI im Container | PHP-QueryBuilder-Schnipsel (`tag_spike.py`) | DB-agnostisch, Präfix |
| Unicode-Normalisierung | eigene Ersetzungstabellen | `unicodedata.normalize("NFKC")` + Kategorien | deckt alle Strich- und Leerzeichenarten |

## Common Pitfalls

### P1: Leerer Nutzer statt Impersonation
**What goes wrong:** Handler ruft WebDAV im App-Kontext, bekommt 401 oder nur public-Tags, meldet "kein Tag" (passed=true) bei unsichtbarem Tag. **How to avoid:** O1, M1; ohne Admin-Nachweis kein Urteil.

### P2: `oc:groups`-403 kippt die ganze PROPFIND
**What goes wrong:** Bei Nicht-Admin könnte `Forbidden` aus dem Property-Handler die gesamte Antwort statt nur ein Propstat betreffen. **How to avoid:** M2 entscheidet Kandidat a oder b; Parser liest Propstat-Status.

### P3: Variante "Kein-KI" fälschlich als Fehler
**What goes wrong:** Groß/Klein-Abweichung wird gemeldet, obwohl der Guard sie erfasst. **How to avoid:** "exakt" = `is_exclude_name`; Unit-Test mit "Kein-KI", " kein-ki ", "KEIN-KI".

### P4: Zählung als Liste oder nutzergefiltert
**What goes wrong:** `nc:files-assigned` (-1) oder REPORT (nur eigene Dateien) liefert falsche Zahl; oder Ids landen im Log. **How to avoid:** `nc:object-ids`, nur `len()` der `files`-Einträge; Test, dass keine Id in Text/JSON/Log steht.

### P5: Doku verspricht, was nicht gemessen ist
**What goes wrong:** Satz zu MariaDB, zu UI-Menüs oder zu `--type=boolean` ohne Beleg. **How to avoid:** jede Befehlszeile der Anleitung steht im Rohbeleg (D-29-08); Unbelegtes als solches kennzeichnen.

### P6: Gedankenstriche/ASCII-Umlaute in DE-Doku
**How to avoid:** Doku-Wahrheitstest prüft U+2013/U+2014 in allen drei Seiten und READMEs.

### P7: `tag:files:add` mit abweichender Zugriffsstufe
**What goes wrong:** `tag:files:add <pfad> kein-ki public` auf ein bestehendes restricted-Tag: `createTag` wirft "exists", `getTag(name, true, true)` findet nichts und wirft (`apps/systemtags/lib/Command/Files/Add.php`). **How to avoid:** Doku nennt die Stufe passend zum Tag.

### P8: Store-Text versehentlich angefasst
**What goes wrong:** Beim Ergänzen des Kommentarblocks in `appinfo/info.xml` ändert sich `<description>`. **How to avoid:** Beleg/Test extrahiert alle `<summary>`/`<description>` (3 Sprachen) aus `git show ca157b4:appinfo/info.xml` und HEAD und vergleicht; leerer Diff als Rohbeleg (Erfolgskriterium 4).

### P9: Lifecycle-Zähltest und Doku-Zahlen
`test_exapp_lifecycle.py:536` erwartet `len(schemes) == 4`; `occ.py:3` sagt "Four of them"; der info.xml-Kommentar zählt "deliberately absent paths". Alles auf fünf bzw. acht nachziehen.

## Code Examples

### Listing-Body (lxml, Muster `systemtags.py:105-114`)
```python
def _details_body() -> bytes:
    root = etree.Element(f"{{{xml.DAV}}}propfind", nsmap={"d": xml.DAV, "oc": xml.OC, "nc": xml.NC})
    prop = etree.SubElement(root, f"{{{xml.DAV}}}prop")
    for name in ("id", "display-name", "user-visible", "user-assignable", "groups"):
        etree.SubElement(prop, f"{{{xml.OC}}}{name}")
    return etree.tostring(root, xml_declaration=True, encoding="utf-8")
```

### Zählung ohne Ids
```python
# PROPFIND Depth 0 {base}/remote.php/dav/systemtags/{tag_id} with <nc:object-ids/>
count = sum(
    1
    for obj in root.iter(f"{{{xml.NC}}}object-id")
    if (obj.findtext(f"{{{xml.NC}}}type") or "").strip() == "files"
)
```

## State of the Art

| Alt | Aktuell | Seit | Wirkung |
|---|---|---|---|
| Groß/Klein-Duplikate möglich | `createTag` verweigert sie (`mb_strtolower`) | NC 32 laut `exclusion.py:81-83` | Varianten entstehen v. a. durch Leerzeichen/Striche |
| Gruppen nur über UI | WebDAV PROPPATCH `oc:groups` / POST mit `groups` | vorhanden NC 32 bis 35 | copybarer curl-Weg für Behörden-Admins |
| Tag-Anlage für alle | Schalter `restrict_creation_to_admin` | im Code NC 35 vorhanden; Einführungsversion [ASSUMED] | Organisationsmodus härten |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|---|---|---|
| A1 | WebDAV `/systemtags/` mit leerem AppAPI-Nutzer antwortet 401 | Frage 2 | gering: dann trotzdem nur public sichtbar, O1 bleibt nötig |
| A2 | Impersonierter Admin sieht unsichtbare Tags und `oc:groups` wie Basic-Admin | Frage 2 | hoch: sonst kein Weg zum Unsichtbar-Befund; M2 vor Implementierung |
| A3 | `cloud/groups/admin/users` trennt Admin/Nicht-Admin per 200/403 | Frage 2 | mittel: Kandidat a nehmen |
| A4 | `nc:object-ids` enthält auch Zuordnungen von Papierkorb-Dateien | Frage 2/Doku | gering: nur Doku-Satz (M4) |
| A5 | `config:app:set ... --type=boolean` ist die richtige Syntax für `restrict_creation_to_admin` | Frage 5 | gering: M8 |
| A6 | Pfadform `/alice/files/Ordner` für `tag:files:add` | Frage 5 | gering: M7 |
| A7 | UI-Ort "Collaborative tags" in den Admin-Einstellungen | Frage 5 | gering: M9 |
| A8 | `group:add`/`group:adduser` Syntax | Frage 5 | gering: M8 |

## Open Questions

1. **O1 Identität:** Option `--admin=<uid>` (Empfehlung) gegenüber automatischer Admin-Suche. Was wir wissen: occ ruft ohne Nutzer, leerer Nutzer sieht keine unsichtbaren Tags. Empfehlung: Option, Owner bestätigt beim Planen.
2. **O2 Variante neben exaktem Tag:** `passed=false` (Empfehlung) oder Hinweis. Owner bestätigt.
3. **O3 Zusatzgrenzen:** die neun D-29-05-Punkte plus die H-4-Liste (SQLite, Upload-Restorakel, Tables/Talk ohne Sandbox, Fremdtext, Staging, D-28-21, Einheitswortlaut, Admin-Sicht unsichtbar, MariaDB). Empfehlung: alle aufnehmen, weil "alle Grenzen einzeln" und das Phase-29-Audit sie verlangt.
4. **O4 `restrict_creation_to_admin` im Prüfkommando melden?** Lesbar nur als Admin über OCS-Provisioning; Nutzen: warnt, dass Nutzer Varianten anlegen können. Empfehlung: nur Doku, nicht im Kommando (Scope schlank).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|---|---|---|---|---|
| uv | alle Tests | ✓ | 0.11.7 | , |
| Docker Desktop | nc35-Live-Messung M1 bis M9, Rohbelege | ✗ (Daemon zur Recherchezeit nicht gestartet) | , | vor der Live-Welle starten; CI-Job `canary-nc35` |
| `.env.nc35` | nc35-Harness | ✓ | , | , |
| nc35-Topologie (`compose.nc35.yml`, NC 35.0.0) | Live-Beleg | nicht geprüft (Docker aus) | , | CI 35.0.1 |

**Blockierend ohne Fallback:** keiner für Code und Unit-Tests; die Live-Belege (Erfolgskriterien 1, 2, D-29-08) brauchen Docker.

## Validation Architecture

(`workflow.nyquist_validation` ist `false`; Abschnitt auf Wunsch des Auftraggebers als Testzuordnung.)

| Erfolgskriterium / Req | Verhalten | Typ | Befehl | Datei |
|---|---|---|---|---|
| SK1 / OPS-01 | Klassifikation: kein Tag (passed, Hinweis), public, restricted mit/ohne Gruppen, invisible (failed), nur Variante (failed), exakt+Variante, "Kein-KI" ist exakt, similar nur Hinweis | unit | `uv run pytest tests/unit/test_exclusion_audit.py -q` | neu |
| SK1 / OPS-01 | Handler: alle Schritte in beiden Formen, immer 200, JSON `passed`/`mode`/`assigned`, keine Ids/Pfade in Text/JSON/Log, Ausfälle (401 von NC, 5xx, Timeout, unparsbar) als benannte Ergebnisse | unit (respx) | `uv run pytest tests/unit/test_exapp_exclusion_check.py -q` | neu |
| SK2 / OPS-01 | nur PROPFIND (ggf. GET) geht hinaus; kein Audit-Eintrag; Guard 404/401; Pfad in keinem `<url>` | unit/contract | wie oben | neu |
| SK1 | Schema Nr. 5, Handler abgeleitet, Modi-Positivliste, Beschreibung ≤ 255 | unit | `uv run pytest tests/unit/test_exapp_lifecycle.py -q` | anpassen |
| SK1 | Route im gebauten App, 200, Proxy 404 | unit | `uv run pytest tests/unit/test_exapp_entry.py -q` | anpassen |
| SK1 + SK2 live | Fälle A bis F gegen echte Instanz, Tabellen-Diff leer je Fall | integration | `uv run pytest tests/integration/test_exclusion_check_live.py -m integration -s` (lokal mit `NC_MCP_E2E_*`-Exporten aus `topology.py:19-24`, `PYTHONUTF8=1`) | neu |
| D-29-08 | Rohbeleg der Anleitung und Kommandoausgaben | Skript | `uv run python scripts/exclusion_evidence.py --nc35` → `.planning/phases/29-pr-fkommando-und-doku/raw/` | neu |
| SK3 / DOC-03 | drei Seiten existieren, jede nennt alle Grenzen (stabile Anker), alle relativen Links lösen auf, Kommandoname = Konstante, README-Abschnitt in drei Sprachen verlinkt die Seite der Sprache, keine U+2013/U+2014 | unit | `uv run pytest tests/unit/test_docs_exclusion_truth.py -q` | neu |
| SK4 | `<summary>`/`<description>` in drei Sprachen gleich dem Stand `ca157b4` | unit + Rohbeleg | im Doku-Wahrheitstest oder `git show ca157b4:appinfo/info.xml` Vergleich | neu |
| Gate | ruff, format, pyright, vulture, unit+contract | CI `unit` | `uv run ruff check . && uv run ruff format --check . && uv run pytest tests/unit tests/contract` | vorhanden |

## Security Domain

| ASVS | Applies | Control |
|---|---|---|
| V2 Authentication | ja | AppAPI-Header über `require_appapi` (vorhanden) |
| V4 Access Control | ja | Pfad nicht im Manifest, `x-origin-ip` → 404 (T-02-20, T-24-27); Impersonation nur für eine ausdrücklich genannte, als Admin nachgewiesene uid |
| V5 Input Validation | ja | `--admin` als Wert aus fremder Eingabe: strip, Länge begrenzen, nie ungeprüft in URL (quote), Body ≤ 4 KB |
| V7 Logging | ja | Log nur `passed`, `mode`, Zahlen; nie uid-Header, Ids, Pfade |
| V6 Cryptography | nein | , |

| Threat | STRIDE | Mitigation |
|---|---|---|
| Orakel über den PHP-Proxy (Tag-Namen, Gruppen der Instanz abfragen) | Information Disclosure | kein `<url>`, Doppel-Guard, Test "in keinem url" |
| Missbrauch der Impersonation | Elevation of Privilege | nur lesende PROPFIND, Contract-Test auf Methoden; AppAPI-Impersonationslog |
| Datei-/Kontodaten in Ausgabe | Information Disclosure | nur Zahlen (D-29-02), Test über Text/JSON/Log |
| Fehlurteil "grün" bei Ausfall | Tampering/Repudiation | jeder Nicht-207-Ausgang → benanntes Ergebnis, `passed=false`, nie "kein Tag" |

## Sources

### Primary (HIGH)
- Codebase: `src/mcp_connector/exapp/exchange_check.py`, `exapp/occ.py`, `entry_exapp.py`, `nextcloud/exclusion.py`, `nextcloud/clients/systemtags.py`, `nextcloud/clients/xml.py`, `deps.py`, `audit/accounts.py`, `appinfo/info.xml`, `scripts/tag_spike.py`, `scripts/exchange_evidence.py`, `tests/integration/topology.py`, `.github/workflows/ci.yml`
- Befunde: `25-MESSBERICHT.md`, `raw/nc35-befunde.txt`, `26-CONTEXT.md`, `27-CONTEXT.md`, `27-SECURITY.md`, `28-CONTEXT.md`, `28-REVIEW.md`, `28-SECURITY.md`
- nextcloud/server stable35 (raw.githubusercontent.com): `apps/dav/lib/SystemTag/SystemTagPlugin.php`, `SystemTagsByIdCollection.php`, `SystemTagNode.php`, `SystemTagsInUseCollection.php`, `SystemTagsObjectList.php`, `SystemTagObjectType.php`, `lib/private/SystemTag/SystemTagManager.php`, `SystemTagObjectMapper.php`, `core/Command/SystemTag/{Add,Edit,ListCommand}.php`, `apps/systemtags/lib/Command/Files/Add.php`, `lib/public/Util.php`; stable32 `SystemTagPlugin.php` zum Abgleich
- nextcloud/app_api main: `lib/Service/AppAPIService.php`, `lib/DavPlugin.php`, `lib/Service/ExAppOccService.php`, `lib/Controller/OCSApiController.php`, `appinfo/routes.php`

### Tertiary (LOW, live zu prüfen)
- Verhalten unter Impersonation (M1, M2, M2b), Papierkorb-Zählung (M4), Syntax `--type=boolean`, UI-Menüpfad

## Metadata

**Confidence breakdown:**
- Verdrahtung/Muster: HIGH (Code mit Zeilen gelesen)
- Nextcloud-APIs: HIGH für Quelltextverhalten, MEDIUM für Impersonation bis M2
- Varianten: HIGH (Guard-Regel + NC-Anlagelogik verifiziert)
- Doku-Inventar: HIGH (alle Quellen mit Zeilen)
- occ-Befehle: HIGH für tag:*, MEDIUM für Gruppen-Delegation (kein occ, curl-Weg aus Quelltext, live M8)

**Research date:** 2026-10-01
**Valid until:** 2026-10-31 (NC 35.x stabil; bei NC 36 erneut prüfen)
