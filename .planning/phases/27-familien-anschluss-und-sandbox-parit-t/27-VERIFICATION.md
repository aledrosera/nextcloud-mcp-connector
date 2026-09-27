---
phase: 27-familien-anschluss-und-sandbox-parit-t
verified: 2026-09-27T00:00:00Z
status: gaps_found
score: 5/6 must-haves verified (1 owner-abgelehnter Befund, 1 residualer CI-Nachweis)
gaps:
  - truth: "Die Wanduhr von prepare_context liegt gemessen im Rahmen der Phase-25-Referenz (Roadmap-Erfolgskriterium 2; Plan 27-08 must_have: Median ≤ 0,88 s short / ≤ 0,97 s full, je 5 Läufe, frisches NcClients je Aufruf)"
    status: failed
    reason: "Szenario B (kein-ki auf Datei und Ordner gesetzt), detail=full misst Median 1,047 s gegen die hergeleitete Schwelle 0,97 s (Referenz 0,81 s + Guard-Flight 0,107 s + Rauschreserve 0,05 s = 0,967 s, gerundet 0,97 s) , Überschreitung um 0,077 s. Der Owner hat diesen Befund am Checkpoint 27-08 (27.09.2026, Task 3) ausdrücklich NICHT akzeptiert und wörtlich 'Lückenplan' verlangt (27-LIVE-BEWEIS.md, Abschnitt '## Abnahme'). Die vom Ausführenden vorgelegte Einordnung (Kontrollmessung ohne Guard auf demselben Host: full 0,99-1,07 s, also Host-Drift) wurde vom Owner nicht als Begründung akzeptiert."
    artifacts:
      - path: ".planning/phases/27-familien-anschluss-und-sandbox-parit-t/27-LIVE-BEWEIS.md"
        issue: "Abschnitt 'Wanduhr prepare_context' zeigt vier Urteile, davon B full 'ueberschritten'; Abschnitt '## Abnahme' dokumentiert den Owner-Entscheid 'Lückenplan', keine Abnahme"
      - path: "tests/integration/test_ctx_bundle.py"
        issue: "Die Messung selbst ist korrekt und reproduzierbar (RUNS=5, frischer Guard je Aufruf, zwei Szenarien) , der gemessene Wert liegt aber tatsächlich über der eigenen, im selben Plan hergeleiteten Schwelle"
    missing:
      - "Ein Lückenplan (/gsd:plan-phase 27 --gaps), der die vom Checkpoint genannte Ansatzrichtung umsetzt: die fileid-Auflösung in prepare_context detail='full' seltener aufrufen (aktuell 3 zusätzliche SEARCH-Requests für Ausschnitte je Bündel in Szenario A full, 4 in B full), oder eine anderweitige Senkung des full-Medians unter 0,97 s"
      - "Eine erneute Wanduhr-Messung nach der Änderung, die B full unter die Schwelle bringt"
      - "Eine erneute, diesmal erteilte Owner-Abnahme (Task 3 von Plan 27-08) mit Datum unter '## Abnahme'"
human_verification:
  - test: "Den CI-Job 'exapp' beim nächsten Push beobachten und bestätigen, dass der Schritt 'Findling hits run through sandbox and exclusion (SBX-01)' (tests/integration/test_findling_sandbox.py) tatsächlich grün durchläuft, nicht nur wie hier verifiziert korrekt verdrahtet und lokal sauber übersprungen ist"
    expected: "Der CI-Schritt meldet PASSED für beide Teilfälle (Root-Sandbox-Fall mit skipped>=1 und Gegenprobe, Tag-Fall mit unverändertem skipped gegenüber der Gegenprobe)"
    why_human: "nc35 (die hier verfügbare Live-Instanz) hat keinen Findling-Provider; der Test kann in dieser Verifikation nur durch Codelesen und den lokalen SKIPPED-Lauf geprüft werden, nicht durch tatsächliche Ausführung gegen einen echten Findling. Das Erfolgskriterium 3 der Roadmap (Findling-Treffer mit nur fileId verschwindet wie ein Pfad-Treffer) ist für den Findling-Teil bis zu diesem CI-Lauf nur durch den gleichartigen comments-Fall (pfadlos, nur fileid, live auf nc35 bewiesen) indirekt gedeckt, nicht direkt."
---

# Phase 27: Familien-Anschluss und Sandbox-Parität Verification Report

