"""The shared output cap: lines up to the cap, then one note, then nothing."""

import pytest

from mcp_connector.documents import limits


def test_a_line_that_fills_the_cap_exactly_ends_the_output_cleanly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(limits, "MAX_OUTPUT_CHARS", 10)
    out = limits.Output()
    out.add("123456789")
    out.add("next line")
    out.add("ignored")

    assert out.full
    assert out.text() == "123456789\n\n(output truncated at 10 characters)\n"


def test_one_huge_line_is_cut_to_the_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(limits, "MAX_OUTPUT_CHARS", 10)
    out = limits.Output()
    out.add("x" * 1000)

    assert out.text() == "xxxxxxxxxx\n\n(output truncated at 10 characters)\n"
