# Phase 27: Familien-Anschluss und Sandbox-Parität - Research

**Researched:** 2026-09-27
**Domain:** Verdrahtung des Ausschluss-Guards (nextcloud/exclusion.py) in alle dateitragenden Tool-Familien, fileid-zu-Pfad-Auflösung für Sandbox-Parität, orakelfreie Fehlerpfade
**Confidence:** HIGH für Code-Landkarte und Fehlerpfade (alles im Repo gelesen), MEDIUM für Nextcloud-/Talk-Verhalten außerhalb des Repos (Quelltext gelesen, nicht live gemessen), LOW für zwei Leck-Kanäle (talk-message-Suchprovider, Datei-Konversationen), die nur live entschieden werden können

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Upload-Orakel (files_upload, upload_binary)
- **D-27-01:** Ein Upload auf einen ausgeschlossenen Pfad (Ziel getaggt oder unter getaggtem Ordner) wird IMMER abgewiesen, Wortlaut byte-gleich zum bestehenden Fehler "The parent folder ... does not exist". Die Story "ausgeschlossen = existiert nicht" gilt auch beim Schreiben; der getaggte Ordner ist in Listings ohnehin unsichtbar. Grenzfall direkt getaggte Datei unter sichtbarem Elternordner: Claude wählt den konsistentesten Wortlaut und dokumentiert ihn im Plan. (Owner 27.09., Empfehlung übernommen)
- **D-27-02:** Bei "nicht prüfbar" (REPORT-Fehler, Timeout, zweiter 412) wird der Upload fail-closed abgewiesen, mit klarer Meldung im einheitlichen Wortlaut von D-27-05. Sonst könnte ein Upload ungeprüft im ausgeschlossenen Teilbaum landen und der Konflikt-Orakel-Schutz wäre in diesem Zustand offen. (Owner 27.09., Empfehlung übernommen)

#### Zählen vs. Schweigen (Degradations-Ausgestaltung je Familie)
- **D-27-03:** Im Erfolgsfall gilt D-v1.7-02 unverändert: komplettes Schweigen über tag-zurückgehaltene Einträge, kein Zähler, kein Hinweis. Bei "nicht prüfbar" GETEILT NACH ZUGRIFFSART: Listen-Familien (files_list, files_search, unified_search, prepare_context, notes-Listen, Findling-Treffer) halten dateitragende Einträge zurück und schreiben EINEN degraded-Eintrag im bestehenden Idiom der Familie; Einzelzugriffe (files_read, files_download, fetch, notes-Einzelzugriff) liefern einen einheitlichen ToolError, für ALLE Ids gleich, damit der Fehler selbst kein Orakel wird. (Owner 27.09., Empfehlung übernommen)
- **D-27-04:** Der bestehende skipped-Zähler in unified_search zählt weiterhin NUR unbrauchbare und Sandbox-Treffer; tag-ausgeschlossene Treffer verschwinden lautlos und erhöhen keinen Zähler. Reihenfolge im Zweifel: Sandbox-Drop vor Tag-Prüfung ist erlaubt (der Sandbox-Grund verrät nichts über das Tag). (Owner 27.09., Empfehlung übernommen)
- **D-27-05:** EIN Wortlaut überall: eine gemeinsame Konstante (z.B. reason "exclusion check unavailable") für degraded-Einträge, die ToolErrors der Einzelzugriffe und die Upload-Abweisung bei "nicht prüfbar". Kein Drift zwischen Familien, ein Satz für die Doku in Phase 29. (Owner 27.09., Empfehlung übernommen)

#### Talk-Platzhalter (EXCL-06)
- **D-27-06:** talk_browse behandelt die getaggte geteilte Datei wie einen Eintrag ohne Namen: der Platzhalter bleibt roh als `{file}` im Nachrichtentext, exakt wie der bestehende Unbekannt-Pfad (talk.py: "An unknown placeholder, and one whose entry carries no name, stays in the text exactly as {placeholder}"). Kein neuer Marker, kein Orakel, die Nachricht selbst bleibt erhalten. Bei "nicht prüfbar" bleiben ALLE Datei-Platzhalter roh plus degraded-Eintrag (konsistent mit D-27-03). Wichtig: auch die rohen messageParameters-Werte (Dateiname, Pfad) dürfen die Antwort nicht auf anderem Weg verlassen. (Owner 27.09., Empfehlung übernommen)

#### Aus früheren Phasen übernommene Entscheide (gelten unverändert, nicht neu verhandeln)
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

### Deferred Ideas (OUT OF SCOPE)
- Obergrenze für die getaggte Menge ({DAV:}limit ungemessen) , Owner-Frage in Phase 29 (deferred-items (a)).
- TTL-Restfenster 60 s des Name-zu-Id-Caches, unsichtbares kein-ki (Admin vs. Nicht-Admin), SQLite-140k-Grenze , Doku in Phase 29 (deferred-items (b)/(d)/(f)).
- Klassifikations-Freeze, Kanarientest, byte-gleiche Paartests, AST-Nadeln , Phase 28.
- EXCL-F02 Store-Text-Erwähnung , reist mit dem nächsten Release.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| EXCL-01 | Getaggtes (und alles darunter) erscheint in keiner Antwort von files_list, files_search, files_read, files_download; ein Upload auf einen ausgeschlossenen Pfad verrät nicht, ob dort etwas existiert | Abschnitt "Familie Dateien" (Prüfpunkte je Tool, Reihenfolge nach stat, Paginierung vor dem Schnitt filtern), Fehlerfabriken `dav.not_found`/`dav.parent_missing` für Byte-Gleichheit, Upload-Grenzfall |
| EXCL-03 | unified_search, fetch (alle Id-Arten, auch eine vor dem Taggen bekannte fileid) und prepare_context liefern keine getaggten Treffer, Ausschnitte, Digests; systemtags-Provider verrät die Menge nicht | Abschnitt "Familie Suche": generischer Datei-Extraktor (fileId-Attribut, path-Attribut, `/f/<id>`-URL, notes-Provider), systemtags- und comments-Provider-Befund, fetch-Reihenfolge, prepare_context Guard-Anstoß |
| EXCL-05 | Notes respektieren den Tag | Abschnitt "Familie Notes": fileid = Notiz-Id, Pfad über fileid-SEARCH, einheitlicher Not-found-Satz auch für Notes-404 |
| EXCL-06 | talk_browse setzt keine Dateinamen getaggter Dateien in den Nachrichtentext | Abschnitt "Familie Talk": `_resolve` ist die eine Stelle (drei Aufrufer), Talk-Dateiparameter trägt `id` (fileid) und `path` relativ zur Nutzer-Home; Zusatzkanäle Datei-Konversationen |
| SBX-01 | Findling-Treffer nur mit fileId laufen durch Sandbox- und Ausschlussprüfung | `search._entry_in_files_root` lässt heute jeden Nicht-files-Provider ohne path durch (belegt); Batch-fileid-SEARCH `d:or` über `search_scope` liefert Pfad und Sandbox in einem Request |
| SBX-02 | Notes laufen durch Sandbox- und Ausschlussprüfung | Kein FILES_ROOT-Bezug in tools/notes.py und clients/notes.py (belegt); dieselbe fileid-Auflösung schließt die Lücke, auch für notes-Treffer in unified_search |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- Code, Kommentare, Docstrings, Fehlertexte an den Nutzer: **Englisch**. Projektkommunikation und Planungsdokumente: Deutsch mit echten Umlauten, keine Em-/En-Dashes, keine Emojis.
- Tests laufen mit `.venv/Scripts/python.exe -m pytest` (uv sync ist durch ein gesperrtes nc-mcp.exe blockiert); CI fährt `uv run ruff check .`, `ruff format --check .`, `pyright` (typeCheckingMode standard), `vulture src scripts vulture_whitelist.py`, `pytest tests/unit tests/contract`, `scripts/check_tool_budget.py`. [VERIFIED: .github/workflows/ci.yml]
- pyright lokal mit `PYRIGHT_PYTHON_FORCE_VERSION=latest` fahren, sonst weicht es von CI ab (Memory-Regel 19.09.).
- Security-Kern: "Der MCP darf nie mehr sehen als der angemeldete Nutzer"; keine destruktiven Writes; der Connector darf Tags nie setzen oder entfernen (EXCL-07, Gate in Phase 28). Tag-Anlage in Live-Tests nur im Test-Harness per `occ tag:files:add` wie in `scripts/tag_spike.py`, nie in `src/`.
- Contract-Gate: keine neuen modulweiten veränderlichen Zustände außer den drei dokumentierten Caches (`tests/contract/test_no_destructive_calls.py::test_no_module_level_mutable_state_outside_the_three_documented_caches`). Ein fileid-zu-Pfad-Cache ist damit verboten. [VERIFIED: tests/contract/test_no_destructive_calls.py:287-289,644]
- Modulgrenzen-Gate: kein Modul greift auf `_privat`-Namen eines anderen Tool-Moduls zu (`tests/contract/test_module_boundaries.py`). Geteilte Helfer müssen öffentliche Namen tragen. [VERIFIED]
- GSD-Workflow: Änderungen nur über `/gsd:execute-phase`.

