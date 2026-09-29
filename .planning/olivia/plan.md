# MCP Connector "olivia" – piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** un fork del connettore MCP Nextcloud in cui `files_download` e `fetch` restituiscono un link di download temporaneo (1 download completato, 10 minuti) servito dal connettore, così Claude in claude.ai/Desktop recupera i file dal proprio ambiente di esecuzione; più `files_read` entro 150.000 caratteri ed eventi/mail più completi.

**Architecture:** fork di `street1983nk/nextcloud-mcp-connector` al tag `v0.3.2`, branch `olivia`. Codice nuovo isolato nel pacchetto `src/mcp_connector/downloads/` (archivio biglietti SQLite separato, rotta pubblica `/dl/{token}`, emissione del link, filtro dei log); modifiche mirate a `files`, `fetch`, `caldav`, `provider_map`, `config`, form amministrativo e `info.xml`. La rinomina dell'app in `mcp_connector_olivia` avviene solo nel workflow di build, tramite script.

**Tech Stack:** Python 3.13, uv, MCP Python SDK (FastMCP), Starlette/uvicorn, httpx, sqlite3 (stdlib), pytest + anyio + respx, GitHub Actions, ghcr.io, Nextcloud AppAPI/HaRP.

**Spec:** `/Users/adrosera/nextcloud/docs/superpowers/specs/2026-09-29-mcp-connector-olivia-design.md` (copiata nel repository al Task 0 come `docs/olivia/design.md`).

## Global Constraints

- Base: tag upstream `v0.3.2`; branch di lavoro `olivia`; tag nostri `v0.3.2-olivia.<n>` (primo `v0.3.2-olivia.1`).
- Repository: `github.com/aledrosera/nextcloud-mcp-connector` (pubblico, AGPL-3.0 invariata); clone locale in `/Users/adrosera/nextcloud/mcp-connector-olivia`.
- App id dopo la rinomina: `mcp_connector_olivia`; immagine `ghcr.io/aledrosera/mcp_connector_olivia:<image-tag>`; `<version>` in `info.xml` resta `0.3.2`, `<image-tag>` = `0.3.2-olivia.<n>`.
- Pacchetto Python `mcp_connector` e logger `"mcp_connector"` **non** si rinominano.
- Link: token `secrets.token_urlsafe(32)`; nel database solo SHA-256; URL `<NC_MCP_PUBLIC_URL>/dl/<token>`; vale fino al primo download **completato**; scadenza default **10** minuti, intervallo **1–60** (`NC_MCP_DOWNLOAD_TTL_MINUTES`, campo form `download_ttl_minutes`); nessuna condivisione Nextcloud.
- Rotta `/dl/{token}`: `GET` e `HEAD`; qualsiasi link non valido → **404** con corpo identico `Not found`; `HEAD` non consuma; Nextcloud irraggiungibile prima dell'invio → **502**.
- Biglietti in `APP_PERSISTENT_STORAGE/downloads.sqlite3`.
- `files_read`: blocco predefinito **64 KiB**; risposta serializzata ≤ **150.000** caratteri.
- CI deve restare verde: `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright`, `uv run vulture src scripts vulture_whitelist.py`, `uv run pytest tests/unit tests/contract`, `uv run python scripts/check_tool_budget.py` (budget 18.000 byte, max 1.400 per strumento).
- Nessuno stato mutabile a livello di modulo (contract test `ALLOWED_MODULE_STATE`); `DELETE FROM` ammesso solo nei file esentati dal contract test (si aggiunge `downloads/store.py`).
- Test asincroni: `@pytest.mark.anyio`; HTTP finto: `respx`; rotte: `starlette.testclient.TestClient`.

## Review Focus

