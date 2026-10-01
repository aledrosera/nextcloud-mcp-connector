"""The classification of every known search provider against the ``kein-ki`` guard.

A data module, not a test, the provider twin of ``tool_classes.py`` (review WR-02 of phase
28). ``unified_search`` decides a hit as file-bearing only when it carries a readable file
reference (``withhold.file_refs``); a provider that names files in its own way passes that
rule unscreened. ``talk-conversations`` (D-28-21) and the Talk message providers (review
CR-01) were two such providers. So every provider this project has met gets exactly one
class with one sentence of reason, and two gates hold the table:

* ``tests/contract/test_provider_classes.py`` checks the table against the code: every id of
  ``provider_map.PROVIDER_KINDS`` is classified, and the room class is exactly the set
  ``search`` screens against the conversation list.
* ``tests/integration/test_provider_classes_live.py`` lists the providers of the live
  instance and fails on every id the table does not know, the D-28-04 pattern: an app that
  brings a new provider turns the gate red instead of passing unseen.

The runtime default stays as it is (a provider without a file reference is kept): turning it
around withholds whole providers from users while anything is tagged, which is an owner
decision and not a review fix. The gate is the conservative half of WR-02.
"""

from collections.abc import Iterable

from mcp_connector import provider_map
from mcp_connector.tools import search as search_tools

# Hits that carry their file as attributes.fileId, attributes.path or a /f/<id> link; the
# generic screen of tools/search.py (_screen, _settle) decides them by that reference.
FILE_REFERENCE: dict[str, str] = {
    "files": "Carries attributes.fileId and attributes.path of the file it names.",
    "comments": "Carries the file id of the commented file in its /f/<id> link.",
    "notes": "A note id is the file id of the note, read from the last numeric URL segment.",
    "systemtags": (
        "Its file entries carry attributes.path, its tag entries name a tag and no file."
    ),
    "findling": "Carries attributes.fileId and the /index.php/f/<id> route of the document.",
}

# Hits that name a Talk conversation, whose name is the file name for a file conversation;
# decided against the conversation list (D-28-21, review CR-01).
ROOM_SCREENED: dict[str, str] = {
    "talk-conversations": "A file conversation carries the file name as its name (D-28-21).",
    "talk-message": "The hit title is '<actor> in <conversation>' with a /call/<token> link.",
    "talk-message-current": "Inherits the entries of MessageSearch, the same title and link.",
}

# Hits that name no Nextcloud file. Argued from the provider source, not measured one by one.
NO_FILE: dict[str, str] = {
    "appstore": "Names an app of the app store, never a file of the account.",
    "settings_apps": "Names an installed app and links to its settings page.",
    "settings": "Names a section of the settings and links to that page.",
    "circles": "Names a team (circle) and links to the team page.",
    "users": "Names an account of the instance and links to its profile.",
    "mail": "Names an IMAP message, which is mail data and not a Nextcloud file.",
    "calendar": "Names an event by its summary; an ATTACH link is not part of the hit.",
    "contacts": "Names a contact of an address book and links to the contacts app.",
    "tasks": "Names a task by its summary and links to the tasks app.",
    "search-deck-card-board": "Names a Deck card or board; attachments are not part of the hit.",
    "search-deck-comment": "Names a comment on a Deck card and links to that card.",
    "tables-search-tables": "Names a table or a view by its title, never a cell value.",
}

# The shortest reason the gate accepts, as in tool_classes.
MIN_REASON = 20

CLASSES: dict[str, dict[str, str]] = {
    "FILE_REFERENCE": FILE_REFERENCE,
    "ROOM_SCREENED": ROOM_SCREENED,
    "NO_FILE": NO_FILE,
}


def unclassified(provider_ids: Iterable[str]) -> list[str]:
    """Every provider id without an entry in any class, sorted."""
    known = FILE_REFERENCE.keys() | ROOM_SCREENED.keys() | NO_FILE.keys()
    return sorted(set(provider_ids) - known)


def _reason_problem(reason: str) -> str | None:
    if len(reason.strip()) < MIN_REASON:
        return f"reason shorter than {MIN_REASON} characters"
    if "\n" in reason:
        return "reason spans more than one line"
    if not reason.endswith("."):
        return "reason does not end with a full stop"
    return None


def provider_findings(installed: Iterable[str]) -> list[str]:
    """Every finding of the gate for the given installed providers, printable.

    Shared by the gates and their counter proofs, so a counter proof never reimplements
    the check it proves.
    """
    findings = [f"unclassified: {pid}" for pid in unclassified(installed)]
    findings += [
        f"mapped but unclassified: {pid}" for pid in unclassified(provider_map.PROVIDER_KINDS)
    ]
    everywhere: dict[str, list[str]] = {}
    for label, table in CLASSES.items():
        for pid, reason in table.items():
            everywhere.setdefault(pid, []).append(label)
            problem = _reason_problem(reason)
            if problem is not None:
                findings.append(f"{problem}: {label}[{pid}]")
    for pid, labels in sorted(everywhere.items()):
        if len(labels) > 1:
            findings.append(f"in more than one class: {pid} ({', '.join(labels)})")
    screened = set(search_tools._ROOM_SCREENED_PROVIDERS)
    if set(ROOM_SCREENED) != screened:
        findings.append(
            f"room class differs from search: table {sorted(ROOM_SCREENED)}, "
            f"search {sorted(screened)}"
        )
    return findings
