# Messbericht Phase 25: Mess-Spike Tag-Abfrage

**Status:** Messung abgeschlossen, Owner-Entscheid vom 2026-09-26 eingetragen (Checkpoint 25-04, D-25-05); Batch-Entscheid E3 offen bis Zusatzplan 25-05
**Gemessen:** 2026-09-26, 17:28Z bis 18:43Z (UTC)
**Ablage:** intern (D-25-06), nichts davon unter docs/
**NC-Versionen (Version of record laut `occ status`):** 32.0.15, 33.0.9, 34.0.4 (je Wegwerf-Instanz), 35.0.0 (nc35-Strecke)
**Datenbank:** sqlite3 auf allen vier Versionen
**memcache.local:** nc35 nicht gesetzt; 32/33/34 `\OC\Memcache\APCu` (Vorgabe des offiziellen Images)
**Topologie:** nc35 über Caddy auf 127.0.0.1:8082 (Container nc35-nc, nc35-harp, nc35-caddy, ExApp nc_app_mcp_connector 0.2.1); Wegwerf-Instanzen nc-spike-tags auf 127.0.0.1:8083, nacheinander, nie zwei gleichzeitig
**Messskript:** `scripts/tag_spike.py`, Stand Commit e3153a4 (letzte Änderung, 25-03); Blöcke controls, findings, latency, ballast-remeasure, teardown, matrix, secret-scan
**Umfang:** fünf Erfolgskriterien der Phase: (K1) App aus auf 32 bis 35, (K2) REPORT unter AppAPI-Impersonation, (K3) Kosten bei 1/100/5000 getaggten Knoten, (K4) Notiz-Id gegen fileid, (K5) Einzelbefunde 412, unsichtbares Tag, gleichnamige Varianten, Zielpfad, Freigabe-Grenze
**Rohdateien:** `raw/nc35-befunde.txt`, `raw/nc35-latenz.txt`, `raw/nc35-prepare-context-baseline.txt`, `raw/nc35-prepare-context-mit-daten.txt`, `raw/matrix-32.txt`, `raw/matrix-33.txt`, `raw/matrix-34.txt`

Jede Zahl unten stammt aus einer dieser Dateien. Was dort nicht gemessen steht, wird nicht behauptet.

## Befundtabelle

### K1: App systemtags aus (app:disable)

| Befund | Kommando | Rohwert | Deutung | Rohdatei |
|---|---|---|---|---|
| App aus, NC 32.0.15 | `occ app:disable systemtags`, danach Capabilities, Suchprovider, PROPFIND /systemtags/, REPORT, PROPFIND mit nc:system-tags, `occ list`; dasselbe nach `docker restart` | `APP-AUS REPORT nachher status=207 treffer=2`; `APP-AUS-NEUSTART REPORT nachher status=207 treffer=2`; sofort: Capability und Suchprovider bleiben; nach Neustart: `Capability ... nachher=fehlt`, `Suchprovider ... nachher=systemtags=nein`; `tag:files:*` fehlen sofort; PROPFIND /systemtags/ und nc:system-tags unverändert 207 | REPORT antwortet unverändert mit Treffern. Weg sind nur Capability, Suchprovider (erst nach Neustart, APCu) und `tag:files:*`; es bleiben PROPFIND /systemtags/ und nc:system-tags | raw/matrix-32.txt |
| App aus, NC 33.0.9 | wie 32 | `APP-AUS REPORT nachher status=207 treffer=2`; `APP-AUS-NEUSTART REPORT nachher status=207 treffer=2`; Capability/Suchprovider sofort vorhanden, nach Neustart fehlend | gleich wie 32 | raw/matrix-33.txt |
| App aus, NC 34.0.4 | wie 32 | `APP-AUS REPORT nachher status=207 treffer=2`; `APP-AUS-NEUSTART REPORT nachher status=207 treffer=2`; Capability/Suchprovider sofort vorhanden, nach Neustart fehlend | gleich wie 32 | raw/matrix-34.txt |
| App aus, NC 35.0.0 | `occ app:disable systemtags`, dieselben fünf Messpunkte (ohne Neustart, kein APCu) | REPORT `[App aus] HTTP 207 treffer=1 fileids=['974']`; Capability `systemtags=fehlt`; Suchprovider `systemtags=nein`; `occ list` ohne `tag:files:*`; PROPFIND /systemtags/ 207 `tag 71 gelistet=ja`; nc:system-tags `['kein-ki-spike25-app']` | REPORT antwortet unverändert; Capability und Suchprovider verschwinden sofort (kein memcache.local) | raw/nc35-befunde.txt |

