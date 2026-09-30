"""Drafts in Nextcloud Mail, new or replies, with Nextcloud files attached (fork olivia)."""

import re
from collections import Counter
from collections.abc import Sequence
from email.utils import getaddresses
from typing import Any

from ..errors import ToolError
from ..nextcloud import NcClients, capabilities
from ..nextcloud.clients import dav, mail_drafts
from ..nextcloud.clients import mail as mail_client

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
        str(r.get("email") or "").lower()
        for r in (original.get("to") or []) + (original.get("cc") or [])
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
            raise ToolError(
                message=f"Attachment {target} cannot be read: {exc.message}", hint=exc.hint
            ) from exc
        if info["is_collection"]:
            raise ToolError(
                message=f"Attachment {target} is a folder.", hint="Attach files, not folders."
            )
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
            raise ToolError(
                message=f"{reply_to!r} is not a mail id.",
                hint="Use the mail:<n> id from search or mail_browse.",
            )
        original, _ = await mail_client.get_message(clients.client, clients.creds, match.group(1))

    if account:
        chosen = _pick(accounts, account)
    elif original is not None:
        chosen = _account_of(accounts, original)
    elif len(accounts) == 1:
        chosen = accounts[0]
    elif not accounts:
        raise ToolError(
            message="No mail account is set up in Nextcloud Mail.",
            hint="Add an account in the Mail app first.",
        )
    else:
        raise ToolError(
            message="Several mail accounts exist.",
            hint=f"Pass account with one of: {_listing(accounts)}.",
        )

    if to:
        recipients = parse_recipients(to)
    elif original is not None:
        source = original.get("replyTo") or original.get("from") or []
        recipients = [
            {"label": r.get("label") or r["email"], "email": r["email"]}
            for r in source
            if r.get("email")
        ]
        if not recipients:
            raise ToolError(
                message="The original mail names no sender to reply to.",
                hint="Pass to with the recipients of the reply.",
            )
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
    # Counted, not looked up: two attachments may share a name from different folders, and
    # Mail storing only one of them must still be reported (fork olivia, review of task 6).
    missing = list((Counter(wanted) - Counter(saved)).elements())
    if missing:
        result["missing_attachments"] = missing
    return result
