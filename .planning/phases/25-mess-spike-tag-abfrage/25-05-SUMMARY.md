---
phase: 25-mess-spike-tag-abfrage
plan: 05
subsystem: messwerkzeug / PostgreSQL-Gegenmessung
tags: [spike, systemtags, webdav-report, postgresql, latenz, schwelle, vorfahren, messung]
requires:
  - 25-02 (Latency-Kette, Zeitlimit als Messwert, wait_until_idle)
  - 25-03 (Wegwerf-Instanz-Muster, compose-Secrets per env, down -v im finally)
  - 25-04 (Messbericht, Owner-Entscheid D-25-05 Option postgres-gegenmessung)
provides:
  - compose.spike-tags-pg.yml (Wegwerf-Paar NC 35.0.0 plus postgres:17-alpine, Loopback 8083)
  - scripts/tag_spike.py (Block gegenmessung --db pg|sqlite, Vorfahren-Bündel V1 bis V4p, Container-parametrisierte Latency-Kette)
  - raw/pg-latenz.txt, raw/sqlite35-kontrolle-latenz.txt
  - 25-MESSBERICHT.md Abschnitte "PostgreSQL-Gegenmessung (Plan 25-05)" und "Owner-Entscheid E3 (Plan 25-05)"
affects: [26, 29]
tech-stack:
  added: []
  patterns:
    - "Gegenmessung auf demselben Image mit zwei Datenbanken nacheinander trennt den Datenbankeffekt vom Instanzeffekt"
    - "Querprüfung eines Alternativwegs gegen die REPORT-Menge nach Segmentregel (gleich=ja|nein)"
key-files:
  created:
    - compose.spike-tags-pg.yml
    - .planning/phases/25-mess-spike-tag-abfrage/raw/pg-latenz.txt
    - .planning/phases/25-mess-spike-tag-abfrage/raw/sqlite35-kontrolle-latenz.txt
  modified:
    - scripts/tag_spike.py
    - tests/unit/test_tag_spike.py
    - vulture_whitelist.py
    - .planning/phases/25-mess-spike-tag-abfrage/25-MESSBERICHT.md
decisions:
  - "E3 entschieden am 2026-09-27 (Owner, vom Orchestrator wörtlich übermittelt: \"ok machen wir wie die empfehlung\"): Option empfehlung = report-je-antwort; EXCL-02 bleibt unverändert bei ein REPORT je Antwort, REQUIREMENTS.md und ROADMAP.md unverändert"
  - "PostgreSQL 17 trägt den REPORT: Stufe 5000 Median warm 182 ms, mit Ballast 172 ms (Schwelle D-25-04 unter); der SQLite-Wert von nc35 (8,8 s) ist ein Datenbankeffekt, die SQLite-Kontrolle auf frischer Instanz misst 8,1 s"
  - "SQLite-Grenze für Phase 29: bei 140.000 Zuordnungen kostet schon ein REPORT mit einem Treffer 240 s; der Guard steht dort praktisch immer auf nicht prüfbar"
metrics:
  duration: "ca. 2 h 10 min (davon Messläufe 43 min PostgreSQL, 57 min SQLite)"
  completed: 2026-09-27
  tasks: 4
  files: 8
---

# Phase 25 Plan 05: PostgreSQL-Gegenmessung Summary

Auf einer Wegwerf-Instanz Nextcloud 35.0.0 mit PostgreSQL 17.11 kostet der REPORT oc:filter-files bei 5000 getaggten Knoten im Median warm 0,182 s, mit Ballast 0,172 s. Die Schwelle D-25-04 wird dort also eingehalten. Die SQLite-Kontrolle auf demselben Image liegt mit 8,114 s nahe an nc35. Der Owner hat E3 danach auf "ein REPORT je Antwort" entschieden, EXCL-02 bleibt unverändert.

## Messwerte (Median warm, n=15)

