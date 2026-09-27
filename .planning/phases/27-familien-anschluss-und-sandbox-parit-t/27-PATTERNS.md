# Phase 27: Familien-Anschluss und Sandbox-Parität - Pattern Map

**Mapped:** 2026-09-27
**Files analyzed:** 17 (12 Quelltext, 5 Test)
**Analogs found:** 16 / 17 (einzig `tests/unit/guard_routes.py` hat kein Modul-Vorbild, nur Helfer in `test_exclusion.py`)

Alle Zeilennummern gegen den Stand 27.09. gelesen. Code-Exzerpte unverändert Englisch (Projektregel).

## File Classification

| Neue/geänderte Datei | Rolle | Datenfluss | Nächstes Vorbild | Qualität |
|----------------------|-------|------------|------------------|----------|
| `src/mcp_connector/nextcloud/__init__.py` | model (Parameterobjekt) | , | eigene Datei + `exclusion.ExclusionGuard.__init__` | exact |
| `src/mcp_connector/nextcloud/exclusion.py` | service (Guard) | request-response | eigene Datei (Import auf TYPE_CHECKING, `has_folders`) | exact |
| `src/mcp_connector/nextcloud/clients/dav.py` | client | request-response / transform | `build_fileid_body` + `find_by_fileid` (Z. 316-391), `_check*` (Z. 672-833) | exact |
| `src/mcp_connector/nextcloud/clients/systemtags.py` | client | request-response | unverändert; `TaggedNode.is_collection` wird gelesen | exact |
| `src/mcp_connector/nextcloud/clients/notes.py` | client | request-response | `get_note` (Z. 70-78), `ocs._status_error` 404 | role-match |
| `src/mcp_connector/tools/withhold.py` (NEU, Name frei) | utility | transform | `tools/search.py` `_reason`/degraded-Idiom, `errors.py` Fabriken | role-match |
| `src/mcp_connector/tools/files.py` | tool (controller) | request-response + file-I/O | eigene Datei `read`/`list_dir`/`search`/`upload*` | exact |
| `src/mcp_connector/tools/search.py` | tool | fan-out / request-response | eigene Datei `unified_search`, `_normalise`, `_entry_in_files_root` | exact |
| `src/mcp_connector/tools/chatgpt.py` | tool | request-response | `_fetch_file` (Z. 231-276), `_fetch_message` (Z. 594-676) | exact |
| `src/mcp_connector/tools/context.py` | tool (Aggregator) | fan-out | `prepare_context` gather (Z. 248-254), `_hits`/`_degraded_of` | exact |
| `src/mcp_connector/tools/notes.py` | tool | request-response | `search` skipped-Idiom (Z. 73-97), `read` (Z. 100-115) | exact |
| `src/mcp_connector/tools/talk.py` | tool | request-response / transform | `_resolve` (Z. 574-604), `one_room` (Z. 630-657), `_conversations` (Z. 359-392) | exact |
| `src/mcp_connector/provider_map.py` | utility | transform | `_file_id` (Z. 197-208) wird öffentlich | exact |
| `vulture_whitelist.py` | config | , | Abschnitte Z. 288-302 ("Empty on purpose") | exact |
| `tests/unit/guard_routes.py` (NEU) | test-helper | , | Helfer `tag_list`/`report_207`/`listed` in `tests/unit/test_exclusion.py` Z. 214-306 | partial |
| `tests/unit/test_dav_home_entries.py` | test | , | `test_unsafe_segments_become_none` Z. 88-101 | exact |
| `tests/unit/test_{files_read,files_list,files_search,files_upload,unified_search,chatgpt_fetch,tools_context,notes_tools,talk_tools}.py` | test | , | je Datei `clients`-Fixture + `respx.mock` | exact |

## Pattern Assignments

### `src/mcp_connector/nextcloud/__init__.py` (model)

