# Phase 28: Gates und Beweise - Pattern Map

**Mapped:** 2026-09-28
**Files analyzed:** 14 (9 neu, 5 geändert, dazu das Rohprotokoll-Verzeichnis)
**Analogs found:** 14 / 14 (für die Fixes ist das Analogon meist ein Nachbar im selben Modul)

Hinweis zur Schreibweise: Code und Identifier Englisch, Prosa in Docstrings Englisch (wie im Bestand), Planungsprosa Deutsch. Keine Gedankenstriche (U+2014/U+2013), auch nicht in Docstrings neuer Tests.

## File Classification

| Neue/geänderte Datei | Rolle | Datenfluss | Nächstes Analogon | Qualität |
|---|---|---|---|---|
| `tests/contract/tool_classes.py` (neu) | config (Datenmodul, kein Testmodul) | transform (statische Tabelle) | `tests/contract/test_tool_surface.py:34-76` (`EXPECTED_TOOLS`, `CREATE_TOOLS`) plus `tests/unit/guard_routes.py:1-18` (Hilfsmodul-Docstring) | exact |
| `tests/contract/test_tool_classes.py` (neu, GATE-01) | test (contract) | request-response (In-Memory `Client(mcp)`) | `tests/contract/test_tool_surface.py:87-101` | exact |
| `tests/contract/test_no_destructive_calls.py` (erweitert, EXCL-07) | test (contract, AST) | batch (Quelltext-Scan) | dieselbe Datei: `FORBIDDEN` `:86-124`, `TALK_ROUTES` `:148-159`, `ALLOWED_*` `:185-216`, `MAIL_MODULES` `:196-197`, `:603-618` | exact |
| `tests/unit/test_pair_equality.py` (neu, GATE-03 Unit, inkl. B4-Pin) | test (unit) | request-response (respx) | `tests/unit/test_talk_exclusion.py:530-568`, `tests/unit/test_chatgpt_search.py:96-102, 217-243`, `tests/unit/guard_routes.py` | role-match |
| `tests/integration/test_canary.py` (neu, GATE-02) | test (integration) | request-response plus file-I/O (Harness) | `tests/integration/test_exclusion_live.py:67-555, 1033-1044` | exact |
| `tests/integration/test_pair_equality_live.py` (neu, GATE-03 live) | test (integration) | request-response | `tests/integration/test_exclusion_live.py:121-146, 1005-1015` | exact |
| `src/mcp_connector/tools/tables.py` (Fix B1, D-28-14) | service (Tool-Logik) | transform (Zellen screenen) | `src/mcp_connector/tools/talk.py:159-237` (`FileScreen`, `file_screen`), `:539-565` | role-match |
| `src/mcp_connector/tools/chatgpt.py` (Fix B1 `fetch(table:)` `:827-864`, Fix B3 `fetch(file:)` `:319-342`) | service | request-response | `src/mcp_connector/tools/files.py:759-772` (`_visible_stat`), `chatgpt.py:790-793` (degraded in metadata) | exact |
| `src/mcp_connector/tools/notes.py` (Fix B3 `read` `:181-196`) | service | request-response | `src/mcp_connector/tools/files.py:759-772` | exact |
| `src/mcp_connector/tools/talk.py` (Fix B2 `one_room` `:847-858`) | service | request-response | dieselbe Funktion `:852-854`, `withhold.unavailable_error()` | exact |
| `src/mcp_connector/tools/notes.py` `create` `:279-289` (B4, **kein** Fix) | service | request-response | unverändert, nur Pin-Test | n/a |
| `.github/workflows/ci.yml` (neuer Schritt im Job `exapp`) | config | batch | `.github/workflows/ci.yml:121-128` (SBX-01-Schritt) | exact |
| `pyproject.toml` (`pythonpath` um `tests/contract`) | config | , | `pyproject.toml:52-57` | exact |
| `vulture_whitelist.py` | config | , | `vulture_whitelist.py:1-36` | voraussichtlich keine Änderung (siehe unten) |
| `.planning/phases/28-gates-und-beweise/raw/28-*.txt` | Rohprotokoll | file-I/O | `test_exclusion_live.py:69-80, 107-118` | exact |

---

## Pattern Assignments

### `tests/contract/tool_classes.py` (config, statische Tabelle)

**Analog:** `tests/contract/test_tool_surface.py` und `tests/unit/guard_routes.py`