**Phase Goal:** Was `kein-ki` trägt oder unter einem getaggten Ordner liegt, erscheint in keiner Antwort eines dateitragenden Werkzeugs mehr, weder als Treffer noch als Inhalt, Ausschnitt, Digest oder eingesetzter Dateiname; Findling-Treffer ohne Pfad und Notes laufen durch dieselbe Sandbox- und Ausschlussprüfung wie Pfad-Treffer.

**Verified:** 2026-09-27
**Status:** gaps_found
**Re-verification:** Nein , Erstverifikation

## Goal Achievement

### Observable Truths (Roadmap-Erfolgskriterien 1-5 plus Plan-Must-Haves)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | SC1: Getaggte Datei/Ordner fehlen in files_list/files_search/files_read/files_download; Upload verrät nichts | ✓ VERIFIED | 27-LIVE-BEWEIS.md SC1: 24 Zeilen gegen nc35, alle "ja"; files_read/download antworten byte-gleich zu `dav.not_found`; PROPFIND nach Upload zeigt unveränderten Zustand (404 bzw. gleiches ETag) |
| 2a | SC2 (ohne Wanduhr): unified_search, ChatGPT-search, fetch (auch vorher bekannte fileid), systemtags-Provider, prepare_context liefern keinen getaggten Treffer/Ausschnitt/Digest | ✓ VERIFIED | 27-LIVE-BEWEIS.md SC2: 10 Zeilen gegen nc35, alle "ja"; systemtags-Provider `roh=6 antwort=1` (Menge nicht verraten); prepare_context `treffer=8 ausschnitte=2` ohne getaggten Namen |
| 2b | SC2 Wanduhr: prepare_context liegt im Rahmen der Phase-25-Referenz (Median short ≤0,88 s, full ≤0,97 s, 2 Szenarien) | ✗ FAILED | raw/27-08-prepare-context.txt + 27-LIVE-BEWEIS.md: A short 0,786 s, A full 0,937 s, B short 0,797 s alle innerhalb; **B full 1,047 s gegen Schwelle 0,97 s, überschritten um 0,077 s.** Owner-Checkpoint 27-08 lehnt dies ab ("Lückenplan"), siehe Gap |
| 3a | SC3: pfadlose Treffer (comments, nur fileid) außerhalb der Root/getaggt verschwinden wie Pfad-Treffer; Notizen außerhalb der Root und getaggte Notizen/Kategorien verschwinden | ✓ VERIFIED | 27-LIVE-BEWEIS.md SC3: 8 Zeilen gegen nc35, alle "ja"; comments-Fall mit `skipped=1`; notes_search/read/create je mit korrektem Verhalten (EXCL-05, SBX-02) |
| 3b | SC3 Findling-Teil: fileId-only-Treffer verschwindet wie Pfad-Treffer (SBX-01) | ? UNCERTAIN | Test `tests/integration/test_findling_sandbox.py` existiert, ist substanziell (292 Zeilen, deckt Root-Fall und Tag-Fall inkl. Gegenproben), korrekt in `.github/workflows/ci.yml` nach dem Content-hit-Schritt verdrahtet (Zeile 121-128); lokal gegen nc35 (kein Findling-Provider) läuft er als SKIPPED mit benanntem Grund, nicht grün gefälscht. **Aber:** der Test ist bis zum nächsten Push noch nie tatsächlich gegen einen echten Findling-Provider gelaufen , 27-LIVE-BEWEIS.md nennt das selbst offen unter "Nicht live belegt". Siehe Human Verification |
| 4 | SC4: talk_browse setzt keinen Dateinamen einer getaggten Datei mehr in den Nachrichtentext ein | ✓ VERIFIED | 27-LIVE-BEWEIS.md SC4: 6 Zeilen gegen nc35, alle "ja"; `{file}`-Platzhalter statt Name, Gegenprobe mit offener Datei zeigt den Namen; Datei-Raum fehlt in conversations |
| 5 | SC5: Bei nicht beantwortbarer Prüfung hält jede Familie zurück und benennt die Degradation einmalig; im Erfolgsfall kein Zähler/Hinweis | ✓ VERIFIED | 27-LIVE-BEWEIS.md SC5: 9 Zeilen, alle "ja"; ein REPORT-500 je Aufruf erzeugt genau einen `{'source': 'exclusion', ...}`-Eintrag; Erfolgsfall: 14 Antworten ohne Zähler/Hinweis |
| 6 | Request-Kosten des Guards sind neu verankert und gemessen statt geschätzt (Pitfall 7) | ✓ VERIFIED | raw/27-08-prepare-context.txt: eigene Kategorien `exclusion-tags`, `exclusion-report`, `files-search`; Werte für kalt/warm/A/B dokumentiert und in test_ctx_bundle.py als Assertions verankert (Zeilen 753-756) |
| 7 | Owner hat den Live-Beweis abgenommen (Checkpoint Task 3 von Plan 27-08) | ✗ FAILED | 27-LIVE-BEWEIS.md Abschnitt "## Abnahme": Owner-Entscheid ist "Lückenplan", keine Abnahme. 27-08-SUMMARY.md bestätigt: "Status: CHECKPOINT OFFEN. Task 3 (Owner-Abnahme) ist nicht erledigt" |

