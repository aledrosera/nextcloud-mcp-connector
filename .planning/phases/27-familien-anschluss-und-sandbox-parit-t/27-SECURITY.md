---
phase: 27
slug: familien-anschluss-und-sandbox-parit-t
status: verified
threats_open: 0
asvs_level: 1
created: 2026-09-28
---

# Phase 27: Security

> Sicherheitsvertrag dieser Phase: Bedrohungsregister, akzeptierte Risiken, Prüfspur.

Gegenstand: der Anschluss aller dateitragenden Werkzeugfamilien an den `kein-ki`-Guard aus
Phase 26 und die Sandbox-Parität für pfadlose Treffer (Findling, comments, Notes). Geprüft
wurde am Code auf `main` 2031403 (Datei:Zeile) und an den Tests, die die jeweilige
Mitigation belegen. Register aus den `<threat_model>`-Blöcken von `27-01-PLAN.md` bis
`27-10-PLAN.md` (63 Einträge), Threat Flags aus allen zehn Summaries (keine neue
Angriffsfläche gemeldet). Der Auditor hat am 28.09. selbst ausgeführt: 14 Unit-Suiten der
Phase plus `tests/contract/` mit 459 passed, 0 failed, 0 skipped
(`test_withhold`, `test_guard_routes`, `test_dav_fileid_paths`, `test_dav_home_entries`,
`test_exclusion`, `test_files_exclusion`, `test_files_upload_exclusion`,
`test_search_exclusion`, `test_fetch_exclusion`, `test_notes_exclusion`,
`test_talk_exclusion`, `test_fetch_message_exclusion`, `test_context_exclusion`,
`test_excerpt_batch`), dazu `scripts/check_tool_budget.py` mit Exit 0 (17233 von 18000
Bytes, 22 Werkzeuge). Integrationstests gegen nc35 wurden nicht erneut gefahren; dafür
gelten die Rohdateien unter `raw/`.

---

## Trust Boundaries

| Grenze | Beschreibung | Was sie überquert |
|--------|--------------|-------------------|
| Nextcloud-DAV-Antwort zu Pfadnormalisierung | hrefs aus REPORT, PROPFIND, SEARCH | unvertraute Pfade; Fehlnormalisierung verschiebt die Teilbaumgrenze |
| Modell zu Werkzeugen | Pfade, Offsets, fileids, Note-Ids, Talk-Tokens, Suchworte | mögliche Orakel-Abfragen |
| Suchprovider (auch Findling) zu unified_search | Einträge mit fileId, Pfad, subline, Ausschnitt | fremde Daten, teils ohne Pfad |
| Notes-App und Talk-API zu Antwort | 404-Detailtexte, messageParameters, Raumnamen | Dateinamen und Existenzsignale |
| Werkzeug zu Modell | Fehlertexte, Zähler (`count`, `skipped`, `total`), `truncated`, `degraded` | jede Abweichung kann Existenz verraten |
| Tool-Aufruf zu nächstem Tool-Aufruf | getaggte Menge, aufgelöste Einträge, Notizpfade | darf keine Antwort überleben (E3) |
| Test-Harness zu nc35 und Messprotokolle zu Repo | occ-Tags, Testdaten, Rohdateien | Testdaten und Credentials |

---

## Threat Register

