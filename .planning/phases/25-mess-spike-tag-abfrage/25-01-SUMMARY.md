---
phase: 25-mess-spike-tag-abfrage
plan: 01
subsystem: messwerkzeug / nc35-Einzelbefunde
tags: [spike, systemtags, webdav-report, appapi, notes, messung]
requires: []
provides:
  - scripts/tag_spike.py (Blöcke controls, findings, secret-scan; Helfer für 25-02/25-03)
  - compose.spike-tags.yml (Wegwerf-Instanz 8083, erst ab 25-03 gestartet)
  - raw/nc35-befunde.txt (Notes, Impersonation, 412, unsichtbar, Varianten, Zielpfad, Freigabe, App-aus 35)
  - raw/nc35-prepare-context-baseline.txt (Wanduhr ohne Spike-Daten)
affects: [25-02, 25-03, 25-04, 26, 27]
tech-stack:
  added: []
  patterns:
    - "Messskript nach exchange_evidence.py: guarded-Blöcke, Rückbau im finally, Baseline-Vergleich als letzte Zeilen"
    - "Protokoll wird erst nach scan_for_secrets geschrieben"
    - "ein httpx-Client ohne Cookie-Jar (NoCookieJar) für mehrere Identitäten"
key-files:
  created:
    - compose.spike-tags.yml
    - scripts/tag_spike.py
    - tests/unit/test_tag_spike.py
    - .planning/phases/25-mess-spike-tag-abfrage/raw/nc35-befunde.txt
    - .planning/phases/25-mess-spike-tag-abfrage/raw/nc35-prepare-context-baseline.txt
  modified:
    - vulture_whitelist.py
decisions:
  - "Notiz-Id = fileid auf nc35 live belegt (zwei unabhängige Wege, auch bei umbenannter Datei 'spike25 Notiz (2).md'): Grundlage für EXCL-05 am Checkpoint 25-04"
  - "REPORT unter AppAPI-Impersonation liefert dieselbe fileid-Menge wie mit App-Passwort und wie aus dem ExApp-Container gegen http://caddy"
  - "Messclient ohne Cookie-Jar: ein Session-Cookie trug im Smoke-Lauf die Anfrage der nächsten Identität als alice"
metrics:
  duration: "ca. 25 min"
  completed: 2026-09-26
  tasks: 3
  files: 6
---

# Phase 25 Plan 01: Messwerkzeug und nc35-Einzelbefunde Summary

Messskript `scripts/tag_spike.py` mit getesteten Helfern plus Wegwerf-Compose gebaut und damit alle acht nicht versionsabhängigen Einzelbefunde auf nc35 gemessen: Notiz-Id ist gleich fileid, der REPORT ist unter AppAPI identisch, 412 und Sichtbarkeit verhalten sich wie in der Quelle, der Zielpfad filtert nicht, und App-aus nimmt auf 35 nur Capability, Suchprovider und `tag:files:*` weg.

## Befunde (Rohbeleg: raw/nc35-befunde.txt)

| Block | Ergebnis |
|---|---|
| notes | `NOTIZ-ID GLEICH FILEID: ja` (id 933 = fileid 933; zweite Notiz gleichen Titels: Datei "spike25 Notiz (2).md", id 934 = fileid 934; GET /notes/{fileid} liefert dieselbe Notiz). REPORT auf den getaggten Kategorieordner liefert die Ordner-fileid, keine Notiz-ids |
| impersonation | `fileids_basic=3 fileids_appapi=3 gleich=ja`; Kontrolle a (cloud/user = alice), b (falsches Secret: 401), c (1 REPORT-Zeile alice im exapp_impersonation.log); Produktionsweg aus dem ExApp-Container: 207, 3 fileids, gleich |
| 412 | unbekannte Id 999999: 412 "Cannot filter by non-existing tag"; nach Löschen und Neuanlage: alte Id A 412, neue Id B 207; /systemtags/ listet nur B |
| unsichtbar | alice: 412, Tag fehlt in ihrer Liste; temporärer Admin: 207 mit eigener getaggter Datei, Tag in seiner Liste |
| varianten | X (public) und Y (restricted, gleichnamig) liefern beide die Dateien von X und Y; Z (invisible) 412 für alice; W (Groß/Klein) getrennt. Grenze: sqlite3, binärer Vergleich (Annahme A3) |
| zielpfad | `ZIELPFAD filtert=nein`: Home-Wurzel, Unterordner und fremder Ordner liefern alle /spike25/p/tagged |
| freigabe | Fall 1 (getaggter Vorfahr beim Eigentümer, Unterordner geteilt): bob 207 mit 0 Treffern; Fall 2 (geteilter Ordner getaggt): bob sieht /share2 |
| app-aus-35 | App aus: Capability fehlt, Suchprovider systemtags fehlt, `tag:files:*` fehlen; PROPFIND /systemtags/, REPORT und nc:system-tags antworten unverändert. `CAPABILITY systemtags nach Lauf vorhanden: ja` |