**Score:** 5/8 Teiltruths verifiziert (2 klar fehlgeschlagen als ein zusammenhängender Befund gezählt, 1 unsicher) → aggregiert 5/6 Muss-Kriterien im Sinne der Anforderungsliste, mit 1 Blocker-Gap und 1 Human-Verification-Punkt

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `tests/integration/test_ctx_bundle.py` | Frischer Guard je Aufruf, RUNS=5, Guard-Kategorien, zwei Wanduhr-Szenarien | ✓ VERIFIED | 1122 Zeilen; `ExclusionGuard()` 1×, `RUNS = 5` 1×, `GUARD_LEGS = ("exclusion-tags", "exclusion-report", "files-search")`; Assertions auf Guard-Kategorien vorhanden |
| `tests/integration/test_findling_sandbox.py` | SBX-01 mit echtem Findling (CI), lokaler Skip mit Grund | ✓ VERIFIED (Code) / ? UNCERTAIN (Laufergebnis) | 292 Zeilen, vollständiger Docstring, Root-Fall + Tag-Fall + Gegenproben, `finally`-Aufräumen; noch nicht real gegen Findling gelaufen |
| `.github/workflows/ci.yml` | Schritt "Findling hits run through sandbox and exclusion (SBX-01)" nach Content-hit-Schritt | ✓ VERIFIED | Zeile 121-128, direkt nach "Content-hit permission fidelity with Findling (BL-02)" (Zeile 115-120), korrekte Env-Ladung |
| `.planning/phases/27.../27-LIVE-BEWEIS.md` | Messbericht mit SC1-5, Schwelle+Herleitung, Merker 28/29 | ✓ VERIFIED | Alle Abschnitte vorhanden, aus Rohdateien gespeist, Abnahme-Abschnitt zeigt Owner-Ablehnung transparent, keine Verschleierung |
| `src/mcp_connector/tools/context.py` | Guard als erstes gather-Mitglied, außerhalb jedes Bein-Budgets | ✓ VERIFIED | Zeile 253-254: `clients.exclusion.scope(clients)` als erstes Element von `asyncio.gather(...)` |
| Plans 27-01 bis 27-07 Artefakte (files_*, notes_*, talk_*, systemtags) | Guard-Verdrahtung je Familie | ✓ VERIFIED | Alle SUMMARYs mit "Self-Check: PASSED", "Known Stubs: Keine"; Requirement-IDs EXCL-01/03/05/06, SBX-01/02 in Plan-Frontmatter über 27-01 bis 27-07 verteilt abgedeckt |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `.github/workflows/ci.yml` (Job exapp) | `tests/integration/test_findling_sandbox.py` | Schritt nach Content-hit-Schritt | ✓ WIRED | Pattern `test_findling_sandbox` gefunden, korrekte Reihenfolge |
| `src/mcp_connector/tools/context.py` (prepare_context) | `clients.exclusion.scope` | erstes `asyncio.gather`-Mitglied | ✓ WIRED | Bestätigt per Codelesen, entspricht Plan-27-06-Anspruch und Merker (c) "gelöst ohne shield" |
| `27-LIVE-BEWEIS.md` | Rohdateien (`raw/27-*.txt`) | Tabellenverweise je Erfolgskriterium | ✓ WIRED | Stichprobenartig gegen raw/27-07-live.txt und raw/27-08-prepare-context.txt geprüft, Zahlen stimmen überein |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|--------------|--------|----------|
| EXCL-01 | 27-01, 27-02, 27-07 | Getaggte Datei/Ordner in keiner Datei-Werkzeug-Antwort, Upload orakelfrei | ✓ SATISFIED | SC1 live bewiesen (24/24 "ja") |
| EXCL-03 | 27-01, 27-03, 27-05, 27-06, 27-07 | unified_search/fetch/prepare_context liefern keinen getaggten Treffer/Ausschnitt/Digest; systemtags-Provider verrät nichts | ⚠️ TEILWEISE (Kernpunkte SATISFIED, Wanduhr-Teil BLOCKED) | SC2-Kernaussagen (10/10 "ja") erfüllt; die im selben Requirement-Kontext geforderte Wanduhr-Parität (Roadmap SC2) verfehlt die Schwelle und ist vom Owner nicht abgenommen |
| EXCL-05 | 27-04, 27-07 | Notes respektieren den Tag (Mess-Spike-Bedingung erfüllt laut Phase 25 K4) | ✓ SATISFIED | notes_search/read/create mit Guard+Sandbox, live SC3 bewiesen |
| EXCL-06 | 27-05, 27-07 | talk_browse setzt keine Dateinamen getaggter Dateien mehr ein | ✓ SATISFIED | SC4 live bewiesen (6/6 "ja") |
| SBX-01 | 27-03, 27-08 | Findling-Treffer nur mit fileId laufen durch Sandbox/Ausschluss | ? NEEDS HUMAN | Code verdrahtet und lokal korrekt übersprungen; realer Findling-Lauf steht noch aus (nächster Push) |
| SBX-02 | 27-01, 27-03, 27-04, 27-07 | Notes laufen durch Sandbox und Ausschluss | ✓ SATISFIED | notes_search mit Root-Filter, live SC3 bewiesen (`count=0 skipped=3`) |

