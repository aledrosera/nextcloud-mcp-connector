---
phase: 28
slug: gates-und-beweise
status: verified
threats_total: 56
threats_closed: 56
threats_open: 0
register_authored_at_plan_time: true
asvs_level: 1
created: 2026-09-30
---

# Phase 28: Security

> Sicherheitsvertrag dieser Phase: Bedrohungsregister, akzeptierte Risiken, Prüfspur.

Gegenstand: die Gates, die "keine Tool-Antwort zeigt Getaggtes" zu einem roten oder grünen
Test machen (GATE-01 Klassifikations-Freeze, GATE-02 Kanarie, GATE-03 Paartests, EXCL-07
AST-Nadeln), dazu die sechs `src/`-Fixes der Phase (D-28-14 Tables-Link-Zellen, D-28-15
Talk-Ausfall, D-28-17 Fehlerreihenfolge, D-28-19 files_search-Ordner, D-28-21
talk-conversations) und die sieben Review-Fixes `1f9da6b..36c08cf` (CR-01, WR-01 bis WR-06).
Geprüft am Code auf `main` 9416b4c (Datei:Zeile) und an den Tests, die die jeweilige
Mitigation belegen. Register aus den `<threat_model>`-Blöcken von `28-01-PLAN.md` bis
`28-12-PLAN.md` (56 Einträge), Threat Flags aus allen zwölf Summaries.

Der Auditor hat am 30.09. selbst ausgeführt:

- 18 Suiten der Phase (`tests/contract/test_tool_classes.py`, `test_result_shapes.py`,
  `test_no_destructive_calls.py`, `test_provider_classes.py`, `test_tool_surface.py`,
  `tests/unit/test_talk_exclusion.py`, `test_fetch_message_exclusion.py`,
  `test_fetch_exclusion.py`, `test_notes_exclusion.py`, `test_tables_exclusion.py`,
  `test_files_exclusion.py`, `test_files_upload_exclusion.py`, `test_pair_equality_files.py`,
  `test_pair_equality_apps.py`, `test_search_exclusion.py`, `test_guard_routes.py`,
  `test_live_requirement.py`, `test_canary_refusals.py`): 403 passed, 0 failed.
- `scripts/check_tool_budget.py`: Exit 0, 17233 von 18000 Bytes, 22 Werkzeuge.
- `git diff 372db35..HEAD -- src/mcp_connector/server/`: leer.
- Secret-Scan des Phasenordners gegen die Werte von `NC_MCP_TEST_APP_PASSWORD`,
  `..._APP_PASSWORD2`, `NC_MCP_TEST_PASSWORD`, `..._PASSWORD2` und `APP_SECRET` aus
  `.env.nc35` und `.env.exapp`: 0 Treffer.
- Nachzählung in `raw/`: `raw/28-11-pairs-live.txt` 56 Zeilen `PAAR `, 51 `: gleich`,
  0 `ungleich`, 0 `: nein`, 39 `AUSFALL-TEXT ... ja`; `raw/28-10-canary.txt` 4x
  `geprüft 22 von 22`, 0x `: nein`.

Integrationstests gegen nc35 oder CI wurden nicht gefahren (kein Docker/Nextcloud hier);
dafür gelten die Rohdateien unter `raw/`, mit dem Vorbehalt aus H-1.

---

## Trust Boundaries

| Grenze | Beschreibung | Was sie überquert |
|--------|--------------|-------------------|
| Harness zu nc35 und CI-Instanz | WebDAV, OCS, Tables, Notes, Talk, Deck, CalDAV, `occ` im Container | Schreibzugriffe, Tags, Freigaben an user2 |
| Client(mcp) zu Nextcloud | Werkzeuge mit dem App-Passwort des Testnutzers | Credentials, Rohantworten |
| Registry zu Gates | ein neues Werkzeug oder ein neuer Suchprovider betritt die Oberfläche | unklassifizierte Ausgabeflächen |
| Quelltext `src/` zu Nextcloud systemtags | jeder künftige Aufruf könnte den Tag setzen, entfernen oder umbenennen | Tag-Relationen, Tag-Sichtbarkeit |
| Modell zu Einzelzugriff | Pfade, fileids, Note-Ids, Talk-Tokens, Tabellen-Ids, Kategorien | Existenz-Orakel |
| Tabellenautor zu Zellwert | Link-Zellen speichern Kopien von Dateiname und fileid | Namen getaggter Dateien |
| Nextcloud-Antworten zu Tool-Antworten | jede Ausgabefläche (Text, structured, Blob, URI, cursors) | Marker, Zähler |
| Messung zu Bericht | Zahlen in `28-LIVE-BEWEIS.md` | Beweiskraft |

