# Phase 26: Guard-Kern - Research

**Researched:** 2026-09-27
**Domain:** Request-gebundene Ausschlussprüfung über Nextcloud-System-Tags: `PROPFIND /remote.php/dav/systemtags/` (Name zu Id), `REPORT oc:filter-files` (getaggte Menge), Single-Flight je Tool-Aufruf, prozessweiter Name-zu-Id-Cache, Drei-Zustands-Modell, Segmentregel für Subtrees
**Confidence:** HIGH für alle Aussagen über die eigene Codebasis (Datei und Zeile gelesen) und für das REPORT-Verhalten (Messbericht Phase 25 plus Server-Quelltext stable32/stable33/master gelesen); MEDIUM für `{DAV:}limit` im REPORT (Quelltext gelesen, nicht gemessen); Timeout-Budget und Namensnormalisierung sind begründete Empfehlungen im Ermessensraum

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Ordner-Ausschlussliste
- **D-26-01:** Das kein-ki-Tag auf einem Ordner IST die freie Ordner-Ausschlussliste. Es gibt KEINE zweite, konfigurierbare Liste (keine Pfadliste in Einstellungen). Begründung: ein Mechanismus, keine zweite Fail-open-Stelle, kein Drift zwischen zwei Quellen der Wahrheit. (Owner 27.09., Empfehlung übernommen)

#### Admin-Schalter
- **D-26-02:** KEIN Admin-Schalter zum Deaktivieren des Filters. Der Guard ist immer aktiv, sobald das Tag existiert; existiert kein kein-ki-Tag, filtert nichts (Zustand "kein Tag" deckt den Normalfall ab). Bei "nicht prüfbar" gilt fail-closed mit klarer Meldung statt Abschaltmöglichkeit. Differenzierer gegen den fail-open-Konkurrenten. (Owner 27.09., Empfehlung übernommen)

#### Aus Phase 25 übernommene Owner-Entscheide (gelten unverändert, nicht neu verhandeln)
- **D-25-05 (Messbericht, wörtlich dokumentiert):** Fail-closed-Auslöser ist der REPORT-Ausgang: 207 = Menge ermittelt; 412 = Tag-Id genau einmal neu auflösen, dann erneut versuchen; jeder andere Ausgang (Fehler, Timeout, zweiter 412) = "nicht prüfbar". Die Capability systemtags.enabled wird NICHT befragt (auf NC 32-34 wegen APCu in beide Richtungen unzuverlässig).
- **E3 (Messbericht, 27.09., "wie die empfehlung"):** Ein REPORT je Antwort (report-je-antwort), EXCL-02 bleibt unverändert. Die getaggte Menge wird nie über den Aufruf hinaus gecacht; nur die Auflösung Name zu Tag-Id ist prozessweit gecacht.
- **EXCL-05-Vorentscheid:** Notiz-Id = fileid ist belegt (doppelt), der Notes-Anschluss wird in Phase 27 gebaut (nicht hier).

### Claude's Discretion
- Zuschnitt der Module (Tag-Abfrage vs. Guard), Namensgebung, Testaufbau.
- Timeout-Budget des REPORT und Fehlerkontrakt des Guards gegenüber den Familien, solange die drei Zustände hart getrennt bleiben und die Erfolgskriterien (respx call_count, Single-Flight nach oauth/jwks.py-Muster, Name-zu-Id-Cache nach capabilities.py-Muster, bestehende Segmentregel für den Subtree) erfüllt sind.
- Umgang mit der dokumentierten SQLite-Grenze (140k Zuordnungen, ~240 s aus Phase 25): in Phase 26 nur als bekannte Grenze berücksichtigen, Dokumentation davon ist Phase 29.

### Deferred Ideas (OUT OF SCOPE)
- Upload-Orakel (files_upload auf ausgeschlossenen Pfad, ConflictError-Detail) , Phase 27, offene discuss-Frage dort.
- Zählen-vs-Schweigen je Tool-Familie (degraded-Meldungsform) , Phase 27, offene discuss-Frage dort.
- Dokumentation der SQLite-140k-Grenze und wirkungslose-Konfiguration-Prüfkommando , Phase 29.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| EXCL-02 | Subtree-Semantik: ein Tag auf einem Ordner deckt alles darunter; die getaggte Menge wird einmal je Antwort geholt (REPORT oc:filter-files) und per Praefixvergleich nach der bestehenden Segmentregel geprueft, nie ueber den Aufruf hinaus gecacht (nur die Aufloesung Name zu Tag-Id darf prozessweit gecacht werden, 412 loest einmal neu auf) | Pattern 2 (REPORT auf Home-Wurzel, ungefilterte href-Normalisierung), Pattern 3 (Segmentregel als eine Funktion, Vorfahren-Mengentest), Pattern 4 (Name-zu-Id-Cache, nur positiv, 412-Invalidierung), Pattern 1 (Single-Flight je Aufruf). Quellbefund A: mehrere `oc:systemtag`-Regeln in einem REPORT sind UND, nicht ODER |
| EXCL-04 | Fail-closed mit drei Zustaenden: kein Tag vorhanden = kein Filter; Menge ermittelt = Filter aktiv; Pruefung nicht beantwortbar = betroffene Eintraege zurueckgehalten und die Degradation benannt (nur dann); Erfolgsantworten sind byte-gleich zu "existiert nicht". Massgeblich ist der Erfolg des REPORT, nicht die systemtags-Capability | Pattern 5 (Zustandsautomat mit exakter Zuordnung jedes Ausgangs), Pitfalls 1 bis 6, Code-Beispiel "Zustände als Werte". Das Zurückhalten und die Meldungsform selbst sind Phase 27; Phase 26 liefert die Zustände und den Grund als Wert |
</phase_requirements>

## Summary

Phase 26 baut zwei neue, voneinander getrennt testbare Module und fasst kein Werkzeug an: einen policy-freien Client für die zwei Nextcloud-Aufrufe (Tag-Liste per `PROPFIND Depth 1 /remote.php/dav/systemtags/`, getaggte Knoten per `REPORT oc:filter-files` auf die Home-Wurzel) und eine Policy-Schicht mit einem pro Tool-Aufruf lebenden Guard, der seine Antwort genau einmal lädt (Single-Flight nach `oauth/jwks.py`), das Ergebnis als einen von drei Zuständen speichert und Pfade sowie fileids dagegen prüft. Der Messbericht aus Phase 25 trägt jede Designentscheidung: der REPORT antwortet bei ausgeschalteter App unverändert (Capability daher nie befragen), eine veraltete oder unsichtbare Id liefert 412 auf allen Versionen 32 bis 35, der Zielpfad filtert nicht, exakt gleichnamige Tags liefert NC bereits vereinigt, eine Variante in anderer Groß-/Kleinschreibung ist getrennt, und PostgreSQL bleibt bei 5000 Treffern unter 0,2 s.

