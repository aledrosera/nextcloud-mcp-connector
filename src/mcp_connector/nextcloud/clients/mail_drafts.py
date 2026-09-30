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
