# Phase 26: Guard-Kern - Pattern Map

**Mapped:** 2026-09-27
**Files analyzed:** 7 (3 neu, 4 geändert)
**Analogs found:** 7 / 7

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/mcp_connector/nextcloud/clients/systemtags.py` (NEU) | client (roh, policy-frei) | request-response (PROPFIND + REPORT, DAV-XML) | `src/mcp_connector/nextcloud/clients/dav.py` (`propfind_children`, `find_by_fileid`, Body-Builder) + `scripts/tag_spike.py:556-581, 1209-1225` | exact |
| `src/mcp_connector/nextcloud/exclusion.py` (NEU) | service/policy (Zustandsautomat + Single-Flight + Modul-Cache) | request-response, request-gebunden gecacht | `src/mcp_connector/oauth/jwks.py` (Lock/Single-Flight) + `src/mcp_connector/nextcloud/capabilities.py` (Modul-Cache `(base_url, user)`, TTL, `clear_cache`) | exact (zwei Analogs kombiniert) |
| `src/mcp_connector/nextcloud/clients/dav.py` (GEÄNDERT, additiv) | utility (Segmentregel, href-Normalisierung) | transform | eigene Funktionen `in_files_root` (Z. 483-490), `safe_path` (Z. 120), `parse_entries` (Z. 466-480), `_home_path_of` (Z. 493-502) | exact (Refactor am Ort) |
| `tests/unit/test_systemtags_client.py` (NEU) | test | request-response (respx) | `tests/unit/test_caldav_client.py` (PROPFIND-Methodenroute, Body-Prüfung) | exact |
| `tests/unit/test_exclusion.py` (NEU) | test | async, call_count, parallele gather | `tests/unit/test_oauth_jwks.py:256-274` (20 parallele = 1 Fetch) + `tests/unit/test_deck_tools.py:58-68` (Cache-Reset-Fixture, `NcClients`-Fixture) | exact |
| `tests/contract/test_no_destructive_calls.py` (GEÄNDERT) | test/gate | config | eigene Stellen Z. 280-288 und Z. 671-676 | exact |
| `vulture_whitelist.py` (GEÄNDERT) | config/gate | config | eigene Abschnitte Z. 162-194 (parkierte Namen mit Begründung) | exact |

## Pattern Assignments

### `src/mcp_connector/nextcloud/clients/systemtags.py` (client, request-response)

**Analog:** `src/mcp_connector/nextcloud/clients/dav.py` plus Body-Vorlagen aus `scripts/tag_spike.py` (nur Muster übernehmen, nicht aus `scripts/` importieren).

**Imports pattern** (`dav.py` Z. 15-33, auf den Bedarf reduziert):
```python
import re
from collections.abc import Sequence
from urllib.parse import quote

import httpx
from lxml import etree

from ..credentials import Credentials
from . import xml
```
Hinweis: `dav.py` importiert `from ...errors import ...`; der neue Client wirft laut RESEARCH Pattern 5 keine ToolErrors selbst, sondern liefert Ausgänge als Werte (Status + geparste Einträge). `xml.parse_multistatus` kann `ToolError` werfen, das fängt erst `exclusion.py`.

**ASCII-Ziffern-Regel** (`dav.py` Z. 38-42, wiederverwenden statt neu schreiben):
```python
#: Digits, and only ASCII ones. ``str.isdigit`` also accepts a superscript two and an
#: Arabic-Indic digit, ...
_DIGITS = re.compile(r"[0-9]+")
```
Entweder `dav._DIGITS` importieren oder identisch als eigenes Modul-Konstantes Muster (unveränderliches `re.Pattern`, kein Gate-Problem).

**REPORT-Body, genau EINE Regel** (`scripts/tag_spike.py` Z. 556-572):
```python
def report_body(tag_id: str) -> bytes:
    if not re.fullmatch(r"[0-9]+", tag_id):
        raise ValueError(f"a tag id must be ASCII digits only (got {tag_id!r})")
    root = etree.Element(
        f"{{{xml.OC}}}filter-files", nsmap={"d": xml.DAV, "oc": xml.OC, "nc": xml.NC}
    )
    prop = etree.SubElement(root, f"{{{xml.DAV}}}prop")
    etree.SubElement(prop, f"{{{xml.OC}}}fileid")
    etree.SubElement(prop, f"{{{xml.DAV}}}resourcetype")
    rules = etree.SubElement(root, f"{{{xml.OC}}}filter-rules")
    etree.SubElement(rules, f"{{{xml.OC}}}systemtag").text = tag_id
    return etree.tostring(root, xml_declaration=True, encoding="utf-8")
