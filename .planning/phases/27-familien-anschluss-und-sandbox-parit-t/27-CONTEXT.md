# Phase 27: Familien-Anschluss und Sandbox-Parität - Context

**Gathered:** 2026-09-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Der Guard aus Phase 26 wird in alle dateitragenden Tool-Familien verdrahtet: was `kein-ki` trägt oder unter einem getaggten Ordner liegt, erscheint in keiner Antwort mehr, weder als Treffer noch als Inhalt, Ausschnitt, Digest oder eingesetzter Dateiname (files_list, files_search, files_read, files_download, files_upload, unified_search, search/fetch, prepare_context, notes, talk_browse). Findling-Treffer, die nur eine fileId tragen, und Notes laufen zusätzlich durch dieselbe Sandbox- (NC_MCP_FILES_ROOT) und Ausschlussprüfung wie Pfad-Treffer. Requirements: EXCL-01, EXCL-03, EXCL-05, EXCL-06, SBX-01, SBX-02. Gates und Beweise (Kanarientest, Klassifikations-Freeze, byte-gleiche Paartests) sind Phase 28; Prüfkommando und Doku sind Phase 29.

</domain>

<decisions>
## Implementation Decisions

### Upload-Orakel (files_upload, upload_binary)
- **D-27-01:** Ein Upload auf einen ausgeschlossenen Pfad (Ziel getaggt oder unter getaggtem Ordner) wird IMMER abgewiesen, Wortlaut byte-gleich zum bestehenden Fehler "The parent folder ... does not exist". Die Story "ausgeschlossen = existiert nicht" gilt auch beim Schreiben; der getaggte Ordner ist in Listings ohnehin unsichtbar. Grenzfall direkt getaggte Datei unter sichtbarem Elternordner: Claude wählt den konsistentesten Wortlaut und dokumentiert ihn im Plan. (Owner 27.09., Empfehlung übernommen)
- **D-27-02:** Bei "nicht prüfbar" (REPORT-Fehler, Timeout, zweiter 412) wird der Upload fail-closed abgewiesen, mit klarer Meldung im einheitlichen Wortlaut von D-27-05. Sonst könnte ein Upload ungeprüft im ausgeschlossenen Teilbaum landen und der Konflikt-Orakel-Schutz wäre in diesem Zustand offen. (Owner 27.09., Empfehlung übernommen)

### Zählen vs. Schweigen (Degradations-Ausgestaltung je Familie)
- **D-27-03:** Im Erfolgsfall gilt D-v1.7-02 unverändert: komplettes Schweigen über tag-zurückgehaltene Einträge, kein Zähler, kein Hinweis. Bei "nicht prüfbar" GETEILT NACH ZUGRIFFSART: Listen-Familien (files_list, files_search, unified_search, prepare_context, notes-Listen, Findling-Treffer) halten dateitragende Einträge zurück und schreiben EINEN degraded-Eintrag im bestehenden Idiom der Familie; Einzelzugriffe (files_read, files_download, fetch, notes-Einzelzugriff) liefern einen einheitlichen ToolError, für ALLE Ids gleich, damit der Fehler selbst kein Orakel wird. (Owner 27.09., Empfehlung übernommen)
- **D-27-04:** Der bestehende skipped-Zähler in unified_search zählt weiterhin NUR unbrauchbare und Sandbox-Treffer; tag-ausgeschlossene Treffer verschwinden lautlos und erhöhen keinen Zähler. Reihenfolge im Zweifel: Sandbox-Drop vor Tag-Prüfung ist erlaubt (der Sandbox-Grund verrät nichts über das Tag). (Owner 27.09., Empfehlung übernommen)
- **D-27-05:** EIN Wortlaut überall: eine gemeinsame Konstante (z.B. reason "exclusion check unavailable") für degraded-Einträge, die ToolErrors der Einzelzugriffe und die Upload-Abweisung bei "nicht prüfbar". Kein Drift zwischen Familien, ein Satz für die Doku in Phase 29. (Owner 27.09., Empfehlung übernommen)

### Talk-Platzhalter (EXCL-06)
- **D-27-06:** talk_browse behandelt die getaggte geteilte Datei wie einen Eintrag ohne Namen: der Platzhalter bleibt roh als `{file}` im Nachrichtentext, exakt wie der bestehende Unbekannt-Pfad (talk.py: "An unknown placeholder, and one whose entry carries no name, stays in the text exactly as {placeholder}"). Kein neuer Marker, kein Orakel, die Nachricht selbst bleibt erhalten. Bei "nicht prüfbar" bleiben ALLE Datei-Platzhalter roh plus degraded-Eintrag (konsistent mit D-27-03). Wichtig: auch die rohen messageParameters-Werte (Dateiname, Pfad) dürfen die Antwort nicht auf anderem Weg verlassen. (Owner 27.09., Empfehlung übernommen)

