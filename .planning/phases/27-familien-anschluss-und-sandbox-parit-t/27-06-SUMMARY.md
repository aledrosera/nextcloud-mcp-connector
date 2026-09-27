---
phase: 27-familien-anschluss-und-sandbox-parit-t
plan: 06
subsystem: prepare-context
tags: [exclusion, kein-ki, prepare_context, single-flight]
requires:
  - "27-01: withhold.EXCLUSION_UNAVAILABLE, withhold.degraded_entry, guard_routes"
  - "27-03: unified_search filtert still und meldet {provider: exclusion}"
  - "27-05: talk_browse (Digest) mit file_screen und {source: exclusion}"
provides:
  - "prepare_context hält die Guard-Flight selbst (erstes gather-Mitglied, ohne Budget)"
  - "context._one_exclusion_entry: genau ein {source: exclusion} je Bündel"
  - "tests/unit/test_context_exclusion.py: familienübergreifender Bündelbeweis"
affects:
  - "prepare_context (short und full)"
  - "27-07/27-08: Live-Messung, ein REPORT je Bündel"
tech-stack:
  added: []
  patterns:
    - "Flight-Halter als eigenes gather-Mitglied ohne Budget statt asyncio.shield (Pattern 6)"
    - "Deduplizierung über den Wortlaut EXCLUSION_UNAVAILABLE, nicht über den Schlüssel"
key-files:
  created:
    - tests/unit/test_context_exclusion.py
  modified:
    - src/mcp_connector/tools/context.py
decisions:
  - "Kein asyncio.shield: der Guard ist erstes gather-Mitglied von prepare_context; sein Ergebnis wird nicht gelesen, eine Exception dort ignoriert, weil jedes Bein den Guard selbst fragt und fail-closed entscheidet"
  - "_one_exclusion_entry erkennt Einträge am reason (EXCLUSION_UNAVAILABLE), damit Suche (provider), Talk (source) und Ausschnitte (Hit-id) gleich behandelt werden; der eine Eintrag steht an der Stelle des ersten"
  - "REPORT-Zählung im Flight-Test beim Start des Requests: respx zählt einen Call erst, wenn sein side_effect zurückkehrt, ein abgebrochener REPORT fehlt sonst in call_count"
metrics:
  duration: "ca. 25 min"
  completed: 2026-09-27
  tasks: 2
  files: 2
---

# Phase 27 Plan 06: prepare_context am Guard Summary

prepare_context stößt `clients.exclusion.scope(clients)` als erstes gather-Mitglied an und hält damit die Flight außerhalb jedes Bein-Budgets; ein Bündel kostet auch bei `detail="full"` genau einen REPORT, und "nicht prüfbar" erscheint als genau ein Eintrag `{"source": "exclusion", "reason": EXCLUSION_UNAVAILABLE}`.

## Was gebaut wurde

**Task 1 (context.py):**
- gather in `prepare_context`: `clients.exclusion.scope(clients)` steht vor `search_tools.unified_search` (Zeile 255 vor 256), Kommentar zu Merker (c) und den 8 bis 10 s auf SQLite.
- `_one_exclusion_entry(degraded)`: entfernt alle Einträge mit `reason == withhold.EXCLUSION_UNAVAILABLE` und setzt an der Stelle des ersten `withhold.degraded_entry("source")`; übrige Einträge unverändert in Reihenfolge. Aufruf nach `_excerpts`, vor `result["degraded"]`.
- Tests: Flight-Test (TALK_BUDGET 0.05, REPORT 0.2 s, Provider-Liste 0.02 s verzögert, damit Talk zuerst am Guard ist): vorher 2 gestartete REPORTs, nachher 1. Unverifiable: genau ein Ausschluss-Eintrag, Kalender-Timeout bleibt dahinter. Untagged: json-gleich zu `patch_untagged`, REPORT 0. Direkter Test von `_one_exclusion_entry` mit Ausschnitts-Eintrag.

**Task 2 (Bündeltest):**
- `detail="full"` mit Datei 901 und Ordner Projekt (900): nur 903 in `results.file`, Ausschnitt vorhanden, Digest zeigt `Siehe {file}`, kein degraded, kein Schlüssel mit withheld/excluded; `json.dumps` ohne `geheim.txt`, `901`, `Projekt/a.txt`; `report.call_count == 1`, Tag-Liste `call_count == 1`.
- Kappungssatz: 7 sichtbare plus 3 getaggte files-Treffer ergeben "Only the first 5 of 7 hits are listed."
- vulture_whitelist.py: keine Änderung nötig, 27-05 hatte den Abschnitt bereits auf "Empty again, as announced" gesetzt; `grep -c "leaves with plan 27-06"` = 0.

## Verifikation

- `ruff check .`, `ruff format --check .`: grün; pyright (latest): 0 errors; vulture: grün.
- `pytest tests/unit tests/contract`: 4814 passed, 33 skipped.
- `check_tool_budget.py`: exit 0 (17233 von 18000 Bytes).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug im Test] respx zählt abgebrochene REPORTs nicht**
- **Found during:** Task 1 (RED)
- **Issue:** Der Flight-Test lief ohne Fix grün: respx verbucht einen Call erst nach Rückkehr des side_effect, der von Talk abgebrochene REPORT fehlte in `call_count`.
- **Fix:** Zusätzliche Zählung beim Start im side_effect (`started`), plus verzögerte Provider-Liste, damit Talk die Flight ohne Fix wirklich startet. RED danach: 2 gestartete REPORTs.
- **Commit:** 0345a97

### Ausführungsumgebung

- Worktree-Base wich ab und wurde laut Auftrag per `git reset --hard e29c3ad` korrigiert.
- venv des Hauptrepos (`../../../.venv`), pytest mit `-o "pythonpath=src tests/integration tests/unit"`, pyright mit `--pythonpath`.

## TDD Gate Compliance

- Task 1: RED `0345a97`, GREEN `5b230e2`.
- Task 2: reine Beweistests (`d24a372`), liefen sofort grün, weil die Filterung aus den Beinen (27-03, 27-05) und der Flight-Halter aus Task 1 schon da sind; kein Produktionscode in Task 2.

## Known Stubs

Keine.

## Threat Flags

Keine neue Angriffsfläche. T-27-50 (Flight-Halter), T-27-51 (Kappung auf gefilterten Treffern), T-27-52 (Ausschnitte nur aus gefilterten Treffern, fetch prüft über denselben Guard) und T-27-53 (ein Eintrag ohne Hit-Quelle) umgesetzt und getestet.

## Commits

- 0345a97 test(27-06): add failing tests for the bundle-owned guard flight
- 5b230e2 feat(27-06): hold the guard flight in prepare_context and fold the exclusion entry
- d24a372 test(27-06): prove the full bundle costs one REPORT and shows nothing tagged

## Self-Check: PASSED