### K2: Impersonation

| Befund | Kommando | Rohwert | Deutung | Rohdatei |
|---|---|---|---|---|
| REPORT Basic gegen AppAPI gegen Produktionsweg | REPORT systemtag=60 auf / als alice mit App-Passwort, mit AppAPI-Headern, und aus dem ExApp-Container gegen http://caddy | `IMPERSONATION fileids_basic=3 fileids_appapi=3 gleich=ja | basic=['937', '938', '939'] appapi=['937', '938', '939']`; `IMPERSONATION produktionsweg fileids=3 gleich_basic=ja` | Der REPORT liefert unter Impersonation dieselbe fileid-Menge; keine Abweichung, keine Rohantwort nötig | raw/nc35-befunde.txt |
| Kontrollen a/b/c | a: GET cloud/user über AppAPI; b: dasselbe mit falschem Secret; c: exapp_impersonation.log | a `id=alice erwartet=alice gleich=ja`; b `HTTP 401 abgelehnt=ja`; c `REPORT-Zeilen von alice seit 2026-09-26T17:29:58Z: 1` | Die Impersonation wirkte wirklich als alice, ein falsches Secret wird abgelehnt, der REPORT lief nachweislich über den Impersonationsweg | raw/nc35-befunde.txt |

### K3: Kosten (nc35, SQLite, 20.000 Spike-Dateien, n=15 nach 3 Aufwärmläufen)

| Befund | Kommando | Rohwert | Deutung | Rohdatei |
|---|---|---|---|---|
| Stufe 1 | REPORT kein-ki-spike25-lat, 1 Knoten (1 Ordner) | `status=207 treffer=1 bytes=459 median=59 p95_zweitgroesster=63 max=74 (ms)` | billig | raw/nc35-latenz.txt |
| Stufe 100 | REPORT, 100 Knoten (99 Dateien, 1 Ordner) | `status=207 treffer=100 bytes=25722 median=243 p95_zweitgroesster=273 max=273 (ms)` | unter 1 s | raw/nc35-latenz.txt |
| Stufe 5000 | REPORT, 5000 Dateien | `status=207 treffer=5000 bytes=1276122 min=8280 median=8848 p95_zweitgroesster=10117 max=10582 (ms)` | weit über 1 s; Wachstum überlinear (59 zu 243 zu 8.848 ms) | raw/nc35-latenz.txt |
| Stufe 5000 kalt | 3 Läufe, vor jedem `apachectl -k graceful` + 5 s Pause | `KALT STUFE 5000 min=8265 median=8563 max=8649 (ms, n=3)` | kalt gleich warm: die Zeit steckt nicht im OPcache, sondern in der Abfrage | raw/nc35-latenz.txt |
| Referenz a | PROPFIND Depth 1 /remote.php/dav/systemtags/ | `status=207 treffer=2 bytes=572 median=48` | Tag-Liste billig | raw/nc35-latenz.txt |
| Referenz c | PROPFIND Depth 1 /spike25/flat/ ohne nc:system-tags | `treffer=10001 bytes=2830499 median=336 max=400` | Riesenordner lesen: 0,34 s | raw/nc35-latenz.txt |
| Referenz d | PROPFIND Depth 1 /spike25/flat/ mit nc:system-tags | `treffer=10001 bytes=3000516 median=346 p95_zweitgroesster=527 max=2135` | Tags je Eintrag mitlesen kostet kaum mehr (346 gegen 336 ms) | raw/nc35-latenz.txt |
| Referenz e | GET /status.php | `status=200 bytes=171 median=16` | Grundrauschen der Strecke | raw/nc35-latenz.txt |
| Stufe 5000 mit Ballast | 14 Füll-Tags auf je 10.000 Dateien (145.000 Zuordnungen), Reihe mit 60-s-Limit, dann Einzellauf mit 300 s | `ZEITLIMIT 60 s überschritten ... Reihe abgebrochen`; `EINZELLAUF zeitlimit=300 s status=207 treffer=5000 ms=249568` | Die Größe der Mapping-Tabelle verteuert den REPORT massiv (8,8 s auf 249,6 s) | raw/nc35-latenz.txt |
| Referenz d mit Ballast | PROPFIND /spike25/flat/ mit nc:system-tags bei stehendem Ballast | `treffer=10001 bytes=22620516 median=879 max=973` | PROPFIND mit Tags bleibt unter 1 s, auch mit Ballast | raw/nc35-latenz.txt |
| Ballast-Aufbau | setObjectIdsForTag je Füll-Tag, Grenze 600 s | `BALLAST abgebrochen nach 613 s bei 145000 Zuordnungen` | Geplant waren 30 bis 40 Füll-Tags (300k bis 400k); gemessen wurde bei 145.000 | raw/nc35-latenz.txt |
| prepare_context ohne Daten | `pytest tests/integration/test_ctx_bundle.py -m integration -s -k "wall_clock or measurement_protocol or no_measured_line"` | `detail='short': median 0.72 s`; `detail='full': median 0.81 s` | Wanduhr des Bündels | raw/nc35-prepare-context-baseline.txt |
| prepare_context mit Daten | dasselbe bei 20.000 Spike-Dateien und Ballast | `detail='short': median 0.72 s`; `detail='full': median 0.82 s` | Spike-Daten ändern die Wanduhr nicht messbar; der REPORT bei 5000 dauert gut das Zehnfache des ganzen Bündels | raw/nc35-prepare-context-mit-daten.txt |
| **Schwelle D-25-04** | Median warm Stufe 5000 gegen 1,0 s | `SCHWELLE D-25-04 median_warm_5000=8.848 s schwelle=1.0 s ergebnis=ueber`; mit Ballast `einzellauf=249.568 s ... ergebnis=ueber` | **Schwelle D-25-04: Median warm bei 5000 = 8,848 s gegen 1,0 s: über.** Die Ableitung stoppt, der Owner entscheidet (D-25-04) | raw/nc35-latenz.txt |