```
Pflicht: nie mehrere `oc:systemtag` in einen Body (UND-Semantik, Quellbefund A).

**PROPFIND-Body** (`scripts/tag_spike.py` Z. 575-581, identisch zu `dav._stat_body` Z. 131-140):
```python
def propfind_body(props: Sequence[str]) -> bytes:
    root = etree.Element(f"{{{xml.DAV}}}propfind", nsmap={"d": xml.DAV, "oc": xml.OC, "nc": xml.NC})
    prop = etree.SubElement(root, f"{{{xml.DAV}}}prop")
    for name in props:
        etree.SubElement(prop, name)
    return etree.tostring(root, xml_declaration=True, encoding="utf-8")
```

**Request-Form (Methode, Header, auth)** (`dav.py` Z. 446-453, `propfind_children`):
```python
response = await client.request(
    "PROPFIND",
    files_url(creds, target),
    headers={"Depth": "1", "Content-Type": "application/xml"},
    content=_list_body(),
    auth=creds.auth(),
)
```
Für die Tag-Liste: URL `f"{creds.base_url}/remote.php/dav/systemtags/"`, Props `oc:id` + `oc:display-name` (und ggf. `oc:user-visible`/`oc:user-assignable` nur falls gebraucht). Auswertung nach `tag_spike.py` Z. 1219-1225:
```python
if result.status == 207:
    for _href, props in xml.parse_multistatus(result.body):
        tag_id = props.get(f"{{{xml.OC}}}id", "")
        if tag_id:           # Collection selbst hat keine oc:id -> überspringen
            ids.append(tag_id)
```

**REPORT-Ziel = Home-Wurzel, NICHT `files_url`** (`scripts/tag_spike.py` Z. 584-590):
```python
def home_url(creds: Credentials, sub: str = "/") -> str:
    """Deliberately not ``dav.files_url``: that one maps the path into ``NC_MCP_FILES_ROOT``"""
    return f"{creds.base_url}{DAV_FILES}{quote(creds.user, safe='')}{quote(sub, safe='/')}"
```
Im Produktionscode `dav.DAV_FILES_PREFIX` (Z. 35) statt `DAV_FILES` nutzen: `f"{creds.base_url}{dav.DAV_FILES_PREFIX}{quote(creds.user, safe='')}/"`.

**Status-Handling:** NICHT `dav._check` aufrufen (wirft ToolError und würde 412 mit anderen Fehlern vermischen). Rohstatus zurückgeben, damit `exclusion.py` 207 / 412 / Rest unterscheidet. Regel aus `dav.py` Modul-Docstring Z. 9-12 gilt weiter: kein Retry nach 401, Redirects nie folgen (`shared_client` hat `follow_redirects=False`).

**Per-Request-Timeout:** httpx erlaubt `timeout=` am `request`; das Gesamtbudget liegt aber in `exclusion.py` per `asyncio.timeout` (siehe unten).

---

### `src/mcp_connector/nextcloud/exclusion.py` (service/policy, request-gebunden)

**Analog A (Single-Flight):** `src/mcp_connector/oauth/jwks.py`

**Lock im Konstruktor, nicht beim ersten Gebrauch** (Z. 145-147):
```python
# One lock per KeySet, and a KeySet is one issuer: the lock per issuer the
# single-flight requirement asks for. Created here, not on first use.
self._lock = asyncio.Lock()
```

**Schneller Pfad ohne Lock, Re-Check unter dem Lock** (Z. 151-157 und 166-171):
```python
now = self._clock()
if not self._stale(now):
    if kid in self._keys.keys:
        # The fast path takes no lock: a fresh cache with a known kid answers at
        # once. Nothing is awaited between the check and the read, ...
        return self._entry(kid, algorithm)
