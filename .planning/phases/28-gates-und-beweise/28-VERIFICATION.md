---
phase: 28-gates-und-beweise
verified: 2026-09-30T19:24:37Z
status: human_needed
score: 3/4 must-haves verified (SC2 uncertain, live only)
head: ad752c5
overrides_applied: 1
overrides:
  - must_have: "Für jeden Einzelzugriff ist die Antwort auf eine getaggte Id byte-gleich zur Antwort auf eine nicht existente Id, im Normalbetrieb und im Ausfallfall der Prüfung"
    reason: "notes_create in eine Kategorie ist im Normalbetrieb die benannte Ausnahme D-28-16 (nicht existente Kategorie wird angelegt, getaggte abgewiesen); gepinnt durch test_notes_create_is_a_named_residual_oracle, im Ausfall byte-gleich (14/14 live), Doku als Restorakel in Phase 29"
    accepted_by: "Owner (D-28-16, 28-CONTEXT.md)"
    accepted_at: "2026-09-28T00:00:00+02:00"
human_verification:
  - test: "Kanarie, Live-Paare und Provider-Live-Gate nach den Review-Fixes (1f9da6b..36c08cf) erneut gegen eine echte Instanz fahren: pytest tests/integration/test_canary.py tests/integration/test_pair_equality_live.py tests/integration/test_provider_classes_live.py -m integration -s mit NC_MCP_REQUIRE_LIVE=1"
    expected: "KANARIE <modus> geprüft 22 von 22 in allen vier Modi, 0 Befundzeilen mit Urteil nein, Kanarien-Welt enthält die Nachricht 'datei-raum-nachricht' im Datei-Raum und kein talk-message-Treffer nennt den Dateinamen; PAARE 13/14 normal (1 Ausnahme) und 14/14 in 500/412/timeout; Provider-Gate grün ohne unklassifizierten Provider"
    why_human: "Braucht Docker und Nextcloud. Alle Live-Belege in 28-LIVE-BEWEIS.md (raw/28-10, raw/28-11, raw/28-12) stammen von HEAD f9f8773/2a92052/6fd4526, also VOR dem Review-Fix CR-01. Der Review zeigte, dass die damalige Kanarien-Welt den Fall 'Nachricht im Datei-Raum' nicht baute; die grüne Kanarie belegte diesen Fall also nicht. Das Provider-Live-Gate (WR-02) ist nie live gelaufen (keine Rohdatei)."
  - test: "Erster CI-Lauf des Schritts 'Canary and pair proofs of the kein-ki exclusion (GATE-02, GATE-03)' im Job exapp nach dem Owner-Push"
    expected: "Schritt grün mit NC_MCP_REQUIRE_LIVE=1 (kein Skip), Ausgabe enthält KANARIE ... geprüft 22 von 22 je Modus und PAARE-Zeilen, providers=[...] ohne Befund"
    why_human: "Läuft erst nach Push (Owner-Entscheid). CI-Topologie ist NC 34.0.3 (compose.exapp.yml) mit Findling, alle Live-Messungen waren nc35 ohne Findling; offene Owner-Frage WR-04 (nc35 oder beide)."
  - test: "Owner-Entscheid WR-02: Laufzeit-Default der Suchprovider-Klassifikation bleibt fail-open (unbekannter Provider ohne lesbare Dateireferenz wird behalten)"
    expected: "Owner bestätigt fail-open plus Provider-Freeze als Gate oder beauftragt Umkehr auf fail-closed"
    why_human: "Produktentscheid mit sichtbarem Verhalten; Restrisiko Drittanbieter-Provider auf Nutzerinstanzen, die das CI-Gate nicht sieht"
---

# Phase 28: Gates und Beweise Verification Report

