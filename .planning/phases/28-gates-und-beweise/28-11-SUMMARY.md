---
phase: 28-gates-und-beweise
plan: 11
subsystem: tests/integration (Live-Paare GATE-03) + CI (Job exapp)
tags: [gate-02, gate-03, live, nc35, pairs, ci]
status: complete
requires:
  - 28-02 (tool_classes, result_shapes)
  - 28-07 (canary_world)
  - 28-10 (test_canary.py)
provides:
  - tests/integration/test_pair_equality_live.py (alle 14 PAIR_CASES live, vier Modi, Ausnahme gepinnt)
  - CI-Schritt "Canary and pair proofs of the kein-ki exclusion (GATE-02, GATE-03)" im Job exapp
affects: [29]
tech-stack:
  added: []
  patterns: [Paar-Dataclass je Fall aus der Kanarien-Welt, Zellvergleich statt erfundener Id für fetch(table:), eigene Upload-Id für aufräumbare Staging-Ordner]
key-files:
  created:
    - tests/integration/test_pair_equality_live.py
    - .planning/phases/28-gates-und-beweise/raw/28-11-pairs-live.txt
  modified:
    - .github/workflows/ci.yml
decisions:
  - "ABWEISUNG (beide Seiten is_error) nur im Normalbetrieb geprüft; im Ausfall antwortet files_list mit Liste plus degraded statt Fehler, dort prüft AUSFALL-TEXT, dass die getaggte Seite EXCLUSION_UNAVAILABLE nennt"
  - "notes_create ist nur im Normalbetrieb benannte Ausnahme; in den drei Ausfällen wird es als gewöhnliches Paar verglichen (wie im Unit-Test 28-09)"
  - "Binär-Chunk mit fester upload_id <stamm>p auf beiden Seiten, damit der Staging-Ordner des erfundenen Ziels (D-28-20) gefunden, gelöscht und zurückgelesen wird"
metrics:
  duration: ca. 35 min
  completed: 2026-09-28
---

# Phase 28 Plan 11: Live-Paare GATE-03 und CI-Verdrahtung Summary

Alle 14 Paarfälle aus `PAIR_CASES` laufen über `Client(mcp)` gegen echte nc35-Antworten: getaggt und nicht existent sind nach `normalised` byte-gleich, im Normalbetrieb und in den Ausfällen 500, 412 und timeout. `fetch(table:)` zeigt die getaggte Link-Zelle als Leerwert. `notes_create` ist als AUSNAHME mit genau dem gepinnten Unterschied protokolliert. Kanarie und Live-Paare sind im CI-Job exapp verdrahtet.

## Tasks

| Task | Name | Commit | Status |
| ---- | ---- | ------ | ------ |
| 1 | Live-Paare über die Kanarien-Welt, Lauf gegen nc35 | c83d27d | erledigt |
| 2 | CI-Schritt im Job exapp für Kanarie und Live-Paare | d8abbe0 | erledigt |

## Beweislauf nc35 (raw/28-11-pairs-live.txt, nach einem Fehlversuch neu begonnen)

- Kommando: `PYTHONUTF8=1 .venv/Scripts/python.exe -m pytest tests/integration/test_pair_equality_live.py -m integration -s`. Die Env aus `.env.nc35` wurde in Python geladen, dazu die `NC_MCP_E2E_*`-Exporte, `PYTHONPATH=<worktree>/src` und Container nc35-nc
- Ergebnis: **6 passed in 79.30s** (1 Abdeckung, 4 Modi, 1 Ausnahmen)
- `PAARE normal verglichen 13 von 14 (ausnahmen 1)`, `PAARE 500|412|timeout verglichen 14 von 14 (ausnahmen 0)`
- 56 PAAR-Zeilen, 0 mal `ungleich`, 0 Zeilen `: nein`; `PAAR <mode> fetch table: Zelle leer ja` in allen vier Modi (im Ausfall mit `degraded` in fetch-metadata und tables_browse)
- AUSFALL call_count: 500 = 28, 412 = 56, timeout = 28; je 13 AUSFALL-TEXT-Zeilen `ja`
- `AUSNAHME notes_create category: getaggt=is_error ... The parent folder /Notes/<stamm>-kat of ... does not exist ... erfunden=erfolg id=note:22721`
- CLEANUP: alle Zeilen gelesen ok; Staging-Ordner des erfundenen Binär-Ziels `(vorher 207): 404`, Notiz `note:22721: 404`, angelegte Kategorie `(vorher 207): 404`, Papierkorb leer
- Ohne Env: `pytest tests/integration/test_canary.py tests/integration/test_pair_equality_live.py -m integration -q` endet mit 10 skipped, Exit 0

