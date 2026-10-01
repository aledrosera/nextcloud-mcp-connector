# Phase 29: Prüfkommando und Doku - Context

**Gathered:** 2026-10-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Ein `occ mcp_connector:exclusion:check`, mit dem eine Administration ohne Live-Sitzung und ohne Zustandsänderung an der Nextcloud sieht, ob ihr `kein-ki`-Tag wirkt (OPS-01), und eine dreisprachige Doku (docs/ + README-Abschnitt), die Einrichtung, Betriebsarten, Prüfkommando und alle ehrlichen Grenzen aus den gemessenen Befunden beschreibt (DOC-03). Letzte Phase von v1.7. Store-Texte bleiben unverändert (EXCL-F02 reist mit dem nächsten Release).

</domain>

<decisions>
## Implementation Decisions

### Übernommen aus früheren Phasen (nicht neu verhandelt)
- **D-26-01:** Das `kein-ki`-Tag auf einem Ordner IST die Ausschlussliste; keine zweite, konfigurierbare Liste. Das Prüfkommando prüft also nur das Tag.
- **D-26-02:** Kein Admin-Schalter, kein konfigurierbarer Tag-Name (`EXCLUDE_TAG = "kein-ki"`, Vergleich ohne Groß/Klein, `src/mcp_connector/nextcloud/exclusion.py`). Damit ist der offene Roadmap-Punkt "hängt an den Entscheiden aus Phase 26" beantwortet.
- **Owner 30.09. (28-REVIEW.md, Owner decisions):** WR-02 bleibt zur Laufzeit fail-open und wird als Grenze dokumentiert; WR-03-Freitext und IN-02 kommen als Grenzen in die Doku.

### Prüfkommando: Befunde
- **D-29-01:** Neben den Pflichtschritten (Tag existiert, ist sichtbar, gleichnamige Varianten / Tippfehler wie "Kein KI", "keinki") erkennt und meldet das Kommando die **Betriebsart**: Selbstbedienung (jeder darf zuweisen, kollaborativ) oder Organisationsmodus (eingeschränktes Tag, Zuweisung nur durch delegierte Gruppe(n), Gruppen werden genannt), jeweils mit einem Satz, was das für die Nutzer heißt.
- **D-29-02:** Das Kommando meldet die **Anzahl** der Objekte, denen `kein-ki` zugewiesen ist, ohne Namen, Pfade oder Konten. Keine Liste.
- **D-29-03:** Gibt es kein `kein-ki`-Tag, ist das ein **Hinweis, kein Fehler** (`passed` bleibt true): "kein Tag vorhanden, der Connector filtert nichts", plus wie man es anlegt. Fehlkonfigurationen (unsichtbares Tag, nur Tippfehler-Variante vorhanden) sind dagegen nicht bestanden.
- Erfolgskriterien der Roadmap bleiben: läuft ohne Sitzung, ändert nichts (Vorher-nachher-Vergleich der Tag- und Zuordnungstabellen leer), gegen eine echte Instanz für unsichtbares Tag und Tippfehler belegt.

### Prüfkommando: Ausgabe
- **D-29-04:** Gleiches Muster wie `exchange:check` (`src/mcp_connector/exapp/exchange_check.py`): lesbarer Text je Prüfschritt, zusätzlich `--json` mit Schlüssel `passed`; der Exit-Code ist über AppAPI immer 0 und wird so dokumentiert, Monitoring liest `passed`.

### Grenzen-Doku
- **D-29-05:** **Alle Grenzen einzeln**, je ein Satz Wirkung plus Verweis auf den Befund (Phase 25 Messbericht bzw. die Phase-26/27/28-Entscheide): Freigabe-Grenze (Tag oberhalb der Freigabe-Wurzel wirkt beim Empfänger nicht), unsichtbares Tag wirkt nicht, App-aus-Verhalten, Timing-Orakel (D-28-12), `search` im Ausfall (D-28-13), `notes_create`-Restorakel (D-28-16), Suchprovider von Drittanbieter-Apps (WR-02), Tables-Freitext mit `/f/<id>` (WR-03), Talk-Datei-Raum-Orakel bei ausfallender Pfadsuche (IN-02).