Nicht gemessen: Stufe 1 und Stufe 100 bei stehendem Ballast. Ob der Ballast auch kleine getaggte Mengen verteuert, ist offen.

### K4: Notiz-Id gegen fileid

| Befund | Kommando | Rohwert | Deutung | Rohdatei |
|---|---|---|---|---|
| Erste Notiz | POST notes/api/v1/notes, dann PROPFIND Depth 1 /Notes/spike25/ | `NOTES id=933 fileid=933 datei=spike25 Notiz.md gleich=ja`; `GET notes/api/v1/notes/933 ... dieselbe_notiz=ja` | Notiz-Id ist die fileid | raw/nc35-befunde.txt |
| Gegenprobe gleichnamige Notiz | zweiter POST mit gleichem Titel | `NOTES id=934 fileid=934 datei=spike25 Notiz (2).md gleich=ja` | gilt auch bei umbenannter Datei | raw/nc35-befunde.txt |
| Ordner-Tag | Kategorieordner /Notes/spike25 getaggt, REPORT auf / | `REPORT ... treffer=1 fileids=['932'] pfade=['/Notes/spike25']`; `NOTES REPORT ordner_fileid=932 im_treffer=ja notiz_ids_im_treffer=[]` | Der REPORT liefert die Ordner-fileid, keine Notiz-Ids; Notizen darunter erkennt man nur über den Pfad (Subtree-Regel) | raw/nc35-befunde.txt |
| **Antwort** | | `NOTIZ-ID GLEICH FILEID: ja` | **ja** | raw/nc35-befunde.txt |

### K5: Einzelbefunde

