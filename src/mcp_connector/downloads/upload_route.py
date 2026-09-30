"""The public ``/ul/{token}`` route: one create-only upload, with the rights of its issuer.

Twin of ``/dl/{token}`` (fork olivia): every unusable link gets the same 404, the credentials
are rebuilt from the connection that issued the link, and the body is streamed to Nextcloud
without a copy on disk. The ticket is spent by a completed upload or by an answer that a
retry could not change (the file exists, the credential is rejected); a transport failure or
an interrupted client puts it back so the same link can be tried again until it expires.
"""

import logging
from collections.abc import AsyncIterator, Mapping

import anyio
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
        declared_length = int(declared) if declared.isdigit() else None
        if declared_length is not None and declared_length > MAX_UPLOAD_BYTES:
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
                if folder:
                    mkcol_status = await dav.ensure_folders(shared_client(), creds, folder)
                    # MKCOL never carries the PUT's own precondition, so its statuses are
                    # mapped on their own here and never fall into the PUT table below: a
                    # bare 405/412 there means "exists" and 200/204 means "replaced a file",
                    # neither of which a folder creation ever claims (fix round 1, M3).
                    if mkcol_status is not None:
                        if mkcol_status in (401, 403):
                            await store.finish(token)
                            return _not_found()
                        if mkcol_status == 409:
                            await store.finish(token)
                            return _json(409, {"error": "conflict", "path": target})
                        await store.release(token)
                        return _bad_gateway()
                status = await dav.put_new_stream(
                    shared_client(), creds, target, body(), content_length=declared_length
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
                    ticket.nc_user,
                    target,
                    received,
                    _masked(token),
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
                logger.error(
                    "upload of %r replaced a file: this instance ignored If-None-Match", target
                )
                return _json(502, {"error": "precondition_ignored"})
            await store.release(token)
            return _too_large() if status == 413 else _bad_gateway()
        except BaseException:
            # A cancellation (the client disconnecting, the server shutting down) is what
            # most often reaches this branch, and it cancels the very scope this code runs
            # in; shield the release so the ticket still goes back instead of the shutdown
            # itself swallowing it (fix round 1, M2, same fix as the GET body of route.py).
            with anyio.CancelScope(shield=True):
                await store.release(token)
            raise

    return [Route(UPLOAD_PATH, upload, methods=["PUT"])]