---

## Threat Register

| Threat ID | Kategorie | Komponente | Disposition | Mitigation und Beleg | Status |
|-----------|-----------|------------|-------------|----------------------|--------|
| T-28-01 | Tampering | Harness schreibt auf die Testinstanz | mitigate | Wegwerfstamm je Lauf (`run_id`, `tests/integration/canary_world.py:742`), jede Nebenwirkung sofort in `Cleanup` gebucht (`:622-684`), `run` entfernt rückwärts und liest jeden Rohwert zurück (`:672-684`), selbst angelegter Tag wird per `tag:delete` entfernt, vorbestehender nur entkoppelt (`add_tag` `:655-670`), `finally` in `canary_world` (`:1244-1252`) und `test_live_questions_28.py:141-148` mit `assert all(cw.cleanup_ok(...))` | closed |
| T-28-02 | Tampering | occ im falschen Container | mitigate | `occ` nur über `topology.NC_CONTAINER` (`canary_world.py:231-243`, Laufprüfung `:171-177`); Literal `nc35-nc` in allen Phase-28-Harnessdateien 0 Treffer (Grep); Aufbau-Assert PROPFIND 207 (`canary_world.py:344`) und `tag:list` mit `kein-ki` (`test_live_questions_28.py:135`) | closed |
| T-28-03 | Information Disclosure | Marker in Rohdatei im Repo | accept | Siehe A-28-01. Marker `mk<uuid4>` je Lauf (`canary_world.py:742`) | closed |
| T-28-04 | Spoofing | App-Passwort im Protokoll | mitigate | `record` schreibt nur die übergebene Zeile (`canary_world.py:124-128`); keine `print`/`record`-Stelle der Phasen-Tests gibt Env, Header oder Auth aus (Grep); Secret-Scan des Phasenordners 0 Treffer (Auditor) | closed |
| T-28-10 | Information Disclosure | neues Werkzeug (files_update) umgeht den Guard | mitigate | `freeze_findings` gegen `Client(mcp).list_tools()` (`tests/contract/tool_classes.py:163-206`, `tests/contract/test_tool_classes.py:27-33`); Probe `files_update` über `mcp.add_tool` muss `unclassified: files_update` liefern (`test_tool_classes.py:36-47`). Ergänzt durch den Provider-Freeze aus WR-02 (`tests/contract/test_provider_classes.py:15-45`) | closed |
| T-28-11 | Tampering | Probe-Werkzeug leckt in andere Registry-Tests | mitigate | `probe_tool` mit `finally: mcp.remove_tool` (`tool_classes.py:209-222`); Abwesenheit nach dem Block geprüft (`test_tool_classes.py:45-47`); `test_tool_surface.py` grün (Auditor) | closed |
| T-28-12 | Repudiation | leere oder floskelhafte Begründung | mitigate | `MIN_REASON = 20`, einzeilig, Schlusspunkt (`tool_classes.py:113`, `:149-159`); alle 22 Gründe tragen einen `datei.py:Zeile`-Anker (Auditor-Prüfung); Gegenproben leer, zu kurz, ohne Punkt (`test_tool_classes.py:50-62`). Hinweis H-3 | closed |
| T-28-13 | Information Disclosure | Id-Normalisierung verdeckt Unterschiede | mitigate | Wortgrenzen-Regex `(?<![0-9A-Za-z])...(?![0-9A-Za-z])` nur für `requested_forms` (`tests/contract/result_shapes.py:32`, `:61-72`); Tests "12" gegen "1234"/"size 120" und kurze Segmente (`tests/contract/test_result_shapes.py:13-38`) | closed |
| T-28-20 | Tampering | Connector entfernt kein-ki (Relation DELETE/PUT) | mitigate | Nadel `systemtags-relations` (`tests/contract/test_no_destructive_calls.py:132`), globale DELETE-Nadel (`:87`), AST `tag_writes` (`:775`); Gegenproben je Nadel (`:682-715`); Grep `src/` ohne Treffer | closed |
| T-28-21 | Elevation of Privilege | PROPPATCH/POST auf `/systemtags/{id}` | mitigate | globale PROPPATCH-Nadel (`test_no_destructive_calls.py:90`) plus AST-Methodenprüfung auf `TAGS_PATH` mit Erlaubnisliste PROPFIND/REPORT (`:233-236`, `:815-824`); Gegenproben POST, PROPPATCH, DELETE auf TAGS_PATH (`:826-864`) | closed |
| T-28-22 | Tampering | mehrzeiliger Aufruf | mitigate | AST über ganze Call-Knoten (`test_no_destructive_calls.py:764-773`); Gegenprobe mehrzeilige Form (`test_the_systemtags_check_would_notice_a_multiline_write_in_real_code`, `:865`); Review-Fix WR-06 `36c08cf`: `build_request` in `CALL_ATTRS` (`:218-223`), Gegenprobe `build_request` plus `send` (`:848-852`, `:919`) | closed |
| T-28-23 | Tampering | Schreibaufruf auf `home_url` im systemtags-Modul | mitigate | Modulregel `systemtags_module_writes` (`test_no_destructive_calls.py:789`); Gegenproben put/POST/send auf `home_url(creds)` (`:885-890`) | closed |
| T-28-24 | Tampering | occ `tag:files` in `src/` | mitigate | Nadel `tag:files` (`test_no_destructive_calls.py:133`), `SRC = src/mcp_connector` (`:30`); Harness in `tests/`; Grep `tag:files` in `src/` ohne Treffer | closed |
| T-28-25 | Tampering | alte Datei-Tags/Favoriten | mitigate | Routen-Nadel `/apps/files/api/v1/files` (`test_no_destructive_calls.py:135`); PROPPATCH-Beweiszeilen `oc:tags`/`oc:favorite` (`:717-733`) | closed |
| T-28-30 | Information Disclosure | `talk.one_room` im Ausfall | mitigate | Guard nur auf dem Fehlerpfad nach der Liste, `unverifiable` ergibt `withhold.unavailable_error()` für jedes nicht sichtbare Token (`src/mcp_connector/tools/talk.py:860-863`); Unit-Paare 500/412/timeout (`tests/unit/test_talk_exclusion.py:607-680`, `tests/unit/test_fetch_message_exclusion.py:197`). Hinweis H-2 (IN-02) | closed |
| T-28-31 | Information Disclosure | fetch(file:)/notes_read bei 5xx des Nachbarn | mitigate | Reihenfolge wie `_visible_stat`: Guard-Fehler, `unverifiable`, Lookup-Fehler, dann Tag (`src/mcp_connector/tools/chatgpt.py:333-344`, `tools/notes.py:189-199`); Tests `tests/unit/test_fetch_exclusion.py:162`, `:182`, `tests/unit/test_notes_exclusion.py:377`, `:398` | closed |
| T-28-32 | Denial of Service | Guard-Request auf dem Talk-Fehlerpfad | accept | Siehe A-28-02. Scope-Abfrage erst nach erfolgloser Listensuche (`talk.py:860`) | closed |
| T-28-33 | Elevation of Privilege | Reihenfolge-Umbau überspringt den Tag | mitigate | `unverifiable` weiterhin zuerst, Tag vor jedem Inhalt (`chatgpt.py:335-346` vor `files_tools.read` `:348`; `notes.py:191-199`); bestehende Ausschluss-Suiten grün (Auditor) | closed |
| T-28-34 | Elevation of Privilege | Wire-Schema | mitigate | `git diff 372db35..HEAD -- src/mcp_connector/server/` leer; `check_tool_budget.py` Exit 0 (Auditor) | closed |
| T-28-40 | Information Disclosure | tables_browse/fetch(table:) zeigen Namen getaggter Dateien | mitigate | `screen_links` vor `_row`/`as_text` (`src/mcp_connector/tools/tables.py:408`, `:458-551`), `fetch(table:)` über dieselbe Funktion (`chatgpt.py:840`); Zelle wird `None` wie die leere Zelle der App (Hinweis H-5); Paar getaggt gegen leer (`tests/unit/test_tables_exclusion.py:200`, `tests/unit/test_pair_equality_apps.py:464`) | closed |
| T-28-41 | Information Disclosure | Ausfall der Prüfung | mitigate | `unverifiable` leert alle Datei- und Raum-Link-Zellen, `unavailable=True` (`tables.py:504-505`), ein `degraded`-Eintrag mit `EXCLUSION_UNAVAILABLE` (`tables.py:423-424`, `tools/withhold.py:62-68`); Tests `test_tables_exclusion.py:269`, `:397`, `:465` | closed |
| T-28-42 | Information Disclosure | getaggter Ordner, nicht auflösbare fileid | mitigate | nicht aufgelöst wird zurückgehalten, Lookup-Fehler leert alles (`tables.py:529-548`); Tests `test_tables_exclusion.py:242`, `:254`; Review-Fix WR-03 `097434c`: fremde providerIds mit `/f/<id>` und Raum-Links (`tables.py:554-600`, Tests `:300`, `:317`, `:365`) | closed |
| T-28-43 | Information Disclosure | Fremdtext mit Dateinamen | accept | Siehe A-28-03 | closed |
| T-28-44 | Information Disclosure | Tables ohne Sandbox | accept | Siehe A-28-04. Grenze im Docstring (`tables.py:481-483`) | closed |
| T-28-45 | Denial of Service | Guard-Request je Tabellenaufruf | mitigate | Guard nur bei vorhandener Link-Zelle (`tables.py:498-499`), höchstens ein REPORT (`:501`); Tests `test_tables_exclusion.py:149`, `:436`, `:475` | closed |
| T-28-50 | Information Disclosure | files_search(folder=getaggt) | mitigate | D-28-19: `dav.not_found(search_scope)` aus derselben Fabrik ohne Zusatzrequest (`src/mcp_connector/tools/files.py:176-177`); Review-Fix WR-01 `e3da1de`: SEARCH-Fehler vor dem Tag (`:172-173`); Tests `tests/unit/test_files_exclusion.py:602`, `:618`, `tests/unit/test_pair_equality_files.py:437`, `:463` (500, 503, timeout) | closed |
| T-28-51 | Information Disclosure | Chunk 1 in getaggten Ordner | mitigate | D-28-20: kein Befund, Pin-Test wortgleich bis auf den Pfad (`tests/unit/test_files_upload_exclusion.py:227-265`, `test_pair_equality_files.py:544`) | closed |
| T-28-52 | Tampering | Fix schreibt Chunks für getaggte Ziele | mitigate | `writes.count == 0` (kein MKCOL, PUT, MOVE) für getaggte Ziele (`test_files_upload_exclusion.py:163`, `:180`, `:258`) | closed |
| T-28-53 | Information Disclosure | benannte Ausnahme wächst still | mitigate | `NAMED_EXCEPTIONS` in `freeze_findings` geprüft (`tool_classes.py:200-205`); `NAMED_HERE` leer für files (`test_pair_equality_files.py:68-69`); Pin `test_notes_create_is_a_named_residual_oracle` (`test_pair_equality_apps.py:554`); Live-Assert `set(NAMED_EXCEPTIONS) == {("notes_create", "category")}` (`tests/integration/test_pair_equality_live.py:457`) | closed |
| T-28-70 | Tampering | Rückstände auf der Testinstanz | mitigate | Cleanup im `finally` mit Rückleseprüfung (`canary_world.py:1244-1252`, `:672-684`), Assert aller Zeilen (`tests/integration/test_canary_world.py:226-237`); zwei Läufe in `raw/28-07-world.txt` mit je `18 Zeilen, 18 gelesen ok` | closed |
| T-28-71 | Tampering | occ im falschen Container | mitigate | wie T-28-02; Aufbaubeweis über die getaggten fileids per Tag-REPORT (`canary_world.py:1161-1184`, `test_canary_world.py:168-175`) | closed |
| T-28-72 | Repudiation | grüne Kanarie bei leerer Welt | mitigate | Kontroll-Marker aus der ungetaggten Datei und Notiz (`test_canary_world.py:134-150`), Tables-Zeile roh mit Namen und `/f/<id>` (`:178-189`), Kalender-ATTACH (`:191-203`) | closed |
| T-28-73 | Information Disclosure | Freigabe an user2 | accept | Siehe A-28-05. Freigabe gebucht und zurückgelesen (`canary_world.py:868-873`, `:1042-1045`; `raw/28-07-world.txt` `CLEANUP share user2 ...: 404`) | closed |
| T-28-80 | Information Disclosure | Existenz-Orakel der Datei-Einzelzugriffe | mitigate | Paartests ganzer `CallToolResult` in fünf Guard-Zuständen (`GUARD_MODES`, `test_pair_equality_files.py:51`, Vergleich `:162-171`) | closed |
| T-28-81 | Repudiation | Paarfall still übersprungen | mitigate | Abdeckungstests gegen `PAIR_CASES` (`test_pair_equality_files.py:575`, `test_pair_equality_apps.py:595`); kein `pytest.skip` in beiden Dateien (Grep) | closed |
| T-28-82 | Information Disclosure | Timing-Orakel | accept | Siehe A-28-06. `test_time_is_not_part_of_the_comparison` (`test_pair_equality_files.py:584`) | closed |
| T-28-90 | Information Disclosure | notes_read/fetch(note) | mitigate | Paare in fünf Zuständen (`test_pair_equality_apps.py:216`, `:224`) plus Notes-5xx (`:242-243`, 500 und 503) | closed |
| T-28-91 | Information Disclosure | Talk-Datei-Raum im Ausfall | mitigate | Paare nach D-28-15, `EXCLUSION_UNAVAILABLE` auf beiden Seiten (`test_pair_equality_apps.py:360-376`) | closed |
| T-28-92 | Tampering | talk_send schreibt trotz Abweisung | mitigate | `routes.call_count == 0` der Chat-POST-Route auf beiden Seiten in allen Zuständen (`test_pair_equality_apps.py:386-387`) | closed |
| T-28-93 | Information Disclosure | notes_create Kategorie-Orakel | accept | Siehe A-28-07. Pin `test_pair_equality_apps.py:554`, Schreibzähler 0 für die getaggte Kategorie (`:568`) | closed |
| T-28-94 | Information Disclosure | fetch(table:) Namensabfluss | mitigate | Paar getaggt gegen leer (normal) und gegen ungetaggt (Ausfall), Dateiname nicht im JSON (`test_pair_equality_apps.py:464-488`) | closed |
| T-28-100 | Information Disclosure | Marker in irgendeiner Tool-Antwort | mitigate | Scan aller Flächen `surfaces` plus `cursor_surfaces` (`tests/integration/test_canary.py:124-130`, `:285-289`), vier Modi (`:439-457`), Registry gleich Plan und `== 22` (`:344-365`); D-28-21 und Review-Fix CR-01 `1f9da6b`: `_ROOM_SCREENED_PROVIDERS` inkl. `talk-message(-current)` (`src/mcp_connector/tools/search.py:95`, `:106`, `:352-395`), Unit-Tests `tests/unit/test_search_exclusion.py:479-640`; Kanarien-Welt schreibt die Datei-Raum-Nachricht (`canary_world.py:1062`). Live-Nachweis nach CR-01 ausstehend, Hinweis H-1 | closed |
| T-28-101 | Repudiation | grüne Kanarie bei leerem Index/falschem Container | mitigate | `KONTROLLE`-Prüfung im Normalbetrieb (`test_canary.py:322-331`), Aufbaubeweis wie T-28-72; Review-Fix WR-04 `51e6a4d`: `NC_MCP_REQUIRE_LIVE=1` macht jeden Skip zum Fehler (`canary_world.py:111-118`, `.github/workflows/ci.yml:139-141`, Test `tests/unit/test_live_requirement.py:23-39`); WR-05 `4675bdb`: Abweisung nur mit dem erwarteten Satz, Schalter neutralisiert (`canary_world.py:190-225`, `test_canary.py:305-320`, `tests/unit/test_canary_refusals.py`) | closed |
| T-28-102 | Information Disclosure | Zähl-Orakel über Provider-cursors | mitigate | cursors im Scan (`test_canary.py:124-130`), Trefferzahl je Provider protokolliert und `< MAX_LIMIT` (alle Treffer auf Seite 1, `:389-400`) | closed |
| T-28-103 | Repudiation | Echo des Markers aus Argumenten | mitigate | `assert world.marker not in json.dumps(args)` vor jedem Aufruf (`test_canary.py:257`, `:350-352`) | closed |
| T-28-104 | Tampering | Rückstände schreibender Werkzeuge | mitigate | `register_tool_write` (`canary_world.py:854-866`, Aufruf `test_canary.py:275`), Werkzeug-Einträge vor der Welt entfernt und zurückgelesen (`canary_world.py:1245-1247`), Assert Anzahl gleich Ledger und alle ok (`test_canary.py:413-424`) | closed |
| T-28-105 | Information Disclosure | search im Ausfall ohne Hinweis | accept | Siehe A-28-08 | closed |
| T-28-110 | Information Disclosure | Existenz-Orakel mit echten Nextcloud-Antworten | mitigate | Live-Paare aller `PAIR_CASES` in vier Modi, ganzer `CallToolResult` normalisiert (`test_pair_equality_live.py:67`, `:321-326`, `:410-431`); Rohdatei `raw/28-11-pairs-live.txt` (Nachzählung oben). Live-Lauf vor WR-01, Hinweis H-1 | closed |
| T-28-111 | Repudiation | Ausnahme still übersprungen | mitigate | `AUSNAHME`-Zeile je `NAMED_EXCEPTIONS`-Schlüssel (`test_pair_equality_live.py:395-396`, `:448-470`; 2 Zeilen in `raw/28-11-pairs-live.txt`), `set(CASES) == set(PAIR_CASES)` (`:404-406`), `compared + skipped == len(PAIR_CASES)` (`:431`) | closed |
| T-28-112 | Tampering | Rückstände der Ausnahme notes_create | mitigate | `register_tool_write` (`test_pair_equality_live.py:256`), Rückleseprüfung (`:305-314`) | closed |
| T-28-113 | Repudiation | CI-Schritt nie gelaufen | accept | Siehe A-28-09. Hinweis im Abschnitt "Offen" (`28-LIVE-BEWEIS.md:156-159`) | closed |
| T-28-114 | Information Disclosure | Secrets im CI-Log durch `-s` | mitigate | `record`/`print` geben nur Tool-Ergebnisse, Zählzeilen und Nutzername aus (`test_canary.py:362-364`, `:403-409`, `test_pair_equality_live.py:430`); kein `set -x` im Schritt (`ci.yml:142-144`); Secret-Scan 0 Treffer (Auditor) | closed |
| T-28-120 | Repudiation | geschönte Zahlen im Live-Beweis | mitigate | Rohdatei-Spalte je Befund (`28-LIVE-BEWEIS.md:29`, `:41`, `:61`, `:71`, `:92`, `:135`); Stichprobe des Auditors deckt sich (56 PAAR, 51 gleich, 39 AUSFALL-TEXT, 4x 22 von 22); Owner-Abnahme (`:172-178`) | closed |
| T-28-121 | Tampering | 27-07-live.txt überschrieben | mitigate | Kopie `raw/28-12-exclusion-live.txt` vorhanden; `git diff --quiet 372db35 HEAD -- .planning/phases/27-.../raw/27-07-live.txt` Exit 0 (Auditor) | closed |
| T-28-122 | Repudiation | CI-Nachweis als erbracht dargestellt | mitigate | Abschnitt "Offen": "Er läuft erst nach dem Push, und der Push ist Owner-Entscheid" (`28-LIVE-BEWEIS.md:156-159`) | closed |
| T-28-123 | Information Disclosure | akzeptierte Restorakel verschwinden | mitigate | "Merker für Phase 29" mit D-28-12, D-28-13, D-28-16, D-28-20, T-28-44, T-28-43 (`28-LIVE-BEWEIS.md:161-170`) | closed |