**Vorbild:** Datei selbst (Z. 7-21), heute:
```python
from dataclasses import dataclass

import httpx

from .credentials import Credentials

__all__ = ["Credentials", "NcClients"]


@dataclass(frozen=True, slots=True)
class NcClients:
    """The HTTP client of the current event loop plus the credentials of this call."""

    client: httpx.AsyncClient
    creds: Credentials
```
**Änderung:** `field(default_factory=ExclusionGuard, compare=False, repr=False)` (RESEARCH Pattern 1). `ExclusionGuard()` nimmt keine Argumente (exclusion.py Z. 324-328, Docstring Z. 309-310 kündigt genau das an). Einzige Konstruktionsstelle in `src/`: `deps.resolve_clients` (deps.py Z. 116-118), bleibt unverändert, weil der Default greift:
```python
def resolve_clients(ctx: Any) -> NcClients:
    """Bundle the event loop client with the credentials of this call."""
    return NcClients(client=shared_client(), creds=resolve_credentials(ctx))
```

---

### `src/mcp_connector/nextcloud/exclusion.py` (service)

**Importzyklus** (Z. 47-57): heute Laufzeitimport `from . import NcClients` (Z. 56). `NcClients` wird nur in Annotationen genutzt (`load_scope` Z. 200, `_fresh_ids` Z. 225, `_flight` Z. 237, `_report_all` Z. 270, `scope` Z. 330) , also unter `TYPE_CHECKING` verschieben.

**TagScope-Erweiterung `has_folders`** (Vorlage `TagScope` Z. 156-163 und `_active` Z. 288-302):
```python
    for tagged in sets:
        for node in tagged.nodes:
            if node.path is None:
                return _unverifiable("foreign_href")
            paths.add(node.path)
            fileids.add(node.fileid)
    return TagScope("active", paths=frozenset(paths), fileids=frozenset(fileids))
```
Hier `node.is_collection` in ein neues Feld `has_folders: bool = False` sammeln. Damit wird `_.is_collection` aus vulture_whitelist.py Z. 327 gelesen (Merker (e) entschieden: lesen).

**Aufrufvertrag für alle Familien** (Z. 165-189): `excludes(path, fileid)` wirft `ValueError` bei `unverifiable`, bei `active` ohne Argumente und bei relativem Pfad. Also immer zuerst `scope.state == "unverifiable"` prüfen, Pfade immer absolut (Home-Form, nicht virtuell).

---

### `src/mcp_connector/nextcloud/clients/dav.py` (client)

**1. Fehlerfabriken `not_found` / `parent_missing`** , Quelle der Byte-Gleichheit. Heutige Texte:

`_check` 404-Zweig (Z. 809-814):
```python
    if status == 404:
        raise ToolError(
            message=f"File not found: {path}.",
            hint="List the parent folder first to get the exact spelling of the path.",
            reason=REASON_UNKNOWN_ID,
        )
```
`_check_chunk_response` (Z. 688-694) und `_check_write` (Z. 751-757), wortgleich:
```python
    if status in (404, 409):
        parent = dirname(path) or "/"
        raise ToolError(
            message=f"The parent folder {parent} of {path} does not exist.",
            hint="Create the folder in Nextcloud first, or upload into a folder that exists.",
            reason=REASON_UNKNOWN_ID,
        )
```
Alle drei Stellen auf `raise not_found(path)` / `raise parent_missing(path)` umstellen; Guard-Pfade rufen dieselben Fabriken. Imports vorhanden (Z. 18 `dirname`, Z. 26-31 `REASON_UNKNOWN_ID`, `ToolError`).