| Befund | Kommando | Rohwert | Deutung | Rohdatei |
|---|---|---|---|---|
| 412 unbekannte Id | REPORT systemtag=999999 | 35: `HTTP 412 ... fehler=Cannot filter by non-existing tag`; 32/33/34 gleich | Unbekannte Id ergibt 412, nicht 207 mit 0 Treffern | raw/nc35-befunde.txt, raw/matrix-32.txt, raw/matrix-33.txt, raw/matrix-34.txt |
| 412 gelöscht/neu | Tag anlegen (Id A), taggen, löschen, gleichnamig neu (Id B), REPORT auf A und B, PROPFIND /systemtags/ | 35: A=61 `HTTP 412`, B=62 `HTTP 207 treffer=1`, `A=61 gelistet=nein B=62 gelistet=ja`; 32/33/34: A=2 `HTTP 412`, B=3 `HTTP 207 treffer=1`, `A=2 gelistet=nein B=3 gelistet=ja` | Eine veraltete Id liefert 412 auf allen Versionen; einmal neu auflösen findet B | raw/nc35-befunde.txt, raw/matrix-32.txt, raw/matrix-33.txt, raw/matrix-34.txt |
| Unsichtbares Tag | Tag invisible, REPORT als alice und als temporärer Admin | alice `HTTP 412 ... Cannot filter by non-existing tag`, `Tag 63 in alices Liste=nein`; Admin `HTTP 207 treffer=1 fileids=['952']`, `Tag 63 in der Admin-Liste=ja` | Für Nicht-Admins existiert ein unsichtbares Tag nicht (412) | raw/nc35-befunde.txt |
| Gleichnamige Varianten | X public (64), Y restricted gleichnamig (65), Z invisible gleichnamig (66), W Groß/Klein anders (67); REPORT als alice | X `treffer=2 fileids=['955', '957']`; Y `treffer=2 fileids=['955', '957']`; W `treffer=1 fileids=['961']`; Z `HTTP 412` | Exakt gleichnamige X und Y liefern beide die Vereinigung; W (andere Schreibung) ist getrennt und muss eigens abgefragt werden; Z ist für alice unsichtbar. Gilt für SQLite (binärer Vergleich, Annahme A3) | raw/nc35-befunde.txt |
| Zielpfad | REPORT auf Home-Wurzel, auf Unterordner des getaggten Ordners, auf fremden Ordner | 35: alle drei `HTTP 207 ... fileids=['963']`, `ZIELPFAD filtert=nein`; 32/33/34: alle drei gleiche Menge, `ZIELPFAD filtert=nein` | Der Zielpfad filtert auf keiner Version; der REPORT liefert immer die ganze getaggte Menge des Nutzers | raw/nc35-befunde.txt, raw/matrix-32.txt, raw/matrix-33.txt, raw/matrix-34.txt |
| Freigabe-Grenze | Fall 1: Vorfahr beim Eigentümer getaggt, Unterordner an bob geteilt; Fall 2: geteilter Ordner selbst getaggt; REPORT als bob | Fall 1 bob `HTTP 207 treffer=0`, Gegenprobe alice `treffer=1 ['/spike25/share1']`; Fall 2 bob `HTTP 207 treffer=1 pfade=['/share2']` | Ein Tag auf einem Vorfahren beim Eigentümer ist für bob unsichtbar (Unterordner erscheint ungeschützt); ein Tag auf dem geteilten Knoten selbst sieht bob | raw/nc35-befunde.txt |

### Rückbau-Nachweis

| Befund | Rohwert | Rohdatei |
|---|---|---|
| nc35 nach findings | `BASELINE tags vorher=[] nachher=[] gleich=ja`; `dateien vorher=275 nachher=275 gleich=ja`; `papierkorb vorher=0 nachher=0 gleich=ja`; `mappings vorher=0 nachher=0 gleich=ja`; `RUECKBAU spike25admin vorhanden: nein` | raw/nc35-befunde.txt |
| nc35 nach latency/teardown | `RUECKBAU /spike25 vorhanden: nein`; `RUECKBAU Spike-Tags vorhanden: keine`; BASELINE dateien/mappings/papierkorb/tags je `gleich=ja` | raw/nc35-latenz.txt |
| Wegwerf-Instanzen | je Version `ABBAU Container vorhanden: nein`, `ABBAU Volume vorhanden: nein` | raw/matrix-32.txt, raw/matrix-33.txt, raw/matrix-34.txt |

## Rohauszüge

Auszüge unverändert aus den Rohdateien; Kürzungen sind mit `[...]` markiert, lange Zeilen am Ende gekürzt.

K1, App aus auf 32 (raw/matrix-32.txt; 33 und 34 zeilengleich):

```
== app-aus ==
occ app:disable systemtags -> systemtags 1.22.0 disabled
[...]
APP-AUS Capability vorher=vorhanden nachher=vorhanden
APP-AUS Suchprovider vorher=systemtags=ja nachher=systemtags=ja
APP-AUS PROPFIND-systemtags vorher=207/gelistet=ja nachher=207/gelistet=ja
APP-AUS REPORT vorher=207/treffer=2 nachher=207/treffer=2
APP-AUS REPORT nachher status=207 treffer=2
APP-AUS-NEUSTART Capability vorher=vorhanden nachher=fehlt
APP-AUS-NEUSTART Suchprovider vorher=systemtags=ja nachher=systemtags=nein
APP-AUS-NEUSTART PROPFIND-systemtags vorher=207/gelistet=ja nachher=207/gelistet=ja
APP-AUS-NEUSTART REPORT vorher=207/treffer=2 nachher=207/treffer=2
APP-AUS-NEUSTART REPORT nachher status=207 treffer=2
```

