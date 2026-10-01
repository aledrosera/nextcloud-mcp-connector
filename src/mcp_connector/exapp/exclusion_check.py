"""The handler behind ``occ mcp_connector:exclusion:check``: does kein-ki work here (OPS-01)?

The verdict lives in ``nextcloud/exclusion_audit.py`` and answers in data, the reads live in
``nextcloud/clients/systemtags.py`` and know no policy; this module fetches, hands the facts
to the verdict and turns the answer into sentences for a console. The same split
``exapp/exchange_check.py`` has with ``oauth/exchange_dryrun.py``, and this file is a
structural copy of that one, not an abstraction over both: a change made for one command
must not silently change how another one reads its input. The test file holds the copied
spellings against ``exapp/audit_verify.py``.

**Why there is no route in the manifest** (``exapp/audit_verify.py:13-23``). AppAPI reaches
this handler over ``PublicFunctions``, the internal path every occ handler of this app
arrives on, so it needs no declaration. A declaration would make it callable by anyone who
can reach the PHP proxy, which attaches valid AppAPI headers itself; what would leak is an
oracle over tag names and delegation groups of the instance (T-29-12). A request carrying
``x-origin-ip`` is therefore 404, a request without valid AppAPI headers 401.

**Why the answer is always 200** (``exapp/audit_verify.py:25-33``). AppAPI writes the body of
an occ handler to the console only after a status check, and on any status but 200 it
prints ``command executeHandler failed`` and drops the body unread. A failed check reported
with an error status would lose exactly the answer that names what failed. The price is
named rather than hidden: the exit code is always 0, so a script reads the ``passed`` key of
``--json`` and never the return value.

**Who the reads run as.** With ``--admin=<uid>`` the handler first proves that this account
is an administrator (``systemtags.confirm_admin``, decision b of plan 29-01) and only then
asks for ``oc:groups``, because a non-admin asking for it gets a 403 for the whole listing.
An account that is proven not to be an administrator ends the run (``passed`` false); an
answer that decides nothing leads onto the way without an administrator's view, read as the
named account, so a missing tag stays a hint there as well (D-29-03). Without ``--admin`` the
reads run as the first account (sorted) of the AppAPI user list that answers the listing
with 207, at most five tries, and only visible tags count (ENTSCHEID ohne-admin, 29-01).
Disabled accounts answer 207 too (M1c); that does no harm, since the counts are instance
wide and not filtered by the reader.

**What this module never writes down.** No object id, no path, no account: not the uid
handed to ``--admin``, not the account read as without it, not the AppAPI token that carries
either (D-29-02, D-29-10, T-29-14). The uid travels only inside that token and never in a
URL. Tag names and group ids are the answer and appear; nothing else does. Only PROPFIND
and GET leave this handler, and it writes no audit entry: it reads configuration, not data
of a user.
"""

import json
import logging
import unicodedata
from collections.abc import Callable, Mapping, Sequence
from typing import Any, Final

import httpx
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route

from .. import config
from ..audit.accounts import existing_users
from ..errors import ToolError
from ..nextcloud.clients import systemtags
from ..nextcloud.credentials import MODE_APPAPI, Credentials
from ..nextcloud.exclusion_audit import (
    KIND_EXACT,
    KIND_SIMILAR,
    KIND_VARIANT,
    MODE_ORGANISATION,
    MODE_SELF_SERVICE,
    STEP_ADMIN_IDENTITY,
    STEP_ASSIGNMENT_COUNT,
    STEP_NO_VARIANTS,
    STEP_OPERATING_MODE,
    STEP_TAG_EXISTS,
    STEP_TAG_LISTING_READABLE,
    STEP_TAG_VISIBLE,
    AuditResult,
    AuditStep,
    TagFacts,
    access_of,
    audit,
    kind_of,
)
from ..nextcloud.http import shared_client
from .auth import AppApiRejected, require_appapi
from .responses import NO_STORE, BodyTooLarge, BodyUnreadable, bounded_body, json_response

__all__ = [
    "ADMIN_OPTION",
    "EXCLUSION_CHECK_PATH",
    "JSON_OPTION",
    "MAX_BODY_BYTES",
    "MAX_UID_LENGTH",
    "STEP_NAMES",
    "exclusion_check_routes",
]