**Frozen-Set-Muster mit Begründungs-Kommentar** (`test_tool_surface.py:34-40, 65-76`):
```python
# The curated set (D-03 to D-09). A set comparison, not a subset check: a twenty-third tool
# fails this file just as loudly as a missing one. ...
EXPECTED_TOOLS = {
    "files_search",
    ...
}
CREATE_TOOLS = {
    "files_upload",
    "calendar_create_event",
    "notes_create",
    "deck_create_card",
    "tables_create_row",
    "talk_send",
}
```
Neue Datei: drei `dict[str, str]` (`FILE_READERS`, `FILE_WRITERS`, `UNAFFECTED`), Name auf einen Satz Begründung, plus `MIN_REASON` und die reine Funktion `unclassified(names)` sowie den Kontextmanager `probe_tool()` (Research Code-Beispiel 1). Aufteilung nach D-28-14: **12 liest / 3 schreibt / 7 nicht betroffen**, `tables_browse` in `FILE_READERS`. `calendar_create_event`, `deck_create_card`, `tables_create_row` stehen in `CREATE_TOOLS`, aber in `UNAFFECTED` (Konsistenzregel: jeder `FILE_WRITERS`-Eintrag ist in `CREATE_TOOLS`, kein `FILE_READERS`-Eintrag ist es). Begründungstexte mit Datei:Zeile aus RESEARCH.md Abschnitt "Nicht betroffen".

**Hilfsmodul-Docstring** (`guard_routes.py:1-18`): Docstring erklärt, warum ein Modul und nicht `conftest.py`, und dass `pyproject.toml` das Verzeichnis auf den Importpfad legt. Gleiches für `tests/contract` übernehmen.

**Import der Registry und Annotationen** (`src/mcp_connector/server/__init__.py:41`):
```python
__all__ = ["CREATE_ONLY", "READ_ONLY", "compact", "graceful", "mcp"]
```
also `from mcp_connector.server import CREATE_ONLY, mcp`.

**Wichtig:** Kanarie und Paartests importieren genau diese Tabelle (`import tool_classes`), keine zweite Wahrheit. Damit `import tool_classes` aus `tests/integration` und `tests/unit` klappt, braucht `pyproject.toml` den `pythonpath`-Eintrag.

---

### `tests/contract/test_tool_classes.py` (test, contract, GATE-01)

**Analog:** `tests/contract/test_tool_surface.py`

**Imports** (`test_tool_surface.py:17-28`):
```python
import pytest
from mcp import Client

from mcp_connector.server import mcp
```
plus `import tool_classes`. `EXPECTED_TOOLS`/`CREATE_TOOLS` liegen in einem Testmodul; ein `import test_tool_surface` geht erst mit dem `pythonpath`-Eintrag `tests/contract` und bindet dann ein Testmodul als Bibliothek. Sauberer: die Kanarie und der Freeze gleichen gegen `list_tools()` ab, `CREATE_TOOLS` wird per Annotation (`read_only_hint is False`) nachgeprüft, und `test_tool_surface.py` bleibt die zweite, unabhängige Wahrheit (Research-Empfehlung: beide Abgleiche). Planer entscheidet.

**Registry-Abfrage** (`test_tool_surface.py:87-92`):
```python
@pytest.mark.anyio
async def test_files_read_is_exposed_with_honest_annotations() -> None:
    async with Client(mcp, raise_exceptions=True) as client:
        tools = {tool.name: tool for tool in (await client.list_tools()).tools}
```

**Gemeinsame Prüffunktion für Gate und Gegenprobe** (`test_no_destructive_calls.py:338-343`):
```python
def _violations(relative: str, lines: Iterable[tuple[int, str]]) -> list[str]:
    """Every finding in already filtered lines, in the form the failure message prints.

    Shared by the gate and by its counter proofs on purpose: a counter proof that
    reimplements the check proves something about the counter proof.
    """
```
Übertragen: `unclassified(names)` wird vom Freeze und von der Probe-Gegenprobe benutzt. Probe über `mcp.add_tool(..., name="files_update", annotations=CREATE_ONLY, structured_output=False)` und `mcp.remove_tool(name)` im `finally` (mcp 2.0.0 `server.py:570-619`). Zählender Assert nach dem Muster `test_no_destructive_calls.py:533-539` (`len(...) == n` mit Begründung im Text).

---

### `tests/contract/test_no_destructive_calls.py` (erweitert, EXCL-07)

**Analog:** dieselbe Datei, Familien Talk und Mail.

**Nadel-Eintrag mit Grund** (`:86-124`): neue Einträge in `FORBIDDEN`, z.B. `"systemtags-relations"`, `"tag:files"`, optional `"/apps/files/api/v1/files"`, jeweils mit Satz; Kommentarblock oberhalb im Stil `:51-63` ("The ... entries ... are the same kind of needle ...").

**Beweiszeile je Nadel** (`:148-159`):
```python
TALK_ROUTES: dict[str, str] = {
    "/schedule": '    await ocs.ocs_post(client, creds, f"{CHAT_PREFIX}/{room}/schedule", b)',
    ...
}
```
Neu: `SYSTEMTAGS_ROUTES` mit Zeilen in der f-String-Schreibweise des Projekts, z.B. `f"{creds.base_url}/remote.php/dav/systemtags-relations/files/{fileid}/{tag}"`, und `occ("tag:files:add", ...)`.