K1, App aus auf 35 (raw/nc35-befunde.txt):

```
== app-aus-35 ==
occ app:disable systemtags -> systemtags 2.0.0-dev.0 disabled
[...] | app-aus-35 | [App aus] GET /ocs/v1.php/cloud/capabilities | HTTP 200 | systemtags=fehlt
[...] | app-aus-35 | [App aus] PROPFIND Depth 1 /remote.php/dav/systemtags/ | HTTP 207 | 42 ms | eintraege=10 tag 71 gelistet=ja
[...] | app-aus-35 | REPORT systemtag=71 als alice (basic) auf / [App aus] | HTTP 207 | 41 ms | treffer=1 fileids=['974'] pfade=['/spike25/app/h.txt']
[App aus] occ list | tag: -> ['tag:add', 'tag:delete', 'tag:edit', 'tag:list']
```

K2, Impersonation (raw/nc35-befunde.txt):

```
== impersonation ==
IMPERSONATION fileids_basic=3 fileids_appapi=3 gleich=ja | basic=['937', '938', '939'] appapi=['937', '938', '939']
KONTROLLE c: exapp_impersonation.log, REPORT-Zeilen von alice seit 2026-09-26T17:29:58Z: 1
[...] | impersonation | REPORT aus dem ExApp-Container gegen http://caddy (AppAPI) | HTTP 207 | 207 3 937,938,939
IMPERSONATION produktionsweg fileids=3 gleich_basic=ja
```

K3, Kosten (raw/nc35-latenz.txt):

```
== stufen ==
STUFE 1 status=207 treffer=1 bytes=459 min=57 median=59 p95_zweitgroesster=63 max=74 (ms, n=15)
STUFE 100 status=207 treffer=100 bytes=25722 min=221 median=243 p95_zweitgroesster=273 max=273 (ms, n=15)
STUFE 5000 status=207 treffer=5000 bytes=1276122 min=8280 median=8848 p95_zweitgroesster=10117 max=10582 (ms, n=15)
== kalt ==
KALT STUFE 5000 min=8265 median=8563 max=8649 (ms, n=3)
== schwelle ==
SCHWELLE D-25-04 median_warm_5000=8.848 s schwelle=1.0 s ergebnis=ueber
== ballast nachmessung ==
STUFE 5000 (mit Ballast) EINZELLAUF zeitlimit=300 s status=207 treffer=5000 bytes=1276122 ms=249568
SCHWELLE D-25-04 (mit Ballast) median_warm_5000=nicht messbar (Reihe über 60 s abgebrochen), einzellauf=249.568 s schwelle=1.0 s ergebnis=ueber
```

Abweichung vom Rohformat: Der erste Ballast-Lauf endete mit `BLOCK FAILED | ballast | ReadTimeout:` (Werkzeugfehler); die Messung mit Ballast steht im angehängten Abschnitt `== ballast nachmessung ==` mit der Zeile `WIEDERHOLUNG Grund: ...`.

K4, Notizen (raw/nc35-befunde.txt):

```
== notes ==
NOTES id=933 fileid=933 datei=spike25 Notiz.md gleich=ja
NOTES id=934 fileid=934 datei=spike25 Notiz (2).md gleich=ja
[...] | notes | REPORT systemtag=59 als alice (basic) auf / [Notes-Kategorieordner getaggt] | HTTP 207 | 81 ms | treffer=1 fileids=['932'] pfade=['/Notes/spike25']
NOTES REPORT ordner_fileid=932 im_treffer=ja notiz_ids_im_treffer=[]
NOTIZ-ID GLEICH FILEID: ja
```

K5, Varianten, Zielpfad, Freigabe (raw/nc35-befunde.txt):