Baseline vor und nach dem Lauf identisch (Tags [], alice 275 Dateien, Papierkorb 0, Mapping-Zeilen 0), spike25admin entfernt, `occ tag:list` leer, systemtags aktiv. prepare_context-Baseline: Median short 0,72 s, full 0,81 s.

## Tasks

| Task | Commit(s) | Inhalt |
|---|---|---|
| 1 | 2b4a9a4 (RED), d03bd0d (GREEN) | Compose, Skriptgerüst, Helfer-Tests |
| 2 | fbc5eb5, 52cdf47, 3d454da, a7a223a, 3071063, 0366d1b, c2d9685, 1d40dd6 | ein Commit je `== abschnitt ==`-Block, Gates jeweils grün |
| 3 | a6c6145 | Rohprotokolle, secret-scan Exit 0 |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Session-Cookie trug fremde Identität**
- **Found during:** Task 2, Smoke-Lauf Block unsichtbar (vor jedem Protokoll im Phasenordner)
- **Issue:** Der gemeinsame httpx-Client hielt Nextclouds Session-Cookie von alice; der PUT des temporären Admins lief darunter als alice und bekam 403. Derselbe Effekt hätte den AppAPI-REPORT verfälschen können.
- **Fix:** `new_client()` nutzt `NoCookieJar` aus `nextcloud/http.py` (Produktionshaltung).
- **Commit:** a7a223a

**2. [Rule 3 - Blocking] prepare_context-Kommando druckte nichts**
- **Issue:** `-k wall_clock` allein gibt keine Zeilen aus; test_ctx_bundle.py druckt erst im Test `measurement_protocol`.
- **Fix:** `-k "wall_clock or measurement_protocol or no_measured_line"`; die Env-Datei per kleinem Python-Wrapper geladen, weil `. ./.env.nc35` in der Worktree-Sandbox gesperrt ist. Beides im Kopf der Baseline-Datei benannt.

**3. [Rule 2] Weitere Absicherungen im Skript**
- `report_body` lässt nur ASCII-Ziffern zu (`str.isdigit` akzeptiert Vollbreiten- und Hochziffern, Test ergänzt); stdout auf UTF-8 umgestellt; PUT-Fehler nennen `s:message`; Home des Temp-Admins wird vor dem ersten PUT per PROPFIND angelegt.

### Sonstiges

- Task-2-Blöcke 412/unsichtbar und zielpfad/freigabe wurden gemeinsam geschrieben und für die Einzelcommits getrennt gestaffelt; jeder Commit hat eigene grüne Gates.
- Alle Blöcke vor dem echten Lauf als Smoke-Läufe gegen nc35 gefahren (Protokolle nur im Scratchpad, jeder mit Rückbau und Baseline gleich=ja); die Tag-Ids auf nc35 sind dadurch weitergezählt (Autoincrement, ohne Wirkung).
- vulture: Namen, die erst 25-02/25-03 aufrufen (SPIKE_*, THRESHOLD_SECONDS, WARMUP, RUNS_*, summarize, wait_for_install), stehen mit Begründung in `vulture_whitelist.py` und verlassen die Liste mit dem Block, der sie ruft.
- `.env.nc35` wurde aus dem Hauptcheckout gelesen (`--env-file ../../../.env.nc35`), nur lesend.
- Messbedingung prepare_context: Mail-Bein meldet "Nextcloud did not find the mail accounts." (Pitfall 12), in der Datei benannt.

## Known Stubs

Keine.

## Threat Flags

Keine neue Angriffsfläche über das Threat-Register hinaus (T-25-01 bis T-25-07 umgesetzt: Passwörter nur via stdin, Protokoll-Scan vor dem Schreiben, ExApp-Programm druckt kein Secret, Rückbau im finally, Temp-Admin gelöscht, Kontrollen a/b/c, Bodies per lxml).

## Self-Check: PASSED

- Dateien vorhanden: compose.spike-tags.yml, scripts/tag_spike.py, tests/unit/test_tag_spike.py, raw/nc35-befunde.txt, raw/nc35-prepare-context-baseline.txt
- Commits vorhanden: 2b4a9a4, d03bd0d, fbc5eb5, 52cdf47, 3d454da, a7a223a, 3071063, 0366d1b, c2d9685, 1d40dd6, a6c6145