**Parametrisierte Gegenprobe gegen das echte Modul** (`:509-530`):
```python
@pytest.mark.parametrize(("needle", "line"), sorted(TALK_ROUTES.items()))
def test_each_talk_needle_trips_on_its_route_and_leaves_the_real_module_alone(
    needle: str, line: str
) -> None:
    relative = "nextcloud/clients/talk.py"
    real = _code_lines(SRC / relative)
    assert _violations(relative, real) == [], (
        f"{relative} must be clean before a needle can prove anything"
    )
    findings = _violations(relative, [*real, (len(real) + 1, line)])
    assert any(repr(needle) in finding for finding in findings), (
        f"the gate must report {needle!r} for: {line.strip()}"
    )
```
Für Systemtags `relative = "nextcloud/clients/systemtags.py"`.

**Zähltest "jede Nadel hat eine Gegenprobe"** (`:533-539`): wörtlich übernehmen mit `SYSTEMTAGS_ROUTES`.

**Erlaubte Formen als Tupel** (`:199-208`, Test `:542-552`): `ALLOWED_SYSTEMTAGS_FORMS` mit den zwei echten Aufrufen aus `src/mcp_connector/nextcloud/clients/systemtags.py`:
```python
# systemtags.py:126-131
    response = await client.request(
        "PROPFIND",
        f"{creds.base_url}{TAGS_PATH}",
        headers={"Depth": "1", "Content-Type": "application/xml"},
        ...
# systemtags.py:156-160
    response = await client.request(
        "REPORT",
        home_url(creds),
        headers={"Content-Type": "application/xml"},
```
Achtung: der REPORT zielt auf `home_url(creds)` (`systemtags.py:84-86`), nicht auf `TAGS_PATH`; eine AST-Prüfung "Aufruf erwähnt TAGS_PATH oder systemtags" sieht den REPORT daher gar nicht. Deshalb zusätzlich die Modulregel.

**Modulregel nach dem Mail-Muster** (`:196-197`, `:603-618`):
```python
MAIL_MODULES = ("nextcloud/clients/mail.py", "tools/mail.py")
WRITING_CALLS = ("ocs_post", ".post(", ".put(", ".patch(", ".delete(", "client.request")
```
Mail verbietet `client.request` komplett; Systemtags braucht `request`, darum hier die AST-Variante (Research Code-Beispiel 4, `tag_writes`): jeder `ast.Call` mit `func.attr in {"request","post","put","patch","delete","stream","send"}` in `nextcloud/clients/systemtags.py` muss `request(<Konstante in {"PROPFIND","REPORT"}>, ...)` sein. Gegenprobe: echten Quelltext plus angehängte mehrzeilige `request(\n "POST",\n f"{creds.base_url}{TAGS_PATH}",\n)` durch dieselbe Funktion schicken (Muster `:395-421`).

**Kommentar/Docstring-Filter wiederverwenden** (`:308-335` `_code_lines`), nicht neu bauen.

**Fundstellen von "systemtags" in `src/` (verifiziert):** nur `nextcloud/clients/systemtags.py`, `nextcloud/exclusion.py` (Modulname `systemtags.` als Attribut-Wert, keine String-Konstante), `nextcloud/capabilities.py:55` und `tools/search.py:276,282` (nur Kommentare/Docstrings). Die AST-Prüfung über alle Module bleibt damit auf dem echten Baum grün.

**Alte Datei-Tags:** `PROPPATCH` steht schon in `FORBIDDEN` (`:90`); Beweiszeilen `PROPPATCH` mit `oc:tags` bzw. `oc:favorite` gegen `nextcloud/clients/dav.py` im Stil `:407-421`.

---

### `tests/unit/test_pair_equality.py` (test, unit, GATE-03, inkl. B4-Pin)

**Analogs:** `tests/unit/guard_routes.py`, `tests/unit/test_talk_exclusion.py`, `tests/unit/test_chatgpt_search.py`, `tests/unit/test_notes_exclusion.py`

**Imports** (`test_talk_exclusion.py:12-25`):
```python
import json
from typing import Any

import guard_routes
import httpx
import pytest
import respx

from mcp_connector.errors import ToolError
from mcp_connector.nextcloud import NcClients, capabilities
from mcp_connector.tools import withhold
```
plus `from mcp import Client`, `from mcp.types import CallToolResult, TextContent` und `from mcp_connector.server import mcp` (`test_chatgpt_search.py:21-27`).

**Cache-Reset je Test** (`test_talk_exclusion.py:43-46`):
```python
@pytest.fixture(autouse=True)
def _fresh_tag_cache() -> None:
    guard_routes.reset()
    capabilities.clear_cache()
```
Kein `patch_untagged`: die Guard-Routen werden echt gemockt (Docstring-Satz wie `test_talk_exclusion.py:3-5`).