#: The path of the one route, and the ``execute_handler`` the occ registration of plan 29-05
#: hands to AppAPI. It appears in no ``<url>`` of the manifest, on purpose.
EXCLUSION_CHECK_PATH = "/exclusion-check"

#: The option that names an administrator to read as (D-29-09).
ADMIN_OPTION = "admin"

#: The shape switch every occ handler of this app carries: with it the answer is JSON.
JSON_OPTION = "json"

#: The envelope AppAPI wraps an occ invocation in (``exapp/audit_verify.py:79-86``).
OCC_ENVELOPE = "occ"

#: Set on the proxy path only. Spelled here rather than imported, for the import cycle
#: ``exapp/exchange_check.py`` describes (``lifecycle`` imports ``occ``, ``occ`` imports the
#: handlers); the test holds it against ``exapp/audit_verify.py``.
HEADER_ORIGIN_IP = "x-origin-ip"

#: The bound of ``exapp/audit_verify.py:97``: the real body is two short options.
MAX_BODY_BYTES: Final[int] = 4096

#: An announced length with more digits than this is above the bound whatever it says, and
#: is never handed to :func:`int` (R-18-08).
MAX_ANNOUNCED_DIGITS = 10

#: The words that mean "yes" for the shape option, copied from ``exapp/audit_verify.py``.
TRUE_WORDS = frozenset({"1", "true", "yes", "on"})

#: The longest uid ``--admin`` accepts. Nextcloud allows 64 characters for a user id.
MAX_UID_LENGTH: Final[int] = 64

#: How many accounts of the user list are tried without ``--admin`` (ENTSCHEID 29-01).
MAX_READ_ATTEMPTS: Final[int] = 5

#: The named outcome of a body this handler did not read, after ``exapp/exchange_check.py``.
OUTCOME_BODY_NOT_READ = "request_body_not_read"

BODY_NOT_READ_SENTENCE = (
    "the body of this invocation was not read, so nothing was checked. It was larger than "
    "this handler reads, unreadable, or not JSON; the container log of this app names which."
)

HEAD_LINE = "checked the kein-ki exclusion tag of this instance, read only"

#: Width of the outcome column; every outcome of the verdict fits.
OUTCOME_WIDTH = 12

#: The names an administrator reads, one per step of ``exclusion_audit.STEPS``.
STEP_NAMES: Final[dict[str, str]] = {
    STEP_ADMIN_IDENTITY: "the named account is an administrator",
    STEP_TAG_LISTING_READABLE: "the tag listing of this instance can be read",
    STEP_TAG_EXISTS: "a tag named exactly kein-ki exists",
    STEP_TAG_VISIBLE: "the kein-ki tag is visible to users",
    STEP_NO_VARIANTS: "no other spelling of kein-ki is in use",
    STEP_OPERATING_MODE: "the operating mode of the kein-ki tag",
    STEP_ASSIGNMENT_COUNT: "the items carrying kein-ki can be counted",
}

CREATE_COMMAND = "php occ tag:add kein-ki public"

NO_TAG_SENTENCE = (
    f"Hint: no kein-ki tag exists, the connector filters nothing. Create it with: {CREATE_COMMAND}"
)
NO_VISIBLE_TAG_SENTENCE = (
    "Hint: no visible kein-ki tag exists; invisible tags were not checked. "
    "Run again with --admin=<uid> to also check invisible tags; "
    f"if none exists, create it with: {CREATE_COMMAND}"
)

