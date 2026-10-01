# Phase 28: Gates und Beweise - Research

**Researched:** 2026-09-28
**Domain:** Test-Gates (pytest, AST, In-Memory-MCP-Client, respx, Live-Harness gegen Nextcloud 35) für den `kein-ki`-Ausschluss
**Confidence:** HIGH für Code-Befunde (alles mit Datei:Zeile belegt), MEDIUM für drei Live-Verhaltensfragen, die erst der Paartest entscheidet

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Klassifikations-Freeze (GATE-01)
- **D-28-01:** Drei Klassen statt zwei: `liest Dateien` / `schreibt in Dateifläche` / `nicht betroffen`. Jede Klasse verlangt ihren eigenen Beweis: Kanarie und Paartest für Leser, Abweisung und Paartest für Schreiber, nichts für nicht betroffene. Der Requirement-Text "betroffen oder nicht betroffen" ist damit erfüllt (die zwei betroffenen Klassen zusammen). (Owner 28.09., Empfehlung übernommen)
- **D-28-02:** Die Klassifikation steht als Tabelle im Test (neben `EXPECTED_TOOLS` / `CREATE_TOOLS` in `tests/contract/`), abgeglichen gegen die laufende Registry von `mcp_connector.server.mcp`. Kein Metadatum an den Werkzeugen, kein Eingriff in `src/mcp_connector/server/`. (Owner 28.09., Empfehlung übernommen)
- **D-28-03:** Jeder Eintrag trägt einen Satz Begründung, ausdrücklich auch jedes `nicht betroffen` (Beispiel: warum Deck-Karten, Kalendereinträge, Tables-Zeilen oder Mail nicht auf Nextcloud-Dateien zeigen können, oder warum es harmlos ist). Ein leerer Grund macht das Gate rot. (Owner 28.09., Empfehlung übernommen)
- **D-28-04:** Die Gegenprobe registriert zur Laufzeit im Test ein Probe-Werkzeug ohne Eintrag und erwartet Rot; das deckt auch ein künftiges `files_update` aus dem Community-PR (Issue #9) ab. (Owner 28.09., Empfehlung übernommen)

#### Kanarien-Integrationstest (GATE-02)
- **D-28-05:** Alle 22 Werkzeuge werden echt aufgerufen, auch die 6 schreibenden, mit neutralen Argumenten, die auf die getaggte Datei zielen (per Id, Token oder Pfad ohne Marker), auf einer Wegwerf- oder Testinstanz; Nebenwirkungen werden vom Harness aufgeräumt und das Aufräumen wird im Protokoll gelesen, nicht angenommen. Die Zahl der geprüften Werkzeuge steht in der Testausgabe. (Owner 28.09., Empfehlung übernommen)
- **D-28-06:** Der Marker wird nie selbst als Argument übergeben, auch nicht als Suchwort. Taucht er auf, kann er nur aus der Instanz kommen. Suchen laufen über einen Wortteil, der im Datei- und Ordnernamen steckt, der Marker selbst nicht. Damit gibt es keine Echo-Ausnahmen. (Owner 28.09., Empfehlung übernommen)
- **D-28-07:** Zwei Modi: Normalbetrieb und erzwungenes "nicht prüfbar" (REPORT blockiert bzw. Ausfallpfad des Guards). Geprüft werden Antworten UND Fehlertexte in beiden Modi. (Owner 28.09., Empfehlung übernommen)
- **D-28-08:** Läuft im CI-Job exapp und lokal gegen nc35 mit Rohprotokoll im Stil von 27-LIVE-BEWEIS (Kommando + Rohwert). Listen- und Suchwerkzeuge blättern über alle Seiten, einschließlich der Provider-cursors; das schließt den Merker "Provider-cursors Kanarientest" (A-27-04 / T-27-25) aus Phase 27. (Owner 28.09., Empfehlung übernommen)

#### Byte-gleiche Paartests (GATE-03)
- **D-28-09:** Einzelzugriff = jedes Werkzeug, das ein Objekt adressiert: `files_read`, `files_download`, `fetch` je Id-Art, `notes_read`, dazu die Schreiber mit Ziel: `files_upload` auf den Pfad, `notes_create`, `talk_send` in den Datei-Raum einer getaggten Datei. Ein Schreiber darf so wenig verraten wie ein Leser. (Owner 28.09., Empfehlung übernommen)
- **D-28-10:** Zwei Ebenen: Unit mit gemocktem Transport (deterministisch, jeder Ausfallpfad: 412, zweiter 412, Timeout, 5xx) und live gegen nc35 und in CI (echte Antworten von Nextcloud). (Owner 28.09., Empfehlung übernommen)
- **D-28-11:** Verglichen wird das ganze Ergebnis: Text, `structuredContent` und `isError`. Nur die angefragte Id selbst wird vor dem Vergleich durch einen Platzhalter ersetzt, weil sie legitim im Fehlertext stehen darf. Alles andere muss byte-gleich sein. (Owner 28.09., Empfehlung übernommen)
- **D-28-12:** Die Antwortzeit gehört NICHT dazu. Das Timing-Orakel (ein getaggtes Objekt kostet einen REPORT mehr als ein fehlendes) wird ein akzeptiertes Risiko mit Doku in Phase 29; keine künstliche Verzögerung. (Owner 28.09., Empfehlung übernommen)

#### ChatGPT-search ohne degraded-Feld (Merker aus Phase 27)
- **D-28-13:** Hinnehmen, testen, dokumentieren. Das Schema `{results:[{id,title,url}]}` bleibt unangetastet. Phase 28 beweist im Kanarien- und Paartest nur, dass im Ausfall nichts Getaggtes durchkommt. Dass `search` im Ausfall weniger Treffer liefert, ohne das zu melden, wird ein akzeptiertes Risiko mit einem Satz Doku in Phase 29. (Owner 28.09., Empfehlung übernommen)

#### Aus früheren Phasen übernommene Entscheide (gelten unverändert, nicht neu verhandeln)
- **D-v1.7-01/02:** Fester Tag-Name `kein-ki`, Groß-/Kleinschreibung egal, Varianten vereinigt; kein Zähler für Zurückgehaltenes.
- **D-25-05:** Fail-closed-Automat (207 / 412 einmal neu auflösen / sonst nicht prüfbar); Capability wird nicht befragt.
- **D-27-01..06:** "Ausgeschlossen = existiert nicht"; Upload-Abweisung byte-gleich zum fehlenden Elternordner; Einzelzugriffe liefern bei "nicht prüfbar" einen einheitlichen ToolError für ALLE Ids; EIN Wortlaut `withhold.EXCLUSION_UNAVAILABLE`; Talk-Platzhalter bleibt roh.

### Claude's Discretion
- **EXCL-07 AST-Nadeln:** Verboten wird jeder Aufruf, der schreibt (PUT, POST, DELETE, PROPPATCH, MOVE, COPY), auf `systemtags-relations` und `systemtags`; erlaubt bleiben PROPFIND und REPORT, die der Guard zum Lesen braucht. Jede Nadel bekommt eine Zeile, die sie treffen muss (Muster `TABLES_ROUTES` / `TALK_ROUTES` in `test_no_destructive_calls.py`), und eine Gegenprobe, die ohne sie rot würde; dazu das Tupel der erlaubten Formen, die `clients/systemtags.py` wirklich baut. `tag:files:add` (occ) bleibt nur im Test-Harness erlaubt, nie in `src/`. Ob auch die alten Datei-Tags (`oc:tags`, Favoriten per PROPPATCH) eine Nadel bekommen, entscheidet der Planer nach Research.
- Exakte Namen der drei Klassen und Form der Tabelle, solange D-28-01..04 erfüllt sind.
- Wie der Ausfallmodus live erzwungen wird (z.B. Proxy-Regel, App kurz aus, falscher Tag-Id-Cache), solange er den echten Ausfallpfad des Guards trifft und das Protokoll ihn belegt.

### Deferred Ideas (OUT OF SCOPE)
- Timing-Orakel (ein REPORT mehr für Getaggtes): akzeptiertes Risiko, Doku in Phase 29 (D-28-12).
- ChatGPT-search ohne Ausfallhinweis: akzeptiertes Risiko, ein Satz Doku in Phase 29 (D-28-13).
- Statischer Hinweis auf der Expired-Seite (Issue #11, UX-Merker): Backlog / Phase-29-Kandidat, nicht Teil von 28.
- Device Grant (RFC 8628): Feature-Idee, nur auf Owner-Wunsch.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| GATE-01 | Klassifikations-Freeze über die aktive Registry, jedes Tool betroffen oder nicht betroffen, neues Tool ohne Eintrag macht das Gate rot | Abschnitt "Klassifikation je Werkzeug" (22 Urteile mit Beleg), Pattern 1 (Freeze gegen `list_tools()` plus Laufzeit-Probe über `mcp.add_tool`/`mcp.remove_tool`, mcp 2.0.0 `server.py:570-619`) |
| GATE-02 | Kanarien-Integrationstest, Marker in Name und Inhalt, taucht in keiner Antwort und keinem Fehlertext irgendeines Tools auf | Pattern 2 (Topologie der Kanarie, Aufrufplan je Werkzeug, Scan über Text, `structuredContent`, Blob, URI; Ausfallmodus per respx mit `pass_through`), Pitfalls 1 bis 9, Befund B1 (Tables-Link-Zellen) |
| GATE-03 | Byte-gleiche Paartests "getaggt gegen nicht existent" für Einzelzugriffe, auch im Ausfallfall | Pattern 3 (Paarmatrix, Normalisierung, Unit-Harness mit `guard_routes`), Befunde B2 bis B6 (Talk-Ausfall, Lookup-Reihenfolge, notes_create, files_search-Ordner, Chunk-Upload) |
| EXCL-07 | Tag-Schreibpfade stehen als Nadel im AST-Gate, der Connector kann den Tag nie setzen oder entfernen | Pattern 4 (Zeilen-Nadeln plus AST-Methodenprüfung, verifizierte Nextcloud-Schreibformen), Code-Beispiel 4 |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- Python 3.13, `uv` als Toolchain (System-Python defekt): alle Kommandos über `.venv/Scripts/python.exe` bzw. `uv run`.
- Qualitätsgates in jedem Commit grün: `ruff check .` (Regelsatz E, F, I, UP, B, S, SIM, C4, RUF, PT, ASYNC, RET, A, ISC), `ruff format --check .`, pyright (in `pyproject.toml` steht `typeCheckingMode = "standard"` und `include = ["src", "scripts", "tests"]`, also werden auch die neuen Tests typgeprüft), vulture. Lokal pyright mit `PYRIGHT_PYTHON_FORCE_VERSION=latest` wie CI (Memory-Regel 19.09.).
- Offizielles MCP-SDK `mcp>=2.0,<3`, Klasse `MCPServer`; In-Memory `Client(mcp)` ist das vorgesehene Werkzeug für Contract-Tests.
- Security: der MCP sieht nie mehr als der angemeldete Nutzer; keine destruktiven Writes; das AST-Gate `test_no_destructive_calls.py` ist die bestehende Erzwingung.
- Sprache: Code und Identifier Englisch, Projektdokumente Deutsch mit echten Umlauten, keine Gedankenstriche U+2014/U+2013, keine Emojis.
- GSD-Workflow: Änderungen nur über `/gsd:execute-phase`; diese Research ändert nichts an `src/` oder `tests/`.
- Byte-Budget `scripts/check_tool_budget.py` (18000 Bytes, gemessen 16412 am 2026-09-20) darf nicht wachsen: diese Phase fügt kein Werkzeug und keine Beschreibung hinzu.
- Commits für OSS nur als Owner (Memory-Regel 25.08.), fremde PRs (files_update, Issue #9) nicht selbst fertigstellen.

## Summary

Phase 28 baut vier Gates und keine Fähigkeit. Die Werkzeuge dafür liegen alle im Repo: `EXPECTED_TOOLS`/`CREATE_TOOLS` als Freeze-Muster, `test_no_destructive_calls.py` mit Nadeln, Beweiszeilen und erlaubten Formen, `tests/unit/guard_routes.py` für die drei Guard-Zustände per respx, der Live-Harness aus `test_exclusion_live.py` (occ-Tagging, REPORT-500-Injektion mit `pass_through`, Aufräumbeweis) und der In-Memory-`Client(mcp)`, der über `NC_MCP_URL`/`NC_MCP_USER`/`NC_MCP_APP_PASSWORD` jedes Werkzeug durch die echte Registry ruft (`tests/unit/test_chatgpt_search.py:97-102`). mcp 2.0.0 hat `MCPServer.add_tool` und `remove_tool` öffentlich (`.venv/.../mcpserver/server.py:570-619`), damit ist die Probe-Gegenprobe von D-28-04 ohne Eingriff in `src/` machbar. Neue Pakete braucht die Phase nicht.

Die Durchsicht der acht vorläufig "nicht betroffenen" Werkzeuge ergibt sieben saubere Urteile und einen echten Befund: **Tables-Zellen vom Typ text-link speichern beim Verlinken einer Nextcloud-Datei eine Kopie von Dateiname und `/f/<fileid>`** (Tables-Quelle `TextLinkBusiness.php` und `rowTypePartials/TextLinkForm.vue`, der Provider `files` ist dort voreingestellt), und `tables_browse` reicht Zellwerte ungefiltert durch (`tools/tables.py:411-422`, `:524-542`). Eine Tabelle, die auf die Kanarien-Datei verlinkt, würde den Marker heute ausgeben, ebenso `fetch(table:<id>)` (`tools/chatgpt.py:849`). Das ändert die Klasse von `tables_browse` und ist nach der Phasenregel ein Fix in dieser Phase, sobald der Owner den Umfang bestätigt.

Die Paartests werden zwei weitere echte Ungleichheiten aufdecken, die heute schon im Code ablesbar sind: (1) im Ausfall antwortet `talk_one_room` für das Token eines Datei-Raums mit dem Einheitsfehler, für ein erfundenes Token aber mit "not in the conversation list" (`tools/talk.py:847-858`), das verletzt GATE-03 wörtlich für `talk_send`, `talk_browse(messages)` und `fetch(message:...)`; (2) `notes_create` in eine getaggte Kategorie wird abgewiesen, in eine nicht existente Kategorie legt die Notes-App die Kategorie an und schreibt (`tools/notes.py:279-289`), dort ist Byte-Gleichheit ohne Schreiben unmöglich (Klasse des akzeptierten Restorakels T-27-16). Dazu kommen zwei Kandidaten, die erst live entschieden werden (`files_search` mit getaggtem Ordner als `folder`, erster Chunk eines Binär-Uploads) und eine niedrige Reihenfolge-Ungleichheit bei scheiterndem Nachbar-Request (`chatgpt.py:334-337`, `notes.py:190-196`).

**Primary recommendation:** Eine gemeinsame Klassentabelle in `tests/contract/` (importierbar für Kanarie und Paartests), Freeze gegen `list_tools()` mit Laufzeit-Probe `files_update`, Kanarie über `Client(mcp)` mit Marker nur aus der Instanz und Kontroll-Marker als Gegenprobe, Paartests auf CallToolResult-Ebene mit wortgrenzen-sicherer Id-Normalisierung, EXCL-07 als Zeilen-Nadeln plus AST-Methodenprüfung für jeden Aufruf, der `TAGS_PATH` oder `systemtags` erwähnt. Vor der Planung vom Owner bestätigen lassen: Tables-Fix (B1), Talk-Ausfall-Fix (B2), Umgang mit `notes_create` (B4).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Klassifikations-Freeze | Test (contract, kein Netz) | MCP-Registry (`mcp_connector.server.mcp`) | D-28-02: Tabelle im Test, Abgleich gegen die laufende Registry; kein Metadatum an Werkzeugen |
| Kanarientest | Test (integration) gegen Nextcloud | API/Backend (Tool-Schicht über `Client(mcp)`) | Nur eine echte Instanz kann beweisen, dass der Marker aus keiner Antwort kommt |
| Ausfallmodus erzwingen | Test-Transport (respx im Prozess) | Nextcloud (echte Listung, echte Nachbar-Requests) | Die Guard-Logik läuft echt, nur die REPORT-Antwort wird ersetzt; App-aus erzeugt laut Phase 25 K1 kein "nicht prüfbar" |
| Paartests Unit | Test (unit, respx) | Tool-Schicht plus SDK-Fehlerpfad | Deterministische Ausfallpfade 412, zweiter 412, Timeout, 5xx |
| Paartests Live | Test (integration) | Nextcloud | Echte 404/409-Antworten von Nextcloud für "nicht existent" |
| EXCL-07 | Test (contract, AST über `src/`) | , | Konstruktionsbeweis über den Quelltext, nicht über Laufzeitverhalten |
| Eventuelle Fixes (B1, B2, B3) | API/Backend (`src/mcp_connector/tools/`) | , | Gehören in die Familie, nie in `server/` (D-28-02) |

## Klassifikation je Werkzeug (Befund mit Beleg)

Registry verifiziert: 22 Werkzeuge in 11 `server/reg_*.py`-Modulen, deckungsgleich mit `EXPECTED_TOOLS` (`tests/contract/test_tool_surface.py:39-62`). [VERIFIED: codebase grep]

### Liest Dateien (11 bestätigt, 12 falls B1 übernommen)

| Werkzeug | Warum betroffen | Beleg |
|---|---|---|
| files_search | liefert Namen und Pfade aus WebDAV SEARCH | `tools/files.py:145-185` |
| files_list | liefert Kinder eines Ordners | `tools/files.py:213-256` |
| files_read | liefert Inhalt per Pfad | `tools/files.py:316-405`, Guard in `_visible_stat` `:728-772` |
| files_download | liefert Bytes per Pfad (EmbeddedResource) | `tools/files.py:408-481` |
| notes_search | Notizen sind Dateien (Phase 25 K4, Notiz-Id = fileid) | `tools/notes.py` |
| notes_read | Notiz per Id = fileid | `tools/notes.py:159-210` |
| unified_search | Provider files, comments, notes, systemtags, Findling tragen Dateien | `tools/search.py:93-189`, `withhold.file_refs` |
| prepare_context | bündelt Suchtreffer und Ausschnitte über `fetch` | `tools/context.py` |
| talk_browse | Datei-Freigaben in Nachrichten, Datei-Räume tragen den Dateinamen als Raumnamen | `tools/talk.py:820-882`, raw/27-05 |
| search | Projektion von unified_search | `tools/chatgpt.py:168-201` |
| fetch | Id-Arten `file`, `note`, `message` tragen Dateien; `card`, `table` tragen Fremdtext mit möglichen Verweisen | `tools/chatgpt.py:236-257` |

### Schreibt in Dateifläche (3 bestätigt)

| Werkzeug | Warum betroffen | Beleg |
|---|---|---|
| files_upload | Ziel ist ein Pfad; `_writable` vor jedem Schreiben | `tools/files.py:484-529`, `:705-725`, Chunk-Pfad `:660-692` |
| notes_create | Ablage plus Kandidatdatei werden geprüft | `tools/notes.py:213-298` |
| talk_send | Token eines Datei-Raums wird über `one_room` abgewiesen | `tools/talk.py:347-...`, `:820-858` |

### Nicht betroffen (7 bestätigt, 1 Befund)

| Werkzeug | Urteil | Begründung mit Beleg |
|---|---|---|
| calendar_list_events | nicht betroffen | Ausgabe ist `id, uid, summary, start, end, all_day, calendar, location` (`tools/calendar.py:440-455`); der Parser liest nur `UID, SUMMARY, DTSTART, DTEND/DURATION, LOCATION` (`clients/caldav.py:391-406`). `ATTACH` und `DESCRIPTION` werden nie gelesen, damit kann ein Kalender-Anhang (Nextcloud legt dafür eine Freigabe an) nicht in die Antwort gelangen. Titel und Ort sind Fremdtext. |
| calendar_create_event | nicht betroffen | Antwort ist das Echo der eigenen Argumente plus Read-back derselben Felder (`tools/calendar.py:300-320`), kein Dateiargument. |
| deck_browse | nicht betroffen | Ausgabe je Ebene nur `id, title, can_edit` / `id, title, cards(Anzahl)` / `id, title, stack, url, duedate` (`tools/deck.py:132-140`, `:143-150`, `:183-190`); `description` und `attachments` der Karte werden nie ausgegeben; der Client spricht bewusst API v1.0 ohne Anhangstypen (`clients/deck.py:14-16`). |
| deck_create_card | nicht betroffen | Antwort `id, title, url, duedate` (`tools/deck.py:119-126`); Board und Stack sind Ziffern-Ids (`clients/deck.py:210-218`). |
| contacts_search | nicht betroffen | Ausgabe `full_name, emails, phones, organization, addressbook, uid` (`tools/contacts.py:132-142`, `clients/carddav.py:315-320`); kein `PHOTO`, kein `URL`, keine rohe vCard. |
| mail_browse | nicht betroffen | Nachrichten tragen nur `has_attachments: true` (`tools/mail.py:505-506`), die Liste der Anhänge wird verworfen (`:459-507`); Mails sind IMAP-Daten, keine Nextcloud-Dateien. Auch `fetch(mail:)` liest keinen Anhang (`tools/chatgpt.py`, Hinweistext "this connector reads no attachment"). |
| tables_create_row | nicht betroffen | Antwort ist die eigene Zeile; ein Link-Wert, den der Aufrufer liefert, kommt nur mit dem Titel zurück, den der Aufrufer selbst mitgab (Tables setzt sonst `title = resourceUrl`, `TextLinkBusiness.php` `parseValue`), und der Marker reist nie als Argument (D-28-06). |
| **tables_browse** | **BEFUND B1: kann Dateinamen getaggter Dateien zeigen** | Tables-Zellen vom Typ `text/link` speichern beim Auswählen über den Unified-Search-Provider `files` ein JSON `{title, value: resourceUrl, providerId: "files"}` (Tables `lib/Service/ColumnTypes/TextLinkBusiness.php`, Zweig `isset($data['resourceUrl'])`; Editor `src/.../rowTypePartials/TextLinkForm.vue:213-231` setzt `item.value = item.resourceUrl` aus `/search/providers/files/search`; `files` ist in `TextLinkForm.vue` der Spaltenkonfiguration voraktiviert). `title` ist der Dateiname zum Zeitpunkt des Verlinkens, `value` enthält `/f/<fileid>`. Der Connector reicht den Zellwert unverändert durch (`tools/tables.py:411-422` `_row`, `:524-542` `_clean` entfernt nur Marker-Sequenzen des Servers). Derselbe Weg gilt für `fetch(table:<id>)` (`tools/chatgpt.py:849`, `tables_tools.as_text`). |

[VERIFIED: codebase grep für alle Connector-Zeilen; VERIFIED: github.com/nextcloud/tables main für TextLinkBusiness.php und TextLinkForm.vue; exakte Drahtform der Zelle in `rows/simple` ist ASSUMED A1]

**Folge für D-28-01:** Mit B1 wird `tables_browse` zu `liest Dateien` (oder zu einer Unterklasse "zeigt Dateiverweise"), die Aufteilung ist dann 12 / 3 / 7. Weitere Fremdtext-Verweise (Deck-Beschreibung per Smart Picker in `fetch(card:)`, Tables-Rich-Text, Notizinhalt mit Link) tragen nach aktuellem Kenntnisstand nur die URL `/f/<fileid>`, nicht den Namen [ASSUMED A2]; sie sind Fremdtext wie ein eingetippter Dateiname und liegen außerhalb dessen, was ein fileid-basierter Guard sieht. Das gehört als ehrliche Grenze in die Doku von Phase 29.

**fetch, alle Id-Arten** (`ids.py:126-233`, `chatgpt.py:236-257`): `file:<fileid>`, `note:<id>`, `card:<board>:<stack>:<card>` oder `card:<card>`, `event:<calendarUri>:<objectName>`, `mail:<databaseId>`, `message:<token>:<messageId>`, `table:<tableId>`, `url:<absolute-url>` (nicht abrufbar, Fehler mit Echo der URL). Adressierende Arten für GATE-03: `file`, `note`, `message` (Datei-Raum-Token), und `table` falls B1 gefixt wird.

## Standard Stack

Keine neuen Abhängigkeiten. Alles vorhanden und gepinnt. [VERIFIED: pyproject.toml, uv.lock, .venv]

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| mcp | 2.0.0 (installiert) | `Client(mcp)` In-Memory, `MCPServer.add_tool`/`remove_tool` | offizielles SDK, Projekt-Constraint |
| pytest | >=9.1.1 | Runner, Marker `integration` | Bestand |
| anyio (pytest-Plugin) | Bestand | `@pytest.mark.anyio`, Backend asyncio (`tests/conftest.py`) | Bestand |
| respx | >=0.23.1 | Ausfallpfade mocken, live mit `pass_through` | Bestand, Muster `test_exclusion_live.py:1034-1047` |
| httpx | 0.28.x | Harness-Client (sync) und Tool-Client | Bestand |
| lxml | Bestand | PROPFIND-Rohantworten im Harness | Bestand |
| ast / tokenize (stdlib) | 3.13 | EXCL-07 | Bestand im Gate |

**Installation:** keine.

## Package Legitimacy Audit

Diese Phase installiert keine externen Pakete. slopcheck nicht nötig.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| (keine) | , | , | , | , | , | , |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
                +-------------------------------------------+
                | tests/contract/tool_classes.py (neu)      |
                |  FILE_READERS / FILE_WRITERS / UNAFFECTED |
                |  je Werkzeug ein Satz Begründung          |
                +-----+----------------+----------------+---+
                      |                |                |
          GATE-01     v      GATE-02   v      GATE-03   v
   +------------------+--+  +----------+---------+  +---+-----------------+
   | list_tools() der     |  | Harness (httpx +   |  | Paarmatrix         |
   | echten Registry      |  | occ) baut Kanarie, |  | (Werkzeug, Id-Art) |
   | -> Set-Vergleich     |  | Kontrolle, Verweise|  +---+-----------+-----+
   | -> leere Gründe rot  |  +----------+---------+      |           |
   | Probe files_update   |             |           Unit v      Live v
   | via add_tool ->      |             v           respx:    nc35 / CI:
   | erwartet rot,        |   Client(mcp) ruft     untagged/  getaggt vs
   | remove_tool finally  |   jedes Werkzeug       active/    erfunden
   +----------------------+   (Normal | Ausfall)   412/412x2/ (Normal |
                                      |            timeout/   Ausfall)
                                      v            5xx          |
                            Scan: Text, structured,    \        v
                            Blob (base64 dekodiert),    +-> CallToolResult
                            URI (unquote), Fehlertext       normalisieren
                                      |                     (Id -> <ID>)
                                      v                     -> byte-gleich?
                            Rohprotokoll raw/28-*.txt
                            "GEPRÜFT n von 22", Aufräumbeweis

   EXCL-07: src/**/*.py --ast/tokenize--> Zeilen-Nadeln + Methodenprüfung
            je Call mit TAGS_PATH/"systemtags" -> nur PROPFIND|REPORT erlaubt
```

### Recommended Project Structure
```
tests/
├── contract/
│   ├── tool_classes.py              # neu: die eine Klassentabelle (kein Testmodul)
│   ├── test_tool_classes.py         # neu: GATE-01 Freeze + Probe-Gegenprobe
│   └── test_no_destructive_calls.py # erweitert: EXCL-07-Familie
├── unit/
│   └── test_pair_equality.py        # neu: GATE-03 Unit über Client(mcp) + guard_routes
└── integration/
    ├── test_canary.py               # neu: GATE-02 (Normal + Ausfall), Rohprotokoll
    └── test_pair_equality_live.py   # neu: GATE-03 live (oder als Abschnitt in test_canary.py)
.planning/phases/28-gates-und-beweise/raw/  # Rohprotokolle
```
`pyproject.toml` braucht dafür `pythonpath = ["tests/integration", "tests/unit", "tests/contract"]`, damit Kanarie und Paartests die Tabelle importieren statt eine zweite Wahrheit zu pflegen. Das ist ein Eingriff in `pyproject.toml`, nicht in `src/`.

### Pattern 1: Freeze gegen die laufende Registry mit Laufzeit-Probe (GATE-01)
**What:** Drei Dicts `name -> Begründung`; Gate prüft (a) Vereinigung == `{t.name for t in await client.list_tools()}`, (b) paarweise disjunkt, (c) keine leere oder zu kurze Begründung, (d) Konsistenz zu `CREATE_TOOLS`: jeder Schreiber ist in `CREATE_TOOLS`, kein Leser ist es. Eine reine Funktion `unclassified(names)` wird vom Gate und von der Gegenprobe benutzt (Muster `_violations`, `test_no_destructive_calls.py:338-360`: "a counter proof that reimplements the check proves something about the counter proof").
**Probe:** `mcp.add_tool(fn, name="files_update", annotations=CREATE_ONLY, structured_output=False)` im Kontextmanager, `mcp.remove_tool(name)` im `finally`. `remove_tool` wirft bei unbekanntem Namen (`tool_manager.py:69-73`), `add_tool` warnt bei Duplikat.
**When to use:** genau einmal, in einem eigenen Contract-Test.

### Pattern 2: Kanarie über `Client(mcp)` (GATE-02)
**Topologie (Vorschlag, je Lauf `h = uuid4().hex[:8]`, Stamm `kanarie28x{h}`, Marker `mk{uuid4().hex}`, nur ASCII-Kleinbuchstaben und Ziffern):**
- `/{stamm}/` ungetaggt (Eltern, Suchwurzel).
- `/{stamm}/{stamm}-{marker}.txt` **getaggt**, Marker in Name und Inhalt (Ziel für Suche, Liste, fetch per fileid, Datei-Raum).
- `/{stamm}/Gesperrt-{h}/` **getaggt** (Name ohne Marker) mit `inhalt-{h}.txt` (Inhalt mit Marker): das Pfadziel für `files_read`, `files_download`, `files_upload`, damit kein Argument den Marker trägt (D-28-06).
- `/{stamm}/{stamm}-kontrolle.txt` ungetaggt mit **Kontroll-Marker** `ok{uuid}` in Inhalt und Name: jede Leser-Antwort, die die Datei zeigen würde, muss den Kontroll-Marker zeigen, sonst ist der grüne Kanarienbefund wertlos (Indexlücke, falscher Container).
- Notiz mit Marker in Titel und Inhalt, per `occ tag:files:add <noteid>` getaggt; Notiz-Kategorie getaggt für `notes_create`.
- Talk: eigener Raum des Harness, getaggte Datei darin geteilt (Freigabetyp 10), zweite Freigabe an `NC_MCP_TEST_USER2` plus `GET /ocs/v2.php/apps/spreed/api/v1/file/{fileid}` für den Datei-Raum (Muster `test_exclusion_live.py:934-1030`).
- Verweis-Kanarien in den "nicht betroffenen" Apps, um die Begründungen zu beweisen statt zu behaupten: Deck-Karte mit Anhang der getaggten Datei, Kalendereintrag mit `ATTACH` auf die Datei, **Tables-Zeile mit Link-Zelle auf die getaggte Datei** (heute voraussichtlich rot, Befund B1).

**Aufrufplan:** ein Dict `tool -> Liste von Argument-Sätzen`; Assertion `set(PLAN) == registry` und Ausgabe `KANARIE geprüft {n} von {len(registry)}` (muss `len(EXPECTED_TOOLS)` sein). Werkzeuge mit Cursor (`files_search`, `files_list`, `tables_browse`, `mail_browse`, `talk_browse` messages) blättern, bis kein `next` mehr kommt, mit `limit` am Maximum.

**Provider-cursors (D-28-08, A-27-04):** `unified_search` hat **keinen** Cursor-Eingang (`server/reg_search.py:18-36`), es gibt also über den Connector keine zweite Seite. Einzulösen ist: der Scan läuft über das ganze Antwort-JSON inklusive `cursors` (`tools/search.py:155-157`, `:183-184`), jeder Cursorwert ist ein Skalar ohne Marker, und der Stamm ist je Lauf eindeutig, sodass alle Treffer unter `MAX_LIMIT = 100` in die erste Seite passen (Protokollzeile mit Rohtrefferzahl je Provider). Der Files-Provider rechnet den Cursor aus Anfrage-Offset plus Limit, nicht aus der Trefferzahl (`apps/files/lib/Search/FilesSearchProvider.php:143` `$query->getCursor() + $query->getLimit()`), damit bestätigt sich A-27-04 für `files`. [VERIFIED: github.com/nextcloud/server master]

**Ausfallmodus (D-28-07):** respx-Router mit `assert_all_mocked=False`, Route `REPORT` auf `systemtags.home_url(creds)` gibt 500, `router.route().pass_through()` für alles andere (bewährt, `test_exclusion_live.py:1034-1047`). Zusätzlich 412-zweimal (REPORT immer 412: echte Listung, erneute Listung, zweiter 412, Grund `stale_twice`) und Timeout (`side_effect=httpx.ReadTimeout`). Das trifft den echten Automaten in `nextcloud/exclusion.py:247-277`; das Protokoll zählt `route.call_count` je Modus. `occ app:disable systemtags` ist **kein** Ausfall: REPORT antwortet laut Phase 25 K1 unverändert 207 auf NC 32 bis 35 (25-MESSBERICHT Zeilen 22-25).

### Pattern 3: Paartest auf CallToolResult-Ebene (GATE-03)
**What:** Beide Aufrufe über `Client(mcp)` (ohne `raise_exceptions`, damit der Werkzeugfehler als `CallToolResult(is_error=True)` zurückkommt, SDK `server.py:415-424`, `tools/base.py:180-181`: Text `Error executing tool <name>: <message> Hint: <hint>`), dann `result.model_dump(mode="json", by_alias=True)` sortiert serialisieren, die angefragte Id wortgrenzen-sicher durch `<ID>` ersetzen, Strings vergleichen.

**Paarmatrix (Empfehlung):**

| Werkzeug / Id-Art | getaggt | nicht existent | Normal heute | Ausfall heute |
|---|---|---|---|---|
| files_read, files_download | Pfad unter getaggtem Ordner, getaggte Datei | erfundener Pfad | gleich (`dav.not_found`, `files.py:728-772`) | gleich (Einheitsfehler vor PROPFIND-Fehler) |
| files_list | getaggter Ordner | erfundener Ordner | gleich (`files.py:233`) | gleich (leere Liste plus degraded, PROPFIND ungelesen) |
| files_search `folder=` | getaggter Ordner | erfundener Ordner | **offen B5** | gleich (degraded) |
| fetch `file:` | getaggte fileid | `999999999` | gleich (`_no_file`) | gleich |
| fetch `note:` / notes_read | getaggte Notiz | erfundene Id | gleich (`_note_not_found`) | gleich |
| fetch `message:` / talk_browse messages / talk_send | Datei-Raum-Token | erfundenes Token | gleich (`_unknown_token`) | **ungleich, B2** |
| files_upload Text | Pfad im getaggten Ordner | Pfad in erfundenem Ordner | gleich (`parent_missing`) | gleich |
| files_upload Binär, Chunk 1 | wie oben | wie oben | **offen B6** | gleich |
| notes_create | getaggte Kategorie | erfundene Kategorie | **ungleich, B4 (Restorakel)** | gleich |
| (Nachbar-Request 5xx) fetch `file:`, notes_read | getaggt | erfunden | **ungleich, B3 (niedrig)** | , |

### Pattern 4: EXCL-07 als Zeilen-Nadeln plus AST-Methodenprüfung
**What:** Die Verben DELETE, PROPPATCH, MOVE, COPY sind bereits global verboten (`test_no_destructive_calls.py:86-124`); PUT und POST sind erlaubt (files_upload, deck, notes). Deshalb:
1. Zeilen-Nadeln in `FORBIDDEN`: `"systemtags-relations"` (Zuordnungsroute; der Connector baut keine einzige Form davon), `"tag:files"` (occ-Kommandos gehören nur in den Harness), optional `"/apps/files/api/v1/files"` (alte Datei-Tags per `Api#updateFileTags`, POST, `apps/files/appinfo/routes.php`). Jede mit Beweiszeile in einem `SYSTEMTAGS_ROUTES`-Dict und Zähl-Test "jede Nadel hat eine Gegenprobe".
2. AST-Prüfung über alle Module: jeder `ast.Call`, dessen Argumente `TAGS_PATH` (Name oder Attribut) oder ein String/f-String-Teil mit `systemtags` enthalten, muss `*.request(<Konstante in {"PROPFIND", "REPORT"}>, ...)` sein; `.post/.put/.patch/.delete/.stream/.send` mit solchem Argument ist ein Fund. Grund: die zwei echten Aufrufe sind mehrzeilig (`clients/systemtags.py:126-132`, `:156-162`), eine Zeilen-Nadel sieht Verb und Ziel nie auf derselben Zeile.
3. Modulregel für `nextcloud/clients/systemtags.py` (Muster `MAIL_MODULES`/`WRITING_CALLS`, `:196-197`, `:603-618`): jeder Aufruf mit Attribut `request/post/put/patch/delete` ist `request("PROPFIND"|"REPORT", ...)`.
4. `ALLOWED_SYSTEMTAGS_FORMS`: die zwei echten Formen als Tupel, gegen die Prüfung grün.

**Verifizierte Nextcloud-Schreibformen** (alle müssen rot werden): `POST /remote.php/dav/systemtags/` (Tag anlegen), `POST /remote.php/dav/systemtags-relations/files/{fileid}` (anlegen und zuordnen), `PUT /remote.php/dav/systemtags-relations/files/{fileid}/{tagid}` (zuordnen), `DELETE` auf Relation oder Tag, `PROPPATCH /remote.php/dav/systemtags/{id}` (Name, Sichtbarkeit, Farbe) und `PROPPATCH` mit `nc:object-ids` auf `/systemtags/{id}/files` (Massenzuordnung). Die App `systemtags` hat als OCS-Route nur `GET /lastused`. [VERIFIED: nextcloud/server master `apps/dav/lib/SystemTag/SystemTagPlugin.php:100-103, 115-140, 404-470`, `apps/systemtags/appinfo/routes.php`]

**Alte Datei-Tags (Planer-Entscheid):** `oc:tags` und `oc:favorite` sind nur per PROPPATCH auf `/remote.php/dav/files/...` oder per `POST /index.php/apps/files/api/v1/files/{path}` schreibbar. PROPPATCH ist global verboten; keine Fundstelle in `src/` (Grep `oc:tags`, `favorite`, `apps/files/api`: nur das Lesefeld `favorite` in `tools/notes.py:208`). Empfehlung: keine eigene PROPPATCH-Nadel, aber je eine Beweiszeile (PROPPATCH mit `oc:tags`, PROPPATCH mit `oc:favorite`) in der Gegenprobe, dass die globale Nadel sie in `clients/dav.py` meldet, plus die billige Routen-Nadel `/apps/files/api/v1/files`.

### Anti-Patterns to Avoid
- **Freeze gegen `EXPECTED_TOOLS` statt gegen `list_tools()`:** ein Werkzeug, das registriert, aber nicht in die Liste eingetragen ist, wäre dann nur in `test_tool_surface.py` rot. Beide Abgleiche machen.
- **Kanarie ruft Tool-Funktionen direkt** (wie `test_exclusion_live.py`): beweist nichts über die Registry und nichts über den SDK-Fehlertext. Über `Client(mcp)` gehen.
- **Marker im Pfad eines Arguments:** jeder Treffer wäre ein Echo. Pfadziele unter dem getaggten Ordner mit neutralem Namen.
- **Grün ohne Gegenprobe:** eine Kanarie ohne Kontroll-Marker ist bei leerem Suchindex oder falschem Container grün.
- **`str.replace` der Id ohne Wortgrenze:** eine kurze fileid ersetzt Ziffern in Größen oder Statuscodes.
- **Probe-Werkzeug ohne `finally`:** leckt in `test_the_byte_gate_counts_exactly_as_many_tools_as_this_file_freezes` und alle anderen Registry-Tests desselben Prozesses.

## Befunde, die `src/` berühren könnten

| # | Befund | Beleg | Schwere | Empfehlung |
|---|---|---|---|---|
| B1 | `tables_browse` und `fetch(table:)` geben Link-Zellen mit Dateiname und fileid getaggter Dateien aus | `tools/tables.py:411-422`, `:524-542`, `:425-454`; `chatgpt.py:849`; Tables `TextLinkBusiness.php` | MITTEL (echter Namensabfluss, aber nur über eine vom Tabellenautor gespeicherte Kopie) | Owner fragen. Fix-Vorschlag: Link-Zellen mit `providerId == "files"` oder `value` auf `/f/<ziffern>` durch den Guard; zurückgehalten wird zu `""` (der Leerwert der App), im Ausfall alle Datei-Link-Zellen `""` plus ein degraded-Eintrag im Familienidiom. Klasse dann `liest Dateien`. |
| B2 | Im Ausfall: Datei-Raum-Token -> Einheitsfehler, erfundenes Token -> `_unknown_token` | `tools/talk.py:847-858` | NIEDRIG bis MITTEL (Existenz eines Datei-Raums im Ausfall erkennbar), aber GATE-03 wörtlich rot | Fix: vor `raise _unknown_token(token)` den Guard fragen und bei `unverifiable` `withhold.unavailable_error()` werfen; kostet einen Flight nur auf dem Fehlerpfad. Deckt `talk_send`, `talk_browse(messages)`, `fetch(message:)`. |
| B3 | Scheitert der Nachbar-Request (fileid-SEARCH bzw. Notes-GET) mit 5xx, antwortet getaggt mit "nicht gefunden", erfunden mit dem 5xx-Fehler | `chatgpt.py:334-337`, `notes.py:190-196` (Tag vor Fehler; `_visible_stat` macht es umgekehrt, `files.py:765-771`) | NIEDRIG (braucht Serverfehler) | Reihenfolge an `_visible_stat` angleichen: Fehler des Nachbar-Requests (außer `REASON_UNKNOWN_ID`) vor der Tag-Entscheidung. Nur wenn der Paartest diesen Fall aufnimmt; Owner/Planer. |
| B4 | `notes_create` in erfundene Kategorie schreibt, in getaggte wird abgewiesen | `notes.py:279-289` | bekannt (Klasse T-27-16/T-27-35) | Nicht fixbar ohne Schreiben. Paartest vergleicht nur die Fälle, die Nextcloud auch abweist, und hält die Ausnahme als benannten, akzeptierten Eintrag in der Matrix fest (nicht still überspringen). Owner bestätigen lassen, weil D-28-09 "so wenig wie ein Leser" sagt. |
| B5 | `files_search(folder=<getaggt>)` antwortet `count 0`, `folder=<erfunden>` hängt davon ab, ob Nextcloud SEARCH auf fehlendem Scope 404 gibt (dann `dav.not_found`, `dav.py:1017-1018`) | `files.py:145-185` | offen (live entscheiden) | Live-Paar aufnehmen. Wird es ungleich: Ordner selbst vor der Suche gegen den Scope prüfen und `dav.not_found(folder)` werfen. |
| B6 | Binär-Upload Chunk 1: getaggt sofort `parent_missing` (`files.py:665-667`), erfunden hängt davon ab, ob Nextcloud beim MKCOL/PUT des Chunks den Zielordner prüft | `files.py:660-692` | offen (live entscheiden) | Live-Paar aufnehmen; bei Ungleichheit Befund an den Owner (Restorakel oder Vorabprüfung des Elternordners). |

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Guard-Zustände im Unit-Test | eigene XML-Antworten | `tests/unit/guard_routes.py` (`untagged`, `active`, `unverifiable`, `tag_list`, `report_207`, `reset`) | bereits gegen den echten Guard geeicht |
| Ausfall live | Proxy-Regel in Caddy, App ausschalten | respx `pass_through` plus REPORT-Route | bewährt in 27-07 SC5, trifft den echten Automaten |
| Werkzeug-Aufruf | direkter Funktionsaufruf, eigener JSON-Wrapper | `Client(mcp).call_tool` | nur so zählen Registry, `graceful` und SDK-Fehlertext mit |
| Probe-Registrierung | Monkeypatch von `_tool_manager._tools` | `mcp.add_tool` / `mcp.remove_tool` | öffentliche API von mcp 2.0.0 |
| Quelltext ohne Prosa | eigener Kommentar-Filter | `_code_lines` aus `test_no_destructive_calls.py:308-335` | entfernt Docstrings und Kommentare, lässt Literale |
| Tagging im Harness | HTTP-PUT auf systemtags-relations | `occ tag:add` / `tag:files:add` / `tag:files:delete` | EXCL-07: auch der Harness baut keine Relationsroute nach, die im Gate verboten ist |
| Container-Namen | Literal `nc35-nc` | `topology.NC_CONTAINER` bzw. `topology.COMPOSE` | `test_exclusion_live.py:83` ist hart auf nc35 und läuft deshalb nicht im CI-Job exapp |

**Key insight:** Jede Gegenprobe muss durch dieselbe Prüffunktion laufen wie das Gate. Ein zweiter Prüfweg beweist nur sich selbst.

## Common Pitfalls

### Pitfall 1: Harness im falschen Container
**What goes wrong:** `occ` läuft in `nc-mcp-exapp-nc` statt `nc35-nc`, `tag:files:add` scheitert mit "not found" oder taggt die falsche Instanz.
**Why it happens:** `topology.py` hat die 34er-Topologie als Default.
**How to avoid:** lokal immer `set -a && . ./.env.nc35 && set +a` plus die sechs `NC_MCP_E2E_*`-Exporte (27-LIVE-BEWEIS, Neumessung 28.09.) plus `PYTHONUTF8=1`; im Test `topology.COMPOSE` oder `NC_CONTAINER` verwenden.
**Warning signs:** Kontroll-Marker fehlt, `tag:list` zeigt kein `kein-ki`.

### Pitfall 2: cp1252-Konsole
**What goes wrong:** Protokoll bricht an einem Talk-Raumnamen mit U+2705.
**How to avoid:** `PYTHONUTF8=1`; Rohdateien mit `encoding="utf-8"` öffnen.

### Pitfall 3: Namens-Cache des Guards zwischen Modi
**What goes wrong:** Nach dem 412-Modus bleiben keine Ids im Cache, nach dem Normalmodus bleiben Ids 60 s gültig; die Zahl der Listungen im Protokoll schwankt.
**How to avoid:** `exclusion.clear_cache()` und `capabilities.clear_cache()` vor jedem Modus; `call_count` der injizierten Route protokollieren.

### Pitfall 4: Probe-Werkzeug leckt
**How to avoid:** Kontextmanager mit `finally: mcp.remove_tool(name)`; kein `pytest-xdist` im Projekt, Tests laufen sequenziell, trotzdem nie auf Modulebene registrieren.

### Pitfall 5: Marker in kodierter Form übersehen
**What goes wrong:** `files_download` liefert Base64 in `BlobResourceContents.blob`, die Ressource-URI ist prozentkodiert (`reg_files.py`, `quote`).
**How to avoid:** Blob dekodieren, URI `unquote`, `structured_content` als JSON, Text-Inhalte; Marker nur ASCII-Kleinbuchstaben und Ziffern, damit weder JSON-Escape noch Prozentkodierung ihn verändern.

### Pitfall 6: Id-Normalisierung bei abgeleiteten Pfaden
**What goes wrong:** `parent_missing` nennt Elternordner und Pfad (`dav.py:72-84`); ersetzt man nur den Pfad, bleibt der Elternname verschieden.
**How to avoid:** "angefragte Id" als das Argument und seine Präfixe definieren (Pfad und `dirname`-Kette, längste zuerst), für `fetch` sowohl `file:22215` als auch `22215`, für Talk das Token (steht per `repr` in Hochkommas). Diese Definition gehört wörtlich in den Test-Docstring.

### Pitfall 7: Schreibende Werkzeuge ohne Aufräumbeweis
**How to avoid:** je Nebenwirkung eine `CLEANUP`-Zeile mit gelesenem Rohwert (PROPFIND 404, Notizliste ohne Id, Board/Tabelle gelöscht, Talk-Nachricht per `DELETE /chat/{token}/{id}` oder Harness-Raum gelöscht, Kalenderobjekt per CalDAV-DELETE); `talk_send` ist per Default an (`config.talk_send_enabled`, nur ein Falschwert schaltet ab).

### Pitfall 8: Leere Apps in CI
**What goes wrong:** Im Job exapp sind notes, deck, tables, mail, spreed installiert (`scripts/bootstrap_exapp.sh:1316-1327`), ein Kalender oder ein Adressbuch für alice ist nicht ausdrücklich angelegt; `calendar_*` und `contacts_search` können mit einem Fehler antworten.
**How to avoid:** Fehlerantworten sind gültige Kanarien-Antworten (gescannt wie Erfolg), aber das Protokoll nennt sie; für echte Schreibaufrufe legt der Harness per MKCALENDAR einen Kalender an oder der Plan akzeptiert die Fehlerantwort mit Begründung.

### Pitfall 9: Byte-Budget
**How to avoid:** keine Beschreibung, kein Parameter ändern; Fixes B1 bis B3 berühren nur Tool-Logik. `scripts/check_tool_budget.py` nach jedem Plan laufen lassen.

### Pitfall 10: pyright standard auf Tests
**What goes wrong:** `CallToolResult.content` ist eine Union (`TextContent | ImageContent | EmbeddedResource | ...`).
**How to avoid:** mit `isinstance` verengen, keine `# type: ignore` ohne Grund.

## Code Examples

### 1. Klassentabelle und Probe (GATE-01)
```python
# Source: mcp 2.0.0 .venv/Lib/site-packages/mcp/server/mcpserver/server.py:570-619
from collections.abc import Iterable, Iterator
from contextlib import contextmanager

from mcp_connector.server import CREATE_ONLY, mcp

FILE_READERS: dict[str, str] = {"files_read": "Reads the content of one file by path.", ...}
FILE_WRITERS: dict[str, str] = {"files_upload": "Creates a file at a path.", ...}
UNAFFECTED: dict[str, str] = {
    "deck_browse": "Answers id, title, stack, url and duedate only; description and "
    "attachments of a card never leave the tool (tools/deck.py:183-190).",
    ...
}
MIN_REASON = 20

def unclassified(names: Iterable[str]) -> list[str]:
    known = FILE_READERS.keys() | FILE_WRITERS.keys() | UNAFFECTED.keys()
    return sorted(set(names) - known)

@contextmanager
def probe_tool(name: str = "files_update") -> Iterator[str]:
    async def files_update(path: str) -> str:
        return path
    mcp.add_tool(files_update, name=name, annotations=CREATE_ONLY, structured_output=False)
    try:
        yield name
    finally:
        mcp.remove_tool(name)
```

### 2. Normalisierter Vergleich (GATE-03)
```python
import json
import re
from mcp.types import CallToolResult

def normalised(result: CallToolResult, *requested: str) -> str:
    text = json.dumps(
        result.model_dump(mode="json", by_alias=True), sort_keys=True, ensure_ascii=False
    )
    for value in sorted({v for v in requested if v}, key=len, reverse=True):
        text = re.sub(rf"(?<![0-9A-Za-z]){re.escape(value)}(?![0-9A-Za-z])", "<ID>", text)
    return text
```

### 3. Marker-Scan (GATE-02)
```python
import base64
import json
from urllib.parse import unquote
from mcp.types import CallToolResult, EmbeddedResource, BlobResourceContents, TextContent

def surfaces(result: CallToolResult) -> list[str]:
    out = [json.dumps(result.structured_content or {}, ensure_ascii=False)]
    for part in result.content:
        if isinstance(part, TextContent):
            out.append(part.text)
        elif isinstance(part, EmbeddedResource):
            out.append(unquote(str(part.resource.uri)))
            if isinstance(part.resource, BlobResourceContents):
                out.append(base64.b64decode(part.resource.blob).decode("utf-8", "replace"))
    return out
```

### 4. EXCL-07 Methodenprüfung
```python
import ast

READ_METHODS = frozenset({"PROPFIND", "REPORT"})
CALL_ATTRS = frozenset({"request", "post", "put", "patch", "delete", "stream", "send"})

def _mentions_tags(node: ast.AST) -> bool:
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name) and sub.id == "TAGS_PATH":
            return True
        if isinstance(sub, ast.Attribute) and sub.attr == "TAGS_PATH":
            return True
        if isinstance(sub, ast.Constant) and isinstance(sub.value, str) and "systemtags" in sub.value:
            return True
    return False

def tag_writes(relative: str, source: str) -> list[str]:
    findings: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        if node.func.attr not in CALL_ATTRS or not _mentions_tags(node):
            continue
        verb = node.args[0] if node.args else None
        if node.func.attr == "request" and isinstance(verb, ast.Constant) and verb.value in READ_METHODS:
            continue
        findings.append(f"{relative}:{node.lineno}: write on systemtags")
    return findings
```
Gegenprobe: an den echten Quelltext von `clients/systemtags.py` eine Funktion mit der mehrzeiligen Form `await client.request(\n    "POST",\n    f"{creds.base_url}{TAGS_PATH}",\n)` anhängen und `tag_writes` muss sie melden; der unveränderte Quelltext muss leer sein.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Live-Beweise über direkte Tool-Funktionen (27-07) | Aufruf über `Client(mcp)` | diese Phase | Registry und SDK-Fehlertext sind Teil des Beweises |
| Paarvergleich über `ToolError.message/hint` (`test_talk_exclusion.py:531-578`) | ganzer `CallToolResult` normalisiert | diese Phase | `isError`, `structuredContent`, Präfix `Error executing tool` zählen mit |
| `FastMCP` | `MCPServer` mit `add_tool`/`remove_tool` | mcp 2.0.0 (28.07.2026) | Probe ohne private Felder |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `GET .../tables/{id}/rows/simple` liefert eine Link-Zelle als JSON-String mit `title` (Dateiname) und `value` (`/f/<fileid>`) | Klassifikation, B1 | Liefert die Route nur die URL, schrumpft B1 auf einen fileid-Abfluss; Wave 0 misst es mit einer Probezeile |
| A2 | Smart-Picker-Links in Deck- und Text-Beschreibungen tragen nur die URL, nicht den Dateinamen | Klassifikation | Trägt der Markdown-Link den Namen, betrifft B1 auch `fetch(card:)` |
| A3 | Nextcloud SEARCH auf fehlendem Scope antwortet 404 | B5 | Antwortet es 207 leer, ist das Paar gleich und kein Fix nötig |
| A4 | Nextcloud prüft beim ersten Chunk (MKCOL/PUT mit `Destination`) nicht, ob der Zielordner existiert | B6 | Prüft es, ist das Paar gleich |
| A5 | Nextcloud legt für alice im CI-Job exapp keinen Kalender und kein Adressbuch von selbst an | Pitfall 8 | nur Protokollinhalt, kein Risiko für das Gate |

## Open Questions (RESOLVED: B1 bis B4 per D-28-14..17 in 28-CONTEXT.md; Frage 5 ExApp/HaRP-Kette bewusst nicht zusätzlich, Empfehlung der Research, kein Plan hängt daran)

1. **B1 Tables-Link-Zellen: Fix in Phase 28 oder dokumentierte Grenze?**
   - What we know: Namensabfluss über eine gespeicherte Kopie, Tables-Quelle verifiziert, Connector reicht durch.
   - What's unclear: Drahtform in `rows/simple` (A1), Owner-Wille zum Umfang.
   - Recommendation: Owner fragen; Standardempfehlung Fix (Zelle `""` bei getaggt, degraded im Ausfall), weil der Kanarientest sonst eine bewusst weggelassene Verweis-Kanarie bräuchte.
2. **B2 Talk im Ausfall: Fix bestätigen.** Empfehlung Fix, klein und im Geist von D-27-03.
3. **B4 notes_create: akzeptierte Ausnahme in der Paarmatrix?** Empfehlung ja, mit Verweis auf T-27-16/A-27-06 und Satz in Phase-29-Doku.
4. **B3 Lookup-Reihenfolge: in den Paartest aufnehmen?** Empfehlung ja (ein Unit-Fall je Werkzeug), Fix ist zwei Zeilen je Stelle.
5. **Pflicht zur ExApp-Kette:** Die Kanarie über `Client(mcp)` spricht mit App-Passwort direkt mit Nextcloud. Soll zusätzlich ein Lauf über HTTP durch HaRP und AppAPI-Impersonation laufen? Phase 25 K2 hat gleiche fileid-Mengen gemessen; Empfehlung: nicht nötig, im Protokoll so benennen.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python (.venv) | alle Tests | ✓ | 3.13.13 | , |
| uv | Toolchain | ✓ | 0.11.7 | , |
| Docker Desktop | occ im Harness | ✓ | läuft (`docker ps`) | , |
| nc35-Topologie | Kanarie, Live-Paare lokal | ✓ | nc35-nc, nc35-harp, nc35-caddy, nc35-greenmail, nc_app_mcp_connector laufen | , |
| `.env.nc35` | lokale Live-Läufe | ✓ | enthält NC_MCP_URL, NC_MCP_TEST_USER, NC_MCP_TEST_APP_PASSWORD, NC_MCP_TEST_USER2, NC_MCP_TEST_TALK_ROOM | , |
| CI-Job exapp | Kanarie in CI | ✓ (Workflow) | `.github/workflows/ci.yml:64-152` | läuft erst beim nächsten Push (Owner-Entscheid), wie SBX-01 |

**Missing dependencies with no fallback:** keine.
**Missing dependencies with fallback:** CI-Nachweis erst nach Push; bis dahin nur lokaler nc35-Beweis (wie SBX-01 in Phase 27).

## Validation Architecture

(`workflow.nyquist_validation` steht in `.planning/config.json` auf `false`; der Abschnitt steht hier auf ausdrücklichen Wunsch des Orchestrators.)

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >=9.1.1 mit anyio-Plugin, respx >=0.23.1 |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (addopts deselektiert `integration`) |
| Quick run command | `.venv/Scripts/python.exe -m pytest tests/contract tests/unit/test_pair_equality.py -q` |
| Full suite command | `uv run pytest tests/unit tests/contract` plus lokal Live (siehe unten) |

Live lokal: `set -a && . ./.env.nc35 && set +a && export NC_MCP_E2E_COMPOSE_FILE=compose.nc35.yml NC_MCP_E2E_PROJECT=nc-mcp-nc35 NC_MCP_E2E_NEXTCLOUD=nc35-nc NC_MCP_E2E_HARP=nc35-harp NC_MCP_E2E_CADDY=nc35-caddy NC_MCP_E2E_CONTAINERS=nc35-nc,nc_app_mcp_connector,nc35-harp,nc35-caddy,nc35-greenmail && PYTHONUTF8=1 .venv/Scripts/python.exe -m pytest tests/integration/test_canary.py -m integration -s`

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| GATE-01 | jede Registry-Zeile klassifiziert, Gründe nicht leer, Probe macht rot | contract | `pytest tests/contract/test_tool_classes.py -x` | ❌ Wave 0 |
| GATE-02 | Marker in 0 Antworten und 0 Fehlertexten, Normal und Ausfall, "geprüft 22 von 22", Kontroll-Marker sichtbar | integration | `pytest tests/integration/test_canary.py -m integration -s` | ❌ Wave 0 |
| GATE-03 | getaggt == erfunden je Paar, Normal, 412, zweiter 412, Timeout, 5xx | unit | `pytest tests/unit/test_pair_equality.py -x` | ❌ Wave 0 |
| GATE-03 | getaggt == erfunden live, Normal und Ausfall | integration | `pytest tests/integration/test_pair_equality_live.py -m integration -s` | ❌ Wave 0 |
| EXCL-07 | Nadeln treffen ihre Zeile, AST meldet injizierte Schreibform, echte Module sauber | contract | `pytest tests/contract/test_no_destructive_calls.py -x` | ✅ (erweitern) |

### Sampling Rate
- **Per task commit:** Quick run plus `ruff check .`, `ruff format --check .`, pyright, vulture, `scripts/check_tool_budget.py`.
- **Per wave merge:** `uv run pytest tests/unit tests/contract`.
- **Phase gate:** voller Lauf plus nc35-Live-Protokoll mit null `: nein`-Zeilen; CI-Schritt exapp verdrahtet.

### Wave 0 Gaps
- [ ] `tests/contract/tool_classes.py` plus `pythonpath`-Eintrag `tests/contract`
- [ ] Live-Probe A1 (eine Tables-Zeile mit Link auf eine Datei, Rohantwort `rows/simple` ins Rohprotokoll)
- [ ] Live-Probe A3/A4 (SEARCH auf fehlendem Scope, Chunk 1 in fehlenden Ordner), nur lesen bzw. eigene Wegwerfpfade
- [ ] Harness-Klasse für die Kanarie auf Basis `TagFixture`/`Harness` mit `topology.COMPOSE`

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | nein | unverändert |
| V3 Session Management | nein | Harness räumt Cookies je Request (`Harness.request`, Nextcloud-401-Falle) |
| V4 Access Control | ja | `kein-ki`-Guard fail-closed; Gates beweisen, dass Ausschluss nicht umgangen wird |
| V5 Input Validation | ja (indirekt) | `ids.parse`, `dav.safe_path` laufen vor dem Guard und hängen nur vom Input ab, daher kein Orakel |
| V6 Cryptography | nein | , |
| V7 Error Handling | ja | ein Wortlaut `EXCLUSION_UNAVAILABLE`, `dav.not_found`, `_no_file`, `_unknown_token`; Paartests beweisen Byte-Gleichheit |
| V8 Data Protection | ja | Marker-Scan über alle Ausgabeflächen |

### Known Threat Patterns for diese Phase

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Existenz-Orakel über unterschiedliche Fehlertexte | Information Disclosure | Paartests GATE-03; Fixes B2, B3 |
| Namensabfluss über gespeicherte Verweise (Tables-Link) | Information Disclosure | Befund B1, Guard-Screening der Zelle |
| Zähl-Orakel über Provider-cursors | Information Disclosure | Files-Cursor aus Anfrage verifiziert; Scan der `cursors`; A-27-04 schließen |
| Connector setzt oder entfernt den Tag | Tampering / Elevation | EXCL-07 Nadeln und AST-Methodenprüfung |
| Neues Werkzeug umgeht den Guard (files_update) | Tampering / Disclosure | GATE-01 Freeze mit Laufzeit-Probe |
| Harness schreibt auf Testinstanz | Tampering | nur Wegwerfbaum je Lauf, `finally`-Aufräumen mit gelesenem Beweis (A-27-05-Muster) |
| Timing-Orakel | Information Disclosure | akzeptiert, Doku Phase 29 (D-28-12) |

## Sources

### Primary (HIGH confidence)
- Codebase (mit Zeilen oben): `src/mcp_connector/tools/{files,notes,talk,chatgpt,search,tables,deck,calendar,contacts,mail,withhold}.py`, `nextcloud/{exclusion,__init__}.py`, `nextcloud/clients/{systemtags,dav,deck,caldav,carddav}.py`, `server/*.py`, `ids.py`, `deps.py`, `config.py`
- Tests: `tests/contract/test_tool_surface.py`, `tests/contract/test_no_destructive_calls.py`, `tests/unit/guard_routes.py`, `tests/unit/test_chatgpt_search.py`, `tests/integration/{test_exclusion_live,test_ctx_bundle,test_findling_sandbox,topology}.py`, `.github/workflows/ci.yml`, `scripts/bootstrap_exapp.sh`, `scripts/check_tool_budget.py`
- mcp 2.0.0 installiert: `mcp/server/mcpserver/server.py:415-424, 481-504, 570-619`, `tools/tool_manager.py:69-89`, `tools/base.py:173-181`
- Nextcloud server master: `apps/dav/lib/SystemTag/SystemTagPlugin.php`, `SystemTagMappingNode.php`, `SystemTagsObjectMappingCollection.php`, `apps/systemtags/appinfo/routes.php`, `apps/files/appinfo/routes.php`, `apps/files/lib/Search/FilesSearchProvider.php`
- Nextcloud tables main: `lib/Service/ColumnTypes/TextLinkBusiness.php`, `lib/Service/ColumnTypes/` (Spaltentypen), `src/shared/components/ncTable/partials/rowTypePartials/TextLinkForm.vue`, `.../columnTypePartials/forms/TextLinkForm.vue`
- Projektdokumente: 28-CONTEXT.md, 27-LIVE-BEWEIS.md, 27-SECURITY.md, 27-CONTEXT.md, 25-MESSBERICHT.md, REQUIREMENTS.md, ROADMAP.md, STATE.md

### Secondary (MEDIUM confidence)
- [nextcloud/tables Issue #2237](https://github.com/nextcloud/tables/issues/2237) und [CHANGELOG](https://github.com/nextcloud/tables/blob/main/CHANGELOG.md) (providerId in Link-Zeilen)

### Tertiary (LOW confidence)
- keine

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH, keine neuen Pakete, SDK-API im installierten Paket gelesen
- Architecture: HIGH, alle Muster existieren im Repo
- Klassifikation: HIGH für die sieben sauberen Urteile, MEDIUM für B1 bis zur Drahtprobe A1
- Pitfalls: HIGH, überwiegend aus gemessenen Phase-27-Befunden

**Research date:** 2026-09-28
**Valid until:** 2026-10-28 (stabil; neu prüfen, sobald files_update aus Issue #9 gemergt wird)