**Umgebung für `Client(mcp)`** (`test_chatgpt_search.py:96-102`):
```python
@pytest.fixture
def stdio_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NC_MCP_URL", BASE)
    monkeypatch.setenv("NC_MCP_USER", USER)
    monkeypatch.setenv("NC_MCP_APP_PASSWORD", SECRET)
    monkeypatch.delenv("NC_MCP_STATIC_BEARER", raising=False)
```
`BASE`/`USER` aus `guard_routes` (`:27-29`), damit die Guard-Routen passen.

**Aufruf über die Registry** (`test_chatgpt_search.py:217-230`), für Paartests aber **ohne** `raise_exceptions=True`, damit der Fehler als `CallToolResult(is_error=True)` kommt:
```python
    with respx.mock(assert_all_called=True) as mock:
        ...
        async with Client(mcp, raise_exceptions=True) as client:
            result = await client.call_tool("search", {"query": "protokoll"})
    assert result.is_error is not True
```

**Paar-Muster "getaggt, reset, erfunden, vergleichen"** (`test_talk_exclusion.py:530-546`):
```python
    with respx.mock(assert_all_called=False) as mock:
        mock_talk(mock, [file_room(), room()], None)
        guard_routes.active(mock, ("Docs/geheim.txt", "901", False))
        ...
            await talk_tools.browse(fresh(), level="messages", token=FILE_TOKEN)
    guard_routes.reset()
    with respx.mock(assert_all_called=False) as mock:
        mock_talk(mock, [room()], None)
        ...
    assert refusal(tagged.value) == refusal(unknown.value)
```
Neu ist nur die Vergleichsebene: statt `refusal(...)` die Funktion `normalised(result, *requested)` (Research Code-Beispiel 2) über `result.model_dump(mode="json", by_alias=True)`.

**Guard-Zustände** (`guard_routes.py:86-109`): `untagged(mock)`, `active(mock, *nodes)`, `unverifiable(mock)` (REPORT 500). Für 412, zweiten 412 und Timeout eigene Routen im selben Stil bauen: `mock.route(method="REPORT", url=guard_routes.HOME).mock(return_value=httpx.Response(412))` bzw. `side_effect=httpx.ReadTimeout`. Falls wiederverwendbar: als weitere Funktionen in `guard_routes.py` ergänzen (dann `tests/unit/test_guard_routes.py` mitziehen).

**Ausfall gleicher Fehler für alle Ids** (`test_notes_exclusion.py:336-349`):
```python
@pytest.mark.parametrize("note_id", ["933", "999"])
async def test_read_unverifiable_answers_every_id_the_same(clients, note_id) -> None:
    with respx.mock(assert_all_called=False) as mock:
        mock_capabilities(mock)
        guard_routes.unverifiable(mock)
        mock_note(mock, "933")
        mock_note_404(mock, "999", "Note not found")
        with pytest.raises(ToolError) as excinfo:
            await notes_tools.read(clients, note_id=f"note:{note_id}")
    assert triple(excinfo.value) == triple(withhold.unavailable_error())
```
Mock-Helfer (`mock_capabilities`, `mock_note`, `mock_note_404`) aus `test_notes_exclusion.py:72-...` als Vorlage kopieren; Tables-URLs aus `tests/unit/test_tables_tools.py:32-50` (`ROWS_URL = f"{V1_BASE}/tables/7/rows/simple"`).

**B4-Pin (D-28-16):** ein benannter Test, der genau den Unterschied festhält: getaggte Kategorie ergibt `dav.parent_missing(candidate)` (`notes.py:279-280`), erfundene Kategorie ruft `notes_client.create_note` (`notes.py:282-288`, respx-Route `call_count == 1`). Name und Docstring sagen "accepted residual oracle, documented in phase 29 like T-27-16"; die Paarliste führt `notes_create` als benannte Ausnahme statt still übersprungen.

**B3-Fälle (D-28-17):** Nachbar-Request 5xx (fileid-SEARCH für `fetch(file:)`, Notes-GET für `notes_read`) bei getaggt und erfunden muss byte-gleich sein; heute rot, nach Fix grün.

---

### `tests/integration/test_canary.py` (test, integration, GATE-02)

**Analog:** `tests/integration/test_exclusion_live.py` (Struktur), `tests/integration/test_ctx_bundle.py` (topology-Import), `tests/integration/test_findling_sandbox.py` (occ über compose)

