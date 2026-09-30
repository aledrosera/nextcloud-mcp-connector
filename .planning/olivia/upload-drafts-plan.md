# Caricamento di file e bozze email (fork olivia) – Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Claude salva in Nextcloud file di qualsiasi formato tramite un link di caricamento monouso (`PUT /ul/<token>`) e crea bozze email in Nextcloud Mail (nuove o in risposta, con allegati da Nextcloud), senza mai sovrascrivere né inviare.

**Architecture:** Il caricamento riusa l'archivio dei biglietti del download (`downloads/store.py`) con percorsi `upload:<path>`, una nuova rotta pubblica gemella di `/dl` e due funzioni WebDAV nuove (`ensure_folders`, `put_new_stream`). Le bozze usano la rotta interna di Mail `POST /index.php/apps/mail/api/drafts` con `OCS-APIRequest: true`, attraverso un client dedicato e un nuovo strumento `mail_draft`. La modalità base64 a pezzi di `files_upload` viene rimossa.

**Tech Stack:** Python 3.13, Starlette, httpx, uv, pytest + anyio + respx, ruff, pyright, vulture.

**Spec:** `.planning/olivia/upload-drafts-design.md` (copia di `~/nextcloud/docs/superpowers/specs/2026-09-30-olivia-upload-drafts-design.md`)

## Global Constraints

- Repository `/Users/adrosera/nextcloud/mcp-connector-olivia`, branch `olivia`; pacchetto Python `mcp_connector` e logger `"mcp_connector"` non si rinominano.
- Link di caricamento: `secrets.token_urlsafe(32)` (già in `TicketStore.issue`), percorso del biglietto `upload:<path>`, URL `<NC_MCP_PUBLIC_URL>/ul/<token>`, **30 minuti** (`UPLOAD_TTL_SECONDS = 1800`), **massimo 100 MB** (`MAX_UPLOAD_BYTES = 104857600`), un caricamento completato.
- Nessuna sovrascrittura: controllo all'emissione + `If-None-Match: *` al caricamento. Nessuna cancellazione o modifica di file o bozze.
- Qualsiasi link non valido → 404 con corpo identico `Not found` (lo stesso `_not_found()` della rotta `/dl`).
- Bozze: una sola rotta di Mail, `POST /index.php/apps/mail/api/drafts`, intestazione `OCS-APIRequest: true`, **mai** `sendAt`; `/message/send` e `/api/outbox` restano vietati ovunque.
- Allegati delle bozze: solo percorsi Nextcloud, al massimo 10, totale al massimo 25 MB (`26214400` byte), controllati prima di creare la bozza.
- Nessuno stato mutabile a livello di modulo (contract test `ALLOWED_MODULE_STATE`).
- Test asincroni con `@pytest.mark.anyio`; HTTP finto con `respx`; rotte con `starlette.testclient.TestClient`.
- Suite: `uv run pytest tests/unit tests/contract`; unico fallimento ammesso il noto baseline macOS `tests/unit/test_exapp_env_setup.py::test_the_registration_inputs_are_pinned_before_json_info[a public address with a second line]`.
- Lint/tipi prima di ogni commit: `uv run ruff check .` ("All checks passed!"), `uv run ruff format --check .`, `uv run pyright` (0 errori), `uv run vulture src scripts vulture_whitelist.py` (nessun output), `uv run python scripts/check_tool_budget.py` (entro 18000 byte, 1400 per strumento).
- Ogni commit termina con le righe `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` e `Claude-Session: https://claude.ai/code/session_01LWokcNcTM4tHdS7QwcMBpN`; stage dei file per nome; niente push, niente tag.

## Review Focus

1. Nomi di file con spazi, accenti e caratteri come `#` e `?` (es. `/Clienti/Rossi/Preventivo à #1.docx`): il link si emette e il PUT arriva al percorso giusto, codificato. → test in Task 1 e Task 3.
2. Client che interrompe il caricamento a metà: il biglietto torna utilizzabile e nessun file resta. → test in Task 3 (`ClientDisconnect`).
3. Una cartella del percorso che in realtà è un file (`/Clienti` è un file): risposta 409 `conflict`, non 502. → test in Task 3.
4. Risposta a una mail arrivata in copia nascosta o a un alias non elencato: nessun account tra i destinatari → errore chiaro con l'elenco degli account, nessuna bozza creata. → test in Task 6.
5. Destinatari con nome contenente virgole o virgolette (`"Rossi, Mario" <m@x.it>`): indirizzo ed etichetta corretti. → test in Task 6.

---

### Task 1: Link di caricamento

**Files:**
- Create: `src/mcp_connector/downloads/upload.py`
- Test: `tests/unit/test_olivia_upload_link.py`

**Interfaces:**
- Consumes: `TicketStore.issue(*, auth_id, nc_user, path, name, content_type, size, ttl_seconds, now=None) -> tuple[str, int]`, `ticket_store(env)`, `deps.TicketOwner`, `dav.safe_path`, `dav.stat` (404 → `ToolError` con `reason == REASON_UNKNOWN_ID`), `config.files_root()`, `config.public_url(env)`, `errors.ConflictError`.
- Produces: `UPLOAD_PREFIX = "upload:"`, `UPLOAD_TTL_SECONDS = 1800`, `MAX_UPLOAD_BYTES = 104857600`, `UPLOAD_HOW_TO: str`, `upload_ticket_path(path: str) -> str`, `parse_upload_path(ticket_path: str) -> str | None`, `async issue_upload_link(clients, owner, path, *, env=None, tickets=None, now=None) -> dict[str, Any]` con chiavi `path, upload_url, method, expires_at, single_use, max_bytes, how_to`.

- [ ] **Step 1: Test che falliscono**

```python
# tests/unit/test_olivia_upload_link.py
import httpx
import pytest
import respx

from mcp_connector import config
from mcp_connector.deps import TicketOwner
from mcp_connector.downloads import store as dl_store
from mcp_connector.downloads import upload
from mcp_connector.errors import ConflictError, ToolError
from mcp_connector.nextcloud import NcClients
from mcp_connector.nextcloud.credentials import Credentials

pytestmark = pytest.mark.anyio
BASE = "http://nc.test"
ENV = {config.ENV_PUBLIC_URL: "https://cloud.example/exapps/mcp_connector"}
TARGET = "/Clienti/Rossi/Preventivo à #1.docx"
URL = f"{BASE}/remote.php/dav/files/alice/Clienti/Rossi/Preventivo%20%C3%A0%20%231.docx"


def clients():
    return NcClients(client=httpx.AsyncClient(), creds=Credentials(BASE, "alice", "pw"))


def test_ticket_path_round_trip():
    assert upload.parse_upload_path(upload.upload_ticket_path("/a/b.pdf")) == "/a/b.pdf"
    assert upload.parse_upload_path("/a/b.pdf") is None
    assert upload.parse_upload_path("mail:1/2") is None
    assert upload.parse_upload_path("upload:relative.pdf") is None


async def test_link_is_issued_for_a_free_path(tmp_path):
    tickets = dl_store.TicketStore(tmp_path / dl_store.TICKETS_FILENAME)
    with respx.mock:
        respx.route(method="PROPFIND", url=URL).mock(return_value=httpx.Response(404))
        card = await upload.issue_upload_link(
            clients(), TicketOwner("auth-1", "alice"), TARGET, env=ENV, tickets=tickets, now=1000
        )
    assert card["path"] == TARGET
    assert card["upload_url"].startswith("https://cloud.example/exapps/mcp_connector/ul/")
    assert card["method"] == "PUT"
    assert card["expires_at"] == "1970-01-01T00:46:40+00:00"  # 1000 + 1800
    assert card["single_use"] is True
    assert card["max_bytes"] == 104857600
    assert "curl -fsS -T" in card["how_to"]
    token = card["upload_url"].rsplit("/", 1)[-1]
    ticket = await tickets.claim(token, now=1001)
    assert ticket is not None
    assert ticket.path == f"upload:{TARGET}"
    assert ticket.auth_id == "auth-1"


async def test_an_existing_path_is_refused(tmp_path):
    tickets = dl_store.TicketStore(tmp_path / dl_store.TICKETS_FILENAME)
    body = (
        '<?xml version="1.0"?><d:multistatus xmlns:d="DAV:"><d:response>'
        "<d:href>/remote.php/dav/files/alice/Clienti/Rossi/x</d:href><d:propstat><d:prop>"
        "<d:getcontentlength>1</d:getcontentlength><d:resourcetype/></d:prop>"
        "<d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response></d:multistatus>"
    )
    with respx.mock:
        respx.route(method="PROPFIND", url=URL).mock(return_value=httpx.Response(207, text=body))
        with pytest.raises(ConflictError, match="already exists"):
            await upload.issue_upload_link(
                clients(), TicketOwner("auth-1", "alice"), TARGET, env=ENV, tickets=tickets
            )


async def test_a_folder_target_is_refused(tmp_path):
    tickets = dl_store.TicketStore(tmp_path / dl_store.TICKETS_FILENAME)
    with pytest.raises(ToolError, match="folder"):
        await upload.issue_upload_link(
            clients(), TicketOwner("auth-1", "alice"), "/Clienti/", env=ENV, tickets=tickets
        )
```
(Se la risposta PROPFIND di prova non viene letta da `dav.stat` come esistente, prendere il corpo XML da un test esistente di `dav.stat` in `tests/unit/` e adattare solo il corpo.)