Die wichtigste neue Erkenntnis dieser Research betrifft die Batch-Form: `FilesReportPlugin::processFilterRulesForFileNodes` verknüpft mehrere `oc:systemtag`-Regeln eines REPORT per **Schnittmenge** (`array_uintersect`), auf stable32, stable33 und master identisch [VERIFIED: Quelltext]. Ein REPORT mit den Ids von `kein-ki` und `Kein-KI` liefert also nur Dateien, die beide Tags tragen: ein stilles Fail-open. Varianten in unterschiedlicher Schreibweise brauchen je einen eigenen REPORT innerhalb desselben Single-Flight; exakt gleichnamige Varianten brauchen keinen eigenen, weil NC per Name sucht. Da `createTag` seit NC 32 neue Groß/Klein-Dubletten verhindert [VERIFIED: 25-RESEARCH Quellbefund 1], ist der Normalfall genau ein REPORT; mehrere entstehen nur aus Altbestand.

Zwei Gates der Codebasis greifen direkt in diese Phase: `tests/contract/test_no_destructive_calls.py` verbietet modulweiten veränderlichen Zustand außer genau zwei gezählten Ausnahmen (der Name-zu-Id-Cache ist die dritte und muss dort mit Begründung eingetragen werden, Zähler 2 auf 3) und verbietet das Wort `Resolve` in Codezeilen (ein Klassenname wie `TagResolver` macht die Suite rot). Außerdem meldet das Vulture-Gate den noch nirgends aufgerufenen Guard als toten Code, bis Phase 27 ihn verdrahtet; die Codebasis hat dafür ein etabliertes Muster (Namen mit Begründung in `vulture_whitelist.py` parken und mit dem aufrufenden Plan wieder entfernen).

**Primary recommendation:** Zwei Module `nextcloud/clients/systemtags.py` (roh, policy-frei, liefert Ausgänge als Werte) und `nextcloud/exclusion.py` (Zustände, Guard mit `asyncio.Lock`, Name-zu-Id-Cache `(base_url, user)` mit 60 s TTL nur für nicht-leere Ergebnisse), REPORT immer auf `/remote.php/dav/files/<user>/` mit genau einer `oc:systemtag`-Regel, eine Segmentregel-Funktion in `dav.py` für Sandbox und Guard, jeder Ausgang außer "alle REPORTs 207" und "Liste ohne kein-ki" ist "nicht prüfbar".

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Tag-Liste lesen (Name, Id, Sichtbarkeit) | Nextcloud-Server (DAV `systemtags`) | API/Backend dieses Connectors (Client-Modul) | Sichtbarkeit (`canUserSeeTag`) entscheidet NC im Nutzerkontext; der Connector sieht nie mehr als der Nutzer (Core Value) |
| Getaggte Menge ermitteln | Nextcloud-Server (`REPORT oc:filter-files`) | Client-Modul `clients/systemtags.py` | Ein Roundtrip liefert alle für den Nutzer sichtbaren getaggten Knoten; der Connector erfindet keine Tag-Logik |
| Zustandsentscheidung (kein Tag / aktiv / nicht prüfbar) | API/Backend (`nextcloud/exclusion.py`) | , | Reine Policy über Statuscodes; muss ohne Netz testbar sein |
| Single-Flight je Tool-Aufruf | API/Backend (Guard-Instanz je Aufruf) | , | Request-gebunden; komponierte Tools teilen dieselbe Instanz (Phase 27 hängt sie an `NcClients`) |
| Name-zu-Id-Cache | API/Backend (Modulzustand, D-20-Ausnahme) | , | Instanz-Metadaten ohne Nutzerdaten und ohne Credential, wie `capabilities._cache` |
| Subtree-Prüfung (Segmentregel) | API/Backend (`dav.py`-Funktion, von Sandbox und Guard geteilt) | , | Eine Regel, eine Stelle; zwei Schreibweisen derselben Präfixregel sind der Fehler, den `ids.py` in v1.3 abgeschafft hat |
| Zurückhalten, Meldungsform, Audit-Grund | Tool-Familien (Phase 27) | , | Außerhalb dieser Phase; Phase 26 liefert nur den Zustand und einen Grund als Wert |

## Standard Stack

Keine neuen Abhängigkeiten. Alles läuft auf dem bestehenden Stack.

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| httpx | 0.28.1 (installiert, `uv run python -c "import httpx"`) | PROPFIND und REPORT über `NcClients.client` (`shared_client`, kein Redirect, keine Cookies) | Einziger HTTP-Client des Projekts; per-request `timeout=` möglich [VERIFIED: Codebasis `nextcloud/http.py`] |
| lxml | installiert | Request-Bodies bauen (nie f-String, T-01-11), Antworten über `xml.parse_multistatus` (XXE/DTD-gehärtet) | Bestehende Konvention in `clients/dav.py`, `clients/xml.py` [VERIFIED: Codebasis] |
| asyncio (stdlib) | Python 3.13 | `asyncio.Lock` für Single-Flight, `asyncio.timeout` für das Budget, `asyncio.gather` für mehrere REPORTs einer Flight | Muster aus `oauth/jwks.py` und `tools/context.py` [VERIFIED: Codebasis] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| respx | 0.23.1 (installiert) | `mock.route(method="REPORT", url=...)`, `route.call_count` | Jeder Unit-Test dieser Phase; Methoden-Routen für PROPFIND sind im Projekt etabliert (`tests/unit/test_caldav_client.py:168`) [VERIFIED: Codebasis] |
| pytest + anyio-Plugin | installiert | `@pytest.mark.anyio`, Fixture `anyio_backend` in `tests/conftest.py:14` | Async-Tests wie `tests/unit/test_oauth_jwks.py` [VERIFIED: Codebasis] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Ein REPORT je unterscheidbarer Schreibweise | Alle Ids in einem REPORT | **Falsch**, nicht nur langsamer: UND-Verknüpfung (Quellbefund A), stilles Fail-open |
| REPORT auf Home-Wurzel | REPORT auf Sandbox-Wurzel via `dav.files_url(creds, "/")` | Zielpfad filtert laut Messung zwar nicht, aber `files_url` läuft durch `safe_path` und bildet auf `NC_MCP_FILES_ROOT` ab; semantisch falsch und bricht, falls NC den Zielpfad je filtert |
| `nc:system-tags` je Antwortknoten plus Vorfahren | REPORT | Vom Owner mit E3 verworfen (Entwurf vorfahren-propfind), nicht erneut erwägen |
| ContextVar für den Guard | Instanz am Parameterobjekt | ContextVar hat Kopiersemantik bei `gather`/`create_task`; Milestone-Architektur empfiehlt das Parameterobjekt [CITED: .planning/research/ARCHITECTURE.md Pattern 1] |

**Installation:** keine.

## Package Legitimacy Audit

Diese Phase installiert keine externen Pakete. slopcheck nicht nötig.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| (keine) | , | , | , | , | , | , |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Quellbefunde dieser Research (neu gegenüber Messbericht und Milestone-Research)