### Aus früheren Phasen übernommene Entscheide (gelten unverändert, nicht neu verhandeln)
- **D-v1.7-01/02:** Fester Tag-Name `kein-ki`, Groß-/Kleinschreibung egal, Varianten vereinigt; kein "n zurückgehalten"-Zähler (Existenz-Orakel).
- **D-26-01/02:** Das Tag ist die einzige Ordner-Ausschlussliste; kein Admin-Schalter, fail-closed mit Meldung.
- **D-25-05:** Fail-closed-Automat: 207 = Menge ermittelt, 412 = Tag-Id genau einmal neu auflösen, jeder andere Ausgang = "nicht prüfbar"; Capability systemtags.enabled wird nicht befragt.
- **E3:** Ein REPORT je Antwort; die getaggte Menge wird nie über den Aufruf hinaus gecacht, nur die Name-zu-Id-Auflösung ist prozessweit gecacht.
- **EXCL-05-Vorentscheid:** Notiz-Id = fileid ist doppelt belegt; der Notes-Anschluss wird in dieser Phase gebaut (kein Vertagen, keine Zusatzrecherche nötig).

### Claude's Discretion
- Wortlaut des Grenzfalls direkt getaggte Datei bei Upload (D-27-01), solange konsistent und dokumentiert.
- Exakter Konstantenname und Schlüssel des einheitlichen Degradations-Wortlauts (D-27-05), solange die Meldung klar benennt, dass die Ausschlussprüfung nicht beantwortbar war, und im Erfolgsfall nichts erscheint.
- Verdrahtungsreihenfolge der Familien, Zuschnitt der Pläne, Teststrategie je Familie; Messläufe gegen die echte Nextcloud (Erfolgskriterien 1, 2 und 4 verlangen Live-Messungen inkl. prepare_context-Wanduhr im Rahmen der Phase-25-Referenz).
- Umgang mit dem Flight-Halter-Abbruch (deferred-items (c)): falls Abbrüche in der Praxis häufig sind, hier neu bewerten, sonst belassen.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Messbefunde und Owner-Entscheide (Grundlage aller Ableitungen)
- `.planning/phases/25-mess-spike-tag-abfrage/25-MESSBERICHT.md` , alle Messzahlen (REPORT 1/100/5000, prepare_context-Referenz, App-aus, 412, Varianten, Zielpfad, Freigabe-Grenze, PG-Gegenmessung, SQLite-140k-Grenze) und die wörtlichen Owner-Entscheide D-25-05 und E3; der Notes-Beleg Notiz-Id = fileid steht hier.
- `.planning/phases/26-guard-kern/26-CONTEXT.md` , Entscheide D-26-01/02 und die übernommenen Phase-25-Entscheide.
- `.planning/phases/26-guard-kern/deferred-items.md` , Merker (e) ist PFLICHT in dieser Phase: ExclusionGuard-Feld an NcClients, vulture_whitelist-Abschnitt räumen, Entscheid über `_.is_collection`; Merker (c) Flight-Halter-Abbruch hier neu bewerten.
- `.planning/phases/26-guard-kern/26-REVIEW.md` , offene Infos IN-02 (_home_path_of unquoted den gesamten href-Pfad) und IN-03 (_plain_path lässt Doppel-Slash durch): VOR der Familien-Verdrahtung mitnehmen (Merker aus NEXT.md).

### Requirements und Roadmap
- `.planning/REQUIREMENTS.md` , EXCL-01/03/05/06, SBX-01/02 (wörtlicher Requirement-Text ist bindend), D-v1.7-01..03, Out-of-Scope-Liste.
- `.planning/ROADMAP.md` , Phase-27-Erfolgskriterien 1-5 (Live-Messungen gegen echte Nextcloud, prepare_context-Wanduhr, talk_browse-Messung, Degradations-Kriterium).

