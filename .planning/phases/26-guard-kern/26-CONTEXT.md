# Phase 26: Guard-Kern - Context

**Gathered:** 2026-09-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Eine policy-freie Tag-Abfrage und ein request-gebundener Guard stehen unabhängig testbar bereit, beantworten je Tool-Aufruf mit genau einem Roundtrip, ob ein Pfad oder eine fileid ausgeschlossen ist, und unterscheiden "nichts getaggt" hart von "nicht prüfbar". Kein Werkzeug wird in dieser Phase angefasst (Familien-Anschluss ist Phase 27). Requirements: EXCL-02, EXCL-04.

</domain>

<decisions>
## Implementation Decisions

### Ordner-Ausschlussliste
- **D-26-01:** Das kein-ki-Tag auf einem Ordner IST die freie Ordner-Ausschlussliste. Es gibt KEINE zweite, konfigurierbare Liste (keine Pfadliste in Einstellungen). Begründung: ein Mechanismus, keine zweite Fail-open-Stelle, kein Drift zwischen zwei Quellen der Wahrheit. (Owner 27.09., Empfehlung übernommen)

### Admin-Schalter
- **D-26-02:** KEIN Admin-Schalter zum Deaktivieren des Filters. Der Guard ist immer aktiv, sobald das Tag existiert; existiert kein kein-ki-Tag, filtert nichts (Zustand "kein Tag" deckt den Normalfall ab). Bei "nicht prüfbar" gilt fail-closed mit klarer Meldung statt Abschaltmöglichkeit. Differenzierer gegen den fail-open-Konkurrenten. (Owner 27.09., Empfehlung übernommen)

### Aus Phase 25 übernommene Owner-Entscheide (gelten unverändert, nicht neu verhandeln)
- **D-25-05 (Messbericht, wörtlich dokumentiert):** Fail-closed-Auslöser ist der REPORT-Ausgang: 207 = Menge ermittelt; 412 = Tag-Id genau einmal neu auflösen, dann erneut versuchen; jeder andere Ausgang (Fehler, Timeout, zweiter 412) = "nicht prüfbar". Die Capability systemtags.enabled wird NICHT befragt (auf NC 32-34 wegen APCu in beide Richtungen unzuverlässig).
- **E3 (Messbericht, 27.09., "wie die empfehlung"):** Ein REPORT je Antwort (report-je-antwort), EXCL-02 bleibt unverändert. Die getaggte Menge wird nie über den Aufruf hinaus gecacht; nur die Auflösung Name zu Tag-Id ist prozessweit gecacht.
- **EXCL-05-Vorentscheid:** Notiz-Id = fileid ist belegt (doppelt), der Notes-Anschluss wird in Phase 27 gebaut (nicht hier).

### Claude's Discretion
- Zuschnitt der Module (Tag-Abfrage vs. Guard), Namensgebung, Testaufbau.
- Timeout-Budget des REPORT und Fehlerkontrakt des Guards gegenüber den Familien, solange die drei Zustände hart getrennt bleiben und die Erfolgskriterien (respx call_count, Single-Flight nach oauth/jwks.py-Muster, Name-zu-Id-Cache nach capabilities.py-Muster, bestehende Segmentregel für den Subtree) erfüllt sind.
- Umgang mit der dokumentierten SQLite-Grenze (140k Zuordnungen, ~240 s aus Phase 25): in Phase 26 nur als bekannte Grenze berücksichtigen, Dokumentation davon ist Phase 29.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Messbefunde und Owner-Entscheide (Grundlage aller Ableitungen)
- `.planning/phases/25-mess-spike-tag-abfrage/25-MESSBERICHT.md` , Alle Messzahlen (REPORT 1/100/5000, App-aus-Verhalten NC 32-35, 412-Verhalten, Varianten, Zielpfad, Freigabe-Grenze, PG-Gegenmessung) und die wörtlichen Owner-Entscheide D-25-05 und E3.
- `.planning/phases/25-mess-spike-tag-abfrage/25-CONTEXT.md` , Entscheidungen des Mess-Spikes (D-25-01..06).