1. **Connessione chiusa a metà download** (l'ambiente di Claude cade): il biglietto deve tornare `ready` e un nuovo `GET` deve funzionare → test in Task 4.
2. **Collegamento revocato o account in pausa dopo l'emissione del link**: il download deve dare 404, mai il file → test in Task 4.
3. **File cancellato o spostato tra emissione e download**: 404 identico, nessun errore 500 → test in Task 4.
4. **Nome file con accenti, spazi o virgolette**: `Content-Disposition` valido (fallback ASCII + `filename*` UTF-8) → test in Task 4.
5. **File di testo con molti caratteri di controllo o virgolette** (l'escape JSON gonfia il blocco): `files_read` deve ridurre il blocco finché la risposta sta sotto 150.000 caratteri → test in Task 9.

---

### Task 0: Fork, clone e ambiente di sviluppo

**Files:**
- Create: `docs/olivia/design.md`, `docs/olivia/plan.md` (copie di spec e piano)

**Interfaces:**
- Consumes: niente.
- Produces: repository `aledrosera/nextcloud-mcp-connector`, branch `olivia` da `v0.3.2`, suite verde di partenza.

- [ ] **Step 1: Creare il fork senza clonarlo**

Run: `gh repo fork street1983nk/nextcloud-mcp-connector --clone=false`
Expected: `✓ Created fork aledrosera/nextcloud-mcp-connector`

- [ ] **Step 2: Clonare nel progetto e creare il branch dal tag**

```bash
git clone https://github.com/aledrosera/nextcloud-mcp-connector /Users/adrosera/nextcloud/mcp-connector-olivia
cd /Users/adrosera/nextcloud/mcp-connector-olivia
git fetch --tags https://github.com/street1983nk/nextcloud-mcp-connector
git checkout -b olivia v0.3.2
```
Expected: `Switched to a new branch 'olivia'`

- [ ] **Step 3: Abilitare GitHub Actions sul fork**

Run: `gh api -X PUT repos/aledrosera/nextcloud-mcp-connector/actions/permissions -F enabled=true -f allowed_actions=all`
Expected: nessun output, exit 0.

- [ ] **Step 4: Installare l'ambiente e verificare la suite di partenza**

```bash
uv sync --frozen
uv run ruff check . && uv run ruff format --check . && uv run pyright && uv run vulture src scripts vulture_whitelist.py
uv run pytest tests/unit tests/contract
uv run python scripts/check_tool_budget.py
```
Expected: tutto verde (uv scarica Python 3.13 se manca). Se qualcosa fallisce già qui, fermarsi e segnalarlo: è lo stato dell'autore.

- [ ] **Step 5: Copiare spec e piano, commit, push**

```bash
mkdir -p docs/olivia
cp /Users/adrosera/nextcloud/docs/superpowers/specs/2026-09-29-mcp-connector-olivia-design.md docs/olivia/design.md
cp /Users/adrosera/nextcloud/docs/superpowers/plans/2026-09-29-mcp-connector-olivia.md docs/olivia/plan.md
git add docs/olivia
git commit -m "docs(olivia): design and implementation plan of the fork"
git push -u origin olivia
```

- [ ] **Step 6: Rimuovere la copia di lavoro del sorgente scaricata durante l'analisi**

Run: `rm -rf /Users/adrosera/nextcloud/.lavoro-mcp`

---

### Task 1: Durata del link configurabile

**Files:**
- Modify: `src/mcp_connector/config.py` (costanti e funzione accanto a `audit_retention_days`, ~riga 720)
- Modify: `src/mcp_connector/exapp/config_values.py:118-147` (`CONFIG_KEYS`, `KEY_TO_ENV`)
- Modify: `src/mcp_connector/exapp/admin_settings.py:104-189` (spacchettamento a otto nomi, nuovo campo)
- Modify: `src/mcp_connector/exapp/ui/strings.py` (etichetta e descrizione)
- Modify: `appinfo/info.xml` (nuova `<variable>` in `<environment-variables>`, righe 506-547)
- Test: `tests/unit/test_olivia_download_config.py`

**Interfaces:**
- Produces: `config.ENV_DOWNLOAD_TTL_MINUTES = "NC_MCP_DOWNLOAD_TTL_MINUTES"`, `config.DOWNLOAD_TTL_MINUTES = 10`, `config.download_ttl_minutes(env: Mapping[str, str] | None = None) -> int`.

- [ ] **Step 1: Test che fallisce**

```python
# tests/unit/test_olivia_download_config.py
import pytest

from mcp_connector import config
from mcp_connector.exapp import admin_settings, config_values


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(None, 10), ("15", 15), ("1", 1), ("60", 60), ("0", 10), ("61", 10), ("abc", 10), (" 5 ", 5)],
)
def test_download_ttl_minutes_reads_a_bounded_number(raw, expected):
    env = {} if raw is None else {config.ENV_DOWNLOAD_TTL_MINUTES: raw}
    assert config.download_ttl_minutes(env) == expected


def test_admin_form_carries_the_download_ttl_field():
    assert "download_ttl_minutes" in config_values.CONFIG_KEYS
    assert config_values.KEY_TO_ENV["download_ttl_minutes"] == config.ENV_DOWNLOAD_TTL_MINUTES
    scheme = admin_settings.form_scheme({})
    field = next(f for f in scheme["fields"] if f["id"] == "download_ttl_minutes")
    assert field["type"] == "number"
    assert field["default"] == ""
```

- [ ] **Step 2: Eseguire e vedere fallire**

Run: `uv run pytest tests/unit/test_olivia_download_config.py -v`
Expected: FAIL con `AttributeError: module 'mcp_connector.config' has no attribute 'ENV_DOWNLOAD_TTL_MINUTES'`. (Se `form_scheme` richiede un argomento diverso da `{}`, adattare la chiamata al test esistente `tests/unit/test_exapp_admin_settings.py`.)

- [ ] **Step 3: Implementare in `config.py`**

```python
ENV_DOWNLOAD_TTL_MINUTES = "NC_MCP_DOWNLOAD_TTL_MINUTES"
#: How long a download link of files_download and fetch stays valid (fork olivia).
DOWNLOAD_TTL_MINUTES = 10
DOWNLOAD_TTL_FLOOR = 1
DOWNLOAD_TTL_CEILING = 60


def download_ttl_minutes(env: Mapping[str, str] | None = None) -> int:
    """Minutes a download link lives; out of range values fall back to the default."""
    value = _bounded_number(env, ENV_DOWNLOAD_TTL_MINUTES, DOWNLOAD_TTL_MINUTES, DOWNLOAD_TTL_FLOOR)
    if value > DOWNLOAD_TTL_CEILING:
        logger.warning(
            "%s is above the highest value this server accepts (%s), so the default of %s stays in force.",
            ENV_DOWNLOAD_TTL_MINUTES,
            DOWNLOAD_TTL_CEILING,
            DOWNLOAD_TTL_MINUTES,
        )
        return DOWNLOAD_TTL_MINUTES
    return value
```
(`_bounded_number` fa già `strip()` e rifiuta i non numerici.)

- [ ] **Step 4: Aggiungere la chiave al form**

In `exapp/config_values.py`: aggiungere `"download_ttl_minutes"` in coda a `CONFIG_KEYS` e `"download_ttl_minutes": config.ENV_DOWNLOAD_TTL_MINUTES` a `KEY_TO_ENV` (non va in `SWITCH_KEYS`).

In `exapp/ui/strings.py`:
```python
ADMIN_FIELD_DOWNLOAD_TTL_LABEL = "Download link lifetime (minutes)"
ADMIN_FIELD_DOWNLOAD_TTL_DESCRIPTION = (
    "How long a link from files_download or fetch stays valid, from 1 to 60 minutes. A link "
    "also ends after its first completed download. Empty keeps the deploy variable or 10. A "
    "change takes effect after you disable and enable this app again."
)
```

In `exapp/admin_settings.py`: aggiungere `download_ttl_field` allo spacchettamento di `CONFIG_KEYS` (righe 104-112, ora otto nomi) e in coda a `"fields"`:
```python
            {
                "id": download_ttl_field,
                "title": strings.ADMIN_FIELD_DOWNLOAD_TTL_LABEL,
                "description": strings.ADMIN_FIELD_DOWNLOAD_TTL_DESCRIPTION,
                "type": "number",
                "placeholder": str(config.DOWNLOAD_TTL_MINUTES),
                "default": "",
            },
```

In `appinfo/info.xml`, dentro `<environment-variables>` dopo `NC_MCP_AUDIT_RETENTION_DAYS`:
```xml
			<variable>
				<name>NC_MCP_DOWNLOAD_TTL_MINUTES</name>
				<display-name>Download link lifetime (minutes)</display-name>
				<description>How long a download link of files_download and fetch stays valid, from 1 to 60 minutes (default 10). A link also ends after its first completed download.</description>
			</variable>
```

- [ ] **Step 5: Eseguire il nuovo test e l'intera suite**

Run: `uv run pytest tests/unit/test_olivia_download_config.py -v && uv run pytest tests/unit tests/contract`
Expected: il nuovo test PASS. Se falliscono test che congelano il numero di chiavi o di variabili (es. `tests/unit/test_exapp_admin_settings.py`, `tests/unit/test_exapp_config_values.py`, `tests/unit/test_exapp_env_setup.py`), aggiornare in quei test solo l'elenco o il conteggio atteso aggiungendo `download_ttl_minutes` / `NC_MCP_DOWNLOAD_TTL_MINUTES`, poi rieseguire fino al verde.

- [ ] **Step 6: Lint e commit**

```bash
uv run ruff check . && uv run ruff format . && uv run pyright
git add -A && git commit -m "feat(olivia): configurable lifetime of download links"
```

---

### Task 2: Archivio dei biglietti di download

**Files:**
- Create: `src/mcp_connector/downloads/__init__.py`
- Create: `src/mcp_connector/downloads/store.py`
- Modify: `tests/contract/test_no_destructive_calls.py:248-249` (esenzione `DELETE FROM` anche per `downloads/store.py`)
- Test: `tests/unit/test_olivia_ticket_store.py`

**Interfaces:**
- Produces:
  - `downloads.store.TICKETS_FILENAME = "downloads.sqlite3"`
  - `downloads.store.token_hash(token: str) -> str`
  - `@dataclass(frozen=True, slots=True) class Ticket: auth_id: str | None; nc_user: str; path: str; name: str; content_type: str; size: int; expires_at: int`
  - `class TicketStore(path: Path)` con metodi async: `issue(*, auth_id: str | None, nc_user: str, path: str, name: str, content_type: str, size: int, ttl_seconds: int, now: float | None = None) -> tuple[str, int]` (token in chiaro, scadenza epoch), `claim(token: str, *, now: float | None = None) -> Ticket | None`, `peek(token: str, *, now: float | None = None) -> Ticket | None`, `finish(token: str) -> None`, `release(token: str) -> None`
  - `downloads.store.ticket_store(env: Mapping[str, str] | None = None) -> TicketStore`

- [ ] **Step 1: Test che falliscono**

```python
# tests/unit/test_olivia_ticket_store.py
import sqlite3

import pytest

from mcp_connector.downloads import store

pytestmark = pytest.mark.anyio


def make(tmp_path):
    return store.TicketStore(tmp_path / store.TICKETS_FILENAME)


async def issue(subject, *, now=1000.0, ttl=600):
    return await subject.issue(
        auth_id="auth-1", nc_user="alice", path="/Docs/scan.pdf", name="scan.pdf",
        content_type="application/pdf", size=1234, ttl_seconds=ttl, now=now,
    )


async def test_issue_stores_only_the_hash(tmp_path):
    subject = make(tmp_path)
    token, expires = await issue(subject)
    assert len(token) >= 40 and expires == 1600
    raw = (tmp_path / store.TICKETS_FILENAME).read_bytes()
    assert token.encode() not in raw
    rows = sqlite3.connect(tmp_path / store.TICKETS_FILENAME).execute(
        "SELECT token_hash, state FROM download_tickets").fetchall()
    assert rows == [(store.token_hash(token), "ready")]


async def test_claim_is_exclusive_and_release_allows_retry(tmp_path):
    subject = make(tmp_path)
    token, _ = await issue(subject)
    ticket = await subject.claim(token, now=1001)
    assert ticket == store.Ticket("auth-1", "alice", "/Docs/scan.pdf", "scan.pdf", "application/pdf", 1234, 1600)
    assert await subject.claim(token, now=1002) is None          # already in progress
    await subject.release(token)
    assert await subject.claim(token, now=1003) is not None       # retry after an interruption


async def test_finish_makes_the_link_unusable(tmp_path):
    subject = make(tmp_path)
    token, _ = await issue(subject)
    assert await subject.claim(token, now=1001) is not None
    await subject.finish(token)
    assert await subject.claim(token, now=1002) is None
    assert await subject.peek(token, now=1002) is None


async def test_expired_and_unknown_tokens_are_refused(tmp_path):
    subject = make(tmp_path)
    token, _ = await issue(subject, ttl=60)
    assert await subject.claim(token, now=1061) is None
    assert await subject.claim("x" * 43, now=1001) is None


async def test_peek_does_not_consume(tmp_path):
    subject = make(tmp_path)
    token, _ = await issue(subject)
    assert await subject.peek(token, now=1001) is not None
    assert await subject.claim(token, now=1002) is not None


async def test_issue_purges_used_and_long_expired_rows(tmp_path):
    subject = make(tmp_path)
    used, _ = await issue(subject, now=1000)
    await subject.claim(used, now=1001)
    await subject.finish(used)
    old, _ = await issue(subject, now=1000, ttl=60)            # expires at 1060
    await issue(subject, now=1060 + store.PURGE_AFTER_SECONDS + 1)
    hashes = {h for (h,) in sqlite3.connect(tmp_path / store.TICKETS_FILENAME).execute(
        "SELECT token_hash FROM download_tickets")}
    assert store.token_hash(used) not in hashes
    assert store.token_hash(old) not in hashes
    assert len(hashes) == 1
```

- [ ] **Step 2: Eseguire e vedere fallire**

Run: `uv run pytest tests/unit/test_olivia_ticket_store.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'mcp_connector.downloads'`

- [ ] **Step 3: Implementare**

```python
# src/mcp_connector/downloads/__init__.py
"""Single-use download links for files_download and fetch (fork olivia)."""
```

```python
# src/mcp_connector/downloads/store.py
"""Download tickets: one row per link, only the SHA-256 of the token is kept.

A ticket is ``ready`` until a download starts (``in_progress``); a completed download marks it
``used``, an interrupted one puts it back to ``ready`` so the client can retry until it expires.
The file lives next to ``oauth.sqlite3`` but is a store of its own, so the upstream OAuth schema
stays untouched.
"""

import asyncio
import hashlib
import secrets
import sqlite3
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from .. import config

TICKETS_FILENAME = "downloads.sqlite3"
PURGE_AFTER_SECONDS = 3600
STATE_READY = "ready"
STATE_IN_PROGRESS = "in_progress"
STATE_USED = "used"

SCHEMA = """
CREATE TABLE IF NOT EXISTS download_tickets (
  token_hash TEXT PRIMARY KEY,
  auth_id TEXT,
  nc_user TEXT NOT NULL,
  path TEXT NOT NULL,
  name TEXT NOT NULL,
  content_type TEXT NOT NULL,
  size INTEGER NOT NULL,
  created_at INTEGER NOT NULL,
  expires_at INTEGER NOT NULL,
  state TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS download_tickets_expiry ON download_tickets(expires_at);
"""

_COLUMNS = "auth_id, nc_user, path, name, content_type, size, expires_at"


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class Ticket:
    auth_id: str | None
    nc_user: str
    path: str
    name: str
    content_type: str
    size: int
    expires_at: int


def _moment(now: float | None) -> int:
    return int(time.time() if now is None else now)


class TicketStore:
    def __init__(self, path: Path) -> None:
        self._path = path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path, isolation_level=None, timeout=5.0)
        conn.execute("PRAGMA busy_timeout = 5000")
        conn.executescript(SCHEMA)
        return conn

    async def _run[T](self, work: Callable[[sqlite3.Connection], T]) -> T:
        def call() -> T:
            conn = self._connect()
            try:
                return work(conn)
            finally:
                conn.close()

        return await asyncio.to_thread(call)

    async def issue(
        self,
        *,
        auth_id: str | None,
        nc_user: str,
        path: str,
        name: str,
        content_type: str,
        size: int,
        ttl_seconds: int,
        now: float | None = None,
    ) -> tuple[str, int]:
        moment = _moment(now)
        token = secrets.token_urlsafe(32)
        expires = moment + ttl_seconds

        def work(conn: sqlite3.Connection) -> None:
            conn.execute(
                "DELETE FROM download_tickets WHERE state = ? OR expires_at < ?",
                (STATE_USED, moment - PURGE_AFTER_SECONDS),
            )
            conn.execute(
                "INSERT INTO download_tickets (token_hash, auth_id, nc_user, path, name,"
                " content_type, size, created_at, expires_at, state)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (token_hash(token), auth_id, nc_user, path, name, content_type, size, moment,
                 expires, STATE_READY),
            )

        await self._run(work)
        return token, expires

    async def claim(self, token: str, *, now: float | None = None) -> Ticket | None:
        moment = _moment(now)
        digest = token_hash(token)

        def work(conn: sqlite3.Connection) -> Ticket | None:
            changed = conn.execute(
                "UPDATE download_tickets SET state = ? WHERE token_hash = ? AND state = ?"
                " AND expires_at > ?",
                (STATE_IN_PROGRESS, digest, STATE_READY, moment),
            ).rowcount
            if changed != 1:
                return None
            row = conn.execute(
                f"SELECT {_COLUMNS} FROM download_tickets WHERE token_hash = ?", (digest,)
            ).fetchone()
            return Ticket(*row)

        return await self._run(work)

    async def peek(self, token: str, *, now: float | None = None) -> Ticket | None:
        moment = _moment(now)

        def work(conn: sqlite3.Connection) -> Ticket | None:
            row = conn.execute(
                f"SELECT {_COLUMNS} FROM download_tickets WHERE token_hash = ? AND state = ?"
                " AND expires_at > ?",
                (token_hash(token), STATE_READY, moment),
            ).fetchone()
            return None if row is None else Ticket(*row)

        return await self._run(work)

    async def finish(self, token: str) -> None:
        await self._set_state(token, STATE_USED)

    async def release(self, token: str) -> None:
        await self._set_state(token, STATE_READY)

    async def _set_state(self, token: str, state: str) -> None:
        digest = token_hash(token)

        def work(conn: sqlite3.Connection) -> None:
            conn.execute(
                "UPDATE download_tickets SET state = ? WHERE token_hash = ? AND state = ?",
                (state, digest, STATE_IN_PROGRESS),
            )

        await self._run(work)


def ticket_store(env: Mapping[str, str] | None = None) -> TicketStore:
    return TicketStore(config.persistent_storage(env) / TICKETS_FILENAME)
```

- [ ] **Step 4: Esenzione nel contract test**

In `tests/contract/test_no_destructive_calls.py` (righe ~248-249) le esenzioni per `"DELETE FROM "` elencano `oauth/store.py` e `audit/store.py`: aggiungere `downloads/store.py` nello stesso formato.

- [ ] **Step 5: Eseguire test e suite**

Run: `uv run pytest tests/unit/test_olivia_ticket_store.py -v && uv run pytest tests/unit tests/contract`
Expected: PASS. Se `vulture` o altri contract test segnalano il nuovo pacchetto (es. `test_module_boundaries`), leggerne il messaggio e adeguare solo la dichiarazione richiesta (elenco moduli ammessi), senza spostare codice.

- [ ] **Step 6: Commit**

```bash
uv run ruff check . && uv run ruff format . && uv run pyright
git add -A && git commit -m "feat(olivia): store for single-use download tickets"
```

---

### Task 3: Download in streaming da WebDAV

**Files:**
- Modify: `src/mcp_connector/nextcloud/clients/dav.py` (nuova funzione dopo `get_range`, riga ~226)
- Test: `tests/unit/test_olivia_dav_stream.py`

**Interfaces:**
- Produces: `async def open_download(client: httpx.AsyncClient, creds: Credentials, path: str) -> httpx.Response` — risposta in streaming già controllata con `_check`; il chiamante deve fare `await response.aclose()`. Solleva `ToolError` (404 → `REASON_UNKNOWN_ID`, 403 → `REASON_PERMISSION_DENIED`, ≥500 → reason di default).

- [ ] **Step 1: Test che falliscono**

```python
# tests/unit/test_olivia_dav_stream.py
import httpx
import pytest
import respx

from mcp_connector.errors import ToolError
from mcp_connector.nextcloud.clients import dav
from mcp_connector.nextcloud.credentials import Credentials

pytestmark = pytest.mark.anyio
BASE = "http://nc.test"
URL = f"{BASE}/remote.php/dav/files/alice/Docs/scan%20%C3%A0.pdf"


async def test_open_download_streams_the_whole_file():
    body = b"%PDF-" + b"x" * 200_000
    creds = Credentials(BASE, "alice", "app-password-test")
    async with httpx.AsyncClient() as client:
        with respx.mock(assert_all_called=True) as mock:
            route = mock.get(URL).mock(return_value=httpx.Response(200, content=body))
            response = await dav.open_download(client, creds, "/Docs/scan à.pdf")
            data = b"".join([chunk async for chunk in response.aiter_raw()])
            await response.aclose()
    assert data == body
    assert route.calls[0].request.headers["accept-encoding"] == "identity"
    assert "range" not in route.calls[0].request.headers


async def test_open_download_raises_and_closes_on_404():
    creds = Credentials(BASE, "alice", "app-password-test")
    async with httpx.AsyncClient() as client:
        with respx.mock:
            respx.get(URL).mock(return_value=httpx.Response(404))
            with pytest.raises(ToolError) as caught:
                await dav.open_download(client, creds, "/Docs/scan à.pdf")
    assert "File not found" in caught.value.message
```

- [ ] **Step 2: Eseguire e vedere fallire**

Run: `uv run pytest tests/unit/test_olivia_dav_stream.py -v`
Expected: FAIL con `AttributeError: module ... has no attribute 'open_download'`

- [ ] **Step 3: Implementare in `dav.py`**

```python
async def open_download(client: httpx.AsyncClient, creds: Credentials, path: str) -> httpx.Response:
    """Open a streamed GET of one whole file for the download route (fork olivia).

    The response is checked like every other DAV answer before it is handed out; the caller
    streams it and must ``aclose()`` it. No Range header: the whole file goes to the client.
    """
    target = safe_path(path)
    request = client.build_request(
        "GET", files_url(creds, target), headers={"Accept-Encoding": "identity"}
    )
    response = await client.send(request, auth=creds.auth(), stream=True)
    try:
        _check(response, target)
    except BaseException:
        await response.aclose()
        raise
    return response
```

- [ ] **Step 4: Eseguire**

Run: `uv run pytest tests/unit/test_olivia_dav_stream.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
uv run ruff check . && uv run ruff format . && uv run pyright
git add -A && git commit -m "feat(olivia): streamed whole-file download from WebDAV"
```

---

### Task 4: Rotta pubblica `/dl/{token}`

**Files:**
- Create: `src/mcp_connector/downloads/route.py`
- Modify: `src/mcp_connector/entry_exapp.py:354-384` (aggiungere le rotte al ciclo)
- Modify: `appinfo/info.xml` (`<routes>`, righe 378-457: nuova rotta in coda)
- Modify: `tests/unit/test_exapp_env_setup.py:99` (`DECLARED_ROUTES = 14`) e l'elenco ordinato alle righe ~750-764
- Modify: `scripts/bootstrap_exapp.sh:~1217` (copia JSON delle rotte)
- Test: `tests/unit/test_olivia_download_route.py`

**Interfaces:**
- Consumes: `TicketStore`, `Ticket` (Task 2); `dav.open_download` (Task 3); `OAuthStore` (`load_authorization`, `app_password`, `access_disabled`); `config.exapp_settings(env)`; `nextcloud.http.shared_client()`.
- Produces: `downloads.route.DOWNLOAD_PATH = "/dl/{token}"`, `downloads.route.download_routes(env: Mapping[str, str], *, oauth_store: StoreProvider, tickets: TicketStore | None = None) -> list[Route]`.

- [ ] **Step 1: Verificare i nomi degli helper di identità**

Run: `grep -rn "def login_name_of\|def principal_of\|class DecryptionRejected\|^def shared_client\|^type StoreProvider" src/mcp_connector`
Expected: i moduli esatti di `login_name_of`, `principal_of` (usati da `oauth/verifier.py`), `DecryptionRejected` (`oauth/crypto.py`), `shared_client` (`nextcloud/http.py`), `StoreProvider` (`oauth/store.py`). Usare questi percorsi negli import dello Step 3.

- [ ] **Step 2: Test che falliscono**

```python
# tests/unit/test_olivia_download_route.py
import asyncio

import httpx
import pytest
import respx
from starlette.applications import Starlette
from starlette.testclient import TestClient

from mcp_connector import config
from mcp_connector.downloads import route as dl_route
from mcp_connector.downloads import store as dl_store
from mcp_connector.oauth import store as oauth_store_module

BASE = "http://nc.test"
KEY = bytes(range(32))
ENV = {
    config.ENV_APP_ID: "mcp_connector",
    config.ENV_APP_SECRET: "app-secret-test",
    config.ENV_APP_VERSION: "0.3.2",
    config.ENV_NEXTCLOUD_URL: BASE,
}
FILE_URL = f"{BASE}/remote.php/dav/files/alice/Docs/Relazione%20%C3%A0.pdf"
BODY = b"%PDF-1.7 " + b"y" * 100_000


def run(work):
    return asyncio.run(work)


@pytest.fixture
def world(tmp_path):
    oauth = oauth_store_module.OAuthStore(tmp_path / oauth_store_module.STORE_FILENAME, KEY)
    run(oauth.save_client("client-1", metadata_json='{"client_id": "client-1"}'))
    run(oauth.create_authorization("auth-1", client_id="client-1", nc_user="alice",
        nc_account_id="alice", app_password="app-password-test", scopes="nextcloud",
        resource="https://nc.example/exapps/x/mcp"))
    tickets = dl_store.TicketStore(tmp_path / dl_store.TICKETS_FILENAME)

    async def provider():
        return oauth

    app = Starlette(routes=dl_route.download_routes(ENV, oauth_store=provider, tickets=tickets))
    return oauth, tickets, TestClient(app)


def issue(tickets, *, auth_id="auth-1", name="Relazione à.pdf"):
    token, _ = run(tickets.issue(auth_id=auth_id, nc_user="alice", path="/Docs/Relazione à.pdf",
        name=name, content_type="application/pdf", size=len(BODY), ttl_seconds=600))
    return token


def test_unknown_and_malformed_tokens_get_the_same_404(world):
    _, _, client = world
    a = client.get("/dl/" + "A" * 43)
    b = client.get("/dl/short")
    assert (a.status_code, a.text) == (404, "Not found")
    assert (b.status_code, b.text) == (404, "Not found")


def test_get_streams_once_then_404(world):
    _, tickets, client = world
    token = issue(tickets)
    with respx.mock:
        respx.get(FILE_URL).mock(return_value=httpx.Response(200, content=BODY))
        first = client.get(f"/dl/{token}")
    assert first.status_code == 200 and first.content == BODY
    assert first.headers["content-type"] == "application/pdf"
    assert first.headers["cache-control"] == "no-store"
    assert first.headers["x-content-type-options"] == "nosniff"
    disposition = first.headers["content-disposition"]
    assert disposition.startswith('attachment; filename="Relazione .pdf"')
    assert "filename*=UTF-8''Relazione%20%C3%A0.pdf" in disposition
    assert client.get(f"/dl/{token}").status_code == 404


def test_head_does_not_consume(world):
    _, tickets, client = world
    token = issue(tickets)
    head = client.head(f"/dl/{token}")
    assert head.status_code == 200 and head.headers["content-length"] == str(len(BODY))
    assert run(tickets.peek(token)) is not None


def test_revoked_connection_gets_404(world):
    oauth, tickets, client = world
    token = issue(tickets)
    run(oauth.revoke_authorization("auth-1"))
    assert client.get(f"/dl/{token}").status_code == 404


def test_file_gone_gets_404_and_keeps_the_ticket_usable(world):
    _, tickets, client = world
    token = issue(tickets)
    with respx.mock:
        respx.get(FILE_URL).mock(return_value=httpx.Response(404))
        assert client.get(f"/dl/{token}").status_code == 404
    assert run(tickets.peek(token)) is not None


def test_nextcloud_down_gets_502(world):
    _, tickets, client = world
    token = issue(tickets)
    with respx.mock:
        respx.get(FILE_URL).mock(return_value=httpx.Response(503))
        assert client.get(f"/dl/{token}").status_code == 502
    assert run(tickets.peek(token)) is not None


class _Broken(httpx.AsyncByteStream):
    async def __aiter__(self):
        yield b"%PDF-partial"
        raise httpx.ReadError("connection reset")


def test_interrupted_download_releases_the_ticket(world):
    _, tickets, client = world
    token = issue(tickets)
    with respx.mock:
        respx.get(FILE_URL).mock(return_value=httpx.Response(200, stream=_Broken()))
        with pytest.raises(Exception):
            client.get(f"/dl/{token}")
    assert run(tickets.peek(token)) is not None
```
(Se `save_client`/`create_authorization`/`revoke_authorization` hanno argomenti in più, copiarli da `tests/unit/test_oauth_store.py::with_authorization`.)

- [ ] **Step 3: Eseguire e vedere fallire**

Run: `uv run pytest tests/unit/test_olivia_download_route.py -v`
Expected: FAIL con `ImportError: cannot import name 'route'`

- [ ] **Step 4: Implementare `downloads/route.py`**

```python
# src/mcp_connector/downloads/route.py
"""The public ``/dl/{token}`` route: streams one file once, with the rights of its issuer.

Every refusal is the same 404, so a caller learns nothing about which tokens exist. The
credentials are rebuilt at download time from the connection that issued the link, so a
connection ended in Nextcloud (or an account paused on the connections page) ends its links too.
"""

import logging
import re
import time
from collections.abc import AsyncIterator, Mapping
from urllib.parse import quote

import httpx
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response, StreamingResponse
from starlette.routing import Route

from .. import config
from ..errors import REASON_PERMISSION_DENIED, REASON_UNKNOWN_ID, ToolError
from ..nextcloud.clients import dav
from ..nextcloud.credentials import MODE_APPAPI, MODE_BASIC, Credentials
from ..nextcloud.http import shared_client
from ..oauth.crypto import DecryptionRejected
from ..oauth.store import StoreProvider
from ..oauth.verifier import login_name_of, principal_of
from .store import Ticket, TicketStore, ticket_store

logger = logging.getLogger(__name__)

DOWNLOAD_PATH = "/dl/{token}"
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_-]{20,128}")
CHUNK_BYTES = 64 * 1024


def _not_found() -> Response:
    return PlainTextResponse("Not found", status_code=404, headers={"Cache-Control": "no-store"})


def _bad_gateway() -> Response:
    return PlainTextResponse("Bad gateway", status_code=502, headers={"Cache-Control": "no-store"})


def _disposition(name: str) -> str:
    fallback = name.encode("ascii", "ignore").decode("ascii").replace('"', "").replace("\\", "")
    return f"attachment; filename=\"{fallback or 'download'}\"; filename*=UTF-8''{quote(name, safe='')}"


def _headers(ticket: Ticket, length: str) -> dict[str, str]:
    return {
        "Content-Type": ticket.content_type or "application/octet-stream",
        "Content-Length": length,
        "Content-Disposition": _disposition(ticket.name),
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
    }


def _masked(token: str) -> str:
    return f"{token[:4]}…"


async def _credentials(
    env: Mapping[str, str], oauth_store: StoreProvider, ticket: Ticket
) -> Credentials | None:
    settings = config.exapp_settings(env)
    store = await oauth_store()
    if ticket.auth_id:
        row = await store.load_authorization(ticket.auth_id)
        if row is None or row.revoked_at is not None:
            return None
        if await store.access_disabled(principal_of(row)):
            return None
        try:
            password = await store.app_password(ticket.auth_id)
        except DecryptionRejected:
            return None
        if not password:
            return None
        return Credentials(settings.base_url, login_name_of(row), password, mode=MODE_BASIC)
    if await store.access_disabled(ticket.nc_user):
        return None
    return Credentials(
        settings.base_url, ticket.nc_user, settings.app_secret, mode=MODE_APPAPI,
        app_id=settings.app_id, app_version=settings.app_version, aa_version=settings.aa_version,
    )


def download_routes(
    env: Mapping[str, str], *, oauth_store: StoreProvider, tickets: TicketStore | None = None
) -> list[Route]:
    store = tickets if tickets is not None else ticket_store(env)

    async def download(request: Request) -> Response:
        token = str(request.path_params.get("token", ""))
        if not TOKEN_PATTERN.fullmatch(token):
            return _not_found()
        if request.method == "HEAD":
            ticket = await store.peek(token)
            if ticket is None or await _credentials(env, oauth_store, ticket) is None:
                return _not_found()
            return Response(status_code=200, headers=_headers(ticket, str(ticket.size)))

        ticket = await store.claim(token)
        if ticket is None:
            return _not_found()
        creds = await _credentials(env, oauth_store, ticket)
        if creds is None:
            await store.release(token)
            return _not_found()
        try:
            upstream = await dav.open_download(shared_client(), creds, ticket.path)
        except ToolError as exc:
            await store.release(token)
            if exc.reason in (REASON_UNKNOWN_ID, REASON_PERMISSION_DENIED):
                return _not_found()
            return _bad_gateway()
        except httpx.HTTPError:
            await store.release(token)
            return _bad_gateway()

        length = upstream.headers.get("Content-Length") or str(ticket.size)

        async def body() -> AsyncIterator[bytes]:
            completed = False
            try:
                async for chunk in upstream.aiter_raw(chunk_size=CHUNK_BYTES):
                    yield chunk
                completed = True
            finally:
                await upstream.aclose()
                if completed:
                    await store.finish(token)
                    logger.info("download delivered: user=%s file=%s link=%s at=%s",
                                ticket.nc_user, ticket.name, _masked(token), int(time.time()))
                else:
                    await store.release(token)

        return StreamingResponse(body(), status_code=200, headers=_headers(ticket, length))

    return [Route(DOWNLOAD_PATH, download, methods=["GET", "HEAD"])]
```

- [ ] **Step 5: Eseguire i test della rotta**

Run: `uv run pytest tests/unit/test_olivia_download_route.py -v`
Expected: PASS (tutti e 7).

- [ ] **Step 6: Collegare la rotta e dichiararla**

In `entry_exapp.py`, nel ciclo delle righe 354-384, aggiungere `*download_routes(env, oauth_store=store),` dopo `*purge_routes(...)`, con `from .downloads.route import download_routes` negli import.

In `appinfo/info.xml`, in coda a `<routes>`:
```xml
			<route>
				<url>^/dl/[A-Za-z0-9_-]{20,128}$</url>
				<verb>GET,HEAD</verb>
				<access_level>PUBLIC</access_level>
				<headers_to_exclude>["AUTHORIZATION-APP-API","EX-APP-ID","EX-APP-VERSION","AA-VERSION","X-ORIGIN-IP"]</headers_to_exclude>
			</route>
```
Aggiornare `tests/unit/test_exapp_env_setup.py` (`DECLARED_ROUTES = 14` e la coppia `("^/dl/[A-Za-z0-9_-]{20,128}$", PUBLIC)` in coda all'elenco ordinato) e la copia JSON in `scripts/bootstrap_exapp.sh` con lo stesso oggetto nello stesso formato delle altre rotte.

- [ ] **Step 7: Suite completa e commit**

Run: `uv run pytest tests/unit tests/contract`
Expected: PASS.
```bash
uv run ruff check . && uv run ruff format . && uv run pyright && uv run vulture src scripts vulture_whitelist.py
git add -A && git commit -m "feat(olivia): public single-use download route"
```

---

### Task 5: Token mascherato nel log di accesso

**Files:**
- Create: `src/mcp_connector/downloads/logs.py`
- Modify: `src/mcp_connector/entry_exapp.py` (`main()`, prima dei due `uvicorn.run`, ~riga 819)
- Test: `tests/unit/test_olivia_download_logs.py`

**Interfaces:**
- Produces: `downloads.logs.RedactDownloadToken(logging.Filter)`, `downloads.logs.redact_download_tokens() -> None`.

- [ ] **Step 1: Test che falliscono**

```python
# tests/unit/test_olivia_download_logs.py
import logging

from mcp_connector.downloads import logs


def record(path: str) -> logging.LogRecord:
    return logging.LogRecord("uvicorn.access", logging.INFO, __file__, 1,
                             '%s - "%s %s HTTP/%s" %d', ("1.2.3.4:5", "GET", path, "1.1", 200), None)


def test_token_is_masked():
    item = record("/dl/AbCdEfGhIjKlMnOpQrStUvWxYz0123456789_-abcd")
    assert logs.RedactDownloadToken().filter(item) is True
    assert item.args[2] == "/dl/AbCd…"
    assert "AbCdEfGh" not in item.getMessage()


def test_other_paths_are_untouched():
    item = record("/mcp")
    logs.RedactDownloadToken().filter(item)
    assert item.args[2] == "/mcp"


def test_install_is_idempotent():
    logs.redact_download_tokens()
    logs.redact_download_tokens()
    access = logging.getLogger("uvicorn.access")
    assert sum(isinstance(f, logs.RedactDownloadToken) for f in access.filters) == 1
```

- [ ] **Step 2: Eseguire e vedere fallire**

Run: `uv run pytest tests/unit/test_olivia_download_logs.py -v`
Expected: FAIL con `ImportError`

- [ ] **Step 3: Implementare**

```python
# src/mcp_connector/downloads/logs.py
"""Keep download tokens out of the uvicorn access log (same shape as entry_oauth's filter)."""

import logging

_PREFIX = "/dl/"


class RedactDownloadToken(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if isinstance(args, tuple) and len(args) >= 3 and isinstance(args[2], str):
            path = args[2]
            if path.startswith(_PREFIX):
                token = path[len(_PREFIX):].split("?", 1)[0]
                record.args = (*args[:2], f"{_PREFIX}{token[:4]}…", *args[3:])
        return True


def redact_download_tokens() -> None:
    access = logging.getLogger("uvicorn.access")
    if not any(isinstance(item, RedactDownloadToken) for item in access.filters):
        access.addFilter(RedactDownloadToken())
```

In `entry_exapp.main()` chiamare `redact_download_tokens()` una volta prima del ramo che sceglie `uvicorn.run(app, uds=...)` / `uvicorn.run(app, host=..., port=...)`.

- [ ] **Step 4: Eseguire e commit**

Run: `uv run pytest tests/unit/test_olivia_download_logs.py -v && uv run pytest tests/unit tests/contract`
Expected: PASS
```bash
uv run ruff check . && uv run ruff format . && uv run pyright
git add -A && git commit -m "feat(olivia): mask download tokens in the access log"
```

---

### Task 6: Emissione del link nel contesto della richiesta

**Files:**
- Create: `src/mcp_connector/downloads/issue.py`
- Modify: `src/mcp_connector/deps.py` (dopo `_credentials_from_oauth`, ~riga 348)
- Test: `tests/unit/test_olivia_issue_link.py`

**Interfaces:**
- Consumes: `TicketStore.issue` (Task 2), `config.download_ttl_minutes` (Task 1), `config.public_url`, `dav.stat`, `dav.safe_path`.
- Produces:
  - `deps.TicketOwner` (`@dataclass(frozen=True, slots=True)`: `auth_id: str | None`, `nc_user: str`)
  - `deps.resolve_ticket_owner(ctx: Any) -> TicketOwner`
  - `downloads.issue.HOW_TO: str`
  - `async def issue_link(clients: NcClients, owner: TicketOwner, path: str, *, env: Mapping[str, str] | None = None, tickets: TicketStore | None = None, now: float | None = None) -> dict[str, Any]` → chiavi `path, name, size, content_type, download_url, expires_at, single_use, how_to`.

- [ ] **Step 1: Test che falliscono**

```python
# tests/unit/test_olivia_issue_link.py
import httpx
import pytest
import respx

from mcp_connector import config
from mcp_connector.deps import TicketOwner
from mcp_connector.downloads import issue
from mcp_connector.downloads import store as dl_store
from mcp_connector.errors import ToolError
from mcp_connector.nextcloud import NcClients
from mcp_connector.nextcloud.credentials import Credentials

pytestmark = pytest.mark.anyio
BASE = "http://nc.test"
URL = f"{BASE}/remote.php/dav/files/alice/Docs/scan.pdf"
ENV = {config.ENV_PUBLIC_URL: "https://cloud.example/exapps/mcp_connector",
       config.ENV_DOWNLOAD_TTL_MINUTES: "5"}


def propfind(*, collection=False, length=1234, content_type="application/pdf"):
    kind = "<d:collection/>" if collection else ""
    return (
        '<?xml version="1.0"?><d:multistatus xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns">'
        "<d:response><d:href>/remote.php/dav/files/alice/Docs/scan.pdf</d:href><d:propstat><d:prop>"
        f"<d:getcontentlength>{length}</d:getcontentlength><d:getcontenttype>{content_type}</d:getcontenttype>"
        f"<d:resourcetype>{kind}</d:resourcetype><oc:fileid>4711</oc:fileid>"
        "</d:prop><d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response></d:multistatus>"
    )


async def test_issue_link_returns_a_single_use_url(tmp_path):
    tickets = dl_store.TicketStore(tmp_path / dl_store.TICKETS_FILENAME)
    clients = NcClients(client=httpx.AsyncClient(), creds=Credentials(BASE, "alice", "pw"))
    with respx.mock:
        respx.route(method="PROPFIND", url=URL).mock(return_value=httpx.Response(207, text=propfind()))
        result = await issue.issue_link(clients, TicketOwner("auth-1", "alice"), "/Docs/scan.pdf",
                                        env=ENV, tickets=tickets, now=1000)
    assert result["download_url"].startswith("https://cloud.example/exapps/mcp_connector/dl/")
    assert result["name"] == "scan.pdf" and result["size"] == 1234
    assert result["content_type"] == "application/pdf" and result["single_use"] is True
    assert result["expires_at"] == "1970-01-01T00:21:40+00:00"          # 1000 + 5 * 60
    assert "web_fetch" in result["how_to"]
    token = result["download_url"].rsplit("/", 1)[-1]
    assert (await tickets.claim(token, now=1001)).auth_id == "auth-1"


async def test_issue_link_refuses_a_folder(tmp_path):
    tickets = dl_store.TicketStore(tmp_path / dl_store.TICKETS_FILENAME)
    clients = NcClients(client=httpx.AsyncClient(), creds=Credentials(BASE, "alice", "pw"))
    with respx.mock:
        respx.route(method="PROPFIND", url=URL).mock(
            return_value=httpx.Response(207, text=propfind(collection=True)))
        with pytest.raises(ToolError, match="folder"):
            await issue.issue_link(clients, TicketOwner("auth-1", "alice"), "/Docs/scan.pdf",
                                   env=ENV, tickets=tickets)
```
Aggiungere a `tests/unit/test_appapi_credentials.py` (o file nuovo `tests/unit/test_olivia_ticket_owner.py`) un test per `resolve_ticket_owner` che costruisce il contesto come fanno i test esistenti di `deps` (identità OAuth con `credential="app-password"` → `TicketOwner(auth_id, nc_user)`; identità con `credential="appapi-impersonation"` → `TicketOwner(None, nc_user)`; credenziali `basic` senza identità → `ToolError`).

- [ ] **Step 2: Eseguire e vedere fallire**

Run: `uv run pytest tests/unit/test_olivia_issue_link.py -v`
Expected: FAIL con `ImportError: cannot import name 'TicketOwner'`

- [ ] **Step 3: Implementare in `deps.py`**

```python
@dataclass(frozen=True, slots=True)
class TicketOwner:
    """Who a download link acts for: the OAuth connection when there is one (fork olivia)."""

    auth_id: str | None
    nc_user: str


def resolve_ticket_owner(ctx: Any) -> TicketOwner:
    identity = _oauth_identity(ctx)
    if identity is not None:
        if identity.credential == CREDENTIAL_APP_PASSWORD and identity.auth_id:
            return TicketOwner(auth_id=identity.auth_id, nc_user=identity.nc_user)
        return TicketOwner(auth_id=None, nc_user=identity.nc_user)
    creds = resolve_credentials(ctx)
    if creds.mode != MODE_APPAPI:
        raise ToolError(
            message="Download links need this server to run as a Nextcloud ExApp.",
            hint="Use files_read for text files in this deployment.",
        )
    return TicketOwner(auth_id=None, nc_user=creds.user)
```
(Importare `CREDENTIAL_APP_PASSWORD` dallo stesso modulo da cui `deps.py` già importa `CREDENTIAL_IMPERSONATE`, e `dataclass` se manca.)

- [ ] **Step 4: Implementare `downloads/issue.py`**

```python
# src/mcp_connector/downloads/issue.py
"""Turn a file path into a single-use download link for the calling connection."""

import sqlite3
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from .. import config
from ..deps import TicketOwner
from ..errors import ToolError
from ..nextcloud import NcClients
from ..nextcloud.clients import dav
from .store import TicketStore, ticket_store

HOW_TO = (
    "Download it from your code execution environment (curl -L or requests); web_fetch cannot "
    "open this link. It works for one completed download and expires at expires_at."
)


async def issue_link(
    clients: NcClients,
    owner: TicketOwner,
    path: str,
    *,
    env: Mapping[str, str] | None = None,
    tickets: TicketStore | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    target = dav.safe_path(path)
    info = await dav.stat(clients.client, clients.creds, target)
    if info["is_collection"]:
        raise ToolError(
            message=f"{target} is a folder, not a file.",
            hint="Use files_list to choose a file inside the folder.",
        )
    name = target.rsplit("/", 1)[-1] or target
    content_type = info["content_type"] or "application/octet-stream"
    store = tickets if tickets is not None else ticket_store(env)
    try:
        token, expires = await store.issue(
            auth_id=owner.auth_id, nc_user=owner.nc_user, path=target, name=name,
            content_type=content_type, size=info["size"],
            ttl_seconds=config.download_ttl_minutes(env) * 60, now=now,
        )
    except (OSError, sqlite3.Error) as exc:
        raise ToolError(
            message="The download link could not be created.",
            hint="Retry in a moment; if it repeats, check the storage of this app.",
        ) from exc
    return {
        "path": target,
        "name": name,
        "size": info["size"],
        "content_type": content_type,
        "download_url": f"{config.public_url(env).rstrip('/')}/dl/{token}",
        "expires_at": datetime.fromtimestamp(expires, UTC).isoformat(),
        "single_use": True,
        "how_to": HOW_TO,
    }
```
Nota: se `deps` importa moduli che importano `downloads` si crea un ciclo; in quel caso spostare `TicketOwner` in `downloads/owner.py` e importarlo da lì sia in `deps.py` sia in `issue.py` (stessa firma).

- [ ] **Step 5: Eseguire e commit**

Run: `uv run pytest tests/unit/test_olivia_issue_link.py -v && uv run pytest tests/unit tests/contract`
Expected: PASS
```bash
uv run ruff check . && uv run ruff format . && uv run pyright
git add -A && git commit -m "feat(olivia): issue download links for the calling connection"
```

---

### Task 7: `files_download` restituisce il link

**Files:**
- Modify: `src/mcp_connector/server/reg_files.py:70-103`
- Modify: `src/mcp_connector/tools/files.py` (rimuovere `download`, `DEFAULT_DOWNLOAD_BYTES`, `HARD_DOWNLOAD_BYTES` se non più usati)
- Modify: `tests/unit/test_files_read.py` (rimuovere i test di `files_tools.download`, righe ~158-300)
- Modify: `tests/contract/test_tool_surface.py:104-119`
- Modify: `src/mcp_connector/audit/allowlist.py:52`
- Test: `tests/unit/test_olivia_files_download_tool.py`

**Interfaces:**
- Consumes: `deps.resolve_clients`, `deps.resolve_ticket_owner`, `issue.issue_link` (Task 6).
- Produces: strumento MCP `files_download(path: str) -> str` (JSON compatto con le chiavi di `issue_link`).

- [ ] **Step 1: Aggiornare il contract test (deve fallire)**

In `tests/contract/test_tool_surface.py`, il blocco di `files_download` diventa: proprietà di input esattamente `{"path"}`, required `{"path"}`, la descrizione contiene `"download_url"` e `"code execution"`.

Nuovo test del comportamento:
```python
# tests/unit/test_olivia_files_download_tool.py
import json

import pytest

from mcp_connector.deps import TicketOwner
from mcp_connector.server import reg_files

pytestmark = pytest.mark.anyio


async def test_files_download_returns_the_link(monkeypatch):
    seen = {}

    async def fake_issue(clients, owner, path):
        seen.update(owner=owner, path=path)
        return {"download_url": "https://x/dl/tok", "single_use": True}

    monkeypatch.setattr(reg_files.deps, "resolve_clients", lambda ctx: "clients")
    monkeypatch.setattr(reg_files.deps, "resolve_ticket_owner", lambda ctx: TicketOwner("a", "alice"))
    monkeypatch.setattr(reg_files.issue, "issue_link", fake_issue)
    tool = reg_files.files_download.__wrapped__ if hasattr(reg_files.files_download, "__wrapped__") else reg_files.files_download
    text = await tool(path="/Docs/scan.pdf", ctx=None)
    assert json.loads(text) == {"download_url": "https://x/dl/tok", "single_use": True}
    assert seen == {"owner": TicketOwner("a", "alice"), "path": "/Docs/scan.pdf"}
```
(Se lo strumento registrato non è richiamabile direttamente, seguire il modo in cui `tests/unit/test_tool_registration*.py` o simili invocano gli strumenti registrati e adattare solo l'invocazione.)

- [ ] **Step 2: Eseguire e vedere fallire**

Run: `uv run pytest tests/contract/test_tool_surface.py tests/unit/test_olivia_files_download_tool.py -v`
Expected: FAIL (schema con `offset`/`chunk_bytes`; `reg_files` non ha `issue`).

- [ ] **Step 3: Implementare in `reg_files.py`**

```python
from ..downloads import issue


@mcp.tool(annotations=READ_ONLY, structured_output=False)
@graceful
async def files_download(
    path: Annotated[str, Field(description="Path of the file, e.g. /Docs/scan.pdf")],
    ctx: Context | None = None,
) -> str:
    """Get a single-use download_url for any file; download it from code execution, not web_fetch."""
    clients = deps.resolve_clients(ctx)
    owner = deps.resolve_ticket_owner(ctx)
    return compact(await issue.issue_link(clients, owner, path))
```
Rimuovere gli import non più usati (`base64`, `quote`, `EmbeddedResource`, `BlobResourceContents`) e, in `tools/files.py`, la funzione `download` con le due costanti di download se nessun altro le usa (`grep -rn "DOWNLOAD_BYTES\|files_tools.download" src tests`). Eliminare da `tests/unit/test_files_read.py` i test che chiamano `files_tools.download`. In `audit/allowlist.py` la voce diventa `"files_download": frozenset({"path"})`.

- [ ] **Step 4: Eseguire suite, budget e commit**

Run: `uv run pytest tests/unit tests/contract && uv run python scripts/check_tool_budget.py && uv run vulture src scripts vulture_whitelist.py`
Expected: PASS
```bash
uv run ruff check . && uv run ruff format . && uv run pyright
git add -A && git commit -m "feat(olivia): files_download answers with a single-use download link"
```

---

### Task 8: `fetch` sui file binari e risultati di Findling

**Files:**
- Modify: `src/mcp_connector/tools/files.py` (esporre `is_text`)
- Modify: `src/mcp_connector/tools/chatgpt.py:190-276` (`fetch`, `_fetch_file`)
- Modify: `src/mcp_connector/server/reg_chatgpt.py:34-39`
- Modify: `src/mcp_connector/provider_map.py:55-85` (`PROVIDER_KINDS`)
- Modify: `tests/unit/test_unified_search.py:~410-415` (atteso `file:9917` per Findling)
- Test: `tests/unit/test_olivia_fetch_binary.py`

**Interfaces:**
- Consumes: `issue.issue_link`, `issue.HOW_TO`, `deps.TicketOwner`.
- Produces: `files_tools.is_text(content_type: str) -> bool`; `chatgpt.fetch(clients, resource_id, *, owner: TicketOwner | None = None)`; `PROVIDER_KINDS["findling"] == "file"`.

- [ ] **Step 1: Test che falliscono**

```python
# tests/unit/test_olivia_fetch_binary.py
import pytest

from mcp_connector import provider_map
from mcp_connector.deps import TicketOwner
from mcp_connector.tools import chatgpt

pytestmark = pytest.mark.anyio


def test_findling_hits_become_file_ids():
    entry = {"resourceUrl": "/index.php/f/9917", "attributes": []}
    kind, identifier, resolvable = provider_map.extract_id("findling", entry, "https://cloud.example")
    assert (kind, identifier, resolvable) == ("file", "file:9917", True)


async def test_fetch_of_a_pdf_returns_a_download_link(monkeypatch):
    async def fake_find(client, creds, fileid):
        return {"path": "/Docs/scan.pdf", "name": "scan.pdf", "size": 1234, "content_type": "application/pdf"}

    async def fake_issue(clients, owner, path):
        return {"download_url": "https://x/dl/tok", "expires_at": "2026-09-29T10:10:00+00:00",
                "size": 1234, "content_type": "application/pdf", "name": "scan.pdf"}

    monkeypatch.setattr(chatgpt.dav_client, "find_by_fileid", fake_find)
    monkeypatch.setattr(chatgpt.issue, "issue_link", fake_issue)
    clients = type("C", (), {"client": None, "creds": type("K", (), {"base_url": "https://cloud.example"})()})()
    result = await chatgpt._fetch_file(clients, "4711", owner=TicketOwner("a", "alice"))
    assert result["url"] == "https://x/dl/tok"
    assert result["metadata"]["download_url"] == "https://x/dl/tok"
    assert "web_fetch" in result["text"]
    assert all(isinstance(v, str) for v in result["metadata"].values())


async def test_fetch_of_a_pdf_without_owner_keeps_the_old_refusal(monkeypatch):
    from mcp_connector.errors import ToolError

    async def fake_find(client, creds, fileid):
        return {"path": "/Docs/scan.pdf", "name": "scan.pdf", "size": 1, "content_type": "application/pdf"}

    async def fake_read(clients, path, max_bytes):
        raise ToolError(message="/Docs/scan.pdf is application/pdf and not text.", hint="h")

    monkeypatch.setattr(chatgpt.dav_client, "find_by_fileid", fake_find)
    monkeypatch.setattr(chatgpt.files_tools, "read", fake_read)
    clients = type("C", (), {"client": None, "creds": type("K", (), {"base_url": "x"})()})()
    with pytest.raises(ToolError):
        await chatgpt._fetch_file(clients, "4711")
```

- [ ] **Step 2: Eseguire e vedere fallire**

Run: `uv run pytest tests/unit/test_olivia_fetch_binary.py -v`
Expected: FAIL (Findling → `url:`; `_fetch_file` senza `owner`).

- [ ] **Step 3: Implementare**

`tools/files.py`:
```python
def is_text(content_type: str) -> bool:
    """Public face of the text check, for fetch (fork olivia)."""
    return _is_text(content_type)
```

`provider_map.py`: aggiungere `"findling": "file",` in `PROVIDER_KINDS`.

`tools/chatgpt.py`:
- import: `from ..deps import TicketOwner` e `from ..downloads import issue`;
- `fetch(...)` riceve il parametro keyword `owner: TicketOwner | None = None` e lo passa solo a `_fetch_file`;
- in `_fetch_file(clients, fileid, max_bytes=None, owner=None)`, subito dopo aver letto `entry` e `path`:
```python
    content_type = str(entry.get("content_type") or "")
    if owner is not None and content_type and not files_tools.is_text(content_type):
        link = await issue.issue_link(clients, owner, path)
        name = marks.without_marks(path.rsplit("/", 1)[-1] or path)
        return {
            "id": ids.encode_file(fileid),
            "title": name,
            "text": (
                f"{name} is a {content_type} file of {link['size']} bytes and is not returned "
                f"as text. {issue.HOW_TO}\n{link['download_url']}"
            ),
            "url": str(link["download_url"]),
            "metadata": {
                "kind": "file",
                "path": path,
                "content_type": content_type,
                "size": str(link["size"]),
                "download_url": str(link["download_url"]),
                "expires_at": str(link["expires_at"]),
            },
        }
```
`server/reg_chatgpt.py`: prima di chiamare `chatgpt.fetch`, risolvere il proprietario senza far fallire i deployment senza ExApp:
```python
    try:
        owner = deps.resolve_ticket_owner(ctx)
    except ToolError:
        owner = None
    ... await chatgpt.fetch(clients, id, owner=owner)
```
Aggiornare il test esistente di Findling in `tests/unit/test_unified_search.py` (~410-415): ora l'id atteso è `file:9917` e `resolvable` è `True`.

- [ ] **Step 4: Eseguire suite e commit**

Run: `uv run pytest tests/unit/test_olivia_fetch_binary.py -v && uv run pytest tests/unit tests/contract`
Expected: PASS
```bash
uv run ruff check . && uv run ruff format . && uv run pyright
git add -A && git commit -m "feat(olivia): fetch hands out download links for binary files; Findling hits are files"
```

---

### Task 9: `files_read` entro 150.000 caratteri

**Files:**
- Modify: `src/mcp_connector/tools/files.py:30` (`DEFAULT_MAX_BYTES`)
- Modify: `src/mcp_connector/server/reg_files.py:58-67`
- Test: `tests/unit/test_olivia_files_read_budget.py`

**Interfaces:**
- Produces: `files_tools.DEFAULT_MAX_BYTES = 64 * 1024`; `reg_files.TOOL_RESULT_CHAR_LIMIT = 150_000`; `reg_files.read_within_budget(clients, path: str, offset: int) -> str`.

- [ ] **Step 1: Test che falliscono**

```python
# tests/unit/test_olivia_files_read_budget.py
import pytest

from mcp_connector.server import reg_files
from mcp_connector.tools import files as files_tools

pytestmark = pytest.mark.anyio


def test_default_chunk_is_64_kib():
    assert files_tools.DEFAULT_MAX_BYTES == 64 * 1024


async def test_inflated_text_is_read_in_smaller_chunks(monkeypatch):
    calls = []

    async def fake_read(clients, path, offset=0, max_bytes=files_tools.DEFAULT_MAX_BYTES):
        calls.append(max_bytes)
        content = "\x01" * max_bytes                     # each char becomes \u0001 in JSON
        return {"path": path, "content": content, "size": 10**6, "content_type": "text/plain",
                "truncated": True, "next_offset": offset + max_bytes}

    monkeypatch.setattr(reg_files.files_tools, "read", fake_read)
    text = await reg_files.read_within_budget(None, "/big.txt", 0)
    assert len(text) <= reg_files.TOOL_RESULT_CHAR_LIMIT
    assert calls[0] == 64 * 1024 and calls[-1] < calls[0]


async def test_plain_text_keeps_the_default_chunk(monkeypatch):
    async def fake_read(clients, path, offset=0, max_bytes=files_tools.DEFAULT_MAX_BYTES):
        return {"path": path, "content": "a" * max_bytes, "size": 10**6, "content_type": "text/plain",
                "truncated": True, "next_offset": offset + max_bytes}

    monkeypatch.setattr(reg_files.files_tools, "read", fake_read)
    text = await reg_files.read_within_budget(None, "/big.txt", 0)
    assert '"next_offset":65536' in text
```

- [ ] **Step 2: Eseguire e vedere fallire**

Run: `uv run pytest tests/unit/test_olivia_files_read_budget.py -v`
Expected: FAIL (`DEFAULT_MAX_BYTES` è 524288; `read_within_budget` non esiste).

- [ ] **Step 3: Implementare**

`tools/files.py`: `DEFAULT_MAX_BYTES = 64 * 1024`.

`server/reg_files.py`:
```python
#: Largest tool answer claude.ai and Claude Desktop accept (Anthropic connector docs).
TOOL_RESULT_CHAR_LIMIT = 150_000
_SMALLEST_CHUNK = 4 * 1024


async def read_within_budget(clients: Any, path: str, offset: int) -> str:
    """Read one slice and shrink it until the serialised answer fits the client limit."""
    budget = files_tools.DEFAULT_MAX_BYTES
    text = compact(await files_tools.read(clients, path=path, offset=offset, max_bytes=budget))
    while len(text) > TOOL_RESULT_CHAR_LIMIT and budget > _SMALLEST_CHUNK:
        budget //= 2
        text = compact(await files_tools.read(clients, path=path, offset=offset, max_bytes=budget))
    return text
```
e nel corpo di `files_read`: `return await read_within_budget(deps.resolve_clients(ctx), path, offset)`.

- [ ] **Step 4: Eseguire suite e commit**

Run: `uv run pytest tests/unit/test_olivia_files_read_budget.py -v && uv run pytest tests/unit tests/contract`
Expected: PASS. Se test esistenti (`test_files_read.py:119`, `test_chatgpt_fetch.py:331`) assumevano 512 KiB in modo esplicito, aggiornare il valore atteso a `64 * 1024`.
```bash
uv run ruff check . && uv run ruff format . && uv run pyright
git add -A && git commit -m "feat(olivia): files_read fits the 150k character limit of claude.ai"
```

---

### Task 10: Descrizione e calendario negli eventi, link diretto alle mail

**Files:**
- Modify: `src/mcp_connector/nextcloud/clients/caldav.py:366-409` (`parse_ics`: campo `description`)
- Modify: `src/mcp_connector/tools/chatgpt.py:359-395` (`_fetch_event`) e `:403-475` (`_fetch_mail`)
- Test: `tests/unit/test_olivia_fetch_event_mail.py`

**Interfaces:**
- Consumes: `caldav.discover_calendars(client, creds) -> list[CalendarRef(uri, display_name)]`, `caldav.get_event(client, creds, calendar_uri, object_name, calendar=None)`, `mail_client.get_message(...) -> tuple[dict, bool]`.
- Produces: eventi con chiave `description`; `chatgpt.MAIL_THREAD_PATH = "/index.php/apps/mail/box/{mailbox}/thread/{message}"`.

- [ ] **Step 1: Test che falliscono**

```python
# tests/unit/test_olivia_fetch_event_mail.py
import datetime as dt

import pytest

from mcp_connector.nextcloud.clients import caldav
from mcp_connector.tools import chatgpt

pytestmark = pytest.mark.anyio

ICS = (
    "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\nUID:u1\r\nSUMMARY:Visita\r\n"
    "DTSTART:20260930T070000Z\r\nDTEND:20260930T071500Z\r\nLOCATION:Studio\r\n"
    "DESCRIPTION:Portare i referti\\, grazie\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"
)


def test_parse_ics_reads_the_description():
    events = caldav.parse_ics(ICS.encode()) if "bytes" in str(caldav.parse_ics.__annotations__) else caldav.parse_ics(ICS)
    assert events[0]["description"] == "Portare i referti, grazie"


async def test_fetch_event_shows_description_location_and_calendar_name(monkeypatch):
    async def fake_discover(client, creds):
        return [caldav.CalendarRef("personal", "Personale")]

    async def fake_get_event(client, creds, calendar_uri, object_name, calendar=None):
        return [{"id": "x", "uid": "u1", "summary": "Visita", "all_day": False,
                 "start": dt.datetime(2026, 9, 30, 7, tzinfo=dt.UTC),
                 "end": dt.datetime(2026, 9, 30, 7, 15, tzinfo=dt.UTC),
                 "location": "Studio", "description": "Portare i referti, grazie",
                 "calendar": calendar or calendar_uri}]

    monkeypatch.setattr(chatgpt.caldav, "discover_calendars", fake_discover)
    monkeypatch.setattr(chatgpt.caldav, "get_event", fake_get_event)
    clients = type("C", (), {"client": None, "creds": type("K", (), {"base_url": "https://cloud.example"})()})()
    result = await chatgpt._fetch_event(clients, "personal", "x.ics")
    assert "Calendar: Personale" in result["text"]
    assert "Location: Studio" in result["text"]
    assert "Description: Portare i referti, grazie" in result["text"]


async def test_fetch_mail_links_the_message(monkeypatch):
    async def fake_require(clients, app):
        return None

    async def fake_get_message(client, creds, message_id):
        return {"subject": "Ciao", "body": "<p>testo</p>", "mailboxId": 6, "databaseId": 21,
                "dateInt": 1790000000}, False

    monkeypatch.setattr(chatgpt.capabilities, "require_app", fake_require)
    monkeypatch.setattr(chatgpt.mail_client, "get_message", fake_get_message)
    clients = type("C", (), {"client": None, "creds": type("K", (), {"base_url": "https://cloud.example"})()})()
    result = await chatgpt._fetch_mail(clients, "21")
    assert result["url"] == "https://cloud.example/index.php/apps/mail/box/6/thread/21"
```
(`parse_ics`: se la firma accetta `str` o `bytes` in modo diverso da come ipotizzato, chiamarla come fanno i test esistenti in `tests/unit/test_caldav*.py` e semplificare la riga. Per la mail: se `_mail_signals` richiede altre chiavi, costruire il messaggio finto con le stesse chiavi di `full_message()` in `tests/unit/test_chatgpt_fetch.py:746-788`, cambiando solo `mailboxId=6` e `databaseId=21`.)

- [ ] **Step 2: Eseguire e vedere fallire**

Run: `uv run pytest tests/unit/test_olivia_fetch_event_mail.py -v`
Expected: FAIL (nessuna `description`, calendario = uri, url generico).

- [ ] **Step 3: Implementare**

`caldav.parse_ics`, nel dizionario di ogni evento accanto a `"location": _text_of(component, "LOCATION"),`:
```python
                "description": _text_of(component, "DESCRIPTION"),
```

`chatgpt._fetch_event`, all'inizio:
```python
    refs = await caldav.discover_calendars(clients.client, clients.creds)
    display = next((ref.display_name for ref in refs if ref.uri == calendar_uri and ref.display_name), calendar_uri)
    events = await caldav.get_event(clients.client, clients.creds, calendar_uri, object_name, calendar=display)
```
e dopo il blocco `location`:
```python
    if event.get("description"):
        lines.append(f"Description: {event['description']}")
```

`chatgpt._fetch_mail`: aggiungere la costante e sostituire l'`url`:
```python
MAIL_THREAD_PATH = "/index.php/apps/mail/box/{mailbox}/thread/{message}"
...
    mailbox = message.get("mailboxId")
    url = (
        f"{clients.creds.base_url}{MAIL_THREAD_PATH.format(mailbox=mailbox, message=message_id)}"
        if str(mailbox).isdigit()
        else f"{clients.creds.base_url}{MAIL_WEB_PREFIX}"
    )
```
(formato verificato su Mail 5.12.2: rotta `page#thread` = `/box/{mailboxId}/thread/{id}`, con `id` = id interno del messaggio, lo stesso di `mail:<id>`).

- [ ] **Step 4: Eseguire suite e commit**

Run: `uv run pytest tests/unit/test_olivia_fetch_event_mail.py -v && uv run pytest tests/unit tests/contract`
Expected: PASS. Aggiornare nei test esistenti di `fetch` (evento e mail) solo le aspettative di `url` e di `Calendar:` se confrontavano il vecchio valore.
```bash
uv run ruff check . && uv run ruff format . && uv run pyright
git add -A && git commit -m "feat(olivia): fetch shows event description and calendar name, links mails directly"
```

---

### Task 11: Rinomina automatica e workflow di rilascio

**Files:**
- Create: `scripts/olivia-rename.sh`, `scripts/olivia-check-rename.sh`
- Modify: `.github/workflows/release.yml`
- Modify: `appinfo/info.xml:194-196` (`<image>`, `<image-tag>`)

**Interfaces:**
- Produces: albero rinominato con app id `mcp_connector_olivia`; release GitHub con asset `info.xml`; immagine `ghcr.io/aledrosera/mcp_connector_olivia:0.3.2-olivia.<n>`.

- [ ] **Step 1: Script di rinomina**

```bash
#!/usr/bin/env bash
# scripts/olivia-rename.sh – rename the ExApp id mcp_connector -> mcp_connector_olivia where it
# names the app. The Python package and the "mcp_connector" logger stay untouched. Idempotent.
set -euo pipefail
cd "$(dirname "$0")/.."
NEW=mcp_connector_olivia
mapfile -t files < <(git ls-files -- appinfo src tests scripts Dockerfile '.github/*' 'compose*.yml' '.env*.example' \
  | grep -v -e '^scripts/olivia-rename.sh$' -e '^scripts/olivia-check-rename.sh$')
perl -pi -e "
  s{<id>mcp_connector</id>}{<id>${NEW}</id>}g;
  s{<name>MCP Connector</name>}{<name>MCP Connector (olivia)</name>}g;
  s{street1983nk/mcp_connector(?!_olivia)}{aledrosera/${NEW}}g;
  s{exapps/mcp_connector(?![_a-z])}{exapps/${NEW}}g;
  s{proxy/mcp_connector(?![_a-z])}{proxy/${NEW}}g;
  s{nc_app_mcp_connector(?![_a-z]|_data)}{nc_app_${NEW}}g;
  s{nc_app_mcp_connector_data}{nc_app_${NEW}_data}g;
  s{\bmcp_connector:(?=[a-z])}{${NEW}:}g;
  s{\"mcp_connector_(admin|settings)\"}{\"${NEW}_\$1\"}g;
  s{APP_ID=\"mcp_connector\"}{APP_ID=\"${NEW}\"}g;
  s{findtext\(\"id\"\) != \"mcp_connector\"}{findtext(\"id\") != \"${NEW}\"}g;
  s{frozen mcp_connector\b(?!_)}{frozen ${NEW}}g;
" "${files[@]}"
echo "renamed ${#files[@]} files to ${NEW}"
```

```bash
#!/usr/bin/env bash
# scripts/olivia-check-rename.sh – fail if a structural reference to the old app id is left.
set -euo pipefail
cd "$(dirname "$0")/.."
pattern='<id>mcp_connector</id>|exapps/mcp_connector([^_a-z]|$)|nc_app_mcp_connector([^_]|$)|nc_app_mcp_connector_data|(^|[^_a-z])mcp_connector:[a-z]|"mcp_connector_(admin|settings)"|street1983nk/mcp_connector'
if git grep -nE "$pattern" -- appinfo src tests scripts Dockerfile ':!scripts/olivia-*.sh'; then
  echo "old app id still present" >&2
  exit 1
fi
echo "rename check passed"
```
Run: `chmod +x scripts/olivia-*.sh`

- [ ] **Step 2: Provare la rinomina in un worktree separato (dentro il progetto)**

```bash
git worktree add ../mcp-connector-olivia-renamed HEAD
cd ../mcp-connector-olivia-renamed
scripts/olivia-rename.sh && scripts/olivia-check-rename.sh
grep -n "<id>\|<image>" appinfo/info.xml
uv sync --frozen && uv run pytest tests/unit tests/contract
cd ../mcp-connector-olivia && git worktree remove --force ../mcp-connector-olivia-renamed
```
Expected: `rename check passed`, `<id>mcp_connector_olivia</id>`, `<image>aledrosera/mcp_connector_olivia</image>`, suite PASS. Se un test fallisce per un riferimento non coperto, aggiungere la regola mancante allo script (non modificare il test) e ripetere. Rieseguire lo script una seconda volta sullo stesso albero per verificare l'idempotenza (`git diff --stat` invariato).

- [ ] **Step 3: Tag dell'immagine in `info.xml`**

In `appinfo/info.xml` (sorgente non rinominato): `<image-tag>0.3.2-olivia.1</image-tag>`; `<version>` resta `0.3.2`; `<image>` resta `street1983nk/mcp_connector` (lo cambia lo script in build).

- [ ] **Step 4: Workflow di rilascio**

Sostituire il job `publish` di `.github/workflows/release.yml` con:
```yaml
jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7

      - name: Decide dry run and image tag
        id: cfg
        run: |
          image_tag="$(grep -oP '(?<=<image-tag>)[^<]+' appinfo/info.xml)"
          if [[ "$GITHUB_REF_TYPE" == "tag" ]]; then
            tag="${GITHUB_REF_NAME#v}"
            if [[ "$tag" != "$image_tag" ]]; then
              echo "tag $tag does not match info.xml <image-tag> $image_tag" >&2
              exit 1
            fi
            echo "dry=false" >> "$GITHUB_OUTPUT"
          else
            echo "dry=${{ inputs.dry_run }}" >> "$GITHUB_OUTPUT"
          fi
          echo "version=$image_tag" >> "$GITHUB_OUTPUT"

      - uses: astral-sh/setup-uv@v6

      - name: Rename the app id for the olivia fork
        run: scripts/olivia-rename.sh && scripts/olivia-check-rename.sh

      - name: Tests on the renamed tree
        run: uv sync --frozen && uv run pytest tests/unit tests/contract

      - uses: docker/setup-qemu-action@v4
      - uses: docker/setup-buildx-action@v4

      - name: Log in to ghcr.io
        if: ${{ steps.cfg.outputs.dry == 'false' }}
        uses: docker/login-action@v4
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Build the multi arch image (push only on a real release)
        uses: docker/build-push-action@v7
        with:
          context: .
          platforms: linux/amd64,linux/arm64
          push: ${{ steps.cfg.outputs.dry == 'false' }}
          tags: ghcr.io/${{ github.repository_owner }}/mcp_connector_olivia:${{ steps.cfg.outputs.version }}

      - name: Publish the renamed info.xml with the release
        if: ${{ steps.cfg.outputs.dry == 'false' }}
        uses: softprops/action-gh-release@v3
        with:
          files: appinfo/info.xml
```
(`on:` e `permissions:` restano quelli dell'autore; il passo dell'archivio per lo store è tolto perché non serve al fork.)

- [ ] **Step 5: Prova a secco del workflow e commit**

```bash
git add -A && git commit -m "build(olivia): rename the app id at build time and publish mcp_connector_olivia"
git push
gh workflow run release.yml --ref olivia -f dry_run=true
gh run watch "$(gh run list --workflow release.yml --limit 1 --json databaseId -q '.[0].databaseId')"
```
Expected: run verde (rinomina, controllo, test, build multi-arch senza push).

---

### Task 12: Rilascio, installazione e accettazione

**Files:** nessuno nel repository (operazioni su GitHub, LXC 104/106, Claude Desktop).

**Interfaces:**
- Consumes: tutto il resto.
- Produces: `mcp_connector_olivia` in esecuzione su Nextcloud, connettore in Claude Desktop, prove di accettazione superate.

- [ ] **Step 1: Tag e rilascio**

```bash
git tag v0.3.2-olivia.1 && git push origin v0.3.2-olivia.1
gh run watch "$(gh run list --workflow release.yml --limit 1 --json databaseId -q '.[0].databaseId')"
```
Expected: run verde; release `v0.3.2-olivia.1` con asset `info.xml`.

- [ ] **Step 2: Immagine pubblica**

Run: `curl -s "https://ghcr.io/token?scope=repository:aledrosera/mcp_connector_olivia:pull" | python3 -c 'import sys,json; print("pubblica" if json.load(sys.stdin).get("token") else "privata")'`
Expected: `pubblica`. Se `privata`: l'utente la rende pubblica da GitHub (Packages → mcp_connector_olivia → Package settings → Change visibility → Public) e si ripete il controllo.

- [ ] **Step 3: Regole nginx per la discovery OAuth del nuovo percorso (LXC 104)**

Aggiungere, accanto alle due `location =` esistenti per `mcp_connector` nel file del sito Nextcloud, le equivalenti per `mcp_connector_olivia`, con backup del file prima della modifica:
```nginx
location = /.well-known/oauth-protected-resource/exapps/mcp_connector_olivia/mcp {
    proxy_pass http://192.168.1.25:8780/exapps/mcp_connector_olivia/.well-known/oauth-protected-resource/mcp;
}
location = /.well-known/oauth-authorization-server/exapps/mcp_connector_olivia {
    proxy_pass http://192.168.1.25:8780/exapps/mcp_connector_olivia/.well-known/oauth-authorization-server;
}
```
(copiare dalle regole esistenti di `mcp_connector` le stesse direttive `proxy_set_header` eventualmente presenti.) Poi `nginx -t && systemctl reload nginx`.

- [ ] **Step 4: Installazione accanto all'originale**

```bash
ssh nextcloud 'cd /var/www/nextcloud && runuser -u www-data -- php occ app_api:app:register mcp_connector_olivia harp \
  --info-xml https://github.com/aledrosera/nextcloud-mcp-connector/releases/download/v0.3.2-olivia.1/info.xml \
  --env NC_MCP_PUBLIC_URL=https://nextcloud.olivia.casa/exapps/mcp_connector_olivia --wait-finish \
  && runuser -u www-data -- php occ app_api:app:list'
```
Expected: `mcp_connector_olivia (MCP Connector (olivia)): 0.3.2 [enabled]` accanto a `mcp_connector … [enabled]`.

- [ ] **Step 5: Verifiche tecniche**

```bash
curl -s https://nextcloud.olivia.casa/.well-known/oauth-protected-resource/exapps/mcp_connector_olivia/mcp
curl -s -o /dev/null -w "%{http_code}\n" -X POST https://nextcloud.olivia.casa/exapps/mcp_connector_olivia/mcp
curl -s -o /dev/null -w "%{http_code}\n" https://nextcloud.olivia.casa/exapps/mcp_connector_olivia/dl/AAAAAAAAAAAAAAAAAAAAAAAA
```
Expected: JSON con `resource` = `https://nextcloud.olivia.casa/exapps/mcp_connector_olivia/mcp`; `401`; `404`.

- [ ] **Step 6: Collegamento in Claude Desktop (utente)**

L'utente aggiunge il connettore personalizzato `https://nextcloud.olivia.casa/exapps/mcp_connector_olivia/mcp` (Personalizza → Connettori → Aggiungi) e completa il login.

- [ ] **Step 7: Prove di accettazione (utente in Claude Desktop, verifica lato server)**

1. "Cerca in Nextcloud le condizioni di Genera Salute RSM e dimmi quante pagine ha e cosa copre": Claude usa `search`/`files_download`, scarica dall'ambiente di esecuzione, risponde (atteso: 20 pagine).
2. Stessa cosa con un file Word presente in Nextcloud.
3. Riusare lo stesso `download_url` dopo il download: 404.
4. Impostare nel form `download_ttl_minutes = 1`, disattivare/riattivare l'app, chiedere un link e lasciarlo scadere oltre 1 minuto: 404; poi rimettere il campo vuoto e riattivare.
5. `files_read` su `/Contratti Assicurativi/Generali/manifest.csv`: risposta a blocchi con `next_offset`, nessun errore di dimensione.
6. `fetch` dell'evento di prova: testo con `Description:` e `Calendar: Personale`.
Lato server, per ogni prova: `ssh pve 'pct exec 106 -- docker logs --since 10m nc_app_mcp_connector_olivia 2>&1 | grep -E "download delivered|/dl/"'` mostra token mascherati (`/dl/xxxx…`).

- [ ] **Step 8: Chiusura**

Aggiornare la memoria del progetto (app `mcp_connector_olivia`, tag, procedura di aggiornamento manuale: rebase di `olivia` sul nuovo tag dell'autore, suite, nuovo tag `v<nuova>-olivia.1`, `app:unregister` + `app:register` con il nuovo `info.xml`). Chiedere all'utente se rimuovere l'originale `mcp_connector`.

**Ritorno indietro in qualsiasi momento:** `occ app_api:app:unregister mcp_connector_olivia` (aggiungere `--rm-data` solo se si vuole cancellare anche il volume), rimuovere le due `location` nginx aggiunte allo Step 3 e il connettore in Claude Desktop. L'originale `mcp_connector` non viene mai modificato.