**2. `paths_of_fileids` (Batch-SEARCH mit `d:or`)** , Vorlage `build_fileid_body` (Z. 316-365) + `find_by_fileid` (Z. 368-391):
```python
    where = etree.SubElement(basic, f"{{{xml.DAV}}}where")
    equals = etree.SubElement(where, f"{{{xml.DAV}}}eq")
    eq_prop = etree.SubElement(equals, f"{{{xml.DAV}}}prop")
    etree.SubElement(eq_prop, f"{{{xml.OC}}}fileid")
    literal = etree.SubElement(equals, f"{{{xml.DAV}}}literal")
    literal.text = number
    ...
    nresults.text = "1"
```
```python
    response = await client.request(
        "SEARCH",
        f"{creds.base_url}{DAV_ROOT_PATH}",
        headers={"Content-Type": "text/xml"},
        content=build_fileid_body(search_scope(creds), fileid),
        auth=creds.auth(),
    )
    _check(response, f"the file with id {fileid}")
    entries = parse_entries(response.content, creds)
    return entries[0] if entries else None
```
Neu: zwischen `where` und den `eq` ein `d:or` einhängen, je Id ein `d:eq`; `nresults` = Anzahl; jede Id vorher gegen `_DIGITS` (Z. 42) prüfen; Blöcke zu höchstens 50 (Kommentar Z. 266-268: Nextcloud lehnt > 100 Operatoren ab), Blöcke per `asyncio.gather`. `parse_entries` filtert bereits auf `in_files_root` (Z. 477), also liefert das Ergebnis Sandbox und Pfad zugleich. Rückgabe `dict[fileid, path]` aus `entry["fileid"]`/`entry["path"]` (`_entry` Z. 539-552).

**3. IN-02 / IN-03 / IN-01** , betroffen:
- `_home_path_of` (Z. 527-536): heute `raw = unquote(urlsplit(href).path)` über den Gesamtpfad. Fix: segmentweise `unquote`, `None` wenn ein decodiertes Segment `/` oder `\x00` enthält.
- `_plain_path` (Z. 520-524): zusätzlich `"//" in path` ablehnen.
- Home-Präfix doppelt in `parse_entries` Z. 473 und `home_entries` Z. 496:
```python
    home = f"{urlsplit(creds.base_url).path.rstrip('/')}{DAV_FILES_PREFIX}{creds.user}"
```
→ eine `_home_prefix(creds)`.

**Pfadform:** `safe_path` (Z. 85-122) liefert Home-Pfade (Root vorangestellt); `stat` gibt `"fileid"` und `"path"` (Z. 163-172). Genau diese Form verlangt `TagScope.excludes`.

---

### `src/mcp_connector/tools/withhold.py` (NEU, utility)

**Vorbild Import-Stil** (tools/search.py Z. 30-39):
```python
import asyncio
from collections.abc import Sequence
from typing import Any

import httpx

from .. import config, provider_map
from ..errors import ToolError
from ..nextcloud import NcClients
from ..nextcloud.clients import dav, ocs
```
**Vorbild Fabrik/Reason** (errors.py Z. 39, Z. 100-108): `REASON_GUARD_TRIPPED` existiert; REASONS ist eingefroren (Z. 55-57, Gate `tests/unit/test_errors_reason.py`), also keinen neuen Reason erfinden.
```python
REASON_GUARD_TRIPPED = "guard_tripped"  # a guard of this server stopped the call
...
class ToolError(Exception):
    def __init__(self, message: str, hint: str, *, reason: str = REASON_UNSPECIFIED) -> None:
```
**Inhalt** wie RESEARCH Code Examples Z. 408-427: `EXCLUSION_UNAVAILABLE`, `unavailable_error()` (ohne Id/Pfad im Text, Pitfall 9), `degraded_entry(key, name)`, `file_refs(provider_id, entry)`. Öffentliche Namen Pflicht (Modulgrenzen-Gate `tests/contract/test_module_boundaries.py`).

---

### `src/mcp_connector/tools/files.py` (tool, request-response + file-I/O)

**Einzelzugriff read/download** , Einhängepunkt direkt nach `stat`, vor jeder Formprüfung. Heute `read` (Z. 243-257):
```python
    target = dav.safe_path(path)
    info = await dav.stat(clients.client, clients.creds, target)

    if info["is_collection"]:
        raise ToolError(
            message=f"{target} is a folder, not a file.",
            hint="Use files_list to see what is inside a folder.",
        )

    content_type = info["content_type"] or "application/octet-stream"
    if not _is_text(content_type):
```
`download` identisch (Z. 323-330). Zwischen Z. 244 und 246 bzw. 324 und 326: `asyncio.gather(clients.exclusion.scope(clients), dav.stat(...), return_exceptions=True)`, dann Reihenfolge unverifiable → Fehler von stat → `excludes(path=target, fileid=info["fileid"] or None)` → `raise dav.not_found(target)` (RESEARCH Pattern 2 Z. 185-201). Die Eingabeprüfungen `offset`/`max_bytes` (Z. 232-241, 312-321) bleiben davor, sie hängen nicht von der Id ab.