### Quellbefund A: Mehrere `oc:systemtag`-Regeln in einem REPORT sind UND
`FilesReportPlugin::processFilterRulesForFileNodes` sammelt alle `oc:systemtag`-Werte, holt die Tags per `getTagsByIds($systemTagIds, $user)` und ruft je Tag `searchBySystemTag($tagName, ...)`; ab dem zweiten Tag wird mit `array_uintersect` geschnitten, bei leerer Zwischenmenge sofort leer zurückgegeben. [VERIFIED: raw.githubusercontent.com nextcloud/server master, stable32, stable33 `apps/dav/lib/Connector/Sabre/FilesReportPlugin.php`, Zeilen 268 bis 281 auf stable32/33]
- **Folge:** Genau eine `oc:systemtag`-Regel je REPORT. Unterscheidbare Schreibweisen (`kein-ki`, `Kein-KI`) je ein REPORT; exakt gleichnamige Tags (public/restricted) nur einmal abfragen, weil `searchBySystemTag` per Name sucht und NC die Vereinigung schon liefert (gemessen: X und Y je `treffer=2 fileids=['955', '957']`, Messbericht K5/G4).
- **Folge 2:** Ist auch nur eine Id eines Mehr-Id-REPORT unbekannt oder unsichtbar, wirft `getTagsByIds` `TagNotFoundException` und der ganze REPORT endet mit 412. Ein Grund mehr für eine Regel je REPORT.
- Die Milestone-Architektur (`.planning/research/ARCHITECTURE.md`) erwähnt die UND-Semantik nicht; dieser Befund ergänzt sie.

### Quellbefund B: `{DAV:}limit` wird im REPORT ausgewertet
`onReport` liest `{DAV:}limit/{DAV:}nresults` und `{http://nextcloud.org/ns}firstresult`; bei genau einem Tag geht das Limit als `$dbLimit` in die Datenbankabfrage, bei mehreren wird nachträglich geschnitten. Ohne `limit` ist `$dbLimit = 0` (unbegrenzt). [VERIFIED: Quelltext stable32/33/master] Nicht gemessen. Relevant nur, falls der Owner eine Obergrenze will (Open Question 2).

### Quellbefund C: Tag-Liste im Nutzerkontext
`SystemTagsByIdCollection::getChildren` liefert für Admins alle Tags, für Nicht-Admins nur sichtbare (`getAllTags($visibilityFilter)` plus `canUserSeeTag`). [VERIFIED: Quelltext stable32 `apps/dav/lib/SystemTag/SystemTagsByIdCollection.php:97-116`] Gemessen: das unsichtbare Tag 63 steht nicht in alices Liste, wohl in der Admin-Liste (raw/nc35-befunde.txt Zeilen 128, 136). Für einen Admin wirkt daher auch ein unsichtbares `kein-ki`; für Nicht-Admins ist es wirkungslos (Doku Phase 29).

### Quellbefund D: Zwei Gates der eigenen Codebasis
- `tests/contract/test_no_destructive_calls.py:285-288` und `:671-676`: `ALLOWED_MODULE_STATE` hat genau zwei Einträge, ein Test prüft `len(...) == 2` ("a third cache is a decision, and a decision has to be made in a review and not in a diff (D-20, T-08-23)"). [VERIFIED: Codebasis]
- Derselbe Test, `:691-703`: die Nadeln `elicit` und `Resolve` (Groß-R) sind in Codezeilen verboten; Kommentare und Docstrings werden vorher ausgeblendet, String-Literale und Bezeichner nicht. [VERIFIED: Codebasis]

## Architecture Patterns

### System Architecture Diagram

```
Tool-Aufruf (Phase 27; in Phase 26 nur Tests)
        |
        v
  ExclusionGuard (eine Instanz je Aufruf)
        |  scope(clients)  <-- parallele Teilaufrufe warten am Lock
        v
  [Lock frei, Zustand schon da?] --ja--> gespeicherter Zustand (0 Roundtrips)
        | nein
        v
  Name-zu-Id-Cache (base_url, user), TTL 60 s, nur nicht-leer
        | Treffer                         | kein Treffer
        |                                 v
        |                  PROPFIND Depth 1 /remote.php/dav/systemtags/
        |                     | nicht 207 / unparsebar --> NICHT PRÜFBAR
        |                     | keine casefold-"kein-ki"-Namen --> KEIN TAG
        |                     v
        |                  Ids je Schreibweise (eine Id je Name) -> Cache
        v
  REPORT oc:filter-files auf /remote.php/dav/files/<user>/, je Schreibweise einer (gather)
        |
        +-- alle 207, alle hrefs im Home abbildbar --> AKTIV(Pfade, fileids)
        +-- mindestens ein 412, noch nicht neu aufgelöst
        |       --> Cache-Eintrag löschen, PROPFIND erneut
        |           --> keine kein-ki-Namen mehr --> KEIN TAG
        |           --> REPORT erneut: alle 207 --> AKTIV, sonst --> NICHT PRÜFBAR
        +-- alles andere (Timeout, Netz, 3xx, 401, 403, 5xx, zweiter 412,
            unparsebar, href außerhalb des Home) --> NICHT PRÜFBAR
        |
        v
  Zustand wird in der Guard-Instanz gespeichert (auch NICHT PRÜFBAR)
        |
        v
  excludes(path, fileid): fileid in Menge ODER ein Vorfahr (inkl. selbst) des Pfads in Menge
```

### Recommended Project Structure
```
src/mcp_connector/nextcloud/
├── clients/systemtags.py   # NEU: roh, policy-frei: list_tags(), tagged_nodes(); Ausgänge als Werte
├── clients/dav.py          # GEÄNDERT (additiv): within(path, root) als eine Segmentregel,
│                           #   home_entries(body, creds) = parse_entries ohne Sandbox-Drop
└── exclusion.py            # NEU: TagScope (3 Zustände), ExclusionGuard (Single-Flight),
                            #   _tag_ids-Cache, EXCLUDE_TAG = "kein-ki"
tests/unit/
├── test_systemtags_client.py  # NEU: Bodies, Parsing, Statusabbildung
├── test_exclusion.py          # NEU: drei Zustände, call_count, 412, Varianten, Segmentregel
└── (bestehend) test_files_list.py u.a. bleiben unverändert grün (dav.py-Änderung ist additiv)
tests/contract/test_no_destructive_calls.py  # GEÄNDERT: dritter Eintrag ALLOWED_MODULE_STATE
vulture_whitelist.py                         # GEÄNDERT: Guard-Namen parken bis Phase 27
```

