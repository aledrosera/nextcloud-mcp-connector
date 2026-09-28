---
phase: 28-gates-und-beweise
plan: 07
subsystem: tests/integration (Kanarien-Welt)
tags: [gate-02, live, nc35, canary, cleanup]
status: complete
requires:
  - 28-01 (canary_world.py Harness-Basis)
provides:
  - tests/integration/canary_world.py World und canary_world(env, raw) für 28-10 und 28-11
  - World.register_tool_write(kind, ident) als Aufräumbuch der Schreibwerkzeuge
affects: [28-10, 28-11]
tech-stack:
  added: []
  patterns: [Cleanup mit gelesenem Rohwert je Nebenwirkung, Papierkorb-Purge per Stamm, Deck-Anhang als Share Typ 12, Kalender-DELETE mit X-NC-CalDAV-No-Trashbin]
key-files:
  created:
    - tests/integration/test_canary_world.py
    - .planning/phases/28-gates-und-beweise/raw/28-07-world.txt
  modified:
    - tests/integration/canary_world.py
decisions:
  - "Deck-Dateianhang als Freigabe Typ 12 an die Karte (so hängt das Deck-Frontend eine vorhandene Datei an), nicht per v1.1-Upload, der eine ungetaggte Kopie mit Marker im Namen anlegen würde; gelingt auf nc35 (200)"
  - "Gelöschte Deck-Karte wird über die Stack-Liste direkt nach ihrem DELETE zurückgelesen, weil Deck GET auf eine gelöschte Karte und nach dem weichen Board-Löschen auch die Stack-Liste mit 403 beantwortet"
  - "Papierkorb wird per Stamm geleert (zuerst registriert, läuft zuletzt), damit keine Datei mit Marker im Namen auf der Instanz bleibt"
metrics:
  duration: ca. 30 min
  completed: 2026-09-28
---

# Phase 28 Plan 07: Kanarien-Welt mit Aufbau- und Aufräumbeweis Summary

`canary_world(env, raw)` baut je Lauf die vollständige Kanarien-Welt (Dateien, Notizen, Kategorie, Talk-Raum und Datei-Raum, Tables-Link, Kalender-ATTACH, Deck-Karte mit Anhang), taggt per occ in `topology.NC_CONTAINER`, belegt alles per Harness und räumt mit gelesenem Rohwert je Nebenwirkung auf. Gegen nc35 zweimal hintereinander 1 passed, je 18 von 18 CLEANUP-Zeilen gelesen ok.

## Tasks

| Task | Name | Commit | Status |
| ---- | ---- | ------ | ------ |
| 1 | World und canary_world() aufbauen | b25e9ff, Fix 0559123 | erledigt |
| 2 | Welt-Test gegen nc35 mit Aufbau- und Aufräumbeweis | c1ccc2b | erledigt |

## Welt (Pfade ohne Marker in Argumenten)

Die f-Strings aus `World` (canary_world.py):
- `locked_dir`: `f"/{self.stamm}/Gesperrt-{self.h}"`
- `locked_file`: `f"{self.locked_dir}/inhalt-{self.h}.txt"`
- `tagged_category`: `f"{self.stamm}-kat"`
- Marker nur in `tagged_file` (`f"/{self.stamm}/{self.stamm}-{self.marker}.txt"`), im Titel der getaggten Notiz und im Inhalt; Kontroll-Marker in `control_file` und Kontrollnotiz (ungetaggt).
- Getaggt: tagged_file, locked_dir, Notizdatei, Kategorie-Ordner `Notes/<stamm>-kat` (mit einer Notiz darin). REPORT bestätigt alle vier, Kontrolldatei und Kontrollnotiz ungetaggt.

## Messlauf

- Env aus `.env.nc35` (in Python geladen, nicht kopiert) plus die sechs `NC_MCP_E2E_*`-Exporte, `PYTHONUTF8=1`, `PYTHONPATH=<worktree>/src`
- Lauf 1: 1 passed in 11.27s; Lauf 2: 1 passed in 13.76s; NC 35.0.0, Container nc35-nc, HEAD 0559123
- Ohne Env: 1 skipped, Exit 0
- raw/28-07-world.txt: zwei Kopfzeilen, 36 CLEANUP-Zeilen, 0 Zeilen ": nein"; WELT-Zeilen für tables-link, kalender-attach, datei-raum und deck (Anhang "share typ 12 an karte ...: 200")
- CLEANUP je Lauf: Papierkorb leer, Baum 404, Kategorie 404, Notizen leer, Talk-Raum und Datei-Raum entfernt, drei Freigaben 404, Tabelle 404, Kalender 404, Board gelöscht (weich), Tag entfernt (selbst angelegt), fünf Werkzeug-Einträge (note, row, card, event, message) 404 bzw. gelöscht

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Gelöschte Deck-Karte las 403 statt eines Löschbelegs**
- **Found during:** Task 2, erste zwei Läufe (Rohdateien verworfen)
- **Issue:** Deck antwortet GET auf eine gelöschte Karte mit 403, nach dem weichen Board-Löschen auch die Stack-Liste; die Zeile endete auf ": 403".
- **Fix:** Direkt nach dem Karten-DELETE die Stack-Liste lesen ("entfernt"), beim Aufräumbeleg die Board-Liste (gelöscht) dazunehmen; Rest bleibt ein sichtbarer Rückstand.
- **Commit:** 0559123

**2. [Rule 2 - Kritisch] Papierkorb und Kalender-Papierkorb**
- **Issue:** DELETE per WebDAV und Notes-API verschiebt Dateien mit Marker im Namen in den Papierkorb; Kalender-DELETE landet im Kalender-Papierkorb. Ohne Purge wäre die Instanz nicht rückstandsfrei (T-28-70).
- **Fix:** Papierkorb-Purge per Stamm als erster Cleanup-Schritt (läuft zuletzt, gelesen "leer"); Kalender-DELETE mit `X-NC-CalDAV-No-Trashbin: 1`.
- **Commit:** b25e9ff

**3. [Ergänzung] Harness-Schreibzugriffe je Ledger-Art im Welt-Test**
- Der Test bucht je eine Notiz, Zeile, Karte, Termin und Talk-Nachricht per Harness über `register_tool_write`, damit der Aufräumweg, den 28-10 für Schreibwerkzeuge braucht, schon hier live belegt ist.

**4. [Auslegung] Deck-Anhang als Freigabe Typ 12**
- Plan: "Versuch eines Datei-Anhangs über die Deck-API". Der v1.1-Upload legt eine neue Datei (Kopie mit Marker im Namen, ungetaggt) an; der Verweis auf die vorhandene getaggte Datei ist die Freigabe Typ 12 an die Karte. Rohstatus in `World.deck_attachment` und WELT-Zeile.

**5. [Kleinigkeit] Zusätzliche World-Felder**
- `harness`, `notes_root`, `category_note_id`, `column_id`, `row_ids`, `tag_id`, `proof`, `cleanup_lines`: nötig für Test und Folgepläne. ATTACH trägt zusätzlich `FMTTYPE` und `X-NC-FILE-ID` wie beim Kalender-App-Anhang.

## Known Stubs

Keine.

## Threat Flags

Keine neue Angriffsfläche; nur Test-Harness gegen die Wegwerfinstanz.

## Self-Check: PASSED

- FOUND: tests/integration/canary_world.py, tests/integration/test_canary_world.py, raw/28-07-world.txt
- FOUND: b25e9ff, 0559123, c1ccc2b
