---
phase: quick-260930-ty7
plan: 01
status: complete
subsystem: ci
tags: [ci, gates, nc35, WR-04]
requirements: [GATE-02, GATE-03, WR-04]
key-files:
  created: []
  modified:
    - compose.exapp.yml
    - .github/workflows/ci.yml
    - scripts/bootstrap_exapp.sh
    - tests/integration/canary_world.py
    - tests/unit/test_live_requirement.py
decisions:
  - "Kanarie und Paarbeweise laufen in CI nur noch auf NC 35.0.1 (neuer Job canary-nc35), NC 34 bleibt über Job exapp abgedeckt"
  - "Image-Wechsel über Compose-Variable NC_EXAPP_NEXTCLOUD_IMAGE mit Default 34.0.3, nicht über compose.nc35.yml (Windows-Pfad, lokales Image, keine Registry)"
metrics:
  completed: 2026-09-30
  tasks: 2
  commits: 1
---

# Quick 260930-ty7: CI-Kanarie auf NC 35 Summary

Kanarie- und Paarbeweise (GATE-02/03) laufen jetzt im eigenen CI-Job `canary-nc35` auf dem offiziellen `nextcloud:35.0.1-apache`, mit `occ status`-Versionsprüfung und `NC_MCP_REQUIRE_LIVE=1`; Job `exapp` und alle lokalen Läufe bleiben per Compose-Default auf 34.0.3.

## Umsetzung

- `compose.exapp.yml`: `image: "${NC_EXAPP_NEXTCLOUD_IMAGE:-nextcloud:34.0.3-apache}"` plus Begründungsabsatz (EXAPP-06, WR-04, nur Patch-Tags).
- `.github/workflows/ci.yml`: Gate-Schritt aus `exapp` entfernt; neuer Job `canary-nc35` (Job-Level-Env mit dem 35.0.1-Image, HaRP-Key mit Maske, Topologie, Bootstrap im Default-Modus, Versionscheck `versionstring: 35\.0\.1`, ExApp-Check, `uv sync --frozen`, Gate-Schritt, Logs bei Fehler). Kein Findling-Install im neuen Job.
- `scripts/bootstrap_exapp.sh`: Kommentar zu Fallback 1 nennt 34.x (Default) und 35.x (Override).
- `tests/integration/canary_world.py`: Docstring von `live_env` nennt `canary-nc35`.
- `tests/unit/test_live_requirement.py`: zwei neue Wächter (`test_the_gates_run_on_nextcloud_35_only`, `test_the_exapp_topology_stays_on_34_0_3_by_default`).

## Verifikation

- YAML-Strukturprüfung (isoliertes uv mit PyYAML): ok, Jobs `unit, image, exapp, canary-nc35, integration`.
- `docker compose config --images` (ohne Daemon möglich): ohne Override `nextcloud:34.0.3-apache`, mit Override `nextcloud:35.0.1-apache`.
- actionlint: nicht installiert, übersprungen.
- Mutationsprobe (temporär, zurückgesetzt): Compose-Default auf 35 und Job-Umbenennung plus Versionscheck-Aufweichung lassen beide neuen Tests scheitern.
- ruff check, ruff format --check (316 Dateien), pyright latest (0 Fehler), vulture: grün.
- pytest tests/unit tests/contract: 5102 passed, 33 skipped.
- Die drei Live-Dateien ohne Live-Umgebung: sammeln und skippen sauber.

## Offen (Owner)

- Echter Beweis ist der erste CI-Lauf von `canary-nc35` nach dem Owner-Push: muss `versionstring: 35.0.1` sowie die vier Zeilen `KANARIE <modus> geprüft 22 von 22` und die `PAARE ... verglichen`-Zeilen wie in 28-LIVE-BEWEIS.md zeigen. Bis dahin bleiben GATE-02/03 offen (28-REVIEW.md WR-04).
- Nicht gepusht.

## Deviations from Plan

None - plan executed exactly as written (einzige Ergänzung: `docker compose config` ohne laufenden Daemon direkt ausgeführt statt übersprungen).

## Commits

- c358b40: ci: run the canary and pair proofs on Nextcloud 35.0.1 only (WR-04) (inkl. PLAN.md)

## Self-Check: PASSED