*Status: open · closed*
*Disposition: mitigate (Umsetzung nötig) · accept (dokumentiertes Risiko) · transfer (Dritte)*

### Unregistered Flags

Alle zwölf Summaries melden unter `## Threat Flags` keine neue Angriffsfläche oder verweisen
nur auf registrierte Ids (28-05, 28-10, 28-11, 28-12); 28-01, 28-03, 28-04, 28-06, 28-08
und 28-09 haben keinen Abschnitt. Aus dem Review (`28-REVIEW.md`) stammen zwei Punkte ohne
Threat-Id und ohne Eintrag im Accepted Risks Log (WARNING, kein Blocker):

- **UF-28-01 (WR-02, Owner-Entscheid offen):** Laufzeit-Default der Suchprovider-Klassifikation
  bleibt fail-open (`tools/withhold.py:103-105`). Gebaut ist nur das Gate
  (`tests/contract/test_provider_classes.py`, `tests/integration/test_provider_classes_live.py`,
  live nie gelaufen). Restrisiko: ein Drittanbieter-Provider auf einer Nutzerinstanz, der
  Dateien auf eigene Weise benennt, läuft ungeprüft durch; das Gate sieht nur die CI-Instanz.
  Empfehlung: nach dem Owner-Entscheid als akzeptiertes Risiko (mit Doku Phase 29) oder als
  Fix erfassen.