MODE_SENTENCES: Final[dict[str, str]] = {
    MODE_SELF_SERVICE: (
        "Self service: every user who can see a file can set and remove kein-ki on it."
    ),
    MODE_ORGANISATION: (
        "Organisation mode: only members of {groups} and administrators can set or remove kein-ki."
    ),
}
ADMINS_ONLY_SENTENCE = "Organisation mode: only administrators can set or remove kein-ki."
GROUPS_NOT_READ_SENTENCE = (
    "Organisation mode: only members of the delegation groups and administrators can set or "
    "remove kein-ki; the groups were not read."
)
INVISIBLE_SENTENCE = (
    "An invisible kein-ki tag does not work for users: the connector reads tags as the user, "
    "who cannot see it, so the items carrying it are not excluded. Make it public or "
    "restricted."
)
ONLY_VARIANT_SENTENCE = (
    "No tag is named exactly kein-ki, only other spellings, which the connector does not "
    "honour: it filters nothing."
)
COUNT_SENTENCE = "Items carrying kein-ki (assignments across the instance, trash bin included): {n}"
COUNT_UNKNOWN_SENTENCE = "The number of items carrying kein-ki could not be read."
VARIANT_WARNING = "Items tagged '{name}' are NOT excluded: {n}"
SIMILAR_SENTENCE = "A tag with a similar name is not the exclusion tag: '{name}'"
NOT_CHECKED_SENTENCE = (
    "Without --admin: invisible tags and delegation groups were not checked; "
    "run again with --admin=<uid>."
)
UNCONFIRMED_SENTENCE = (
    "The named administrator could not be confirmed; invisible tags and delegation groups "
    "were not checked; run again with --admin=<uid> of an administrator."
)
NOT_ADMIN_SENTENCE = (
    "the account named with --admin is not an administrator of this instance; nothing was checked."
)
BAD_UID_SENTENCE = (
    f"the value of --admin is not a user id this command accepts (at most {MAX_UID_LENGTH} "
    "characters, no control characters); nothing was checked."
)
DEPLOY_SENTENCE = (
    "deploy environment incomplete: this app cannot reach Nextcloud, so nothing was checked. "
    "The container log at startup names the missing variable."
)
LISTING_FAILED_SENTENCE = "the tag listing could not be read: {why}"
REASON_NO_ACCOUNTS = (
    "the account list of this instance could not be read, so there is no account to read "
    "the tag listing as; run again with --admin=<uid>"
)
REASON_NO_READER = (
    f"none of the first {MAX_READ_ATTEMPTS} accounts of this instance could read the tag "
    "listing; run again with --admin=<uid>"
)
LIMIT_SENTENCE = (
    "A green result does not cover shares: a tag above the root of a share does not protect "
    "it for the recipient. See docs/exclusion.md."
)

#: The failures of a read that become a named result instead of an exception: transport,
#: an unreadable Multi-Status (``xml.parse_root``) and data Nextcloud cannot have sent.
_READ_FAILURES = (httpx.HTTPError, ToolError, ValueError)

logger = logging.getLogger("mcp_connector.exapp.exclusion_check")


def exclusion_check_routes(
    env: Mapping[str, str] | None = None,
    *,
    client_provider: Callable[[], httpx.AsyncClient] | None = None,
) -> list[Route]:
    """The one route of the check, handed out rather than registered on the server object.

    A factory for the reason ``exapp/exchange_check.exchange_check_routes`` gives: a
    registration on the shared server object would put this path into the standalone mode,
    which has no AppAPI identity to check it against. ``client_provider`` defaults to the
    shared client of the running loop; the account list is read by ``existing_users`` over
    that same shared client either way.
    """
    provide = client_provider or shared_client

    async def exclusion_check(request: Request) -> Response:
        """Read the tags, judge them, and name every step with its outcome."""
        guarded = _guard(request, env)
        if isinstance(guarded, Response):
            return guarded

        payload, unread = await _payload(request)
        if unread is not None:
            # Always text: the shape option travels in the body that was not read.
            return _text(f"{unread}: {BODY_NOT_READ_SENTENCE}\n")
        as_json = _set_in(payload)

        try:
            document, text = await _run(env, provide, _value(payload, ADMIN_OPTION))
            logger.info(
                "an exclusion check ran: passed=%s, mode=%s, assigned=%s, admin_checked=%s",
                document["passed"],
                document.get("mode"),
                document.get("assigned"),
                document.get("admin_checked"),
            )
            answer = json_response(document) if as_json else _text(text)
        except Exception as exc:
            # The type only, never the message: it can carry a URL or a value handed in.
            logger.error("the exclusion check could not run: %s", type(exc).__name__)
            if as_json:
                return json_response(
                    {"checked": False, "passed": False, "error": type(exc).__name__}
                )
            return _text(f"the exclusion check could not run: {type(exc).__name__}\n")
        return answer

    return [Route(EXCLUSION_CHECK_PATH, exclusion_check, methods=["POST"])]