### Requirements und Roadmap
- `.planning/REQUIREMENTS.md` , EXCL-02 und EXCL-04 (wörtlicher Requirement-Text ist bindend; beide stehen auf Pending).
- `.planning/ROADMAP.md` , Phase-26-Erfolgskriterien 1-4 (drei Zustände mit Tests, ein REPORT je Aufruf, Subtree-Segmentregel, Varianten-Vereinigung).

### Muster im Code (von den Erfolgskriterien vorgegeben)
- `src/mcp_connector/oauth/jwks.py` , Single-Flight-Muster für den einen REPORT je Antwort bei parallelen Teilaufrufen.
- `src/mcp_connector/nextcloud/capabilities.py` , Muster für den prozessweiten Name-zu-Tag-Id-Cache.
- `src/mcp_connector/nextcloud/clients/xml.py` , XXE-gehärteter XML-Parser (parse_root) für REPORT-Antworten.
- `src/mcp_connector/nextcloud/clients/dav.py` , bestehender DAV-Client samt Segmentregel für Pfad-Präfixvergleiche.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `oauth/jwks.py`: Single-Flight-Implementierung (ein Fetch bei parallelen Anfragen) , Vorlage für die eine REPORT-Abfrage je Tool-Aufruf.
- `nextcloud/capabilities.py`: prozessweiter Cache mit definierter Invalidierung , Vorlage für den Name-zu-Tag-Id-Cache (412 löst genau einmal neu auf).
- `nextcloud/clients/xml.py`: gehärtetes XML-Parsing für die REPORT-Multistatus-Antwort.
- `scripts/tag_spike.py` (Phase 25): erprobte REPORT-oc:filter-files-Request-Bodies und Antwort-Auswertung als Referenz (Messwerkzeug, nicht Produktionscode; Review-Warnings WR-01..07 beachten, falls Code übernommen wird).

### Established Patterns
- Segmentregel für Pfadvergleiche existiert (Sandbox NC_MCP_FILES_ROOT): /A/kein deckt /A/kein/x, nicht /A/keine. Der Guard nutzt dieselbe Regel; die getaggte Menge wird NICHT durch die Sandbox gefiltert (Vorfahr oberhalb der Root wirkt).
- Tests: pytest + respx (call_count-Messung ist Erfolgskriterium 2), In-Memory-MCP-Client für Contract-Tests.

### Integration Points
- Der Guard wird request-gebunden aufgebaut (je Tool-Aufruf), aber in dieser Phase noch nirgends eingehängt , Phase 27 verdrahtet die Familien.

</code_context>

<specifics>
## Specific Ideas

- Erfolgsantworten im Zustand "kein Tag" müssen byte-gleich zum Stand vor v1.7 sein (Erfolgskriterium 1) , der Guard darf im Normalfall keinerlei Spur in der Antwort hinterlassen.
- Alle gleichnamigen kein-ki-Varianten (Groß-/Kleinschreibung, Sichtbarkeit) werden vereinigt ausgewertet; Testfall mit drei Varianten unterschiedlicher Sichtbarkeit und Schreibweise ist Pflicht (Erfolgskriterium 4).

</specifics>

<deferred>
## Deferred Ideas

- Upload-Orakel (files_upload auf ausgeschlossenen Pfad, ConflictError-Detail) , Phase 27, offene discuss-Frage dort.
- Zählen-vs-Schweigen je Tool-Familie (degraded-Meldungsform) , Phase 27, offene discuss-Frage dort.
- Dokumentation der SQLite-140k-Grenze und wirkungslose-Konfiguration-Prüfkommando , Phase 29.

</deferred>

---

*Phase: 26-guard-kern*
*Context gathered: 2026-09-27*
