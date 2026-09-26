---
phase: 25-mess-spike-tag-abfrage
plan: 03
subsystem: messwerkzeug / Versionsmatrix 32 bis 34
tags: [spike, systemtags, webdav-report, app-aus, 412, zielpfad, messung]
requires:
  - 25-01 (scripts/tag_spike.py, compose.spike-tags.yml, findings-Unterblöcke)
  - 25-02 (Lehren: Zeitlimit als Messwert, Warten auf ruhende Instanz)
provides:
  - scripts/tag_spike.py (Block matrix mit --nc-tag, validate_nc_tag, Run.container)
  - raw/matrix-32.txt, raw/matrix-33.txt, raw/matrix-34.txt
affects: [25-04, 26, 27]
tech-stack:
  added: []
  patterns:
    - "Wegwerf-Instanz je Version: Vorbedingung leer, up -d --wait, Messung, down -v im finally, Abbau-Prüfung als letzte Zeilen"
    - "Secrets an docker compose nur über env des Unterprozesses (run(..., env=))"
    - "App-aus zweimal messen: sofort und nach docker restart (APCu des Webservers)"
key-files:
  created:
    - .planning/phases/25-mess-spike-tag-abfrage/raw/matrix-32.txt
    - .planning/phases/25-mess-spike-tag-abfrage/raw/matrix-33.txt
    - .planning/phases/25-mess-spike-tag-abfrage/raw/matrix-34.txt
  modified:
    - scripts/tag_spike.py
    - tests/unit/test_tag_spike.py
    - vulture_whitelist.py
decisions:
  - "Fail-closed-Auslöser (EXCL-04) auf Messwerten 32 bis 35: REPORT und PROPFIND /systemtags/ antworten bei ausgeschalteter App unverändert 207 mit Treffern; nur Capability, Suchprovider und tag:files:* verschwinden. Eine Capability-Prüfung würde die App-aus-Lage erkennen, der REPORT-Erfolg allein nicht; Entscheidung am Checkpoint 25-04"
  - "Capability und Suchprovider verschwinden auf 32/33/34 erst nach einem Neustart des Webservers: das offizielle Image setzt memcache.local=APCu, occ auf der Kommandozeile leert den APCu des Apache nicht"
metrics:
  duration: "ca. 25 min"
  completed: 2026-09-26
  tasks: 2
  files: 6
---

# Phase 25 Plan 03: Versionsmatrix 32 bis 34 Summary

Block `matrix` fährt je Version eine Wegwerf-Instanz (offizielles apache-Image, SQLite, 127.0.0.1:8083) von der leeren Maschine bis zum entfernten Volume. Auf 32.0.15, 33.0.9 und 34.0.4 verhalten sich REPORT, 412 und Zielpfad wie auf 35. Beim Abschalten der App systemtags bleiben DAV-Seite und REPORT unverändert, Capability und Suchprovider fallen erst nach einem Neustart des Webservers weg.

## Befunde (Rohbelege: raw/matrix-32.txt, -33.txt, -34.txt)

| Messpunkt | 32.0.15 | 33.0.9 | 34.0.4 | 35 (25-01) |
|---|---|---|---|---|
| VERSION OF RECORD (occ status) | 32.0.15 | 33.0.9 | 34.0.4 | 35.0.0 |
| memcache.local | APCu | APCu | APCu | nicht gesetzt |
| Grundform: REPORT Home-Wurzel | 207, 2 Treffer (Ordner /spike25/p/tagged, Datei /spike25/a.txt) | gleich | gleich | 207 |
| ZIELPFAD filtert | nein | nein | nein | nein |
| 412 unbekannte Id 999999 | 412 "Cannot filter by non-existing tag" | gleich | gleich | gleich |
| 412 alte Id A nach Löschen/Neuanlage | 412; neue Id B 207; /systemtags/ listet nur B | gleich | gleich | gleich |
| App aus sofort: Capability / Suchprovider | bleiben | bleiben | bleiben | fehlen |
| App aus nach Neustart: Capability / Suchprovider | fehlen | fehlen | fehlen | - |
| App aus: PROPFIND /systemtags/, REPORT, nc:system-tags | unverändert 207 (REPORT 2 Treffer) | gleich | gleich | gleich |
| App aus: occ tag:files:* | fehlen (tag:add/delete/edit/list bleiben) | gleich | gleich | gleich |

- `APP-AUS REPORT nachher status=207 treffer=2` auf allen drei Versionen, auch nach Neustart (`APP-AUS-NEUSTART REPORT nachher status=207 treffer=2`).
- Die Capability nach `app:enable` im finally (Zeile "CAPABILITY systemtags nach Lauf vorhanden") schwankt: 32 nein, 33 ja, 34 nein. Das ist derselbe APCu-Effekt in umgekehrter Richtung: Der Webserver hält nach dem Neustart den Stand "App aus" im Cache. Die Instanz fiel danach mit `down -v`, die Zeile besagt über die Versionen nichts.
- Versionsbefund am Rand: `occ user:auth-tokens:add` kennt auf 32 kein `--name`, und auf 33.0.9 bricht es mit `--password-from-env` immer ab (`The "login-name" option does not exist`: Der Code liest eine nicht definierte Option). 34.0.4 läuft mit `--name`. Relevant für `scripts/bootstrap_test_nc.sh`, falls die CI je gegen 33.0.9 bootstrapt.
- Laufzeiten: 32 von 18:35:43 bis 18:36:22Z, 33 von 18:40:20 bis 18:41:03Z, 34 von 18:42:37 bis 18:43:23Z (UTC, keine Überlappung). `up -d --wait` etwa 12 bis 16 s, die Installation ist dann schon fertig.

