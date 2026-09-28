# Phase 28: Gates und Beweise - Context

**Gathered:** 2026-09-28
**Status:** Ready for planning (Nachentscheide D-28-14..17 nach Research)

<domain>
## Phase Boundary

Die Aussage "keine Tool-Antwort zeigt Getaggtes" wird zu roten oder grünen Tests statt eines Versprechens. Die Phase liefert vier Beweise (GATE-01, GATE-02, GATE-03, EXCL-07) und baut keine neue Fähigkeit:

1. Klassifikations-Freeze über die aktive Registry (22 Werkzeuge), ein Werkzeug ohne Eintrag macht das Gate rot.
2. Kanarien-Integrationstest über jedes Werkzeug der Registry.
3. Byte-gleiche Paartests "getaggt gegen nicht existent" für jeden Einzelzugriff, auch im Ausfallfall der Prüfung.
4. AST-Nadeln gegen die systemtags-Schreibpfade, jede mit Gegenprobe.

Code in `src/` wird nur angefasst, wenn ein Beweis eine echte Lücke aufdeckt; dann ist der Fix Teil dieser Phase, eine neue Fähigkeit ist es nicht.

</domain>

<decisions>
## Implementation Decisions

### Klassifikations-Freeze (GATE-01)
- **D-28-01:** Drei Klassen statt zwei: `liest Dateien` / `schreibt in Dateifläche` / `nicht betroffen`. Jede Klasse verlangt ihren eigenen Beweis: Kanarie und Paartest für Leser, Abweisung und Paartest für Schreiber, nichts für nicht betroffene. Der Requirement-Text "betroffen oder nicht betroffen" ist damit erfüllt (die zwei betroffenen Klassen zusammen). (Owner 28.09., Empfehlung übernommen)
- **D-28-02:** Die Klassifikation steht als Tabelle im Test (neben `EXPECTED_TOOLS` / `CREATE_TOOLS` in `tests/contract/`), abgeglichen gegen die laufende Registry von `mcp_connector.server.mcp`. Kein Metadatum an den Werkzeugen, kein Eingriff in `src/mcp_connector/server/`. (Owner 28.09., Empfehlung übernommen)
- **D-28-03:** Jeder Eintrag trägt einen Satz Begründung, ausdrücklich auch jedes `nicht betroffen` (Beispiel: warum Deck-Karten, Kalendereinträge, Tables-Zeilen oder Mail nicht auf Nextcloud-Dateien zeigen können, oder warum es harmlos ist). Ein leerer Grund macht das Gate rot. (Owner 28.09., Empfehlung übernommen)
- **D-28-04:** Die Gegenprobe registriert zur Laufzeit im Test ein Probe-Werkzeug ohne Eintrag und erwartet Rot; das deckt auch ein künftiges `files_update` aus dem Community-PR (Issue #9) ab. (Owner 28.09., Empfehlung übernommen)

### Kanarien-Integrationstest (GATE-02)
- **D-28-05:** Alle 22 Werkzeuge werden echt aufgerufen, auch die 6 schreibenden, mit neutralen Argumenten, die auf die getaggte Datei zielen (per Id, Token oder Pfad ohne Marker), auf einer Wegwerf- oder Testinstanz; Nebenwirkungen werden vom Harness aufgeräumt und das Aufräumen wird im Protokoll gelesen, nicht angenommen. Die Zahl der geprüften Werkzeuge steht in der Testausgabe. (Owner 28.09., Empfehlung übernommen)
- **D-28-06:** Der Marker wird nie selbst als Argument übergeben, auch nicht als Suchwort. Taucht er auf, kann er nur aus der Instanz kommen. Suchen laufen über einen Wortteil, der im Datei- und Ordnernamen steckt, der Marker selbst nicht. Damit gibt es keine Echo-Ausnahmen. (Owner 28.09., Empfehlung übernommen)
- **D-28-07:** Zwei Modi: Normalbetrieb und erzwungenes "nicht prüfbar" (REPORT blockiert bzw. Ausfallpfad des Guards). Geprüft werden Antworten UND Fehlertexte in beiden Modi. (Owner 28.09., Empfehlung übernommen)
- **D-28-08:** Läuft im CI-Job exapp und lokal gegen nc35 mit Rohprotokoll im Stil von 27-LIVE-BEWEIS (Kommando + Rohwert). Listen- und Suchwerkzeuge blättern über alle Seiten, einschließlich der Provider-cursors; das schließt den Merker "Provider-cursors Kanarientest" (A-27-04 / T-27-25) aus Phase 27. (Owner 28.09., Empfehlung übernommen)

### Byte-gleiche Paartests (GATE-03)
- **D-28-09:** Einzelzugriff = jedes Werkzeug, das ein Objekt adressiert: `files_read`, `files_download`, `fetch` je Id-Art, `notes_read`, dazu die Schreiber mit Ziel: `files_upload` auf den Pfad, `notes_create`, `talk_send` in den Datei-Raum einer getaggten Datei. Ein Schreiber darf so wenig verraten wie ein Leser. (Owner 28.09., Empfehlung übernommen)
- **D-28-10:** Zwei Ebenen: Unit mit gemocktem Transport (deterministisch, jeder Ausfallpfad: 412, zweiter 412, Timeout, 5xx) und live gegen nc35 und in CI (echte Antworten von Nextcloud). (Owner 28.09., Empfehlung übernommen)
- **D-28-11:** Verglichen wird das ganze Ergebnis: Text, `structuredContent` und `isError`. Nur die angefragte Id selbst wird vor dem Vergleich durch einen Platzhalter ersetzt, weil sie legitim im Fehlertext stehen darf. Alles andere muss byte-gleich sein. (Owner 28.09., Empfehlung übernommen)
- **D-28-12:** Die Antwortzeit gehört NICHT dazu. Das Timing-Orakel (ein getaggtes Objekt kostet einen REPORT mehr als ein fehlendes) wird ein akzeptiertes Risiko mit Doku in Phase 29; keine künstliche Verzögerung. (Owner 28.09., Empfehlung übernommen)

### ChatGPT-search ohne degraded-Feld (Merker aus Phase 27)
- **D-28-13:** Hinnehmen, testen, dokumentieren. Das Schema `{results:[{id,title,url}]}` bleibt unangetastet. Phase 28 beweist im Kanarien- und Paartest nur, dass im Ausfall nichts Getaggtes durchkommt. Dass `search` im Ausfall weniger Treffer liefert, ohne das zu melden, wird ein akzeptiertes Risiko mit einem Satz Doku in Phase 29. (Owner 28.09., Empfehlung übernommen)

### Nachentscheide nach der Research (Owner 28.09., alle Empfehlung übernommen)
- **D-28-14 (B1 Tables):** In Phase 28 fixen. `tables_browse` wird Leser (Aufteilung 12 liest / 3 schreibt / 7 nicht betroffen). Link-Zellen, die auf eine getaggte fileid zeigen (Name plus `/f/<fileid>`), werden wie ein leerer Wert behandelt, auch in `fetch(table:)`; im Ausfall fail-closed mit dem degraded-Idiom der Familie und `withhold.EXCLUSION_UNAVAILABLE`. Das Format der Link-Zelle in `rows/simple` (Research A1) wird vor dem Fix live gemessen.
- **D-28-15 (B2 Talk):** Angleichen. Im Ausfall bekommt jedes Token, das nicht in der Konversationsliste sichtbar ist, denselben Einheitsfehler (`withhold.unavailable_error()`), auch ein erfundenes; gilt für `talk_send`, `talk_browse` auf Nachrichtenebene und `fetch(message:)` (Research B2, `talk.py:847-858`).
- **D-28-16 (B4 notes_create):** Benannte, akzeptierte Ausnahme in der Paarliste: nicht existente Kategorie wird angelegt, getaggte wird abgewiesen. Ein Test hält genau diesen Unterschied fest (Pin, damit er nicht still wächst); Doku als Restorakel in Phase 29, gleicher Art wie T-27-16.
- **D-28-17 (B3 Reihenfolge):** `fetch(file:)` und `notes_read` werten den Fehler des parallelen Requests VOR der Tag-Entscheidung aus, nach dem Muster `_visible_stat`; der Paartest deckt den 5xx-Fall ab.
- Die offenen Live-Fragen der Research (A1 Link-Zellenformat, A3 SEARCH auf fehlendem Scope bzw. B5 `files_search` mit getaggtem `folder`, A4/B6 erster Chunk eines Binär-Uploads) werden im ersten Plan gemessen, bevor Fixes und Paartests darauf bauen; ein Befund, der eine neue Lücke zeigt, geht an den Owner-Checkpoint.

### Nachentscheide nach der Messung 28-01 (Owner 28.09.2026)
Grundlage: `raw/28-01-live-questions.txt` (nc35, NC 35.0.0, 3 passed, Block ZUSAMMENFASSUNG 28-01).
- **D-28-18 (A1 Zellform):** Owner-Wortlaut: "Wie gemessen (Empfohlen)": 28-05 filtert genau das gemessene Format (JSON-String, providerId "files", fileid aus dem value-Ende "/f/<id>", escapte Slashes beachten); getaggt -> Zelle wie null, im Ausfall fail-closed; andere providerIds unberührt. Gemessene Zellform in `rows/simple`: JSON-String `{"title": "<Dateiname>", "value": "<url>/f/<fileid>", "providerId": "files"}` mit PHP-escapten Schrägstrichen (`\/`), eine leere Zelle kommt als `null`.
- **D-28-19 (B5 files_search-Ordner):** Owner-Wortlaut: "Fixen (Empfohlen)": getaggter/ausgeschlossener Ordner in files_search antwortet vorab mit genau dem Fehler des erfundenen Ordners (dav.not_found(search_scope), gleicher Scope-Pfad-Wortlaut); umgesetzt in 28-06. Gemessen: der erfundene Ordner antwortet "File not found: /files/<user>/<Ordner>. Hint: List the parent folder first to get the exact spelling of the path.", der getaggte heute eine leere Trefferliste ohne Fehler.
- **D-28-20 (B6 erster Binär-Chunk):** Owner-Wortlaut: "Kein Befund, Staging als Merker (Empfohlen)": nur Paartest; der liegen gebliebene Staging-Ordner uploads/<user>/nc-mcp-<sha256> ist kein Orakel und wird Aufräum-Merker für Backlog/Phase 29, kein Fix in 28. Gemessen: Chunk 1 (5 MiB) in getaggten und erfundenen Ordner antwortet wortgleich bis auf den Pfad; der Text-Upload ebenso (B6-text gleich).

### Aus früheren Phasen übernommene Entscheide (gelten unverändert, nicht neu verhandeln)
- **D-v1.7-01/02:** Fester Tag-Name `kein-ki`, Groß-/Kleinschreibung egal, Varianten vereinigt; kein Zähler für Zurückgehaltenes.
- **D-25-05:** Fail-closed-Automat (207 / 412 einmal neu auflösen / sonst nicht prüfbar); Capability wird nicht befragt.
- **D-27-01..06:** "Ausgeschlossen = existiert nicht"; Upload-Abweisung byte-gleich zum fehlenden Elternordner; Einzelzugriffe liefern bei "nicht prüfbar" einen einheitlichen ToolError für ALLE Ids; EIN Wortlaut `withhold.EXCLUSION_UNAVAILABLE`; Talk-Platzhalter bleibt roh.

### Claude's Discretion
- **EXCL-07 AST-Nadeln:** Verboten wird jeder Aufruf, der schreibt (PUT, POST, DELETE, PROPPATCH, MOVE, COPY), auf `systemtags-relations` und `systemtags`; erlaubt bleiben PROPFIND und REPORT, die der Guard zum Lesen braucht. Jede Nadel bekommt eine Zeile, die sie treffen muss (Muster `TABLES_ROUTES` / `TALK_ROUTES` in `test_no_destructive_calls.py`), und eine Gegenprobe, die ohne sie rot würde; dazu das Tupel der erlaubten Formen, die `clients/systemtags.py` wirklich baut. `tag:files:add` (occ) bleibt nur im Test-Harness erlaubt, nie in `src/`. Ob auch die alten Datei-Tags (`oc:tags`, Favoriten per PROPPATCH) eine Nadel bekommen, entscheidet der Planer nach Research.
- Exakte Namen der drei Klassen und Form der Tabelle, solange D-28-01..04 erfüllt sind.
- Wie der Ausfallmodus live erzwungen wird (z.B. Proxy-Regel, App kurz aus, falscher Tag-Id-Cache), solange er den echten Ausfallpfad des Guards trifft und das Protokoll ihn belegt.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements und Roadmap
- `.planning/REQUIREMENTS.md` , GATE-01, GATE-02, GATE-03, EXCL-07 (wörtlicher Requirement-Text ist bindend); SBX-01 steht auf Pending bis zum CI-Nachweis.
- `.planning/ROADMAP.md` , Phase-28-Erfolgskriterien 1-4.

### Befunde und Merker aus Phase 27
- `.planning/phases/27-familien-anschluss-und-sandbox-parit-t/27-LIVE-BEWEIS.md` , Abschnitte "Merker für Phase 28" (talk_send und notes_create betroffen, ChatGPT-search ohne degraded, Provider-cursors) und "Merker für Phase 29"; Messbericht-Stil; Harness-Falle nc35 (Abschnitt "Neumessung im ruhigen Fenster (28.09.)").
- `.planning/phases/27-familien-anschluss-und-sandbox-parit-t/27-SECURITY.md` , akzeptierte Risiken A-27-01..11 (A-27-04 cursors wird hier eingelöst).
- `.planning/phases/27-familien-anschluss-und-sandbox-parit-t/27-CONTEXT.md` , D-27-01..06.
- `.planning/phases/27-familien-anschluss-und-sandbox-parit-t/27-VERIFICATION.md` , offener Human-Punkt SBX-01 (CI-Schritt nie gelaufen).

### Bestehende Gates im Code
- `tests/contract/test_tool_surface.py` , `EXPECTED_TOOLS` (22) und `CREATE_TOOLS` (6): Vorlage und Anker für den Freeze (D-28-02).
- `tests/contract/test_no_destructive_calls.py` , AST-Gate mit Nadeln je Familie, Zeilen-je-Nadel-Beweis (`TABLES_ROUTES`, `TALK_ROUTES`, `MAIL_ROUTES`) und Tupel erlaubter Formen: Muster für EXCL-07.
- `scripts/check_tool_budget.py` , Byte-Budget der Registry; darf durch diese Phase nicht wachsen.

### Guard und Werkzeuge
- `src/mcp_connector/nextcloud/exclusion.py` , Guard, Ausfallzustände (Grundlage des erzwungenen "nicht prüfbar").
- `src/mcp_connector/nextcloud/clients/systemtags.py` , die einzigen systemtags-Formen, die der Connector baut (erlaubte Formen für EXCL-07).
- `src/mcp_connector/tools/withhold.py` , `EXCLUSION_UNAVAILABLE`, `unavailable_error()`.
- `src/mcp_connector/tools/chatgpt.py` , search/fetch; `metadata["degraded"]` nur bei fetch (D-28-13).

### Live-Harness
- `tests/integration/test_ctx_bundle.py` , `test_exclusion_live.py`, `test_findling_sandbox.py` , Muster für Tag-Fixture per occ, frischen Guard je Aufruf, Rohprotokoll.
- `tests/integration/topology.py` , NC_MCP_E2E_*-Variablen; für nc35 PFLICHT exportieren, sonst läuft occ im falschen Container.
- `compose.nc35.yml` , nc35-Strecke.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `EXPECTED_TOOLS` / `CREATE_TOOLS` (test_tool_surface.py): Freeze-Muster mit Set-Vergleich (kein Subset), daran hängt die neue Klassentabelle.
- `test_no_destructive_calls.py`: Nadel + Beweiszeile + erlaubte Formen je Familie; EXCL-07 ist eine weitere Familie in derselben Datei.
- `TagFixture` in `tests/integration/test_ctx_bundle.py`: legt Datei und Ordner per WebDAV an, taggt per occ, räumt auf und liest das Aufräumen zurück; Vorlage für die Kanarien-Fixture.
- In-Memory `Client(mcp)`: ruft jedes Werkzeug über die echte Registry, auch für die Paartests auf Unit-Ebene.

### Established Patterns
- Vorläufige Einordnung (vom Planer mit Research zu bestätigen, nicht bindend): liest Dateien = files_search, files_list, files_read, files_download, notes_search, notes_read, unified_search, prepare_context, talk_browse, search, fetch (11); schreibt in Dateifläche = files_upload, notes_create, talk_send (3); nicht betroffen = calendar_list_events, calendar_create_event, deck_browse, deck_create_card, contacts_search, tables_browse, tables_create_row, mail_browse (8). Research muss für jedes `nicht betroffen` klären, ob Anhänge oder Dateiverweise (Deck-Anhänge, Kalender-ATTACH, Tables-Dateispalten, Mail-Anhänge) doch Nextcloud-Dateien zeigen.
- Live-Beweise im Messbericht-Stil (Kommando + Rohwert + Deutung), Rohdateien unter `phases/28-gates-und-beweise/raw/`.
- Unit-Tests: pytest + respx (call_count), gemockte Ausfallpfade.

### Integration Points
- CI-Job exapp (Findling-Schritt SBX-01 als Vorbild): der Kanarientest wird dort als eigener Schritt verdrahtet; er läuft erst beim nächsten Push (Push-Entscheid beim Owner).
- nc35 lokal: `set -a && . ./.env.nc35 && set +a` PLUS NC_MCP_E2E_*-Exporte und `PYTHONUTF8=1`.

</code_context>

<specifics>
## Specific Ideas

- Die durchgängige Story bleibt "ausgeschlossen = existiert nicht"; die Paartests sind ihr Beweis.
- Ein Marker, der nie als Argument reist, macht jeden Treffer in einer Antwort zu einem echten Leck (keine Echo-Ausnahme).
- Die Zahl der geprüften Werkzeuge in der Testausgabe muss gleich `len(EXPECTED_TOOLS)` sein, nicht nur "alle grün".

</specifics>

<deferred>
## Deferred Ideas

- Timing-Orakel (ein REPORT mehr für Getaggtes): akzeptiertes Risiko, Doku in Phase 29 (D-28-12).
- ChatGPT-search ohne Ausfallhinweis: akzeptiertes Risiko, ein Satz Doku in Phase 29 (D-28-13).
- Statischer Hinweis auf der Expired-Seite (Issue #11, UX-Merker): Backlog / Phase-29-Kandidat, nicht Teil von 28.
- Device Grant (RFC 8628): Feature-Idee, nur auf Owner-Wunsch.

</deferred>

---

*Phase: 28-gates-und-beweise*
*Context gathered: 2026-09-28*