...
async with self._lock:
    # Re-read the clock and re-check every condition under the lock: whoever
    # waited here takes the outcome of the fetch that just happened instead of
    # starting a second one (single-flight).
```
Übertragen auf den Guard (RESEARCH Pattern 1): `__init__()` parameterlos (damit Phase 27 `field(default_factory=ExclusionGuard)` an `NcClients` hängen kann), `async def scope(self, clients) -> TagScope`, `if self._scope is not None: return self._scope` vor dem Lock, erneut unter dem Lock.

**Fehlschlag wird geteilt, nicht erneut bezahlt** (Z. 173-176):
```python
if self._fetches != fetches_seen:
    # A concurrent caller fetched while this one waited and the cache is
    # still stale, so that fetch failed; share the refusal, not the cost.
    raise self._refuse("the key set could not be refreshed")
```
Im Guard einfacher: auch `UNVERIFIABLE` wird in `self._scope` gespeichert, dadurch teilen alle Wartenden automatisch denselben Zustand. Ausnahme: `asyncio.CancelledError` nie als Zustand speichern (RESEARCH Pitfall 8).

**Exception-Fang an einer Stelle** (Z. 246-252, `_attempt`): Muster "ein Durchgangspunkt für jeden Versuch". Im Guard: `load_scope` fängt `httpx.TimeoutException` (vor `httpx.HTTPError`), `httpx.HTTPError`, `TimeoutError`, `ToolError`, `ValueError`; kein pauschales `except Exception` (anders als jwks Z. 248, dort wird re-raised).

**Leere Antwort ist kein Erfolg** (Z. 279-285):
```python
if not keys:
    # A 200 carrying no usable key is treated as a failed fetch, so the old cache
    # stays: the refusal happens before the assignment below.
    raise self._refuse("the JWKS carries no usable key")
```
Übertragung: 207 mit Einträgen, deren hrefs nicht auf das Home abbildbar sind, ist `UNVERIFIABLE(foreign_href)`, nie "aktiv, leere Menge" (RESEARCH Pitfall 1).

**Analog B (prozessweiter Name-zu-Id-Cache):** `src/mcp_connector/nextcloud/capabilities.py`

**Imports / Modulkopf** (Z. 29-35):
```python
import dataclasses
import time
from typing import Any

from ..errors import AppMissingError, ToolError
from . import NcClients
from .clients import ocs
```
Für `exclusion.py`: `import asyncio`, `import time`, `from dataclasses import dataclass`, `from typing import Literal`, `import httpx`, `from ..errors import ToolError`, `from . import NcClients`, `from .clients import dav, systemtags`.

**TTL-Konstante mit Begründung** (Z. 60-62):
```python
#: Lifetime of a cache entry in seconds. Short enough that installing an app during a
#: session is noticed within a minute, long enough to save the round trip in a tool burst.
TTL_SECONDS = 60.0
```

**Cache-Deklaration, Schlüssel, Lesen/Schreiben** (Z. 150-165):
```python
#: (base_url, user) -> (stored_at, capabilities). No secrets, no session state.
_cache: dict[tuple[str, str], tuple[float, Capabilities]] = {}


async def load(clients: NcClients) -> Capabilities:
    key = (clients.creds.base_url, clients.creds.user)
    now = time.monotonic()
    cached = _cache.get(key)
    if cached is not None and now - cached[0] < TTL_SECONDS:
        return cached[1]
    ...
    _cache[key] = (now, result)
    return result
