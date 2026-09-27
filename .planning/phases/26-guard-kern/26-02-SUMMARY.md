---
phase: 26-guard-kern
plan: 02
subsystem: nextcloud-exclusion
tags: [systemtags, exclusion, single-flight, fail-closed, cache]
requires:
  - "26-01: systemtags.list_tags / systemtags.tagged_nodes, dav.within"
provides:
  - "exclusion.TagScope (untagged / active / unverifiable mit Grundcode), excludes wirft bei unverifiable"
  - "exclusion.load_scope(clients): D-25-05-Automat unter TAG_BUDGET, wirft nie für Nextcloud-Ausgänge"
  - "exclusion.ExclusionGuard: eine Flight je Tool-Aufruf (Single-Flight), parameterloser Konstruktor für Phase 27"
  - "exclusion._tag_ids: prozessweiter Name-zu-Id-Cache je (base_url, user), 60 s, nur positiv"
affects: [27]
tech-stack:
  added: []
  patterns: ["Zustände als Werte (frozen Dataclass)", "Single-Flight mit Lock im Konstruktor und Re-Check (jwks.py)", "ein REPORT je Schreibweise per asyncio.gather"]
key-files:
  created:
    - src/mcp_connector/nextcloud/exclusion.py
    - tests/unit/test_exclusion.py
    - .planning/phases/26-guard-kern/deferred-items.md
  modified:
    - tests/contract/test_no_destructive_calls.py
    - vulture_whitelist.py
decisions:
  - "Zweiter 412 löscht den Cache-Eintrag ebenfalls (nichts als veraltet Erkanntes bleibt liegen)"
  - "Gemischte Status (412 plus 500) werten als 'status', nicht als 'stale_twice'"
  - "TaggedNode.is_collection bleibt in der Vulture-Liste: ancestors deckt Dateien und Ordner gleich, der Guard braucht das Flag nicht; Phase 27 liest es oder entfernt es"
metrics:
  duration: "ca. 35 min"
  completed: 2026-09-27
  tasks: 3
  files: 5
---

# Phase 26 Plan 02: Guard-Kern (TagScope, load_scope, ExclusionGuard) Summary

Policy-Schicht `nextcloud/exclusion.py`: Drei-Zustands-Wert `TagScope`, positiver Name-zu-Id-Cache je (base_url, user), D-25-05-Automat mit genau einer Neuauflösung nach 412 unter `asyncio.timeout(TAG_BUDGET)` und ein request-gebundener `ExclusionGuard` mit Single-Flight; nichts ist an Werkzeuge oder `NcClients` gehängt.

## Tasks

| Task | Name | Commits | Dateien |
|------|------|---------|---------|
| 1 | TagScope, ancestors, Name-zu-Id-Cache, Gate-Eintrag | 3416e5b (RED), 4700286 (GREEN) | exclusion.py, test_exclusion.py, test_no_destructive_calls.py |
| 2 | load_scope und ExclusionGuard mit respx-Matrix | d8ace24 (RED), 6e5493a (GREEN) | exclusion.py, test_exclusion.py |
| 3 | Vulture-Abschnitt, Merker-Datei, Gates | bfc30c9 | vulture_whitelist.py, deferred-items.md |

## Nachweis je Szenario (tests/unit/test_exclusion.py, 71 Tests)