```
== varianten ==
[...] REPORT systemtag=64 [...] [Variante X] | HTTP 207 | 41 ms | treffer=2 fileids=['955', '957'] [...]
[...] REPORT systemtag=65 [...] [Variante Y] | HTTP 207 | 41 ms | treffer=2 fileids=['955', '957'] [...]
[...] REPORT systemtag=67 [...] [Variante W] | HTTP 207 | 41 ms | treffer=1 fileids=['961'] [...]
[...] REPORT systemtag=66 [...] [Variante Z] | HTTP 412 | 40 ms | fehler=Cannot filter by non-existing tag
== zielpfad ==
ZIELPFAD filtert=nein (getaggter Ordner fileid=963, Antworten je Zielpfad={'/': (207, ['963']), '/spike25/p/tagged/sub/': (207, ['963']), '/spike25/q/': (207, ['963'])})
== freigabe ==
[...] REPORT systemtag=69 als bob (basic) auf / [Fall 1: getaggter Vorfahr beim Eigentümer, Unterordner geteilt] | HTTP 207 | 54 ms | treffer=0 fileids=[] pfade=[]
[...] REPORT systemtag=70 als bob (basic) auf / [Fall 2: geteilter Ordner selbst getaggt] | HTTP 207 | 41 ms | treffer=1 fileids=['971'] pfade=['/share2']
```

K5, 412 auf 33 (raw/matrix-33.txt; 32 und 34 gleich):

```
== 412 ==
[...] REPORT systemtag=999999 als alice (basic) auf / [unbekannte Id] | HTTP 412 | 34 ms | fehler=Cannot filter by non-existing tag
[...] REPORT systemtag=2 als alice (basic) auf / [Id A=2 nach Loeschen und Neuanlage] | HTTP 412 | 34 ms | fehler=Cannot filter by non-existing tag
[...] REPORT systemtag=3 als alice (basic) auf / [Id B=3 (gleicher Name, neu)] | HTTP 207 | 34 ms | treffer=1 fileids=['157'] pfade=['/spike25/a.txt']
```

## Grenzen der Messung

- **SQLite:** Alle vier Versionen liefen auf sqlite3. SQLite vergleicht Namen binär (case-sensitiv). MariaDB/MySQL und PostgreSQL können bei Groß/Klein-Varianten anders vergleichen und bei der Latenz abweichen (Annahme A3). Der Varianten-Befund und alle Zeiten gelten nur für SQLite.
- **Einzelhost mit Mitläufern:** Laut `docker stats` liefen neben nc35 die 34er-Topologie (nc-mcp-exapp-*), findling-nextcloud, n8n-mcp-test und nc_app_mcp_connector_park34 mit (raw/nc35-latenz.txt, Abschnitt messbedingungen). Die Werte sind Einzelhost-Werte, keine Serverklasse.
- **Kaltdefinition:** "kalt" heißt `apachectl -k graceful` (neue mod_php-Worker, OPcache leer) plus 5 s Pause; der OS-Seitencache der SQLite-Datei bleibt warm (Annahme A5). Für D-25-04 maßgeblich ist der Warmwert.
- **Kein APCu auf nc35:** memcache.local ist auf nc35 nicht gesetzt; die Wegwerf-Instanzen 32 bis 34 laufen mit APCu. Deshalb verschwinden Capability und Suchprovider dort erst nach einem Neustart des Webservers.
- **Ballast unvollständig:** 145.000 statt 300.000 bis 400.000 Zuordnungen (600-s-Grenze); Stufe 1 und 100 mit Ballast nicht gemessen.
- **Image-Wahl:** Gemessen wurde mit dem offiziellen Image mit Patch-Tag (nextcloud:32.0.15-apache, 33.0.9-apache, 34.0.4-apache) statt mit nextcloud-docker-dev, weil nextcloud-docker-dev einen Branch klont und damit keinen Release misst. Das deckt Claude's Discretion in D-25-01 ("nextcloud-docker-dev vs. offizielle Images"); es weicht vom Klammerzusatz "(nextcloud-docker-dev)" in D-25-01 ab.

## Nebenbefunde

- `nextcloud:35.0.1-apache` hat seit 25.09.2026 ein amd64-Manifest (25-RESEARCH.md). Der Kommentar in `compose.nc35.yml` ("no matching manifest for linux/amd64") ist damit veraltet. Backlog-Notiz, in dieser Phase keine Änderung.
- nextcloud/server PR #64298 ist weiter offen. Der PR-Text nennt jetzt 6,2 s / 2,4 s statt der in PITFALLS zitierten 6,4 s / 2,1 s. Gemessen wurde dort ein PROPFIND mit nc:system-tags, nicht der REPORT. Unsere Referenz d (PROPFIND mit nc:system-tags auf 10.000 Dateien) liegt bei 346 ms, mit 145.000 Zuordnungen bei 879 ms (raw/nc35-latenz.txt).
- `occ user:auth-tokens:add` kennt auf 32.0.15 kein `--name` und scheitert auf 33.0.9 immer (`The "login-name" option does not exist`); relevant für `scripts/bootstrap_test_nc.sh`, falls die CI je gegen 33.0.9 bootstrapt (raw/matrix-32.txt, raw/matrix-33.txt).
- Gezogene Images liegen noch auf dem Host: nextcloud:32.0.15-apache 2,07 GB, nextcloud:33.0.9-apache 2,05 GB, nextcloud:34.0.4-apache 2,1 GB (laut `docker image ls`, 25-03). Entfernung auf Owner-Wunsch.

