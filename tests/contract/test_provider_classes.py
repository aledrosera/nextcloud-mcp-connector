"""The provider freeze of review WR-02 (phase 28): every known search provider has a class.

The live half lists the providers of a running instance
(``tests/integration/test_provider_classes_live.py``); this half holds the table against the
code and proves that the check turns red where it has to.
"""

import provider_classes as pc
import pytest

from mcp_connector import provider_map
from mcp_connector.tools import search as search_tools


def test_every_known_provider_has_exactly_one_class_and_a_reason() -> None:
    known = [*pc.FILE_REFERENCE, *pc.ROOM_SCREENED, *pc.NO_FILE]
    assert pc.provider_findings(known) == []
    assert pc.unclassified(provider_map.PROVIDER_KINDS) == []


def test_the_room_class_is_what_search_screens_against_the_conversation_list() -> None:
    assert set(pc.ROOM_SCREENED) == set(search_tools._ROOM_SCREENED_PROVIDERS)


def test_an_unknown_provider_turns_the_gate_red() -> None:
    """The D-28-04 counter proof: a provider that brings its own file naming is not waved on."""
    findings = pc.provider_findings(["files", "collectives"])
    assert findings == ["unclassified: collectives"]


def test_a_provider_in_two_classes_turns_the_gate_red(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(pc.NO_FILE, "files", "Pretends the files provider named no file.")
    assert "in more than one class: files (FILE_REFERENCE, NO_FILE)" in pc.provider_findings([])


def test_a_short_reason_turns_the_gate_red(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(pc.NO_FILE, "mail", "safe")
    assert "reason shorter than 20 characters: NO_FILE[mail]" in pc.provider_findings([])


def test_a_room_class_that_drifts_from_search_turns_the_gate_red(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(search_tools, "_ROOM_SCREENED_PROVIDERS", frozenset({"talk-conversations"}))
    assert any(item.startswith("room class differs") for item in pc.provider_findings([]))