### Pattern 1: Single-Flight je Tool-Aufruf (Muster `oauth/jwks.py`)
**What:** Eine Guard-Instanz je Tool-Aufruf mit `asyncio.Lock`; der erste Aufrufer lädt, alle anderen warten und bekommen denselben gespeicherten Zustand, auch einen Fehlschlag ("share the refusal, not the cost", `jwks.py:173-176`).
**When to use:** Immer; `prepare_context` holt Suche plus bis zu drei Auszüge parallel (`context.py:752`), das sind die parallelen Teilaufrufe aus Erfolgskriterium 2.
**Wichtig:** Die Signatur `scope(clients)` statt `__init__(clients)` wählen, damit Phase 27 die Klasse ohne Umbau als `field(default_factory=ExclusionGuard)` an das `frozen`/`slots`-Dataclass `NcClients` hängen kann [CITED: .planning/research/ARCHITECTURE.md Pattern 1].
**Example:**
```python
# Muster aus src/mcp_connector/oauth/jwks.py:167-194, auf den Aufruf reduziert
class ExclusionGuard:
    __slots__ = ("_lock", "_scope")

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._scope: TagScope | None = None

    async def scope(self, clients: NcClients) -> TagScope:
        if self._scope is not None:          # schneller Pfad ohne Lock
            return self._scope
        async with self._lock:
            if self._scope is None:          # unter dem Lock erneut prüfen
                self._scope = await load_scope(clients)   # wirft nie für Nextcloud-Ausgänge
            return self._scope
```

### Pattern 2: REPORT auf die Home-Wurzel mit genau einer Regel
**What:** Ziel-URL `{base_url}/remote.php/dav/files/{quote(user, safe='')}/`, Body mit `d:prop` = `oc:fileid` + `d:resourcetype` und genau einem `oc:systemtag`.
**Why:** Der Zielpfad filtert auf keiner Version (Messbericht K5 Zielpfad, 32 bis 35); ein getaggter Vorfahr oberhalb von `NC_MCP_FILES_ROOT` muss drin bleiben (Erfolgskriterium 3).
**hrefs:** über eine ungefilterte Variante von `parse_entries` normalisieren (`dav.home_entries`), nie über `parse_entries` selbst, das per `in_files_root` alles außerhalb der Sandbox verwirft (`dav.py:476-478`).
**Example:** siehe Code Examples "REPORT-Body" und "Tag-Liste".

### Pattern 3: Eine Segmentregel, von Sandbox und Guard geteilt
**What:** Die Regel `root == "/" or path == root or path.startswith(root + "/")` steht heute in `dav.in_files_root` (`dav.py:489-490`) und sinngleich in `safe_path` (`dav.py:120`). Als Funktion `within(path, root)` herauslösen, `in_files_root` darauf umstellen (Verhalten unverändert, bestehende Tests decken es).
**Guard-Anwendung:** Nicht jede getaggte Wurzel gegen jeden Pfad testen (O(n x m) bei bis zu 5000 Treffern mal bis zu 100 Einträgen), sondern die Vorfahren des Pfads aufzählen (`/A/kein/x` ergibt `/A/kein/x`, `/A/kein`, `/A`, `/`) und gegen die Pfadmenge testen. Für normalisierte absolute Pfade ist das äquivalent zu `any(within(path, t) for t in tagged)`; ein parametrisierter Test hält die Äquivalenz fest (inklusive `/A/kein` gegen `/A/keine`).
**Alle getaggten Pfade in die Menge**, Dateien und Ordner: Eine getaggte Datei deckt dann genau sich selbst (Gleichheit), ein Ordner seinen Teilbaum. Das ist einfacher als die Unterscheidung in der Milestone-Architektur und schließt den Fall ab, in dem ein Aufrufer nur den Pfad kennt.

### Pattern 4: Name-zu-Id-Cache nach `capabilities.py`
**What:** Modul-Dict `_tag_ids: dict[tuple[str, str], tuple[float, tuple[str, ...]]]`, Schlüssel `(base_url, user)` wie `capabilities._cache` (`capabilities.py:150-151`), Wert = eine Id je unterscheidbarer Schreibweise, TTL 60 s wie `capabilities.TTL_SECONDS`, `clear_cache()` für Tests.
**Drei Regeln, die über `capabilities` hinausgehen:**
1. **Nur nicht-leere Ergebnisse speichern.** "Kein kein-ki" wird nie gecacht, sonst wirkt ein frisch angelegtes und vergebenes Tag bis zu 60 s nicht (Fail-open) [CITED: .planning/research/ARCHITECTURE.md Frage 3; .planning/research/PITFALLS.md Pitfall 3]. Die Liste kostet 48 ms (Messbericht K3 Referenz a).
2. **Bei 412 den Eintrag löschen**, bevor neu gelistet wird.
3. **Schlüssel je Nutzer**, nicht je Instanz: Ein Admin sieht unsichtbare Tags, alice nicht (Quellbefund C); ein instanzweiter Eintrag aus Admin-Sicht würde alices REPORT in einen 412-Kreislauf schicken.
**Gate:** `ALLOWED_MODULE_STATE` um `("nextcloud/exclusion.py", "_tag_ids")` ergänzen und die Zählung in `test_the_two_allowed_caches_still_exist_where_they_are_claimed_to_be` auf 3 heben, mit Kommentar, der E3 und EXCL-02 als Entscheid nennt (der Test verlangt ausdrücklich eine Review-Entscheidung, die liegt mit E3 vor). Testname und Docstring ("two") mit anpassen.

### Pattern 5: Zustände als Werte, nicht als Exceptions
**What:** `load_scope` gibt immer einen `TagScope` zurück: `UNTAGGED`, `ACTIVE(paths, fileids)` oder `UNVERIFIABLE(reason)`. Nextcloud-Ausgänge werden nie als Exception durchgereicht.
**Why:** Jede Familie spricht "nicht prüfbar" in Phase 27 in ihrer eigenen Form aus (ToolError mit `REASON_GUARD_TRIPPED`, oder `degraded`-Eintrag je Provider) [CITED: .planning/research/ARCHITECTURE.md Frage 5]. Der Grund bleibt ein interner Code (z.B. `timeout`, `unreachable`, `status`, `stale_twice`, `unparsable`, `foreign_href`); kein 13. Wert in `errors.REASONS` (frozen, `test_errors_reason.py` läuft `src/` ab).
**Welche Exceptions gefangen werden:** `httpx.TimeoutException` (vor `httpx.HTTPError` prüfen, sonst geht die Unterscheidung verloren), `httpx.HTTPError`, `TimeoutError` aus `asyncio.timeout`, `ToolError` aus `xml.parse_root`/`parse_multistatus`, `ValueError` aus eigener Validierung. **Nicht** `asyncio.CancelledError` (muss durchlaufen und darf nicht als Zustand gespeichert werden) und kein pauschales `except Exception` (Programmierfehler sollen laut scheitern; das bleibt fail-closed, weil dann keine Antwort entsteht).