| Threat ID | Kategorie | Komponente | Disposition | Mitigation und Beleg | Status |
|-----------|-----------|------------|-------------|----------------------|--------|
| T-27-01 | Tampering | `dav._home_path_of` | mitigate | Segmentweises `unquote`, decodiertes `/` oder `\x00` ergibt `None` (`src/mcp_connector/nextcloud/clients/dav.py:744-746`). Tests `tests/unit/test_dav_home_entries.py:105`, `:119` | closed |
| T-27-02 | Tampering | `dav._plain_path` | mitigate | `"//" in path` wird abgelehnt (`dav.py:724-725`); dieselbe Prüfung über `in_files_root` (`dav.py:711-713`) in `parse_entries` (`:673`) und `entries_of_fileids` (`:565`). Test `test_dav_home_entries.py:133` | closed |
| T-27-03 | Information Disclosure | `dav._check`, `_check_write`, `_check_chunk_response` | mitigate | Eine Fabrik je Satz: `not_found` (`dav.py:58-69`), `parent_missing` (`:72-84`); genutzt in `_check` (`:1018`), `_check_write` (`:965`), `_check_chunk_response` (`:907`) und von allen Ausschlusspfaden (`tools/files.py:233`, `:725`, `:750`, `:771`, `tools/notes.py:280`). Tests `tests/unit/test_dav_fileid_paths.py:82-115` | closed |
| T-27-04 | Tampering | `dav.paths_of_fileids` | mitigate | `_DIGITS.fullmatch` vor jedem Request (`dav.py:476-478`), Body nur per lxml (`:395-432`), `FILEID_BLOCK = 50` (`:52`, `:484`), Scope `search_scope(creds)` (`:483`). Tests `test_dav_fileid_paths.py:197` (120 Ids = 3 SEARCH), `:218` (Nicht-Ziffer ohne Request), `:231` (außerhalb der Root fehlt) | closed |
| T-27-05 | Information Disclosure | `withhold.unavailable_error` | mitigate | Funktion ohne Argument, konstante Nachricht `EXCLUSION_UNAVAILABLE` ohne Pfad/Id, `reason=REASON_GUARD_TRIPPED` (`src/mcp_connector/tools/withhold.py:36-59`). Tests `tests/unit/test_withhold.py:21`, `:35` | closed |
| T-27-06 | Information Disclosure | `NcClients.exclusion` | mitigate | `field(default_factory=ExclusionGuard)` (`src/mcp_connector/nextcloud/__init__.py:29`). Test `tests/unit/test_exclusion.py:392`; Contract-Gate `tests/contract/test_no_destructive_calls.py:644` (drei dokumentierte Caches, `:289`) grün | closed |
| T-27-07 | Elevation of Privilege | `guard_routes.patch_untagged` | accept | Siehe A-27-01. Grep `^from tests|^import tests` in `src/` ohne Treffer; Helfer nur in `tests/unit/guard_routes.py:112` | closed |
| T-27-10 | Information Disclosure | `files.read`/`download` | mitigate | `_visible_stat`: Guard parallel zu stat, `unverifiable` vor allem, Ausschluss direkt nach stat mit `dav.not_found` (`tools/files.py:759-772`), vor den Formprüfungen in `read` (`:352-372`) und `download` (`:436`). Tests `tests/unit/test_files_exclusion.py:132`, `:155`, `:176`, `:194`, `:210` | closed |
| T-27-11 | Information Disclosure | `files.list_dir`/`search` Zähler | mitigate | Filter vor Sortierung und Fenster (`files.py:242-253`); Suche über `_visible_hits` mit Nachladen (`:262-292`), `count`/`truncated`/`next` aus gefilterter Liste (`:167-183`). Tests `test_files_exclusion.py:315`, `:333`, `:459`, `:479`, `:517` | closed |
| T-27-12 | Information Disclosure | `files.upload`/`upload_binary` | mitigate | `_writable` vor jedem Schreib-Request (`files.py:528`, `:650`, `:666`, `:668`, `:691`), `dav.parent_missing` aus derselben Fabrik (`:724-725`). Tests `tests/unit/test_files_upload_exclusion.py:115`, `:134`, `:188` | closed |
| T-27-13 | Elevation of Privilege | Upload bei nicht prüfbar | mitigate | `unverifiable` ergibt `withhold.unavailable_error()`, kein Schreib-Request (`files.py:721-723`). Test `test_files_upload_exclusion.py:226` | closed |
| T-27-14 | Information Disclosure | unverifiable-Antworten | mitigate | PROPFIND/stat-Ergebnis wird bei `unverifiable` nicht gelesen (`files.py:219-227`, `:154-162`, `:766-767`). Tests `test_files_exclusion.py:236`, `:387`, `:532` | closed |
| T-27-15 | Information Disclosure | Zeitunterschied getaggt vs. fehlend | accept | Siehe A-27-02. Gleiche Request-Folge belegt: stat und Guard immer parallel (`files.py:759-763`), Liste (`:212-216`) | closed |
| T-27-16 | Information Disclosure | Upload-Grenzfall direkt getaggte Datei | accept | Siehe A-27-03. Restorakel im Docstring benannt (`files.py:706-714`) | closed |
| T-27-20 | Information Disclosure | unified_search, pfadlose Treffer | mitigate | `withhold.file_refs` providerunabhängig (`withhold.py:85-110`), Einreihen in `_screen` (`tools/search.py:297-313`), Auflösung über `dav.paths_of_fileids` im Sandbox-Scope (`search.py:317-328`), Entscheid in `_settle` (`:331-362`). Tests `tests/unit/test_search_exclusion.py:182`, `:221` | closed |
| T-27-21 | Information Disclosure | `skipped`/`count` als Zähler | mitigate | Tag-Drops ohne Zähler (`search.py:359-360`), nur Sandbox- und Unbrauchbar-Drops zählen (`:295`, `:306`, `:309`, `:356`). Test `test_search_exclusion.py:280` | closed |
| T-27-22 | Information Disclosure | systemtags-Provider | mitigate | Datei-Einträge laufen durch den Filter, Tag-Einträge ohne fileId sind nicht dateitragend (`withhold.py:103-105`, `search.py:298-300`). Test `test_search_exclusion.py:340` | closed |
| T-27-23 | Information Disclosure | talk-message-Provider subline | mitigate | Live-Probe vor dem Bau: `KLASSE=kein-leak`, `UNTERSCHEIDUNG=keine` (`raw/27-03-provider-probe.txt:8-9`); Klassifikation mit Probe-Verweis (`search.py:81-90`, `:298`). Hinweis H-3 | closed |
| T-27-24 | Information Disclosure | `fetch(file)` mit alter Id | mitigate | Guard vor Auswertung des Lookups, `excludes(fileid)` vor `entry` (`tools/chatgpt.py:330-342`), `_no_file` für alle drei Fälle (`:372-385`), `unavailable_error` bei nicht prüfbar (`:332-333`). Tests `tests/unit/test_fetch_exclusion.py:107`, `:130`, `:142` | closed |
| T-27-25 | Information Disclosure | Provider-cursors | accept | Siehe A-27-04. `cursors` werden roh aus der Provider-Antwort übernommen (`search.py:155-157`), nicht aus gefilterter Zahl | closed |
| T-27-26 | Denial of Service | Guard im 15-s-Provider-Timeout | mitigate | Guard als erstes `gather`-Mitglied außerhalb von `_ask` mit `asyncio.timeout` (`search.py:125-131`, `:248-250`). Test `test_search_exclusion.py:455` | closed |
| T-27-27 | Information Disclosure | Fehler der fileid-Auflösung | mitigate | `_resolve` fängt `ToolError`, `httpx.HTTPError`, `ValueError` und meldet `lookup_failed` (`search.py:325-328`); betroffene Einträge zurückgehalten (`:353-354`), ein `degraded`-Eintrag (`:172-173`). Test `test_search_exclusion.py:395` | closed |
| T-27-28 | Tampering | Probe-Harness schreibt auf nc35 | accept | Siehe A-27-05. `src/` ohne `tag:files:add` (Grep ohne Treffer) | closed |
| T-27-30 | Information Disclosure | `notes.read` (fileid-Orakel) | mitigate | `_note_not_found` für Ausschluss, Notes-404/998 ohne Fremdtext, Sandbox (`tools/notes.py:190-194`, `:309-320`, `:359-368`). Tests `tests/unit/test_notes_exclusion.py:303`, `:328` | closed |
| T-27-31 | Information Disclosure | `notes.search` | mitigate | Sandbox-Drop gezählt (`notes.py:135-138`), Tag-Drop lautlos (`:139-141`), `unverifiable` und Lookup-Fehler ergeben `_withheld_search` (`:117-128`). Tests `test_notes_exclusion.py:173`, `:191`, `:208`, `:227`, `:248` | closed |
| T-27-32 | Elevation of Privilege | Notes außerhalb `NC_MCP_FILES_ROOT` | mitigate | `paths_of_fileids` bei `needs_paths` (Root ungleich `/` oder Ordner getaggt, `withhold.py:113-119`) in search (`notes.py:121-125`) und read (`:197-198`, `:363`); create prüft `dav.in_files_root(folder)` (`:271-278`). Tests `test_notes_exclusion.py:208`, `:376`, `:535` | closed |
| T-27-33 | Information Disclosure | `notes.create` renamed-Kollision | mitigate | Kandidatpfad vor dem POST geprüft, `dav.parent_missing(candidate)` (`notes.py:269`, `:279-280`, POST erst `:282`). Tests `test_notes_exclusion.py:471`, `:489` | closed |
| T-27-34 | Elevation of Privilege | `notes.create` bei nicht prüfbar | mitigate | `unavailable_error` bei `unverifiable`, Settings-Fehler oder unbrauchbarem `notesPath`, kein POST (`notes.py:253-261`). Tests `test_notes_exclusion.py:573`, `:590`, `:606` | closed |
| T-27-35 | Information Disclosure | Titel-Sanitisierung der Notes-App | accept | Siehe A-27-06. Grenze im Docstring benannt (`notes.py:234-235`) | closed |
| T-27-40 | Information Disclosure | `talk._resolve` (Platzhalter) | mitigate | `screen.hides(entry)` ergibt `match.group(0)`, derselbe Weg wie unbekannter Platzhalter (`tools/talk.py:783-792`). Tests `tests/unit/test_talk_exclusion.py:168`, `:201` | closed |
| T-27-41 | Information Disclosure | rohe `messageParameters` | mitigate | Feste Projektionen `_message` (`talk.py:703-720`), `_conversation` (`:590-609`), `_preview` (`:611-625`). Test `test_talk_exclusion.py:188` (`json.dumps` ohne Name und Pfad) | closed |
| T-27-42 | Information Disclosure | Datei-Konversationen | mitigate | Filter vor dem Schnitt und vor `total` (`talk.py:546-562`), `one_room` mit `_unknown_token` (`:850-858`, `:861-866`). Tests `test_talk_exclusion.py:469`, `:500`, `:531` | closed |
| T-27-43 | Information Disclosure | pfadlose Datei-Parameter bei getaggtem Ordner | mitigate | `paths_of_fileids` bei `has_folders`, nicht aufgelöst = verborgen, Lookup-Fehler verbirgt alles (`talk.py:245-262`). Tests `test_talk_exclusion.py:214`, `:229`, `:285` | closed |
| T-27-44 | Denial of Service | Guard im schnellen Talk-Bein | mitigate | Ohne Datei-Bezug kein Guard (`talk.py:228-231`); in `prepare_context` Guard früh als erstes `gather`-Mitglied (`tools/context.py:253-260`). Tests `test_talk_exclusion.py:142`, `:405` | closed |
| T-27-45 | Tampering | `talk_send` in getaggten Datei-Raum | mitigate | `send` ruft `one_room` vor `send_message` (`talk.py:456-462`). Test `test_talk_exclusion.py:550-560` (`post.call_count == 0`) | closed |
| T-27-46 | Information Disclosure | pfadlose Verweise außerhalb `NC_MCP_FILES_ROOT` | accept | Siehe A-27-07. Grenze im Docstring benannt (`talk.py:224-226`) | closed |
| T-27-50 | Denial of Service | Flight-Halter mit kurzem Budget | mitigate | Guard als erstes `gather`-Mitglied ohne Budget (`context.py:248-260`). Test `tests/unit/test_context_exclusion.py:177` | closed |
| T-27-51 | Information Disclosure | Kappungssätze, Digest-Zähler | mitigate | Beine filtern vor dem Zählen (Suche über `unified_search`, `context.py:255`, `:263`). Test `test_context_exclusion.py:418-420` (7 sichtbar, 3 getaggt) | closed |
| T-27-52 | Information Disclosure | Ausschnitte (`fetch`) | mitigate | Ausschnitte nur aus gefilterten `results` (`context.py:767-772`), jeder über `chatgpt.fetch` mit demselben Guard (`:832-843`, `chatgpt.py:321-342`) | closed |
| T-27-53 | Information Disclosure | mehrfache degraded-Einträge | mitigate | `_one_exclusion_entry` faltet auf einen Eintrag ohne Treffer-Quelle (`context.py:883-902`, Aufruf `:283`). Tests `test_context_exclusion.py:234`, `:265` | closed |
| T-27-60 | Tampering | Tag-Schreiben | mitigate | `occ("tag:files:add", ...)` nur im Harness (`tests/integration/test_exclusion_live.py:481`); Grep `tag:files:add` in `src/` ohne Treffer | closed |
| T-27-61 | Information Disclosure | Rohprotokoll | mitigate | Auditor-Prüfung: keine der Werte von `NC_MCP_TEST_APP_PASSWORD`, `..._PASSWORD2`, `NC_MCP_TEST_PASSWORD`, `..._PASSWORD2`, `APP_SECRET` aus `.env.nc35` kommt in irgendeiner Datei des Phasenordners vor (0 Treffer); Musterfunde nur Variablennamen (`raw/27-04-notes-settings.txt:6`, `:9`) | closed |
| T-27-62 | Repudiation | Scheinbeweis durch langlebiges NcClients | mitigate | `Fresh` bricht bei doppelt ausgegebener Guard-Instanz ab (`test_exclusion_live.py:340-358`, Assertion `:349`) | closed |
| T-27-63 | Denial of Service | Rest-Testdaten auf nc35 | mitigate | `finally` mit `_cleanup` und Nachlauf-Assertions (PROPFIND 404, `CLEANUP notes left: 0`, Tag-Zuordnung) (`test_exclusion_live.py:547-555`) | closed |
| T-27-70 | Information Disclosure | Findling-Ausschnitte fileId-only | mitigate | Test mit echtem Findling (`tests/integration/test_findling_sandbox.py:192-291`, Sandbox `skipped>=1` `:256`, Tag ohne Zähleränderung `:278`) im CI-Job (`.github/workflows/ci.yml:121-128`); Code-Kontrolle selbst belegt über T-27-20. Hinweis H-1 | closed |
| T-27-71 | Repudiation | Wanduhr-Messung mit langlebigem NcClients | mitigate | `fresh()` mit neuem `ExclusionGuard` (`tests/integration/test_ctx_bundle.py:186-194`), `RUNS = 5` (`:107`), `LAUF`-Zeilen (`:707`); Rohdatei `raw/27-08-prepare-context.txt` (28 LAUF-Zeilen) | closed |
| T-27-72 | Information Disclosure | Rohdateien im Repo | mitigate | `test_no_measured_line_carries_the_app_secret` vorhanden (`test_ctx_bundle.py:1125`); Wertprüfung wie T-27-61 ohne Treffer | closed |
| T-27-73 | Denial of Service | Wanduhr über Schwelle | accept | Siehe A-27-08. Owner-Entscheid unter `## Abnahme` (`27-LIVE-BEWEIS.md:323`), Override in `27-VERIFICATION.md:7-11` | closed |
| T-27-90 | Information Disclosure | `context._excerpts`, `chatgpt._fetch_file` | mitigate | Gescheiterter Sammelweg fällt auf Einzelweg (`context.py:836-843`, `chatgpt.py:321-329`). Paritätstests mit `json.dumps(sort_keys=True)` (`tests/unit/test_excerpt_batch.py:261`, `:687`, `:716`, `:621`) | closed |
| T-27-91 | Information Disclosure | `file_entries`, `entries_of_fileids` (E3) | mitigate | Einträge nur in der lokalen Task (`context.py:775-790`), `_settle` bricht ab (`:847-859`), keine Modul-Variable (`chatgpt.py:259-291`, `dav.py:496-538`). Test `test_excerpt_batch.py:819`; Contract-Gate `test_no_destructive_calls.py:644` grün | closed |
| T-27-92 | Elevation of Privilege | `files.read(known=...)` | mitigate | `known` nur bei `path == target` (`target = dav.safe_path(path)`, `files.py:351`) und nicht leerer fileid; Guard abgewartet, `unverifiable` und `excludes(path, fileid)` in derselben Reihenfolge (`files.py:744-750`). Tests `test_excerpt_batch.py:518`, `:550` | closed |
| T-27-93 | Information Disclosure | `entries_of_fileids` außerhalb Root | mitigate | `search_scope(creds)` (`dav.py:530`), Href außerhalb Root ergibt `None` (`:564-565`), `None` ergibt `_no_file` (`chatgpt.py:338-339`). Test `test_excerpt_batch.py:700` | closed |
| T-27-94 | Information Disclosure | Zeitverhalten getaggt gegen unbekannt | accept | Siehe A-27-09 | closed |
| T-27-95 | Tampering | Datei verschwindet zwischen Sammel-SEARCH und GET | accept | Siehe A-27-10 | closed |
| T-27-96 | Elevation of Privilege | Wire-Schema (`known`/`resolved`) | mitigate | Parameter keyword-only (`chatgpt.py:207-210`, `files.py:322`); Grep `known|resolved|note_batch|batch|kinds` in `src/mcp_connector/server/` ohne Treffer, kein Commit in `server/` seit 26.09.; `check_tool_budget.py` Exit 0 (Auditor) | closed |
| T-27-97 | Repudiation | Messung (27-09) | mitigate | `RUNS = 5`, frischer Guard, Schwellen unverändert `THRESHOLD = {"short": 0.88, "full": 0.97}` (`test_ctx_bundle.py:107`, `:114`, `:186-194`); Rohdatei `raw/27-09-prepare-context.txt` (30 LAUF-Zeilen); Owner-Checkpoint `27-LIVE-BEWEIS.md:323` | closed |
| T-27-100 | Information Disclosure | `notes._check_note_path` mit batch | mitigate | Gleicher Entscheid `path is None or scope.excludes(...)` ergibt `_note_not_found` in beiden Wegen (`notes.py:356-368`), Fehlen oder Fehlschlag des Batch geht Einzelweg (`:351-362`). Tests `test_excerpt_batch.py:937`, `:966`, `:1157`, `:1188` | closed |
| T-27-101 | Information Disclosure | Notizpfad in Antwortfeld | mitigate | Pfad nur lokal in `_check_note_path` (`notes.py:358-360`), Antwort nur aus `get_note` (`:200-210`). Test `test_excerpt_batch.py:1071` | closed |
| T-27-102 | Information Disclosure | Sammelauflösung über den Aufruf hinaus | mitigate | Wie T-27-91 (`context.py:775-790`, `:847-859`). Test `test_excerpt_batch.py:1083`; Contract-Gate grün | closed |
| T-27-103 | Elevation of Privilege | Guard-Reihenfolge in `notes.read` | mitigate | `unverifiable` und `excludes(fileid)` vor jedem Warten auf batch (`notes.py:188-191` vor `:197-198`). Tests `test_excerpt_batch.py:1027`, `:1206` | closed |
| T-27-104 | Information Disclosure | Zeitverhalten Notizen | accept | Siehe A-27-11 | closed |
| T-27-105 | Elevation of Privilege | Wire-Schema (`batch`/`note_batch`/`kinds`) | mitigate | Keyword-only (`notes.py:162-163`, `chatgpt.py:210`, `:262-263`); `server/` ohne Treffer und ohne Commit seit 26.09.; `check_tool_budget.py` Exit 0 | closed |
| T-27-106 | Repudiation | Messung (27-10) | mitigate | Wie T-27-97; Rohdateien `raw/27-10-prepare-context.txt` (86 LAUF-Zeilen), `raw/27-10-prepare-context-2026-09-28.txt` (34 LAUF-Zeilen, Kontrollen am selben Host); Abnahme `27-LIVE-BEWEIS.md:323` | closed |

