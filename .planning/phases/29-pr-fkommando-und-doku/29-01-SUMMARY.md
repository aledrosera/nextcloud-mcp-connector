---
phase: 29-pr-fkommando-und-doku
plan: 01
subsystem: testing
tags: [nc35, systemtags, appapi, webdav, ocs, evidence]

requires:
  - phase: 28-gates-und-beweise
    provides: nc35-Topologie und Env-Vorspann (28-LIVE-BEWEIS.md)
provides:
  - scripts/exclusion_evidence.py (Messwerkzeug M1 bis M9 ohne M5, Aufräumen mit Rückleseprobe)
  - raw/29-01-messungen.txt (Rohprotokoll zweier Läufe, BEFUND-, ENTSCHEID-, DOKU-Zeilen)
  - Entscheid Admin-Nachweis (Kandidat b) und Identität ohne --admin für 29-03
affects: [29-03, 29-04, 29-06, 29-07, 29-08]

tech-stack:
  added: []
  patterns:
    - "ExApp-Request als base64-JSON-Spec per stdin-Programm im ExApp-Container, nur Status und Körper gedruckt"
    - "record() maskiert U+2010 bis U+2015, damit Rohprotokolle strichfrei bleiben"

key-files:
  created:
    - scripts/exclusion_evidence.py
    - .planning/phases/29-pr-fkommando-und-doku/raw/29-01-messungen.txt
  modified: []

key-decisions:
  - "Admin-Nachweis = Kandidat b: GET /ocs/v2.php/cloud/groups/admin/users unter Impersonation, 200 Admin, 403 kein Admin"
  - "Kandidat a verworfen: oc:groups als Nicht-Admin kippt die ganze PROPFIND auf 403 (P2 tritt ein)"
  - "Ohne --admin: erstes Konto (sortiert) der AppAPI-Nutzerliste mit 207, nur user-visible=true, oc:groups nie anfordern"
  - "Zählung: innere nc:object-ids mit nc:type=files zählen; nc:id ist ein Index, keine fileid"

patterns-established:
  - "Messskript-Lauf hängt an das Rohprotokoll an, Fehlversuche bleiben stehen, Zusammenfassung von Hand"

requirements-completed: []

duration: 25min
completed: 2026-10-01
---

# Phase 29 Plan 01: Live-Messungen gegen nc35 Summary

**A1 bis A8 auf nc35 bestätigt; Admin-Nachweis über cloud/groups/admin/users (200/403), weil oc:groups beim Nicht-Admin die ganze PROPFIND auf 403 kippt; Zählung über innere nc:object-ids**

## Performance

- **Duration:** ca. 25 min
- **Completed:** 2026-10-01T05:15Z
- **Tasks:** 2/2
- **Files:** 2 erstellt

## Accomplishments

- Messwerkzeug `scripts/exclusion_evidence.py measure` (ruff, format, pyright latest, vulture grün), Preflight bricht bei vorbestehenden Namen ab, finally-Aufräumen mit CLEANUP-Zeile je Objekt
- Zwei Läufe gegen nc35 (35.0.0), Lauf 2 maßgeblich; Instanz danach leer (`tag:list` = `[]`, bob enabled)
- Messwerte: M1 401; M1b Nutzerliste 200/3 Konten, alice sieht public und restricted, nicht invisible; M1c deaktiviertes Konto 207; M2 admin sieht unsichtbares Tag und gids, alice mit oc:groups ganze Antwort 403; M2b admin 200, alice 403; M3 2 Zuordnungen, Pfadform `alice/files/<pfad>`; M3b alice zählt ebenfalls 2; M4 2/2/2 (bleibt auch nach trashbin:cleanup); M6 Varianten anlegbar, Groß/Klein abgelehnt; M7 "public tag named kein-ki added.", am Ordner sichtbar; M8 PROPPATCH 207, POST 201, alice 201, bob 403, Schalter wirkt (201 zu 403); M9 Menüpfad EN/DE/FR

## Task Commits

1. **Task 1: Messwerkzeug** - `cf7a581` (test)
2. **Task 2: Messung** - Korrektur `c14ee6a` (fix), Rohprotokoll `f6a29f1` (test)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Zählung las das falsche Element**
- **Found during:** Task 2, Lauf 1
- **Issue:** Nextcloud serialisiert jede Zuordnung als inneres `nc:object-ids` (nicht `nc:object-id`, wie 29-RESEARCH annahm); Lauf 1 meldete M3/M3b/M4 mit 0
- **Fix:** count_files zählt innere Elemente mit `nc:type`; Lauf 2 ergibt 2
- **Commit:** c14ee6a

**2. [Rule 1 - Bug] M1b lief vor der Tag-Anlage**
- **Fix:** Block M1b nach M2/M3 verschoben, damit public, restricted und invisible existieren
- **Commit:** c14ee6a

**3. [Rule 3] M9 las "Basic settings" aus der falschen l10n-Datei** (liegt in apps/settings/l10n), php-Helfer entfernt (unbenutzt, vulture)
- **Commit:** c14ee6a

**4. Orchestrator-Vorgabe statt Plantext:** nc35 nach dem Lauf gestoppt (`docker compose stop`, Volumes bleiben) und Docker Desktop beendet, statt weiterlaufen zu lassen; 29-06 muss nc35 neu starten.

**5. requirements mark-complete ausgelassen:** OPS-01 und DOC-03 werden erst von späteren Plänen erfüllt; dieser Plan liefert nur Messgrundlagen.

## Hinweise für 29-03

- Ohne Admin-Nachweis nie oc:groups anfordern (ganze Antwort 403)
- Deaktivierte Konten antworten unter Impersonation mit 207 (M1c); eine Regel "401 überspringen" greift für sie nicht
- "Wer public-Tags entfernen darf" ist nur aus dem Quelltext belegt, nicht gemessen

## Self-Check: PASSED

- scripts/exclusion_evidence.py vorhanden, raw/29-01-messungen.txt vorhanden
- Commits cf7a581, c14ee6a, f6a29f1 vorhanden
- Plan-Verifikation Task 2 (BEFUND, ENTSCHEID, CLEANUP, strichfrei) VERIFY_OK