async def _run(
    env: Mapping[str, str] | None,
    provide: Callable[[], httpx.AsyncClient],
    admin: str | None,
) -> tuple[dict[str, Any], str]:
    """One check from the option to the answer: the JSON document and the text."""
    if admin is not None and not _acceptable_uid(admin):
        return _refusal(BAD_UID_SENTENCE)
    try:
        settings = config.exapp_settings(env)
    except ToolError:
        return _refusal(DEPLOY_SENTENCE)

    client = provide()

    def creds_for(user: str) -> Credentials:
        return Credentials(
            base_url=settings.base_url,
            user=user,
            secret=settings.app_secret,
            mode=MODE_APPAPI,
            app_id=settings.app_id,
            app_version=settings.app_version,
            aa_version=settings.aa_version,
        )

    unconfirmed = False
    if admin is not None:
        reader = creds_for(admin)
        proven = await systemtags.confirm_admin(client, reader)
        if proven is False:
            result = audit((), admin_checked=False, admin_failed=True)
            return _finish(result, reason=NOT_ADMIN_SENTENCE, unconfirmed=False)
        admin_checked = proven is True
        unconfirmed = not admin_checked
        listing, why = await _read_listing(client, reader, with_groups=admin_checked)
        if listing is None:
            result = audit((), admin_checked=admin_checked, listing_ok=False)
            reason = LISTING_FAILED_SENTENCE.format(why=why)
            return _finish(result, reason=reason, unconfirmed=unconfirmed)
    else:
        admin_checked = False
        found = await _first_reader(env, client, creds_for)
        if isinstance(found, str):
            result = audit((), admin_checked=False, listing_ok=False)
            return _finish(result, reason=found, unconfirmed=False)
        reader, listing = found

    details = [t for t in listing.tags if admin_checked or t.visible]
    facts = [await _facts(client, reader, detail) for detail in details]
    result = audit(facts, admin_checked=admin_checked)
    return _finish(result, reason=None, unconfirmed=unconfirmed)


def _acceptable_uid(uid: str) -> bool:
    """At most :data:`MAX_UID_LENGTH` characters and no character of category C (T-29-15)."""
    if len(uid) > MAX_UID_LENGTH:
        return False
    return not any(unicodedata.category(ch).startswith("C") for ch in uid)


async def _read_listing(
    client: httpx.AsyncClient, creds: Credentials, *, with_groups: bool
) -> tuple[systemtags.TagDetailListing | None, str]:
    """The listing on 207, or ``None`` and the reason in words. Never "no tag" (T-29-16)."""
    try:
        listing = await systemtags.list_tag_details(client, creds, with_groups=with_groups)
    except httpx.HTTPError as exc:
        return None, type(exc).__name__
    except (ToolError, ValueError):
        return None, "unreadable answer"
    if listing.status != 207:
        return None, f"Nextcloud answered {listing.status}"
    return listing, ""


async def _first_reader(
    env: Mapping[str, str] | None,
    client: httpx.AsyncClient,
    creds_for: Callable[[str], Credentials],
) -> tuple[Credentials, systemtags.TagDetailListing] | str:
    """The first account (sorted) that reads the listing with 207, or the reason there is none.

    Without groups: a non-admin asking for them gets a 403 for the whole listing. Every
    other status and every read failure counts as one try and moves on to the next account.
    """
    accounts = await existing_users(env)
    if not accounts:
        return REASON_NO_ACCOUNTS
    for account in sorted(accounts)[:MAX_READ_ATTEMPTS]:
        creds = creds_for(account)
        listing, _ = await _read_listing(client, creds, with_groups=False)
        if listing is not None:
            return creds, listing
    return REASON_NO_READER


async def _facts(
    client: httpx.AsyncClient, creds: Credentials, detail: systemtags.TagDetail
) -> TagFacts:
    """One tag as the verdict reads it; exact tags and variants only are counted.

    No count for other or similar names: one PROPFIND per tag of the instance would be the
    Depth-1-over-everything anti-pattern, and the verdict never sums those anyway.
    """
    assigned: int | None = None
    if kind_of(detail.name) in (KIND_EXACT, KIND_VARIANT):
        try:
            assigned = (await systemtags.count_tag_objects(client, creds, detail.id)).files
        except _READ_FAILURES:
            assigned = None
    return TagFacts(
        id=detail.id,
        name=detail.name,
        visible=detail.visible,
        assignable=detail.assignable,
        groups=detail.groups,
        assigned=assigned,
    )


