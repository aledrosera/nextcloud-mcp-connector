---
phase: 29-pr-fkommando-und-doku
plan: 07
subsystem: docs
tags: [docs, exclusion, kein-ki, truth-test, doc-03]

requires:
  - phase: 29-pr-fkommando-und-doku
    provides: raw/29-01-messungen.txt (occ/curl lines, M1 to M9), raw/29-06-live-beweis.txt (exclusion:check outputs), exclusion:check handler incl. f016f8f
provides:
  - docs/exclusion.md (EN operator page, 21 anchors)
  - docs/exclusion.de.md (DE operator page, same anchors)
  - tests/unit/test_docs_exclusion_truth.py (truth test for three pages and three README sections)
affects: [29-08, 29-09]

tech-stack:
  added: []
  patterns:
    - "Doku-Wahrheitstest: Anker-Abschnitt vom <a id> bis zum nächsten <a id>, Befundlink je Grenze muss existieren"
    - "Sprachumschalter-Links aus der Link-Auflösung ausgenommen, eigener Test plus Existenztest der Schwesterseite"
    - "Strich-Konstanten im Test per chr(0x2013)/chr(0x2014), damit die Testdatei selbst strichfrei bleibt"

key-files:
  created:
    - tests/unit/test_docs_exclusion_truth.py
    - docs/exclusion.md
    - docs/exclusion.de.md
  modified: []

key-decisions:
  - "Hinweis ohne --admin aus der Handler-Konstante NO_VISIBLE_TAG_SENTENCE (Stand f016f8f) zitiert, nicht aus dem älteren Live-Text von 29-06"
  - "M4 als Zählgrenze im Abschnitt check-command: Zuordnungen instanzweit, inklusive Papierkorb, auf nc35 auch nach trashbin:cleanup"
  - "Beispielausgaben mit --admin=<uid> statt der uid des Wegwerf-Admins (T-29-25)"
  - "Link-Auflösung überspringt die Schwester-Sprachseiten, damit EN/DE vor der FR-Seite aus 29-08 grün sein können"

requirements-completed: []

duration: 25min
completed: 2026-10-01
---

# Phase 29 Plan 07: Betreiberseiten kein-ki (EN, DE) und Doku-Wahrheitstest Summary

**Englische und deutsche Betreiberseite zum kein-ki-Tag mit gemessenen occ/curl-Befehlen, Prüfkommando samt wörtlicher Live-Ausgaben und 17 Grenzen mit Befundlinks, gehalten von einem Wahrheitstest gegen Code-Konstanten und Rohbelege**

## Performance

- **Duration:** ca. 25 min (06:52Z bis 07:16Z)
- **Completed:** 2026-10-01
- **Tasks:** 3/3
- **Files:** 3 erstellt

## Accomplishments

- Wahrheitstest mit 21 Anker-Ids, Befundlink-Existenz je Grenze, 25-MESSBERICHT-Pflicht für drei Grenzen, Link-Auflösung, Konstanten (`OCC_EXCLUSION_CHECK_COMMAND_NAME`, `ADMIN_OPTION`, `JSON_OPTION`, `EXCLUDE_TAG`), Exit-Code 0 je Sprache, Sprachumschalter, Striche, ASCII-Umlaute (mit Gegenprobe), README-Abschnitte (3 bis 4 Zeilen, Tag, Freigabe-Grenze)
- docs/exclusion.md: Betriebsarten-Tabelle, Einrichtung Selbstbedienung und Organisationsmodus, UI-Menüpfad (M9) und zwei curl-Wege, `restrict_creation_to_admin`, Prüfkommando (sieben Schritte, Urteil, Exit-Code, ohne --admin, Zählung), zwei wörtliche Ausgaben (Fall B, Fall F), neun Grenzen, acht weitere technische Grenzen
- docs/exclusion.de.md: deckungsgleich, echte Umlaute, Menüpfad DE "Administrationseinstellungen > Grundeinstellungen > Kollaborative Schlagworte"

## Task Commits

1. **Task 1: Doku-Wahrheitstest (RED)** - `d9bf196` (test)
2. **Task 2: docs/exclusion.md** - `aaa2727` (docs)
3. **Task 3: docs/exclusion.de.md** - `f77b701` (docs)

## Abgleich occ-Zeilen gegen Rohbeleg

Jede `php occ`-Zeile der EN-Seite (DE identisch) per `grep -F` gegen raw/29-01-messungen.txt und raw/29-06-live-beweis.txt:

