---
phase: 29-pr-fkommando-und-doku
plan: 06
subsystem: testing
tags: [nc35, occ, exclusion, live-proof, ci]

requires:
  - phase: 29-pr-fkommando-und-doku
    provides: occ mcp_connector:exclusion:check (29-04 Handler, 29-05 Verdrahtung)
provides:
  - tests/integration/test_exclusion_check_live.py (Fälle A bis H, Tabellen-Diff je Aufruf)
  - CI-Schritt "exclusion:check live (OPS-01)" im Job canary-nc35
  - raw/29-06-live-beweis.txt (wörtliche Ausgaben mit Zeilennummern für 29-07)
affects: [29-07, 29-08, 29-09]

tech-stack:
  added: []
  patterns:
    - "Tabellen-Dump per PHP-QueryBuilder über stdin, Zeilenzahl plus SHA-256 vor und nach jedem Aufruf"
    - "Eigenes Admin-Konto je Lauf, Passwort über die Umgebung von docker exec (-e OC_PASS ohne Wert)"

key-files:
  created:
    - tests/integration/test_exclusion_check_live.py
    - .planning/phases/29-pr-fkommando-und-doku/raw/29-06-live-beweis.txt
  modified:
    - .github/workflows/ci.yml

key-decisions:
  - "Passwort des Test-Admins über -e OC_PASS ohne Wert plus Prozessumgebung statt -e OC_PASS=<wert>: nie im argv"
  - "Fall G läuft im selben Test wie B (gleicher Aufbau), Fall D zusätzlich ohne --admin"

requirements-completed: [OPS-01]

duration: 30min
completed: 2026-10-01
---

# Phase 29 Plan 06: Live-Beweis exclusion:check Summary

**occ mcp_connector:exclusion:check gegen nc35 (35.0.0) in allen Fällen A bis H belegt, 80 Tabellenvergleiche vor/nach je Aufruf gleich, derselbe Test als CI-Schritt im Job canary-nc35**

## Performance

- **Duration:** ca. 30 min
- **Completed:** 2026-10-01
- **Tasks:** 2/2
- **Files:** 2 erstellt, 1 geändert

## Accomplishments

- Live-Test mit 7 Testfunktionen (A, B+G, C, D, E, F, H), je Option Text und --json, je Aufruf Dump vorher/nachher von systemtag, systemtag_object_mapping, systemtag_group, appconfig(systemtags)
- Vorbedingungen: Kommando registriert (sonst skip_or_fail "ExApp aus aktuellem Quellstand neu bauen"), Instanz ohne kein-ki-Schreibweise
- ExApp in nc35 aus dem Arbeitsbaum neu gebaut: `app_api:app:unregister mcp_connector`, dann `bash scripts/bootstrap_exapp.sh --nc35` (Image 0.3.2, sha256:73beb4e9...), danach fünf Kommandos inkl. exclusion:check mit --admin und --json
- Live-Lauf: `PYTHONUTF8=1 NC_MCP_REQUIRE_LIVE=1 uv run pytest tests/integration/test_exclusion_check_live.py -m integration -s` mit .env.nc35 und NC_MCP_E2E_*-Exporten: **7 passed in 40.63s, 0 failed**, erster Lauf, kein Fix nötig
- Ohne Live-Variablen: 7 skipped, Exit 0

## Ergebnisse je Fall

| Fall | Ergebnis |
|------|----------|
| A kein Tag | passed=true mode=none; ohne --admin passed=true admin_checked=false, Hinweis tag:add |
| B Selbstbedienung | passed=true mode=self_service assigned=1 |
| C Organisationsmodus | passed=true mode=organisation, gid in Text und JSON |
| D unsichtbar | mit --admin passed=false, tag_visible failed; ohne --admin passed=true admin_checked=false |
| E nur "Kein KI" | passed=false, tag_exists und no_variants failed |
| F kein-ki + keinki | passed=true unprotected=1, Warnung nennt keinki |
| G ohne --admin (B) | passed=true admin_checked=false, Satz zu nicht geprüften Teilen |
| H --admin=alice | checked=false passed=false |

Tabellen-Diff in allen 20 Aufrufen leer; keine Ausgabe mit Dateiname, Pfad, fileid oder uid; alle CLEANUP-Zeilen gelesen ok.

## Task Commits

1. **Task 1: Live-Test und CI-Schritt** - `2a3529b` (test)
2. **Task 2: Live-Beweis** - `849ed3f` (test)

## Gates

Vor Commit 2a3529b grün: ruff check, ruff format --check, pyright latest (0 Fehler), vulture (src scripts vulture_whitelist.py), PYTHONUTF8=1 pytest tests/unit tests/contract. Plan-Verify Task 1 (CI-Blockprüfung, skip ohne Env) und Task 2 (gleich=ja, keine Abweichung, FALL A bis H, strichfrei) grün.

## Deviations from Plan

1. **[Rule 2 - Security] Passwortweg:** Plan nannte `docker exec -e OC_PASS=<zufall>`; gebaut ist `-e OC_PASS` ohne Wert mit dem Passwort in der Prozessumgebung, damit es nie im argv steht (T-29-22).
2. **Orchestrator-Vorgabe:** nc35 nach dem Lauf gestoppt (Volumes bleiben), ExApp-Container und Registry gestoppt, Docker Desktop beendet. Für den Bau lief zusätzlich der Registry-Container der 34-Topologie (nc-mcp-exapp-registry), sonst nichts außerhalb nc35.
3. **Bootstrap braucht HP_SHARED_KEY:** erster Bootstrap-Versuch ohne `. ./.env.nc35` hing in der Installationswarteschleife (compose-Interpolation scheitert still); abgebrochen, mit Env neu gestartet. Kein Code betroffen.

## Hinweise für 29-07

- Zeilennummern der wörtlichen Ausgaben stehen als DOKU-AUSGABE-Liste in raw/29-06-live-beweis.txt
- Fall D ohne --admin: der Hinweis empfiehlt `php occ tag:add kein-ki public`, obwohl ein unsichtbares kein-ki existiert (tag:add würde mit "already exists" scheitern); die Doku sollte dort auf den Lauf mit --admin verweisen
- Der CI-Schritt läuft erst nach dem nächsten Owner-Push (wie A-28-09)

## Known Stubs

Keine.

## Self-Check: PASSED

- tests/integration/test_exclusion_check_live.py, raw/29-06-live-beweis.txt vorhanden, ci.yml enthält den Schritt
- Commits 2a3529b, 849ed3f vorhanden