**Phase Goal:** Die Aussage "keine Tool-Antwort zeigt Getaggtes" ist ein roter oder grüner Test statt eines Versprechens: jedes Werkzeug der aktiven Registry ist klassifiziert, ein Kanarienwort taucht nirgends auf, getaggt und nicht existent sind byte-gleich, und der Connector kann den Tag konstruktionsbedingt nie setzen oder entfernen
**Verified:** 2026-09-30T19:24:37Z (HEAD ad752c5)
**Status:** human_needed
**Re-verification:** Nein, erste Verifikation

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Klassifikations-Freeze über die aktive Registry, Probe-Werkzeug ohne Eintrag macht rot (deckt files_update) | VERIFIED | `tests/contract/test_tool_classes.py` vergleicht `tool_classes.freeze_findings` mit `Client(mcp).list_tools()` (22 Werkzeuge, 12/3/7), nicht mit einem Literal; `probe_tool("files_update")` registriert wirklich zur Laufzeit, Test verlangt `unclassified: files_update` und prüft, dass die Probe danach verschwindet. Keine bedingte Registrierung in `src/` (kein remove_tool/Tags-Filter), die Registry ist also die aktive. Lokal grün. |
| 2 | Kanarie: getaggte Datei mit Marker in Name und Inhalt, jedes Werkzeug aufgerufen, Marker in null Antworten und Fehlertexten, Zahl in der Ausgabe | UNCERTAIN (human) | Code substanziell: `tests/integration/test_canary.py` prüft `set(PLAN) == registry` aus `list_tools()`, gibt `KANARIE <mode> geprüft <n> von <registry>` aus, assert `== 22`, vier Modi, Kontroll-Marker gegen leeren Scan, Seiten-/Cursor-Blättern. Live-Beleg raw/28-10-canary.txt und raw/28-12-gates.txt: je 4x `geprüft 22 von 22`, 0x `: nein` (von mir nachgezählt). ABER: beide Läufe liegen vor CR-01; der Review belegt, dass die damalige Welt keine Nachricht im Datei-Raum hatte und `talk-message`-Treffer ungeprüft durchliefen. Fix (`_ROOM_SCREENED_PROVIDERS` in search.py:106, Welt-Nachricht canary_world.py:1062) ist unit-belegt, live nie gelaufen (`datei-raum-nachricht` in keiner Rohdatei). |
| 3 | Einzelzugriffe getaggt gegen nicht existent byte-gleich, normal und im Ausfall | PASSED (override) | `PAIR_CASES` 14 Fälle (tool_classes.py:119-132); `tests/unit/test_pair_equality_files.py` und `..._apps.py` über fünf Guard-Zustände, Abdeckungstests je Familie; WR-01-Reihenfolge in files.py:172-176 korrigiert, 5xx-Paar ergänzt. Live (vor Review-Fixes): `PAARE normal 13 von 14 (ausnahmen 1)`, 500/412/timeout je 14/14, 0x `ungleich`. Einzige Abweichung notes_create(category) normal = D-28-16, Owner-akzeptiert, gepinnt. |
| 4 | AST-Gate trägt Nadeln für systemtags-relations und systemtags-Schreibpfade, jede mit Gegenprobe | VERIFIED | `FORBIDDEN` enthält `systemtags-relations`, `tag:files`, `/apps/files/api/v1/files`; `SYSTEMTAGS_ROUTES` je Nadel eine Treffzeile; AST-Prüfung `test_no_module_writes_on_systemtags` erlaubt nur PROPFIND/REPORT. Eigene Mutationsprobe (Skript im Scratchpad, unabhängig vom Testmuster): je Nadel mit Nadel gefangen = True, ohne Nadel 0 Befunde, echtes systemtags-Modul sauber. Die Gegenprobe würde also ohne Nadel rot. |

**Score:** 3/4 verifiziert (davon 1 per Override), 1 unsicher (nur live beweisbar)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `tests/contract/tool_classes.py` | Klassen 12/3/7, Gründe, PAIR_CASES, Probe | VERIFIED | 222 Zeilen, von Freeze-, Paar- und Kanarientests genutzt |
| `tests/contract/test_tool_classes.py` | GATE-01 mit Gegenproben | VERIFIED | 7 Tests, grün |
| `tests/contract/test_no_destructive_calls.py` | EXCL-07 Nadeln, AST-Prüfung | VERIFIED | Nadeln bewaffnet, Mutationsprobe bestanden |
| `tests/integration/test_canary.py`, `canary_world.py` | GATE-02 | VERIFIED (Code), Live-Nachweis nach Fix offen | REQUIRE_LIVE macht Skip zu Fail (canary_world.py:111-118) |
| `tests/unit/test_pair_equality_files.py`, `..._apps.py` | GATE-03 Unit | VERIFIED | 609 und 600 Zeilen, grün |
| `tests/integration/test_pair_equality_live.py` | GATE-03 live | VERIFIED (Code), Live-Lauf vor Review-Fixes | |
| `tests/contract/test_provider_classes.py`, `tests/integration/test_provider_classes_live.py` | WR-02 Provider-Freeze | VERIFIED (Contract), Live nie gelaufen | findling, talk-*, deck, tables u. a. klassifiziert |
| `.github/workflows/ci.yml` Schritt GATE-02/03 | CI-Verdrahtung | WIRED | Job exapp, `NC_MCP_REQUIRE_LIVE: "1"`, drei Dateien; Bootstrap installiert notes, deck, tables, mail, spreed |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| test_tool_classes | Server-Registry | `Client(mcp).list_tools()` | WIRED | kein Literal |
| test_canary | Registry + tool_classes | `list_tools()`, PLAN-Gleichheit | WIRED | |
| search.py `_screen_conversations` | talk-message(-current) | `_ROOM_SCREENED_PROVIDERS` | WIRED | CR-01-Fix, Unit-Fälle in test_search_exclusion.py |
| ci.yml exapp | Kanarie/Paare/Provider-Gate | pytest mit REQUIRE_LIVE | WIRED | Lauf erst nach Push |