- **UF-28-02 (IN-02, nicht behoben):** im Zustand `active` mit getaggtem Ordner antwortet ein
  gelisteter Datei-Raum bei scheiterndem Pfad-Lookup mit `unavailable_error()`
  (`tools/talk.py:852-856`, `file_screen` `:245-249`), ein erfundenes Token mit
  `_unknown_token` (`:863`). Während eines DAV-SEARCH-Ausfalls ist damit erkennbar, dass ein
  Token ein Datei-Raum ist, auch für eine getaggte Datei. Schmales Nachbar-Ausfall-Orakel der
  Art D-28-17, außerhalb der Mitigation von T-28-30 (die den Guard-Ausfall abdeckt).
  Empfehlung: für Phase 29 als Restorakel dokumentieren oder angleichen.

---

## Accepted Risks Log

| Risk ID | Threat Ref | Begründung | Akzeptiert von | Datum |
|---------|------------|------------|----------------|-------|
| A-28-01 | T-28-03 | Marker je Lauf zufällig (uuid4), benennt keine echte Datei, nur Testinstanz | Plan 28-01 | 2026-09-28 |
| A-28-02 | T-28-32 | Zusätzlicher Guard-Request nur auf dem Fehlerpfad, ein Scope je Aufruf, kein Brute-Force-Zähler bei Nextcloud (Liste statt `/room/{token}`) | Plan 28-04 | 2026-09-28 |
| A-28-03 | T-28-43 | Fremdtext mit Dateinamen (eingetippt, Rich-Text, Deck-Beschreibung, Freitextzelle mit `/f/<id>`) liegt außerhalb eines fileid-basierten Guards; ehrliche Grenze in Phase-29-Doku (Research A2, D-28-18, Review-Notiz WR-03) | Plan 28-05, Owner D-28-18 | 2026-09-28 |
| A-28-04 | T-28-44 | Tables bekommt wie Talk (T-27-46) nur den Tag, keine Sandbox; Merker Phase 29 | Plan 28-05 | 2026-09-28 |
| A-28-05 | T-28-73 | Freigabe nur zwischen Testkonten der Wegwerfinstanz, wird gelöscht und zurückgelesen | Plan 28-07 | 2026-09-28 |
| A-28-06 | T-28-82 | Timing-Orakel (ein REPORT mehr für Getaggtes), keine künstliche Verzögerung, Doku Phase 29 | Owner D-28-12 | 2026-09-28 |
| A-28-07 | T-28-93 | notes_create: nicht existente Kategorie wird angelegt, getaggte abgewiesen; gepinnt, Doku als Restorakel Phase 29 (Override in `28-VERIFICATION.md`) | Owner D-28-16 | 2026-09-28 |
| A-28-08 | T-28-105 | ChatGPT-`search` liefert im Ausfall weniger Treffer ohne Hinweis; Schema bleibt, Kanarie belegt nur, dass nichts Getaggtes durchkommt; ein Satz Doku Phase 29 | Owner D-28-13 | 2026-09-28 |
| A-28-09 | T-28-113 | CI-Schritt läuft erst nach Push (Owner-Entscheid, wie SBX-01); lokaler nc35-Beweis im Rohprotokoll | Plan 28-11 | 2026-09-28 |