### Anti-Patterns to Avoid
- **Mehrere `oc:systemtag` in einem REPORT:** UND-Semantik, stilles Fail-open (Quellbefund A).
- **`dav.files_url(creds, "/")` als REPORT-Ziel:** geht durch `safe_path` in die Sandbox-Wurzel.
- **`dav.parse_entries` für die REPORT-Antwort:** verwirft getaggte Vorfahren oberhalb von `NC_MCP_FILES_ROOT` (Erfolgskriterium 3 wäre rot).
- **412 als leere Menge:** `if status == 412: return frozenset()` ist genau das Warnzeichen aus PITFALLS Pitfall 3.
- **Capability `systemtags` lesen oder gar darauf gaten:** D-25-05; der Test aus Erfolgskriterium 1 muss beweisen, dass der Capabilities-Endpunkt nie angefragt wird.
- **Retry bei 401 oder 5xx:** `dav.py` verbietet Wiederholung nach Authentifizierungsfehlern (NC zählt Fehlversuche je Quell-IP); einzige Wiederholung ist der eine 412-Neuversuch.
- **Namen mit `Resolve`:** `TagResolver`, `Resolved...` machen `test_no_tool_stops_to_ask_the_user_or_resolves_a_reference` rot; `lookup_tag_ids`, `tag_ids_for` o.ä. verwenden.
- **Konfigurierbarer Tag-Name (`NC_MCP_EXCLUDE_TAG`):** wäre ein Umgehungsweg und widerspricht dem Geist von D-26-02; Konstante `EXCLUDE_TAG = "kein-ki"`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| XML parsen | eigenen Parser, `etree.fromstring` direkt | `clients/xml.parse_multistatus` / `parse_root` | XXE-, DTD- und Billion-Laughs-Härtung an einer Stelle (T-01-11) |
| Request-Bodies | f-Strings | lxml wie `dav._stat_body`, `tag_spike.report_body` | Escaping (T-01-11); Id nur ASCII-Ziffern (`re.fullmatch(r"[0-9]+", ...)`, `str.isdigit` akzeptiert Hochzahlen) |
| href zu Home-Pfad | neue Dekodierlogik | `dav._home_path_of` über ein öffentliches `home_entries` | Konto-Präfix-Falle (`alicexyz` beginnt mit `alice`, `dav.py:499-501`) ist dort gelöst |
| Segmentregel | zweite Schreibweise im Guard | `dav.within` (aus `in_files_root` herausgelöst) | Erfolgskriterium 3 verlangt die bestehende Regel |
| HTTP-Client | eigener `AsyncClient` | `clients.client` (`shared_client`) | Kein Cookie-Jar (Sitzungsleck zwischen Nutzern, `http.py` NoCookieJar), keine Redirects |
| Single-Flight | eigenes Future-Management | `asyncio.Lock` plus Re-Check wie `jwks.py` | Im Projekt erprobt und getestet (20 parallele Aufrufe = 1 Fetch, `test_oauth_jwks.py:258-269`) |

**Key insight:** Jede Stelle, an der ein Fehler "leer" aussieht, ist in diesem Feature ein Fail-open. Die bestehenden, gehärteten Bausteine liefern bei Fehlern Exceptions; der Guard übersetzt sie zentral in "nicht prüfbar", statt sie irgendwo als leere Liste enden zu lassen.

## Common Pitfalls

### Pitfall 1: Leere Menge durch nicht abbildbare hrefs
**What goes wrong:** Weicht der Pfadanteil von `base_url` vom Webroot ab, den Nextcloud in hrefs schreibt (Proxy, `overwritewebroot`, AppAPI-interne Adresse), liefert `_home_path_of` für jeden href `None`. Ein Parser, der solche Einträge still verwirft, meldet "aktiv, leere Menge", also kein Filter.
**How to avoid:** Jeder `d:response` eines 207-REPORT muss auf einen Home-Pfad abbildbar sein, sonst ganzer Zustand `UNVERIFIABLE(foreign_href)`. Unit-Test mit einem href unter fremdem Präfix.
**Warning signs:** 207 mit Einträgen, aber leere Pfadmenge.

### Pitfall 2: Negativ-Cache und neue Schreibweise
**What goes wrong:** (a) "kein Tag" gecacht: frisch vergebenes Tag wirkt bis TTL nicht. (b) Positiver Eintrag `{kein-ki}` gecacht, danach legt jemand per Altbestand-Import eine zweite Schreibweise an: bis TTL fehlt ihr REPORT.
**How to avoid:** (a) nie leer cachen; (b) TTL kurz halten (60 s wie `capabilities`) und das Restfenster als bekannte Grenze notieren. Da `createTag` ab NC 32 neue Groß/Klein-Dubletten verhindert, entsteht (b) nur durch Direktzugriff auf die Datenbank. Exakt gleichnamige neue Tags sind abgedeckt, weil NC per Name sucht.
**Warning signs:** Cache-Schreibzugriff ohne `if ids:`.

### Pitfall 3: Zweiter 412 und gelöschtes Tag verwechselt
**What goes wrong:** D-25-05 sagt "zweiter 412 = nicht prüfbar"; der Messbericht (Ableitungen Phase 26, erster Punkt) präzisiert: nach dem 412 wird neu gelistet, und fehlt der Name dann in der Liste, ist das Tag gelöscht, also "kein Tag". Wer das Neulisten überspringt, meldet bei jedem gelöschten Tag eine Degradation; wer es falsch herum baut, deutet einen echten zweiten 412 als "kein Tag".
**How to avoid:** Reihenfolge fest: 412 → Cache löschen → PROPFIND → (keine kein-ki-Namen: `UNTAGGED`) / (sonst REPORT erneut: 207 `ACTIVE`, 412 oder anderes `UNVERIFIABLE`). Genau eine Neuauflösung je Aufruf, egal ob die ersten Ids aus dem Cache oder aus einer frischen Liste stammten. Drei Tests: 412 dann Tag weg; 412 dann neue Id 207; 412 dann wieder 412.

### Pitfall 4: Timeout in SQLite-Instanzen
**What goes wrong:** Auf SQLite kostet der REPORT bei 5000 Treffern 8,1 bis 10,6 s, bei 140.000 Fremd-Zuordnungen 240 s schon für einen Treffer (Messbericht G1/G2). Ohne eigenes Budget greift nur das Client-Timeout des gemeinsamen Clients (read 30 s, `http.py`), und ein Tool-Aufruf hängt bis dahin.
**How to avoid:** Budget über die ganze Flight mit `asyncio.timeout(TAG_BUDGET)`; Empfehlung `TAG_BUDGET = 15.0` s (deckt SQLite-5000 inklusive p95/Max mit Luft, liegt in der Größenordnung der bestehenden Budgets 5 bis 10 s in `context.py:118-161`) [ASSUMED: Wert im Ermessensraum]. Ablauf ergibt `UNVERIFIABLE(timeout)`. Die 140k-Grenze ist bekannt und wird in Phase 29 dokumentiert; dort steht der Guard konstruktionsbedingt immer auf "nicht prüfbar".
**Warning signs:** Test mit langsamem Mock läuft 30 s statt kurz.

