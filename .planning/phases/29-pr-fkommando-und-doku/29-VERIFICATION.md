---
phase: 29-pr-fkommando-und-doku
verified: 2026-10-01T12:05:00Z
status: passed
score: 4/4 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Nach dem nächsten Owner-Push den CI-Schritt 'exclusion:check live (OPS-01)' im Job canary-nc35 (.github/workflows/ci.yml:215) grün sehen"
    expected: "tests/integration/test_exclusion_check_live.py läuft mit NC_MCP_REQUIRE_LIVE=1 gegen nc35 grün, kein Skip"
    why_human: "Der Schritt läuft erst nach dem Push (55 Commits nur lokal); lokal gibt es dafür keinen gleichwertigen Lauf ohne Docker-Topologie"
---

# Phase 29: Prüfkommando und Doku, Verifikationsbericht

**Phase Goal:** Eine Administration erkennt ohne Live-Sitzung, ob ihr `kein-ki`-Tag wirkt, und die Doku in drei Sprachen beschreibt Einrichtung, Betriebsarten und ehrliche Grenzen ausschließlich aus den gemessenen Befunden
**Verified:** 2026-10-01 (HEAD 4d228b9)
**Status:** human_needed (einziger offener Punkt: CI-Schritt nach Owner-Push)
**Re-verification:** Nein, Erstverifikation

## Goal Achievement

### Observable Truths (Roadmap-Erfolgskriterien)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `occ mcp_connector:exclusion:check` benennt je Prüfschritt das Ergebnis gegen eine echte Instanz, auch für unsichtbares Tag und Tippfehler | VERIFIED | Handler `src/mcp_connector/exapp/exclusion_check.py` (699 Z.) + reine Urteilslogik `nextcloud/exclusion_audit.py` (7 Schritte, immer alle benannt). Registriert in `exapp/occ.py:433-457`, Route gemountet in `entry_exapp.py:383`. Live nc35: `raw/29-REVIEW-FIX-live-beweis.txt` (13:28:45, head=5da76f3 = letzter src-Commit) Fälle A bis H, darunter D (unsichtbar: `tag_visible failed`, passed=false) und E (`Kein KI` nur Variante: `tag_exists failed`, `no_variants failed`), F (Variante neben exakt: note + Warnung) |
| 2 | Läuft ohne Sitzung, ändert nichts: Vorher-nachher-Vergleich der Tag- und Zuordnungstabellen leer | VERIFIED | Gleicher Rohbeleg: 20 Aufrufe, je 8 Tabellen (systemtag, systemtag_object_mapping, systemtag_group, appconfig, preferences, storages, mounts, filecache) `gleich=ja`; `raw/29-REVIEW-FIX-live.txt` WR-04: frisches, nie angemeldetes Konto als erster Leser, auch oc_authtoken gleich. Code: nur PROPFIND/GET (`tests/contract/test_no_destructive_calls.py` grün) |
| 3 | Doku unter docs/ und README in drei Sprachen mit Freigabe-Grenze, unsichtbarem Tag, App-aus, Selbstbedienung und Organisationsmodus; Grenzaussagen mit Befund-Verweis | VERIFIED | `docs/exclusion.md`, `.de.md`, `.fr.md` (359/370/377 Z.) mit identischen Ankern (operating-modes, setup-*, check-command, 9 limit-*, 8 tech-*); README.md:93, README.de.md:102, README.fr.md:106 je 4-Zeilen-Abschnitt mit Link auf die Sprachseite. Die drei DOC-03-Grenzen verweisen auf 25-MESSBERICHT.md (K5, K1); die weiteren (D-29-05/D-29-11) auf ihre tatsächliche Quelle (28-CONTEXT/28-SECURITY/28-REVIEW/27-*), da es dafür keinen Phase-25-Befund gibt. Keine Gedankenstriche (0 Treffer U+2013/U+2014), echte Umlaute. Wortlaut Owner-abgenommen (01.10.) |
| 4 | Store-Beschreibungen unverändert, leerer Diff der drei Store-Texte | VERIFIED | Eigene Gegenprobe (awk-Extraktion, nicht das Muster des Pins): SHA-256 aller summary/description-Blöcke ca157b4 = HEAD = 2fa82aa8...; `git diff ca157b4 HEAD -- appinfo/info.xml` nur 11 Einfügungen im XML-Kommentar (29-05, IN-03). Pin `tests/unit/test_store_texts_frozen.py` grün |

**Score:** 4/4

### Required Artifacts