**Liste list_dir** (Z. 179-197):
```python
    itself, children = await dav.propfind_children(clients.client, clients.creds, target)
    if not itself["is_collection"]:
        raise ToolError(...)

    children.sort(key=lambda entry: (not entry["is_collection"], entry["name"].casefold()))
    window = children[offset : offset + capped]
    ...
    if len(children) > offset + capped:
        result["truncated"] = True
```
Ziel selbst prüfen (vor `is_collection`-Prüfung, sonst Formorakel), Kinder vor `sort`/Fenster filtern, `truncated` aus gefilterter Länge.

**Liste search** (Z. 133-155): `fetch = min(offset + capped + 1, MAX_SEARCH_FETCH)`; `truncated` aus `len(hits)`. Pitfall 3: nach dem Filtern nachladen bis Fenster + Wächter voll oder Rohliste kürzer oder `MAX_SEARCH_FETCH`.

**Upload** (Z. 390-411 `upload`, Z. 435-571 `upload_binary`): Prüfpunkt nach allen reinen Eingabeprüfungen, vor jedem `dav.put_new_file` (Z. 411, 527), `dav.start_chunked_upload` (Z. 538), `dav.put_upload_chunk` (Z. 539), `dav.finish_chunked_upload` (Z. 561); bei jedem Chunk-Aufruf. `unverifiable` → `withhold.unavailable_error()`, ausgeschlossen → `raise dav.parent_missing(target)` (D-27-01, auch Grenzfall direkt getaggte Datei).

**Projektion** `_as_item` (Z. 200-218) bleibt; sie setzt `id` aus `fileid`.

---

### `src/mcp_connector/tools/search.py` (tool, fan-out)

**Guard als eigenes gather-Mitglied** , heute (Z. 104-107):
```python
    outcomes = await asyncio.gather(
        *(_ask(clients, provider_id, term, capped) for provider_id in selected),
        return_exceptions=True,
    )
```
Guard nicht in `_ask` (Z. 196-198, 15-s-Timeout) legen, sondern daneben (Pattern 6).

**degraded-/skipped-Idiom** (Z. 101, 109-137), D-27-03/04-Anker:
```python
    degraded: list[dict[str, str]] = []
    ...
        if isinstance(outcome, BaseException):
            degraded.append({"provider": provider_id, "reason": _reason(outcome)})
            continue
        hits, unusable = _normalise(clients, provider_id, outcome)
        results.extend(hits)
        skipped += unusable
    ...
    if degraded:
        result["degraded"] = degraded
    ...
    if skipped:
        result["skipped"] = skipped
```
Bei unverifiable: EIN `{"provider": "exclusion", "reason": EXCLUSION_UNAVAILABLE}` (Schlüsselname `provider` wie hier). Tag-Drops erhöhen `skipped` nie.

**Sandbox-Lücke SBX-01** (Z. 240-255), wird ersetzt:
```python
def _entry_in_files_root(provider_id: str, entry: dict[str, Any]) -> bool:
    root = config.files_root()
    if root == "/":
        return True
    attributes = entry.get("attributes")
    if not isinstance(attributes, dict):
        return provider_id != "files"
    raw_path = attributes.get("path")
    if raw_path is None:
        return provider_id != "files"
    if not isinstance(raw_path, str):
        return False
    return dav.in_files_root("/" + raw_path.lstrip("/"))
```
Die beiden `return provider_id != "files"` sind das Leck (Findling, notes, comments). Neu: `withhold.file_refs` → pfadlose über `dav.paths_of_fileids` (nur wenn Root ≠ `/` oder `scope.has_folders`), nicht aufgelöst = `skipped += 1`.

