---
created: 2026-09-30
title: Phase 29 Restliste kein-ki (aus Review Phase 28, Owner-Entscheid 30.09.)
area: docs
---

- Doku-Grenze: Suchprovider von Drittanbieter-Apps sind nicht klassifiziert; benennen sie Dateien ohne fileId/Pfad/`/f/`-Link, blendet der Tag sie nicht aus (WR-02, Laufzeit bleibt fail-open). Spaeter ggf. Admin-Option "strict", Standard aus.
- Doku-Grenze: Tables-Freitextzellen mit `/f/<id>` bleiben ungefiltert (WR-03, D-28-18).
- Doku-Grenze oder Angleichung: IN-02, Talk-Datei-Raum-Orakel bei ausfallender Pfadsuche.

**Erledigt 2026-10-01 (Phase 29):** alle drei Grenzen stehen in docs/exclusion.md (und .de/.fr) unter den Ankern `limit-third-party-providers`, `limit-tables-free-text` und `limit-talk-file-room`.
