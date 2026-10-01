# Phase 28: Live-Beweis (Gates und Beweise)

**Datum:** 2026-09-28
**Instanz:** nc35 (Nextcloud 35.0.0 laut `occ status`, spreed 25.0.0, notes 6.1.0, tables 2.3.1, deck 1.19.0, mail 5.12.0, app_api 35.0.0 laut `occ app:list`, beides in raw/28-12-gates.txt), Topologie nc35-nc, nc_app_mcp_connector, nc35-harp, nc35-caddy, nc35-greenmail; Konto alice (kein Admin), zweites Konto bob
**Kommandos:**

Env-Vorspann aller Live-Läufe:

```
set -a && . ./.env.nc35 && set +a && export NC_MCP_E2E_COMPOSE_FILE=compose.nc35.yml NC_MCP_E2E_PROJECT=nc-mcp-nc35 NC_MCP_E2E_NEXTCLOUD=nc35-nc NC_MCP_E2E_HARP=nc35-harp NC_MCP_E2E_CADDY=nc35-caddy NC_MCP_E2E_CONTAINERS=nc35-nc,nc_app_mcp_connector,nc35-harp,nc35-caddy,nc35-greenmail && PYTHONUTF8=1
```

- `<Vorspann> .venv/Scripts/python.exe -m pytest tests/integration/test_live_questions_28.py -m integration -s` (Plan 28-01, Messung A1, B5, B6)
- `<Vorspann> .venv/Scripts/python.exe -m pytest tests/integration/test_canary_world.py -m integration -s` (Plan 28-07, Kanarien-Welt)
- `<Vorspann> .venv/Scripts/python.exe -m pytest tests/integration/test_canary.py -m integration -s` (Plan 28-10, GATE-02)
- `<Vorspann> .venv/Scripts/python.exe -m pytest tests/integration/test_pair_equality_live.py -m integration -s` (Plan 28-11, GATE-03 live)
- `<Vorspann> .venv/Scripts/python.exe -m pytest tests/integration/test_exclusion_live.py -m integration -s` (Plan 28-12, Regression Phase 27)
- `<Vorspann> .venv/Scripts/python.exe -m pytest tests/integration/test_canary.py tests/integration/test_pair_equality_live.py tests/integration/test_canary_world.py tests/integration/test_live_questions_28.py -m integration -q` (Plan 28-12, gemeinsamer Lauf)
- Gate-Lauf (Plan 28-12): `pytest tests/unit tests/contract`, `ruff check .`, `ruff format --check .`, `PYRIGHT_PYTHON_FORCE_VERSION=latest pyright`, `vulture src scripts vulture_whitelist.py`, `python scripts/check_tool_budget.py`, `pytest tests/contract/test_tool_classes.py tests/contract/test_no_destructive_calls.py -rA`

In der Worktree-Isolation lud ein kleiner Python-Lader dieselbe Env-Datei (`. ./.env.nc35` ist dort gesperrt) und setzte dieselben sechs `NC_MCP_E2E_*`-Exporte, `PYTHONUTF8=1` und `PYTHONPATH=<worktree>/src`; statt `uv run` liefen die Binaries der venv des Haupt-Checkouts. Das Kommando in den Rohdateien ist das geplante.

**Rohdateien:** `raw/28-01-live-questions.txt` (Messung vor den Fixes), `raw/28-07-world.txt` (Kanarien-Welt, Aufbau und Aufräumen), `raw/28-10-befund-diagnose.txt` (Kanarienbefund vor D-28-21), `raw/28-10-canary.txt` (Kanarie nach D-28-21, vier Modi), `raw/28-11-pairs-live.txt` (Live-Paare, vier Modi plus Ausnahmen), `raw/28-12-gates.txt` (Gate-Lauf, Testnamen, gemeinsamer Integrationslauf), `raw/28-12-exclusion-live.txt` (Regression der Phase-27-Live-Beweise)

Jede Zahl unten steht wörtlich in einer dieser Dateien.

## Erfolgskriterium 1: Klassifikations-Freeze