**Schleife `_normalise`** (Z. 210-237) ist der Ort, an dem je Eintrag Sandbox (zählend) und dann Tag (lautlos) entschieden wird; `_normalise` ist synchron, daher Auflösung vorher im `unified_search`-Rumpf sammeln.

---

### `src/mcp_connector/tools/chatgpt.py` (tool, request-response)

**`_fetch_file`** (Z. 240-252), heute:
```python
    entry = await dav_client.find_by_fileid(clients.client, clients.creds, fileid)
    if entry is None:
        raise ToolError(
            message=f"This account has no file with the id {fileid}.",
            hint=(
                "Run search again and use the id from the fresh answer: a file id stops "
                "resolving once the file is deleted or the share is gone."
            ),
        )

    path = str(entry["path"])
    limit = MAX_TEXT_BYTES if max_bytes is None else max_bytes
    answer = await files_tools.read(clients, path=path, max_bytes=limit)
```
Den ToolError in eine Fabrik ziehen (heute ohne `reason`; Fabrik muss exakt dieses Objekt bauen). Guard und `find_by_fileid` parallel; unverifiable → `unavailable_error()`; `fileid in scope` → derselbe Satz vor jeder Pfadauswertung; dann `excludes(path=entry["path"])`. `files_tools.read` teilt denselben Guard (Fast Path exclusion.py Z. 340-343).

**`_fetch_note`** (Z. 279-297): erbt von `notes_tools.read`.

**`_fetch_message`** (Z. 622-628): `one_room` (Datei-Konversationen) + `one_message` → `_message` → `_resolve`; erbt die Talk-Änderungen.

**Titel** (Z. 272): `marks.without_marks(path.rsplit("/", 1)[-1] or path)` , Dateiname im Titel; nur nach bestandener Prüfung erreichbar.

---

### `src/mcp_connector/tools/context.py` (tool, fan-out)

**gather mit Guard als erstem Mitglied** , heute (Z. 248-254):
```python
    search_out, calendar_out, talk_out, mail_out = await asyncio.gather(
        search_tools.unified_search(clients, query=term, limit=SEARCH_LIMIT),
        _events(clients, start, end),
        _talk(clients),
        _mail(clients),
        return_exceptions=True,
    )
```
`clients.exclusion.scope(clients)` als eigenes Mitglied, außerhalb von `_talk` (TALK_BUDGET 5 s, Z. 310-315) und `_events` (Pattern 6, Merker (c)).

**degraded-Weitergabe** (Z. 516-518, 800-805) übernimmt Einträge der Unterwerkzeuge unverändert:
```python
    degraded.extend(_degraded_of(outcome))
```
Schlüssel hier `source`, in search.py `provider`. D-27-03 verlangt EINEN Eintrag: nach dem Einsammeln Einträge mit `reason == EXCLUSION_UNAVAILABLE` auf einen `{"source": ..., "reason": ...}` deduplizieren.

**Kappungssätze** `_bundle` (Z. 523-546, "Only the first {MAX_PER_BUCKET} of {found} hits") rechnen auf bereits gefilterten Treffern , keine Änderung nötig, solange unified_search vorher filtert.

**Ausschnitte** `_excerpt` (Z. 768-776) über `chatgpt_tools.fetch(clients, ...)` mit demselben `clients` → kein zweiter REPORT.

---

### `src/mcp_connector/tools/notes.py` (tool)

**Liste `search`** (Z. 73-97) mit bestehendem skipped-Idiom:
```python
    results: list[dict[str, str]] = []
    skipped = 0
    for entry in entries:
        if not isinstance(entry, dict):
            skipped += 1
            continue
        note_id = _note_id_from_resource_url(entry.get("resourceUrl"))
        if note_id is None:
            skipped += 1
            continue
        results.append({...})

    result: dict[str, Any] = {"count": len(results), "results": results}
    if skipped:
        result["skipped"] = skipped
```
Neu: Ids sammeln, Guard + `dav.paths_of_fileids` (Notiz-Id = fileid), Sandbox-Drops in `skipped`, Tag-Drops lautlos; unverifiable → `results` leer + `degraded` (neu in dieser Datei, Form `{"source"|"provider": ..., "reason": EXCLUSION_UNAVAILABLE}`).