## Summary

Der Guard ist fertig und korrekt (TagScope mit drei Zuständen, Single-Flight je Instanz, `excludes(path, fileid)` wirft im Zustand unverifiable). Er wird nirgends aufgerufen, und `NcClients` hat noch kein Feld für ihn. Diese Phase ist deshalb überwiegend Verdrahtung, aber die Verdrahtung hat drei Stellen, an denen sie still schiefgehen kann: (1) Fehlertexte und Zähler, die "getaggt" von "nicht existent" unterscheidbar machen (Reihenfolge der Prüfungen nach `stat`, `truncated` bei gefilterter Suche, Notes-404 mit Fremdtext); (2) Treffer ohne Pfad (Findling, comments-Provider, notes-Provider, Talk-Dateiparameter ohne path), für die Sandbox und Teilbaum-Regel einen Home-Pfad brauchen; (3) Test-Infrastruktur, weil jeder bestehende respx-Test einer dateitragenden Familie ab dem ersten verdrahteten Guard einen unerwarteten `PROPFIND /remote.php/dav/systemtags/` sieht (483 Tests in den betroffenen Dateien, alle heute grün).

Die tragende technische Empfehlung ist eine einzige Batch-Auflösung "fileids zu Home-Pfaden" per WebDAV SEARCH mit `d:or` aus `d:eq oc:fileid` innerhalb von `dav.search_scope(creds)`: ein Request liefert zugleich die Sandbox-Antwort (was nicht zurückkommt, liegt außerhalb von NC_MCP_FILES_ROOT oder existiert nicht) und den Pfad für die Teilbaum-Prüfung. Sie wird nur gebraucht, wenn wirklich pfadlose Treffer vorliegen UND (Sandbox-Root ungleich `/` ODER die getaggte Menge enthält Ordner). Für den zweiten Teil liest TagScope das bisher ungenutzte `is_collection` (löst Merker (e)). Im Normalfall (Root `/`, kein Tag) kostet die Phase je Antwort genau einen zusätzlichen Request (die Tag-Liste, rund 48 ms), bei vorhandenem Tag nach dem ersten Aufruf nur den REPORT (Name-zu-Id-Cache 60 s).

Zwei Befunde gehen über den bisherigen Phasentext hinaus und brauchen eine Planentscheidung: Der `comments`-Suchprovider (Stock-Nextcloud) liefert Treffer mit Dateipfad im subline und fileid nur in der URL `/f/<id>`; der generische Extraktor fängt ihn. Und Talk kennt Datei-Konversationen (`objectType` `file`), deren Name der Dateiname ist; sie erscheinen in talk_browse, talk_send und fetch(message) über `one_room`. Beides ist ein Dateinamen-Leck für getaggte Dateien und fällt dem Kanarientest von Phase 28 auf, wenn er nicht hier behandelt wird.