- [ ] **Step 2: Eseguire e vedere fallire**

Run: `uv run pytest tests/unit/test_olivia_upload_link.py -v`
Expected: FAIL con `ImportError` (modulo `upload` assente).

- [ ] **Step 3: Implementare**

```python
# src/mcp_connector/downloads/upload.py
"""Single-use upload links: Claude PUTs a new file from its code execution environment (fork olivia).

The link is the mirror of a download link. It lives in the same ticket store, under a ticket
path ``upload:<path>`` so that neither route can ever redeem the other's ticket, it acts with
the rights of the connection that issued it, and it can create a file but never replace one:
the path is checked here, and the PUT itself carries ``If-None-Match: *``.
"""

import sqlite3
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from .. import config
from ..deps import TicketOwner
from ..errors import REASON_UNKNOWN_ID, ConflictError, ToolError
from ..nextcloud import NcClients
from ..nextcloud.clients import dav
from .store import TicketStore, ticket_store

UPLOAD_PREFIX = "upload:"
UPLOAD_TTL_SECONDS = 30 * 60
MAX_UPLOAD_BYTES = 100 * 1024 * 1024
UPLOAD_HOW_TO = (
    "Upload from your code execution environment: curl -fsS -T <file> <upload_url>. "
    "One completed upload; the target must not exist; missing folders are created."
)
_FILE_HINT = "Give the full path of the new file, for example /Docs/report.docx."


def upload_ticket_path(path: str) -> str:
    """The ticket path an upload link is stored under."""
    return f"{UPLOAD_PREFIX}{path}"


def parse_upload_path(ticket_path: str) -> str | None:
    """The target path of an upload ticket, or ``None`` when the ticket is not one."""
    if not ticket_path.startswith(UPLOAD_PREFIX):
        return None
    path = ticket_path[len(UPLOAD_PREFIX) :]
    return path if path.startswith("/") else None


async def issue_upload_link(
    clients: NcClients,
    owner: TicketOwner,
    path: str,
    *,
    env: Mapping[str, str] | None = None,
    tickets: TicketStore | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    if (path or "").strip().endswith("/"):
        raise ToolError(message=f"{path!r} names a folder, not a file.", hint=_FILE_HINT)
    target = dav.safe_path(path)
    if target == config.files_root():
        raise ToolError(message="The upload target is the root folder, not a file.", hint=_FILE_HINT)
    try:
        await dav.stat(clients.client, clients.creds, target)
    except ToolError as exc:
        if exc.reason != REASON_UNKNOWN_ID:
            raise
    else:
        raise ConflictError(
            message=f"Something already exists at {target}.",
            hint="This server never overwrites. Choose a different name.",
        )
    store = tickets if tickets is not None else ticket_store(env)
    try:
        token, expires = await store.issue(
            auth_id=owner.auth_id,
            nc_user=owner.nc_user,
            path=upload_ticket_path(target),
            name=target.rsplit("/", 1)[-1],
            content_type="",
            size=0,
            ttl_seconds=UPLOAD_TTL_SECONDS,
            now=now,
        )
    except (OSError, sqlite3.Error) as exc:
        raise ToolError(
            message="The upload link could not be created.",
            hint="Retry in a moment; if it repeats, check the storage of this app.",
        ) from exc
    return {
        "path": target,
        "upload_url": f"{config.public_url(env).rstrip('/')}/ul/{token}",
        "method": "PUT",
        "expires_at": datetime.fromtimestamp(expires, UTC).isoformat(),
        "single_use": True,
        "max_bytes": MAX_UPLOAD_BYTES,
        "how_to": UPLOAD_HOW_TO,
    }
```
(Se `config.files_root()` ha un'altra firma, adattare solo la chiamata come in `tools/files.py::upload`.)

- [ ] **Step 4: Eseguire, lint e commit**

Run: `uv run pytest tests/unit/test_olivia_upload_link.py -v && uv run pytest tests/unit tests/contract`
Expected: PASS (salvo il baseline noto). Poi i comandi di lint delle Global Constraints; se vulture segnala le funzioni nuove ancora senza chiamanti, aggiungerle a `vulture_whitelist.py` con un commento "wired in Task 3/5".
```bash
git add src/mcp_connector/downloads/upload.py tests/unit/test_olivia_upload_link.py vulture_whitelist.py
git commit -m "feat(olivia): single-use upload links"
```

---

### Task 2: WebDAV – cartelle e PUT in streaming

**Files:**
- Modify: `src/mcp_connector/nextcloud/clients/dav.py` (dopo `put_new_file`, ~riga 575)
- Test: `tests/unit/test_olivia_dav_upload.py`

**Interfaces:**
- Consumes: `safe_path`, `files_url`, `Credentials.auth()`.
- Produces: `async ensure_folders(client, creds, folder: str) -> int | None` (None = tutte le cartelle ci sono; altrimenti lo stato HTTP del primo `MKCOL` fallito); `async put_new_stream(client, creds, path: str, body: AsyncIterator[bytes]) -> int` (stato HTTP della risposta; la risposta viene chiusa).

- [ ] **Step 1: Test che falliscono**

```python
# tests/unit/test_olivia_dav_upload.py
import httpx
import pytest
import respx

from mcp_connector.nextcloud.clients import dav
from mcp_connector.nextcloud.credentials import Credentials

pytestmark = pytest.mark.anyio
BASE = "http://nc.test"
CREDS = Credentials(BASE, "alice", "pw")
ROOT = f"{BASE}/remote.php/dav/files/alice"


async def chunks(*parts: bytes):
    for part in parts:
        yield part


async def test_ensure_folders_creates_top_down_and_accepts_existing():
    with respx.mock:
        a = respx.route(method="MKCOL", url=f"{ROOT}/Clienti").mock(return_value=httpx.Response(405))
        b = respx.route(method="MKCOL", url=f"{ROOT}/Clienti/Rossi%20%C3%A0").mock(
            return_value=httpx.Response(201)
        )
        async with httpx.AsyncClient() as client:
            assert await dav.ensure_folders(client, CREDS, "/Clienti/Rossi à") is None
    assert a.called
    assert b.called


async def test_ensure_folders_reports_the_first_failure():
    with respx.mock:
        respx.route(method="MKCOL", url=f"{ROOT}/Clienti").mock(return_value=httpx.Response(403))
        async with httpx.AsyncClient() as client:
            assert await dav.ensure_folders(client, CREDS, "/Clienti/Rossi") == 403


async def test_put_new_stream_sends_the_precondition_and_the_body():
    with respx.mock:
        route = respx.put(f"{ROOT}/Docs/a.pdf").mock(return_value=httpx.Response(201))
        async with httpx.AsyncClient() as client:
            status = await dav.put_new_stream(client, CREDS, "/Docs/a.pdf", chunks(b"ab", b"cd"))
    assert status == 201
    request = route.calls.last.request
    assert request.headers["If-None-Match"] == "*"
    assert request.content == b"abcd"


async def test_put_new_stream_returns_the_refusal_status():
    with respx.mock:
        respx.put(f"{ROOT}/Docs/a.pdf").mock(return_value=httpx.Response(412))
        async with httpx.AsyncClient() as client:
            assert await dav.put_new_stream(client, CREDS, "/Docs/a.pdf", chunks(b"x")) == 412
```

- [ ] **Step 2: Eseguire e vedere fallire**

Run: `uv run pytest tests/unit/test_olivia_dav_upload.py -v`
Expected: FAIL con `AttributeError` (funzioni assenti).

- [ ] **Step 3: Implementare in `dav.py`**

```python
#: A whole upload may take long on a slow link; the write of each chunk and the answer after
#: the last one get generous limits (fork olivia, upload links). nginx and HaRP allow 1800 s.
UPLOAD_TIMEOUT = httpx.Timeout(1800.0, connect=30.0)


async def ensure_folders(client: httpx.AsyncClient, creds: Credentials, folder: str) -> int | None:
    """MKCOL every folder of ``folder`` from the top down (fork olivia, upload links).

    201 created and 405 already there both count as present. The first other status is
    returned so the caller can map it; ``None`` means every folder exists now.
    """
    target = safe_path(folder)
    current = ""
    for part in (p for p in target.split("/") if p):
        current = f"{current}/{part}"
        response = await client.request("MKCOL", files_url(creds, current), auth=creds.auth())
        if response.status_code not in (201, 405):
            return response.status_code
    return None


async def put_new_stream(
    client: httpx.AsyncClient, creds: Credentials, path: str, body: AsyncIterator[bytes]
) -> int:
    """PUT a streamed body to a file that must not exist yet, and return the status.

    ``If-None-Match: *`` makes Nextcloud refuse with 412 when anything exists at the path, so
    a file created between the link and the upload is never replaced. No Content-Length is
    needed: Nextcloud accepts a chunked PUT (verified 2026-09-30) and writes a part file
    that only becomes the target when the transfer completes.
    """
    target = safe_path(path)
    response = await client.put(
        files_url(creds, target),
        content=body,
        headers={"If-None-Match": "*"},
        auth=creds.auth(),
        timeout=UPLOAD_TIMEOUT,
    )
    return response.status_code
```
(Importare `AsyncIterator` da `collections.abc` se manca. `safe_path` di una cartella: se rifiuta il formato senza estensione, usare lo stesso controllo che usa `files_list`.)

- [ ] **Step 4: Eseguire, lint e commit**

Run: `uv run pytest tests/unit/test_olivia_dav_upload.py -v && uv run pytest tests/unit tests/contract` poi i lint.
Expected: PASS. Se il contract test dei verbi distruttivi obietta a `MKCOL` fuori dalla riga già esentata, riportarlo nel report e aggiungere un'eccezione stretta sul modello di `CHUNK_ASSEMBLY_MOVE` (riga esatta, solo `dav.py`, con controprova).
```bash
git add src/mcp_connector/nextcloud/clients/dav.py tests/unit/test_olivia_dav_upload.py vulture_whitelist.py
git commit -m "feat(olivia): WebDAV folder creation and streamed create-only PUT"
```

---

### Task 3: Rotta pubblica `PUT /ul/{token}`

**Files:**
- Create: `src/mcp_connector/downloads/upload_route.py`
- Modify: `src/mcp_connector/downloads/route.py` (rinominare `_credentials` in `rebuild_credentials` e usarla; `/dl` rifiuta i biglietti `upload:`)
- Test: `tests/unit/test_olivia_upload_route.py`, `tests/unit/test_olivia_download_route.py` (un test in più)

**Interfaces:**
- Consumes: Task 1 (`parse_upload_path`, `MAX_UPLOAD_BYTES`), Task 2 (`ensure_folders`, `put_new_stream`), `route.TOKEN_PATTERN`, `route._not_found`, `route._masked`, `TicketStore.claim/finish/release`, `shared_client()`.
- Produces: `route.rebuild_credentials(env, oauth_store, ticket) -> Credentials | None` (ex `_credentials`); `upload_route.UPLOAD_PATH = "/ul/{token}"`; `upload_route.upload_routes(env, *, oauth_store, tickets=None) -> list[Route]`.

Mappatura degli esiti (dalla spec §4.2):

| Situazione | Risposta | Biglietto |
|---|---|---|
| token malformato / biglietto non valido / non `upload:` / credenziali non ricostruibili | 404 `Not found` | rilasciato se era stato preso |
| `Content-Length` dichiarato > 100 MB | 413 `{"error":"too_large","max_bytes":…}` | non preso |
| corpo reale > 100 MB | 413 | rilasciato |
| `MKCOL` 401/403 · PUT 401/403 | 404 | bruciato (`finish`) |
| `MKCOL` 409 · PUT 404/409 | 409 `{"error":"conflict","path":…}` | bruciato |
| PUT 412/405 | 409 `{"error":"exists","path":…}` | bruciato |
| PUT 200/204 (precondizione ignorata) | 502 `{"error":"precondition_ignored"}` + log di errore | bruciato |
| PUT 413 | 413 | rilasciato |
| altri stati, 5xx, `httpx.HTTPError` | 502 `Bad gateway` | rilasciato |
| `ClientDisconnect` | 400 | rilasciato |
| PUT 201 | 201 `{"path":…,"size":<byte ricevuti>}` | usato (`finish`) + log `upload stored` |

- [ ] **Step 1: Test che falliscono**

```python
# tests/unit/test_olivia_upload_route.py
import asyncio

import httpx
import pytest
import respx
from starlette.applications import Starlette
from starlette.testclient import TestClient

from mcp_connector import config
from mcp_connector.downloads import store as dl_store
from mcp_connector.downloads import upload
from mcp_connector.downloads import upload_route
from mcp_connector.oauth import store as oauth_store_module

BASE = "http://nc.test"
KEY = bytes(range(32))
ENV = {
    config.ENV_APP_ID: "mcp_connector",
    config.ENV_APP_SECRET: "app-secret-test",
    config.ENV_APP_VERSION: "0.3.2",
    config.ENV_NEXTCLOUD_URL: BASE,
}
ROOT = f"{BASE}/remote.php/dav/files/alice"
TARGET = "/Clienti/Rossi/Preventivo à #1.docx"
FILE_URL = f"{ROOT}/Clienti/Rossi/Preventivo%20%C3%A0%20%231.docx"


def run(work):
    return asyncio.run(work)


@pytest.fixture
def world(tmp_path):
    oauth = oauth_store_module.OAuthStore(tmp_path / oauth_store_module.STORE_FILENAME, KEY)
    run(oauth.save_client("client-1", metadata_json='{"client_id": "client-1"}'))
    run(
        oauth.create_authorization(
            "auth-1",
            client_id="client-1",
            nc_user="alice",
            nc_account_id="alice",
            app_password="app-password-test",
            scopes="nextcloud",
            resource="https://nc.example/exapps/x/mcp",
        )
    )
    tickets = dl_store.TicketStore(tmp_path / dl_store.TICKETS_FILENAME)

    async def provider():
        return oauth

    app = Starlette(routes=upload_route.upload_routes(ENV, oauth_store=provider, tickets=tickets))
    return oauth, tickets, TestClient(app)


def issue(tickets, path=TARGET):
    token, _ = run(
        tickets.issue(
            auth_id="auth-1", nc_user="alice", path=upload.upload_ticket_path(path),
            name=path.rsplit("/", 1)[-1], content_type="", size=0, ttl_seconds=1800,
        )
    )
    return token


def folders_ok():
    respx.route(method="MKCOL", url__startswith=ROOT).mock(return_value=httpx.Response(405))


def test_a_completed_upload_creates_the_file_and_burns_the_link(world):
    _, tickets, client = world
    token = issue(tickets)
    with respx.mock:
        folders_ok()
        put = respx.put(FILE_URL).mock(return_value=httpx.Response(201))
        answer = client.put(f"/ul/{token}", content=b"x" * 1000)
    assert answer.status_code == 201
    assert answer.json() == {"path": TARGET, "size": 1000}
    assert put.calls.last.request.headers["If-None-Match"] == "*"
    assert run(tickets.peek(token)) is None
    again = client.put(f"/ul/{token}", content=b"x")
    assert (again.status_code, again.text) == (404, "Not found")


def test_unknown_malformed_and_download_tickets_get_the_same_404(world):
    _, tickets, client = world
    dl_token, _ = run(tickets.issue(auth_id="auth-1", nc_user="alice", path="/Docs/a.pdf",
                                    name="a.pdf", content_type="application/pdf", size=1, ttl_seconds=600))
    for path in ("/ul/" + "A" * 43, "/ul/short", f"/ul/{dl_token}"):
        answer = client.put(path, content=b"x")
        assert (answer.status_code, answer.text) == (404, "Not found")
    assert run(tickets.peek(dl_token)) is not None


def test_a_file_that_appeared_meanwhile_is_409_exists_and_burns(world):
    _, tickets, client = world
    token = issue(tickets)
    with respx.mock:
        folders_ok()
        respx.put(FILE_URL).mock(return_value=httpx.Response(412))
        answer = client.put(f"/ul/{token}", content=b"x")
    assert answer.status_code == 409
    assert answer.json()["error"] == "exists"
    assert run(tickets.peek(token)) is None


def test_a_folder_that_is_a_file_is_409_conflict(world):
    _, tickets, client = world
    token = issue(tickets)
    with respx.mock:
        folders_ok()
        respx.put(FILE_URL).mock(return_value=httpx.Response(409))
        answer = client.put(f"/ul/{token}", content=b"x")
    assert answer.status_code == 409
    assert answer.json()["error"] == "conflict"


def test_declared_size_over_the_limit_is_413_before_claiming(world):
    _, tickets, client = world
    token = issue(tickets)
    answer = client.put(f"/ul/{token}", content=b"x", headers={"Content-Length": str(upload.MAX_UPLOAD_BYTES + 1)})
    assert answer.status_code == 413
    assert run(tickets.peek(token)) is not None


def test_real_size_over_the_limit_is_413_and_releases(world, monkeypatch):
    _, tickets, client = world
    monkeypatch.setattr(upload_route, "MAX_UPLOAD_BYTES", 5)
    token = issue(tickets)

    def body():
        yield b"123"
        yield b"456"

    with respx.mock:
        folders_ok()

        async def consume(request):
            await request.aread()
            return httpx.Response(201)

        respx.put(FILE_URL).mock(side_effect=consume)
        answer = client.put(f"/ul/{token}", content=body())
    assert answer.status_code == 413
    assert run(tickets.peek(token)) is not None


def test_nextcloud_down_is_502_and_releases(world):
    _, tickets, client = world
    token = issue(tickets)
    with respx.mock:
        folders_ok()
        respx.put(FILE_URL).mock(side_effect=httpx.ConnectError("down"))
        answer = client.put(f"/ul/{token}", content=b"x")
    assert answer.status_code == 502
    assert run(tickets.peek(token)) is not None


def test_rejected_credentials_are_404_and_burn(world):
    _, tickets, client = world
    token = issue(tickets)
    with respx.mock:
        respx.route(method="MKCOL", url__startswith=ROOT).mock(return_value=httpx.Response(401))
        answer = client.put(f"/ul/{token}", content=b"x")
    assert (answer.status_code, answer.text) == (404, "Not found")
    assert run(tickets.peek(token)) is None


def test_revoked_connection_is_404(world):
    oauth, tickets, client = world
    token = issue(tickets)
    run(oauth.revoke_authorization("auth-1"))
    answer = client.put(f"/ul/{token}", content=b"x")
    assert (answer.status_code, answer.text) == (404, "Not found")


def test_the_log_masks_the_token(world, caplog):
    _, tickets, client = world
    token = issue(tickets)
    with respx.mock, caplog.at_level("INFO"):
        folders_ok()
        respx.put(FILE_URL).mock(return_value=httpx.Response(201))
        client.put(f"/ul/{token}", content=b"x")
    assert f"link={token[:4]}…" in caplog.text
    assert token not in caplog.text
```
```python
def test_a_client_that_disconnects_mid_upload_leaves_the_link_usable(world):
    _, tickets, client = world
    token = issue(tickets)
    messages = [
        {"type": "http.request", "body": b"abc", "more_body": True},
        {"type": "http.disconnect"},
    ]
    sent = []

    async def receive():
        return messages.pop(0) if messages else {"type": "http.disconnect"}

    async def send(message):
        sent.append(message)

    scope = {
        "type": "http", "asgi": {"version": "3.0", "spec_version": "2.3"}, "http_version": "1.1",
        "method": "PUT", "scheme": "http", "path": f"/ul/{token}", "raw_path": f"/ul/{token}".encode(),
        "query_string": b"", "root_path": "", "headers": [],
        "server": ("test", 80), "client": ("1.2.3.4", 5),
    }
    with respx.mock:
        folders_ok()

        async def consume(request):
            await request.aread()
            return httpx.Response(201)

        respx.put(FILE_URL).mock(side_effect=consume)
        run(client.app(scope, receive, send))
    assert sent[0]["status"] in (400, 502)
    assert run(tickets.peek(token)) is not None
```
(Se httpx avvolge `ClientDisconnect` in un proprio errore, la rotta risponde 502 attraverso il ramo `httpx.HTTPError`: per il test vale lo stesso, perché conta che il biglietto torni utilizzabile.) Controllare la firma reale di `revoke_authorization` in `tests/unit/test_oauth_store.py` e adattare solo la chiamata.

In `tests/unit/test_olivia_download_route.py` aggiungere: un biglietto `upload:/Docs/a.pdf` su `GET /dl/<token>` e `HEAD /dl/<token>` → 404 `Not found`, biglietto ancora utilizzabile.

- [ ] **Step 2: Eseguire e vedere fallire**

Run: `uv run pytest tests/unit/test_olivia_upload_route.py -v`
Expected: FAIL (`upload_route` assente).

- [ ] **Step 3: Implementare**

In `route.py`: rinominare `_credentials` → `rebuild_credentials` (tutte le occorrenze, docstring di una riga "shared by the download and the upload route"); in GET e HEAD, subito dopo aver preso/letto il biglietto, se `ticket.path.startswith(upload.UPLOAD_PREFIX)` → per GET `await store.release(token)` e `_not_found()`, per HEAD `_not_found()`.

```python
# src/mcp_connector/downloads/upload_route.py
"""The public ``/ul/{token}`` route: one create-only upload, with the rights of its issuer.

Twin of ``/dl/{token}`` (fork olivia): every unusable link gets the same 404, the credentials
are rebuilt from the connection that issued the link, and the body is streamed to Nextcloud
without a copy on disk. The ticket is spent by a completed upload or by an answer that a
retry could not change (the file exists, the credential is rejected); a transport failure or
an interrupted client puts it back so the same link can be tried again until it expires.
"""

import logging
from collections.abc import AsyncIterator, Mapping

import httpx
from starlette.requests import ClientDisconnect, Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from ..nextcloud.clients import dav
from ..nextcloud.http import shared_client
from ..oauth.store import StoreProvider
from .route import TOKEN_PATTERN, _bad_gateway, _masked, _not_found, rebuild_credentials
from .store import TicketStore, ticket_store
from .upload import MAX_UPLOAD_BYTES, parse_upload_path

logger = logging.getLogger(__name__)

UPLOAD_PATH = "/ul/{token}"


class _TooLarge(Exception):
    """The streamed body passed :data:`MAX_UPLOAD_BYTES`."""


def _json(status: int, payload: dict[str, object]) -> Response:
    return JSONResponse(payload, status_code=status, headers={"Cache-Control": "no-store"})


def _too_large() -> Response:
    return _json(413, {"error": "too_large", "max_bytes": MAX_UPLOAD_BYTES})


def upload_routes(
    env: Mapping[str, str] | None, *, oauth_store: StoreProvider, tickets: TicketStore | None = None
) -> list[Route]:
    async def upload(request: Request) -> Response:
        token = str(request.path_params.get("token", ""))
        if not TOKEN_PATTERN.fullmatch(token):
            return _not_found()
        declared = request.headers.get("content-length", "")
        if declared.isdigit() and int(declared) > MAX_UPLOAD_BYTES:
            return _too_large()
        store = tickets if tickets is not None else ticket_store(env)
        ticket = await store.claim(token)
        if ticket is None:
            return _not_found()
        try:
            target = parse_upload_path(ticket.path)
            creds = None if target is None else await rebuild_credentials(env, oauth_store, ticket)
            if target is None or creds is None:
                await store.release(token)
                return _not_found()

            received = 0

            async def body() -> AsyncIterator[bytes]:
                nonlocal received
                async for chunk in request.stream():
                    received += len(chunk)
                    if received > MAX_UPLOAD_BYTES:
                        raise _TooLarge
                    yield chunk

            try:
                folder = target.rsplit("/", 1)[0]
                failed = await dav.ensure_folders(shared_client(), creds, folder) if folder else None
                status = (
                    failed
                    if failed is not None
                    else await dav.put_new_stream(shared_client(), creds, target, body())
                )
            except _TooLarge:
                await store.release(token)
                return _too_large()
            except ClientDisconnect:
                await store.release(token)
                return Response(status_code=400)
            except httpx.HTTPError:
                await store.release(token)
                return _bad_gateway()

            if status == 201:
                await store.finish(token)
                logger.info(
                    "upload stored: user=%s path=%r bytes=%s link=%s",
                    ticket.nc_user, target, received, _masked(token),
                )
                return _json(201, {"path": target, "size": received})
            if status in (401, 403):
                await store.finish(token)
                return _not_found()
            if status in (405, 412):
                await store.finish(token)
                return _json(409, {"error": "exists", "path": target})
            if status in (404, 409):
                await store.finish(token)
                return _json(409, {"error": "conflict", "path": target})
            if status in (200, 204):
                await store.finish(token)
                logger.error("upload of %r replaced a file: this instance ignored If-None-Match", target)
                return _json(502, {"error": "precondition_ignored"})
            await store.release(token)
            return _too_large() if status == 413 else _bad_gateway()
        except BaseException:
            await store.release(token)
            raise

    return [Route(UPLOAD_PATH, upload, methods=["PUT"])]
```
Nota: `MKCOL` 405 è "cartella già presente" dentro `ensure_folders`; lo stato 405 della tabella riguarda solo il PUT. `release` dopo un `finish`/`release` è innocuo (lo store aggiorna solo le righe `in_progress`). Importare `_bad_gateway` da `route.py` (esiste già). Se pyright rifiuta l'importazione di nomi privati, rinominarli pubblici in `route.py` (`not_found`, `bad_gateway`, `masked`) aggiornando i chiamanti.

- [ ] **Step 4: Eseguire, lint e commit**

Run: `uv run pytest tests/unit/test_olivia_upload_route.py tests/unit/test_olivia_download_route.py -v && uv run pytest tests/unit tests/contract` poi i lint.
Expected: PASS.
```bash
git add src/mcp_connector/downloads/upload_route.py src/mcp_connector/downloads/route.py tests/unit/test_olivia_upload_route.py tests/unit/test_olivia_download_route.py vulture_whitelist.py
git commit -m "feat(olivia): public single-use upload route"
```

---

### Task 4: Cablaggio della rotta `/ul` (manifest, avvio, log)

**Files:**
- Modify: `src/mcp_connector/entry_exapp.py` (accanto a `*download_routes(env, oauth_store=store),` ~riga 381)
- Modify: `appinfo/info.xml` (nuova `<route>` dopo quella di `/dl`, commento "Exactly fourteen routes" → quindici)
- Modify: `scripts/bootstrap_exapp.sh` (JSON delle rotte, ~riga 1217)
- Modify: `src/mcp_connector/downloads/logs.py` (maschera anche `/ul/`)
- Modify (valori congelati): `tests/unit/test_exapp_env_setup.py` (`DECLARED_ROUTES = 15`, elenco atteso con `("^/ul/[A-Za-z0-9_-]{20,128}$", "PUBLIC")`, nomi/testi "fourteen" → "fifteen"), `tests/unit/test_exapp_audit_verify.py` e `tests/unit/test_exapp_purge.py` (`len(urls) == 15`), `tests/unit/test_oauth_connect.py` (test di cablaggio: `UPLOAD_PATH` nell'app ExApp e non in quella HTTP), `tests/unit/test_olivia_download_logs.py` (test `/ul/`)

**Interfaces:**
- Consumes: `upload_route.upload_routes`, `upload_route.UPLOAD_PATH`.
- Produces: rotta `/ul/{token}` montata e dichiarata PUBLIC con verbo `PUT`.

- [ ] **Step 1: Test che falliscono**

```python
# in tests/unit/test_olivia_download_logs.py
def test_upload_token_is_masked():
    item = record("/ul/AbCdEfGhIjKlMnOpQrStUvWxYz0123456789_-abcd")
    logs.RedactDownloadToken().filter(item)
    assert isinstance(item.args, tuple)
    assert item.args[2] == "/ul/AbCd…"
```
```python
# in tests/unit/test_oauth_connect.py, accanto al test di cablaggio di DOWNLOAD_PATH
def test_the_upload_route_is_mounted_in_the_exapp_only() -> None:
    from mcp_connector.downloads import upload_route

    exapp = {getattr(route, "path", "") for route in build_exapp_app(ENV).router.routes}
    standalone = {getattr(route, "path", "") for route in entry_http.build_app({}).router.routes}
    assert upload_route.UPLOAD_PATH in exapp
    assert upload_route.UPLOAD_PATH not in standalone
```
Più gli aggiornamenti dei valori congelati elencati sopra (lista delle rotte con la voce `/ul`, conteggi 15).

- [ ] **Step 2: Eseguire e vedere fallire**

Run: `uv run pytest tests/unit/test_olivia_download_logs.py tests/unit/test_oauth_connect.py tests/unit/test_exapp_env_setup.py -v`
Expected: FAIL sui test nuovi e sui conteggi.

- [ ] **Step 3: Implementare**

- `logs.py`: `_PREFIXES = ("/dl/", "/ul/")`; nel filtro, per il primo prefisso con cui inizia il percorso, `record.args = (*args[:2], f"{prefix}{token[:4]}…", *args[3:])`; docstring aggiornata ("download and upload tokens").
- `entry_exapp.py`: `from .downloads.upload_route import upload_routes` e `*upload_routes(env, oauth_store=store),` subito dopo `*download_routes(...)`.
- `info.xml`, dopo la rotta `/dl`:
```xml
			<route>
				<url>^/ul/[A-Za-z0-9_-]{20,128}$</url>
				<verb>PUT</verb>
				<access_level>PUBLIC</access_level>
				<headers_to_exclude>["AUTHORIZATION-APP-API","EX-APP-ID","EX-APP-VERSION","AA-VERSION","X-ORIGIN-IP"]</headers_to_exclude>
			</route>
```
  e nel commento: "Exactly fifteen routes"; una riga per la quindicesima: "the single-use upload route at /ul/{token}, PUT only, with the same 404 for every unusable token". Non scrivere nomi di elementi XML con le parentesi angolari nei commenti.
- `bootstrap_exapp.sh`: nel JSON aggiungere dopo la voce `/dl` `{"url":"^/ul/[A-Za-z0-9_-]{20,128}$","verb":"PUT","access_level":0,"headers_to_exclude":${EXCLUDED_HEADERS}}`.

- [ ] **Step 4: Eseguire, lint e commit**

Run: `uv run pytest tests/unit tests/contract` poi i lint.
Expected: PASS (salvo il baseline noto).
```bash
git add src/mcp_connector/entry_exapp.py appinfo/info.xml scripts/bootstrap_exapp.sh src/mcp_connector/downloads/logs.py tests/unit/test_exapp_env_setup.py tests/unit/test_exapp_audit_verify.py tests/unit/test_exapp_purge.py tests/unit/test_oauth_connect.py tests/unit/test_olivia_download_logs.py
git commit -m "feat(olivia): declare and mount the upload route, mask its token"
```

---

### Task 5: `files_upload` restituisce il link (via la modalità base64)

**Files:**
- Modify: `src/mcp_connector/server/reg_files.py` (`files_upload`, ~righe 94-163)
- Modify: `src/mcp_connector/tools/files.py` (rimuovere `upload_binary`, `HARD_UPLOAD_CHUNK_BYTES`, `MIN_UPLOAD_CHUNK_BYTES`, `MAX_UPLOAD_CHUNKS`, `_UPLOAD_ID_RE` e ciò che resta senza uso)
- Modify: `src/mcp_connector/nextcloud/clients/dav.py` (rimuovere `uploads_url`, `start_chunked_upload`, `put_upload_chunk`, `finish_chunked_upload`, `_check_chunk_response` se restano senza chiamanti)
- Modify: `tests/unit/test_files_upload.py`, `tests/unit/test_file_transfer_review.py` (togliere solo i test della modalità a pezzi)
- Modify: `tests/contract/test_no_destructive_calls.py` (se la riga `"MOVE",` di `finish_chunked_upload` sparisce, togliere l'eccezione `CHUNK_ASSEMBLY_MOVE` e la sua controprova: `MOVE` torna vietato ovunque)
- Modify: `tests/contract/test_tool_surface.py` (proprietà di `files_upload` esattamente `{"path", "content"}`, required `{"path"}`, descrizione contiene `"never overwrites"` e `"upload_url"`)
- Modify: `src/mcp_connector/audit/allowlist.py` (`"files_upload": frozenset({"path"})`; `content_base64` resta in `FORBIDDEN_PARAMS` solo se il test di superficie dell'audit lo accetta, altrimenti rimuoverlo)
- Modify: `README.md` (riga `files_upload`)
- Test: `tests/unit/test_olivia_files_upload_link.py`

**Interfaces:**
- Consumes: `upload.issue_upload_link`, `deps.resolve_clients`, `deps.resolve_ticket_owner`, `files_tools.upload` (testo, invariato).
- Produces: strumento `files_upload(path: str, content: str | None = None) -> str`.

- [ ] **Step 1: Test che falliscono**

```python
# tests/unit/test_olivia_files_upload_link.py
import json

import pytest

from mcp_connector.deps import TicketOwner
from mcp_connector.server import reg_files

pytestmark = pytest.mark.anyio


def tool():
    return getattr(reg_files.files_upload, "__wrapped__", reg_files.files_upload)


async def test_without_content_the_tool_returns_an_upload_link(monkeypatch):
    seen = {}

    async def fake_issue(clients, owner, path):
        seen.update(owner=owner, path=path)
        return {"upload_url": "https://x/ul/tok", "method": "PUT"}

    monkeypatch.setattr(reg_files.deps, "resolve_clients", lambda ctx: "clients")
    monkeypatch.setattr(reg_files.deps, "resolve_ticket_owner", lambda ctx: TicketOwner("a", "alice"))
    monkeypatch.setattr(reg_files.upload, "issue_upload_link", fake_issue)
    text = await tool()(path="/Docs/new.docx", ctx=None)
    assert json.loads(text) == {"upload_url": "https://x/ul/tok", "method": "PUT"}
    assert seen == {"owner": TicketOwner("a", "alice"), "path": "/Docs/new.docx"}


async def test_with_content_the_text_path_is_unchanged(monkeypatch):
    async def fake_upload(clients, path, content):
        return {"path": path, "created": True}

    monkeypatch.setattr(reg_files.deps, "resolve_clients", lambda ctx: "clients")
    monkeypatch.setattr(reg_files.files_tools, "upload", fake_upload)
    text = await tool()(path="/Docs/n.md", content="ciao", ctx=None)
    assert json.loads(text) == {"path": "/Docs/n.md", "created": True}
```
Aggiornare il contract test di superficie come indicato nei Files.

- [ ] **Step 2: Eseguire e vedere fallire**

Run: `uv run pytest tests/unit/test_olivia_files_upload_link.py tests/contract/test_tool_surface.py -v`
Expected: FAIL.

- [ ] **Step 3: Implementare**

```python
from ..downloads import upload


@mcp.tool(annotations=CREATE_ONLY, structured_output=False)
@graceful
async def files_upload(
    path: Annotated[str, Field(description="New file path; must not exist")],
    content: Annotated[
        str | None,
        Field(description="UTF-8 text to write now; omit to get an upload_url for any file"),
    ] = None,
    ctx: Context | None = None,
) -> str:
    """Create a new file; never overwrites. Text: pass content. Any other file: omit content,
    then PUT it to upload_url from code execution (curl -T)."""
    clients = deps.resolve_clients(ctx)
    if content is None:
        owner = deps.resolve_ticket_owner(ctx)
        return compact(await upload.issue_upload_link(clients, owner, path))
    return compact(await files_tools.upload(clients, path=path, content=content))
```
Rimuovere il codice e i test della modalità a pezzi elencati nei Files (`grep -rn "upload_binary\|chunked_upload\|upload_chunk\|uploads_url\|UPLOAD_CHUNK\|MAX_UPLOAD_CHUNKS\|_UPLOAD_ID_RE" src tests scripts vulture_whitelist.py` deve restare vuoto, salvo commenti storici). README: `| files_upload | create | New file, never overwrites: text directly, any other file through a single-use upload link |`.

- [ ] **Step 4: Eseguire, budget, lint e commit**

Run: `uv run pytest tests/unit tests/contract && uv run python scripts/check_tool_budget.py` poi i lint.
Expected: PASS; budget sotto 18000.
```bash
git add src/mcp_connector/server/reg_files.py src/mcp_connector/tools/files.py src/mcp_connector/nextcloud/clients/dav.py src/mcp_connector/audit/allowlist.py tests/unit/test_files_upload.py tests/unit/test_file_transfer_review.py tests/unit/test_olivia_files_upload_link.py tests/contract/test_tool_surface.py tests/contract/test_no_destructive_calls.py README.md vulture_whitelist.py
git commit -m "feat(olivia): files_upload hands out an upload link; drop the base64 chunk mode"
```

---

### Task 6: Bozze email – client e logica

**Files:**
- Create: `src/mcp_connector/nextcloud/clients/mail_drafts.py`
- Create: `src/mcp_connector/tools/drafts.py`
- Modify: `tests/contract/test_no_destructive_calls.py` (eccezione di una riga per `DRAFTS_PATH`, con controprova)
- Test: `tests/unit/test_olivia_mail_drafts.py`

**Interfaces:**
- Consumes: `mail_client.get_accounts(client, creds) -> list[dict]` (chiavi `id`, `email`, `aliases` = lista di dict con `email`), `mail_client.get_message(client, creds, id) -> tuple[dict, bool]` (chiavi `to`, `cc`, `from`, `replyTo` = liste di `{"label","email"}`, `messageId`, `subject`), `capabilities.require_app(clients, "mail")`, `dav.safe_path`, `dav.stat` (chiavi `is_collection`, `size`).
- Produces: `mail_drafts.DRAFTS_PATH`, `async mail_drafts.create_draft(client, creds, payload: dict) -> dict`; `drafts.MAX_ATTACHMENTS = 10`, `drafts.MAX_ATTACHMENT_BYTES = 26214400`, `drafts.DRAFT_NOTE: str`, `drafts.parse_recipients(values: Sequence[str]) -> list[dict[str, str]]`, `drafts.reply_subject(subject: str) -> str`, `async drafts.create(clients, *, to=None, cc=None, bcc=None, subject="", body="", account="", reply_to="", attachments=None) -> dict[str, Any]`.

- [ ] **Step 1: Test che falliscono**

```python
# tests/unit/test_olivia_mail_drafts.py
import json

import httpx
import pytest
import respx

from mcp_connector.errors import ToolError
from mcp_connector.nextcloud import NcClients
from mcp_connector.nextcloud.clients import mail_drafts
from mcp_connector.nextcloud.credentials import Credentials
from mcp_connector.tools import drafts

pytestmark = pytest.mark.anyio
BASE = "http://nc.test"
DRAFTS_URL = f"{BASE}/index.php/apps/mail/api/drafts"
ACCOUNTS = [
    {"id": 2, "email": "drosera@abnet.it", "aliases": []},
    {"id": 3, "email": "alessandro.drosera@gmail.com", "aliases": [{"email": "ale@drosera.info"}]},
]
ORIGINAL = {
    "subject": "cauzioni",
    "messageId": "<abc@belloni>",
    "from": [{"label": "Elena", "email": "elena@belloni.it"}],
    "replyTo": [{"label": "Elena Studio", "email": "studio@belloni.it"}],
    "to": [{"label": "Ale", "email": "Alessandro.Drosera@gmail.com"}],
    "cc": [],
}


@pytest.fixture
def clients(monkeypatch):
    async def fake_require(clients, app):
        return None

    async def fake_accounts(client, creds):
        return ACCOUNTS

    async def fake_message(client, creds, message_id):
        assert str(message_id) == "140813"
        return ORIGINAL, False

    monkeypatch.setattr(drafts.capabilities, "require_app", fake_require)
    monkeypatch.setattr(drafts.mail_client, "get_accounts", fake_accounts)
    monkeypatch.setattr(drafts.mail_client, "get_message", fake_message)
    return NcClients(client=httpx.AsyncClient(), creds=Credentials(BASE, "alice", "pw"))


def created(attachments=()):
    return httpx.Response(201, json={"status": "success", "data": {
        "id": 7, "attachments": [{"fileName": name} for name in attachments]}})


def test_recipients_with_commas_and_quotes():
    assert drafts.parse_recipients(['"Rossi, Mario" <m@x.it>', "anna@y.it"]) == [
        {"label": "Rossi, Mario", "email": "m@x.it"},
        {"label": "anna@y.it", "email": "anna@y.it"},
    ]
    with pytest.raises(ToolError):
        drafts.parse_recipients(["not an address"])


def test_reply_subject_does_not_stack_prefixes():
    assert drafts.reply_subject("cauzioni") == "Re: cauzioni"
    assert drafts.reply_subject("RE: cauzioni") == "RE: cauzioni"
    assert drafts.reply_subject("R: cauzioni") == "R: cauzioni"


async def test_a_new_draft_with_two_accounts_needs_an_account(clients):
    with pytest.raises(ToolError, match="drosera@abnet.it"):
        await drafts.create(clients, to=["a@b.it"], subject="s", body="b")


async def test_a_new_draft_is_posted_with_the_exact_payload(clients):
    with respx.mock:
        route = respx.post(DRAFTS_URL).mock(return_value=created())
        result = await drafts.create(clients, to=["Anna <a@b.it>"], subject="Ciao", body="Testo",
                                     account="alessandro.drosera@gmail.com")
    request = route.calls.last.request
    assert request.headers["OCS-APIRequest"] == "true"
    payload = json.loads(request.content)
    assert payload["accountId"] == 3
    assert payload["to"] == [{"label": "Anna", "email": "a@b.it"}]
    assert payload["bodyPlain"] == "Testo"
    assert payload["isHtml"] is False
    assert payload["inReplyToMessageId"] is None
    assert "sendAt" not in payload
    assert result["draft_id"] == 7
    assert result["note"] == drafts.DRAFT_NOTE


async def test_a_reply_takes_account_recipient_subject_and_thread_from_the_original(clients):
    with respx.mock:
        route = respx.post(DRAFTS_URL).mock(return_value=created())
        await drafts.create(clients, reply_to="mail:140813", body="Grazie")
    payload = json.loads(route.calls.last.request.content)
    assert payload["accountId"] == 3
    assert payload["to"] == [{"label": "Elena Studio", "email": "studio@belloni.it"}]
    assert payload["subject"] == "Re: cauzioni"
    assert payload["inReplyToMessageId"] == "<abc@belloni>"


async def test_a_reply_with_no_account_among_the_recipients_is_refused(clients, monkeypatch):
    async def bcc_message(client, creds, message_id):
        return {**ORIGINAL, "to": [{"label": "L", "email": "list@x.it"}]}, False

    monkeypatch.setattr(drafts.mail_client, "get_message", bcc_message)
    with pytest.raises(ToolError, match="account"):
        await drafts.create(clients, reply_to="mail:140813", body="x")


async def test_attachments_are_checked_before_the_draft(clients, monkeypatch):
    async def fake_stat(client, creds, path):
        if path == "/Docs/missing.pdf":
            raise ToolError(message="File not found", hint="h", reason="unknown_id")
        return {"is_collection": path == "/Docs", "size": 10}

    monkeypatch.setattr(drafts.dav, "stat", fake_stat)
    for bad in (["/Docs/missing.pdf"], ["/Docs"], [f"/Docs/{i}.pdf" for i in range(11)]):
        with respx.mock:
            route = respx.post(DRAFTS_URL).mock(return_value=created())
            with pytest.raises(ToolError):
                await drafts.create(clients, to=["a@b.it"], subject="s", body="b", account="3",
                                    attachments=bad)
        assert not route.called


async def test_attachments_over_25_mb_are_refused(clients, monkeypatch):
    async def big(client, creds, path):
        return {"is_collection": False, "size": 20 * 1024 * 1024}

    monkeypatch.setattr(drafts.dav, "stat", big)
    with pytest.raises(ToolError, match="25"):
        await drafts.create(clients, to=["a@b.it"], subject="s", body="b", account="3",
                            attachments=["/a.pdf", "/b.pdf"])


async def test_attachments_are_sent_as_cloud_files_and_missing_ones_reported(clients, monkeypatch):
    async def ok(client, creds, path):
        return {"is_collection": False, "size": 10}

    monkeypatch.setattr(drafts.dav, "stat", ok)
    with respx.mock:
        route = respx.post(DRAFTS_URL).mock(return_value=created(["a.pdf"]))
        result = await drafts.create(clients, to=["a@b.it"], subject="s", body="b", account="3",
                                     attachments=["/Docs/a.pdf", "/Docs/b.pdf"])
    payload = json.loads(route.calls.last.request.content)
    assert payload["attachments"] == [
        {"type": "cloud", "fileName": "/Docs/a.pdf"},
        {"type": "cloud", "fileName": "/Docs/b.pdf"},
    ]
    assert result["attachments"] == ["a.pdf"]
    assert result["missing_attachments"] == ["b.pdf"]


async def test_only_the_drafts_route_is_ever_called(clients):
    with respx.mock(assert_all_called=False) as mock:
        respx.post(DRAFTS_URL).mock(return_value=created())
        await drafts.create(clients, to=["a@b.it"], subject="s", body="b", account="2")
    assert [str(call.request.url) for call in mock.calls] == [DRAFTS_URL]
```
Nel contract test aggiungere le controprove dell'eccezione `DRAFTS_PATH` (stesso schema di quella degli allegati: riga esatta solo in `nextcloud/clients/mail_drafts.py`; la stessa riga altrove e un'altra riga con `/api/drafts` nello stesso file restano vietate; `/api/outbox` e `/message/send` restano vietati anche lì).

- [ ] **Step 2: Eseguire e vedere fallire**

Run: `uv run pytest tests/unit/test_olivia_mail_drafts.py -v`
Expected: FAIL (`drafts` assente).

- [ ] **Step 3: Implementare**

```python
# src/mcp_connector/nextcloud/clients/mail_drafts.py
"""Create one draft in Nextcloud Mail (fork olivia). Never sends, never changes, never deletes.

Mail 5.12.2 declares no API for drafts: its openapi.json has reads and ``message/send`` only.
This module uses the route Mail's own composer uses, verified live on 2026-09-30: it stores a
local draft (201 with its id) that Mail's DraftsJob appends to the account's Drafts folder
over IMAP after about five minutes, with a null transport, so nothing is ever sent. Without
the ``OCS-APIRequest`` header Nextcloud refuses the request with 412 (CSRF check failed).
"""

from typing import Any

import httpx

from ...errors import ToolError
from ..credentials import Credentials

DRAFTS_PATH = "/index.php/apps/mail/api/drafts"


async def create_draft(
    client: httpx.AsyncClient, creds: Credentials, payload: dict[str, Any]
) -> dict[str, Any]:
    """POST one draft and return the draft Mail stored."""
    response = await client.post(
        f"{creds.base_url}{DRAFTS_PATH}",
        json=payload,
        auth=creds.auth(),
        headers={"OCS-APIRequest": "true", "Accept": "application/json"},
    )
    if response.status_code != 201:
        raise ToolError(
            message=f"The Mail app refused the draft (status {response.status_code}).",
            hint="Check the account in Nextcloud Mail and retry once.",
        )
    data = response.json().get("data")
    if not isinstance(data, dict):
        raise ToolError(
            message="The Mail app answered without the stored draft.",
            hint="Open Nextcloud Mail to check whether the draft is there.",
        )
    return data
```
(Adattare gli import relativi a quelli degli altri moduli in `nextcloud/clients/`.)

```python
# src/mcp_connector/tools/drafts.py
"""Drafts in Nextcloud Mail, new or replies, with Nextcloud files attached (fork olivia)."""

import re
from collections.abc import Sequence
from email.utils import getaddresses
from typing import Any

from ..errors import ToolError
from ..nextcloud import NcClients, capabilities
from ..nextcloud.clients import dav
from ..nextcloud.clients import mail as mail_client
from ..nextcloud.clients import mail_drafts

APP = "mail"
MAX_ATTACHMENTS = 10
MAX_ATTACHMENT_BYTES = 25 * 1024 * 1024
DRAFT_NOTE = (
    "Saved as a draft in Nextcloud Mail and never sent by this server. It moves to the "
    "account's Drafts folder within about 10 minutes; a reply keeps its link to the original "
    "only until then."
)
_REPLY_PREFIX = re.compile(r"^\s*(re|r|aw|sv|fwd?|i|inoltro)\s*:", re.IGNORECASE)
_MAIL_ID = re.compile(r"mail:([0-9]+)")


def parse_recipients(values: Sequence[str]) -> list[dict[str, str]]:
    result = []
    for label, email in getaddresses(list(values)):
        if "@" not in email:
            raise ToolError(
                message=f"{email or label!r} is not an email address.",
                hint="Write recipients as name@example.com or Name <name@example.com>.",
            )
        result.append({"label": label or email, "email": email})
    return result


def reply_subject(subject: str) -> str:
    return subject if _REPLY_PREFIX.match(subject or "") else f"Re: {subject}"


def _emails(account: dict[str, Any]) -> set[str]:
    found = {str(account.get("email") or "").lower()}
    found.update(str(alias.get("email") or "").lower() for alias in account.get("aliases") or [])
    return found - {""}


def _listing(accounts: list[dict[str, Any]]) -> str:
    return ", ".join(f"{a.get('id')}: {a.get('email')}" for a in accounts)


def _pick(accounts: list[dict[str, Any]], wanted: str) -> dict[str, Any]:
    key = wanted.strip().lower()
    for account in accounts:
        if key == str(account.get("id")) or key in _emails(account):
            return account
    raise ToolError(
        message=f"No mail account matches {wanted!r}.",
        hint=f"Use one of: {_listing(accounts)}.",
    )


def _account_of(accounts: list[dict[str, Any]], original: dict[str, Any]) -> dict[str, Any]:
    addressed = {
        str(r.get("email") or "").lower() for r in (original.get("to") or []) + (original.get("cc") or [])
    }
    matches = [a for a in accounts if _emails(a) & addressed]
    if len(matches) != 1:
        raise ToolError(
            message="The account this mail was addressed to cannot be told apart.",
            hint=f"Pass account with one of: {_listing(accounts)}.",
        )
    return matches[0]


async def _checked_attachments(clients: NcClients, paths: Sequence[str]) -> list[str]:
    if len(paths) > MAX_ATTACHMENTS:
        raise ToolError(
            message=f"{len(paths)} attachments; at most {MAX_ATTACHMENTS} are allowed.",
            hint="Attach fewer files or share a folder link instead.",
        )
    targets, total = [], 0
    for path in paths:
        target = dav.safe_path(path)
        try:
            info = await dav.stat(clients.client, clients.creds, target)
        except ToolError as exc:
            raise ToolError(message=f"Attachment {target} cannot be read: {exc.message}", hint=exc.hint) from exc
        if info["is_collection"]:
            raise ToolError(message=f"Attachment {target} is a folder.", hint="Attach files, not folders.")
        total += int(info["size"] or 0)
        targets.append(target)
    if total > MAX_ATTACHMENT_BYTES:
        raise ToolError(
            message=f"The attachments total {total} bytes; the limit is 25 MB.",
            hint="Attach fewer or smaller files.",
        )
    return targets


async def create(
    clients: NcClients,
    *,
    to: Sequence[str] | None = None,
    cc: Sequence[str] | None = None,
    bcc: Sequence[str] | None = None,
    subject: str = "",
    body: str = "",
    account: str = "",
    reply_to: str = "",
    attachments: Sequence[str] | None = None,
) -> dict[str, Any]:
    await capabilities.require_app(clients, APP)
    accounts = await mail_client.get_accounts(clients.client, clients.creds)
    original: dict[str, Any] | None = None
    if reply_to:
        match = _MAIL_ID.fullmatch(reply_to.strip())
        if match is None:
            raise ToolError(message=f"{reply_to!r} is not a mail id.", hint="Use the mail:<n> id from search or mail_browse.")
        original, _ = await mail_client.get_message(clients.client, clients.creds, match.group(1))

    if account:
        chosen = _pick(accounts, account)
    elif original is not None:
        chosen = _account_of(accounts, original)
    elif len(accounts) == 1:
        chosen = accounts[0]
    else:
        raise ToolError(message="Several mail accounts exist.", hint=f"Pass account with one of: {_listing(accounts)}.")

    if to:
        recipients = parse_recipients(to)
    elif original is not None:
        source = original.get("replyTo") or original.get("from") or []
        recipients = [{"label": r.get("label") or r.get("email"), "email": r.get("email")} for r in source]
    else:
        raise ToolError(message="A new draft needs at least one recipient.", hint="Pass to.")
    if not subject and original is not None:
        subject = reply_subject(str(original.get("subject") or ""))
    if not subject:
        raise ToolError(message="A new draft needs a subject.", hint="Pass subject.")

    paths = await _checked_attachments(clients, attachments or [])
    payload: dict[str, Any] = {
        "accountId": chosen["id"],
        "subject": subject,
        "bodyPlain": body,
        "bodyHtml": None,
        "editorBody": None,
        "isHtml": False,
        "smimeSign": False,
        "smimeEncrypt": False,
        "to": recipients,
        "cc": parse_recipients(cc or []),
        "bcc": parse_recipients(bcc or []),
        "attachments": [{"type": "cloud", "fileName": path} for path in paths],
        "aliasId": None,
        "inReplyToMessageId": original.get("messageId") if original is not None else None,
    }
    stored = await mail_drafts.create_draft(clients.client, clients.creds, payload)
    saved = [str(a.get("fileName")) for a in stored.get("attachments") or []]
    wanted = [path.rsplit("/", 1)[-1] for path in paths]
    result: dict[str, Any] = {
        "draft_id": stored.get("id"),
        "account": chosen.get("email"),
        "to": [r["email"] for r in recipients],
        "cc": [r["email"] for r in payload["cc"]],
        "subject": subject,
        "attachments": saved,
        "mail_url": f"{clients.creds.base_url}/index.php/apps/mail/",
        "note": DRAFT_NOTE,
    }
    missing = [name for name in wanted if name not in saved]
    if missing:
        result["missing_attachments"] = missing
    return result
```

- [ ] **Step 4: Eseguire, lint e commit**

Run: `uv run pytest tests/unit/test_olivia_mail_drafts.py tests/contract/test_no_destructive_calls.py -v && uv run pytest tests/unit tests/contract` poi i lint.
Expected: PASS. Se un altro contract test dell'autore vieta `.post(` o percorsi di Mail fuori da `clients/mail.py`, aggiungere un'eccezione stretta con controprova sullo stesso schema e annotarlo nel report.
```bash
git add src/mcp_connector/nextcloud/clients/mail_drafts.py src/mcp_connector/tools/drafts.py tests/unit/test_olivia_mail_drafts.py tests/contract/test_no_destructive_calls.py vulture_whitelist.py
git commit -m "feat(olivia): create mail drafts, new or replies, with Nextcloud attachments"
```

---

### Task 7: Strumento `mail_draft`

**Files:**
- Modify: `src/mcp_connector/server/reg_mail.py`
- Modify: `tests/contract/test_tool_surface.py` (`EXPECTED_TOOLS` e `CREATE_TOOLS` con `mail_draft`; testi "six write paths" → "seven")
- Modify: `src/mcp_connector/audit/allowlist.py` (`"mail_draft": frozenset({"account", "attachments", "reply_to"})`; aggiungere `body`, `subject`, `to`, `cc`, `bcc` a `FORBIDDEN_PARAMS` con una riga di commento: contenuto della mail e dati personali)
- Modify: `README.md` (riga nuova nella tabella strumenti)
- Test: `tests/unit/test_olivia_mail_draft_tool.py`

**Interfaces:**
- Consumes: `drafts.create` (Task 6), `deps.resolve_clients`, `CREATE_ONLY`, `graceful`, `compact`.
- Produces: strumento MCP `mail_draft(to, cc, bcc, subject, body, account, reply_to, attachments) -> str`.

- [ ] **Step 1: Test che falliscono**

```python
# tests/unit/test_olivia_mail_draft_tool.py
import json

import pytest
from fastmcp import Client  # usare lo stesso import di tests/contract/test_tool_surface.py

from mcp_connector.server import mcp, reg_mail

pytestmark = pytest.mark.anyio


async def test_the_tool_passes_everything_to_drafts_create(monkeypatch):
    seen = {}

    async def fake_create(clients, **kwargs):
        seen.update(kwargs)
        return {"draft_id": 7}

    monkeypatch.setattr(reg_mail.deps, "resolve_clients", lambda ctx: "clients")
    monkeypatch.setattr(reg_mail.drafts, "create", fake_create)
    tool = getattr(reg_mail.mail_draft, "__wrapped__", reg_mail.mail_draft)
    text = await tool(to=["a@b.it"], subject="s", body="b", reply_to="mail:1",
                      attachments=["/Docs/a.pdf"], ctx=None)
    assert json.loads(text) == {"draft_id": 7}
    assert seen["attachments"] == ["/Docs/a.pdf"]
    assert seen["reply_to"] == "mail:1"


async def test_the_tool_is_create_only_and_says_it_never_sends():
    async with Client(mcp, raise_exceptions=True) as client:
        tools = {tool.name: tool for tool in (await client.list_tools()).tools}
    tool = tools["mail_draft"]
    assert tool.annotations is not None
    assert tool.annotations.read_only_hint is False
    assert tool.annotations.destructive_hint is False
    assert "never sent" in (tool.description or "")
```
(Allineare l'import di `Client` e di `mcp` a quelli usati in `tests/contract/test_tool_surface.py`.)

- [ ] **Step 2: Eseguire e vedere fallire**

Run: `uv run pytest tests/unit/test_olivia_mail_draft_tool.py -v`
Expected: FAIL.

- [ ] **Step 3: Implementare in `reg_mail.py`**

```python
from ..tools import drafts


@mcp.tool(annotations=CREATE_ONLY, structured_output=False)
@graceful
async def mail_draft(
    to: Annotated[list[str] | None, Field(description="Recipients; a reply defaults to the sender")] = None,
    subject: Annotated[str, Field(description="Subject; a reply defaults to Re: ...")] = "",
    body: Annotated[str, Field(description="Plain text body")] = "",
    reply_to: Annotated[str, Field(description="mail:<id> to answer")] = "",
    account: Annotated[str, Field(description="Sender account email or id")] = "",
    cc: Annotated[list[str] | None, Field(description="Cc recipients")] = None,
    bcc: Annotated[list[str] | None, Field(description="Bcc recipients")] = None,
    attachments: Annotated[list[str] | None, Field(description="Nextcloud file paths")] = None,
    ctx: Context | None = None,
) -> str:
    """Create a draft in Nextcloud Mail, new or a reply, with Nextcloud files attached; it is
    never sent. The user reviews and sends it in Mail."""
    clients = deps.resolve_clients(ctx)
    return compact(
        await drafts.create(
            clients, to=to, cc=cc, bcc=bcc, subject=subject, body=body,
            account=account, reply_to=reply_to, attachments=attachments,
        )
    )
```
(Importare `CREATE_ONLY` accanto a `READ_ONLY`.) README: `| mail_draft | create | Draft in Nextcloud Mail, new or reply, with Nextcloud files attached; never sent |`.

- [ ] **Step 4: Eseguire, budget, lint e commit**

Run: `uv run pytest tests/unit tests/contract && uv run python scripts/check_tool_budget.py` poi i lint.
Expected: PASS, budget sotto 18000.
```bash
git add src/mcp_connector/server/reg_mail.py src/mcp_connector/audit/allowlist.py tests/contract/test_tool_surface.py tests/unit/test_olivia_mail_draft_tool.py README.md vulture_whitelist.py
git commit -m "feat(olivia): mail_draft tool"
```

---

### Task 8: Rilascio, installazione e verifiche dal vivo (controller)

**Files:** `appinfo/info.xml` (`<image-tag>0.3.2-olivia.3</image-tag>`); nessun altro file del repository.

- [ ] **Step 1:** `<image-tag>0.3.2-olivia.3</image-tag>`, suite e lint, commit `build(olivia): image tag 0.3.2-olivia.3`, push di `olivia`, tag `v0.3.2-olivia.3`, attesa del workflow `release.yml` (verde, asset `info.xml` con id rinominato e rotta `/ul`).
- [ ] **Step 2:** sul LXC 104: `occ app_api:app:unregister mcp_connector_olivia` (senza `--rm-data`) e `occ app_api:app:register mcp_connector_olivia harp --info-xml https://github.com/aledrosera/nextcloud-mcp-connector/releases/download/v0.3.2-olivia.3/info.xml --env NC_MCP_PUBLIC_URL=https://nextcloud.olivia.casa/exapps/mcp_connector_olivia --wait-finish`; container `healthy`, autorizzazione OAuth ancora presente.
- [ ] **Step 3: prove dal vivo (autorizzate):**
  - emettere un link di caricamento per `/TEST-MCP-upload/sotto/prova à.bin` con il codice installato (impersonazione AppAPI, come nelle prove precedenti);
  - dal Mac `curl -fsS -T` di 1 MB e di 50 MB attraverso Cloudflare → 201, file presenti con la dimensione giusta, cartelle create;
  - secondo caricamento sullo stesso percorso → 409 `exists`;
  - link riusato → 404;
  - log con `/ul/xxxx…`;
  - una bozza nuova (account Gmail, a sé stesso) e una di risposta alla mail 140813 con allegato uno dei file caricati: controllo in `oc_mail_local_messages`, allegato presente;
  - pulizia di file, cartelle e bozze di prova (bozze locali con `DELETE /api/drafts/<id>` solo nello script di prova).
- [ ] **Step 4: accettazione in Claude Desktop (utente):**
  - "crea un documento Word di prova e salvalo in /TEST-MCP/";
  - "salvalo di nuovo nello stesso percorso" (rifiuto);
  - "prepara una bozza di risposta alla mail cauzioni allegando quel documento";
  - "prepara una bozza nuova a me stesso dal mio account Gmail".

  Verifica lato server dai log. Qui si chiude anche la verifica aperta del PUT dall'ambiente di Claude.
- [ ] **Step 5:** pulizia dei dati di prova, aggiornamento della memoria (`mcp-connector-olivia-fork.md`: rilascio .3, caricamento, bozze, limite dell'aggancio delle risposte).
