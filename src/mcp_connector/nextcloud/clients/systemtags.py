"""System tag client: the tag listing and the nodes carrying one tag, free of any policy.

Two Nextcloud calls and nothing else. This module knows no tag name, keeps no cache and
decides nothing; the exclusion guard on top of it does all of that.

Why the REPORT goes to the home root and not through ``dav.files_url``: that helper maps
every path into ``NC_MCP_FILES_ROOT``, and the measurement of phase 25 showed that the
target path of a ``REPORT oc:filter-files`` does not narrow the answer anyway. A tagged
folder above the sandbox has to take effect on everything below it, so the question is
always asked of the whole home.

Why exactly one ``oc:systemtag`` rule per REPORT: Nextcloud's FilesReportPlugin intersects
several rules (``array_uintersect``), so two rules mean "carries both tags". Asking for
two spellings of one tag in one body would silently answer "nothing" for a node that
carries only one of them, which is fail-open. ``filter_files_body`` therefore takes a
single id and cannot be handed a sequence.

Why outcomes come back as values instead of a ``ToolError``: the guard treats 207, 412
and every other status differently (D-25-05), and a raised error would erase exactly that
difference. Only data that cannot be what Nextcloud sends raises: a non-digit id or file
id is a ``ValueError``, an unparsable body is the ``ToolError`` of ``xml.parse_multistatus``.
Transport errors from httpx are not caught here either.

No retry, ever (the rule of ``dav``: Nextcloud counts failed logins per source IP), and
the ``systemtags`` capability is never read (D-25-05): the listing itself is the only
answer that counts.
"""

import re
from dataclasses import dataclass
from urllib.parse import quote, unquote, urlsplit

import httpx
from lxml import etree

from ..credentials import Credentials
from . import dav, xml

TAGS_PATH = "/remote.php/dav/systemtags/"

#: Digits, and only ASCII ones, the same rule as ``dav._DIGITS``: ``str.isdigit`` also
#: accepts a superscript two, and neither a tag id nor a file id ever looks like that.
_DIGITS = re.compile(r"[0-9]+")

_FILEID = f"{{{xml.OC}}}fileid"
_RESOURCETYPE = f"{{{xml.DAV}}}resourcetype"
_TAG_ID = f"{{{xml.OC}}}id"
_TAG_NAME = f"{{{xml.OC}}}display-name"


@dataclass(frozen=True, slots=True)
class Tag:
    """One system tag as Nextcloud lists it; the name is passed on unmodified."""

    id: str
    name: str


@dataclass(frozen=True, slots=True)
class TagListing:
    """The status of the listing and, on 207 only, the tags it carried."""

    status: int
    tags: tuple[Tag, ...]


@dataclass(frozen=True, slots=True)
class TaggedNode:
    """One node carrying the tag. ``path`` is ``None`` when the href is not mappable."""

    path: str | None
    fileid: str
    is_collection: bool


@dataclass(frozen=True, slots=True)
class TaggedSet:
    """The status of one REPORT and, on 207 only, every node it named."""

    status: int
    nodes: tuple[TaggedNode, ...]


def home_url(creds: Credentials) -> str:
    """The WebDAV root of the user's whole home, deliberately outside the sandbox."""
    return f"{creds.base_url}{dav.DAV_FILES_PREFIX}{quote(creds.user, safe='')}/"


def filter_files_body(tag_id: str) -> bytes:
    """Build a ``REPORT oc:filter-files`` body with exactly one tag rule, with lxml."""
    if not _DIGITS.fullmatch(tag_id):
        raise ValueError(f"a tag id must be ASCII digits only (got {tag_id!r})")
    root = etree.Element(
        f"{{{xml.OC}}}filter-files",
        nsmap={"d": xml.DAV, "oc": xml.OC, "nc": xml.NC},
    )
    prop = etree.SubElement(root, f"{{{xml.DAV}}}prop")
    etree.SubElement(prop, _FILEID)
    etree.SubElement(prop, _RESOURCETYPE)
    rules = etree.SubElement(root, f"{{{xml.OC}}}filter-rules")
    etree.SubElement(rules, f"{{{xml.OC}}}systemtag").text = tag_id
    return etree.tostring(root, xml_declaration=True, encoding="utf-8")


def _listing_body() -> bytes:
    """Build the PROPFIND body of the tag listing with lxml (threat T-01-11)."""
    root = etree.Element(
        f"{{{xml.DAV}}}propfind",
        nsmap={"d": xml.DAV, "oc": xml.OC, "nc": xml.NC},
    )
    prop = etree.SubElement(root, f"{{{xml.DAV}}}prop")
    etree.SubElement(prop, _TAG_ID)
    etree.SubElement(prop, _TAG_NAME)
    return etree.tostring(root, xml_declaration=True, encoding="utf-8")


async def list_tags(client: httpx.AsyncClient, creds: Credentials) -> TagListing:
    """List every system tag the user can see, with Depth 1 on the tag collection.

    The collection itself answers without ``oc:id`` and is recognised by its href; any
    other response without an id raises, because a tag whose id cannot be read must end
    in ``unverifiable``, never in ``untagged`` (the listing would otherwise be the one
    entrance where missing mandatory data is tolerated silently). Any status other than
    207 comes back as a value with no tags; what it means is the caller's decision.
    """
    response = await client.request(
        "PROPFIND",
        f"{creds.base_url}{TAGS_PATH}",
        headers={"Depth": "1", "Content-Type": "application/xml"},
        content=_listing_body(),
        auth=creds.auth(),
    )
    if response.status_code != 207:
        return TagListing(status=response.status_code, tags=())
    tags: list[Tag] = []
    for href, props in xml.parse_multistatus(response.content):
        tag_id = props.get(_TAG_ID, "")
        if not tag_id:
            if unquote(urlsplit(href).path).rstrip("/").endswith("/systemtags"):
                continue  # the collection itself carries no oc:id
            raise ValueError(f"Nextcloud listed a tag without an id: {href!r}")
        if not _DIGITS.fullmatch(tag_id):
            raise ValueError(f"Nextcloud listed a tag id that is not ASCII digits: {tag_id!r}")
        tags.append(Tag(id=tag_id, name=props.get(_TAG_NAME, "")))
    return TagListing(status=207, tags=tuple(tags))


async def tagged_nodes(client: httpx.AsyncClient, creds: Credentials, tag_id: str) -> TaggedSet:
    """Ask the whole home for the nodes carrying one tag, with one rule in one REPORT.

    The body is built before the request, so an invalid id raises before any traffic.
    Every ``d:response`` becomes one node; a href that does not map onto the home keeps
    the path ``None`` (see ``dav.home_entries``). A node without a digit file id raises.
    """
    body = filter_files_body(tag_id)
    response = await client.request(
        "REPORT",
        home_url(creds),
        headers={"Content-Type": "application/xml"},
        content=body,
        auth=creds.auth(),
    )
    if response.status_code != 207:
        return TaggedSet(status=response.status_code, nodes=())
    nodes: list[TaggedNode] = []
    for path, props in dav.home_entries(response.content, creds):
        fileid = props.get(_FILEID, "")
        if not _DIGITS.fullmatch(fileid):
            raise ValueError(f"Nextcloud named a tagged node without a digit file id: {fileid!r}")
        nodes.append(
            TaggedNode(
                path=path,
                fileid=fileid,
                is_collection=f"{{{xml.DAV}}}collection" in props.get(_RESOURCETYPE, ""),
            )
        )
    return TaggedSet(status=207, nodes=tuple(nodes))
