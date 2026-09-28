---
phase: 28-gates-und-beweise
plan: 02
subsystem: tests/contract
tags: [gate-01, freeze, kein-ki, klassifikation]
requires: []
provides:
  - tests/contract/tool_classes.py (FILE_READERS, FILE_WRITERS, UNAFFECTED, MIN_REASON, PAIR_CASES, NAMED_EXCEPTIONS, unclassified, freeze_findings, probe_tool)
  - tests/contract/result_shapes.py (requested_forms, normalised, surfaces, leaks)
affects: [28-canary, 28-pair-tests]
tech-stack:
  added: []
  patterns: [eine reine Befundfunktion für Gate und Gegenprobe, Laufzeit-Probe mit finally remove_tool]
key-files:
  created:
    - tests/contract/tool_classes.py
    - tests/contract/result_shapes.py
    - tests/contract/test_tool_classes.py
    - tests/contract/test_result_shapes.py
  modified:
    - pyproject.toml
decisions:
  - "freeze_findings druckt Befunde als 'unclassified: <name>', 'stale: <name>', 'in more than one class: ...', '<problem>: <KLASSE>[<name>]'; Kanarie und Paartests können darauf aufsetzen"
  - "Grund gilt als gültig ab 20 Zeichen, einzeilig, mit Schlusspunkt"
metrics:
  duration: ~20 min
  completed: 2026-09-28
  tasks: 2
  files: 5
---

# Phase 28 Plan 02: GATE-01 Klassifikations-Freeze Summary

Drei-Klassen-Tabelle (12 Leser / 3 Schreiber / 7 nicht betroffen, je ein Satz Grund mit Datei:Zeile) gegen die laufende Registry, mit Laufzeit-Probe `files_update`, die rot macht und spurlos verschwindet; dazu gemeinsame Vergleichs- und Scanbausteine für GATE-02/03.

## Erledigt

| Task | Inhalt | Commit |
|------|--------|--------|
| 1 | tool_classes.py, result_shapes.py, pythonpath um tests/contract | 8f91ac6 |
| 2 | test_tool_classes.py (7 Tests), test_result_shapes.py (6 Tests) | 702776f |

- `tables_browse` steht in FILE_READERS (D-28-14); calendar_create_event, deck_create_card, tables_create_row in UNAFFECTED.
- PAIR_CASES mit 14 Fällen (Familien files/apps), NAMED_EXCEPTIONS genau ("notes_create","category") nach D-28-16.
- `freeze_findings` prüft: unclassified, stale, Doppelklasse, Grundqualität, PAIR_CASES nur für Leser/Schreiber, jeder Schreiber hat einen Paarfall, Ausnahmen nur für vorhandene Paarfälle.
- `probe_tool` registriert per `mcp.add_tool(..., annotations=CREATE_ONLY, structured_output=False)` und entfernt in `finally`.
- `requested_forms` definiert die angefragte Id wörtlich im Docstring (Pfad plus dirname-Kette, fetch-Id plus nackte Id und Segmente ab 3 Zeichen).

## Gates

- pytest tests/unit tests/contract: Exit 0 (13 neue Tests grün, test_tool_surface unverändert grün)
- ruff check, ruff format --check: grün
- pyright latest: 0 errors
- vulture src scripts vulture_whitelist.py: Exit 0
- check_tool_budget.py: Exit 0
- `git diff -- src/`: leer

## Deviations from Plan

- TDD-Hinweis: Task 2 trägt `tdd="true"`, die Implementierung kam aber planmäßig schon in Task 1. Die Tests liefen daher direkt grün; die Rotprobe liefert der Test selbst (Probe-Werkzeug und monkeypatch-Gegenproben über dieselbe `freeze_findings`). Kein separater RED-Commit.
- Werkzeug-Aufrufe: pyright/vulture über die Binaries der Haupt-venv statt `uv run` (kein zweites venv im Worktree); inhaltlich gleiche Gates.

Sonst: Plan wie geschrieben ausgeführt.

## Threat Flags

Keine; nur Testcode, keine neue Oberfläche.

## Self-Check: PASSED

- tests/contract/tool_classes.py, result_shapes.py, test_tool_classes.py, test_result_shapes.py: vorhanden
- Commits 8f91ac6, 702776f: vorhanden