```
Abweichungen für `_tag_ids` (RESEARCH Pattern 4): Wert `tuple[str, ...]` (eine Id je unterscheidbarer Schreibweise); **nur schreiben, wenn nicht leer** (`if ids:`); bei 412 `_tag_ids.pop(key, None)` vor dem Neulisten. Der Name `_tag_ids` muss exakt so heißen wie im Gate-Eintrag.

**clear_cache** (Z. 198-200):
```python
def clear_cache() -> None:
    """Drop every entry. Safe at any time, by construction (D-20)."""
    _cache.clear()
```
Achtung Vulture (RESEARCH Pitfall 5): `clear_cache` hat über `capabilities` bereits Aufrufer-Namensschatten, gehört also NICHT in die Whitelist.

**Frozen/slots-Dataclass als Wertobjekt** (Z. 110-112):
```python
@dataclasses.dataclass(frozen=True, slots=True)
class Capabilities:
    """The optional-app snapshot of one Nextcloud, as far as this project cares."""
```
Vorlage für `TagScope(state, paths, fileids, reason)`. Unbekannte Eingaben als Programmierfehler melden wie `Capabilities.has` (Z. 144-147, `raise ValueError(...) from None`), z.B. `excludes()` im Zustand `unverifiable` wirft `ValueError` (RESEARCH, Code-Beispiel "Zustände als Werte").

**Analog C (Zeitbudget):** `src/mcp_connector/tools/context.py`

**Budget-Konstante + asyncio.timeout** (Z. 118, Z. 304-307):
```python
CALENDAR_BUDGET = 10.0
...
async def _events(clients: NcClients, start: str, end: str) -> dict[str, Any]:
    """The calendar leg, under the ceiling of this tool instead of the one of that tool."""
    async with asyncio.timeout(CALENDAR_BUDGET):
        return await calendar_tools.list_events(clients, start=start, end=end, limit=MAX_EVENTS)
```
Übertragung: `TAG_BUDGET = 15.0` (Annahme A1), `async with asyncio.timeout(TAG_BUDGET):` um die ganze Flight (PROPFIND + alle REPORTs + ggf. 412-Neuversuch). Mehrere REPORTs je Schreibweise per `asyncio.gather` wie `context.py` Z. 248/752.

**Segmentregel:** über `dav.within(path, root)` (siehe nächster Abschnitt), Vorfahren-Aufzählung gegen die Pfadmenge.

**Verbotene Bezeichner:** kein `Resolve` (Groß-R) in Code und String-Literalen (`test_no_destructive_calls.py` Z. 691-703). Also `lookup_tag_ids`, `tag_ids_for`, nicht `TagResolver`. Konstante `EXCLUDE_TAG = "kein-ki"`, Vergleich `name.strip().casefold() == EXCLUDE_TAG`.

---

### `src/mcp_connector/nextcloud/clients/dav.py` (utility, transform; additive Änderung)

**Bestehende Segmentregel, heute zweimal geschrieben:**

`in_files_root` (Z. 483-490):
```python
def in_files_root(path: str) -> bool:
    """Check a returned absolute path without remapping it into the virtual root."""
    if "\\" in path or any(ord(char) < 32 or ord(char) == 127 for char in path):
        return False
    if any(part in (".", "..") for part in path.split("/")):
        return False
    root = config.files_root()
    return root == "/" or path == root or path.startswith(root + "/")
```
`safe_path` (Z. 118-121):
```python
if requested == root or requested.startswith(root + "/"):
    return requested
```
Änderung: `def within(path: str, root: str) -> bool: return root == "/" or path == root or path.startswith(root + "/")` herauslösen, `in_files_root` (Z. 490) und optional `safe_path` (Z. 120) darauf umstellen. Verhalten unverändert, bestehende Tests (`test_files_list.py`, `test_file_transfer_review.py`, `test_config.py`) decken es.

**Ungefilterte href-Normalisierung** (Vorlage `parse_entries` Z. 466-480):
```python
def parse_entries(body: str | bytes, creds: Credentials) -> list[dict[str, Any]]:
    home = f"{urlsplit(creds.base_url).path.rstrip('/')}{DAV_FILES_PREFIX}{creds.user}"
    entries: list[dict[str, Any]] = []
    for href, props in xml.parse_multistatus(body):
        path = _home_path_of(href, home)
        if path is None or not in_files_root(path):
            continue
        entries.append(_entry(path, props))
    return entries