*Status: open · closed*
*Disposition: mitigate (Umsetzung nötig) · accept (dokumentiertes Risiko) · transfer (Dritte)*

Unregistered Flags: keine. Alle zehn Summaries melden unter `## Threat Flags` "Keine neue
Angriffsfläche" und verweisen nur auf registrierte Ids.

---

## Accepted Risks Log

| Risk ID | Threat Ref | Begründung | Akzeptiert von | Datum |
|---------|------------|------------|----------------|-------|
| A-27-01 | T-27-07 | `patch_untagged` existiert nur in `tests/unit/guard_routes.py`; `src/` importiert `tests` nie, die echten Zustände prüfen die `*_exclusion`-Testmodule | Plan 27-01 (Owner-Planfreigabe) | 2026-09-27 |
| A-27-02 | T-27-15 | Restzeitkanal getaggt gegen fehlend LOW: gleiche Request-Folge, Guard parallel; Doku in Phase 29 | Plan 27-02 | 2026-09-27 |
| A-27-03 | T-27-16 | Restorakel "sichtbarer Elternordner plus Abweisung" ohne Schreiben nicht vermeidbar, gleich stark wie jede Abweisung; Doku in Phase 29 | Plan 27-02 | 2026-09-27 |
| A-27-04 | T-27-25 | Provider-cursors stammen aus Offset plus Limit der Anfrage, nicht aus der gefilterten Zahl; Restrisiko LOW, Kanarientest in Phase 28 | Plan 27-03 | 2026-09-27 |
| A-27-05 | T-27-28 | Probe-Harness schreibt nur auf die Testinstanz nc35, eigene Probe-Datei, Aufräumen im `finally`; `src/` schreibt keine Tags | Plan 27-03 | 2026-09-27 |
| A-27-06 | T-27-35 | Notes sanitisiert den Titel, Kandidatpfad kann vom echten Dateinamen abweichen; Restorakel LOW, Merker Phase 29 | Plan 27-04 | 2026-09-27 |
| A-27-07 | T-27-46 | Talk hat keine eigene Sandbox für Namen; nur bei `has_folders` und Root ungleich `/` relevant, Merker Phase 29 | Plan 27-05 | 2026-09-27 |
| A-27-08 | T-27-73 | Kein automatisches Wanduhr-Gate (Messmaschine); Owner entschied am 28.09.2026 "ok weiter" auf Vorlage (a) mit Begründung, Schwellen unverändert | Owner (street1983nk) | 2026-09-28 |
| A-27-09 | T-27-94 | Getaggt und unbekannt kosten gleich viel (Einzelweg eine SEARCH, Sammelweg keine eigene, kein GET); kein neues Unterscheidungsmerkmal | Plan 27-09 | 2026-09-27 |
| A-27-10 | T-27-95 | GET übersetzt 404 über denselben `_check`; das Rennfenster bestand vorher zwischen stat und GET genauso und sagt nichts über das Tag | Plan 27-09 | 2026-09-27 |
| A-27-11 | T-27-104 | Getaggte und ungetaggte Notizen warten auf dieselbe tag-unabhängige Sammel-SEARCH; direkt getaggte antworten wie vorher ohne Pfad-SEARCH | Plan 27-10 | 2026-09-27 |

