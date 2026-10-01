"""Single-use upload links: Claude PUTs a new file from its code execution environment.

Fork olivia. The link is the mirror of a download link. It lives in the same ticket store,
under a ticket path ``upload:<path>`` so that neither route can ever redeem the other's
ticket, it acts with the rights of the connection that issued it, and it can create a file
but never replace one: the path is checked here, and the PUT itself carries ``If-None-Match: *``.
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
from ..tools import files as files_tools
from .store import TicketStore, ticket_store

UPLOAD_PREFIX = "upload:"
UPLOAD_TTL_SECONDS = 30 * 60
MAX_UPLOAD_BYTES = 100 * 1024 * 1024
UPLOAD_HOW_TO = (
    "Upload from your code execution environment: "
    "curl --fail-with-body -sS -T <file> <upload_url>. "
    "One completed upload; the target must not exist; missing folders are created."
)
_FILE_HINT = "Give the full path of the new file, for example /Docs/report.docx."


def upload_ticket_path(path: str) -> str:
    """The ticket path an upload link is stored under."""
    return f"{UPLOAD_PREFIX}{path}"


def parse_upload_path(ticket_path: str) -> str | None:
    """The target path of an upload ticket, or ``None`` when the ticket is not one.

    Also rejects the bare root (``upload:/``) and anything ending in ``/``: neither names a
    file, and the create-only PUT downstream has no folder semantics to fall back on.
    """
    if not ticket_path.startswith(UPLOAD_PREFIX):
        return None
    path = ticket_path[len(UPLOAD_PREFIX) :]
    if not path.startswith("/") or path == "/" or path.endswith("/"):
        return None
    return path


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
        raise ToolError(
            message="The upload target is the root folder, not a file.",
            hint=_FILE_HINT,
        )
    # Upstream's kein-ki write check before the existence probe, which would itself tell a
    # tagged file from a missing one: a tagged target, or one below a tagged folder, gets the
    # refusal of a missing parent folder (upstream 0.4.0, D-27-01, D-27-02).
    await files_tools.writable(clients, target)
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
