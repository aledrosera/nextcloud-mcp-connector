---
phase: 25-mess-spike-tag-abfrage
plan: 02
subsystem: messwerkzeug / nc35-Kostenmessung
tags: [spike, systemtags, webdav-report, latenz, schwelle, messung]
requires:
  - 25-01 (scripts/tag_spike.py, Helfer, prepare_context-Baseline)
provides:
  - scripts/tag_spike.py (Blöcke latency, ballast-remeasure, teardown; --keep-data)
  - raw/nc35-latenz.txt (Stufen 1/100/5000, Referenzen, kalt, Ballast, Schwelle, Rückbau)
  - raw/nc35-prepare-context-mit-daten.txt (Wanduhr mit 20.000 Spike-Dateien)
affects: [25-04, 26, 27]
tech-stack:
  added: []
  patterns:
    - "Zeitlimit eines Messlaufs ist ein Messwert: Reihe abbrechen, auf ruhende Instanz warten, ein Einzellauf mit 300 s"
    - "Baseline als JSON (nur Zähler) für einen Rückbau in einem getrennten Prozess, nach dem Vergleich gelöscht"
key-files:
  created:
    - .planning/phases/25-mess-spike-tag-abfrage/raw/nc35-latenz.txt
    - .planning/phases/25-mess-spike-tag-abfrage/raw/nc35-prepare-context-mit-daten.txt
  modified:
    - scripts/tag_spike.py
    - tests/unit/test_tag_spike.py
    - vulture_whitelist.py
decisions:
  - "D-25-04 geprüft, nicht entschieden: Median warm bei 5000 = 8,848 s, ergebnis=ueber; die Entscheidung fällt am Owner-Checkpoint 25-04"
  - "Mit Ballast (145.000 Zuordnungen) braucht derselbe REPORT 249,6 s (Einzellauf): die Größe der Mapping-Tabelle verteuert den REPORT massiv"
metrics:
  duration: "ca. 45 min"
  completed: 2026-09-26
  tasks: 2
  files: 5
---

# Phase 25 Plan 02: Kostenmessung REPORT auf nc35 Summary

Der REPORT `oc:filter-files` kostet auf nc35 (SQLite, ohne memcache.local) bei 5000 getaggten Dateien im Median warm 8,85 s und liegt damit klar über der Schwelle D-25-04 von 1,0 s. Mit 145.000 Zuordnungen Ballast dauert er 250 s. Die prepare_context-Wanduhr bleibt mit den Spike-Daten unverändert, nc35 ist vollständig zurückgebaut.

## Messwerte (Rohbeleg: raw/nc35-latenz.txt)

| Messung | Status | Treffer | Bytes | Median warm | p95 (zweitgrößter) | max |
|---|---|---|---|---|---|---|
| STUFE 1 (1 Ordner) | 207 | 1 | 459 | 59 ms | 63 ms | 74 ms |
| STUFE 100 (99 Dateien + 1 Ordner) | 207 | 100 | 25.722 | 243 ms | 273 ms | 273 ms |
| STUFE 5000 (5000 Dateien) | 207 | 5000 | 1.276.122 | 8.848 ms | 10.117 ms | 10.582 ms |
| REFERENZ a PROPFIND /systemtags/ | 207 | 2 | 572 | 48 ms | 73 ms | 90 ms |
| REFERENZ c /spike25/flat ohne nc:system-tags | 207 | 10.001 | 2.830.499 | 336 ms | 371 ms | 400 ms |
| REFERENZ d /spike25/flat mit nc:system-tags | 207 | 10.001 | 3.000.516 | 346 ms | 527 ms | 2.135 ms |
| REFERENZ e GET /status.php | 200 | - | 171 | 16 ms | 23 ms | 24 ms |
| KALT 5000 (n=3, nach graceful) | 207 | 5000 | 1.276.122 | 8.563 ms | - | 8.649 ms |
| STUFE 5000 mit Ballast | 207 | 5000 | 1.276.122 | Reihe über 60 s abgebrochen, Einzellauf 249.568 ms | - | - |
| REFERENZ d mit Ballast | 207 | 10.001 | 22.620.516 | 879 ms | 942 ms | 973 ms |

- `SCHWELLE D-25-04 median_warm_5000=8.848 s schwelle=1.0 s ergebnis=ueber`
- `SCHWELLE D-25-04 (mit Ballast) ... einzellauf=249.568 s ... ergebnis=ueber`
- Aufbau (Annahme A1): 20.000 Dateien in 3,9 s, `files:scan` in 12,0 s. Smoke `setObjectIdsForTag` (A2) grün, kein DAV-Rückfall nötig.
- Ballast: 14 von 35 Füll-Tags in 613 s (etwa 40 s je Tag mit 10.000 Zuordnungen), dann an der 600-s-Grenze abgebrochen: `BALLAST abgebrochen nach 613 s bei 145000 Zuordnungen`.
- Auffällig für den Checkpoint: Der REPORT wächst überlinear (1 zu 100 zu 5000: 59 zu 243 zu 8.848 ms), ein PROPFIND über 10.000 Einträge samt Tags kostet dagegen nur 346 ms. Warm und kalt liegen gleichauf, die Zeit steckt also nicht im OPcache.
- prepare_context mit Daten: Median short 0,72 s (Baseline 0,72 s), full 0,82 s (Baseline 0,81 s). Der REPORT bei 5000 dauert damit gut das Zehnfache der ganzen Bündel-Wanduhr.