**Kopf, Marker, Rohprotokoll** (`test_exclusion_live.py:67-80, 107-118`):
```python
pytestmark = [pytest.mark.integration, pytest.mark.anyio]

RAW = (
    Path(__file__).resolve().parents[2]
    / ".planning" / "phases" / "27-familien-anschluss-und-sandbox-parit-t" / "raw" / "27-07-live.txt"
)

def record(line: str) -> None:
    RAW.parent.mkdir(parents=True, exist_ok=True)
    with RAW.open("a", encoding="utf-8") as fh:
        fh.write(line.rstrip("\n") + "\n")

def check(criterion: str, tool: str, case: str, ok: bool, raw: str) -> None:
    short = raw if len(raw) <= 240 else raw[:237] + "..."
    record(f"{criterion} {tool} {case}: {'ja' if ok else 'nein'} ({short})")
    assert ok, f"{criterion} {tool} {case}: {short}"
```
Pfad auf `28-gates-und-beweise/raw/28-canary.txt` ändern.

**occ ohne hart kodierten Container** (Falle: `test_exclusion_live.py:81` `CONTAINER = "nc35-nc"` läuft nicht im CI-Job exapp). Stattdessen `test_ctx_bundle.py:75, 488-500`:
```python
from topology import CONTAINERS, NC_CONTAINER

def occ(*argv: str, check_status: bool = True) -> str:
    finished = subprocess.run(  # noqa: S603 - fixed argv, test harness
        ["docker", "exec", "-u", "www-data", NC_CONTAINER, "php", "occ", *argv],  # noqa: S607
        capture_output=True, text=True, timeout=120, check=False,
    )
```
oder die compose-Form aus `test_findling_sandbox.py:49, 73-85` (`[*COMPOSE, "exec", "-T", "--user", "www-data", "nextcloud", "php", "occ", *argv]`). Beide lesen `NC_MCP_E2E_*` (`topology.py:17-24, 53-73`).

**Harness und Aufräumbeweis:** `Harness` (`test_exclusion_live.py:189-298`, v.a. `request` mit `cookies.clear()` `:200-207`, `stat` `:223-236`, `share` `:257-265`, `notes` `:278-286`), Tag per `occ` (`:464-486`), Aufräumen mit gelesenem Beweis (`:489-516`) und Fixture mit Nach-Asserts (`:519-555`):
```python
    finally:
        lines = _cleanup(state)
        for line in lines:
            record(line)
        harness.close()
        exclusion_core.clear_cache()
    assert all(line.endswith(": 404") for line in lines if "PROPFIND" in line), lines
    assert "CLEANUP notes left: 0" in lines, lines
```
Alternativ schlanker: `TagFixture` (`test_ctx_bundle.py:521-598`) plus `tag_fixture` (`:601-628`).

**Env und Skip** (`test_exclusion_live.py:361-377`): fehlende Variablen ergeben `pytest.skip(...)` mit Namen; `NC_MCP_TEST_USER != "admin"` asserten. Für CI die Variablen aus `.env.exapp` (`test_findling_sandbox.py:106-117`).

**Ausfallmodus live** (`test_exclusion_live.py:1033-1044`):
```python
@contextmanager
def report_500(world: World) -> Iterator[respx.Route]:
    home = systemtags_client.home_url(world.creds)
    with respx.mock(assert_all_called=False, assert_all_mocked=False) as router:
        failing = router.route(method="REPORT", url=home).mock(return_value=httpx.Response(500))
        router.route().pass_through()
        yield failing
```
`failing.call_count` ins Protokoll; vor jedem Modus `exclusion_core.clear_cache()` und `capabilities.clear_cache()`.

**Talk-Datei-Raum erzeugen** (`test_exclusion_live.py:985-990, 1016-1027`): Freigabe an `user2`, `GET /apps/spreed/api/v1/file/{fileid}`, `participants/active` POST/DELETE, Aufräumen mit `participants/self` DELETE und gelesener Raumliste.

**Neu gegenüber dem Analogon:** Aufrufe über `Client(mcp)` statt Tool-Funktionen (Anti-Pattern in RESEARCH.md); `Client(mcp)` liest `NC_MCP_URL`/`NC_MCP_USER`/`NC_MCP_APP_PASSWORD` (Muster `test_chatgpt_search.py:96-102`, live per `monkeypatch.setenv` aus den `NC_MCP_TEST_*`-Werten). Aufrufplan-Dict `tool -> Argumente`, `assert set(PLAN) == registry`, Ausgabezeile `KANARIE geprüft {n} von {len(registry)}`. Scan-Funktion `surfaces(result)` (Research Code-Beispiel 3). Blättern über `next` bis leer.

---

### `tests/integration/test_pair_equality_live.py` (test, integration, GATE-03 live)

**Analog:** `tests/integration/test_exclusion_live.py`