*Akzeptierte Risiken tauchen in späteren Audits nicht erneut auf.*

---

## Hinweise (keine offenen Threats)

- **H-1 (T-28-100, T-28-101, T-28-110, T-28-111):** Alle Live-Belege (`raw/28-10`, `raw/28-11`,
  `raw/28-12`) stammen vom Stand vor den Review-Fixes. Die damalige Kanarien-Welt baute den
  CR-01-Fall (Nachricht im Datei-Raum) nicht, `datei-raum-nachricht` steht in keiner Rohdatei;
  das Provider-Live-Gate (WR-02) lief nie. Code und Unit-Tests der Fixes sind vorhanden und
  grün; kein Plan verlangte den Live-Neulauf als Mitigation selbst. Offen bleiben der
  Live-Neulauf mit `NC_MCP_REQUIRE_LIVE=1` und der erste CI-Lauf nach dem Owner-Push
  (`28-VERIFICATION.md`, `human_verification`). CI läuft gegen NC 34 (`compose.exapp.yml`),
  die Live-Messungen gegen nc35 (Owner-Frage WR-04).
- **H-2 (T-28-30):** Siehe UF-28-02; die registrierte Mitigation ist umgesetzt, der
  benachbarte Lookup-Ausfall ist nicht abgedeckt.
