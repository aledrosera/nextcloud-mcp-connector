---
phase: 25-mess-spike-tag-abfrage
verified: 2026-09-27T12:00:00Z
status: passed
score: 5/5 must-haves verified (Roadmap Success Criteria); alle Plan-Must-Haves (25-01 bis 25-05) zusätzlich geprüft
overrides_applied: 0
---

# Phase 25: Mess-Spike Tag-Abfrage Verification Report

**Phase Goal:** Jede Annahme, auf der die Architektur des Filters ruht, ist gegen echte Nextcloud-Instanzen gemessen statt aus dem Quelltext gelesen; das Messprotokoll entscheidet Batch-Strategie, Notes-Anschluss und Fail-closed-Auslöser
**Verified:** 2026-09-27
**Status:** passed
**Re-verification:** No , initial verification

## Vorgehen

Die Phase trägt laut ROADMAP.md und allen fünf Plan-Frontmatters bewusst keine eigenen Requirement-IDs (`requirements: []`); sie liefert nur die Messvorbedingungen für EXCL-02, EXCL-04 und EXCL-05. Verifiziert wurden deshalb die 5 Erfolgskriterien aus ROADMAP.md Phase 25 sowie die `must_haves` aus allen fünf PLAN-Dateien, jeweils gegen die tatsächlichen Rohprotokolle unter `raw/`, den Messbericht, das Messwerkzeug und die Git-Historie , nicht gegen die SUMMARY-Behauptungen.

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria 1-5)

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | REPORT bei ausgeschalteter systemtags-App ist auf NC 32, 33, 34 (und 35 zur Bestätigung) mit Statuscode und Trefferliste protokolliert; nur Capability/Suchprovider verschwinden | ✓ VERIFIED | `raw/matrix-32.txt`, `-33.txt`, `-34.txt` enthalten je `== app-aus ==` mit `APP-AUS REPORT nachher status=207 treffer=2`; `raw/nc35-befunde.txt` Abschnitt `== app-aus-35 ==`. Präzisierung im Messbericht: auf 32-34 verschwinden Capability/Suchprovider erst nach `docker restart` (APCu-Effekt), auf 35 sofort , als Befund benannt, nicht verschwiegen |
| 2 | REPORT unter AppAPI-Impersonation liefert dieselbe fileid-Menge wie mit App-Passwort | ✓ VERIFIED | `raw/nc35-befunde.txt`: `IMPERSONATION fileids_basic=3 fileids_appapi=3 gleich=ja`, plus Produktionsweg aus dem ExApp-Container `gleich_basic=ja`, plus Kontrollen a/b/c (cloud/user=alice, falsches Secret 401, Logzeile) |
| 3 | Kosten des REPORT als Zahlen bei 1/100/5000 getaggten Knoten, dazu prepare_context-Referenz | ✓ VERIFIED | `raw/nc35-latenz.txt`: STUFE 1/100/5000 mit min/median/p95/max/bytes/treffer; `raw/nc35-prepare-context-baseline.txt` und `-mit-daten.txt`; Schwelle D-25-04 geprüft (8,848 s, über 1,0 s) und über die PostgreSQL-Gegenmessung (`raw/pg-latenz.txt`: 0,182 s, unter 1,0 s) tatsächlich entschieden , nicht nur gemessen, sondern zur Batch-Entscheidung (E3) geführt |
| 4 | Notiz-Id gegen fileid mit Beleg beantwortet (ja/nein), Ergebnis entscheidet Notes-Weg Phase 27 | ✓ VERIFIED | `raw/nc35-befunde.txt`: `NOTIZ-ID GLEICH FILEID: ja` (zwei unabhängige Wege, auch bei umbenannter zweiter Notiz); Owner-Entscheid E1 im Messbericht übernimmt das Ergebnis für Phase 27 |
| 5 | 412 gelöscht/neu, unsichtbares Tag, gleichnamige Varianten, Zielpfad, Freigabe-Grenze je als Einzelbefund | ✓ VERIFIED | `raw/nc35-befunde.txt` Abschnitte `412`, `unsichtbar`, `varianten`, `zielpfad`, `freigabe`; versionsübergreifend bestätigt in `raw/matrix-32/33/34.txt` (412, Zielpfad) |