**Primary recommendation:** Erst ein Fundament-Plan (IN-02/IN-03 richtig gefixt, `NcClients.exclusion` mit `compare=False` und aufgelöstem Importzyklus, ein öffentliches Helfermodul für Wortlaut, Fehlerfabriken und fileid-Auflösung, Test-Helfer für die Guard-Routen), dann die Familien Dateien, Suche/fetch/prepare_context, Notes/Talk, zuletzt ein Live-Beweislauf gegen nc35 mit frischem `NcClients` je Tool-Aufruf.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Getaggte Menge ermitteln (REPORT, 412-Automat) | API / Backend (nextcloud/exclusion.py, fertig) | Nextcloud DAV | Policy bleibt im Guard, Tools fragen nur `excludes` |
| Entscheidung "zurückhalten" je Eintrag | API / Backend (tools/*) | , | Nur die Tool-Schicht kennt Eintragsformen und Idiome (exclusion.py-Docstring: "the tool layer of phase 27 does that") |
| Wortlaut, degraded-Eintrag, uniforme ToolErrors | API / Backend (ein neues öffentliches Helfermodul) | , | D-27-05 verlangt eine Konstante; Modulgrenzen-Gate verlangt öffentliche Namen |
| fileid zu Home-Pfad (Sandbox + Teilbaum) | API / Backend (clients/dav.py) | Nextcloud DAV SEARCH | Ein Request je Antwort, Sandbox-Scope serverseitig |
| Byte-gleiche Not-found-Fehler | API / Backend (clients/dav.py Fabriken) | , | Eine Fabrik für echten 404 und Ausschluss verhindert Drift |
| Tag-Anlage für Beweise | Test-Harness (occ) | , | EXCL-07: `src/` schreibt nie Tags |

## Standard Stack

Keine neuen Abhängigkeiten. Alles läuft mit dem vorhandenen Stack. [VERIFIED: pyproject.toml, .venv]

| Library | Version (installiert) | Zweck in dieser Phase |
|---------|------------------------|------------------------|
| httpx | 0.28.1 | alle Nextcloud-Requests, Guard-Flight |
| lxml | vorhanden | SEARCH-Body mit `d:or`, nie per String |
| respx | 0.23.1 | Unit-Tests: Guard-Routen, `call_count` für "ein REPORT je Antwort" |
| pytest / pytest anyio | 9.1.1 | Unit, Contract, `-m integration` gegen nc35 |

**Installation:** keine.

## Package Legitimacy Audit

Diese Phase installiert keine externen Pakete. Kein slopcheck-Lauf nötig.

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### Datenfluss je Tool-Antwort

```
Tool-Aufruf (reg_*.py)
   |
   v
deps.resolve_clients(ctx) ---> NcClients(client, creds, exclusion=ExclusionGuard())   [neu je Aufruf]
   |
   v
Tool-Funktion (tools/*.py)
   |---- gather ---------------------------------------------+
   |                                                          |
   v                                                          v
Primärabfrage (PROPFIND/SEARCH/OCS/Talk)        clients.exclusion.scope(clients)
   |                                              (PROPFIND systemtags [+ REPORT je Schreibweise])
   |                                                          |
   +--------------------------+-------------------------------+
                              v
                  Entscheidung in fester Reihenfolge:
                  1. scope.state == "unverifiable"?
                        Liste  -> dateitragende Einträge weg + EIN degraded-Eintrag
                        Einzel -> uniformer ToolError (gleich für alle Ids), vor jeder Id-Auswertung
                        Upload -> uniformer ToolError, kein Schreib-Request
                  2. Fehler der Primärabfrage (404 usw.) wie bisher
                  3. pfadlose Treffer? und (Root != "/" oder scope.has_folders)
                        -> dav.paths_of_fileids (ein SEARCH d:or, Sandbox-Scope)
                        -> nicht gefunden = Sandbox-Drop (skipped++ wo es den Zähler gibt)
                  4. scope.excludes(path=..., fileid=...) je Eintrag
                        Liste  -> lautlos weg (kein Zähler, kein Hinweis)
                        Einzel -> dav.not_found(...) / Not-found-Satz der Familie, byte-gleich
                        Upload -> dav.parent_missing(target)
                  5. erst danach: Paginierung, Buckets, Kappungen, Ausschnitte
                              |
                              v
                        Antwort an das Modell
```

### Recommended Project Structure (Änderungen)

```
src/mcp_connector/
├── nextcloud/__init__.py        # NcClients bekommt exclusion-Feld (compare=False, repr=False)
├── nextcloud/exclusion.py       # NcClients nur unter TYPE_CHECKING importieren; TagScope.has_folders
├── nextcloud/clients/dav.py     # IN-01/02/03, not_found(), parent_missing(), paths_of_fileids()
├── tools/withhold.py            # NEU, Name frei: EXCLUSION_UNAVAILABLE, unavailable_error(),
│                                #   degraded_entry(key), file_refs(entry) für Suchtreffer
├── tools/files.py               # list/search/read/download/upload/upload_binary
├── tools/search.py              # unified_search: Extraktor, Sandbox via Auflösung, Tag-Filter
├── tools/chatgpt.py             # _fetch_file Reihenfolge; _fetch_message über one_room
├── tools/context.py             # Guard früh anstoßen, degraded deduplizieren
├── tools/notes.py               # search/read (create: siehe Open Questions)
└── tools/talk.py                # _resolve mit scope, one_room/_conversations für Datei-Räume
tests/unit/guard_routes.py       # NEU (Name frei): respx-Routen untagged/active/unverifiable
```

### Pattern 1: NcClients-Feld ohne Importzyklus
**What:** `nextcloud/__init__.py` muss `ExclusionGuard` beim Klassenaufbau kennen (default_factory), `exclusion.py` importiert heute zur Laufzeit `from . import NcClients`. Das ist ein Zyklus. [VERIFIED: exclusion.py:58, nextcloud/__init__.py]
**Fix:** In exclusion.py `NcClients` nur unter `TYPE_CHECKING` importieren (Annotationen als Strings oder `from __future__ import annotations`); NcClients wird dort nur in Annotationen benutzt. [VERIFIED: alle Vorkommen in exclusion.py sind Parameter-Annotationen]
```python
# nextcloud/__init__.py
from dataclasses import dataclass, field
from .exclusion import ExclusionGuard  # exclusion.py imports NcClients under TYPE_CHECKING only

@dataclass(frozen=True, slots=True)
class NcClients:
    client: httpx.AsyncClient
    creds: Credentials
    # One guard per tool call; compare/repr off so equality of two bundles stays what it was.
    exclusion: ExclusionGuard = field(default_factory=ExclusionGuard, compare=False, repr=False)
```
`compare=False` hat Vorbild im Projekt (Quick-Task 26.09., `_windows` aus eq/hash). [VERIFIED: STATE.md]

### Pattern 2: Primärabfrage und Guard parallel, Entscheidung in fester Reihenfolge
**What:** Die Guard-Flight (Liste rund 48 ms, REPORT ab 59 ms, gemessen nc35) läuft parallel zur Primärabfrage, damit die Wanduhr nicht die Summe wird. Entschieden wird danach immer in derselben Reihenfolge: unverifiable schlägt jeden anderen Ausgang, auch einen 404 der Primärabfrage, sonst unterscheidet sich der Fehler zwischen existenten und nicht existenten Ids. [VERIFIED Latenzen: 25-MESSBERICHT K3 Referenz a, Stufe 1]
```python
# tools/files.py, read (Skizze)
target = dav.safe_path(path)             # reine Eingabeprüfung darf vorher werfen
scope, info = await asyncio.gather(
    clients.exclusion.scope(clients),
    dav.stat(clients.client, clients.creds, target),
    return_exceptions=True,
)
if isinstance(scope, BaseException):
    raise scope                           # nur ValueError aus der Identitätsprüfung möglich
if scope.state == "unverifiable":
    raise withhold.unavailable_error()    # identisch für jede Id, auch für nicht existente
if isinstance(info, BaseException):
    raise info                            # der normale 404 "File not found: {target}."
if scope.excludes(path=target, fileid=info["fileid"] or None):
    raise dav.not_found(target)           # byte-gleich zu dem 404 oben, eine Fabrik
# erst jetzt: is_collection, content_type, offset-Prüfungen
```
Wichtig: `gather(return_exceptions=True)` fängt keine `CancelledError`-Semantik weg, die der Guard braucht; ein Abbruch des Tool-Aufrufs bricht beide ab, der Guard speichert dann nichts (bestehendes Verhalten). [VERIFIED: exclusion.py ExclusionGuard-Docstring]

### Pattern 3: Eine Fehlerfabrik für echten 404 und Ausschluss
**What:** Die Byte-Gleichheit (Phase-28-Paartests) wird konstruktiv hergestellt, nicht per Kopie. `dav._check` (404-Zweig), `_check_write`/`_check_chunk_response` (404/409-Zweig) rufen künftig dieselben Fabriken wie der Guard-Pfad.
```python
def not_found(path: str) -> ToolError:
    return ToolError(
        message=f"File not found: {path}.",
        hint="List the parent folder first to get the exact spelling of the path.",
        reason=REASON_UNKNOWN_ID,
    )

def parent_missing(path: str) -> ToolError:
    parent = dirname(path) or "/"
    return ToolError(
        message=f"The parent folder {parent} of {path} does not exist.",
        hint="Create the folder in Nextcloud first, or upload into a folder that exists.",
        reason=REASON_UNKNOWN_ID,
    )
```
Die heutigen Texte stehen in dav.py:809-814 (`_check`), 688-694 (Chunk) und 751-757 (PUT); PUT- und Chunk-Variante sind heute wortgleich, auch der Hint. [VERIFIED: dav.py]

### Pattern 4: fileid zu Home-Pfad, ein SEARCH je Antwort
**What:** Für pfadlose Treffer eine Batch-Auflösung analog `build_fileid_body`, aber mit `d:or` über mehrere `d:eq oc:fileid`, Scope `search_scope(creds)` (also NC_MCP_FILES_ROOT), `nresults` = Anzahl der Ids, Ergebnis über `parse_entries` (die filtert bereits auf `in_files_root`). `d:or`, `d:eq` und die Suchbarkeit von `oc:fileid` sind offiziell dokumentiert. [CITED: docs.nextcloud.com/server/latest/developer_manual/client_apis/WebDAV/search.html] Nextcloud lehnt Anfragen mit mehr als 100 Operatoren ab [VERIFIED: Kommentar dav.py:266-268, Projektbefund], also in Blöcken zu höchstens 50 Ids und die Blöcke per `gather`.
```python
async def paths_of_fileids(client, creds, fileids: Sequence[str]) -> dict[str, str]:
    """fileid -> absolute home path, inside NC_MCP_FILES_ROOT only; missing = outside or gone."""
```
Nicht messbar ohne Live-Lauf: die Latenz eines `d:or` mit 25 bis 50 Ids auf SQLite und PostgreSQL. In den Live-Plan aufnehmen. [ASSUMED: Kosten ähnlich `find_by_fileid`, weil fileid Primärschlüssel ist]

### Pattern 5: `has_folders` statt ungenutztem `is_collection`
**What:** Ohne getaggten Ordner entscheidet die fileid allein (ein Knoten ohne getaggten Vorfahren ist nur ausgeschlossen, wenn er selbst getaggt ist). TagScope bekommt `has_folders: bool` aus `TaggedNode.is_collection`; dann entfällt die Pfad-Auflösung für Findling-, comments- und Notes-Treffer im häufigen Fall "nur einzelne Dateien getaggt, Root /". Damit ist Merker (e) "`_.is_collection` lesen oder Feld entfernen" entschieden: lesen. [VERIFIED: systemtags.py TaggedNode, vulture_whitelist.py:319-327]

### Pattern 6: Guard in prepare_context früh und ohne Bein-Budget anstoßen
**What:** Die Beine laufen unter eigenen Budgets (Talk 5 s, Excerpt 5 s, je Provider 15 s), TAG_BUDGET ist 15 s. Hält ein Bein mit kurzem Budget die Flight und läuft in sein Timeout, wird die Flight abgebrochen, nichts gespeichert, und der nächste Wartende startet eine zweite Flight (Merker (c)). Auf SQLite mit 5000 getaggten Knoten dauert der REPORT 8,1 bis 10,6 s, also länger als TALK_BUDGET. [VERIFIED: context.py Budgets, 25-MESSBERICHT K3/G1, deferred-items (c)]
**Empfehlung:** `prepare_context` ruft `clients.exclusion.scope(clients)` als erstes Mitglied seines `gather` auf, außerhalb jedes Bein-Budgets. Dann ist der Halter der Flight nie ein Bein mit kurzem Budget; Beine, die im Warten abbrechen, brechen nur ihr Warten ab. Das löst (c) für den einzigen realistischen Fall ohne `asyncio.shield`. Dasselbe gilt in `unified_search`: der Guard ist ein eigenes `gather`-Mitglied, nicht innerhalb von `_ask` (15-s-Provider-Timeout).

### Pattern 7: Frisches NcClients je Tool-Aufruf auch in Tests
**What:** Der Guard lebt genau so lange wie das NcClients-Objekt. Produktion baut es je Aufruf neu (`deps.resolve_clients`). [VERIFIED: deps.py:116-118, einzige Konstruktionsstelle in src] Die Integrations-Fixture `alice` in `tests/integration/test_ctx_bundle.py:226` lebt dagegen über alle Läufe; mit dem neuen Feld würde nur der erste Lauf die Flight bezahlen und ein nach dem ersten Aufruf gesetztes Tag nie gesehen. Live-Beweise und Wanduhr-Messungen müssen je Aufruf `dataclasses.replace(alice, exclusion=ExclusionGuard())` verwenden.

### Anti-Patterns to Avoid
- **Ausschluss erst nach Formprüfungen:** "is a folder, not a file", "is application/pdf and not text", "offset past the end", "is a file, not a folder" für einen getaggten Knoten verraten Existenz. Die Ausschlussprüfung steht direkt nach `stat`/PROPFIND und vor jeder Formprüfung.
- **Nach dem Schnitt filtern:** Buckets, `MAX_PER_BUCKET`-Sätze ("Only the first 5 of N hits"), `truncated`, `total` und Paginierungs-Offsets müssen auf der gefilterten Liste rechnen, sonst wird N zum Zähler.
- **`truncated` aus der Roh-Trefferzahl von files_search:** siehe Pitfall 3.
- **Tag-Drops in `skipped` zählen:** verboten (D-27-04). Sandbox-Drops (auch die aus der fileid-Auflösung) zählen weiter.
- **Neuer Cache für fileid zu Pfad:** vom Contract-Gate verboten und fachlich falsch (Pfade ändern sich).
- **Guard innerhalb einer Provider- oder Bein-Timeout-Hülle aufrufen:** siehe Pattern 6.

## Werkzeug-Landkarte (für die Planung und den Klassifikations-Freeze von Phase 28)

Aktive Registry: 22 Werkzeuge. [VERIFIED: server/reg_*.py]

| Werkzeug | Dateitragend? | Was trägt es | Einhängepunkt | Einzel oder Liste |
|----------|---------------|--------------|---------------|-------------------|
| files_list | ja | Pfad, Name, fileid je Kind; Ordner selbst | nach `propfind_children`: Ziel selbst prüfen, dann Kinder vor Sortierung/Schnitt filtern | Liste (Ziel selbst ausgeschlossen: `not_found(target)`) |
| files_search | ja | Pfad, Name, fileid | Treffer vor dem Fenster filtern; Nachladen bis Fenster voll (Pitfall 3) | Liste |
| files_read | ja | Inhalt, Pfad | Pattern 2 | Einzel |
| files_download | ja | Bytes, Pfad (auch in EmbeddedResource-URI) | Pattern 2 | Einzel |
| files_upload (Text + Binär, ein Tool) | ja (Orakel) | Existenz über Konflikt | vor jedem PUT/MKCOL/MOVE, bei jedem Chunk-Aufruf | Upload (D-27-01/02) |
| unified_search | ja | Treffer aller Provider inkl. Findling-Ausschnitte | nach `_normalise`-Vorstufe, vor `results` | Liste |
| search (ChatGPT) | ja | wie unified_search | erbt von unified_search | Liste |
| fetch | ja (file, note, message) | Inhalt, Titel = Dateiname | `_fetch_file` vor `find_by_fileid`-Auswertung; note über notes.read; message über one_room/_resolve | Einzel |
| prepare_context | ja | Treffer, Ausschnitte, Talk-Digest (Vorschau mit Platzhaltern) | erbt; Guard früh anstoßen; degraded deduplizieren | Liste |
| notes_search | ja | Titel, Ausschnitt | nach Provider-Antwort, fileid-Auflösung | Liste |
| notes_read | ja | Inhalt | vor dem Notes-API-Aufruf | Einzel |
| notes_create | Orakel möglich | `renamed` bei Namenskollision in getaggter Kategorie; Schreiben außerhalb Sandbox | Open Question 1 | Upload-artig |
| talk_browse | ja | Platzhalter `{file}`, Raumname von Datei-Konversationen, Vorschau | `_resolve`, `_conversations`, `one_room` | Liste |
| talk_send | indirekt | Antwort trägt `conversation` = Raumname (Datei-Konversation) | `one_room` | Einzel (Open Question 2) |
| calendar_list_events, calendar_create_event | nein | Termine; ATTACH wird nicht projiziert | , | , |
| contacts_search | nein | vCards | , | , |
| deck_browse, deck_create_card | nein | Karten-Titel, Beschreibung, Fälligkeit; Anhänge werden nicht projiziert (API 1.0) | , | , |
| mail_browse | nein | Mails; nur `has_attachments`-Flag, Mail-Anhänge sind keine Nextcloud-Dateien | , | , |
| tables_browse, tables_create_row | nein | Zeilen; kein Dateityp in Spalten projiziert | , | , |

[VERIFIED: tools/deck.py:120-190, tools/calendar.py:306-313/443-449, tools/mail.py:465-506 per grep; die "nein"-Zeilen sind Projektionsbefunde, keine Aussage darüber, was Nutzer in Freitext schreiben]

## Familie Dateien (EXCL-01)

- **Pfadform:** `parse_entries` liefert absolute Home-Pfade, nicht den virtuellen Root-Blick; `excludes` erwartet genau diese Form. `safe_path` bildet virtuelle Pfade vorher auf Home-Pfade ab. [VERIFIED: dav.py:85-122, 466-480; exclusion.py `excludes`-Docstring]
- **files_list:** `propfind_children` liefert `(itself, children)`. Ziel ausgeschlossen (Pfad oder fileid von `itself`) wird zu `dav.not_found(target)`, byte-gleich zum 404 von `_check`. Kinder werden vor `sort`/Fenster gefiltert, `truncated`/`next` aus der gefilterten Länge. Bei unverifiable: leere `items`, `count` 0, ein degraded-Eintrag, kein `next`; empfohlen, die PROPFIND-Antwort dann gar nicht auszuwerten (sie kann nichts zeigen), damit auch ein nicht existentes Ziel dieselbe Antwort bekommt.
- **files_read / files_download:** Pattern 2. Zusätzlich die fileid aus `stat` prüfen, das fängt abweichende Schreibweisen auf case-insensitiven externen Speichern für den Knoten selbst (nicht für Teilbäume, siehe Pitfall 6).
- **Upload (files_upload Text und Binär):** Prüfung `scope.excludes(path=target)` vor `put_new_file`, `start_chunked_upload`, `put_upload_chunk` und `finish_chunked_upload`, bei jedem Tool-Aufruf (jeder Chunk ist ein eigener Aufruf, das Tag kann zwischen zwei Chunks gesetzt werden; die abschließende MOVE ist das eigentliche Anlegen). Kosten: ein REPORT je Chunk-Aufruf, rund 60 ms gegen 8 MiB Upload, vernachlässigbar.
- **Upload-Grenzfall (Claude's Discretion, D-27-01), Empfehlung:** auch die direkt getaggte Datei unter sichtbarem Elternordner bekommt `dav.parent_missing(target)`. Begründung zum Dokumentieren: Jede Abweisung unterscheidet sich von dem 201, den ein wirklich freier Name bekäme; "A file already exists" verriete Existenz, "parent does not exist" verrät bei sichtbarem Elternordner, dass dort etwas Besonderes liegt. Beide Restorakel sind gleich stark (unsichtbar plus abgewiesen heißt ausgeschlossen), keines ist vermeidbar ohne zu schreiben. Ein Wortlaut für alle Ausschluss-Abweisungen ist deshalb das Konsistenteste. Das Restorakel gehört in die Phase-29-Doku.
- **Upload bei unverifiable (D-27-02):** `withhold.unavailable_error()` ohne Pfad im Text (gleich für alle Ziele), kein Schreib-Request.

## Familie Suche, fetch, prepare_context (EXCL-03, SBX-01)

### Befunde zu den Providern

| Provider | Was ein Eintrag trägt | Quelle |
|----------|----------------------|--------|
| files | `attributes.fileId`, `attributes.path` (relativ zur Nutzer-Home) | [VERIFIED: provider_map.py:55-61 Kommentar mit Quellbezug] |
| findling | `attributes.fileId`, optional `highlights`; subline = Ausschnitt oder Pfad; resourceUrl `/index.php/f/<id>`; ein "Show all results"-Tür-Eintrag ohne fileId | [VERIFIED: nextcloud-search/php/lib/Search/Provider.php:368-446] |
| notes | kein attributes; Notiz-Id (= fileid) nur in resourceUrl | [VERIFIED: provider_map.py:62-68; 25-MESSBERICHT K4] |
| systemtags | Tag-Einträge ("All tagged %s ...", ohne fileId) und Datei-Einträge mit `fileId` und `path` für Dateien, die ein passendes Tag tragen | [CITED: github.com/nextcloud/server apps/systemtags/lib/Search/TagSearchProvider.php] |
| comments | Titel = Autor, subline = Dateipfad, resourceUrl `files.View.showFile` mit fileid, keine attributes | [CITED: github.com/nextcloud/server apps/comments/lib/Search/CommentsSearchProvider.php] |
| talk-message(-current) | attributes conversation/messageId; subline = Nachrichtentext mit ersetzten Parametern (`{file}` wird zum Dateinamen), gesucht werden auch `object_shared`-Nachrichten | [CITED: github.com/nextcloud/spreed lib/Search/MessageSearch.php] |

Heute lässt `search._entry_in_files_root` jeden Eintrag eines Nicht-files-Providers ohne `attributes.path` durch; Findling, notes und comments umgehen damit die Sandbox. [VERIFIED: search.py:240-255] Das ist SBX-01/SBX-02 im Code.

### Empfohlene Mechanik in unified_search
1. Guard als eigenes `gather`-Mitglied neben den Provider-Aufrufen (Pattern 6).
2. Ein öffentlicher Extraktor `file_refs(provider_id, entry) -> (fileid | None, path | None)`, providerunabhängig: `attributes.fileId` (nur ASCII-Ziffern), `attributes.path` (normalisiert zu `"/" + raw.strip("/")`, geprüft mit `_plain_path`), fileid aus `/f/<id>` der resourceUrl (dieselbe Regel wie `provider_map._file_id`, dann als öffentliche Funktion), Notiz-Id für den notes-Provider. Ein Eintrag mit irgendeinem davon ist dateitragend.
3. Sandbox zuerst (D-27-04): Einträge mit path wie heute über `in_files_root`; pfadlose über `paths_of_fileids`, wenn Root ungleich `/` oder `scope.has_folders`. Nicht aufgelöst = Sandbox-Drop, `skipped += 1`.
4. Dann `scope.excludes(path=..., fileid=...)`, lautlos.
5. Bei unverifiable: alle dateitragenden Einträge weg, nicht dateitragende bleiben, EIN degraded-Eintrag im Idiom `{"provider": ..., "reason": EXCLUSION_UNAVAILABLE}` (Schlüsselname frei, Empfehlung ein fester Pseudo-Name wie `"exclusion"`).
6. systemtags-Tag-Einträge ohne fileId: Empfehlung stehen lassen. Sie nennen einen Tag, den der Nutzer ohnehin in der Tag-Auswahl sieht, nicht die getaggte Menge; die Datei-Einträge desselben Providers laufen durch Schritt 2 bis 4. [ASSUMED: die Existenz eines sichtbaren Tags ist kein Geheimnis im Sinne von EXCL-03]

### fetch
- `_fetch_file`: Guard vor der Auswertung von `find_by_fileid` (beide parallel). unverifiable: uniformer Fehler. fileid in der Menge: derselbe Satz wie "This account has no file with the id {fileid}." inklusive Hint, noch bevor ein Pfad bekannt ist; sonst Pfad aus `find_by_fileid` prüfen (Teilbaum). Erst danach `files_tools.read`, das den Guard über dasselbe NcClients teilt (Fast Path, kein zweiter REPORT). Diese Reihenfolge erfüllt "eine vor dem Taggen bekannte fileid liefert nichts mehr" (Erfolgskriterium 2). [VERIFIED: chatgpt.py:231-276]
- Der Not-found-Satz von `_fetch_file` hat heute keinen `reason`; für die Byte-Gleichheit muss der Ausschlusspfad exakt dasselbe Objekt bauen, also ebenfalls eine Fabrik.
- `url:`-Ids (auch Findling-Treffer, die als `url:` kodiert sind, weil `findling` nicht in `PROVIDER_KINDS` steht) werden nie geladen und antworten für jede Id gleich; kein Handlungsbedarf. [VERIFIED: chatgpt.py:224-228, provider_map.py]

### prepare_context
- Erbt die Filterung aus unified_search; `_bundle` zählt dann bereits gefilterte Treffer, die Kappungssätze bleiben orakelfrei. [VERIFIED: context.py:523-546]
- Ausschnitte laufen über `chatgpt.fetch` mit demselben NcClients, also ohne zweiten REPORT. [VERIFIED: context.py:768-776]
- Der Talk-Digest projiziert `last_message` über `talk._preview` und `_resolve`; er ist damit ein Platzhalter-Kanal und braucht den Scope (siehe Talk).
- degraded: unified_search und der Talk-Zweig schreiben bei unverifiable je einen Eintrag; D-27-03 verlangt EINEN je Familie. Empfehlung: prepare_context dedupliziert Einträge mit dem Wortlaut EXCLUSION_UNAVAILABLE auf einen `{"source": ..., "reason": ...}`.
- Wanduhr-Referenz: nc35, Phase 25, `detail='short'` Median 0,72 s, `detail='full'` Median 0,81 s (je drei Läufe), leer und mit 20.000 Spike-Dateien gleich (0,72/0,82). [VERIFIED: 25-MESSBERICHT K3, raw/nc35-prepare-context-baseline.txt] Die bestehende Messung `test_the_wall_clock_of_four_legs_stays_under_one_budget` misst genau diese Zahlen, muss aber je Lauf ein frisches NcClients bekommen (Pattern 7).

## Familie Notes (EXCL-05, SBX-02)

- **Id:** Notiz-Id ist die fileid (933/933, 934/934 inkl. umbenannter Datei). Ein getaggter Kategorieordner erscheint im REPORT nur als Ordner-fileid (932), Notizen darunter nur über den Pfad. [VERIFIED: 25-MESSBERICHT K4]
- **Pfad:** Die Notes-API liefert keinen Dateinamen, die Suche (Provider `notes`) nicht einmal die Kategorie. [VERIFIED: tools/notes.py, clients/notes.py] Der robuste Weg ist dieselbe fileid-Auflösung wie bei Findling: `paths_of_fileids` gibt den echten Pfad (`/Notes/<Kategorie>/<Datei>.md`) und prüft zugleich NC_MCP_FILES_ROOT. Der alternative Weg über `GET /apps/notes/api/v1/settings` (notesPath) plus Kategorie braucht für notes_search je Treffer die Kategorie und damit N Requests. [ASSUMED: Inhalt der settings-Antwort; die Route selbst ist im notes.py-Docstring als vorhanden gelistet]
- **notes_search:** Treffer-Ids sammeln, eine Auflösung, Sandbox-Drops in `skipped`, Tag-Drops lautlos. unverifiable: `results` leer plus ein degraded-Eintrag (das Idiom existiert in notes_search noch nicht, es kommt neu hinzu).
- **notes_read und fetch(note):** vor dem Notes-API-Aufruf Guard und Auflösung. Nicht auflösbar, ausgeschlossen, und auch ein 404 der Notes-API: alle drei auf EINEN Satz abbilden. Grund: heute wird ein 404 zu "Nextcloud did not find the note 12. Nextcloud says: <Fremdtext der Notes-App>" (ocs.py:295-300). Wenn der Ausschlusspfad einen eigenen Satz baut, unterscheidet sich eine getaggte Nicht-Notiz-Datei (fileid existiert, Notes-API antwortet 404 mit Detail) von einer ungetaggten; das wäre ein fileid-Orakel über notes_read. [VERIFIED: ocs.py `_status_error`, tools/notes.py read]
- **Notizen außerhalb der Sandbox:** verschwinden wie nicht existente (SBX-02, Erfolgskriterium 3). Das ändert das sichtbare Verhalten für Instanzen mit gesetztem NC_MCP_FILES_ROOT, wenn der Notes-Ordner nicht darunter liegt: notes_search wird dort leer. Das ist die geforderte Parität, gehört aber in die Phase-29-Doku.

## Familie Talk (EXCL-06, D-27-06)

- **Eine Ersetzungsstelle:** `_resolve(message, parameters)` in talk.py:574-604, aufgerufen von `_message` (Nachrichten-Ebene), `_preview` (Konversationsliste und damit prepare_context-Digest) und über `one_message` von `chatgpt._fetch_message`. messageParameters verlassen die Antwort heute sonst nirgends (`_message` und `_conversation` projizieren eine feste Feldliste). [VERIFIED: talk.py:395-452, 513-571]
- **Form des Datei-Parameters:** `type: "file"`, `id` = fileid als String, `name`, `path` relativ zur Nutzer-Home des Betrachters (für Eigentümer und für andere Teilnehmer aus deren eigenem Nutzerordner), dazu `link`, `mimetype`, `etag` usw.; Gäste bekommen `path = name`. [CITED: github.com/nextcloud/spreed lib/Chat/Parser/SystemMessage.php getFileFromShare] Damit passt `"/" + path` zur Pfadform des REPORT (beide aus der Sicht desselben Nutzers).
- **Umsetzung:** `_resolve` bekommt den Scope (oder eine Prüffunktion). Für Einträge mit `type == "file"`: unverifiable oder `excludes(path="/" + path, fileid=id)` → `match.group(0)` zurückgeben, exakt wie der Unbekannt-Pfad. Fehlt `path`, entscheidet bei `has_folders == False` die fileid allein, sonst Auflösung über `paths_of_fileids` (oder konservativ roh lassen; Planentscheidung). Den Guard nur anfragen, wenn im Fenster überhaupt ein Datei-Parameter vorkommt: eine Antwort ohne Datei kostet dann null REPORTs, was E3 ("höchstens einer") erfüllt.
- **Zusatzkanal Datei-Konversationen (über EXCL-06 hinaus, Open Question 2):** Talk kennt `OBJECT_TYPE_FILE = 'file'` [VERIFIED: github.com/nextcloud/spreed lib/Room.php]. Die Seitenleisten-Unterhaltung zu einer Datei ist so ein Raum; sein `displayName` ist der Dateiname und `objectId` die fileid [ASSUMED: aus dem FilesIntegration-Weg von spreed, nicht gelesen]. Dieser Name erscheint in `talk_browse` (Konversationsliste und Nachrichten-Umschlag `conversation`), in `talk_send` (Antwortfeld `conversation`, Fehlertexte mit Name) und in `fetch(message)` (Titel). Alle drei laufen über `one_room` bzw. `_conversations`; ein Filter dort ("ausgeschlossener Datei-Raum = Token nicht in der Liste", derselbe ToolError wie ein unbekanntes Token) deckt sie ab.
- **Zusatzkanal talk-message-Suchprovider (Open Question 3):** Der subline enthält den Dateinamen einer geteilten Datei, und `object_shared`-Nachrichten werden durchsucht. [CITED: MessageSearch.php] Ob ein Suchbegriff eine Datei-Nachricht überhaupt trifft (der gespeicherte Kommentartext einer Dateifreigabe ist JSON mit Freigabe-Id, nicht der Dateiname), ist nicht belegt [ASSUMED]. Live messen, bevor gebaut wird.
- **Live-Aufbau für Erfolgskriterium 4:** Datei als alice hochladen, per OCS-Share (shareType 10, shareWith = Token) in eine Konversation teilen, `occ tag:files:add <fileid> kein-ki public`, dann talk_browse(messages), talk_browse(conversations) und fetch(message) prüfen. [ASSUMED: shareType 10 für Talk-Räume, Standard der files_sharing-API]

## Offene Review-Infos aus Phase 26 (vor der Verdrahtung)

- **IN-02 (`_home_path_of`, dav.py:527-536):** Der im Review vorgeschlagene Fix `"/".join(unquote(seg) for seg in path.split("/"))` ist wirkungslos: ein Segment `A%2Fkein` wird zu `A/kein` decodiert und durch das Join wieder zu einem Trenner. Richtig ist: segmentweise decodieren und `None` zurückgeben, wenn ein decodiertes Segment `/` (oder `\x00`) enthält. `None` endet in `home_entries` fail-closed in unverifiable (`foreign_href`) und wird in `parse_entries` verworfen. [VERIFIED: Code gelesen, Verhalten von `urllib.parse.unquote` ist Standard]
- **IN-03 (`_plain_path`, dav.py:520-524):** zusätzlich `"//" in path` ablehnen, nicht per Segmentliste, damit `/` gültig bleibt. Betrifft `in_files_root` und `home_entries` gleichermaßen, beide Seiten bleiben konsistent.
- **IN-01 (doppelte Home-Präfix-Berechnung, dav.py:473/496):** im selben Zug eine `_home_prefix(creds)`; es ist dieselbe Funktion, die IN-02 anfasst, und genau dort vergleicht der Guard.
- **Tests:** `tests/unit/test_dav_home_entries.py` (u.a. `test_unsafe_segments_become_none`, parametrisiert über hrefs) um `%2F`-Segment und `//` erweitern; zusätzlich ein Fall in `test_exclusion.py`, dass ein solcher href im REPORT zu `unverifiable/foreign_href` führt. [VERIFIED: Testnamen per grep]
- **IN-04** (TTL-Test patcht globales `time.monotonic`) ist nicht verdrahtungsrelevant; optional mitnehmen.

## Merker aus deferred-items

- **(e) Pflicht:** NcClients-Feld (Pattern 1); vulture-Abschnitt "The guard core of phase 26, wired in by phase 27" räumen: `_.excludes` fällt weg, sobald die erste Familie `excludes` aufruft; `_.is_collection` fällt weg, wenn `has_folders` es liest (Pattern 5). Jeder neue öffentliche Helfer, der erst einen Plan später einen Aufrufer bekommt, braucht einen eigenen Whitelist-Eintrag mit Testverweis und muss mit dem aufrufenden Plan wieder gehen (Projektbrauch, siehe Abschnitte in vulture_whitelist.py). [VERIFIED: vulture_whitelist.py:319-340]
- **(c) Flight-Halter-Abbruch:** in prepare_context und unified_search real möglich (Pattern 6); durch frühen Anstoß ohne Bein-Budget gelöst, kein `asyncio.shield` nötig.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Tag-Menge, 412, Varianten, Budget | eigene REPORT-Aufrufe in Tools | `clients.exclusion.scope(clients)` | Automat, Single-Flight und fail-closed sind getestet (26-VERIFICATION) |
| Teilbaum-Vergleich | `startswith`-Vergleiche in Tools | `TagScope.excludes` (nutzt `ancestors`, bewiesen gleich `dav.within`) | Segmentregel `/A/kein` vs `/A/keine` |
| Not-found- und Parent-missing-Texte | kopierte f-Strings | `dav.not_found`, `dav.parent_missing`, eine Fabrik für den fetch-Satz | Byte-Gleichheit ist die Phase-28-Prüfung |
| fileid zu Pfad | PROPFIND-Walk, N Einzel-SEARCHes, Notes-settings-Rekonstruktion | ein SEARCH `d:or` im `search_scope` | ein Request, Sandbox serverseitig |
| XML-Bodies | f-Strings | lxml wie `build_fileid_body` | T-01-11/T-01-30 |
| Wartezeit-Hülle für den Guard | eigenes Timeout um `scope()` | TAG_BUDGET im Guard | ein zu kurzes äußeres Timeout erzeugt Abbruch-Doppelflights |

**Key insight:** Jede Stelle, die einen Text, einen Zähler oder eine Reihenfolge eigenständig baut, ist eine potenzielle Unterscheidbarkeit zwischen "getaggt" und "gibt es nicht". Fabriken und eine feste Entscheidungsreihenfolge machen das prüfbar.

## Common Pitfalls

### Pitfall 1: Alle bestehenden Familien-Tests brechen am ersten verdrahteten Guard
**What goes wrong:** respx läuft standardmäßig mit `assert_all_mocked=True`; der neue `PROPFIND /remote.php/dav/systemtags/` ist in keinem bestehenden Test gemockt. respx wirft dann einen AssertionError-Abkömmling, den `load_scope` nicht fängt (es fängt nur Timeout, httpx.HTTPError, ToolError, ValueError). [VERIFIED: exclusion.py `load_scope`; 483 Tests in den 13 betroffenen Unit-Dateien, alle grün am 27.09.]
**How to avoid:** Wave-0-Helfer `tests/unit/guard_routes.py` mit `untagged(mock)`, `active(mock, nodes)`, `unverifiable(mock)` und je Familien-Datei eine Fixture, die die Untagged-Route setzt. Tests mit `assert_all_called=True` brauchen die Route nur dort, wo der Guard wirklich gefragt wird (bei faul fragenden Familien wie Talk nicht).
**Warning signs:** `AllMockedAssertionError` in vielen Dateien gleichzeitig.

### Pitfall 2: Langlebiges NcClients misst und prüft den falschen Zustand
**What goes wrong:** Eine Fixture, die ein NcClients über mehrere Tool-Aufrufe hält, cached den Scope des ersten Aufrufs; "Tag setzen, dann prüfen" wird grün, obwohl nichts gefiltert wird, und Wanduhren enthalten die Flight nur einmal. [VERIFIED: test_ctx_bundle.py:226-231]
**How to avoid:** Pattern 7, `dataclasses.replace(clients, exclusion=ExclusionGuard())` je Aufruf.

### Pitfall 3: files_search `truncated` wird zum Zähler
**What goes wrong:** Heute holt files_search `offset + capped + 1` Treffer und setzt `truncated`, wenn mehr als das Fenster kam. Nach dem Filtern kann das Fenster kurz sein, während die Rohliste voll war; `truncated: true` mit drei Treffern verrät zurückgehaltene Einträge. Umgekehrt kann ein Filter die Wächterzeile entfernen und die nächste Seite überspringen. [VERIFIED: files.py:133-155]
**How to avoid:** Offsets beziehen sich auf die gefilterte Liste; wenn die Rohliste voll war (`len(hits) == fetch`) und gefiltert zu wenig übrig blieb, mit größerem Limit erneut suchen, bis genug sichtbare Treffer plus Wächter da sind, die Rohliste kürzer als angefordert ist, oder `MAX_SEARCH_FETCH` erreicht ist (dann greift der bestehende Kappungssatz, der nur die Roh-Obergrenze nennt). Jeder Nachlade-SEARCH kostet einen Request, keinen REPORT (derselbe Scope).

### Pitfall 4: Formprüfung vor Ausschlussprüfung
**What goes wrong:** siehe Anti-Patterns; ein getaggtes PDF bekommt bei files_read "is application/pdf and not text" statt "File not found".
**How to avoid:** Ausschluss direkt nach der Metadaten-Abfrage, als erstes nach unverifiable.

### Pitfall 5: Importzyklus nextcloud/__init__ und exclusion
**What goes wrong:** `ImportError: cannot import name 'NcClients' from partially initialized module`. [VERIFIED: Importstruktur]
**How to avoid:** Pattern 1.

### Pitfall 6: Schreibweisen-Abweichungen zwischen Modell-Pfad und REPORT-Pfad
**What goes wrong:** Auf case-insensitiven externen Speichern (SMB) oder bei Unicode-NFD-Eingaben trifft der Präfixvergleich den getaggten Ordner nicht. [ASSUMED: Nextcloud normalisiert Pfade intern auf NFC; externe Speicher können case-insensitiv sein]
**How to avoid:** Bei Einzelzugriffen zusätzlich die fileid aus `stat` prüfen (deckt den Knoten selbst). Die Teilbaum-Lücke auf case-insensitiven externen Speichern als Grenze in Phase 29 dokumentieren.

### Pitfall 7: Integrationstest der Request-Kosten ändert seine Zahlen
**What goes wrong:** `test_the_request_cost_of_one_bundle_cold_and_warm` zählt Requests je Bündel; der Guard fügt Tag-Liste, ggf. REPORT und ggf. eine fileid-Auflösung hinzu. [VERIFIED: test_ctx_bundle.py:406-486]
**How to avoid:** Die Guard-Requests in der Tally als eigene Kategorie zählen und die Erwartung neu verankern (Messung statt Schätzung, Projektregel).

### Pitfall 8: Guard-Anfrage im Talk-Zweig auch ohne Datei
**What goes wrong:** Der Talk-Digest ist das schnellste Bein (0,04 s); ein unbedingter Guard-Aufruf dort macht ihn im SQLite-Worst-Case zum Timeout-Kandidaten und bei kurzem Budget zum Flight-Halter.
**How to avoid:** Guard nur bei vorhandenem Datei-Parameter und in prepare_context ohnehin früh angestoßen (Pattern 6).

### Pitfall 9: Uniformer Fehler mit Id im Text
**What goes wrong:** Ein unavailable-ToolError, der Pfad oder Id nennt, ist nicht mehr "für ALLE Ids gleich". [VERIFIED: D-27-03]
**How to avoid:** Konstante Nachricht und Hint ohne Parameter; `reason=REASON_GUARD_TRIPPED` (existiert, die REASONS-Menge bleibt eingefroren). [VERIFIED: errors.py:34-71]

## Code Examples

### Einheitlicher Wortlaut und Helfer (Skizze, Namen frei)
```python
# tools/withhold.py  (English in code, per project rule)
from ..errors import REASON_GUARD_TRIPPED, ToolError

#: D-27-05: the one sentence for degraded entries, single-access errors and upload refusals.
EXCLUSION_UNAVAILABLE = (
    "The exclusion check (tag kein-ki) could not be answered, so entries that may carry "
    "file content are withheld."
)

def unavailable_error() -> ToolError:
    # Identical for every id and every path: the error itself must not become an oracle.
    return ToolError(
        message=EXCLUSION_UNAVAILABLE,
        hint="Retry in a minute; if it persists, ask an administrator to check the system tags.",
        reason=REASON_GUARD_TRIPPED,
    )

def degraded_entry(key: str, name: str) -> dict[str, str]:
    return {key: name, "reason": EXCLUSION_UNAVAILABLE}
```

### Talk-Platzhalter wie der Unbekannt-Pfad
```python
# tools/talk.py, inside _resolve.replace (Skizze)
entry = params.get(match.group(1))
if not isinstance(entry, dict):
    return match.group(0)
if str(entry.get("type") or "") == "file" and hidden(entry):  # scope-bound predicate
    return match.group(0)                                      # stays exactly "{file}"
name = str(entry.get("name") or "").strip()
```

### Tag im Live-Harness setzen (nie in src/)
```python
# pattern of scripts/tag_spike.py:936-946
occ(container, "tag:files:add", fileid, "kein-ki", "public")
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Sandbox nur über `attributes.path` des files-Providers | Sandbox für jeden dateitragenden Treffer über Pfad oder fileid-Auflösung | diese Phase | Findling, notes, comments bekommen dieselbe Grenze |
| Notes ohne Sandbox | Notes über fileid-Auflösung im Sandbox-Scope | diese Phase | Notes außerhalb der Root verschwinden |
| Notes-404 mit Fremdtext | ein Not-found-Satz für notes_read | diese Phase | kein fileid-Orakel über notes_read |

**Deprecated/outdated:** der IN-02-Fixvorschlag aus 26-REVIEW (wirkungslos, siehe oben).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Batch-SEARCH mit `d:or` aus bis zu 50 `d:eq oc:fileid` ist so billig wie ein Einzel-`find_by_fileid` | Pattern 4 | Wanduhr von unified_search/notes_search steigt; dann Blockgröße senken oder nur bei Bedarf auflösen (has_folders/Root) |
| A2 | Existenz eines sichtbaren Tags ist kein Geheimnis; nur die Menge ist es | Suche, systemtags | Tag-Einträge des systemtags-Providers müssten zusätzlich weg |
| A3 | Datei-Konversationen tragen `displayName` = Dateiname und `objectId` = fileid | Talk | Filter in one_room greift ins Leere oder zu weit; live prüfen |
| A4 | talk-message-Provider trifft Datei-Nachrichten nicht über den Dateinamen | Talk | Dateinamen-Leck in unified_search über subline; Kanarientest (Phase 28) würde es finden |
| A5 | Notes settings-Route liefert notesPath (nur relevant, wenn notes_create in Scope kommt) | Notes | kein Einfluss auf read/search |
| A6 | shareType 10 teilt eine Datei in einen Talk-Raum | Live-Beweis Talk | nur Testaufbau betroffen |
| A7 | Nextcloud-Pfade sind NFC-normalisiert, externe Speicher können case-insensitiv sein | Pitfall 6 | Teilbaum-Lücke auf Sonderspeichern, dokumentieren |
| A8 | "Im Rahmen der Phase-25-Referenz" heißt: Median short/full höchstens rund 0,1 bis 0,15 s über 0,72/0,81 s (eine Tag-Liste plus REPORT, parallel angestoßen) | prepare_context | Abnahmekriterium unscharf; Schwelle im Plan festlegen oder beim Owner bestätigen |

## Open Questions

1. **notes_create in Scope?**
   - What we know: SBX-02 sagt "Notes laufen durch Sandbox- und Ausschlussprüfung"; notes_create schreibt in `notesPath/<Kategorie>` auch außerhalb von NC_MCP_FILES_ROOT, und das Feld `renamed` verrät eine Namenskollision in einer getaggten Kategorie (Existenz-Orakel wie beim Upload).
   - What's unclear: ob der Owner das Anlegen in dieser Phase anfassen will (Verhaltensänderung).
   - Recommendation: mitbauen wie D-27-01: Kategorieordner (notesPath aus settings plus Kategorie) ausgeschlossen oder außerhalb der Sandbox → Abweisung im parent-missing-Stil; bei unverifiable → unavailable_error. Sonst im Plan ausdrücklich als Grenze für Phase 29 benennen.
2. **Datei-Konversationen (Talk) mitnehmen?**
   - What we know: Raumname kann der Dateiname sein; drei Werkzeuge zeigen ihn.
   - Recommendation: in `one_room` und `_conversations` filtern (billig, eine Stelle, byte-gleich zu "token not in list"); talk_send wird damit im Freeze von Phase 28 "betroffen". Live bestätigen (A3).
3. **talk-message-Suchtreffer bei unverifiable und bei Datei-Freigaben?**
   - Recommendation: zuerst live messen (Datei mit eindeutigem Namen teilen, nach dem Namen und nach einer Beschriftung suchen). Trifft die Suche, message-Treffer als dateitragend behandeln, wenn der subline den Namen eines Datei-Parameters tragen kann; sonst als nicht dateitragend klassifizieren und dokumentieren.
4. **Findling live in dieser Phase?**
   - What we know: Findling ist weder auf nc35 noch auf der nc-mcp-exapp-Topologie installiert; die CI-Strecke `exapp` installiert es per `scripts/install_findling.sh` (NC 34) und fährt `test_content_hit_fidelity.py`. [VERIFIED: occ app:list, ci.yml]
   - Recommendation: Erfolgskriterium 3 unit-seitig mit der echten Findling-Eintragsform (Provider.php) beweisen und live mit dem Stock-`comments`-Provider (gleiche Klasse "fileid nur in URL"); einen Findling-Livefall als CI-Test in den bestehenden Findling-Schritt hängen.
5. **Abnahmeschwelle Wanduhr (A8):** im Plan als Zahl festlegen.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| nc35-Topologie (nc35-nc, harp, caddy, greenmail, ExApp) | Live-Beweise SC 1, 2, 4, 5 | ✓ (läuft seit 46 h) | NC 35.0.0, sqlite3 | , |
| notes auf nc35 | EXCL-05 live | ✓ | 6.1.0 | , |
| spreed auf nc35 | EXCL-06 live | ✓ | 25.0.0 | , |
| systemtags / comments auf nc35 | Tag setzen, comments-Provider als pfadloser Fall | ✓ | 2.0.0-dev.0 / 2.0.0-dev.0 | , |
| Findling auf nc35 oder nc-mcp-exapp | SBX-01 live mit echtem Findling | ✗ | , | Unit mit echter Eintragsform + comments-Provider live; CI-Schritt `install_findling.sh` |
| `.env.nc35` | Live-Läufe | ✓ | , | , |
| `.venv/Scripts/python.exe` | Tests (uv sync blockiert) | ✓ | Python 3.13, respx 0.23.1, httpx 0.28.1 | , |
| PostgreSQL-Instanz | nicht nötig (Latenz ist in 25-05 gemessen) | , | , | , |

**Missing dependencies with no fallback:** keine.
**Missing dependencies with fallback:** Findling live (siehe Open Question 4).

## Validation Architecture

(`workflow.nyquist_validation` ist `false` in .planning/config.json; der Abschnitt entfällt. Teststrategie steht in "Common Pitfalls" und im folgenden Kurzüberblick.)

- Unit (respx): je Familie drei Zustände (untagged byte-gleich zu heute, active mit Datei + Datei unter Ordner + Ordner oberhalb Root, unverifiable mit genau einem degraded-Eintrag bzw. uniformem Fehler); `REPORT`-`call_count == 1` je Tool-Aufruf auch für prepare_context `detail="full"` mit Ausschnitten; Paartests "getaggt gegen nicht existent" als Vorstufe für Phase 28.
- Contract: bestehende Gates grün (Modulgrenzen, keine neuen Caches, keine destruktiven Aufrufe).
- Live (`-m integration`, nc35, frisches NcClients je Aufruf): Tag per occ auf Datei und Ordner, alle Datei-Werkzeuge, fetch mit vorher gemerkter fileid, systemtags- und comments-Provider, Notiz in getaggter Kategorie und außerhalb der Root, Talk-Freigabe, prepare_context-Wanduhr gegen 0,72/0,81 s; unverifiable live über respx-Passthrough mit injiziertem 500 nur für den REPORT. Kommando wie Phase 25: Env aus `.env.nc35`, `.venv/Scripts/python.exe -m pytest tests/integration/<datei> -m integration -s`.
- Gates vor jedem Commit: `ruff check .`, `ruff format --check .`, `pyright` (latest), `vulture src scripts vulture_whitelist.py`, `pytest tests/unit tests/contract`, `scripts/check_tool_budget.py` (Tool-Beschreibungen ändern sich nicht, soll so bleiben).

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | nein | unverändert |
| V3 Session Management | nein | unverändert |
| V4 Access Control | ja (Kern der Phase) | Guard je Antwort, fail-closed, Sandbox für alle dateitragenden Treffer |
| V5 Input Validation | ja | `safe_path`, ASCII-Ziffern für fileids (`_DIGITS`), lxml-Bodies, href-Normalisierung (IN-02/03) |
| V6 Cryptography | nein | , |
| V7 Error Handling | ja | Fehlerfabriken, uniforme Fehler, feste Entscheidungsreihenfolge, keine Id im unavailable-Text |
| V8 Data Protection | ja | keine Tag-Menge über den Aufruf hinaus, kein Pfad-Cache |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Existenz-Orakel über Fehlertext (read/download/list/fetch/notes) | Information Disclosure | eine Fabrik je Satz, Ausschluss vor Formprüfung |
| Orakel über Zähler (`skipped`, `truncated`, Bucket-Sätze, `total`) | Information Disclosure | vor dem Schnitt filtern, Tag-Drops nie zählen, files_search nachladen |
| Upload-Konflikt-Orakel | Information Disclosure | D-27-01 parent-missing, D-27-02 fail-closed |
| Dateiname über Nebenkanäle (Talk-Platzhalter, Datei-Räume, comments-subline, talk-message-subline) | Information Disclosure | `_resolve`/`one_room`-Filter, generischer Datei-Extraktor, Live-Messung |
| Fehlnormalisierte hrefs verschieben Pfadgrenzen | Tampering | IN-02 (decodiertes Segment mit `/` ablehnen), IN-03 |
| Doppelte Flight durch Abbruch, REPORT-Last | Denial of Service | Guard früh ohne Bein-Budget anstoßen, TAG_BUDGET |
| Zeitunterschied getaggt vs. nicht existent | Information Disclosure | gleiche Request-Folge (stat immer, dann entscheiden); Rest als LOW dokumentieren |

## Sources

### Primary (HIGH confidence)
- Repo-Code gelesen: `nextcloud/exclusion.py`, `nextcloud/clients/{systemtags,dav,notes,ocs}.py`, `nextcloud/__init__.py`, `deps.py`, `tools/{files,search,chatgpt,context,notes,talk}.py`, `provider_map.py`, `vulture_whitelist.py`, `server/reg_*.py`, `.github/workflows/ci.yml`, `tests/integration/test_ctx_bundle.py`, `tests/unit/test_exclusion.py`, `tests/unit/test_dav_home_entries.py`
- `.planning/phases/25-mess-spike-tag-abfrage/25-MESSBERICHT.md` (Latenzen, Notes-Beleg, prepare_context-Referenz), `raw/nc35-prepare-context-baseline.txt`
- `.planning/phases/26-guard-kern/26-REVIEW.md`, `deferred-items.md`
- Findling-Quelltext `C:/Users/Student/nextcloud-search/php/lib/Search/Provider.php`
- Live-Abfrage `occ app:list` auf nc35-nc und nc-mcp-exapp-nc (27.09.)

### Secondary (MEDIUM confidence)
- https://docs.nextcloud.com/server/latest/developer_manual/client_apis/WebDAV/search.html (d:or, d:eq, oc:fileid suchbar)
- https://github.com/nextcloud/server apps/systemtags/lib/Search/TagSearchProvider.php
- https://github.com/nextcloud/server apps/comments/lib/Search/CommentsSearchProvider.php
- https://github.com/nextcloud/spreed lib/Chat/Parser/SystemMessage.php (getFileFromShare), lib/Search/MessageSearch.php, lib/Room.php (OBJECT_TYPE_FILE)

### Tertiary (LOW confidence)
- Verhalten des talk-message-Providers bei Datei-Freigaben, Name/objectId von Datei-Konversationen (A3, A4), Kosten des Batch-SEARCH (A1)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH, keine neuen Pakete
- Architecture: HIGH für Einhängepunkte und Reihenfolgen (Code gelesen), MEDIUM für fileid-Batch-Auflösung (dokumentiert, Kosten ungemessen)
- Pitfalls: HIGH für Test-Infrastruktur, Importzyklus, Fixture-Lebensdauer, files_search-Truncation, IN-02-Fix; LOW für die zwei Talk-Nebenkanäle

**Research date:** 2026-09-27
**Valid until:** 2026-10-27 (Code-Stand), Nextcloud-/Talk-Quellbefunde bis zum nächsten Hauptrelease