| Artifact | Status | Details |
|----------|--------|---------|
| `src/mcp_connector/exapp/exclusion_check.py` | VERIFIED | Text und `--json` mit `passed`, `error`-Schlüssel auf allen Pfaden, `--admin`, immer 200, Steuerzeichen escaped (WR-03) |
| `src/mcp_connector/nextcloud/exclusion_audit.py` | VERIFIED | exakt/Variante/ähnlich, Betriebsart, Urteil nach D-29-03/D-29-10 |
| `src/mcp_connector/nextcloud/clients/systemtags.py` | VERIFIED | `confirm_admin` True nur bei uid in Mitgliederliste (WR-02, Owner: delegierte Admins/Subadmins sind keine Admins) |
| `exapp/occ.py`, `entry_exapp.py` | VERIFIED | Fünftes occ-Kommando registriert, Route gemountet, nicht im Manifest deklariert |
| `docs/exclusion{,.de,.fr}.md`, 3 READMEs | VERIFIED | siehe Truth 3 |
| `.github/workflows/ci.yml:215` | VERIFIED (Lauf offen) | Schritt existiert, läuft erst nach Push |

### Key Link Verification

| From | To | Status |
|------|----|--------|
| occ-Registrierung `execute_handler` | `EXCLUSION_CHECK_PATH` | WIRED (abgeleitet, nicht kopiert) |
| `entry_exapp` | `exclusion_check_routes(env)` | WIRED |
| Handler | `systemtags.list_tag_details` / `count_tag_objects` / `confirm_admin` -> `audit()` | WIRED, Live-Ausgabe zeigt echte Zählungen (1, 0) |
| Doku-Zitate | Code (Schritt-Ids, Namen, Grenzsatz, TAG_BUDGET) | WIRED über `tests/unit/test_docs_exclusion_truth.py` (IN-05) |

### Behavioral Spot-Checks / Gates (selbst gefahren, PYTHONUTF8=1)

| Gate | Ergebnis | Status |
|------|----------|--------|
| `pytest tests/unit tests/contract -q` | 5312 passed, 33 skipped, Exit 0 | PASS |
| Phasentests (store_texts_frozen, docs_exclusion_truth, exapp_exclusion_check, exclusion_audit, systemtags_details) | alle grün | PASS |
| `ruff check .` / `ruff format --check .` | All checks passed / 329 formatted | PASS |
| `PYRIGHT_PYTHON_FORCE_VERSION=latest pyright` | 0 errors, 0 warnings | PASS |
| Live nc35 | nicht erneut gefahren (Docker); Rohbeleg 13:28:45 nach letztem Handler-Commit 5da76f3 (13:26:51), deckt A bis H in Text und JSON | PASS (Beleg) |

### Probe Execution

Keine Probes deklariert (`scripts/*/tests/probe-*.sh` nicht vorhanden). SKIPPED.

### Requirements Coverage

| Requirement | Status | Evidence |
|-------------|--------|----------|
| OPS-01 | SATISFIED | Truths 1 und 2 |
| DOC-03 | SATISFIED | Truth 3 |

Keine verwaisten Requirements: REQUIREMENTS.md ordnet Phase 29 genau OPS-01 und DOC-03 zu.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `src/mcp_connector/exapp/exclusion_check.py` | 533 | `\uXXXX` | Info | Formatbeschreibung, kein Schuldmarker |
| `.github/workflows/ci.yml` | 216-219 | Kommentar nennt nur die 4 Tag-Tabellen | Info | Test vergleicht seit WR-04 auch die Kontotabellen; Kommentar veraltet, Verhalten korrekt |

Keine TBD/FIXME/TODO in den Phasendateien.

### Human Verification Required

#### 1. CI-Schritt exclusion:check live nach dem Owner-Push

**Test:** Nach dem nächsten Push den Job canary-nc35, Schritt "exclusion:check live (OPS-01)" ansehen.
**Expected:** Grün, ohne Skip (NC_MCP_REQUIRE_LIVE=1).
**Why human:** Läuft erst nach dem Push; 55 Commits liegen nur lokal.

### Gaps Summary

Keine Lücken. Alle vier Erfolgskriterien und OPS-01/DOC-03 sind im Code und in den Rohbelegen nachgewiesen; die 13 Review-Befunde sind umgesetzt und durch den Live-Wiederholungslauf auf 5da76f3 gedeckt. Offen ist nur der CI-Lauf nach dem Push.

---

_Verified: 2026-10-01_
_Verifier: Claude (gsd-verifier)_

## Nachtrag 2026-10-01

Offener Punkt erledigt: CI-Lauf 36861555478 auf 5a89219 (Push nach Owner-Freigabe), Schritt `exclusion:check live (OPS-01)` success, alle 5 Jobs gruen inkl. canary-nc35. Status human_needed -> passed.
