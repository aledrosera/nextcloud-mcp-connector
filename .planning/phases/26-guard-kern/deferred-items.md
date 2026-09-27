# Phase 26: Merker für Phase 27 und 29

Punkte, die Phase 26 bewusst nicht löst. Jeder Punkt nennt die Phase, in der er aufgegriffen wird.

## (a) Obergrenze für die getaggte Menge

- Phase 26 setzt bewusst keine Obergrenze für die Zahl der getaggten Knoten.
- Grund: Eine Obergrenze würde aus einem gültigen 207 ein "nicht prüfbar" machen und damit von D-25-05 abweichen (207 = Menge, 412 = einmal neu auflösen, alles andere = nicht prüfbar).
- Owner-Frage, Merker für Phase 29: Soll es eine Obergrenze geben? `{DAV:}limit` wirkt laut Quelltext von FilesReportPlugin, ist aber ungemessen.

## (b) TTL-Restfenster von 60 s

- Der Name-zu-Id-Cache (`_tag_ids`, `TTL_SECONDS = 60.0`) sieht eine per DB-Direktzugriff neu entstandene zweite Schreibweise von kein-ki bis zu 60 s lang nicht (Annahme A4).
- Ab Nextcloud 32 verhindert der Server neue Groß/Klein-Dubletten beim Anlegen; das Fenster betrifft nur Eingriffe an der Datenbank vorbei.
- Doku in Phase 29.

## (c) Abbruch des Flight-Halters

- Wird der Task abgebrochen, der die Abfrage-Flight eines `ExclusionGuard` hält, speichert der Guard nichts; der nächste Aufrufer startet eine zweite Flight (Pitfall 8).
- Fail-closed bleibt erhalten, nur die Kosten verdoppeln sich.
- Kein `asyncio.shield` in Phase 26; falls Phase 27 Abbrüche häufig sieht, dort neu bewerten.

## (d) SQLite-Grenze bei rund 140k Zuordnungen

- Auf SQLite dauert der REPORT bei rund 140k Tag-Zuordnungen länger als `TAG_BUDGET = 15.0` s.
- Der Guard ist dort konstruktionsbedingt immer "nicht prüfbar" (Grund `timeout`).
- Doku in Phase 29 (Betriebshinweis: PostgreSQL oder MySQL/MariaDB für große Bestände).

## (e) NcClients-Feld und Vulture-Abschnitt

- Phase 27 hängt `exclusion: ExclusionGuard = field(default_factory=ExclusionGuard)` an `NcClients` (in Phase 26 bewusst kein Feld, RESEARCH Open Question 3).
- Phase 27 räumt den Abschnitt "The guard core of phase 26, wired in by phase 27" in `vulture_whitelist.py` (derzeit `_.excludes`) und entscheidet über `_.is_collection` (lesen oder Feld entfernen).

## (f) Unsichtbares kein-ki

- Ein unsichtbarer Tag kein-ki wirkt für Admins (sie sehen ihn in der Tag-Liste), nicht für Nicht-Admins (Quellbefund C).
- Der Cache-Schlüssel je `(base_url, user)` verhindert, dass Admin-Ids einen Nicht-Admin bedienen.
- Doku in Phase 29.