```
Neue öffentliche Variante `home_entries(body, creds)`: gleiche Schleife **ohne** `in_files_root`-Drop, und ein `None` aus `_home_path_of` darf nicht still verschwinden (Aufrufer muss `foreign_href` erkennen können, z.B. `path: str | None` im Ergebnis oder Exception/Sentinel). `_home_path_of` (Z. 493-502) unverändert wiederverwenden, dort ist die Konto-Präfix-Falle (`alicexyz`) gelöst.

---

### `tests/unit/test_systemtags_client.py` (test, respx)

**Analog:** `tests/unit/test_caldav_client.py`

**Imports + Konstanten** (Z. 16-31):
```python
import httpx
import pytest
import respx
from lxml import etree

from mcp_connector.errors import ConflictError, ToolError
from mcp_connector.nextcloud.clients import caldav
from mcp_connector.nextcloud.clients import xml as davxml
from mcp_connector.nextcloud.credentials import Credentials

BASE = "http://nc.test"
USER = "alice"
SECRET = "app-password-test"
```

**Fixtures** (Z. 46-53):
```python
@pytest.fixture
def creds() -> Credentials:
    return Credentials(BASE, USER, SECRET)


@pytest.fixture
def client() -> httpx.AsyncClient:
    return httpx.AsyncClient(follow_redirects=False)
```

**Methodenroute + Header- und Body-Prüfung** (Z. 162-184):
```python
@pytest.mark.anyio
async def test_discovery_keeps_only_vevent_collections(
    client: httpx.AsyncClient, creds: Credentials
) -> None:
    with respx.mock(assert_all_called=True) as mock:
        route = mock.route(method="PROPFIND", url=CALENDAR_HOME).mock(
            return_value=calendars_response()
        )
        calendars = await caldav.discover_calendars(client, creds)
    ...
    request = route.calls[0].request
    assert request.headers["Depth"] == "1"
    assert request.headers["Content-Type"] == "application/xml"

    body = etree.fromstring(request.content, parser=davxml.hardened_parser())
    asked = {str(element.tag) for element in body.iter() if isinstance(element.tag, str)}
    assert f"{{{davxml.CAL}}}supported-calendar-component-set" in asked
```
Übertragung: `mock.route(method="REPORT", url=f"{BASE}/remote.php/dav/files/alice/")`, im Body genau ein `{OC}systemtag`-Element zählen; Id mit Nicht-ASCII-Ziffer (`"²"`) -> `ValueError`. 207-Antworten als `httpx.Response(207, text=..., headers={"Content-Type": "application/xml; charset=utf-8"})` (Z. 56-61), Multistatus-XML inline oder als Fixture unter `tests/fixtures/`.

---

### `tests/unit/test_exclusion.py` (test, async + call_count)

**Analog A:** `tests/unit/test_oauth_jwks.py` (Single-Flight)

**Imports** (Z. 9-24, reduziert):
```python
import asyncio

import httpx
import pytest
import respx
```

**20 parallele Aufrufe = 1 Fetch, gleiche Instanz** (Z. 256-274):
```python
@respx.mock
@pytest.mark.anyio
async def test_twenty_concurrent_calls_cost_one_fetch_and_share_the_key() -> None:
    async def slow_answer(_request: httpx.Request) -> httpx.Response:
        for _ in range(5):
            await asyncio.sleep(0)
        return httpx.Response(200, json={"keys": [jwk_of(PRIVATE)]})

    route = respx.get(JWKS_URL).mock(side_effect=slow_answer)
    keys = key_set(Clock())

    found = await asyncio.gather(*(keys.key(KID, "RS256") for _ in range(20)))

    assert route.call_count == 1
    assert all(key is found[0] for key in found)