**Einzel `read`** (Z. 100-115): nach `_ready` und `_plain_note_id` (Z. 102-103), vor `notes_client.get_note` (Z. 105). Nicht auflösbar / ausgeschlossen / Notes-404 → EIN Satz. Heutiger 404-Text aus `ocs._status_error` (ocs.py Z. 295-300) trägt Fremdtext:
```python
    if status in (404, 998):
        return ToolError(
            message=f"Nextcloud did not find {what}.{suffix}",
            hint="Search for it first; the id or the name is unknown to this instance.",
            reason=REASON_UNKNOWN_ID,
        )
```
`suffix` = `" Nextcloud says: {detail}"` → Orakel. Den 404 in `tools/notes.read` abfangen und auf die gemeinsame Note-not-found-Fabrik abbilden.

**`create`** (Z. 118-161, `renamed` Z. 159-160): Open Question 1, Planentscheid.

---

### `src/mcp_connector/tools/talk.py` (tool, transform)

**`_resolve`** (Z. 593-604), der D-27-06-Anker:
```python
    params = parameters if isinstance(parameters, dict) else {}

    def replace(match: re.Match[str]) -> str:
        entry = params.get(match.group(1))
        if not isinstance(entry, dict):
            return match.group(0)
        name = str(entry.get("name") or "").strip()
        if not name:
            return match.group(0)
        return f"@{name}" if _is_mention(match.group(1), entry) else name

    return marks.without_marks(_PLACEHOLDER.sub(replace, str(message or "")))
```
Einfügen vor `name = ...`: `type == "file"` und (unverifiable oder `excludes(path="/" + path, fileid=id)`) → `return match.group(0)`. `_resolve` bekommt ein Prädikat oder den Scope als Parameter.

**Drei Aufrufer** (alle umzustellen): `_preview` Z. 451, `_message` Z. 526 (über `one_message` Z. 570 auch `chatgpt._fetch_message`). Guard nur anfragen, wenn im Fenster ein `type == "file"`-Parameter vorkommt (Pitfall 8).

**Datei-Konversationen** (Open Question 2): Filter in `one_room` (Z. 648-657) und `_conversations` (Z. 375-381). Refusal byte-gleich zum unbekannten Token:
```python
    raise ToolError(
        message=f"The token {token!r} is not in the conversation list of this account.",
        hint=_CONVERSATION_HINT,
    )
```
Filterstelle in `_conversations`:
```python
    entries = [
        _conversation(clients.creds, room)
        for room in ordered
        if not room.get("isArchived") and str(room.get("token") or "").strip()
    ]
```

---

### `src/mcp_connector/provider_map.py` (utility)

`_file_id` (Z. 197-208) ist die Regel "`attributes.fileId`, sonst `/f/<id>` der URL" , für `withhold.file_refs` öffentlich machen (Modulgrenzen-Gate):
```python
def _file_id(attributes: Mapping[str, Any], url: str) -> str:
    """``attributes.fileId`` first, then the ``/f/<fileid>`` segment of the URL."""
    raw = attributes.get("fileId")
    candidate = str(raw).strip() if raw is not None else ""
    if _DIGITS.fullmatch(candidate):
        return candidate

    segments = [segment for segment in urlsplit(url).path.split("/") if segment]
    for index, segment in enumerate(segments[:-1]):
        if segment == "f" and _DIGITS.fullmatch(segments[index + 1]):
            return segments[index + 1]
    return ""
```
Notiz-Id: `_last_numeric_segment` (Z. 256-262). URL vorher über `absolute_url` (Z. 112-124).

---

### `vulture_whitelist.py` (config)