**Vergleichbarer Fehler mit Platzhalter** (`:121-137`):
```python
def shape(exc: ToolError, *substitutions: tuple[str, str]) -> tuple[str, str, str, str]:
    message, hint = exc.message, exc.hint
    for value, placeholder in substitutions:
        message = message.replace(value, placeholder)
        hint = hint.replace(value, placeholder)
    return (type(exc).__name__, message, hint, exc.reason)
```
Für Phase 28 ersetzt durch `normalised(CallToolResult, *requested)` mit Wortgrenze (Pitfall 6: Pfad und `dirname`-Kette, längste zuerst; `file:<id>` und `<id>`; Talk-Token).

**Live-Paar-Beispiel** (`:1005-1015`):
```python
            refused = await refusal(talk_tools.browse(fresh(), level="messages", token=file_token))
            reference = await refusal(
                talk_tools.browse(fresh(), level="messages", token=INVENTED_TOKEN)
            )
            check(
                "SC4", "talk_browse", "Datei-Raum messages wie erfundenes Token",
                shape(refused, (file_token, "<T>")) == shape(reference, (INVENTED_TOKEN, "<T>")),
                f"{shape(refused, (file_token, '<T>'))[1]!r}",
            )
```
Konstanten `UNKNOWN_FILEID = "999999999"` (`:91`), `INVENTED_TOKEN` (`:914`). Kann als Abschnitt in `test_canary.py` leben (Planer), dann eine gemeinsame Welt-Fixture.

---

### `src/mcp_connector/tools/tables.py` (Fix B1, D-28-14)

**Analog:** `src/mcp_connector/tools/talk.py` (`FileScreen`/`file_screen`), `src/mcp_connector/tools/withhold.py`

**Eingriffsstellen:** `_rows` (`tables.py:359-408`, Zeilen werden in `:380` über `_row` gebaut), `_row` (`:411-422`), `as_text` (`:425-454`, synchron, genutzt von `chatgpt._fetch_table` `:849`). Der Screen muss asynchron **vor** `_row`/`as_text` laufen und ein Ergebnis hineinreichen (Parameter wie `screen=` bei `talk_tools.one_message(window, message_id, screen=screen)`, `chatgpt.py:752`).

**Screen-Wert, einmal je Aufruf** (`talk.py:159-187`):
```python
@dataclass(frozen=True, slots=True)
class FileScreen:
    hidden_keys: frozenset[tuple[str, str]]
    hide_all: bool
    unavailable: bool
    ...
NO_SCREEN = FileScreen(frozenset(), False, False)
```

**Guard nur fragen, wenn es etwas zu fragen gibt** (`talk.py:228-237`):
```python
    params = [...]
    if not params and not rooms:
        return NO_SCREEN
    scope = await clients.exclusion.scope(clients)
    if scope.state == "untagged":
        return NO_SCREEN
    if scope.state == "unverifiable":
        return FileScreen(frozenset(), hide_all=True, unavailable=True)
```
Für Tables: "etwas zu fragen" = Link-Zelle mit `providerId == "files"` oder `value` mit `/f/<ziffern>`. Die fileid liefert `provider_map.file_id({}, url)` (`provider_map.py:197-208`), keine eigene Regex. Bei getaggtem Ordner (`scope.has_folders`) Pfade über `dav.paths_of_fileids` auflösen wie `file_screen` (`talk.py:217-221`), nicht auflösbar heißt zurückhalten (fail-closed). Entscheid über `scope.excludes(path=..., fileid=...)` (`exclusion.py:175`).

**Zurückgehaltene Zelle:** Wert `""`, der Leerwert der App (`tables.py:416-420`: "A row that is shorter than the title row keeps empty strings, which is the same 'missing value' the app sends"). Form der Zelle (JSON-String vs. Objekt) erst nach Live-Messung A1 festlegen.

**degraded-Idiom der Familie** (`talk.py:563-564`, `files.py:161`, `notes.py:328`):
```python
    if screen.unavailable:
        answer["degraded"] = [withhold.degraded_entry("source")]
```
Byte-Budget: keine Beschreibung und kein Parameter ändern (Pitfall 9). Marker-Filter `_clean`/`_text` (`:515-542`) bleibt davor oder danach unverändert in Kraft.

---

### `src/mcp_connector/tools/chatgpt.py` (Fix B1 `fetch(table:)`, Fix B3 `fetch(file:)`)

**B1, `_fetch_table`** (`chatgpt.py:827-864`): vor `tables_tools.as_text(...)` (`:849`) denselben Tables-Screen aufrufen; im Ausfall das fetch-Idiom:
```python
# chatgpt.py:790-793 (message-Zweig)
    if screen.unavailable:
        metadata["degraded"] = withhold.EXCLUSION_UNAVAILABLE
```
D-28-13 gilt nur für `search`; `fetch` hat `metadata["degraded"]`.