- **untagged:** Liste ohne kein-ki: REPORT call_count 0, `_tag_ids` leer, zweiter Guard listet neu (PROPFIND 2); Beispielliste `==` und `json.dumps`-gleich.
- **active:** 64 mit /A/kein (955, Ordner) und /A/doc.md (957): paths und fileids exakt.
- **Capability:** Route mit leerem capabilities-Abschnitt gemockt, call_count 0, Zustand active.
- **unverifiable je Grund:** REPORT 500/401/403/301 -> status (call_count 1); ConnectError, RemoteProtocolError -> unreachable; ReadTimeout, ConnectTimeout -> timeout; Budget 0,01 s bei 1 s Handler -> timeout, Test < 0,5 s; unparsebarer 207 -> unparsable; Knoten ohne fileid -> unparsable; fremder href -> foreign_href; Liste 500/401/404 -> status; Liste unparsebar -> unparsable; Liste mit Id "6a" -> unparsable; Listen-ConnectError -> unreachable. `excludes` wirft ValueError.
- **412-Folgen:** warm + Tag weg -> untagged (REPORT 1, PROPFIND 1, Cache leer); warm + neue Id 70 -> active (REPORT 2 mit 64 dann 70, PROPFIND 1, Cache ("70",)); warm + 412 zweimal -> stale_twice (REPORT 2, PROPFIND 1); kalt + 412 zweimal -> stale_twice (PROPFIND 2, REPORT 2); 412 dann 500 -> status; 412 dann Liste 503 -> status.
- **Single-Flight:** 20 parallele `scope()` -> REPORT 1, PROPFIND 1, alle `is` dasselbe Objekt; bei REPORT 500 ebenso ein Aufruf und ein geteiltes unverifiable-Objekt.
- **Zweiter Tool-Aufruf:** zwei Guards nacheinander -> REPORT 2, PROPFIND 1, neuer Knoten erscheint im zweiten Aufruf.
- **Per-User-Key:** admin zuerst, dann alice -> PROPFIND 2 (Auth-Header geprüft), jeder REPORT mit der eigenen Id.
- **Varianten:** alice 64/65 "kein-ki", 67 "Kein-KI" -> genau 2 REPORTs (64, 67, kein 65), Vereinigung; admin zusätzlich 63 "KEIN-KI" -> 3 REPORTs. Der Handler prüft je Body genau eine Id.
- **Sandbox-Vorfahr:** NC_MCP_FILES_ROOT=/Shared/KI, href .../alice/Shared/ -> paths {"/Shared"}, `/Shared/KI/doc.md` ausgeschlossen, `/Sharedx/doc.md` nicht.
- **Abbruch:** Flight-Halter abgebrochen -> `guard._scope is None`, nächster Aufruf startet neue Flight (Handler zählt 2 REPORTs).
- **Segmentregel:** parametrisierter Äquivalenztest ancestors gegen dav.within (18 Fälle, inkl. /A/kein gegen /A/keine).

## Gates

- ruff check, ruff format --check: grün
- pyright (PYRIGHT_PYTHON_FORCE_VERSION=latest): 0 Fehler
- vulture src scripts vulture_whitelist.py: grün
- pytest tests/unit tests/contract: Exit 0 (4637 Tests gesammelt)
- Greps: kein `except Exception/BaseException/CancelledError`, kein capabilities-Bezug, kein "Resolve", kein environ/getenv/config in exclusion.py; nichts in tools/, deps.py, nextcloud/__init__.py

## Deviations from Plan

1. **[Rule 1 - Test] respx zählt abgebrochene Anfragen nicht.** respx trägt einen Aufruf erst ein, wenn der Handler zurückkehrt. Im Timeout- und im Abbruch-Test zählt deshalb der Handler selbst (`entered`); respx-`call_count` wird zusätzlich mit dem erwarteten Wert (0 bzw. 1 abgeschlossene Anfrage) geprüft. Aussage des Plans (ein REPORT ohne Retry; zweite Flight nach Abbruch) bleibt vollständig belegt.
2. **[Ergänzung] Zweiter 412 löscht den Cache-Eintrag** (`_drop_ids` auch bei stale_twice), damit keine als veraltet erkannte Id liegen bleibt. Der Plan schrieb das nur für den ersten 412 vor.
3. **[Vulture] `_.is_collection` bleibt** mit angepasster Begründung: exclusion.py braucht das Flag nicht, weil `ancestors` Dateien und Ordner gleich behandelt. Plan erlaubt das ausdrücklich ("Namen, die weiterhin gemeldet werden, bleiben"). Neu geparkt nur `_.excludes`; `ExclusionGuard`, `scope`, `is_exclude_name` meldet vulture nicht.
4. **[Konvention] Gate-Kommentar über der Zeile** statt Zeilenkommentar für `("nextcloud/exclusion.py", "_tag_ids")`, weil der Zeilenkommentar die Zeilenlänge 100 gesprengt hätte.
5. **Umgebung:** Worktree ohne eigene `.venv`, `uv sync` gesperrt. Gates liefen mit der venv des Hauptrepos, `PYTHONPATH=src` und `pyright --pythonpath`; Import aus dem Worktree geprüft (`mcp_connector.__file__` zeigt in den Worktree).

## TDD Gate Compliance

Task 1 und 2: je `test(26-02)`-Commit (RED: Collection-Error bzw. AttributeError wegen fehlender Namen) vor `feat(26-02)`-Commit (GREEN). Kein Refactor-Commit nötig.

## Known Stubs

Keine. `TagScope.excludes` hat bis Phase 27 keinen Aufrufer im Code und ist in `vulture_whitelist.py` geparkt (Abschnitt "The guard core of phase 26, wired in by phase 27").

## Threat Flags

Keine neue Angriffsfläche über das Threat-Register hinaus (T-26-08 bis T-26-17 umgesetzt bzw. wie geplant akzeptiert/übertragen).

## Self-Check: PASSED

- FOUND: src/mcp_connector/nextcloud/exclusion.py, tests/unit/test_exclusion.py, .planning/phases/26-guard-kern/deferred-items.md
- FOUND: 3416e5b, 4700286, d8ace24, 6e5493a, bfc30c9