- **H-3 (T-28-12):** Der Freeze prüft die `datei.py:Zeile`-Anker nicht auf Existenz; der Anker
  von `tables_create_row` zeigt auf die falschen Zeilen (Review IN-01, nicht behoben).
- **H-4:** Fünf akzeptierte Risiken (A-28-03, A-28-04, A-28-06, A-28-07, A-28-08) plus der
  Staging-Merker D-28-20 und die zwei D-28-21-Regeln hängen an der Doku in Phase 29. Das Audit
  von Phase 29 muss sie dort nachweisen.
- **H-5 (T-28-40):** Der Plan nannte `""` als Ersatzwert, gebaut ist `None`, weil die App eine
  leere Link-Zelle als `null` liefert (Messung 28-01, Summary 28-05); nur so ist das Paar
  getaggt gegen leer byte-gleich. Stärker als geplant, kein Befund.
- **H-6 (T-28-02, T-28-71):** `nc35-nc` steht nur in der Export-Anleitung im Docstring von
  `tests/integration/topology.py:21-24`; `NC_CONTAINER` kommt aus `NC_MCP_E2E_NEXTCLOUD`
  (`topology.py:54`), `test_exclusion_live.py:84` nutzt es ebenfalls.

---

## Security Audit 2026-09-30

| Kennzahl | Wert |
|----------|------|
| Threats gesamt | 56 (T-28-01 bis T-28-123 aus zwölf Plänen) |
| Closed | 56 |
| Open | 0 |
| Disposition | 47 mitigate, 9 accept, 0 transfer |
| Unregistered Flags | 2 (UF-28-01 WR-02, UF-28-02 IN-02), WARNING |
| Testlauf (Auditor) | 18 Suiten, 403 passed, 0 failed |
| Tool-Budget | `check_tool_budget.py` Exit 0, 17233 von 18000 Bytes |
| Secret-Scan Phasenordner | 0 Treffer für die Werte aus `.env.nc35` und `.env.exapp` |

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-09-30 | 56 | 56 | 0 | gsd-security-auditor |

Prüfspur: Threat-Register aus `28-01-PLAN.md` bis `28-12-PLAN.md`, Threat Flags aus
`28-01-SUMMARY.md` bis `28-12-SUMMARY.md`, `28-CONTEXT.md` (D-28-01 bis D-28-21),
`28-REVIEW.md`, `28-VERIFICATION.md`, `28-LIVE-BEWEIS.md`, `raw/`; Code in
`src/mcp_connector/tools/talk.py`, `chatgpt.py`, `notes.py`, `tables.py`, `files.py`,
`search.py`, `withhold.py`, `server/`; Tests unter `tests/contract/`, `tests/unit/`,
`tests/integration/canary_world.py`, `test_canary.py`, `test_canary_world.py`,
`test_live_questions_28.py`, `test_pair_equality_live.py`, `test_exclusion_live.py`;
`.github/workflows/ci.yml`. Keine Implementierungsdatei verändert.

---

## Sign-Off

- [x] Jeder Threat hat eine Disposition (mitigate / accept / transfer)
- [x] Akzeptierte Risiken im Accepted Risks Log
- [x] `threats_open: 0` bestätigt
- [x] `status: verified` im Frontmatter

**Approval:** verified 2026-09-30