### Pitfall 5: Vulture meldet den unverdrahteten Guard
**What goes wrong:** CI läuft `uv run vulture src scripts vulture_whitelist.py` (`.github/workflows/ci.yml:34`); Tests zählen nicht als Aufrufer. Klasse, Methoden, `clear_cache` und die Client-Funktionen sind in Phase 26 ohne Produktionsaufrufer.
**How to avoid:** Namen in `vulture_whitelist.py` unter einem neuen Abschnitt "Phase 26 guard core" mit je einer Zeile Begründung parken und ankündigen, dass Phase 27 sie wieder entfernt (etabliertes Muster, siehe die Abschnitte zu 24-03, 24-05, 25-01 in der Whitelist). Namensschatten beachten: ein Name, der anderswo schon einen Aufrufer hat (z.B. `clear_cache` in `capabilities`), wird von Vulture nicht gemeldet und darf dann nicht in die Liste (WR-07 aus 25-REVIEW zeigt den Mechanismus).

### Pitfall 6: Gates aus `test_no_destructive_calls.py`
**What goes wrong:** Dritter Modul-Cache ohne Eintrag: `test_no_module_level_mutable_state_outside_the_two_documented_caches` rot. Eintrag ohne Zählerhebung: `len(ALLOWED_MODULE_STATE) == 2` rot. Bezeichner mit `Resolve`: rot.
**How to avoid:** Beide Stellen im selben Plan wie den Cache ändern, Begründung im Kommentar. Kein `Resolve` in Bezeichnern oder String-Literalen. Die geplante Phase-28-Nadel `systemtags-relations` (EXCL-07) trifft den Lesepfad `/remote.php/dav/systemtags/` nicht; den Pfad nie als `systemtags-relations` schreiben.

### Pitfall 7: Case-Folding und Leerraum
**What goes wrong:** `lower()` statt `casefold()` verpasst Sonderfälle; ein Tag `" kein-ki"` mit Leerzeichen aus Altbestand fällt durch.
**How to avoid:** Vergleich `name.strip().casefold() == EXCLUDE_TAG`. Das Strippen weitet nur in Richtung "mehr ausschließen" (fail-closed-Richtung) [ASSUMED: ob NC Namen beim Anlegen trimmt, nicht verifiziert]. Keine NFKC-Normalisierung (würde Homoglyphen-Diskussion aufmachen, die niemand bestellt hat).

### Pitfall 8: Abbruch während der Flight
**What goes wrong:** Wird der Aufrufer, der die Flight hält, abgebrochen (äußeres `asyncio.timeout` in `context.py`), bleibt `_scope` leer; der nächste Wartende startet eine zweite Flight (call_count 2).
**How to avoid:** Akzeptieren und dokumentieren (fail-closed bleibt gewahrt, nur die Kosten verdoppeln sich im Abbruchfall), `CancelledError` nie als Zustand speichern. Kein `asyncio.shield`-Konstrukt in Phase 26; Test für den Normalfall "20 parallele Aufrufe = 1 REPORT" wie `test_oauth_jwks.py:258`.

## Code Examples

### REPORT-Body (eine Regel)
```python
# Source: scripts/tag_spike.py:556-575 (Messwerkzeug, von 25-REVIEW ohne Befund für diese Funktion)
def report_body(tag_id: str) -> bytes:
    if not re.fullmatch(r"[0-9]+", tag_id):
        raise ValueError("a tag id must be ASCII digits only")
    root = etree.Element(f"{{{xml.OC}}}filter-files", nsmap={"d": xml.DAV, "oc": xml.OC, "nc": xml.NC})
    prop = etree.SubElement(root, f"{{{xml.DAV}}}prop")
    etree.SubElement(prop, f"{{{xml.OC}}}fileid")
    etree.SubElement(prop, f"{{{xml.DAV}}}resourcetype")
    rules = etree.SubElement(root, f"{{{xml.OC}}}filter-rules")
    etree.SubElement(rules, f"{{{xml.OC}}}systemtag").text = tag_id   # genau EINE Regel
    return etree.tostring(root, xml_declaration=True, encoding="utf-8")
```
Die 25-REVIEW-Warnings WR-01 bis WR-07 betreffen `run()`, `wait_until_idle`, `measure_bundle`, `block_threshold`, `block_notes`, den Rückbau und `access_lines`, also Messinfrastruktur. `report_body`, `propfind_body` und `systemtag_listing` sind nicht betroffen und dürfen als Vorlage dienen; übernommen wird nur das Muster, nicht der Import aus `scripts/`.

### Tag-Liste
```python
# Source: scripts/tag_spike.py:1210-1226 (systemtag_listing), erweitert um display-name
response = await clients.client.request(
    "PROPFIND",
    f"{clients.creds.base_url}/remote.php/dav/systemtags/",
    headers={"Depth": "1", "Content-Type": "application/xml"},
    content=propfind_body([f"{{{xml.OC}}}id", f"{{{xml.OC}}}display-name"]),
    auth=clients.creds.auth(),
)
# 207 -> xml.parse_multistatus; Eintrag ohne oc:id (die Collection selbst) überspringen;
# Id nur ASCII-Ziffern; eine Id je unterscheidbarer Schreibweise behalten
```

### Zustände als Werte
```python
# Empfehlung; Namen im Ermessensraum, aber ohne "Resolve"
@dataclass(frozen=True, slots=True)
class TagScope:
    state: Literal["untagged", "active", "unverifiable"]
    paths: frozenset[str] = frozenset()      # absolute Home-Pfade, ungefiltert durch die Sandbox
    fileids: frozenset[str] = frozenset()
    reason: str | None = None                # nur bei "unverifiable"

    def excludes(self, path: str | None = None, fileid: str | None = None) -> bool:
        if self.state != "active":
            return False          # "unverifiable" entscheidet der Aufrufer (Phase 27), nie hier
        if fileid and fileid in self.fileids:
            return True
        return path is not None and any(a in self.paths for a in ancestors(path))
```
`excludes` im Zustand `unverifiable` mit `False` zu beantworten wäre gefährlich, wenn ein Aufrufer den Zustand ignoriert. Deshalb empfohlen: `excludes` wirft `ValueError` (oder liefert ein Drei-Werte-Ergebnis), wenn `state == "unverifiable"`, damit Phase 27 den Zustand nicht übersehen kann. Die Entscheidung zwischen Exception und Drei-Werte-Enum ist Ermessen; wichtig ist, dass kein Zwei-Werte-Rückgabetyp "nicht prüfbar" zu "erlaubt" macht.