**Score:** 5/5 Roadmap-Erfolgskriterien verifiziert.

### Zusätzliche Plan-Must-Haves (25-01 bis 25-05)

| Plan | Kern-Must-Have | Status | Evidence |
|---|---|---|---|
| 25-01 | Messwerkzeug + 8 nc35-Einzelbefunde, Rückbau gleich=ja | ✓ VERIFIED | `scripts/tag_spike.py` (3259 Zeilen), `tests/unit/test_tag_spike.py` (44 Tests, alle grün), `compose.spike-tags.yml`; BASELINE-Zeilen in `raw/nc35-befunde.txt` viermal `gleich=ja` |
| 25-02 | Kostenmessung 1/100/5000 + Ballast + Schwelle D-25-04 + Rückbau | ✓ VERIFIED | `raw/nc35-latenz.txt` mit allen STUFE-/Referenz-/Kalt-/Ballast-/Schwelle-Zeilen; BASELINE viermal `gleich=ja`; `nc35-baseline.json` wie vorgesehen gelöscht |
| 25-03 | Versionsmatrix 32-34, App-aus/412/Zielpfad, keine Wegwerf-Reste | ✓ VERIFIED | `raw/matrix-32/33/34.txt` mit allen Pflichtzeilen; `docker ps -a`/`docker volume ls` aktuell leer für `nc-spike-tags` (live geprüft) |
| 25-04 | Messbericht deckt alle 5 Kriterien, Owner-Entscheid D-25-05 mit Datum | ✓ VERIFIED | `25-MESSBERICHT.md` Abschnitte K1-K5, Owner-Entscheid 2026-09-26 mit E1-E4, Ableitungen für Phase 26/27 |
| 25-05 | PostgreSQL-Gegenmessung, Vorfahren-Bündel, Owner-Entscheid E3 | ✓ VERIFIED | `compose.spike-tags-pg.yml`, `raw/pg-latenz.txt`, `raw/sqlite35-kontrolle-latenz.txt`, Abschnitt „PostgreSQL-Gegenmessung (Plan 25-05)" und „Owner-Entscheid E3 (Plan 25-05)" im Messbericht (2026-09-27); `NC35 UNBERUEHRT ... gleich=ja` in beiden neuen Rohdateien |

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `compose.spike-tags.yml` | Wegwerf-Instanz, Loopback 8083, Pflichtvariable | ✓ VERIFIED | `127.0.0.1:8083:80` (1x), `NC_SPIKE_TAG:?` (1x), kein `0.0.0.0` außerhalb Kommentaren |
| `compose.spike-tags-pg.yml` | NC 35 + PostgreSQL 17, Loopback, kein DB-Port | ✓ VERIFIED | gelesen; Loopback 8083, `NC_SPIKE_DB_PASSWORD:?` Pflichtvariable, DB-Dienst ohne `ports:` |
| `scripts/tag_spike.py` | Blöcke controls/findings/latency/matrix/gegenmessung/secret-scan | ✓ VERIFIED | `--help` listet alle 8 Blöcke inkl. `gegenmessung --db pg\|sqlite`; `shell=True` 0x im Code |
| `tests/unit/test_tag_spike.py` | Unit-Tests aller reinen Helfer | ✓ VERIFIED | 44 Tests, `pytest -q` → alle grün (60 Testfälle inkl. parametrisierter) |
| `raw/nc35-befunde.txt`, `raw/nc35-latenz.txt`, `raw/nc35-prepare-context-*.txt`, `raw/matrix-32/33/34.txt`, `raw/pg-latenz.txt`, `raw/sqlite35-kontrolle-latenz.txt` | Rohprotokolle je Plan | ✓ VERIFIED | alle 9 Dateien vorhanden, alle geforderten Abschnittsköpfe und Ergebniszeilen per grep bestätigt |
| `25-MESSBERICHT.md` | Messbericht mit Owner-Entscheid | ✓ VERIFIED | Befundtabelle K1-K5, G1-G5, zwei Owner-Entscheid-Abschnitte mit Datum |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `scripts/tag_spike.py` | `raw/*.txt` | `write_protocol` nach `scan_for_secrets` | ✓ WIRED | live ausgeführt: `--block secret-scan` → `secret-scan: 10 files, 0 findings` |
| `25-MESSBERICHT.md` | `raw/pg-latenz.txt`, `raw/sqlite35-kontrolle-latenz.txt` | wörtliche Zitate der Medianwerte | ✓ WIRED | `median=182`, `median=172` etc. wörtlich im Bericht wie in den Rohdateien |
| `25-MESSBERICHT.md` | `.planning/REQUIREMENTS.md` (EXCL-02) | nur bei freigegebenem neuem Wortlaut ändern | ✓ WIRED | Owner wählte `empfehlung`/`report-je-antwort`; EXCL-02 in REQUIREMENTS.md unverändert (Git-Historie zeigt nur eine Erst-Einfügung, keine spätere Änderung) |
| Alle Plan-Commits | Repository-Historie | einzelne Commits je Block | ✓ WIRED | 27 in Summaries genannte Commit-Hashes stichprobenartig gegen `git cat-file -e` geprüft , alle vorhanden |

