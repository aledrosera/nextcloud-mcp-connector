# Phase 28: Gates und Beweise - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md, this log preserves the alternatives considered.

**Date:** 2026-09-28
**Phase:** 28-gates-und-beweise
**Areas discussed:** Freeze: Form und Klassen, Kanarientest: Schreibwerkzeuge, Byte-Gleichheit: Umfang, ChatGPT-search ohne degraded

---

## Freeze: Form und Klassen

| Frage | Optionen | Gewählt |
|--------|-------------|----------|
| Klassen | Drei Klassen (liest / schreibt in Dateifläche / nicht betroffen); Zwei Klassen | Drei Klassen (Empfohlen) |
| Ort | Tabelle im Test neben EXPECTED_TOOLS; Metadatum am Werkzeug in server/reg_*.py | Tabelle im Test (Empfohlen) |
| Begründung je "nicht betroffen" | Ja, ein Satz je Eintrag; Nein | Ja (Empfohlen) |
| Gegenprobe | Probe-Werkzeug zur Laufzeit im Test registrieren; Claude entscheidet | Im Test registrieren (Empfohlen) |

**User's choice:** alle Empfehlungen

---

## Kanarientest: Schreibwerkzeuge

| Frage | Optionen | Gewählt |
|--------|-------------|----------|
| Schreiber | Echt mit neutralen Argumenten auf Wegwerfinstanz; nur Leser live, Schreiber per Unit | Echt (Empfohlen) |
| Echo | Marker nie in Argumenten; Marker als Suchwort mit Echo-Ausnahme | Marker nie in Argumenten (Empfohlen) |
| Ausfall | Beide Modi; nur Normalbetrieb | Beide Modi (Empfohlen) |
| Ort und Tiefe | CI plus nc35, alle Seiten inkl. cursors; nur CI, erste Seite | CI plus nc35, alle Seiten (Empfohlen) |

**User's choice:** alle Empfehlungen

---

## Byte-Gleichheit: Umfang

| Frage | Optionen | Gewählt |
|--------|-------------|----------|
| Umfang | Jedes Werkzeug, das ein Objekt adressiert (inkl. Schreiber mit Ziel); nur lesende Einzelzugriffe | Jedes adressierende Werkzeug (Empfohlen) |
| Ebene | Unit und live; nur Unit | Unit und live (Empfohlen) |
| Timing | Nein, Restrisiko dokumentieren; ja, messen und angleichen | Nein, Restrisiko (Empfohlen) |
| Vergleich | Ganzes Ergebnis, Id normalisiert; nur Fehlertext | Ganzes Ergebnis (Empfohlen) |

**User's choice:** alle Empfehlungen

---

## ChatGPT-search ohne degraded

| Option | Description | Selected |
|--------|-------------|----------|
| Hinnehmen, testen, dokumentieren | Schema bleibt, Beweis nur "nichts Getaggtes im Ausfall", Doku Phase 29 | ✓ |
| Im Ausfall ganz abweisen | einheitlicher ToolError, kostet alle Nicht-Datei-Treffer | |
| Zusatzfeld neben results | degraded-Schlüssel, Verträglichkeit mit ChatGPT ungemessen | |

**User's choice:** Hinnehmen, testen, dokumentieren (Empfohlen)

---

## Claude's Discretion

- EXCL-07 AST-Nadeln: schreibende Verben auf systemtags-relations und systemtags verboten, PROPFIND/REPORT erlaubt, Beweiszeile und Gegenprobe je Nadel; alte Datei-Tags (oc:tags, Favoriten) nach Research. Owner bestätigte mit "Bereit für CONTEXT.md".
- Namen der Klassen, Tabellenform, Weg zum erzwungenen Ausfall live.

## Deferred Ideas

- Timing-Orakel und ChatGPT-search-Ausfallhinweis: akzeptierte Risiken, Doku Phase 29.
- Expired-Seiten-Hinweis (Issue #11), Device Grant: nicht Teil von 28.
