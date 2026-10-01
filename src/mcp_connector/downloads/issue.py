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
from ..tools import files as files_tools
from .store import TicketStore, ticket_store

HOW_TO = (
    "Download it from your code execution environment (curl -fL -o <file> or requests); "
    "web_fetch cannot open this link. It works for one completed download and expires at "
    "expires_at."
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
    # Upstream's kein-ki read check: a tagged file answers like a missing one, and a check
    # that cannot be answered refuses every path alike (upstream 0.4.0, EXCL-01).
    info = await files_tools.visible_stat(clients, target)
    if info["is_collection"]:
        raise ToolError(
            message=f"{target} is a folder, not a file.",
            hint="Use files_list to choose a file inside the folder.",
        )
    name = target.rsplit("/", 1)[-1] or target
    content_type = info["content_type"] or "application/octet-stream"
    return await issue_ticket(
        owner,
        path=target,
        name=name,
        content_type=content_type,
        size=info["size"],
        env=env,
        tickets=tickets,
        now=now,
    )


async def issue_ticket(
    owner: TicketOwner,
    *,
    path: str,
    name: str,
    content_type: str,
    size: int,
    env: Mapping[str, str] | None = None,
    tickets: TicketStore | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    """Issue one ticket and its card, for a target this caller already stat'ed itself.

    The "biglietto + scheda" half of :func:`issue_link` (fork olivia, mail attachments):
    everything above the stat call is specific to a WebDAV path, everything from here on is
    not, which is why a mail attachment link (whose size and content type come from the
    Mail app's own envelope, not from a PROPFIND) calls this directly instead.
    """
    store = tickets if tickets is not None else ticket_store(env)
    try:
        token, expires = await store.issue(
            auth_id=owner.auth_id,
            nc_user=owner.nc_user,
            path=path,
            name=name,
            content_type=content_type,
            size=size,
            ttl_seconds=config.download_ttl_minutes(env) * 60,
            now=now,
        )
    except (OSError, sqlite3.Error) as exc:
        raise ToolError(
            message="The download link could not be created.",
            hint="Retry in a moment; if it repeats, check the storage of this app.",
        ) from exc
    return {
        "path": path,
        "name": name,
        "size": size,
        "content_type": content_type,
        "download_url": f"{config.public_url(env).rstrip('/')}/dl/{token}",
        "expires_at": datetime.fromtimestamp(expires, UTC).isoformat(),
        "single_use": True,
        "how_to": HOW_TO,
    }