Abschnitte Z. 315-327 (`_.is_collection`) und Z. 329-340 (`_.excludes`) räumen, im Stil der geleerten Abschnitte (Z. 288-293):
```python
# --- The refusal writer of plan 24-03, wired in by plan 24-04 ----------------------------
# Empty on purpose, and that is the rule of this file at work rather than an omission. ...
```
Neue öffentliche Helfer, die erst einen Plan später einen Aufrufer bekommen (z.B. `paths_of_fileids`, `withhold.*`), bekommen je einen Eintrag mit Testverweis und verlassen die Liste mit dem aufrufenden Plan.

---

### `tests/unit/guard_routes.py` (NEU, test-helper)

**Vorbild:** Helfer in `tests/unit/test_exclusion.py` Z. 20-29, 231-274:
```python
BASE = "http://nc.test"
TAGS = f"{BASE}/remote.php/dav/systemtags/"
HOME = f"{BASE}/remote.php/dav/files/alice/"
XML_HEADERS = {"Content-Type": "application/xml; charset=utf-8"}
```
```python
def tag_list(*tags: tuple[str, str]) -> bytes:
    """A 207 tag listing: the collection itself (no id) plus one entry per (id, name)."""
    entries = [_response("/remote.php/dav/systemtags/", "<oc:display-name></oc:display-name>")]
    ...

def report_207(*nodes: tuple[str, str, bool], user: str = "alice") -> bytes:
    """A 207 REPORT answer; each node is (href suffix below the home, fileid, is_collection)."""

def listed(body: bytes) -> httpx.Response:
    return httpx.Response(207, content=body, headers=XML_HEADERS)
```
Route-Muster (Z. 316-320, 341-349):
```python
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as mock:
        listing = mock.route(method="PROPFIND", url=TAGS).mock(
            return_value=listed(tag_list(("70", "projekt"), ("71", "kein-ki-alt")))
        )
        report = mock.route(method="REPORT", url=HOME)
```
Zu bauen: `untagged(mock)`, `active(mock, nodes)`, `unverifiable(mock)` (z.B. REPORT 500). Cache-Reset per `exclusion.clear_cache()` wie autouse-Fixture `_fresh_cache` (Z. 34-35). Kein `conftest.py` in `tests/unit/` vorhanden; `tests/conftest.py` importiert absichtlich nichts aus `mcp_connector` (Docstring Z. 1-6), also Helfer als importierbares Modul, nicht dort.

---

### `tests/unit/test_dav_home_entries.py`

Parametrisierung erweitern (Z. 88-101):
```python
@pytest.mark.parametrize(
    "href",
    [
        "/remote.php/dav/files/alice/A/../B",
        "/remote.php/dav/files/alice/A%5CB",
        "/remote.php/dav/files/alice/A%01B",
        "/remote.php/dav/files/alice/A%7FB",
        "/remote.php/dav/files/alice/./A",
    ],
)
def test_unsafe_segments_become_none(creds: Credentials, href: str) -> None:
    entries = dav.home_entries(multistatus(href), creds)

    assert [path for path, _props in entries] == [None]
```
Neu: `A%2Fkein`, `A//B`.

---

### Familien-Tests (`test_files_read.py`, `test_unified_search.py`, `test_talk_tools.py`, ...)

**Fixture-Muster** (test_files_read.py Z. 68-73, identisch in test_unified_search.py Z. 80-85):
```python
@pytest.fixture
def clients() -> NcClients:
    return NcClients(
        client=httpx.AsyncClient(follow_redirects=False),
        creds=Credentials(BASE, USER, SECRET),
    )
```
Frisches NcClients je Test ⇒ frischer Guard (Pattern 7). Tests mit `respx.mock(assert_all_called=True)` (z.B. test_files_read.py Z. 79) brauchen die untagged-Route (Pitfall 1).