```
Der `slow_answer`-Trick (mehrere `asyncio.sleep(0)`) ist wichtig, damit die Wartenden wirklich am Lock stehen. Für den Timeout-Test statt echter Wartezeit `TAG_BUDGET` per `monkeypatch.setattr(exclusion, "TAG_BUDGET", 0.01)` senken (RESEARCH Pitfall 4, Warnzeichen "Test läuft 30 s").

**Analog B:** `tests/unit/test_deck_tools.py` Z. 58-68 (Cache-Reset und `NcClients`):
```python
@pytest.fixture(autouse=True)
def _empty_cache() -> None:
    capabilities.clear_cache()


@pytest.fixture
def clients() -> NcClients:
    return NcClients(
        client=httpx.AsyncClient(follow_redirects=False),
        creds=Credentials(BASE, USER, SECRET),
    )
```
Übertragung: `exclusion.clear_cache()` autouse. Capabilities-Route mitmocken und `call_count == 0` prüfen (Erfolgskriterium 1, D-25-05).

**Sandbox-Test** (`tests/unit/test_file_transfer_review.py` Z. 62):
```python
monkeypatch.setenv(config.ENV_FILES_ROOT, "/Docs")
```
Übertragung: `NC_MCP_FILES_ROOT=/Shared/KI`, getaggte Menge `{"/Shared"}` -> `/Shared/KI/doc.md` ausgeschlossen (Erfolgskriterium 3).

Testmatrix vollständig in RESEARCH "Testmatrix zu den Erfolgskriterien" (drei Zustände, 412-Dreiklang, Varianten 64/65/67, Segment `/A/kein` vs `/A/keine`).

---

### `tests/contract/test_no_destructive_calls.py` (gate, Änderung)

**Stelle 1** (Z. 280-288), dritten Eintrag mit Begründung ergänzen:
```python
ALLOWED_MODULE_STATE: set[tuple[str, str]] = {
    ("nextcloud/http.py", "_clients"),  # one httpx client per event loop, weakly keyed
    ("nextcloud/capabilities.py", "_cache"),  # capabilities per (base_url, user), 60 s TTL
}
```
-> `("nextcloud/exclusion.py", "_tag_ids"),  # tag name to ids per (base_url, user), 60 s TTL, positive only (E3, EXCL-02)`; Kommentar Z. 280-284 ("These two are ...") auf drei anpassen.

**Stelle 2** (Z. 671-676): Testname `test_the_two_allowed_caches_...` und `len(ALLOWED_MODULE_STATE) == 2` auf 3, Assertion-Text nennt E3 als die Review-Entscheidung. Auch `test_no_module_level_mutable_state_outside_the_two_documented_caches` (Z. 630) sinngemäß umbenennen.

**Stelle 3** (Z. 691-703): unverändert lassen, aber beachten (keine `Resolve`/`elicit`-Nadel im neuen Code).

---

### `vulture_whitelist.py` (gate, Änderung)

**Analog:** Abschnitt Phase 18 (Z. 162-194): Überschrift `# --- ... ---`, je Name ein Absatz Begründung mit Test-Verweis und "leaves this list with the plan that calls it", danach die nackten Namen:
```python
# --- The store API of phase 18 ----------------------------------------------------------
# audit/store.py was built in one piece in plan 18-01, ...
#
# last_entry: the youngest row of one chain, ... It is driven directly by
#   tests/unit/test_audit_store.py::..., and it leaves this list with the plan that calls it.
_.last_entry
_.used_bytes_after
```
Neuer Abschnitt `# --- The guard core of phase 26, wired in by phase 27 ---`; Methoden/Attribute als `_.name`, Modulfunktionen/Klassen als bloßer Name. Namen mit bestehendem Produktionsaufrufer (z.B. `clear_cache`) nicht eintragen. Erst nach `uv run vulture src scripts vulture_whitelist.py` die tatsächlich gemeldeten Namen parken.

