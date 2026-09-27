---
phase: 27-familien-anschluss-und-sandbox-parit-t
plan: 07
subsystem: live-beweise
tags: [exclusion, kein-ki, live, nc35, sandbox, respx]
requires:
  - "27-02 bis 27-06: alle Familien am Guard (files, search/fetch, notes, talk, prepare_context)"
provides:
  - "tests/integration/test_exclusion_live.py: Live-Beweise der Erfolgskriterien 1, 2 (ohne Wanduhr), 3, 4, 5 und Messung A1"
  - "raw/27-07-live.txt: Rohprotokoll je Prüfung (Kommando, NC-Version, Befundzeile, Aufräumnachweis)"
affects:
  - "27-08: Wanduhr prepare_context, Request-Kosten, Findling-CI-Fall"
  - "Phase 28/29: Paarformen live bestätigt, Restorakel dokumentieren"
tech-stack:
  added: []
  patterns:
    - "Fresh: ein NcClients mit neuem ExclusionGuard je Tool-Aufruf, doppelte Ausgabe bricht ab (T-27-62)"
    - "check(): Befundzeile zuerst protokollieren, dann asserten"
    - "shape(): Fehlervergleich mit Platzhaltern für Pfad/Id/Token, exact() gegen die Fabrik"
    - "respx.mock mit REPORT-500 plus pass_through für alles andere"
key-files:
  created:
    - tests/integration/test_exclusion_live.py
    - .planning/phases/27-familien-anschluss-und-sandbox-parit-t/raw/27-07-live.txt
  modified: []
decisions:
  - "Testnamen tragen die Laufkennung (offen-<hex>.txt, Projekt-<hex>/, Kategorien Live27Offen-<hex>/Live27Geheim-<hex>), damit Namenssuchen eindeutig sind und kein Rest früherer Läufe mitzählt"
  - "Fehlergleichheit live: getaggt gegen denselben Pfad aus der Fabrik (exact) plus Form gegen einen echt fehlenden Pfad mit Platzhalter (shape), weil die Sätze Pfad/Id/Token enthalten"
  - "Harness-Requests ohne Session-Cookie: nach einer Notes-API-Antwort beantwortete nc35 alle weiteren WebDAV-Requests desselben Clients mit 401"
metrics:
  duration: "ca. 45 min"
  completed: 2026-09-27
  tasks: 3
  files: 2
---

# Phase 27 Plan 07: Live-Beweise gegen nc35 Summary

Ein Integrationsmodul baut je Lauf einen eigenen Testbaum, taggt ihn per occ und belegt gegen die echte Nextcloud 35.0.0: getaggte Dateien, Ordner, Notizen, Kategorien, Talk-Freigaben und Datei-Räume antworten wie nicht existent, die Sandbox greift auch für pfadlose comments-/notes-Treffer, ein injizierter REPORT-500 lässt jede Familie mit genau einem degraded-Eintrag bzw. dem uniformen Fehler zurückhalten, und im Erfolgsfall schweigt jede Antwort.

## Was gebaut wurde

**Harness (Task 1):** `World` mit `/live27-<hex8>/` (offen, geheim, vorher, Projekt/ mit a, scan.pdf, Unter/b), Datei außerhalb `/live27-out-<hex>.txt`, drei Notizen (A offen, B getaggt in Live27Offen-<hex>, G in getaggter Kategorie Live27Geheim-<hex>), zwei Kommentare. vorher.txt wird vor dem Taggen per `fetch(file:<id>)` gelesen (Scope `untagged` belegt). `kein-ki` wird angelegt, wenn tag:list es nicht kennt, und am Ende per `tag:delete` entfernt. Teardown löscht Notizen, Baum und Außendatei und prüft PROPFIND 404, 0 Notizen übrig, 0 Tags.

**SC1:** files_list ohne geheim/Projekt, getaggter Ordner wie fehlender Pfad; files_search für alle getaggten Namen leer, Laufkennung ohne getaggte Namen, Gegenprobe offen; files_read und files_download für geheim, a, b, scan.pdf, Projekt byte-gleich zu `dav.not_found` (kein "not text", kein "is a folder"); files_upload auf Projekt/neu.txt und geheim wie fehlender Elternordner, danach PROPFIND 404 bzw. ETag unverändert.

**SC3:** Mit `NC_MCP_FILES_ROOT=/live27-<hex>` liefert comments nur den inneren Treffer (skipped=1), notes_search nichts (skipped=3); ohne Root nur die ungetaggte Notiz; notes_read für B und G wie Id 999999999; notes_create in die getaggte Kategorie = `dav.parent_missing(candidate)`, Notizzahl unverändert.

**SC2 (Task 2):** unified_search und ChatGPT-search (Laufkennung, geheim-Name, Projekt-Name) ohne getaggte Id oder Namen; fetch der vorher gelesenen fileid wie `file:999999999`; systemtags-Provider roh 6 Einträge (5 mit attributes), Antwort 1 Eintrag ohne fileId, keine getaggte Datei; prepare_context full ohne getaggten Treffer, Ausschnitt oder Namen.

**SC4:** Geteilte getaggte Datei in messages, conversations (last_message `{file}`) und fetch(message) (`From: alice\n{file}`) nur als Platzhalter; Gegenprobe offen zeigt den Namen; Datei-Raum (Route api/v1/file, Join/Leave) steht roh in der Raumliste, fehlt in talk_browse und antwortet wie ein erfundenes Token. Shares und Teilnahme danach entfernt und geprüft.