**B3, `_fetch_file`** (`chatgpt.py:319-342`), heute:
```python
    if isinstance(scope, BaseException):
        raise scope
    if scope.state == "unverifiable":
        raise withhold.unavailable_error()
    if scope.excludes(fileid=fileid):
        raise _no_file(fileid)
    if isinstance(entry, BaseException):
        raise entry
```
Ziel-Reihenfolge nach `files.py:764-771` (`_visible_stat`):
```python
    if isinstance(scope, BaseException):
        raise scope
    if scope.state == "unverifiable":
        raise withhold.unavailable_error()
    if isinstance(info, BaseException):
        raise info
    if scope.excludes(path=target, fileid=...):
        raise dav.not_found(target)
```
Also `if isinstance(entry, BaseException): raise entry` vor `scope.excludes(fileid=fileid)` ziehen. Docstring (`:300-309`, "the guard decides first") mit anpassen.

---

### `src/mcp_connector/tools/notes.py` (Fix B3 `read`)

**Stelle** (`notes.py:181-196`), heute Tag vor Fehler:
```python
    if scope.state == "unverifiable":
        raise withhold.unavailable_error()
    if scope.excludes(fileid=raw):
        raise _note_not_found(raw)
    if isinstance(fetched, ToolError) and fetched.reason == REASON_UNKNOWN_ID:
        raise _note_not_found(raw) from None
    if isinstance(fetched, BaseException):
        raise fetched
```
Ziel (D-28-17, `_visible_stat`-Muster): nach `unverifiable` zuerst `REASON_UNKNOWN_ID` auf `_note_not_found`, dann `isinstance(fetched, BaseException): raise fetched`, erst danach `scope.excludes(fileid=raw)`. Achtung: `REASON_UNKNOWN_ID` darf weiterhin "nicht gefunden" liefern (Research B3 "außer `REASON_UNKNOWN_ID`"). Docstring `:167-172` angleichen.

**`create` (`:279-289`) bleibt unverändert** (B4, D-28-16); nur Pin-Test.

---

### `src/mcp_connector/tools/talk.py` (Fix B2, D-28-15)

**Stelle** (`talk.py:847-858`):
```python
    for room in rooms:
        if str(room.get("token") or "").strip() != token:
            continue
        fileid = _room_fileid(room)
        if fileid:
            screen = await file_screen(clients, (), room_fileids=[fileid])
            if screen.unavailable:
                raise withhold.unavailable_error()
            if screen.hides_room(fileid):
                raise _unknown_token(token)
        return room
    raise _unknown_token(token)
```
Fix vor dem letzten `raise _unknown_token(token)` nach dem Muster `files.py:721-723`:
```python
    scope = await clients.exclusion.scope(clients)
    if scope.state == "unverifiable":
        raise withhold.unavailable_error()
```
Kostet einen Guard-Flight nur auf dem Fehlerpfad (einmal je Aufruf dank geteiltem Scope). Deckt `talk_send`, `talk_browse(level="messages")` und `fetch(message:)` ab, weil alle drei über `one_room` laufen (`chatgpt.py:741`). Docstring `:838-842` anpassen ("While the check cannot be answered, every token that is not visible ..."). Bestehender Test `tests/unit/test_talk_exclusion.py:571-588` bleibt grün (normaler Raum kostet weiter keinen Guard-Request); neuen Unit-Fall "erfundenes Token im Ausfall = Einheitsfehler" im selben Stil ergänzen.

---

### `.github/workflows/ci.yml` (neuer Schritt im Job `exapp`)

**Analog** (`ci.yml:121-128`):
```yaml
      - name: Findling hits run through sandbox and exclusion (SBX-01)
        # Findling entries carry only a file id, so the sandbox and the kein-ki check have
        # to resolve them before they can decide. ...
        run: |
          set -a && . ./.env.exapp && set +a
          uv run pytest tests/integration/test_findling_sandbox.py -m integration
```
Neuer Schritt direkt danach (vor dem OAuth-Schritt `:129`), Name mit Requirement-Ids (`GATE-02, GATE-03`), Kommentar erklärt Warum, `-s` optional für die Zählzeile. Keine `NC_MCP_E2E_*`-Exporte nötig: im Job gelten die `topology.py`-Defaults (`compose.exapp.yml`). Hinweis: der Job `integration` (`:179-182`) ruft `pytest -m integration` über alles; die neuen Dateien müssen dort ohne ExApp-Variablen sauber skippen (Muster `_env()` `test_findling_sandbox.py:106-117`).

---

### `pyproject.toml`

**Analog** (`pyproject.toml:52-57`):
```toml
# The integration directory carries one module that is not a test file,
# `topology.py`, ... tests/unit carries exactly one module that is
# not a test file as well, `guard_routes.py`, the mock helpers of the kein-ki guard.
pythonpath = ["tests/integration", "tests/unit"]
```
Ziel: `pythonpath = ["tests/integration", "tests/unit", "tests/contract"]` und den Kommentar um `tool_classes.py` ergänzen. Kein Eingriff in `src/`.

---