| Messung | PostgreSQL | SQLite-Kontrolle | nc35 (25-02) |
|---|---|---|---|
| Stufe 1 / 100 / 5000 | 55 / 58 / 182 ms | 47 / 200 / 8.114 ms | 59 / 243 / 8.848 ms |
| Stufe 1 / 100 / 5000 mit Ballast | 62 / 59 / 172 ms (110.005 bis 115.004 Zuordnungen) | Einzelläufe 240.298 / 240.749 / 249.651 ms (140.005 bis 145.004) | 5000: Einzellauf 249.568 ms |
| Vorfahren V1 / V2 / V3p / V4p mit Ballast | 391 / 1.003 / 1.578 / 6.821 ms | 223 / 992 / 1.063 / 4.512 ms | nicht gemessen |
| Querprüfung Vorfahren gegen REPORT | 12 von 12 gleich=ja | 12 von 12 gleich=ja | |
| Varianten X/Y/W/Z | wie nc35 (X und Y Vereinigung, W getrennt, Z 412); nc:system-tags liefert W in Originalschreibung | gleich | |

## Tasks

| Task | Commit(s) | Inhalt |
|---|---|---|
| 1 | 898b50f, bfc46fc, be46245, 54ae160, 649fd5a, 71ec6e6, d632da7 | Abschnitte A bis F: compose pg-Variante, Tests RED, reine Helfer, Container-Parametrisierung, Vorfahren-Bündel, Block gegenmessung, Whitelist wieder leer; Gates je Abschnitt grün |
| 2 | 6865a6e | PostgreSQL-Lauf, danach SQLite-Kontrolllauf; beide Instanzen abgebaut, nc35 unberührt, secret-scan 0 Funde |
| 3 | 5e1fba1 | Messbericht-Nachtrag G1 bis G5, Grenzen, E3-Empfehlung nach Regel A, EXCL-02-Entwurf vorfahren-propfind |
| 4 | 1924085 | Owner-Entscheid E3 im Messbericht, Phase-26-Ableitung ergänzt |

## Deviations from Plan

### Auto-fixed Issues

Keine. Es gab weder Werkzeugfehler noch Wiederholungen.

### Sonstiges

- Ballast auf PostgreSQL an der 900-s-Grenze abgebrochen: `BALLAST abgebrochen nach 926 s bei 110104 Zuordnungen`, also 110.000 statt 140.000 Fremd-Zuordnungen. Laut Plan ist das ein Messwert, im Bericht steht es unter Grenzen.
- Die Zeile VARIANTEN dbtype ist jetzt datenbankneutral ("SQLite vergleicht binär" steht nur noch bei sqlite3).
- Nach dem Anlegen von alice sorgt ein PROPFIND Depth 0 auf das Home dafür, dass ihr Dateisystem existiert, bevor der Datenaufbau per Shell schreibt.
- Die Zusammensetzungszeilen der Ballast-Stufen tragen `zuordnungen_gesamt=` (die Plan-Zeile mit PHP_COUNT_MAPPINGS).
- Zusätzlicher Unit-Test für format_bundle (die Zeile VORFAHREN).
- Gates liefen mit dem Python der venv des Hauptcheckouts und PYTHONPATH=src. `.env.nc35` wurde nur lesend aus dem Hauptcheckout genutzt. postgres:17-alpine bleibt als Image auf dem Host liegen.

## Known Stubs

Keine.

## Threat Flags

Keine neue Angriffsfläche über das Threat-Register hinaus. Umgesetzt: T-25-20 (drei Zufallspasswörter je Lauf, nur env/stdin, psql über den lokalen Socket), T-25-21 (nur 127.0.0.1:8083, DB ohne Port, down -v im finally), T-25-22 (RAM-Vorbedingung frei 5,93 bzw. 5,92 GiB, mem_limit, Läufe nacheinander), T-25-23 (NC35 UNBERUEHRT gleich=ja in beiden Läufen), T-25-SC (Digest sha256:b0f9560a... im Protokoll).

## Self-Check: PASSED

- Dateien vorhanden: compose.spike-tags-pg.yml, scripts/tag_spike.py, raw/pg-latenz.txt, raw/sqlite35-kontrolle-latenz.txt, 25-MESSBERICHT.md
- Commits vorhanden: 898b50f, bfc46fc, be46245, 54ae160, 649fd5a, 71ec6e6, d632da7, 6865a6e, 5e1fba1, 1924085
- Keine Container und kein Volume mit dem Namen nc-spike-tags, secret-scan Exit 0