**SC5 (Task 3):** REPORT auf die Home-URL = 500, alles andere pass_through. files_list, notes_search, talk_browse: genau `[degraded_entry("source")]`; files_read (offen und erfunden), files_upload (nichts geschrieben) und fetch(file): exakt `withhold.unavailable_error()`; unified_search ohne dateitragende Treffer mit einem `{provider: exclusion}`; prepare_context genau ein Ausschluss-Eintrag. Der injizierte REPORT wurde 9-mal beantwortet, einmal je Tool-Aufruf (auch prepare_context nur einmal). Schweigen: 14 Antworten im active-Zustand ohne Schlüssel withheld/excluded/hidden/exclusion und ohne den Ausschluss-Satz.

**A1:** `dav.paths_of_fileids` auf nc35 (5 Läufe nach 1 Aufwärmlauf): Vollauf n=1 median 27,9 ms (max 28,5), n=25 29,3 ms (max 30,3), n=50 30,7 ms (max 31,8); der Einzellauf davor lag gleichauf (28,0/29,0/31,7). Ein Block mit 50 Ids kostet praktisch nicht mehr als eine einzelne Id.

## Verifikation

- Voller Modul-Lauf gegen nc35: 10 passed. Rohdatei: 0 Zeilen `^SC[1-5] .*: nein`; über vier Läufe SC1 48, SC2 22, SC3 16, SC4 12, SC5 18 ja-Zeilen, 6 A1-Zeilen (je Lauf mindestens 24/11/8/6/9 bzw. 3).
- Nach dem Lauf: `occ tag:list` = `[]`, kein `live27*` im Home von alice.
- `grep -rc "tag:files:add" src` = 0.
- `ruff check .`, `ruff format --check .`: grün; pyright (latest): 0 errors; vulture: grün; `pytest tests/unit tests/contract`: 4814 passed, 33 skipped.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug im Harness] Session-Cookie machte das Aufräumen wirkungslos**
- **Found during:** Task 1 (erster Lauf)
- **Issue:** Nach den Notes-API-Aufrufen beantwortete nc35 jeden weiteren WebDAV-Request des Harness-Clients mit 401; DELETE von Baum und Außendatei griff nicht, der Teardown meldete es korrekt (PROPFIND 401 statt 404).
- **Fix:** `Harness.request` leert vor jedem Request die Cookies; Reste des ersten Laufs per DELETE entfernt und mit PROPFIND 404 geprüft. Rohdatei dieses Fehllaufs verworfen.
- **Commit:** ec1e564

**2. Laufkennung in allen Namen**
- Statt "geheim.txt", "Projekt/", "Live27Geheim" tragen alle Namen `-<hex8>`, damit Namenssuchen nur Testdaten dieses Laufs treffen (alte Freigabe-Nachrichten früherer Proben stehen noch im Test-Raum). Die json.dumps-Prüfungen suchen den laufgenauen Namen.

**3. Vergleich der Fehler mit Platzhaltern**
- Wie schon in 27-02 begründet, enthalten Not-found-, Parent-missing-, Notiz- und Token-Sätze den Wert selbst. Geprüft wird daher `exact(getaggt) == exact(Fabrik(gleicher Wert))` und `shape(getaggt) == shape(echt fehlend)` mit Platzhalter.

### Ausführungsumgebung

- Worktree-Base war abweichend (7a93585) und wurde laut Auftrag per `git reset --hard 0e1612a` korrigiert.
- `set -a && . ./.env.nc35` ist in der Worktree-Isolation gesperrt; ein temporärer Python-Lader (nicht committet, danach gelöscht) las die Env-Datei des Hauptrepos und startete pytest mit `-o "pythonpath=src tests/integration tests/unit"` über die Hauptrepo-venv. Das Kommando in der Rohdatei ist das geplante.

## Merker

- prepare_context full meldete im Erfolgsfall einen degraded-Eintrag `file:<id>` für einen Ausschnitt (Treffer der Laufkennung, vermutlich der Ordner /live27-<hex>, den fetch als Ordner ablehnt). Kein Ausschluss-Bezug, kein Leck; Verhalten vor Phase 27 identisch. Für 27-08/Phase 28 notiert.
- Der Test-Raum sammelt Freigabe-Nachrichten gelöschter Dateien (Probe-Läufe); sie sind für die Prüfungen irrelevant, weil nur laufgenaue Namen gesucht werden.

## Known Stubs

Keine.

## Threat Flags

Keine neue Angriffsfläche. T-27-60 (occ nur im Harness, grep src = 0), T-27-61 (Rohdatei ohne App-Passwort/APP_SECRET, nur Testdaten), T-27-62 (Fresh bricht bei doppelter Guard-Ausgabe ab), T-27-63 (finally-Aufräumen mit Nachlauf-Prüfung) umgesetzt.

## Commits

- ec1e564 test(27-07): live proof of the files family, uploads, notes and comments sandbox
- d2941aa test(27-07): live proof of search, fetch by an old file id, systemtags, bundle and Talk
- ea3a594 test(27-07): live degradation with an injected REPORT 500, silence on success, fileid lookup cost

## Self-Check: PASSED