| Befund | Kommando | Rohwert | Deutung | Rohdatei |
|---|---|---|---|---|
| Aufteilung | Klassenausdruck aus `tests/contract/tool_classes.py` | `FILE_READERS 12`, `FILE_WRITERS 3`, `UNAFFECTED 7` | 12 liest Dateien / 3 schreibt in Dateifläche / 7 nicht betroffen, zusammen 22 wie die Registry; `tables_browse` ist Leser (D-28-14) | raw/28-12-gates.txt |
| Freeze gegen die laufende Registry | Gate-Lauf `-rA` | `PASSED tests/contract/test_tool_classes.py::test_every_registered_tool_has_exactly_one_class_and_a_reason`; `...::test_the_three_classes_add_up_to_the_frozen_surface` | jedes Werkzeug genau eine Klasse und ein Satz Grund, auch jedes `nicht betroffen` (D-28-03) | raw/28-12-gates.txt |
| Gegenprobe Probe-Werkzeug | Gate-Lauf `-rA` | `PASSED tests/contract/test_tool_classes.py::test_a_probe_tool_without_entry_turns_the_freeze_red` | ein zur Laufzeit registriertes Werkzeug ohne Eintrag (`files_update`, Issue #9) macht das Gate rot und verschwindet danach (D-28-04) | raw/28-12-gates.txt |
| weitere Gegenproben | Gate-Lauf `-rA` | `...::test_an_empty_reason_turns_the_freeze_red`, `...::test_a_tool_in_two_classes_turns_the_freeze_red`, `...::test_a_pair_case_of_an_unaffected_tool_turns_the_freeze_red`, `...::test_readers_are_read_only_and_writers_are_not` | leerer Grund, Doppelklasse und Paarfall für ein nicht betroffenes Werkzeug sind rot | raw/28-12-gates.txt |
| Paarliste | Klassenausdruck | `PAIR_CASES 14`, `NAMED_EXCEPTIONS [('notes_create', 'category')]` | 14 Einzelzugriffe, genau eine benannte Ausnahme (D-28-16) | raw/28-12-gates.txt |

## Erfolgskriterium 2: Kanarie

Beweislauf 28-10 nach dem Fix D-28-21, HEAD f9f8773, je Modus eine eigene Welt mit eigenem Marker; der Marker reist nie als Argument (D-28-06).

| Befund | Kommando | Rohwert | Deutung | Rohdatei |
|---|---|---|---|---|
| Normalbetrieb | test_canary | `KANARIE normal geprüft 22 von 22` | alle 22 Werkzeuge aufgerufen, Marker in keiner Antwort und keinem Fehlertext | raw/28-10-canary.txt |
| Ausfall REPORT 500 | test_canary | `KANARIE ausfall-500 geprüft 22 von 22`; `AUSFALL 500 report-route call_count=24`; `AUSFALL 500 nicht-prüfbar-antworten=23` | der erzwungene Ausfall trifft wirklich den Guard, 23 Antworten nennen `EXCLUSION_UNAVAILABLE` | raw/28-10-canary.txt |
| Ausfall 412 zweimal | test_canary | `KANARIE ausfall-412 geprüft 22 von 22`; `AUSFALL 412 report-route call_count=48`; `AUSFALL 412 nicht-prüfbar-antworten=23` | doppelte Zahl REPORTs: der Automat listet neu und fragt ein zweites Mal (D-25-05) | raw/28-10-canary.txt |
| Ausfall timeout | test_canary | `KANARIE ausfall-timeout geprüft 22 von 22`; `AUSFALL timeout report-route call_count=24`; `AUSFALL timeout nicht-prüfbar-antworten=23` | ja | raw/28-10-canary.txt |
| Scans | Auszählung der Rohdatei | je Modus 40 Zeilen `GATE-02 ...` (eine je Antwortseite) und 39 Zeilen `AUFRUF ...`, 0 Zeilen `: nein` | jede Seite jeder Antwort ist gescannt, auch Folgeseiten | raw/28-10-canary.txt |
| Kontroll-Marker | test_canary, normal | 8 Zeilen `KONTROLLE ... : ja (kontroll-marker gesehen in 1 seite(n))`, etwa `KONTROLLE files_search normal {"query": "kanarie28xfd2e9208"}: ja` | der Scan sieht einen Marker, wenn er da ist: ein leerer Scan wäre kein Beweis | raw/28-10-canary.txt |
| Provider-cursors | test_canary | je Modus `CURSOR provider=circles cursor=25 treffer=0`, `CURSOR provider=files cursor=25 treffer=3` (normal) bzw. `treffer=0` (Ausfall), `CURSOR provider=tables-search-tables cursor=25 treffer=1`, `CURSOR provider=talk-message cursor=25 treffer=0` | die Folgeseiten über Provider-cursors sind geblättert und gescannt: **A-27-04 / T-27-25 eingelöst** | raw/28-10-canary.txt |
| Schreiber | test_canary | je Modus `ABWEISUNG files_upload ...: ja`, `ABWEISUNG notes_create ...: ja`, `ABWEISUNG talk_send ...: ja` (`is_error=[True] gebucht=['-']`) | die drei Schreiber mit getaggtem Ziel weisen ab und schreiben nichts | raw/28-10-canary.txt |
| Aufräumen Kanarie | test_canary | 4 mal `ZUSAMMENFASSUNG cleanup: 16 Zeilen, 16 gelesen ok, 3 Werkzeug-Einträge`, 64 CLEANUP-Zeilen, etwa `CLEANUP tag kein-ki: entfernt`, `CLEANUP tool row 85: 404` | jede Nebenwirkung (Termin, Karte, Zeile) ist gelesen entfernt, nicht angenommen | raw/28-10-canary.txt |
| Aufräumen Welt | test_canary_world | 2 mal `ZUSAMMENFASSUNG 28-07 cleanup: 18 Zeilen, 18 gelesen ok`; `WELT tags getaggte fileids per REPORT: ja` | Welt mit Tables-Link, Kalender-ATTACH, Datei-Raum und Deck-Anhang, getaggt per occ im Container nc35-nc | raw/28-07-world.txt |
| gemeinsamer Lauf 28-12 | vier Phase-28-Integrationsdateien, HEAD 6fd4526 | `14 passed in 210.60s (0:03:30)`; darin erneut `KANARIE normal geprüft 22 von 22` und dieselbe Zeile für ausfall-500, ausfall-412, ausfall-timeout, `AUSFALL 500 report-route call_count=24`, `AUSFALL 412 report-route call_count=48`, `AUSFALL timeout report-route call_count=24`, je `nicht-prüfbar-antworten=23`, 4 mal `ZUSAMMENFASSUNG cleanup: 16 Zeilen, 16 gelesen ok, 3 Werkzeug-Einträge`, 0 Befundzeilen mit Urteil nein | nach allen Fixes der Phase und im Stand nach dem Merge gemeinsam grün; dieselben Zahlen wie im Beweislauf 28-10 | raw/28-12-gates.txt |

**Befund vor dem Fix (D-28-21):** die Kanarie fand gegen nc35 den Dateinamen der getaggten Datei im Titel des Talk-Datei-Raums über den Suchprovider `talk-conversations`, in `unified_search`, `prepare_context` (full und short) und `search`, im Normalbetrieb und im Ausfall timeout (raw/28-10-befund-diagnose.txt). Owner-Entscheid "Gegen Raumliste prüfen (Empfohlen)"; der Fix steht unter "Fixes dieser Phase".

## Erfolgskriterium 3: Paartests

### Unit (gemockter Transport, fünf Guard-Zustände)

| Befund | Kommando | Rohwert | Deutung | Rohdatei |
|---|---|---|---|---|
| Familie files | `pytest tests/unit/test_pair_equality_files.py` | `39 passed in 4.47s` | files_read, files_download, files_list, files_search(folder), fetch(file:), files_upload text und Chunk 1, je in active, 412 einmal, 412 zweimal, Timeout, 5xx; dazu D-28-17 (SEARCH 500/503) | raw/28-12-gates.txt |
| Familie apps | `pytest tests/unit/test_pair_equality_apps.py` | `40 passed in 2.70s` | notes_read, fetch(note:), talk_browse(messages), talk_send, fetch(message:), fetch(table:), notes_create im Ausfall, Pin der Ausnahme | raw/28-12-gates.txt |
| Abdeckung | Testnamen (collect-only) | `test_the_files_family_covers_exactly_its_pair_cases`, `test_the_apps_family_covers_exactly_its_pair_cases`, `test_time_is_not_part_of_the_comparison`, `test_notes_create_is_a_named_residual_oracle` | ein neuer Paarfall oder eine neue Ausnahme ohne eigenen Test macht rot; die Zeit gehört nicht zum Vergleich (D-28-12) | raw/28-12-gates.txt |

Verglichen wird der ganze `CallToolResult` (Text, `structuredContent`, `isError`), nur die angefragte Id ist durch `<ID>` ersetzt (D-28-11).

### Live gegen nc35 (Beweislauf 28-11, HEAD 2a92052)

| Befund | Kommando | Rohwert | Deutung | Rohdatei |
|---|---|---|---|---|
| Normalbetrieb | test_pair_equality_live | `PAARE normal verglichen 13 von 14 (ausnahmen 1)`; etwa `PAAR normal files_read path: gleich`, `PAAR normal talk_send token: gleich`, `PAAR normal fetch file: gleich` | 13 Paare byte-gleich, der 14. Fall ist die benannte Ausnahme | raw/28-11-pairs-live.txt |
| Ausfall 500 | test_pair_equality_live | `PAARE 500 verglichen 14 von 14 (ausnahmen 0)`; `AUSFALL 500 report-route call_count=28` | im Ausfall auch notes_create gleich | raw/28-11-pairs-live.txt |
| Ausfall 412 | test_pair_equality_live | `PAARE 412 verglichen 14 von 14 (ausnahmen 0)`; `AUSFALL 412 report-route call_count=56` | ja | raw/28-11-pairs-live.txt |
| Ausfall timeout | test_pair_equality_live | `PAARE timeout verglichen 14 von 14 (ausnahmen 0)`; `AUSFALL timeout report-route call_count=28` | ja | raw/28-11-pairs-live.txt |
| Gesamt | Auszählung der Rohdatei | 56 PAAR-Zeilen, 51 davon `: gleich`, 4 `fetch table: Zelle leer ja`, 1 `benannte Ausnahme, gemessen als AUSNAHME`; 0 mal `ungleich`, 0 Zeilen `: nein`; 39 AUSFALL-TEXT-Zeilen `ja` | kein Paar ungleich | raw/28-11-pairs-live.txt |
| fetch(table:) | test_pair_equality_live | `PAAR normal fetch table: Zelle leer ja` und in 500, 412, timeout; `GATE-03 fetch normal table: ja (browse-zelle=None fetch-zeile='' name-im-json=False ...)` | die getaggte Link-Zelle antwortet wie eine leere | raw/28-11-pairs-live.txt |
| Aufräumen | test_pair_equality_live | `ZUSAMMENFASSUNG cleanup: 16 Zeilen, 16 gelesen ok` je Modus, `ZUSAMMENFASSUNG cleanup: 15 Zeilen, 15 gelesen ok, 1 Werkzeug-Einträge` im Ausnahmelauf | Staging-Ordner des Binär-Chunks und angelegte Kategorie gelesen entfernt | raw/28-11-pairs-live.txt |

### Benannte Ausnahmen

| Ausnahme | Rohwert | Entscheid | Rohdatei |
|---|---|---|---|
| notes_create in eine Kategorie | `AUSNAHME notes_create category: getaggt=is_error Error executing tool notes_create: The parent folder /Notes/kanarie28x756fdff9-kat of ... does not exist. ... erfunden=erfolg id=note:22721` | D-28-16: benannte, akzeptierte Ausnahme; eine nicht existente Kategorie wird angelegt, eine getaggte abgewiesen. Pin-Test `test_notes_create_is_a_named_residual_oracle`, Doku als Restorakel in Phase 29 | raw/28-11-pairs-live.txt |
| Staging-Ordner nach Chunk 1 in einen erfundenen Ordner | `B6 upload-ordner kanarie28x6736161fe (nc-mcp-<sha256>): PROPFIND 207`; `BEFUND B6 gleich` | D-28-20: kein Orakel (für das Modell unsichtbar, die Antwort ist gleich), Aufräum-Merker für Phase 29 | raw/28-01-live-questions.txt |

B5 (D-28-19) ist keine Ausnahme mehr, sondern gefixt (siehe "Fixes dieser Phase").

## Erfolgskriterium 4: AST-Nadeln

| Befund | Kommando | Rohwert | Deutung | Rohdatei |
|---|---|---|---|---|
| Nadeln mit Beweiszeile | Gate-Lauf `-rA` | `PASSED ...::test_each_systemtags_needle_trips_on_its_route_and_leaves_the_real_module_alone[systemtags-relations-...]`, `[tag:files-...]`, `[/apps/files/api/v1/files-...]` | drei Nadeln, jede trifft ihre Zeile und lässt das echte Modul in Ruhe | raw/28-12-gates.txt |
| Gegenprobe je Nadel | Gate-Lauf `-rA` | `PASSED ...::test_every_systemtags_needle_of_this_phase_has_a_counter_proof` | ohne die Nadel wäre die Beweiszeile nicht rot: jede Nadel ist nötig | raw/28-12-gates.txt |
| alte Datei-Tags | Gate-Lauf `-rA` | `PASSED ...::test_legacy_file_tag_writes_are_caught_by_the_global_proppatch_needle[...<oc:tags>kein-ki</oc:tags...]` und `[...<oc:favorite>1</oc:favori...]` | PROPPATCH auf `oc:tags` und `oc:favorite` fängt die globale Nadel | raw/28-12-gates.txt |
| AST-Prüfung | Gate-Lauf `-rA` | `PASSED ...::test_no_module_writes_on_systemtags`; `...::test_the_systemtags_check_would_notice_a_multiline_write_in_real_code[POST on TAGS_PATH]`, `[PROPPATCH on TAGS_PATH]`, `[delete on a tag]`, `[put on a relation]`; `...::test_the_systemtags_client_only_reads[...]` (2 Fälle) | jeder systemtags-Aufruf in `src/` ist PROPFIND oder REPORT, auch mehrzeilig geschrieben | raw/28-12-gates.txt |
| erlaubte Formen | Gate-Lauf `-rA` | `PASSED ...::test_the_two_forms_the_systemtags_client_really_builds_stay_allowed` | eingefroren: `("PROPFIND", "f'{creds.base_url}{TAGS_PATH}'")` und `("REPORT", "home_url(creds)")` | raw/28-12-gates.txt |
| Gesamtgate | Gate-Lauf `-rA` | `PASSED ...::test_the_production_code_contains_no_destructive_request` | ja | raw/28-12-gates.txt |

Der Connector kann `kein-ki` damit konstruktionsbedingt weder setzen noch entfernen; `tag:files:add` (occ) steht nur im Test-Harness.

## Fixes dieser Phase

| Fix | Entscheid | Datei | Unit-Beleg | Live-Beleg |
|---|---|---|---|---|
| B1 Tables-Link-Zellen | D-28-14, D-28-18 | `src/mcp_connector/tools/tables.py` (`screen_links`), `src/mcp_connector/tools/chatgpt.py` (`fetch(table:)`) | `tests/unit/test_tables_exclusion.py` (Lauf in raw/28-12-gates.txt) | `PAAR <modus> fetch table: Zelle leer ja` in allen vier Modi (raw/28-11-pairs-live.txt); vorher `A1 tables_browse rows` mit Dateinamen samt Marker (raw/28-01-live-questions.txt); dieselbe Messung nach dem Fix: `BEFUND A1 zellform=json-string title_im_draht=ja fileid_im_draht=ja marker_in_tables_browse=nein` (raw/28-12-gates.txt) |
| B2 Talk im Ausfall | D-28-15 | `src/mcp_connector/tools/talk.py` (`one_room`) | `tests/unit/test_talk_exclusion.py`, `tests/unit/test_fetch_message_exclusion.py` | `PAAR 500 talk_send token: gleich` und entsprechend 412/timeout (raw/28-11-pairs-live.txt) |
| B3 Reihenfolge Nachbar-Fehler | D-28-17 | `src/mcp_connector/tools/chatgpt.py` (`_fetch_file`), `src/mcp_connector/tools/notes.py` (`read`) | `tests/unit/test_fetch_exclusion.py`, `tests/unit/test_notes_exclusion.py`, D-28-17-Fälle in `test_pair_equality_files.py` / `test_pair_equality_apps.py` | live nicht eigens erzwungen (der 5xx des Nachbar-Requests ist ein Unit-Fall); maßgeblich ist der Unit-Beleg, live bleiben `PAAR <modus> fetch file: gleich` und `PAAR <modus> notes_read note: gleich` in allen vier Modi (raw/28-11-pairs-live.txt) |
| B5 files_search auf getaggtem Ordner | D-28-19 | `src/mcp_connector/tools/files.py` (`search`) | `tests/unit/test_files_exclusion.py` | `PAAR normal files_search folder: gleich` (raw/28-11-pairs-live.txt); vorher `BEFUND B5 ungleich` (raw/28-01-live-questions.txt); dieselbe Messung nach dem Fix: `BEFUND B5 gleich` (raw/28-12-gates.txt) |
| B7 talk-conversations in der Suche | D-28-21 | `src/mcp_connector/tools/search.py` (`_screen_conversations`), `src/mcp_connector/tools/talk.py` (`room_fileid`) | `tests/unit/test_search_exclusion.py` (sechs neue Fälle) | `KANARIE <modus> geprüft 22 von 22` in allen vier Modi (raw/28-10-canary.txt); vorher der Befund in raw/28-10-befund-diagnose.txt |

Die acht Unit-Dateien der Fixes (`test_tables_exclusion`, `test_search_exclusion`, `test_talk_exclusion`, `test_fetch_exclusion`, `test_notes_exclusion`, `test_files_exclusion`, `test_files_upload_exclusion`, `test_fetch_message_exclusion`) laufen im Gate-Lauf gemeinsam mit `184 passed in 7.26s` (raw/28-12-gates.txt).

B6 (erster Binär-Chunk, D-28-20) brauchte keinen Fix: `BEFUND B6 gleich`, `BEFUND B6-text gleich` (raw/28-01-live-questions.txt).

**Zwei konservative Regeln des Ausführenden zu D-28-21 (bei der Abnahme vom Owner bestätigt):**

1. **Unbekanntes Token:** ein `talk-conversations`-Treffer, dessen Token nicht in der Gesprächsliste des Kontos steht, bekommt die Id `-`, die keine Datei trägt, und wird zurückgehalten, sobald irgendetwas getaggt ist (fail-closed wie `room_fileid`). Ohne jeden Tag (`untagged`) bleibt er.
2. **Nicht lesbare Gesprächsliste:** alle `talk-conversations`-Treffer werden zurückgehalten, dazu genau ein degraded-Eintrag unter dem Provider-Namen: `{"provider": "talk-conversations", "reason": "The conversation list could not be read, so conversation hits are withheld."}`. Das ist nicht der Wortlaut `EXCLUSION_UNAVAILABLE`, weil nicht die Ausschlussprüfung, sondern die Talk-Liste ausfiel.

Beide Regeln stehen im Docstring von `_screen_conversations` und in `tests/unit/test_search_exclusion.py`. Der ursprüngliche Owner-Entscheid D-28-21 nannte sie nicht ausdrücklich; bei der Abnahme am 28.09.2026 hat der Owner beide bestätigt ("Beide so lassen (Empfohlen)", siehe "## Abnahme").

## Messung vor den Fixes (28-01)

| Frage | Kommando | Rohwert | Deutung | Rohdatei |
|---|---|---|---|---|
| A1 Link-Zellform | test_live_questions_28 | `A1 rows/simple roh: [["Verweis"],["{\"title\": \"kanarie28x6736161f-mk2122...txt\", \"value\": \"http:\/\/127.0.0.1:8082\/f\/22521\", \"providerId\": \"files\"}"],[null]]` | JSON-String mit Dateiname und `/f/<fileid>`, Schrägstriche PHP-escapt, leere Zelle `null`; Grundlage von D-28-18 | raw/28-01-live-questions.txt |
| B5 files_search mit getaggtem Ordner | test_live_questions_28 | `B5 roh-SEARCH getaggt ...: 207` mit leerem multistatus gegen `B5 roh-SEARCH erfunden ...: 404`; `BEFUND B5 ungleich` | Existenz-Orakel vor dem Fix | raw/28-01-live-questions.txt |
| B6 erster Binär-Chunk | test_live_questions_28 | `BEFUND B6 gleich`, `BEFUND B6-text gleich`, `BEFUND B6-klein gleich` | kein Orakel; die 16-Byte-Probe endet vor dem Guard, deshalb 5 MiB | raw/28-01-live-questions.txt |
| Lauf | test_live_questions_28 | `# pytest: 3 passed in 14.25s (Lauf gegen nc35, NC 35.0.0, HEAD 8e64c7a, ...)` | ja | raw/28-01-live-questions.txt |

## Regression Phase 27

| Befund | Kommando | Rohwert | Deutung | Rohdatei |
|---|---|---|---|---|
| Live-Beweise 27-07 nach allen Fixes | test_exclusion_live | `10 passed in 57.68s`; Abschnitt `# 27-07 live run 2026-09-28 15:24:23 +0200`, 57 Befundzeilen mit Urteil ja, 0 mit Urteil nein | die Phase-27-Beweise bleiben nach B1 bis B7 grün | raw/28-12-exclusion-live.txt |
| Aufräumen | test_exclusion_live | `CLEANUP SC4 shares left: 0, file conversation still listed: False`; `CLEANUP PROPFIND root: 404`; `CLEANUP notes left: 0`; `CLEANUP tag kein-ki listed: 0` | nichts bleibt im Dateibaum; die Papierkorb-Einträge dieses Laufs und des gemeinsamen Laufs (9 Stück) sind danach per WebDAV gelöscht und gelesen: je `DELETE 204, danach PROPFIND 404`, `occ tag:list` = `[]` | raw/28-12-exclusion-live.txt, raw/28-12-gates.txt |
| ein REPORT je Aufruf | test_exclusion_live, SC5 | `# SC5 injected REPORT 500 answered 9 times` | wie in Phase 27 | raw/28-12-exclusion-live.txt |

Geänderte Erwartungen: keine. Kein Fall hielt das alte Verhalten vor D-28-15 oder D-28-17 fest. Die einzige Änderung an `tests/integration/test_exclusion_live.py` ist `CONTAINER = topology.NC_CONTAINER` statt der festen Zeichenkette `nc35-nc` (Harness-Falle aus 27-10: `occ` läuft sonst im falschen Container). `raw/27-07-live.txt` ist nach dem Lauf per `git checkout --` unverändert.

## Gates

| Gate | Rohwert | Rohdatei |
|---|---|---|
| pytest tests/unit tests/contract | `5049 passed, 33 skipped in 275.86s (0:04:35)`, `EXIT=0` | raw/28-12-gates.txt |
| ruff check . | `All checks passed!`, `EXIT=0` | raw/28-12-gates.txt |
| ruff format --check . | `311 files already formatted`, `EXIT=0` | raw/28-12-gates.txt |
| pyright (latest) | `0 errors, 0 warnings, 0 informations`, `EXIT=0` | raw/28-12-gates.txt |
| vulture | `EXIT=0` ohne Befund | raw/28-12-gates.txt |
| check_tool_budget | `tools/list: 17233 bytes, 22 tools, budget 18000`, `EXIT=0`; zu Beginn der Phase (Stand 372db35) ebenfalls `tools/list: 17233 bytes, 22 tools, budget 18000` | raw/28-12-gates.txt |

Zum Budget: Der Plan nennt als Referenz 16412 Bytes vom 2026-09-20. Dieser Wert ist älter als Phase 27; spätestens seit Phase 27 liegt das Budget bei 17233 Bytes (27-02-SUMMARY: "17233/18000 Bytes"). Phase 28 hat es nicht verändert: am Anfang der Phase und heute je 17233 Bytes. Gegen 16412 gemessen ist es gewachsen, aber nicht durch diese Phase.

## Offen

- **CI-Nachweis GATE-02 und GATE-03:** Der Schritt "Canary and pair proofs of the kein-ki exclusion (GATE-02, GATE-03)" ist im Job exapp verdrahtet (`.github/workflows/ci.yml` direkt nach dem SBX-01-Schritt, Plan 28-11). Er läuft erst nach dem Push, und der Push ist Owner-Entscheid. Bis dahin ist GATE-02/GATE-03 nur lokal gegen nc35 belegt.
- **SBX-01 (Findling):** unverändert offen aus Phase 27; der CI-Schritt "Findling hits run through sandbox and exclusion (SBX-01)" läuft ebenfalls erst nach dem Push.

## Merker für Phase 29

- **Timing-Orakel (D-28-12):** ein getaggtes Objekt kostet einen REPORT mehr als ein fehlendes; die Antwortzeit gehört nicht zum Paarvergleich (`test_time_is_not_part_of_the_comparison`). Akzeptiertes Risiko, Doku in Phase 29, keine künstliche Verzögerung.
- **ChatGPT-search ohne degraded (D-28-13):** `search` liefert im Ausfall weniger Treffer, ohne das zu melden; das Schema `{results:[{id,title,url}]}` bleibt. Die Kanarie belegt nur, dass nichts Getaggtes durchkommt. Ein Satz Doku in Phase 29.
- **notes_create Restorakel (D-28-16):** eine nicht existente Kategorie wird angelegt, eine getaggte abgewiesen (gepinnt). Doku als Restorakel gleicher Art wie T-27-16.
- **Staging-Ordner nach dem Upload (D-28-20):** Chunk 1 in einen erfundenen Ordner lässt `uploads/<user>/nc-mcp-<sha256>` liegen; kein Orakel, aber Aufräum-Merker für Backlog/Phase 29.
- **Tables ohne Sandbox (T-28-44):** Tables bekommt wie Talk nur den Tag, keine Sandbox; `NC_MCP_FILES_ROOT` wirkt dort nur über die Pfadauflösung bei getaggtem Ordner. Fremdtext mit `/f/<id>` ohne `providerId: "files"` bleibt unverändert (T-28-43, Research A2).
- **ExApp/HaRP-Kette nicht eigens durch die Kanarie gelaufen:** Kanarie und Live-Paare rufen `Client(mcp)` mit App-Passwort direkt gegen nc35 (Nextcloud-Seite der Topologie), nicht über AppAPI-Impersonation und HaRP. Die ExApp-Kette ist nur durch die bestehenden Phase-27-Beweise und den CI-Job exapp abgedeckt.
- **SBX-01 und der neue Kanarien-/Paar-Schritt in CI:** erst nach dem Push des Owners belegt (siehe "Offen").
- Die zwei vom Owner bestätigten Regeln zu D-28-21 (siehe "Fixes dieser Phase") gehören in die Doku.

## Abnahme

Owner-Entscheid 28.09.2026 am Checkpoint 28-12 zu den zwei Regeln von D-28-21 (wörtlich): "Beide so lassen (Empfohlen)". Das unbekannte Token bleibt zurückgehalten, sobald etwas getaggt ist; eine nicht lesbare Gesprächsliste hält alle `talk-conversations`-Treffer mit genau einem degraded-Eintrag unter dem Provider-Namen zurück. Nachtrag in 28-CONTEXT.md unter D-28-21.

Owner-Entscheid 28.09.2026 zu Phase 28 (wörtlich): "Abnehmen (Empfohlen)".

Die vier Erfolgskriterien sind abgenommen. Offen bleiben wie oben aufgeführt: der CI-Nachweis für GATE-02/GATE-03 und SBX-01, der erst nach dem Push durch den Owner läuft (Abschnitt "Offen"), und die Merker für Phase 29 (D-28-12, D-28-13, D-28-16, D-28-20, T-28-44, ExApp/HaRP-Kette). Phase 28 ist damit zur Verifikation frei.

## Neulauf 2026-10-01 nach Review-Fixes

Human-Verification-Punkt 1 aus 28-VERIFICATION.md: Kanarie, Live-Paare und Provider-Live-Gate nach den Review-Fixes (1f9da6b..ad752c5, c358b40) erneut gegen nc35, HEAD 4a91775, mit `NC_MCP_REQUIRE_LIVE=1` (kein Skip möglich).

Kommando: `<Vorspann> NC_MCP_REQUIRE_LIVE=1 uv run pytest tests/integration/test_canary.py tests/integration/test_pair_equality_live.py tests/integration/test_provider_classes_live.py -m integration -s`

Kanarie und Live-Paare rufen `Client(mcp)` im Testprozess auf, laufen also mit dem Code des Arbeitsbaums; das ExApp-Image im Container nc_app_mcp_connector spielt für diese drei Dateien keine Rolle. Die Tests hängen ihre Zeilen an `raw/28-10-canary.txt` und `raw/28-11-pairs-live.txt` an; die angehängten Zeilen sind in eigene Dateien verschoben, die alten Rohdateien sind unverändert.

**Rohdateien:** `raw/28-neulauf-2026-10-01-pytest.txt` (pytest-Ausgabe mit `-s`), `raw/28-neulauf-2026-10-01-canary.txt` (Kanarie, vier Modi), `raw/28-neulauf-2026-10-01-pairs-live.txt` (Live-Paare, vier Modi plus Ausnahme)

| Befund | Rohwert | Deutung | Rohdatei |
|---|---|---|---|
| Gesamt | `11 passed in 135.70s (0:02:15)` | alle drei Dateien grün | raw/28-neulauf-2026-10-01-pytest.txt |
| Kanarie | `KANARIE normal geprüft 22 von 22`, `KANARIE ausfall-500 geprüft 22 von 22`, `KANARIE ausfall-412 geprüft 22 von 22`, `KANARIE ausfall-timeout geprüft 22 von 22` | alle 22 Werkzeuge in allen vier Modi, Marker in keiner Antwort | raw/28-neulauf-2026-10-01-pytest.txt |
| Ausfälle | `AUSFALL 500 report-route call_count=24`, `AUSFALL 412 report-route call_count=48`, `AUSFALL timeout report-route call_count=24`; je `nicht-prüfbar-antworten=23` | dieselben Zahlen wie im Beweislauf 28-10 | raw/28-neulauf-2026-10-01-canary.txt |
| Scans | 160 Zeilen `GATE-02 ...` (40 je Modus), 156 Zeilen `AUFRUF ...` (39 je Modus), 0 Zeilen `: nein`, 8 Zeilen `KONTROLLE ...: ja`, 12 Zeilen `ABWEISUNG ...: ja` | jede Seite gescannt, Kontroll-Marker gesehen, drei Schreiber je Modus abgewiesen | raw/28-neulauf-2026-10-01-canary.txt |
| Datei-Raum-Nachricht (CR-01) | je Modus `CLEANUP talk datei-raum-nachricht 330: 404`, `... 337: 404`, `... 344: 404`, `... 351: 404`; 4 mal `CURSOR provider=talk-message cursor=25 treffer=0` | die Welt baut jetzt eine Nachricht mit dem Stamm im Datei-Raum; kein Scan fand den Marker, die talk-message-Folgeseite liefert keinen Treffer aus dem Datei-Raum; die Nachricht ist gelesen entfernt | raw/28-neulauf-2026-10-01-canary.txt |
| Aufräumen Kanarie | 4 mal `ZUSAMMENFASSUNG cleanup: 17 Zeilen, 17 gelesen ok, 3 Werkzeug-Einträge` | eine Zeile mehr als 28-10 (16), das ist die Datei-Raum-Nachricht | raw/28-neulauf-2026-10-01-canary.txt |
| Live-Paare | `PAARE normal verglichen 13 von 14 (ausnahmen 1)`, `PAARE 500 verglichen 14 von 14 (ausnahmen 0)`, `PAARE 412 verglichen 14 von 14 (ausnahmen 0)`, `PAARE timeout verglichen 14 von 14 (ausnahmen 0)` | wie 28-11; einzige Ausnahme `PAAR normal notes_create category: benannte Ausnahme, gemessen als AUSNAHME` (D-28-16) | raw/28-neulauf-2026-10-01-pytest.txt |
| Paare Auszählung | 56 PAAR-Zeilen, 51 `: gleich`, 4 `fetch table: Zelle leer ja`, 0 mal `ungleich`, 0 Zeilen `: nein`; `AUSFALL 500 report-route call_count=28`, `AUSFALL 412 report-route call_count=56`, `AUSFALL timeout report-route call_count=28` | kein Paar ungleich | raw/28-neulauf-2026-10-01-pairs-live.txt |
| Aufräumen Paare | 4 mal `ZUSAMMENFASSUNG cleanup: 17 Zeilen, 17 gelesen ok, 0 Werkzeug-Einträge`, 1 mal `ZUSAMMENFASSUNG cleanup: 16 Zeilen, 16 gelesen ok, 1 Werkzeug-Einträge` | alles gelesen entfernt | raw/28-neulauf-2026-10-01-pairs-live.txt |
| Provider-Live-Gate (WR-02) | `# providers=['appstore', 'circles', 'comments', 'files', 'mail', 'notes', 'search-deck-card-board', 'search-deck-comment', 'settings', 'systemtags', 'tables-search-tables', 'talk-conversations', 'talk-message']`, Test passed | erster Live-Lauf des Gates: alle 13 Provider der Instanz sind klassifiziert, kein Befund | raw/28-neulauf-2026-10-01-pytest.txt |

Damit ist Human-Verification-Punkt 1 erfüllt. Offen bleibt Punkt 2 (erster CI-Lauf nach dem Owner-Push).