### `vulture_whitelist.py`

Voraussichtlich **keine Änderung**: vulture läuft nur über `src scripts vulture_whitelist.py` (`ci.yml:34`), Tests werden nicht gescannt. Neue Helfer in `tools/tables.py` werden aus `_rows` und `chatgpt._fetch_table` gerufen und sind damit sichtbar erreichbar. Nur falls ein Fix ein Dataclass-Feld einführt, das vulture nicht als gelesen erkennt, eine Zeile mit Begründung im Stil `vulture_whitelist.py:1-18`.

---

## Shared Patterns

### Einheitsfehler im Ausfall
**Quelle:** `src/mcp_connector/tools/withhold.py:36-59`
**Anwenden auf:** Fixes B1 (fail-closed), B2, B3; Paartests vergleichen dagegen
```python
def unavailable_error() -> ToolError:
    return ToolError(
        message=EXCLUSION_UNAVAILABLE,
        hint=UNAVAILABLE_HINT,
        reason=REASON_GUARD_TRIPPED,
    )
```

### degraded-Eintrag in Listen
**Quelle:** `withhold.py:62-68`; Nutzung `talk.py:563-564`, `files.py:161, 226`, `notes.py:328`
**Anwenden auf:** `tables_browse` (Schlüssel `"source"`); `fetch` nutzt `metadata["degraded"] = withhold.EXCLUSION_UNAVAILABLE` (`chatgpt.py:793`)

### Entscheidungsreihenfolge Einzelzugriff
**Quelle:** `files.py:733-742` (Docstring) und `:759-772`
**Anwenden auf:** `chatgpt._fetch_file`, `notes.read`
Reihenfolge: Guard-Exception, `unverifiable`, Fehler des Nachbar-Requests, dann Tag.

### Frischer Guard und Cache-Reset
**Quelle:** Unit `test_talk_exclusion.py:43-54`, live `test_exclusion_live.py:340-358`, `test_findling_sandbox.py:120-129`
**Anwenden auf:** alle neuen Unit- und Live-Tests; vor jedem Ausfallmodus `exclusion_core.clear_cache()` plus `capabilities.clear_cache()`

### Gegenprobe durch dieselbe Prüffunktion
**Quelle:** `test_no_destructive_calls.py:338-343, 395-421`
**Anwenden auf:** GATE-01-Probe (`unclassified`), EXCL-07 (`_violations`, `tag_writes`), Kanarie (Kontroll-Marker läuft durch denselben Scan)

### Messbericht-Protokoll
**Quelle:** `test_exclusion_live.py:107-118` (`record`/`check`, erst schreiben, dann asserten), Kopfzeilen `:537-541`
**Anwenden auf:** `test_canary.py`, `test_pair_equality_live.py`; Rohdateien `raw/28-*.txt`, `encoding="utf-8"`, Lauf mit `PYTHONUTF8=1`

### occ nur im Harness
**Quelle:** `test_ctx_bundle.py:488-500` / `test_findling_sandbox.py:73-85`
**Anwenden auf:** alle Live-Tests; `tag:files:add` nie in `src/` (EXCL-07-Nadel `"tag:files"` prüft `src/` nur, Tests liegen außerhalb von `SRC`, `test_no_destructive_calls.py:30`)

## No Analog Found

| Datei / Teil | Rolle | Datenfluss | Grund |
|---|---|---|---|
| Probe-Registrierung in `test_tool_classes.py` (`mcp.add_tool`/`remove_tool`) | test | , | Bisher registriert kein Test zur Laufzeit ein Werkzeug; Vorlage ist Research Code-Beispiel 1 (mcp 2.0.0 `server.py:570-619`) |
| `normalised()` über ganzen `CallToolResult` | test utility | transform | Bestand vergleicht nur `ToolError`-Tripel (`test_notes_exclusion.py:64-65`, `test_exclusion_live.py:121-137`); Vorlage Research Code-Beispiel 2 |
| Marker-Scan über Blob und URI | test utility | transform | Kein Bestand; Research Code-Beispiel 3 |
| AST-Methodenprüfung `tag_writes` | test (contract) | batch | Bestehende Gates sind zeilenbasiert; Research Code-Beispiel 4 |
| Screen für Tables-Link-Zellen | service | transform | Familie Tables fragt den Guard heute nie; nächstes Muster ist `talk.file_screen` |

## Metadata

**Analog search scope:** `tests/contract/`, `tests/unit/`, `tests/integration/`, `src/mcp_connector/tools/`, `src/mcp_connector/nextcloud/clients/systemtags.py`, `src/mcp_connector/server/__init__.py`, `src/mcp_connector/provider_map.py`, `.github/workflows/ci.yml`, `pyproject.toml`, `vulture_whitelist.py`
**Files scanned:** 22
**Pattern extraction date:** 2026-09-28