### Guard und Muster im Code
- `src/mcp_connector/nextcloud/exclusion.py` , der in Phase 26 gebaute Guard (TagScope drei Zustände, ExclusionGuard Single-Flight, TAG_BUDGET 15 s, excludes wirft bei unverifiable).
- `src/mcp_connector/nextcloud/clients/systemtags.py` , policy-freie Tag-Abfrage (Tag-Liste, REPORT auf die Home-Wurzel, Rohstatus).
- `src/mcp_connector/nextcloud/clients/dav.py` , Segmentregel/within, home_entries, Upload-Fehlerpfade ("A file already exists" / "The parent folder ... does not exist", Zeilen ~678/~691/~739/~751) als Wortlaut-Vorlage für D-27-01.
- `src/mcp_connector/tools/search.py` , bestehendes degraded/skipped-Idiom (D-27-03/04-Anker).
- `src/mcp_connector/tools/context.py` , degraded-Idiom von prepare_context ("jeder Cap benennt sich"; D-v1.7-02 ist die dokumentierte Ausnahme).
- `src/mcp_connector/tools/talk.py` , Platzhalter-Mechanik (`_PLACEHOLDER`, Substitution ~Zeile 575; Unbekannt-Pfad lässt {placeholder} roh stehen) als D-27-06-Anker.
- `vulture_whitelist.py` , Abschnitt "The guard core of phase 26, wired in by phase 27" räumen (Merker (e)).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `nextcloud/exclusion.py` (Phase 26): fertiger Guard, request-gebunden, noch nirgends eingehängt , diese Phase verdrahtet ihn.
- `tools/search.py`: degraded-Liste + skipped-Zähler existieren; Tag-Drops laufen daran vorbei (D-27-04).
- `tools/context.py`: degraded-Einträge je Cap; die Tag-Rückhaltung bleibt dort im Erfolgsfall unsichtbar (dokumentierte Ausnahme D-v1.7-02).
- `tools/talk.py`: Unbekannt-Platzhalter-Pfad ist der fertige Mechanismus für D-27-06.
- `clients/dav.py`: Fehlertexte der Upload-Pfade als byte-gleiche Vorlage für D-27-01.

### Established Patterns
- Sandbox-Segmentregel (NC_MCP_FILES_ROOT) gilt; die getaggte Menge wird NICHT durch die Sandbox gefiltert (Vorfahr oberhalb der Root wirkt, Phase-26-Erfolgskriterium 3).
- Notes umgehen die Sandbox heute vollständig (kein FILES_ROOT-Bezug in tools/notes.py oder clients/notes.py) , SBX-02 schließt das; Notes sind Dateien, Notiz-Id = fileid ist belegt.
- Tests: pytest + respx (call_count), In-Memory-MCP-Client; Live-Beweise gegen die nc35-Strecke (compose.nc35.yml), Messbericht-Stil mit Kommando + Rohwert.

### Integration Points
- NcClients bekommt das Feld `exclusion: ExclusionGuard = field(default_factory=ExclusionGuard)` (deferred-items (e)).
- Ein REPORT je Tool-Antwort (E3): die Familien holen die Menge einmal am Anfang der Antwort und prüfen alle Einträge dagegen; parallele Teilaufrufe teilen sich die Flight (Single-Flight ist im Guard).
- IN-02/03 (Pfadnormalisierung: href-Unquoting, Doppel-Slash) vor oder mit der Verdrahtung fixen, sonst vergleicht der Guard falsch normalisierte Pfade.

</code_context>

<specifics>
## Specific Ideas

- "Ausgeschlossen = existiert nicht" ist die durchgängige Story: Listings zeigen nichts, Einzelzugriffe antworten wie auf nicht existente Ids (byte-gleich, Phase-28-Paartests bereiten das vor), Uploads scheitern wie an einem fehlenden Elternordner.
- Der systemtags-Suchprovider darf die getaggte Menge nicht verraten (EXCL-03): unified_search muss diesen Provider-Kanal mitbehandeln.
- Eine vor dem Taggen bekannte fileid (fetch) darf nach dem Taggen nichts mehr liefern , Test ausdrücklich gefordert (Erfolgskriterium 2).

</specifics>

<deferred>
## Deferred Ideas

- Obergrenze für die getaggte Menge ({DAV:}limit ungemessen) , Owner-Frage in Phase 29 (deferred-items (a)).
- TTL-Restfenster 60 s des Name-zu-Id-Caches, unsichtbares kein-ki (Admin vs. Nicht-Admin), SQLite-140k-Grenze , Doku in Phase 29 (deferred-items (b)/(d)/(f)).
- Klassifikations-Freeze, Kanarientest, byte-gleiche Paartests, AST-Nadeln , Phase 28.
- EXCL-F02 Store-Text-Erwähnung , reist mit dem nächsten Release.

</deferred>

---

*Phase: 27-familien-anschluss-und-sandbox-parit-t*
*Context gathered: 2026-09-27*
