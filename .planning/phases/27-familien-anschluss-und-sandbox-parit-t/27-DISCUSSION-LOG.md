# Phase 27: Familien-Anschluss und Sandbox-Parität - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md , this log preserves the alternatives considered.

**Date:** 2026-09-27
**Phase:** 27-Familien-Anschluss und Sandbox-Parität
**Areas discussed:** Upload-Orakel, Zählen vs. Schweigen, Talk-Platzhalter

---

## Upload-Orakel

### Frage 1: Verhalten von files_upload auf einen ausgeschlossenen Pfad

| Option | Description | Selected |
|--------|-------------|----------|
| Wie nicht existent (Empfohlen) | Upload immer abweisen, Wortlaut byte-gleich zu "The parent folder ... does not exist"; Grenzfall direkt getaggte Datei: Claude wählt den konsistentesten Wortlaut | ✓ |
| Neutraler Einheitsfehler | Eigener neutraler Wortlaut, identisch ob belegt oder frei; schwaches Rest-Orakel "hier ist etwas ausgeschlossen" | |
| Erlauben wenn frei | Upload in den Teilbaum erlauben, nur Konflikt maskieren; verletzt das Erfolgskriterium (Erfolg vs. Abweisung ist das Orakel) | |

**User's choice:** Wie nicht existent (Empfohlen)

### Frage 2: files_upload/upload_binary bei "nicht prüfbar"

| Option | Description | Selected |
|--------|-------------|----------|
| Abweisen, klare Meldung (Empfohlen) | Fail-closed auch beim Schreiben, Wortlaut einheitlich mit den Lese-Familien | ✓ |
| Durchlassen | Uploads erzeugen nur Neues; Risiko: Konflikt-Orakel offen, Schreiben in ausgeschlossenen Teilbaum möglich | |

**User's choice:** Abweisen, klare Meldung (Empfohlen)

---

## Zählen vs. Schweigen

### Frage 1: Meldeform des Zustands "nicht prüfbar" je Tool-Familie

| Option | Description | Selected |
|--------|-------------|----------|
| Geteilt nach Zugriffsart (Empfohlen) | Listen-Familien: Einträge zurückhalten + degraded-Eintrag im bestehenden Idiom; Einzelzugriffe: einheitlicher ToolError für alle Ids | ✓ |
| Überall degraded-Eintrag | Auch Einzelzugriffe leer + degraded; schwerer zu deuten als ein klarer Fehler | |
| Überall ToolError | Alles bricht ab, wirft auch nicht-dateitragende Bündel-Teile (Kalender, Mail) weg | |

**User's choice:** Geteilt nach Zugriffsart (Empfohlen)

### Frage 2: Bestehender skipped-Zähler in unified_search vs. Tag-Ausschluss

| Option | Description | Selected |
|--------|-------------|----------|
| Nur Sandbox zählt (Empfohlen) | skipped bleibt für unbrauchbare/Sandbox-Treffer; Tag-Drops lautlos; Sandbox-Drop vor Tag-Prüfung erlaubt | ✓ |
| skipped ganz entfernen | Nimmt dem Assistenten dokumentierte Information, ändert getestetes Verhalten ohne Not | |
| Tag zählt mit | Verletzt D-v1.7-02 (Existenz-Orakel) | |

**User's choice:** Nur Sandbox zählt (Empfohlen)

### Frage 3: Wortlaut/Schlüssel des degraded-Eintrags

| Option | Description | Selected |
|--------|-------------|----------|
| Ein Wortlaut überall (Empfohlen) | Gemeinsame Konstante (z.B. "exclusion check unavailable") in degraded, ToolErrors und Upload-Abweisung | ✓ |
| Familienspezifisch | Eigener Text je Familie; kostet Konsistenz und Doku | |
| Du entscheidest | Claude legt Wortlaut/Schlüssel fest | |

**User's choice:** Ein Wortlaut überall (Empfohlen)

---

## Talk-Platzhalter

### Frage 1: Ersatz für den Dateinamen einer getaggten geteilten Datei (EXCL-06)

| Option | Description | Selected |
|--------|-------------|----------|
| Roher Platzhalter (Empfohlen) | Behandeln wie Eintrag ohne Namen: {file} bleibt roh im Text, wie der bestehende Unbekannt-Pfad; kein neuer Marker, kein Orakel | ✓ |
| Nachricht ganz zurückhalten | Versteckt mehr, aber Lückenmuster fällt auf, harmloser Kontext geht verloren | |
| Generisches Wort | Fester Ersatztext "[Datei]"; eigener Marker, unterscheidbar vom Unbekannt-Fall, schwaches Orakel | |

**User's choice:** Roher Platzhalter (Empfohlen)

---

## Claude's Discretion

- Wortlaut des Grenzfalls direkt getaggte Datei bei Upload (dokumentiert im Plan)
- Konstantenname/Schlüssel des einheitlichen Degradations-Wortlauts
- Verdrahtungsreihenfolge, Planzuschnitt, Teststrategie, Messläufe
- Flight-Halter-Abbruch (deferred-items (c)): neu bewerten, falls Abbrüche häufig

## Deferred Ideas

- Keine neuen. Bestehende Merker: Obergrenze getaggte Menge (Phase 29), TTL-Restfenster/unsichtbares Tag/SQLite-Grenze (Doku Phase 29), Gates (Phase 28), EXCL-F02 Store-Text (nächstes Release).