## Shared Patterns

### Gehärtetes XML-Parsing
**Source:** `src/mcp_connector/nextcloud/clients/xml.py` Z. 65-94 (`parse_multistatus`), Z. 40-62 (`parse_root`)
**Apply to:** `systemtags.py`, `dav.home_entries`
```python
def parse_multistatus(body: str | bytes) -> list[tuple[str, dict[str, str]]]:
    """Return ``[(href, {qualified-prop-name: text})]`` for every ``d:response``.
    Only ``d:propstat`` blocks with a 2xx status contribute properties; ..."""
```
Wirft `ToolError` bei unparsebarem Body, DTD oder Nicht-Multistatus-Wurzel; `exclusion.py` übersetzt das in `UNVERIFIABLE("unparsable")`. `resourcetype` kommt als Kind-Tag-String (`_value_of`, Z. 104-109), Ordnertest: `f"{{{xml.DAV}}}collection" in props.get(f"{{{xml.DAV}}}resourcetype", "")` wie `dav._entry` Z. 507/512.

### HTTP-Client und Credentials
**Source:** `src/mcp_connector/nextcloud/__init__.py` Z. 16-21
**Apply to:** alle neuen Funktionen
```python
@dataclass(frozen=True, slots=True)
class NcClients:
    client: httpx.AsyncClient
    creds: Credentials
```
Immer `clients.client` (shared, NoCookieJar, keine Redirects) und `auth=clients.creds.auth()`; kein eigener `AsyncClient` (jwks nutzt einen eigenen nur wegen fremder Trust-Domain). `NcClients` in Phase 26 NICHT um ein Guard-Feld erweitern (RESEARCH Open Question 3).

### Body-Bau nur mit lxml, Ids nur ASCII-Ziffern
**Source:** `dav.py` Z. 38-42 (`_DIGITS`), Z. 131-140 (`_stat_body`), Z. 316-332 (`build_fileid_body` mit doppelter Ziffernprüfung)
**Apply to:** `systemtags.py`

### Kein Retry außer dem einen 412-Neuversuch
**Source:** `dav.py` Modul-Docstring Z. 9-12, `_check` Z. 751-752 ("No retry, ever")
**Apply to:** `exclusion.py`

### Fehlerwerte statt Exceptions an der Policy-Grenze
**Source:** `dav.find_by_fileid` Z. 375-377 ("``None`` and not an exception: ... the caller words that better than this layer could") und `jwks.py` Z. 24-27 (Layer definiert keine eigene Exception)
**Apply to:** `exclusion.py` (`TagScope` mit Grundcode, kein neuer Wert in `errors.REASONS`)

### Englische Docstrings mit Begründung ("Why ...")
**Source:** Modul-Docstrings von `jwks.py` Z. 1-28 und `capabilities.py` Z. 1-27
**Apply to:** beide neuen Module (Modul-Docstring erklärt D-25-05, E3, UND-Semantik, warum Home-Wurzel statt Sandbox).

## No Analog Found

Keine. Einzige echte Neuheit ist die UND-Semantik-bedingte Aufteilung "ein REPORT je Schreibweise innerhalb einer Flight"; dafür gibt es kein Codebasis-Analog, das Muster steht in RESEARCH (Quellbefund A, Testmatrix Kriterium 4) und wird mit `asyncio.gather` wie in `tools/context.py` Z. 248 umgesetzt.

## Metadata

**Analog search scope:** `src/mcp_connector/oauth/`, `src/mcp_connector/nextcloud/` (inkl. `clients/`), `src/mcp_connector/tools/context.py`, `src/mcp_connector/config.py`, `scripts/tag_spike.py`, `tests/unit/`, `tests/contract/`, `tests/conftest.py`, `vulture_whitelist.py`
**Files scanned:** 14
**Pattern extraction date:** 2026-09-27