## Tasks

| Task | Commit(s) | Inhalt |
|---|---|---|
| 1 | 3594763, 51609a6, bae065d, 7e3bea4, 7e76b11, 1ea1403, b402b82, ab4b22d | je ein Commit pro Block (messbedingungen, datenaufbau, stufen, referenzen, kalt, ballast, schwelle, teardown), Gates jeweils grün |
| 2 | 404b22a, 6b2e4a7 (Werkzeug-Fixes), ea8f9c1 (Rohprotokolle) | Messlauf, Ballast-Nachmessung, prepare_context mit Daten, Rückbau, secret-scan |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Zeitlimit als Blockfehler statt als Messwert**
- **Found during:** Task 2, erster latency-Lauf
- **Issue:** Die Messreihe mit Ballast lief in das 60-s-Clientlimit. `httpx.ReadTimeout` beendete den Block als `BLOCK FAILED`, die Messung mit Ballast fehlte.
- **Fix:** `measure_series` bricht die Reihe beim ersten Timeout ab und schreibt `ZEITLIMIT`, danach folgt ein Einzellauf mit 300 s. Neuer Block `ballast-remeasure` misst nur Stufe 5000 und Referenz d bei stehendem Ballast neu. Die Wiederholung ist im Protokoll mit Grund benannt (`WIEDERHOLUNG Grund: ...`), der Ballast wurde nicht neu aufgebaut.
- **Commit:** 404b22a

**2. [Rule 1 - Bug] Einzellauf neben verwaistem REPORT**
- **Found during:** Task 2, vor der Nachmessung
- **Issue:** Der vom Client aufgegebene REPORT rechnete serverseitig rund 4 min weiter (99 % CPU). Ein sofort folgender Lauf hätte zwei REPORTs gleichzeitig gemessen.
- **Fix:** `wait_until_idle` pollt `docker stats`, bis die CPU unter 10 % liegt. Die Wartezeit steht im Protokoll (195 s).
- **Commit:** 6b2e4a7

### Sonstiges

- DAV-PUT-Rückfall für A2 nicht gebaut: `setObjectIdsForTag` war schon in 25-01 (Block varianten) auf nc35 belegt, der Smoke-Test in diesem Lauf war grün. Scheitert der Smoke-Test, bricht der Block mit `RunFailed` ab, statt still zurückzufallen.
- `PHP_SET_TAG_OBJECTS` nimmt jetzt optional eine Ordnerliste (Subtree-Fall) und gibt die Zusammensetzung aus. Der Aufruf aus 25-01 (vier Argumente) bleibt gültig.
- Gates liefen mit dem Python der venv des Hauptcheckouts und `PYTHONPATH` auf `src` des Worktrees, weil der Worktree keine eigene venv hat. Pyright meldet dazu nur den Hinweis "venv .venv subdirectory not found" und 0 Fehler.
- vulture: Vorwärtsnamen standen nach dem Muster aus 25-01 zwischenzeitlich in `vulture_whitelist.py` und sind mit dem Block `schwelle` wieder entfernt. `WARMUP`, `RUNS_*`, `THRESHOLD_SECONDS`, `summarize` und `SPIKE_CONTAINER` haben die Liste verlassen.
- prepare_context: Das Detail "full" meldet diesmal `degraded=empty`, in der Baseline stand das Mail-Bein noch auf "did not find the mail accounts". Das ist in der Datei als Unterschied benannt, der nicht zur Messung gehört.
- `.env.nc35` wurde nur lesend aus dem Hauptcheckout genutzt (`--env-file ../../../.env.nc35`).

## Known Stubs

Keine.

## Threat Flags

Keine neue Angriffsfläche über das Threat-Register hinaus. Umgesetzt sind: T-25-08 (nur `/spike25` und die Präfixe `kein-ki-spike25` und `spike25-fill-`, Rückbau mit Baseline gleich=ja), T-25-09 (keine Wegwerf-Instanz geprüft, `docker stats` vor jedem Block, Ballast-Grenze 600 s) und T-25-10 (Protokoll erst nach `scan_for_secrets`, Baseline-JSON nur mit Zählern und gelöscht, secret-scan mit 4 Dateien und 0 Funden).

## Self-Check: PASSED

- Dateien vorhanden: scripts/tag_spike.py, tests/unit/test_tag_spike.py, raw/nc35-latenz.txt, raw/nc35-prepare-context-mit-daten.txt; raw/nc35-baseline.json ist wie vorgesehen gelöscht
- Commits vorhanden: 3594763, 51609a6, bae065d, 7e3bea4, 7e76b11, 1ea1403, b402b82, ab4b22d, 404b22a, 6b2e4a7, ea8f9c1
- nc35: `occ tag:list` = [], `/spike25` fehlt, BASELINE viermal gleich=ja
