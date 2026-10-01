---
phase: 28-gates-und-beweise
plan: 01
subsystem: tests/integration (Live-Harness, Messung)
tags: [gate-02, gate-03, live, nc35, tables, files_search, files_upload]
status: complete
requires: []
provides:
  - tests/integration/canary_world.py (Harness-Basis für 28-07, 28-10, 28-11)
  - Live-Befunde A1, B5, B6, B6-text als Grundlage für D-28-18..20
affects: [28-05, 28-06, 28-10, 28-11]
tech-stack:
  added: []
  patterns: [Client(mcp) ohne Exception-Durchreichung, occ über topology.NC_CONTAINER, Cleanup mit gelesenem Rohwert]
key-files:
  created:
    - tests/integration/canary_world.py
    - tests/integration/test_live_questions_28.py
    - .planning/phases/28-gates-und-beweise/raw/28-01-live-questions.txt
  modified:
    - .planning/phases/28-gates-und-beweise/28-CONTEXT.md
decisions:
  - "D-28-18 (A1): wie gemessen, 28-05 filtert den JSON-String mit providerId files, fileid aus /f/<id>, getaggt wie null, Ausfall fail-closed"
  - "D-28-19 (B5): Fix in 28-06, getaggter Ordner antwortet vorab mit dav.not_found(search_scope)"
  - "D-28-20 (B6): kein Befund, nur Paartest; Staging-Rest uploads/<user>/nc-mcp-<sha256> als Aufräum-Merker für Backlog/Phase 29"
  - "B6-Messung mit 5 MiB statt 16 Bytes: die 16-Byte-Probe des Plans endet in der Größenprüfung vor dem Guard (B6-klein protokolliert)"
  - "Upload-Ordner über dav.uploads_url (nc-mcp-<sha256>) gelesen, nicht über den wörtlichen Pfad uploads/<user>/<upload_id> des Plans (beide protokolliert)"
metrics:
  duration: ca. 25 min
  completed: 2026-09-28
---

# Phase 28 Plan 01: Live-Fragen A1, B5, B6 gemessen Summary

Harness-Basis `canary_world.py` plus drei Messtests gegen nc35 (3 passed, Aufräumen gelesen): A1 Link-Zelle ist ein JSON-String mit Dateiname und `/f/<fileid>`, B5 ungleich (Existenz-Orakel für getaggte Ordner), B6 und B6-text gleich. Owner-Entscheide D-28-18..20 stehen in 28-CONTEXT.md.

## Tasks

| Task | Name | Commit | Status |
| ---- | ---- | ------ | ------ |
| 1 | Harness-Basis canary_world.py und drei Messtests | c2df823, Fix 8e64c7a | erledigt |
| 2 | Messung gegen nc35, Rohprotokoll + ZUSAMMENFASSUNG | 84f5d2d | erledigt |
| 3 | Owner-Entscheid A1-Form, B5, B6 (checkpoint:decision) | siehe docs(28-01) | erledigt, D-28-18..20 eingetragen |

## Messlauf

- Kommando: Env aus `.env.nc35` plus die sechs `NC_MCP_E2E_*`-Exporte, `PYTHONUTF8=1`, `PYTHONPATH=<worktree>/src`, `python -m pytest tests/integration/test_live_questions_28.py -m integration -s`
- Ergebnis: **3 passed in 14.25s**, NC 35.0.0, Container nc35-nc (über topology.NC_CONTAINER), HEAD 8e64c7a
- Ohne Env: 3 skipped, Exit 0
- CLEANUP: Baum 404, Tag kein-ki entfernt (selbst angelegt), Tabelle 404, beide Upload-Ordner 404

## Befunde (Details: raw/28-01-live-questions.txt, Block ZUSAMMENFASSUNG 28-01)

- **A1:** `rows/simple` liefert die Link-Zelle als JSON-String `{"title": "<Dateiname>", "value": "<url>/f/<fileid>", "providerId": "files"}` (Schrägstriche als `\/` escapt), leere Zelle als `null`. `tables_browse` zeigt heute den Namen der getaggten Datei samt Marker: B1 live bestätigt.
- **B5 ungleich:** getaggter Ordner antwortet `count 0, items []` ohne Fehler; erfundener Ordner `isError`, "File not found: /files/alice/<Ordner>. Hint: List the parent folder first ...". Der Fehlertext nennt den internen Scope, nicht den übergebenen Ordner.
- **B6 gleich:** Chunk 1 (5 MiB) in getaggten und erfundenen Ordner: wortgleich "The parent folder <Ordner> of <Ordner>/neu.bin does not exist." Nebenbefund: beim erfundenen Ordner bleibt ein Staging-Ordner `uploads/<user>/nc-mcp-<sha256>` liegen (für das Modell unsichtbar).
- **B6-text gleich:** derselbe Satz für `content="x"`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] B6-Probe erreichte den Guard nicht**
- **Found during:** Task 1 (Lesen von upload_binary)
- **Issue:** 16 Bytes, total 32, final=false scheitert an "A non-final chunk must contain at least 5 MiB" vor `_writable`; das Paar wäre trivial gleich.
- **Fix:** Plan-Probe als "B6-klein" behalten und protokolliert, die eigentliche B6-Messung mit `MIN_UPLOAD_CHUNK_BYTES` (5 MiB), total = 5 MiB + 16.
- **Commit:** c2df823

**2. [Rule 1 - Bug] Upload-Ordnerpfad des Plans existiert so nicht**
- **Issue:** Der Connector legt Staging-Ordner als `nc-mcp-<sha256(files_root, path, upload_id)>` an, nicht als `uploads/<user>/<upload_id>`.
- **Fix:** Lesen und Löschen über `dav.uploads_url`, der wörtliche Pfad wird zusätzlich protokolliert (404).
- **Commit:** c2df823

**3. [Rule 1 - Bug] fileid_im_draht falsch "nein"**
- **Found during:** Task 2, erster Lauf
- **Issue:** PHP escapt `/` als `\/`, der Substring `/f/<fileid>` fand sich im Rohtext nicht.
- **Fix:** Vergleich mit aufgehobenem Escape; Rohdatei des Vorlaufs verworfen, sauberer Neulauf.
- **Commit:** 8e64c7a

**4. [Kleinigkeit] Tagging über fileid statt `<user>/files<pfad>`**
- `occ tag:files:add` mit fileid ist die in 27-07 gemessene Form; `tag(fileid)` in canary_world.

## Checkpoint (Task 3): geschlossen

Owner-Entscheid vom 28.09.2026, wörtlich in 28-CONTEXT.md unter "Nachentscheide nach der Messung 28-01":
- **D-28-18 (A1):** "Wie gemessen (Empfohlen)": 28-05 filtert genau die gemessene Form; getaggt wie null, Ausfall fail-closed, andere providerIds unberührt.
- **D-28-19 (B5):** "Fixen (Empfohlen)": getaggter Ordner antwortet vorab mit dav.not_found(search_scope); Umsetzung in 28-06.
- **D-28-20 (B6):** "Kein Befund, Staging als Merker (Empfohlen)": nur Paartest; Staging-Rest als Aufräum-Merker für Backlog/Phase 29.

## Known Stubs

Keine.

## Self-Check: PASSED

- FOUND: tests/integration/canary_world.py, tests/integration/test_live_questions_28.py, raw/28-01-live-questions.txt
- FOUND: c2df823, 8e64c7a, 84f5d2d
