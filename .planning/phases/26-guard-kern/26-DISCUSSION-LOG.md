# Phase 26: Guard-Kern - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md , this log preserves the alternatives considered.

**Date:** 2026-09-27
**Phase:** 26-guard-kern
**Areas discussed:** Ordner-Ausschlussliste, Admin-Schalter

---

## Ordner-Ausschlussliste

| Option | Description | Selected |
|--------|-------------|----------|
| Nur das Tag (Empfohlen) | Ein Mechanismus: Ordner taggen = ausgeschlossen samt Subtree. Keine zweite Konfigurationsstelle, damit keine zweite Fail-open-Stelle und kein Drift zwischen zwei Listen. Deckt sich mit der Recherche-Empfehlung und der Phase-25-Messung (Subtree per Praefixregel). | ✓ |
| Tag + Pfadliste | Zusaetzlich eine konfigurierbare Pfadliste (Admin- oder Nutzer-Einstellung). Flexibler fuer Admins ohne Tag-Rechte, aber zweite Quelle der Wahrheit, eigene Fail-closed-Logik und mehr Testflaeche. | |

**User's choice:** Nur das Tag (Empfohlen)
**Notes:** Entspricht der Recherche-Empfehlung aus der Roadmap (zweite Liste waere eine zweite Fail-open-Stelle).

---

## Admin-Schalter

| Option | Description | Selected |
|--------|-------------|----------|
| Nein, keine Abschaltung (Empfohlen) | Der Filter ist immer aktiv, sobald das Tag existiert; existiert kein Tag, filtert nichts. Bei "nicht pruefbar" klare Meldung statt Schalter. Keine Fail-open-Konfiguration, weniger Supportflaeche. Recherche-Empfehlung; Differenzierer gegen den Konkurrenten (fail-open). | ✓ |
| Ja, Admin-Schalter | ExApp-Einstellung (Admin), die den Guard abschaltet, z.B. fuer Fehlersuche oder Instanzen mit SQLite-Latenzproblem (140k-Zuordnungen-Grenze aus Phase 25). Preis: eine dokumentierte Fail-open-Stelle samt Tests und Doku. | |

**User's choice:** Nein, keine Abschaltung (Empfohlen)
**Notes:** Keine.

---

## Claude's Discretion

- Modulzuschnitt (Tag-Abfrage vs. Guard), Namensgebung, Testaufbau.
- Timeout-Budget des REPORT und Fehlerkontrakt des Guards, solange die drei Zustaende hart getrennt bleiben und die Erfolgskriterien erfuellt sind.
- Umgang mit der SQLite-140k-Grenze innerhalb der Phase (Doku davon ist Phase 29).

## Deferred Ideas

- Upload-Orakel (files_upload auf ausgeschlossenen Pfad) , Phase 27.
- Zaehlen-vs-Schweigen je Tool-Familie , Phase 27.
- Doku der SQLite-Grenze + Pruefkommando , Phase 29.