### Data-Flow Trace (Level 4)

Nicht anwendbar im klassischen Sinn (kein UI/State-Rendering) , stattdessen wurde die Kette „Messwert im Rohprotokoll → wörtlich im Messbericht zitiert → Owner-Entscheid darauf gestützt" geprüft:

| Kennzahl | Rohdatei | Zitiert im Messbericht | Owner-Entscheid darauf gestützt |
|---|---|---|---|
| Median warm Stufe 5000, SQLite (nc35) | `8848` ms | ja, Tabelle K3 und G1 | Schwelle D-25-04 „über" → Zusatzplan 25-05 ausgelöst |
| Median warm Stufe 5000, PostgreSQL | `182` ms | ja, Tabelle G1/G5 | E3 „report-je-antwort" bestätigt (Regel A greift) |
| Notiz-Id = fileid | `933`/`933`, `934`/`934` | ja, Tabelle K4 | E1 „EXCL-05 bauen" |

Alle drei Ketten sind lückenlos nachvollziehbar, keine Ableitung ohne Rohbeleg gefunden.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Unit-Tests der reinen Helfer laufen | `uv run --no-sync pytest tests/unit/test_tag_spike.py -q` | 60 passed | ✓ PASS |
| ruff check | `uv run --no-sync ruff check scripts/tag_spike.py tests/unit/test_tag_spike.py` | All checks passed! | ✓ PASS |
| ruff format --check | `uv run --no-sync ruff format --check ...` | 2 files already formatted | ✓ PASS |
| vulture | `uv run --no-sync vulture src scripts vulture_whitelist.py` | keine Ausgabe (0 Funde) | ✓ PASS |
| CLI-Blockliste vollständig | `python scripts/tag_spike.py --help` | listet controls, findings, latency, ballast-remeasure, teardown, matrix, gegenmessung, secret-scan | ✓ PASS |
| secret-scan live | `python scripts/tag_spike.py --env-file .env.nc35 --block secret-scan` | `secret-scan: 10 files, 0 findings` | ✓ PASS |
| Keine Wegwerf-Reste aktuell auf dem Host | `docker ps -a --filter name=nc-spike-tags`, `docker volume ls --filter name=nc-spike-tags` | beide leer | ✓ PASS |
| Commit-Hashes aus Summaries existieren | `git cat-file -e <hash>` für 16 Stichproben | alle vorhanden | ✓ PASS |
| EXCL-02 unverändert seit Ersteinfügung | `git log -p -- .planning/REQUIREMENTS.md \| grep EXCL-02` | nur eine Einfügung, keine Änderung | ✓ PASS |

### Probe Execution