## Tasks

| Task | Commit(s) | Inhalt |
|---|---|---|
| 1 | 0f3827d | Block matrix, validate_nc_tag, Run.container, Wiederverwendung von 412/zielpfad/app-aus, Unit-Tests |
| 2 | e3153a4 (Werkzeug-Fixes), d8c5f56 (Rohprotokolle) | drei sequenzielle Läufe, secret-scan 7 Dateien, 0 Funde |

Beleg für die Akzeptanzkriterien: `compose(["down", "-v"], ...)` steht in scripts/tag_spike.py Zeile 2528, im `finally:` des matrix-Blocks (Zeile 2526). `NC_SPIKE_ADMIN_PASSWORD` kommt nur als Schlüssel von `compose_env` vor (Zeile 2446), nie als argv.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `--name` fehlt auf NC 32**
- **Found during:** Task 2, erster Lauf 32
- **Issue:** `user:auth-tokens:add --name` bricht auf 32.0.15 ab ("option does not exist").
- **Fix:** Bei genau dieser Meldung zweiter Aufruf ohne `--name`, im Protokoll benannt. Lauf 32 komplett neu gefahren (frisches Volume).
- **Commit:** e3153a4

**2. [Rule 1 - Bug] `user:auth-tokens:add` auf 33.0.9 defekt**
- **Found during:** Task 2, erster Lauf 33
- **Issue:** 33.0.9 liest `getOption('login-name')` ohne die Option zu definieren (Quelle v33.0.9 geprüft); jeder Aufruf mit Passwort scheitert.
- **Fix:** Rückfall auf `GET /ocs/v2.php/core/getapppassword` mit Basic-Auth über Loopback (Passwort nicht in argv), als `BEFUND` im Protokoll. Das Token wird jetzt aus der Zeile nach "app password:" gelesen statt aus der letzten Zeile, weil stdout und stderr zusammenlaufen. Eine Fehlermeldung zeigt nur Zeilen mit Leerzeichen, ein Token kann so nicht hineingeraten. Lauf 33 komplett neu gefahren.
- **Commit:** e3153a4

**3. [Rule 2 - Messkorrektheit] App-aus-Messung durch APCu verfälscht**
- **Found during:** Task 2, Lauf 32
- **Issue:** Direkt nach `app:disable` meldeten Capability und Suchprovider auf 32 noch systemtags, auf 35 nicht. Ursache: Das offizielle Image setzt `memcache.local = \OC\Memcache\APCu`, und occ (CLI) kann den APCu des Apache nicht leeren.
- **Fix:** Die Sofortmessung bleibt als Befund stehen (Zeilen `APP-AUS ...`). Zusätzlich misst der Block nach `docker restart` alle sechs Punkte erneut (Zeilen `APP-AUS-NEUSTART ...`), und `memcache.local` steht im Protokollkopf. Lauf 32 danach komplett neu gefahren. Nach dem Neustart fehlen Capability und Suchprovider, die Ursache ist damit belegt.
- **Commit:** e3153a4

### Sonstiges

- `tag:files:add` bekommt wie in 25-01 die fileid statt des Pfads `/alice/files/...`. Laut Quelle stable32 nimmt es "file id or path", und die Wiederverwendung von `tag_files_add` blieb so unverändert.
- Grundform und 412 taggen `a.txt` beide; nc:system-tags von a.txt zeigt daher `kein-ki-spike25-m` und `kein-ki-spike25-m412`.
- Vorbedingung prüft `docker ps -a` (auch gestoppte Container), strenger als im Plan.
- Die findings-Unterblöcke laufen unverändert mit Standardwerten (Run.container = nc35-nc, block_412/zielpfad/block_app_aus mit Schlüsselwort-Defaults). Nicht erneut gegen nc35 gefahren, geprüft über Unit-Tests, pyright und `--help`.
- vulture_whitelist: SPIKE_BASE_URL, SPIKE_COMPOSE und wait_for_install haben die Liste wie angekündigt verlassen, der Abschnitt ist leer.
- Gates mit dem Python der venv des Hauptcheckouts, `PYTHONPATH=src`, pyright mit `--pythonpath` auf diese venv; `.env.nc35` nur lesend aus dem Hauptcheckout (`--env-file ../../../.env.nc35`).
- Gezogene Images bleiben liegen, ihre Entfernung ist Sache des Owners: nextcloud:32.0.15-apache 2,07 GB, nextcloud:33.0.9-apache 2,05 GB, nextcloud:34.0.4-apache 2,1 GB (Plattenbelegung laut `docker image ls`).

## Known Stubs

Keine.

## Threat Flags

Keine neue Angriffsfläche über das Threat-Register hinaus. T-25-12 (nur 127.0.0.1:8083, Zufallspasswörter je Lauf, down -v im finally), T-25-13 (Admin-Passwort nur in env von docker compose, alle erzeugten Passwörter und Tokens vor dem Schreiben gescannt), T-25-14 (matrix spricht nur nc-spike-tags und 8083 an), T-25-15 (Volume-Vorbedingung, Abbau-Prüfung nach jedem Lauf). Neu ist nur der OCS-Rückfall `getapppassword`: ein Loopback-Aufruf gegen die Wegwerf-Instanz mit dem dort erzeugten Zufallspasswort.

## Self-Check: PASSED

- Dateien vorhanden: scripts/tag_spike.py, tests/unit/test_tag_spike.py, raw/matrix-32.txt, raw/matrix-33.txt, raw/matrix-34.txt
- Commits vorhanden: 0f3827d, e3153a4, d8c5f56
- Kein Container nc-spike-tags, kein Volume nc-mcp-spike-tags_nc-spike-tags-data; secret-scan Exit 0