**Sandbox-Testvorlage** (test_unified_search.py Z. 169-194) für SBX-01 mit fileId-only-Einträgen:
```python
    monkeypatch.setenv(config.ENV_FILES_ROOT, "/rtc/mth/knsk")
    inside = {
        "title": "inside.pdf",
        "resourceUrl": f"{BASE}/index.php/f/5001",
        "attributes": {"fileId": "5001", "path": "rtc/mth/knsk/inside.pdf"},
    }
    ...
    assert [hit["id"] for hit in result["results"]] == ["file:5001"]
    assert result["skipped"] == 1
```
**Talk-Parameter-Test** (test_talk_tools.py Z. 696): `message(id=42, message="Der Vorgang {ticket} ist offen", messageParameters=parameters)` , als Vorlage für `{file}` mit `type: "file"`, `id`, `name`, `path`.

**REPORT-Zählung:** `report.call_count == 1` je Tool-Aufruf (Stil test_exclusion.py Z. 359-360).

## Shared Patterns

### Entscheidungsreihenfolge (alle Einzelzugriffe)
**Quelle:** RESEARCH Pattern 2; Guard-Verhalten exclusion.py Z. 165-189
**Gilt für:** files.read, files.download, chatgpt._fetch_file, notes.read
1. reine Eingabeprüfung (darf werfen) → 2. `gather(scope, primär, return_exceptions=True)` → 3. unverifiable → `unavailable_error()` → 4. Primärfehler wie bisher → 5. `excludes` → Not-found-Fabrik → 6. Formprüfungen.

### Listenfilter vor Schnitt
**Gilt für:** files.list_dir, files.search, unified_search, notes.search, talk._conversations
Filtern vor `sort`/Fenster/Buckets; `truncated`, `total`, `count`, Bucket-Sätze aus gefilterter Liste; Tag-Drops nie zählen; Sandbox-Drops zählen weiter (`skipped`).

### Degraded-Idiom
**Quelle:** search.py Z. 101/114/129-130 (`provider`-Schlüssel), context.py Z. 513/518/800-805 (`source`-Schlüssel)
**Gilt für:** alle Listen-Familien bei unverifiable, genau ein Eintrag mit `reason = EXCLUSION_UNAVAILABLE`.

### Fehlerfabriken statt f-String-Kopien
**Quelle:** dav.py Z. 688-694, 751-757, 809-814; chatgpt.py Z. 242-248
**Gilt für:** jeder Ausschlusspfad, der "existiert nicht" antworten muss.

### lxml-Bodies
**Quelle:** dav.py `build_fileid_body` Z. 334-365, systemtags.py `filter_files_body` Z. 89-102
**Gilt für:** `paths_of_fileids`. Nie f-Strings (T-01-11/T-01-30).

### Contract-Gates
- Keine neue modulweite veränderliche Struktur (tests/contract/test_no_destructive_calls.py Z. 280-290, erlaubt nur `_clients`, `_cache`, `_tag_ids`) , kein fileid-Pfad-Cache.
- Keine `_privat`-Zugriffe über Tool-Modulgrenzen (`tests/contract/test_module_boundaries.py`) , `one_room`/`one_message` sind das Vorbild für öffentliche Helfer (talk.py Docstring Z. 633-637).
- `reason=` nur aus `errors.REASONS` (`tests/unit/test_errors_reason.py`).

## No Analog Found

| Datei | Rolle | Datenfluss | Grund |
|-------|-------|------------|-------|
| `tests/unit/guard_routes.py` | test-helper | , | Kein geteiltes Test-Helfermodul in `tests/unit/`; Helfer existieren nur lokal in `test_exclusion.py` (Vorlage oben) |

Teilweise ohne Vorbild: `d:or` im SEARCH-Body (im Repo nirgends gebaut, nur `d:eq`/`d:like`); Struktur laut RESEARCH Pattern 4 und Nextcloud-Doku.

## Metadata

**Analog search scope:** `src/mcp_connector/{nextcloud,tools}/`, `src/mcp_connector/{provider_map,errors,deps}.py`, `vulture_whitelist.py`, `tests/unit/`, `tests/contract/`, `tests/conftest.py`
**Files scanned:** 22
**Pattern extraction date:** 2026-09-27