Keine dedizierten `scripts/*/tests/probe-*.sh`-Dateien für diese Phase gefunden; die Phase liefert stattdessen Messprotokolle als Belege. Nicht anwendbar (SKIPPED, kein konventioneller Probe-Pfad für diesen Phasentyp).

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| EXCL-02 (Messvorbedingung) | 25-02, 25-05 | Batch-Entscheid „ein REPORT je Antwort" | ✓ SATISFIED | Messwert PostgreSQL 0,182/0,172 s unter Schwelle; Owner-Entscheid E3 „empfehlung" 2026-09-27; Wortlaut in REQUIREMENTS.md unverändert wie entschieden |
| EXCL-04 (Messvorbedingung) | 25-01, 25-03, 25-04 | Fail-closed-Auslöser = REPORT-Ausgang, nicht Capability | ✓ SATISFIED | K1-Tabelle über 4 Versionen, Owner-Entscheid E2 „empfehlung" |
| EXCL-05 (Messbedingung) | 25-01, 25-04 | Notiz-Id = fileid entscheidet Notes-Anschluss | ✓ SATISFIED | `NOTIZ-ID GLEICH FILEID: ja`, Owner-Entscheid E1 „EXCL-05 bauen" |

Keine verwaisten Requirements: laut REQUIREMENTS.md Zeile 82 trägt Phase 25 bewusst keine eigenen IDs; alle drei referenzierten IDs sind offiziell Phase 26/27 zugeordnet (Pending), was korrekt ist , Phase 25 liefert nur die Messgrundlage, nicht die Umsetzung.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---|---|---|---|
| `scripts/tag_spike.py` | diverse (siehe `25-REVIEW.md`) | 7 Warnings aus vorhandenem Code-Review (stdout/stderr-Vermengung, `wait_until_idle`-Rückgabewert, Reihenfolge-Bug in `measure_bundle`, unerreichbarer Schwellen-Zweig, `block_notes` stürzt im Negativfall ab, Papierkorb-Reste bei nicht-leerem Ausgangszustand, toter `access_lines`-Code) | ⚠️ WARNING (bereits dokumentiert, 0 Critical) | Betrifft die Robustheit des Wegwerf-Messwerkzeugs für künftige Läufe, nicht die Korrektheit der bereits vorliegenden Messwerte: alle Rohprotokolle zeigen konsistente Ergebnisse (kein unerwartetes `BLOCK FAILED`, keine `gleich=nein`-Zeile, keine „nicht messbar"-Lücke ohne begründete Zeile). Kein Fund von TBD/FIXME/XXX ohne Referenz |

Keine Debt-Marker (TBD/FIXME/XXX) im gesamten Skript gefunden. Der vorhandene `25-REVIEW.md` (2026-09-27, `status: issues_found`, 0 Critical/7 Warning/7 Info) wurde als unabhängige Quelle gegengeprüft; keine der Warnungen betrifft eine bereits abgelieferte Messung, da der Negativfall (der `block_notes` abstürzen ließe) im tatsächlichen Lauf nicht eintrat und alle Rückbau-Zeilen `gleich=ja` zeigen.

### Human Verification Required

Keine. Beide vorgesehenen Owner-Checkpoints (D-25-05 am 2026-09-26 und E3 am 2026-09-27) sind bereits durchlaufen, mit Datum, wörtlicher Owner-Antwort und Options-Id im Messbericht dokumentiert und durch die Git-Historie (Commits `1924085`, `d29b900`) belegt. Es bleibt keine offene Entscheidung, die einer weiteren menschlichen Prüfung bedürfte.

### Gaps Summary

Keine Gaps gefunden. Alle fünf Roadmap-Erfolgskriterien sind durch Rohprotokolle belegt, das Messwerkzeug ist unit-getestet und alle Qualitätsgates (pytest, ruff check, ruff format, vulture) laufen grün, der secret-scan läuft live mit 0 Funden, keine Wegwerf-Container/-Volumes sind auf dem Host zurückgeblieben, nc35 ist nachweislich unberührt (`NC35 UNBERUEHRT ... gleich=ja`), und beide Owner-Checkpoints (D-25-05, E3) sind mit Datum und wörtlicher Antwort abgeschlossen. Die zusätzliche PostgreSQL-Gegenmessung (Plan 25-05, per Owner-Entscheid vom 26.09. beauftragt) ist vollständig durchgeführt und im Messbericht nachgetragen. Die 7 Warnings aus dem separaten Code-Review (`25-REVIEW.md`) betreffen die Robustheit des Werkzeugs für künftige Läufe, nicht die Gültigkeit der bereits erhobenen und dokumentierten Messwerte, und werden hier nicht als Gap gewertet.

---

_Verified: 2026-09-27_
_Verifier: Claude (gsd-verifier)_
