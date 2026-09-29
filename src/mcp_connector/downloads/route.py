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
from ..oauth.principal import login_name_of, principal_of
from ..oauth.store import StoreProvider
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
    encoded = quote(name, safe="")
    return f"attachment; filename=\"{fallback or 'download'}\"; filename*=UTF-8''{encoded}"


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
    env: Mapping[str, str] | None, oauth_store: StoreProvider, ticket: Ticket
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
        settings.base_url,
        ticket.nc_user,
        settings.app_secret,
        mode=MODE_APPAPI,
        app_id=settings.app_id,
        app_version=settings.app_version,
        aa_version=settings.aa_version,
    )


def download_routes(
    env: Mapping[str, str] | None, *, oauth_store: StoreProvider, tickets: TicketStore | None = None
) -> list[Route]:
    async def download(request: Request) -> Response:
        # Resolved per request, not once at wiring time: ``ticket_store(env)`` reads
        # ``APP_PERSISTENT_STORAGE`` through :func:`config.persistent_storage`, and every other
        # store of this app pays that cost at first use rather than at ``build_exapp_app`` time
        # (see ``oauth/store.py::explicit_store_opener``), so an application built for a route
        # that never touches storage still builds against an incomplete deploy environment.
        store = tickets if tickets is not None else ticket_store(env)
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
                    logger.info(
                        "download delivered: user=%s file=%s link=%s at=%s",
                        ticket.nc_user,
                        ticket.name,
                        _masked(token),
                        int(time.time()),
                    )
                else:
                    await store.release(token)

        return StreamingResponse(body(), status_code=200, headers=_headers(ticket, length))

    return [Route(DOWNLOAD_PATH, download, methods=["GET", "HEAD"])]