def _refusal(sentence: str) -> tuple[dict[str, Any], str]:
    """A run that ended before any read: nothing checked, the reason named."""
    return {"checked": False, "passed": False, "reason": sentence}, sentence + "\n"


def _finish(
    result: AuditResult, *, reason: str | None, unconfirmed: bool
) -> tuple[dict[str, Any], str]:
    """Both shapes of one verdict."""
    return (
        _machine_readable(result, reason=reason),
        _report(result, reason=reason, unconfirmed=unconfirmed),
    )


def _report(result: AuditResult, *, reason: str | None, unconfirmed: bool) -> str:
    """Head, one line per step (all seven), the sentences, and the limit last."""
    lines = [HEAD_LINE]
    lines.extend(_line(step) for step in result.steps)
    if reason is not None:
        lines.append(reason)
    if result.checked:
        lines.extend(_sentences(result))
        if not result.admin_checked:
            lines.append(UNCONFIRMED_SENTENCE if unconfirmed else NOT_CHECKED_SENTENCE)
    lines.append(LIMIT_SENTENCE)
    return "\n".join(lines) + "\n"


def _sentences(result: AuditResult) -> list[str]:
    """What a checked verdict means, in the order an administrator acts on it."""
    sentences: list[str] = []
    exists = next(s for s in result.steps if s.step == STEP_TAG_EXISTS)
    if exists.note == "no_tag":
        sentences.append(NO_TAG_SENTENCE)
    elif exists.note == "no_visible_tag":
        sentences.append(NO_VISIBLE_TAG_SENTENCE)

    exact = [t for t in result.tags if kind_of(t.name) == KIND_EXACT]
    visible_exact = [t for t in exact if t.visible]
    # Variants and invisible exact tags: items that look protected and are not.
    unprotected = [
        t
        for t in result.tags
        if kind_of(t.name) == KIND_VARIANT or (kind_of(t.name) == KIND_EXACT and not t.visible)
    ]
    if any(not t.visible for t in exact):
        sentences.append(INVISIBLE_SENTENCE)
    if not exact and unprotected:
        sentences.append(ONLY_VARIANT_SENTENCE)
    mode = _mode_sentence(visible_exact)
    if mode is not None:
        sentences.append(mode)
    if visible_exact:
        sentences.append(
            COUNT_UNKNOWN_SENTENCE
            if result.assigned is None
            else COUNT_SENTENCE.format(n=result.assigned)
        )
    for tag in unprotected:
        count = "unknown" if tag.assigned is None else tag.assigned
        sentences.append(VARIANT_WARNING.format(name=tag.name, n=count))
    for tag in result.tags:
        if kind_of(tag.name) == KIND_SIMILAR:
            sentences.append(SIMILAR_SENTENCE.format(name=tag.name))
    return sentences


def _mode_sentence(visible_exact: Sequence[TagFacts]) -> str | None:
    """The operating mode in a sentence (D-29-01); ``None`` without a visible exact tag."""
    if not visible_exact:
        return None
    if any(t.assignable for t in visible_exact):
        return MODE_SENTENCES[MODE_SELF_SERVICE]
    if any(t.groups is None for t in visible_exact):
        return GROUPS_NOT_READ_SENTENCE
    groups = sorted({gid for t in visible_exact for gid in t.groups or ()})
    if not groups:
        return ADMINS_ONLY_SENTENCE
    return MODE_SENTENCES[MODE_ORGANISATION].format(groups=", ".join(groups))


def _line(step: AuditStep) -> str:
    """One step: the outcome in its column, the name, and the note word that qualifies it."""
    line = f"{step.outcome:<{OUTCOME_WIDTH}} {STEP_NAMES.get(step.step, step.step)}"
    if step.note is not None:
        line += f" ({step.note})"
    return line


def _machine_readable(result: AuditResult, *, reason: str | None) -> dict[str, Any]:
    """The same verdict for a script; ``passed`` is what it watches, the exit code is 0.

    ``mode`` is ``None`` for a run that checked nothing, so a failure can never be read as
    "no tag" (T-29-16). Tags carry name, access, groups, count and kind, never an id.
    """
    return {
        "checked": result.checked,
        "passed": result.passed,
        "mode": result.mode if result.checked else None,
        "assigned": result.assigned,
        "unprotected": result.unprotected,
        "admin_checked": result.admin_checked,
        "reason": reason,
        "steps": [
            {
                "step": step.step,
                "name": STEP_NAMES.get(step.step, step.step),
                "outcome": step.outcome,
                "note": step.note,
            }
            for step in result.steps
        ],
        "tags": [
            {
                "name": tag.name,
                "access": access_of(tag),
                "groups": None if tag.groups is None else list(tag.groups),
                "assigned": tag.assigned,
                "kind": kind_of(tag.name),
            }
            for tag in result.tags
        ],
        "limit": LIMIT_SENTENCE,
    }