### Behavioral Spot-Checks (lokal, PYTHONUTF8=1)

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Unit + Contract | `uv run pytest tests/unit tests/contract -q` | 5100 passed, 33 skipped (Punkte gezählt, addopts unterdrückt die Summenzeile), EXIT=0 | PASS |
| Lint | `uv run ruff check .` | All checks passed!, EXIT=0 | PASS |
| Format | `uv run ruff format --check .` | 316 files already formatted | PASS |
| Typen | `PYRIGHT_PYTHON_FORCE_VERSION=latest uv run pyright` | 0 errors, 0 warnings, 0 informations | PASS |
| EXCL-07 Mutation | Scratchpad-Skript, Nadel aus FORBIDDEN entfernt | ohne Nadel 0 Befunde je Route | PASS |
| Kanarie/Paare/Provider live | braucht Docker + Nextcloud | nicht lokal | SKIP (human) |

### Probe Execution

Keine `scripts/*/tests/probe-*.sh` für diese Phase deklariert. Step 7c: nicht anwendbar.

### Requirements Coverage

| Requirement | Description | Status | Evidence |
|-------------|-------------|--------|----------|
| GATE-01 | Klassifikations-Freeze | SATISFIED | SC1 |
| GATE-02 | Kanarien-Integrationstest | NEEDS HUMAN | SC2, Live-Lauf nach CR-01 und erster CI-Lauf offen |
| GATE-03 | Byte-gleiche Paartests inkl. Ausfall | SATISFIED (Override D-28-16) | SC3 |
| EXCL-07 | Tag-Schreibpfade als Nadel | SATISFIED | SC4 |

Keine verwaisten Requirements. REQUIREMENTS.md führt alle vier noch als `Pending` (Traceability beim Phasenabschluss nachziehen, Info).

### Anti-Patterns Found

Keine TBD/FIXME/XXX/TODO/HACK in den 45 seit 372db35 geänderten Dateien unter src/, tests/, .github/.

| Befund | Severity | Impact |
|--------|----------|--------|
| Live-Belege von GATE-02/03 stammen vom Stand vor den Review-Fixes | Warning | Beweiskette zu SC2 lückenhaft, bis neu gefahren |
| Suchprovider-Default fail-open (WR-02, Owner-Entscheid offen) | Warning | unbekannte Drittanbieter-Provider auf Nutzerinstanzen ungeprüft |
| Kanarie läuft mit App-Passwort direkt, nicht über AppAPI/HaRP | Info | ExApp-Kette nur über CI-Job und Phase-27-Beweise |
| Tables-Freitextzellen mit `/f/<id>` bleiben unverändert (D-28-18) | Info | Restliste Phase 29 |

### Human Verification Required

1. **Live-Neulauf nach Review-Fixes:** Kanarie, Live-Paare, Provider-Gate gegen nc35 mit `NC_MCP_REQUIRE_LIVE=1`. Erwartet: 22 von 22 in vier Modi, 0 Urteil nein, Datei-Raum-Nachricht gebaut und nicht sichtbar, Paare 13/14 plus 3x 14/14, kein unklassifizierter Provider. Grund: alle Rohdateien liegen vor CR-01; die alte Welt baute den CR-01-Fall nicht.
2. **Erster CI-Lauf des GATE-02/03-Schritts** nach Owner-Push, NC 34 mit Findling. Grund: nur nach Push, andere Version und Provider-Menge als die Live-Messung (WR-04).
3. **Owner-Entscheid WR-02** fail-open gegen fail-closed.

### Gaps Summary

Keine blockierenden Lücken im Code: Freeze, Nadeln und Paartests sind substanziell, verdrahtet und lokal grün; die EXCL-07-Gegenproben habe ich unabhängig per Mutation bestätigt. Offen ist nur der Beweis für SC2 nach den Review-Fixes. Die in 28-LIVE-BEWEIS.md zitierten Zahlen stehen wörtlich in den Rohdateien (nachgezählt), aber sie belegen den Stand vor CR-01, und der Review hat genau für diesen Stand gezeigt, dass eine grüne Kanarie den Datei-Raum-Nachrichtenfall nicht abdeckte. Erst ein Live-Neulauf (lokal nc35 oder erster CI-Lauf) macht GATE-02 zu einem belegten grünen Test.

---

_Verified: 2026-09-30T19:24:37Z_
_Verifier: Claude (gsd-verifier)_