*Akzeptierte Risiken tauchen in späteren Audits nicht erneut auf.*

---

## Hinweise (keine offenen Threats)

- **H-1 (T-27-70, SBX-01):** Test und CI-Schritt sind vorhanden und verdrahtet, der Lauf gegen einen echten Findling steht aus: `main` ist seit dem 26.09. nicht gepusht, der Schritt lief nie (`27-VERIFICATION.md:20-23`). Der Test kann in CI auch mit `pytest.skip` enden (`test_findling_sandbox.py:115`, `:208`, `:213`), ein Skip wäre kein Nachweis. Die Filterlogik selbst ist über T-27-20 und den strukturgleichen comments-Fall belegt. Gleichzeitig steht **SBX-01 in `.planning/REQUIREMENTS.md:30` und `:74` bereits auf Complete**, obwohl die Verifikation den Punkt als `NEEDS HUMAN` führt (`27-VERIFICATION.md:109`). Empfehlung: SBX-01 erst nach grünem, nicht übersprungenem CI-Schritt als Complete führen oder den Vorbehalt in REQUIREMENTS.md vermerken.
- **H-2 (A-27-02, A-27-03, A-27-06, A-27-07):** Vier akzeptierte Risiken hängen an einer Dokumentation in Phase 29. Das Audit von Phase 29 muss prüfen, dass diese Grenzen in der Doku stehen.
- **H-3 (T-27-23):** Die Einstufung der Talk-Message-Provider als nicht dateitragend stützt sich auf eine Probe mit NC 35.0.0 und spreed 25.0.0. Ändert eine spätere spreed-Version das Suchverhalten, muss die Probe wiederholt und `_FILE_SHARE_PROVIDERS` fail-closed umgestellt werden (so im Code-Kommentar `search.py:88-89` festgehalten).
- **H-4 (A-27-04):** Die Prüfung der Provider-cursors ist an den Kanarientest in Phase 28 übergeben; dort nachweisen.