def _guard(request: Request, env: Mapping[str, str] | None) -> str | Response:
    """Return the Nextcloud user id of this request, or the response that ends it.

    Verbatim the guard of ``exapp/audit_verify.py`` and ``exapp/exchange_check.py``: a
    response instead of an exception so no rejection escapes as a 500, and no detail in it.
    """
    if HEADER_ORIGIN_IP in request.headers:
        return _text("Not Found", status_code=404)
    try:
        return require_appapi(request, env=env)
    except (AppApiRejected, ToolError):
        return json_response({}, status_code=401)


def _set_in(payload: Any, *, inside_envelope: bool = False) -> bool:
    """Whether this invocation carries ``--json``, in any shape AppAPI may send it."""
    if not isinstance(payload, dict):
        return False
    if JSON_OPTION in payload and _is_set(payload[JSON_OPTION]):
        return True

    options = payload.get("options")
    if isinstance(options, dict) and JSON_OPTION in options and _is_set(options[JSON_OPTION]):
        return True
    if isinstance(options, list | tuple) and any(
        isinstance(item, str) and item.strip().lstrip("-") == JSON_OPTION for item in options
    ):
        return True

    if not inside_envelope:
        return _set_in(payload.get(OCC_ENVELOPE), inside_envelope=True)
    return False


def _is_set(value: object) -> bool:
    """Whether this value means the shape option is set. A positive list, nothing beside it."""
    if isinstance(value, bool):
        return value
    if value is None:
        return True
    if isinstance(value, int | float):
        return value == 1
    if not isinstance(value, str):
        return False
    return value.strip().lower() in TRUE_WORDS


def _value(payload: Any, name: str, *, inside_envelope: bool = False) -> str | None:
    """The value of one option: in the occ envelope, at the top level, or under ``options``."""
    if not isinstance(payload, dict):
        return None

    for source in (payload, payload.get("options")):
        if isinstance(source, dict) and name in source:
            given = _given(source[name])
            if given is not None:
                return given

    if not inside_envelope:
        return _value(payload.get(OCC_ENVELOPE), name, inside_envelope=True)
    return None


def _given(value: object) -> str | None:
    """The input in this value, stripped, or ``None`` when there is none."""
    if not isinstance(value, str):
        return None
    return value.strip() or None


async def _payload(request: Request) -> tuple[Any, str | None]:
    """The JSON body, and :data:`OUTCOME_BODY_NOT_READ` when there is none this handler read.

    The shape of ``exapp/exchange_check._payload``, with one warning line naming which of
    the three refusals it was, never the body.
    """
    announced = request.headers.get("content-length", "")
    plain_number = announced.isascii() and announced.isdigit()
    why: str | None = None
    raw = b""
    if plain_number and _above_the_body_bound(announced):
        why = "announced a body above the bound"
    else:
        try:
            raw = await bounded_body(request, MAX_BODY_BYTES)
        except BodyTooLarge:
            why = "sent a body above the bound"
        except BodyUnreadable:
            why = "sent a body that could not be read"
    payload: Any = None
    if why is None and raw:
        try:
            payload = json.loads(raw)
        except ValueError:
            why = "sent a body that is not JSON"
    if why is not None:
        logger.warning("an exclusion check call %s", why)
        return None, OUTCOME_BODY_NOT_READ
    return payload, None


def _above_the_body_bound(announced: str) -> bool:
    """Whether a run of ASCII digits stands for a number above :data:`MAX_BODY_BYTES`."""
    return len(announced) > MAX_ANNOUNCED_DIGITS or int(announced) > MAX_BODY_BYTES


def _text(body: str, status_code: int = 200) -> Response:
    """Every answer that is not JSON, and 200 unless a guard says otherwise."""
    return Response(body, status_code=status_code, media_type="text/plain", headers=NO_STORE)