## Empfehlungen für den Checkpoint

- **E1 Notes-Weg:** Befund ja (id 933 = fileid 933, auch bei "spike25 Notiz (2).md"), daher EXCL-05 in Phase 27 bauen: Notes-Anschluss über die fileid der Notiz plus Pfad aus notesPath und category, weil ein getaggter Kategorieordner im REPORT nur als Ordner-fileid erscheint.
- **E2 Fail-closed-Auslöser:** Der REPORT antwortet nach app:disable auf 32, 33, 34 und 35 gleich (207 mit Treffern), die Capability dagegen hängt auf 32 bis 34 am APCu und verschwindet erst nach Neustart; maßgeblich ist daher der Ausgang des REPORT (207 = Menge ermittelt, alles andere nach einmaligem Neuauflösen bei 412 = nicht prüfbar), die Capability wird nicht befragt.
- **E3 Batch-Strategie:** Median warm bei 5000 = 8,848 s, also über 1 s: "ein REPORT je Antwort" ist nicht bestätigt. Von den vorgesehenen Alternativen scheidet der engere Zielpfad nach Messung aus (Zielpfad filtert nicht, auf allen Versionen), der Cache widerspricht EXCL-02. Gemessen günstig ist dagegen das Mitlesen von nc:system-tags per PROPFIND (346 ms für 10.001 Einträge, 879 ms mit Ballast); ein Weg "Tag-Prüfung an den Antwortknoten und ihren Vorfahren" wäre eine neue Alternative mit Änderung am Wortlaut von EXCL-02, ihr Vorfahren-Anteil ist nicht gemessen. Empfehlung: vor dem Entscheid über EXCL-02 eine kurze Zusatzmessung (siehe E4).
- **E4 PostgreSQL-Gegenmessung:** Da der Median über 1,0 s liegt: vor Phase 26 ein Zusatzplan 25-05 (erweitert D-25-02), der auf PostgreSQL Stufe 1/100/5000 misst, dazu Stufe 1 und 100 bei stehendem Ballast (bisher nicht gemessen) und den PROPFIND-Weg mit nc:system-tags an Antwortknoten plus Vorfahrenkette.

## Owner-Entscheid

**Datum:** 2026-09-26, Checkpoint 25-04 Task 2 (D-25-05). Owner-Antwort, vom Orchestrator wörtlich übermittelt: "Empfehlungen übernehmen".

- **E1 Notes-Weg:** "Empfehlungen übernehmen", Option `empfehlung`: EXCL-05 wird in Phase 27 gebaut, Anschluss über die fileid der Notiz plus Pfadprüfung über notesPath und category.
- **E2 Fail-closed-Auslöser:** "Empfehlungen übernehmen", Option `empfehlung`: maßgeblich ist der Ausgang des REPORT (207 = Menge ermittelt, 412 = Tag-Id einmal neu auflösen, alles andere = nicht prüfbar); die Capability wird nicht befragt.
- **E3 Batch-Strategie:** "Empfehlungen übernehmen", also gemäß Empfehlung E3 **vertagt** bis zur Zusatzmessung 25-05; keine der Optionen `empfehlung` oder `batch-alternative` ist gewählt. "Ein REPORT je Antwort" ist nicht bestätigt.
- **E4 PostgreSQL-Gegenmessung:** "Empfehlungen übernehmen", Option `postgres-gegenmessung`: Zusatzplan 25-05 vor Phase 26 (Stufen 1/100/5000 auf PostgreSQL, Stufe 1 und 100 bei stehendem Ballast von 145.000 Zuordnungen, PROPFIND-Weg mit nc:system-tags an Antwortknoten plus Vorfahren). D-25-02 ist damit erweitert; Phase 25 wird noch nicht abgeschlossen.

## Ableitungen für Phase 26 und 27

Gilt erst nach dem Owner-Entscheid (D-25-05); der Entscheid oben liegt vor. Jede Ableitung nennt ihren Befund.

### Phase 26 (Guard-Kern, EXCL-02 und EXCL-04)