---

## Security Audit 2026-09-28

| Kennzahl | Wert |
|----------|------|
| Threats gesamt | 63 (T-27-01 bis T-27-106 aus zehn Plänen) |
| Closed | 63 |
| Open | 0 |
| Disposition | 52 mitigate, 11 accept, 0 transfer |
| Unregistered Flags | 0 |
| Testlauf (Auditor) | 14 Unit-Suiten plus `tests/contract/`, 459 passed, 0 failed |
| Tool-Budget | `check_tool_budget.py` Exit 0, 17233 von 18000 Bytes |
| Secret-Scan Phasenordner | 0 Treffer für die Werte aus `.env.nc35` |

Prüfspur: Threat-Register aus `27-01-PLAN.md` bis `27-10-PLAN.md`, Threat Flags aus
`27-01-SUMMARY.md` bis `27-10-SUMMARY.md`, `27-VERIFICATION.md`, `27-LIVE-BEWEIS.md`,
`raw/`; Code in `src/mcp_connector/nextcloud/clients/dav.py`, `nextcloud/__init__.py`,
`tools/withhold.py`, `tools/files.py`, `tools/search.py`, `tools/chatgpt.py`,
`tools/notes.py`, `tools/talk.py`, `tools/context.py`, `server/`; Tests unter
`tests/unit/`, `tests/contract/`, `tests/integration/test_exclusion_live.py`,
`test_ctx_bundle.py`, `test_findling_sandbox.py`; `.github/workflows/ci.yml`;
`.planning/REQUIREMENTS.md`. Keine Implementierungsdatei verändert.

---

## Sign-Off

- [x] Jeder Threat hat eine Disposition (mitigate / accept / transfer)
- [x] Akzeptierte Risiken im Accepted Risks Log
- [x] `threats_open: 0` bestätigt
- [x] `status: verified` im Frontmatter

**Approval:** verified 2026-09-28
