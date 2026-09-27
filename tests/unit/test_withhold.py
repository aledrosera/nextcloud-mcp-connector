"""The shared withholding helpers: one wording, one refusal, one degraded entry, one extractor.

The entries below follow the shapes real providers send: the files provider with
``attributes.fileId`` and ``attributes.path``, Findling with ``fileId`` only, the comments
provider with nothing but a ``/index.php/f/<id>`` link, and notes with the note id as the
last segment of its link.
"""

import re

import pytest

from mcp_connector import config
from mcp_connector.errors import REASON_GUARD_TRIPPED
from mcp_connector.nextcloud import exclusion
from mcp_connector.tools import withhold

BASE = "http://nc.test"


def test_the_unavailable_error_is_the_same_for_every_call() -> None:
    first = withhold.unavailable_error()
    second = withhold.unavailable_error()

    assert (first.message, first.hint, first.reason) == (
        second.message,
        second.hint,
        second.reason,
    )
    assert first is not second
    assert first.reason == REASON_GUARD_TRIPPED
    assert first.message == withhold.EXCLUSION_UNAVAILABLE


def test_the_wording_names_neither_a_path_nor_an_id() -> None:
    assert "/" not in withhold.EXCLUSION_UNAVAILABLE
    assert re.search(r"[0-9]", withhold.EXCLUSION_UNAVAILABLE) is None
    assert "kein-ki" in withhold.EXCLUSION_UNAVAILABLE


@pytest.mark.parametrize("key", ["provider", "source"])
def test_the_degraded_entry_follows_the_key_of_the_family(key: str) -> None:
    assert withhold.degraded_entry(key) == {
        key: "exclusion",
        "reason": withhold.EXCLUSION_UNAVAILABLE,
    }


def test_a_files_entry_carries_id_and_path() -> None:
    entry = {
        "title": "x.pdf",
        "resourceUrl": f"{BASE}/index.php/f/5001",
        "attributes": {"fileId": "5001", "path": "rtc/x.pdf"},
    }

    assert withhold.file_refs(BASE, "files", entry) == withhold.FileRef(
        fileid="5001", path="/rtc/x.pdf", file_bearing=True
    )


def test_a_findling_entry_carries_the_id_only() -> None:
    entry = {
        "title": "Vertrag.pdf",
        "subline": "... Kündigungsfrist ...",
        "resourceUrl": "/index.php/f/5002",
        "attributes": {"fileId": "5002"},
    }

    assert withhold.file_refs(BASE, "findling", entry) == withhold.FileRef(
        fileid="5002", path=None, file_bearing=True
    )


def test_a_comments_entry_is_read_from_the_file_link() -> None:
    entry = {"title": "a comment", "resourceUrl": f"{BASE}/index.php/f/5003", "attributes": []}

    refs = withhold.file_refs(BASE, "comments", entry)

    assert refs == withhold.FileRef(fileid="5003", path=None, file_bearing=True)


def test_a_notes_entry_carries_the_note_id_as_file_id() -> None:
    entry = {"title": "Einkauf", "resourceUrl": "/index.php/apps/notes/note/933"}

    assert withhold.file_refs(BASE, "notes", entry) == withhold.FileRef(
        fileid="933", path=None, file_bearing=True
    )


def test_a_deck_entry_is_not_file_bearing() -> None:
    entry = {"title": "Card", "resourceUrl": f"{BASE}/index.php/apps/deck/card/17"}

    refs = withhold.file_refs(BASE, "search-deck-card-board", entry)

    assert refs == withhold.FileRef(fileid=None, path=None, file_bearing=False)


def test_a_findling_door_entry_without_a_file_is_not_file_bearing() -> None:
    entry = {"title": "Findling öffnen", "resourceUrl": "/index.php/apps/findling/"}

    refs = withhold.file_refs(BASE, "findling", entry)

    assert refs == withhold.FileRef(fileid=None, path=None, file_bearing=False)


@pytest.mark.parametrize("raw", [42, None, ["a"]])
def test_a_path_that_is_no_string_stays_file_bearing_without_a_path(raw: object) -> None:
    entry = {"resourceUrl": "/index.php/f/5004", "attributes": {"fileId": "5004", "path": raw}}

    refs = withhold.file_refs(BASE, "files", entry)

    assert refs == withhold.FileRef(fileid="5004", path=None, file_bearing=True)


@pytest.mark.parametrize("raw", ["../x", "A/../x", "A//x", "A/./x", "A\\x", "A\x01x"])
def test_a_path_that_is_not_plain_becomes_none(raw: str) -> None:
    entry = {"attributes": {"path": raw}}

    refs = withhold.file_refs(BASE, "findling", entry)

    assert refs.path is None
    assert refs.file_bearing is True


def test_a_non_ascii_file_id_is_not_an_id() -> None:
    entry = {"attributes": {"fileId": "٤٢"}}

    refs = withhold.file_refs(BASE, "findling", entry)

    assert refs.fileid is None
    assert refs.file_bearing is True  # the attribute is there, so the entry is withheld


def test_needs_paths_follows_the_sandbox_and_tagged_folders(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(config.ENV_FILES_ROOT, raising=False)
    files_only = exclusion.TagScope("active", fileids=frozenset({"7"}))
    folders = exclusion.TagScope("active", paths=frozenset({"/A"}), has_folders=True)

    assert withhold.needs_paths(exclusion.UNTAGGED) is False
    assert withhold.needs_paths(files_only) is False
    assert withhold.needs_paths(folders) is True

    monkeypatch.setenv(config.ENV_FILES_ROOT, "/Shared/KI")
    assert withhold.needs_paths(exclusion.UNTAGGED) is True