## CI-Schritt (Reihenfolge per grep -n)

```
121:      - name: Findling hits run through sandbox and exclusion (SBX-01)
129:      - name: Canary and pair proofs of the kein-ki exclusion (GATE-02, GATE-03)
140:      - name: The OAuth connection over the full chain (AUTH-02, AUTH-03, SC 4, SC 5)
```

YAML parst (`uv run --no-project --with pyyaml`), Job integration unverändert. CI-Nachweis erst nach Push (Owner).

## Gates vor jedem Commit

ruff check . und ruff format --check . (311 Dateien) grün, pyright ohne Fehler (latest), vulture Exit 0, check_tool_budget.py Exit 0, tests/unit + tests/contract Exit 0.

## Deviations from Plan

**1. [Rule 1 - Testfehler] ABWEISUNG im Ausfall zu streng**
- **Gefunden in:** Task 1, erster Lauf (Modus 500)
- **Problem:** Meine Zusatzprüfung verlangte `is_error` auf beiden Seiten auch im Ausfall. `files_list` antwortet dort aber auf beiden Seiten gleich mit einer Liste plus degraded-Eintrag, ohne Fehler. Das Paar selbst war `gleich`, es gab keinen Befund.
- **Fix:** ABWEISUNG gilt nur im Normalbetrieb. Im Ausfall prüft AUSFALL-TEXT, dass `EXCLUSION_UNAVAILABLE` genannt wird. Das Rohprotokoll des Fehlversuchs wurde gelöscht und der Lauf komplett neu gefahren.
- **Commit:** c83d27d

**2. [Ergänzung] notes_create im Ausfall als gewöhnliches Paar**
- Laut Plan fällt jeder NAMED_EXCEPTIONS-Fall aus dem Vergleich heraus. Die Ausnahme D-28-16 gilt aber nur bei beantworteter Prüfung, deshalb wird der Fall im Ausfall mitverglichen, wie im Unit-Test von 28-09. Ergebnis: gleich in allen drei Ausfällen.

**3. [Form] CASES liefert eine `Pair`-Dataclass statt eines Tupels**
- Sie trägt Tool, Argumente und Id-Formen je Seite, weil files_search den Scope in zwei Schreibweisen zurückgibt (D-28-19).

**4. [Rule 2] Aufräumen außerhalb der Welt**
- Den Staging-Ordner des Binär-Chunks und die angelegte Notizkategorie kennt die Welt nicht. Beide werden im Test gelöscht und mit eigener CLEANUP-Zeile zurückgelesen; `assert_cleanup` prüft sie mit.

Keine Ungleichheit gefunden, deshalb kein Checkpoint nötig.

## Known Stubs

Keine.

## Threat Flags

Keine. T-28-110, T-28-111, T-28-112 und T-28-114 sind wie geplant mitigiert. T-28-113 bleibt akzeptiert: CI-Nachweis erst nach Push (Owner).

## Self-Check: PASSED

- FOUND: tests/integration/test_pair_equality_live.py, .planning/phases/28-gates-und-beweise/raw/28-11-pairs-live.txt, .github/workflows/ci.yml (Schritt Z. 129)
- FOUND: c83d27d, d8abbe0