- **Fail-closed-Auslöser (E2, K1):** Der Guard wertet ausschließlich den Ausgang der Tag-Abfrage aus. 207 mit gültigem Body = Menge ermittelt, Filter aktiv. 412 = die gecachte Tag-Id ist veraltet oder unsichtbar: Name zu Id einmal neu auflösen und einmal wiederholen; kommt erneut 412 oder fehlt das Tag in der Liste, gilt "kein Tag vorhanden" nur, wenn PROPFIND /systemtags/ den Namen nicht mehr listet, sonst "nicht prüfbar". Jeder andere Ausgang (5xx, 401/403, Zeitlimit, Netzfehler, nicht parsebarer Body) = nicht prüfbar, betroffene Einträge zurückgehalten, Degradation benannt. Die systemtags-Capability wird nicht befragt: Sie hängt auf 32 bis 34 am APCu und sagt über die Antwortfähigkeit des REPORT nichts (REPORT 207 mit Treffern bei App aus auf allen vier Versionen). Folge: Bei ausgeschalteter App filtert der Guard weiter.
- **412-Verhalten (K5):** Auf allen Versionen liefert eine unbekannte oder nach Löschen/Neuanlage veraltete Id 412 ("Cannot filter by non-existing tag"), die neue Id B 207. Das stützt EXCL-02 wie geschrieben: prozessweiter Cache nur für Name zu Id, bei 412 genau einmal neu auflösen.
- **Varianten (K5):** Exakt gleichnamige Tags (X public, Y restricted) liefern je Id schon die Vereinigung; eine Variante in anderer Groß/Klein-Schreibung (W) ist getrennt. Der Guard löst daher alle Tags auf, deren Name casefold gleich `kein-ki` ist, und vereinigt die Mengen je Id. Ein für den Nutzer unsichtbares Tag (Z) liefert 412 und fehlt in seiner Liste: Es wird nicht zur Abfrage herangezogen und zählt nicht als "nicht prüfbar". Grenze: nur SQLite gemessen (A3), PostgreSQL folgt in 25-05.
- **Zielpfad-Regel (K5):** Der REPORT filtert auf keiner Version nach Zielpfad; er liefert immer die ganze für den Nutzer sichtbare getaggte Menge. Der Guard schickt ihn auf die Home-Wurzel und prüft die Menge selbst per Präfixvergleich nach der bestehenden Segmentregel (EXCL-02). Einen engeren Zielpfad als Kostenhebel gibt es nicht.
- **Batch-Form (E3): offen.** Der Median warm bei 5000 liegt mit 8,848 s über der Schwelle D-25-04 (mit Ballast 249,6 s). Ob Phase 26 "ein REPORT je Antwort" baut oder eine Tag-Prüfung an den Antwortknoten und ihren Vorfahren (mit Änderung am Wortlaut von EXCL-02), entscheidet der Owner nach Plan 25-05. Bis dahin plant Phase 26 die Batch-Form nicht fest; unabhängig davon gelten die Punkte oben.

### Phase 27 (Werkzeug-Anschluss, EXCL-01, EXCL-03, EXCL-05)

- **Notes-Weg (E1, K4):** EXCL-05 wird gebaut. Eine Notiz ist ausgeschlossen, wenn ihre Id (gleich fileid, belegt mit 933 und 934) in der getaggten Menge liegt oder ihr Pfad `notesPath/category/...` unter einem getaggten Ordner liegt; der REPORT liefert für einen getaggten Kategorieordner nur dessen fileid (932), keine Notiz-Ids. Die Pfadprüfung läuft über dieselbe Segmentregel wie bei den Datei-Werkzeugen.
- **Freigabe-Grenze (K5):** Ein Tag auf einem Vorfahren beim Eigentümer ist für den Empfänger einer Unterordner-Freigabe unsichtbar (bob: 207, 0 Treffer); der geteilte Unterordner erscheint bei bob ungeschützt. Ein Tag auf dem geteilten Knoten selbst sieht bob (/share2). Phase 27 behandelt das als dokumentierte Grenze (Tag auf den geteilten Knoten setzen), die Doku folgt in Phase 29.

### Offen bis 25-05

- Batch-Entscheid E3 und damit der endgültige Wortlaut von EXCL-02.
- Latenz und Varianten auf PostgreSQL, Stufe 1 und 100 mit Ballast, Kosten des PROPFIND-Wegs an Antwortknoten plus Vorfahren.