### Test: ein REPORT bei 20 parallelen Teilaufrufen
```python
# Muster: tests/unit/test_oauth_jwks.py:258-269
@pytest.mark.anyio
async def test_twenty_parallel_scopes_cost_one_report() -> None:
    exclusion.clear_cache()
    with respx.mock(assert_all_mocked=True) as mock:
        mock.route(method="PROPFIND", url=TAGS_URL).mock(return_value=tag_list("kein-ki"))
        report = mock.route(method="REPORT", url=HOME_URL).mock(return_value=report_207(["/A/kein"]))
        capabilities = mock.get(CAPS_URL)   # darf nie angefragt werden (Erfolgskriterium 1)
        guard = exclusion.ExclusionGuard()
        scopes = await asyncio.gather(*(guard.scope(clients) for _ in range(20)))
    assert report.call_count == 1
    assert capabilities.call_count == 0
    assert all(s is scopes[0] for s in scopes)
```

### Testmatrix zu den Erfolgskriterien
| Kriterium | Test | Erwartung |
|---|---|---|
| 1 kein Tag | Liste ohne kein-ki | `untagged`, REPORT `call_count == 0`, `excludes` überall `False`, gefilterte Beispielliste `==` Eingabe und `json.dumps`-gleich |
| 1 aktiv | Liste mit kein-ki, REPORT 207 | `active`, Pfade und fileids gesetzt |
| 1 nicht prüfbar | REPORT 500 / 401 / 3xx / `httpx.ConnectError` / Timeout / unparsebarer Body / fremder href / zweiter 412 / Liste 500 | je `unverifiable` mit Grundcode |
| 1 Capability | Capabilities-Route mit `systemtags` aus gemockt, REPORT 207 | `active`, Capabilities `call_count == 0` |
| 2 Single-Flight | 20 parallele `scope()` | REPORT 1 |
| 2 zweiter Aufruf | zwei Guard-Instanzen nacheinander, Cache warm | REPORT 2, PROPFIND 1 |
| 2 412 | Cache mit alter Id, REPORT 412, Liste mit neuer Id, REPORT 207 | REPORT 2, PROPFIND 1, `active` |
| 3 Segment | Menge `{"/A/kein"}` | `/A/kein/x` ja, `/A/kein` ja, `/A/keine` nein, `/A` nein |
| 3 Sandbox | `NC_MCP_FILES_ROOT=/Shared/KI`, Menge `{"/Shared"}` | `/Shared/KI/doc.md` ausgeschlossen |
| 4 Varianten | Liste: `kein-ki` (public, Id 64), `kein-ki` (restricted, Id 65), `Kein-KI` (Id 67); unsichtbare Variante fehlt in der Nutzerliste | genau 2 REPORTs (64 und 67, nicht 65), Vereinigung beider Mengen; bei Admin-Liste mit unsichtbarer Variante in anderer Schreibweise ein REPORT mehr |

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| REPORT vergleicht Tag-Ids | REPORT sucht per Tag-Name (`searchBySystemTag`) | vor NC 32 (auf stable32 bis master vorhanden) | Exakt gleichnamige Varianten kommen vereinigt, eine Id je Schreibweise genügt |
| Groß/Klein-Dubletten beim Anlegen möglich | `createTag` verhindert sie per `mb_strtolower`-Vergleich | NC 32 [VERIFIED: 25-RESEARCH Quellbefund 1] | Mehrere Schreibweisen nur aus Altbestand oder DB-Direktzugriff |
| Capability als Feature-Schalter | REPORT-Ausgang maßgeblich | Owner-Entscheid D-25-05 | App aus ändert nichts am Filter |

**Deprecated/outdated:**
- Entwurf "vorfahren-propfind" (Messbericht): vom Owner mit E3 verworfen.
- Die in der Milestone-Architektur erwogene Konfiguration `NC_MCP_EXCLUDE_TAG`: durch D-26-02 obsolet (kein Schalter), siehe Anti-Patterns.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `TAG_BUDGET = 15.0` s ist ein passendes Gesamtbudget | Pitfall 4 | Zu kurz: SQLite-Instanzen mit vielen getaggten Knoten kippen früher auf "nicht prüfbar"; zu lang: Tool-Aufrufe hängen länger. Kein Sicherheitsrisiko, beide Richtungen fail-closed |
| A2 | Tag-Namen per `strip().casefold()` vergleichen, obwohl unbekannt ist, ob NC beim Anlegen trimmt | Pitfall 7 | Schlimmstenfalls wird ein Tag `" kein-ki"` mitgezählt, das jemand bewusst anders gemeint hat (mehr Ausschluss, nicht weniger) |
| A3 | MySQL/MariaDB mit case-insensitiver Kollation liefern bei `searchBySystemTag("kein-ki")` zusätzlich `Kein-KI`-Knoten | Quellbefund A | Keines: der Guard fragt ohnehin je Schreibweise und vereinigt; überlappende Mengen sind harmlos |
| A4 | 60 s TTL für den Name-zu-Id-Cache sind als Restfenster für eine per DB-Direktzugriff neu entstandene zweite Schreibweise vertretbar | Pitfall 2 | Bis 60 s wird diese neue Schreibweise nicht gefiltert; Owner könnte kürzere TTL oder Verzicht auf den Cache wollen (Open Question 1) |

## Open Questions

1. **"Genau ein REPORT" bei mehreren Schreibweisen**
   - What we know: UND-Semantik zwingt zu einem REPORT je unterscheidbarer Schreibweise (Quellbefund A); ab NC 32 entstehen neue Groß/Klein-Dubletten nicht mehr.
   - What's unclear: Erfolgskriterium 2 sagt "genau ein REPORT", Kriterium 4 verlangt Vereinigung über Schreibweisen hinweg. Beides zusammen geht nur als "eine Flight je Aufruf mit einem REPORT je Schreibweise".
   - Recommendation: So bauen; der Plan formuliert den Test zu Kriterium 2 mit einer Schreibweise (call_count 1) und den zu Kriterium 4 mit exakter Erwartung (2 REPORTs bei zwei Schreibweisen, keiner für die exakt gleichnamige). In der Plan-Einleitung ausdrücklich als Lesart festhalten, damit Verifier und Owner es nicht als Abweichung werten. Keine Änderung am Wortlaut von EXCL-02 nötig ("die getaggte Menge wird einmal je Antwort geholt" bleibt wahr).

2. **Obergrenze für die getaggte Menge**
   - What we know: `{DAV:}limit` wirkt im REPORT (Quellbefund B, nicht gemessen); 5000 Treffer = 1,27 MB; eine Obergrenze mit "darüber = nicht prüfbar" wäre robust, selbst wenn NC das Limit ignorierte (man zählt nach).
   - What's unclear: D-25-05 sagt wörtlich "207 = Menge ermittelt"; eine Obergrenze machte aus einem 207 ein "nicht prüfbar". Das ist eine neue Fail-closed-Stelle, also eine Owner-Frage.
   - Recommendation: In Phase 26 keine funktionale Obergrenze; Speicher ist bei realistischen Mengen unkritisch und das Zeitbudget (A1) begrenzt den teuren Fall schon. Als Merker für Phase 29 notieren.

