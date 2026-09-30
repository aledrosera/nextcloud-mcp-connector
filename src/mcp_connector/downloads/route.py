"""The public ``/dl/{token}`` route: streams one file once, with the rights of its issuer.

Every refusal is the same 404, so a caller learns nothing about which tokens exist. The
credentials are rebuilt at download time from the connection that issued the link, so a
connection ended in Nextcloud (or an account paused on the connections page) ends its links too.
HEAD only checks the ticket and the link, never the file itself; a file that has since
disappeared in Nextcloud only surfaces on GET.
"""

import logging
import re
import time
from collections.abc import AsyncIterator, Mapping
from urllib.parse import quote

import anyio
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
from . import mail_attachment, upload
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
    # The fallback is untrusted: besides the quote and backslash that would break out of the
    # quoted-string, drop ASCII control characters (< 32, and DEL at 127) too.
    ascii_only = name.encode("ascii", "ignore").decode("ascii")
    fallback = "".join(c for c in ascii_only if c not in '"\\' and 32 <= ord(c) != 127)
    encoded = quote(name, safe="")
    return f"attachment; filename=\"{fallback or 'download'}\"; filename*=UTF-8''{encoded}"


def _headers(ticket: Ticket, length: str | None) -> dict[str, str]:
    headers = {
        "Content-Type": ticket.content_type or "application/octet-stream",
        "Content-Disposition": _disposition(ticket.name),
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
    }
    if length is not None:
        headers["Content-Length"] = length
    return headers


def _masked(token: str) -> str:
    return f"{token[:4]}…"


async def rebuild_credentials(
    env: Mapping[str, str] | None, oauth_store: StoreProvider, ticket: Ticket
) -> Credentials | None:
    """Rebuild the credentials of a ticket's issuer; shared by the download and the upload route."""
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
        token = str(request.path_params.get("token", ""))
        if not TOKEN_PATTERN.fullmatch(token):
            return _not_found()
        # Resolved per request, not once at wiring time: ``ticket_store(env)`` reads
        # ``APP_PERSISTENT_STORAGE`` through :func:`config.persistent_storage`, and every other
        # store of this app pays that cost at first use rather than at ``build_exapp_app`` time
        # (see ``oauth/store.py::explicit_store_opener``), so an application built for a route
        # that never touches storage still builds against an incomplete deploy environment.
        store = tickets if tickets is not None else ticket_store(env)
        if request.method == "HEAD":
            ticket = await store.peek(token)
            if ticket is None or ticket.path.startswith(upload.UPLOAD_PREFIX):
                return _not_found()
            if await rebuild_credentials(env, oauth_store, ticket) is None:
                return _not_found()
            return Response(status_code=200, headers=_headers(ticket, str(ticket.size)))

        ticket = await store.claim(token)
        if ticket is None:
            return _not_found()
        # From here on the ticket is claimed (``in_progress``): every path below either
        # returns a response that already released or finished it, or re-raises through the
        # handler below, which releases it so a client can retry instead of losing the link
        # to an error it never caused.
        try:
            # An upload ticket (fork olivia): the download route never serves it, and the
            # link goes back unburned so a client that guessed wrong is not the one paying.
            if ticket.path.startswith(upload.UPLOAD_PREFIX):
                await store.release(token)
                return _not_found()
            creds = await rebuild_credentials(env, oauth_store, ticket)
            if creds is None:
                await store.release(token)
                return _not_found()
            # A mail attachment ticket carries its own two part path (fork olivia): the same
            # route serves both kinds, and which upstream call to make is decided here, once,
            # from the ticket's own path rather than from anything the request carries.
            attachment_parts = mail_attachment.parse_ticket_path(ticket.path)
            try:
                if attachment_parts is not None:
                    message_id, attachment_id = attachment_parts
                    upstream = await mail_attachment.open_attachment(
                        shared_client(), creds, message_id, attachment_id
                    )
                else:
                    upstream = await dav.open_download(shared_client(), creds, ticket.path)
            except ToolError as exc:
                if exc.reason == REASON_PERMISSION_DENIED:
                    # Burn the ticket instead of releasing it: a retry would only resend the
                    # same rejected credential and feed Nextcloud's failed-login counter.
                    await store.finish(token)
                    return _not_found()
                if exc.reason == REASON_UNKNOWN_ID:
                    await store.release(token)
                    return _not_found()
                await store.release(token)
                return _bad_gateway()
            except httpx.HTTPError:
                await store.release(token)
                return _bad_gateway()

            length = upstream.headers.get("Content-Length")

            async def body() -> AsyncIterator[bytes]:
                completed = False
                try:
                    async for chunk in upstream.aiter_raw(chunk_size=CHUNK_BYTES):
                        yield chunk
                    completed = True
                finally:
                    # The client can disconnect mid-stream, which cancels this scope; shield
                    # the cleanup so aclose/finish/release (and the delivery log) still run
                    # instead of being cut off by the cancellation that triggered them.
                    with anyio.CancelScope(shield=True):
                        await upstream.aclose()
                        if completed:
                            await store.finish(token)
                            logger.info(
                                "download delivered: user=%s file=%r link=%s at=%s",
                                ticket.nc_user,
                                ticket.name,
                                _masked(token),
                                int(time.time()),
                            )
                        else:
                            await store.release(token)

            return StreamingResponse(body(), status_code=200, headers=_headers(ticket, length))
        except BaseException:
            # Shielded for the same reason as the ``body()`` cleanup above: this branch is
            # most often reached because the surrounding scope was cancelled, and an
            # unshielded release would itself be cancelled before the ticket went back
            # (fix round 1, M2).
            with anyio.CancelScope(shield=True):
                await store.release(token)
            raise

    return [Route(DOWNLOAD_PATH, download, methods=["GET", "HEAD"])]