Keine Waisen-Requirements: alle sechs der Phase 27 zugeordneten IDs (EXCL-01, EXCL-03, EXCL-05, EXCL-06, SBX-01, SBX-02) sind über die Plan-Frontmatter-Felder `requirements:` der Pläne 27-01 bis 27-08 abgedeckt; REQUIREMENTS.md führt keine weitere Phase-27-ID, die in keinem Plan erscheint.

### Anti-Patterns Found

Keine TBD/FIXME/XXX/HACK/PLACEHOLDER-Marker in den von Phase 27 modifizierten Dateien (`tests/integration/test_ctx_bundle.py`, `tests/integration/test_findling_sandbox.py`, Tool-/Client-Dateien der Familien files/notes/talk/search). Alle acht Plan-SUMMARYs melden explizit "Known Stubs: Keine".

### Gaps Summary

Ein Blocker steht der Zielerreichung entgegen: Die vom Milestone selbst als Erfolgskriterium 2 verlangte Wanduhr-Parität von `prepare_context` gegenüber der Phase-25-Referenz ist gemessen, aber im Szenario B (kein-ki auf Datei und Ordner gesetzt), detail='full', mit Median 1,047 s um 0,077 s über der eigens hergeleiteten Schwelle von 0,97 s. Das Ausführungsteam hat diesen Befund transparent im Live-Beweis dokumentiert (kein stiller Pass) und eine Einordnung über eine Kontrollmessung ohne Guard-Code auf demselben Host geliefert (Host-Drift-Hypothese: 0,99-1,07 s auch ohne Guard). Der Owner hat diese Einordnung am Checkpoint 27-08 (27.09.2026) jedoch ausdrücklich abgelehnt und wörtlich einen Lückenplan verlangt, mit dem Ansatzpunkt, die fileid-Auflösung in prepare_context detail='full' seltener aufzurufen. Damit ist die Owner-Abnahme (Task 3 von Plan 27-08) nicht erteilt, und die Phase gilt laut eigenem Plan-Text ("Die Phase bleibt offen, bis die Messung unter der Schwelle liegt und die Abnahme erneut vorgelegt wurde") als nicht abgeschlossen.

Zusätzlich bleibt ein einzelner, benannter Residualpunkt offen: der Findling-Anteil von Erfolgskriterium 3 (SBX-01) ist korrekt und substanziell als CI-Test verdrahtet, lief aber bis zu dieser Verifikation noch nie gegen einen echten Findling-Provider (nc35 hat keinen). Der Live-Beweis benennt das selbst unter "Nicht live belegt" und stützt sich ersatzweise auf den strukturgleichen comments-Fall. Das ist keine verdeckte Lücke, aber ein noch unbestätigtes Muss-Kriterium; es wird als Human-Verification-Punkt geführt statt als eigener Blocker, weil die Codequalität und die CI-Verdrahtung selbst keine offenen Fragen aufwerfen.

Alle übrigen Erfolgskriterien (1, 2 ohne Wanduhr, 3 ohne Findling-Teil, 4, 5) sowie die Request-Kosten-Messung sind live gegen nc35 bewiesen und stimmen mit den Rohdateien überein.

---

_Verified: 2026-09-27_
_Verifier: Claude (gsd-verifier)_