3. **Wann bekommt `NcClients` das dritte Feld?**
   - What we know: Die Milestone-Architektur sieht `exclusion: ExclusionGuard = field(default_factory=ExclusionGuard)` vor; das Feld würde durch `deps.resolve_clients` automatisch je Aufruf eine neue Instanz erzeugen.
   - What's unclear: Ob das Feld schon "Einhängen" ist, das CONTEXT für Phase 26 ausschließt.
   - Recommendation: Feld erst in Phase 27. Phase 26 baut die Klasse so (`scope(clients)`-Signatur, parameterloser Konstruktor), dass das Feld dort eine Zeile ist.

## Environment Availability

Step 2.6: Reine Code-Phase mit Unit-Tests gegen respx. Werkzeuge vorhanden: uv 0.11.7, httpx 0.28.1, respx 0.23.1 (lokal geprüft). Die nc35-Strecke läuft (`docker ps`: nc35-nc, nc35-harp, nc35-caddy), wird aber nicht gebraucht; ein optionaler Integrationstest mit Marker `integration` ist möglich, verändert dann aber Tag-Bestand auf nc35 und braucht Rückbau. Empfehlung: in Phase 26 keinen Integrationstest, der echte REPORT-Beweis gegen die Test-Nextcloud gehört in das Klassifikations-Gate von Phase 27.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | nein (nutzt bestehende Credentials) | `creds.auth()`; kein Retry nach 401 (`dav.py`-Regel) |
| V3 Session Management | ja, indirekt | gemeinsamer Client mit `NoCookieJar`; Guard-Zustand stirbt mit dem Aufruf, Cache-Schlüssel je Nutzer |
| V4 Access Control | ja (Kern der Phase) | Fail-closed-Automat: nur zwei Ausgänge führen zu "kein Filter" bzw. "Filter aktiv", alles andere "nicht prüfbar"; Nutzerkontext entscheidet Sichtbarkeit (NC) |
| V5 Input Validation | ja | Tag-Ids nur ASCII-Ziffern; hrefs nur über `_home_path_of`; Bodies mit lxml |
| V6 Cryptography | nein | , |
| V12/V14 XML | ja | `xml.parse_multistatus` (keine Entities, kein Netz, keine DTD) |

### Known Threat Patterns for diesen Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Fehler als leere Menge (Fail-open) | Information Disclosure | Drei Zustände als Werte, jeder unerwartete Ausgang `unverifiable` (Pitfalls 1 und 3) |
| Mehrere Tag-Regeln mit UND verknüpft | Information Disclosure | Eine Regel je REPORT (Quellbefund A) |
| Cache überlebt Tag-Anlage | Information Disclosure | Kein Negativ-Cache, Menge nie cachen (E3) |
| Cache-Vergiftung zwischen Nutzern (Admin-Ids für alice) | Tampering/DoS | Schlüssel `(base_url, user)` |
| XXE/Billion Laughs im REPORT-Body | Tampering/DoS | gehärteter Parser |
| Langsamer REPORT blockiert Aufrufe | DoS | `asyncio.timeout(TAG_BUDGET)` über die Flight |
| Existenz-Orakel über die Antwortform | Information Disclosure | Phase 27 (Byte-Gleichheit zu "existiert nicht"); Phase 26 hinterlässt im Zustand `untagged` keinerlei Spur |

## Project Constraints (from CLAUDE.md)

- Python 3.13, uv als Toolchain (`uv run ...`), httpx für alle Nextcloud-Aufrufe, lxml für DAV-XML; keine neuen Abhängigkeiten nötig.
- Code und Docstrings Englisch; deutsche Planungstexte mit echten Umlauten, keine Em-Dashes, keine Emojis.
- Gates lokal grün vor Commit, identisch zu CI: `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright` (standard, mit `PYRIGHT_PYTHON_FORCE_VERSION=latest` wie CI, Memory-Regel 19.09.), `uv run vulture src scripts vulture_whitelist.py`, `uv run pytest tests/unit tests/contract`.
- Security: der MCP sieht nie mehr als der angemeldete Nutzer; keine destruktiven Writes (Gate `test_no_destructive_calls.py`, dort auch D-20 Modulzustand und `Resolve`-Nadel).
- OSS-Commits nur als Owner (`street1983nk <k.cherif@outlook.de>`), keine Claude-Trailer (Memory-Regel 25.08.).
- Alle Pfade testen: Happy, Fehler, Edge, no_data (globale Regel im Stack-Abschnitt).

## Sources

### Primary (HIGH confidence)
- `.planning/phases/25-mess-spike-tag-abfrage/25-MESSBERICHT.md`: K1 bis K5, G1 bis G5, Owner-Entscheide D-25-05 und E3, Ableitungen Phase 26
- `.planning/phases/25-mess-spike-tag-abfrage/raw/nc35-befunde.txt` Zeilen 128 bis 152 (unsichtbares Tag, Varianten)
- nextcloud/server `apps/dav/lib/Connector/Sabre/FilesReportPlugin.php` master, stable32, stable33 (WebFetch und curl, 27.09.2026): `onReport`, `processFilterRulesForFileNodes`, UND-Verknüpfung, 412, `{DAV:}limit`
- nextcloud/server stable32 `apps/dav/lib/SystemTag/SystemTagsByIdCollection.php` (Sichtbarkeit der Tag-Liste)
- Codebasis: `oauth/jwks.py`, `nextcloud/capabilities.py`, `nextcloud/clients/dav.py`, `nextcloud/clients/xml.py`, `nextcloud/http.py`, `nextcloud/__init__.py`, `deps.py:116-118`, `errors.py`, `tests/contract/test_no_destructive_calls.py`, `tests/unit/test_oauth_jwks.py`, `vulture_whitelist.py`, `pyproject.toml`, `.github/workflows/ci.yml`

### Secondary (MEDIUM confidence)
- `.planning/research/ARCHITECTURE.md` (Milestone v1.7): Guard am Parameterobjekt, Cache nur positiv, Engstellen für Phase 27
- `.planning/research/PITFALLS.md` Pitfall 3 und 9
- `.planning/phases/25-mess-spike-tag-abfrage/25-RESEARCH.md` Quellbefund 1 (Suche per Name, `createTag`-Dublettenschutz ab NC 32)
- `.planning/phases/25-mess-spike-tag-abfrage/25-REVIEW.md` (WR-01 bis WR-07 betreffen die übernommenen Helfer nicht)

### Tertiary (LOW confidence)
- keine

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH, keine neuen Pakete, alles installiert und im Projekt erprobt
- Architecture: HIGH, Muster stammen aus der Codebasis, REPORT-Semantik aus Messung plus Quelltext von drei Branches
- Pitfalls: HIGH für Gates, 412-Ablauf und UND-Semantik; MEDIUM für Timeout-Wert und Namensnormalisierung (Ermessen)

**Research date:** 2026-09-27
**Valid until:** 2026-10-27 (stabil; neu prüfen, falls NC 36 `FilesReportPlugin` ändert)
