"""Stream one mail attachment through the same single-use link route as a file (fork olivia).

Verified live against Mail 5.12.2 (2026-09-30, change approved by the user that day): the
route Mail *declares* for this, ``/ocs/v2.php/apps/mail/message/{id}/attachment/{aid}``,
answers 200 with an EMPTY body for a binary attachment, so it cannot serve a download at
all. The internal route Mail's own frontend uses instead answers 200 with the exact bytes,
the real content type and a ``Content-Disposition: attachment`` header; an unknown message
or attachment answers 404. This module builds exactly that one GET and nothing else, the
same way ``nextcloud/clients/dav.py`` builds ``open_download`` for a file: no send, no
draft, no move, no delete stands here. It is a sibling of ``nextcloud/clients/mail.py``, not
an edit to it, and the read only promise and contract test of that module are about that
module alone.
"""

import re

import httpx

from ..errors import REASON_PERMISSION_DENIED, REASON_UNKNOWN_ID, ToolError
from ..nextcloud.credentials import Credentials

#: The one route this module ever builds. See the module docstring for why the route Mail
#: declares for the same purpose cannot be used instead.
ATTACHMENT_PATH = "/index.php/apps/mail/api/messages/{message}/attachment/{attachment}"

#: A ticket path of this family: ``mail:<message id>/<attachment id>``. The attachment id is
#: the IMAP part number Mail reports (``"2"``, sometimes a sub-part like ``"2.1"``), so a
#: dotted tail is accepted and nothing else is: no slash, no leading zero rule, nothing that
#: is not a digit or a dot between digits.
_TICKET_PATTERN = re.compile(r"mail:([0-9]+)/([0-9]+(?:\.[0-9]+)*)")


def ticket_path(message_id: str, attachment_id: str) -> str:
    """Build the ticket path an issued attachment link is stored under."""
    return f"mail:{message_id}/{attachment_id}"


def parse_ticket_path(path: str) -> tuple[str, str] | None:
    """Split a ticket path back into ``(message_id, attachment_id)``, or ``None``.

    Only the exact shape :func:`ticket_path` builds is accepted. Anything else, including a
    non numeric id, a trailing slash, or an attempt to walk out of it with ``..``, is not a
    mail attachment ticket, and the caller (``downloads/route.py``) falls back to treating
    the ticket as an ordinary file path instead.
    """
    match = _TICKET_PATTERN.fullmatch(path)
    if match is None:
        return None
    return match.group(1), match.group(2)


async def open_attachment(
    client: httpx.AsyncClient, creds: Credentials, message_id: str, attachment_id: str
) -> httpx.Response:
    """Open a streamed GET of one mail attachment for the download route (fork olivia).

    Built the same way as ``dav.open_download``: no Range header, ``Accept-Encoding:
    identity``, and the response is handed back open for the caller to stream and
    ``aclose()``. Only a GET is ever built here, and it is the only request this function
    sends.
    """
    what = f"the attachment {attachment_id} of the message {message_id}"
    url = f"{creds.base_url}{ATTACHMENT_PATH.format(message=message_id, attachment=attachment_id)}"
    request = client.build_request("GET", url, headers={"Accept-Encoding": "identity"})
    response = await client.send(request, auth=creds.auth(), stream=True)
    # Same reading as ``dav.open_download``: a rejected credential behind a download link is
    # the same as a revoked connection from the link's point of view.
    if response.status_code == 401:
        await response.aclose()
        raise ToolError(
            message="Nextcloud rejected the credentials of this link.",
            hint="Ask for a new link.",
            reason=REASON_PERMISSION_DENIED,
        )
    try:
        _check(response, what)
    except BaseException:
        await response.aclose()
        raise
    return response


def _check(response: httpx.Response, what: str) -> None:
    """Translate a Nextcloud status the same way ``dav._check`` does. No retry, ever."""
    status = response.status_code
    if status == 200:
        return
    if status == 403:
        raise ToolError(
            message=f"No permission to read {what}.",
            hint="Ask the owner of the mail account for a fresh link.",
            reason=REASON_PERMISSION_DENIED,
        )
    if status == 404:
        raise ToolError(
            message=f"Not found: {what}.",
            hint="The message or attachment may have been deleted; ask for a new link.",
            reason=REASON_UNKNOWN_ID,
        )
    if status >= 500:
        raise ToolError(
            message=f"Nextcloud reported a server error ({status}) for {what}.",
            hint="This is a problem on the Nextcloud side. Retry later or check its log.",
        )
    raise ToolError(
        message=f"Nextcloud answered with an unexpected status {status} for {what}.",
        hint="Retry once; if it persists, check the Nextcloud log for that request.",
    )