### Doku-Aufbau und README
- **D-29-06:** Eine eigene Seite je Sprache: `docs/exclusion.md` (EN), `docs/exclusion.de.md`, `docs/exclusion.fr.md`, Inhalt: Einrichtung, Betriebsarten, Prüfkommando, Grenzen. Deutsch mit echten Umlauten, keine Gedankenstriche.
- **D-29-07:** README.md / README.de.md / README.fr.md bekommen je einen **kurzen Abschnitt** (3 bis 4 Zeilen): was das Tag tut, die wichtigste Grenze in einem Satz, Link auf die Doku-Seite der Sprache.
- **D-29-08:** Die Doku enthält eine **Schritt-für-Schritt-Anleitung mit occ-Befehlen** für beide Betriebsarten (Tag anlegen; eingeschränktes Tag mit Gruppen-Delegation; Kontrolle mit dem Prüfkommando), gegen nc35 nachgemessen, Befehle und Ausgaben als Rohbeleg.

### Claude's Discretion
- Wortlaut und Reihenfolge der Prüfschritte, Schlüsselnamen im `--json` (am exchange:check-Schema orientiert), Erkennung der Tippfehler-Varianten (Normalisierung von Leerzeichen, Bindestrich, Groß/Klein), technische Umsetzung der Zählung ohne Zustandsänderung.

### Folded Todos
- `.planning/todos/pending/2026-09-30-phase29-restliste-kein-ki.md` (Owner-Entscheid 30.09.): Drittanbieter-Provider, Tables-Freitext, IN-02 als Grenzen in die Doku (in D-29-05 aufgenommen).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Anforderungen und Ziel
- `.planning/REQUIREMENTS.md` - OPS-01, DOC-03, EXCL-F02
- `.planning/ROADMAP.md` - Phase 29, Erfolgskriterien 1 bis 4

### Befunde und Entscheide, auf die die Doku verweist
- `.planning/phases/25-mess-spike-tag-abfrage/25-MESSBERICHT.md` - gemessene Grenzen (Freigabe-Grenze, unsichtbares Tag, App aus)
- `.planning/phases/26-guard-kern/26-CONTEXT.md` - D-26-01, D-26-02
- `.planning/phases/27-familien-anschluss-und-sandbox-parit-t/27-CONTEXT.md` - Verhalten bei "nicht prüfbar", Einheitswortlaut
- `.planning/phases/28-gates-und-beweise/28-CONTEXT.md` - D-28-12, D-28-13, D-28-16 (akzeptierte Restrisiken)
- `.planning/phases/28-gates-und-beweise/28-REVIEW.md` - WR-02, WR-03, IN-02 und Owner decisions
- `.planning/phases/28-gates-und-beweise/28-SECURITY.md` - akzeptierte Risiken A-28-01 bis A-28-09

### Muster für das Kommando
- `src/mcp_connector/exapp/exchange_check.py` - Text/--json/passed, Exit-Code-Verhalten
- `src/mcp_connector/exapp/occ.py` - Registrierung der occ-Kommandos
- `docs/exchange-evidence.md` - Form eines Rohbelegs für ein Prüfkommando
- `src/mcp_connector/nextcloud/exclusion.py` - Tag-Name, Vergleich, Guard-Zustände

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `exapp/exchange_check.py`: komplette Vorlage für ein AppAPI-occ-Prüfkommando (Route, Guard, Text- und JSON-Antwort, `passed`).
- `nextcloud/exclusion.py`: Tag-Suche und Vergleichslogik des Guards, wiederverwendbar für "existiert / sichtbar".
- nc35-Harness (`compose.nc35.yml`, `tests/integration/topology.py`) und Kanarienwelt für Live-Belege.

### Established Patterns
- Prüfkommandos laufen über AppAPI ohne Nutzersitzung, Exit-Code immer 0, Ergebnis in `passed`.
- Live-Belege als Rohprotokoll (Kommando + Rohwert) unter `.planning/phases/<n>/raw/`.
- docs/ war bisher einsprachig (EN); README dreisprachig. Phase 29 führt `.de.md`/`.fr.md` für die Doku-Seite ein.

### Integration Points
- occ-Kommando-Registrierung in `appinfo/info.xml` bzw. `exapp/occ.py`.
- README-Abschnitte in allen drei READMEs.

</code_context>

<specifics>
## Specific Ideas

- Vorher-nachher-Vergleich der Tag- und Zuordnungstabellen als Beweis "ändert nichts" (Muster exchange:check).
- Organisationsmodus-Anleitung so, dass ein Behörden-Admin die occ-Befehle kopieren kann.

</specifics>

<deferred>
## Deferred Ideas

- Admin-Option "strict" (unbekannte Suchprovider fail-closed), Standard aus: Kandidat für einen späteren Meilenstein, falls ein Kunde strikte Garantie braucht.
- Store-Texte zum Ausschluss-Tag (EXCL-F02): reisen mit dem nächsten Release.

</deferred>

---

*Phase: 29-pr-fkommando-und-doku*
*Context gathered: 2026-10-01*