| Zeile | Rohbeleg |
|---|---|
| `php occ tag:add kein-ki public --output=json` | 29-01 M7 |
| `php occ tag:files:add alice/files/KI-frei kein-ki public` | 29-01 M7 |
| `php occ group:add ki-verantwortung` | 29-01 M8 |
| `php occ group:adduser ki-verantwortung alice` | 29-01 M8 |
| `php occ tag:add kein-ki restricted --output=json` | 29-01 M8 |
| `php occ config:app:set systemtags restrict_creation_to_admin --value=true --type=boolean` | 29-01 M8 |
| `php occ config:app:get systemtags restrict_creation_to_admin` | 29-01 M8 |
| `php occ mcp_connector:exclusion:check --admin=<uid>` (Platzhalter) | 29-06, mit echter Test-uid gelaufen; Form steht in der --help-Ausgabe |
| `php occ mcp_connector:exclusion:check --admin=<uid> --json` (Platzhalter) | 29-06, wie oben |

curl-Zeilen: aus 29-01 M8, nur Host, Passwort und Tag-Id durch `https://cloud.example.com`, `<app-password>`, `<tag-id>` ersetzt (POST-Beispiel mit Tag-Name `kein-ki` statt des Messnamens `kein-ki-m8b`).

## Gates

Vor Commit d9bf196: ruff check . grün, ruff format --check . grün (324 Dateien), pyright latest 0 Fehler, vulture (src scripts vulture_whitelist.py) grün, PYTHONUTF8=1 pytest tests/unit tests/contract: alle Fehlschläge ausschließlich im neuen, planmäßig roten Test (0 Fehlschläge außerhalb). Nach Task 3: `pytest tests/unit/test_docs_exclusion_truth.py -k "lang_en or lang_de"` 18 passed; Umlaut-Test der DE-Seite grün.

Planmäßig weiter rot bis 29-08 (16 Fälle): alle `lang_fr`-Fälle (Seite fehlt), alle `readme_*`-Fälle und der Umlaut-Test des README.de-Abschnitts (Abschnitte fehlen).

## Deviations from Plan

1. **[Rule 3 - Blocking] Link-Auflösung und Sprachumschalter:** Der Plan verlangt "alle relativen Links lösen auf" und zugleich den Link auf exclusion.fr.md, die erst 29-08 schreibt; lang_en wäre damit in 29-07 nie grün. Die Link-Auflösung überspringt die drei Sprachseiten; deren Existenz hält `test_the_page_exists`, die Verlinkung `test_the_page_links_both_other_languages`. Im Test-Docstring benannt.
2. **[Orchestrator-Vorgabe] Hinweis ohne --admin:** Text aus der Konstante `NO_VISIBLE_TAG_SENTENCE` (f016f8f) zitiert und auf exclusion_check.py verlinkt; der 29-06-Live-Text dieser Zeile ist veraltet und wird nicht als Ausgabe zitiert. Erledigt damit auch die Auffälligkeit aus 29-06 (Fall D ohne --admin).
3. **[Orchestrator-Vorgabe] Zählgrenze M4:** im Abschnitt check-command (instanzweit, Papierkorb, nach trashbin:cleanup gemessen 2/2/2).
4. **Gate-Lauf mit rotem Test:** TDD-RED und das Nutzer-Gate "unit+contract grün" widersprechen sich für Task 1; Gate lief mit dem Nachweis, dass nur der neue Test rot ist.
5. **Wortlaut tech-one-wording:** Plan nennt "exclusion check unavailable" (Arbeitsbegriff aus D-27-05); zitiert ist der tatsächliche Text von `withhold.EXCLUSION_UNAVAILABLE`.
6. **Nicht übernommen (P5):** Satz "Nutzer können bei App aus keine Tags mehr setzen" aus der Research-Tabelle; gemessen ist nur das Fehlen von `tag:files:*`, so steht es in der Seite. Admin-Sitzungs-Folgerung (Research-Zeile ohne Anker) steckt im Satz von limit-invisible-tag.

## Known Stubs

Keine. Der Sprachumschalter verlinkt exclusion.fr.md, die 29-08 anlegt (planmäßig).

## Self-Check: PASSED

- tests/unit/test_docs_exclusion_truth.py, docs/exclusion.md, docs/exclusion.de.md vorhanden
- Commits d9bf196, aaa2727, f77b701 vorhanden
