"""The comparison and scan helpers of phase 28, proven on hand-built answers."""

import base64

from mcp.types import BlobResourceContents, CallToolResult, EmbeddedResource, TextContent
from result_shapes import leaks, normalised, requested_forms, surfaces


def _text(text: str) -> CallToolResult:
    return CallToolResult(content=[TextContent(type="text", text=text)])


def test_a_short_id_never_touches_a_longer_number() -> None:
    out = normalised(_text("id 12, other 1234, size 120"), "12")
    assert "id <ID>," in out
    assert "1234" in out
    assert "size 120" in out


def test_the_longest_path_is_replaced_first() -> None:
    assert requested_forms("/a/b/c.txt") == ("/a/b/c.txt", "/a/b", "/a")
    out = normalised(_text("missing /a/b/c.txt in /a/b"), "/a/b/c.txt")
    assert "missing <ID> in <ID>" in out
    assert "c.txt" not in out


def test_a_fetch_id_also_replaces_the_bare_id() -> None:
    assert set(requested_forms("file:22215")) == {"file:22215", "22215"}
    out = normalised(_text("file:22215 not found, fileid 22215"), "file:22215")
    assert "22215" not in out
    assert "<ID> not found, fileid <ID>" in out


def test_short_segments_of_a_fetch_id_stay() -> None:
    forms = requested_forms("message:abcd1234:7")
    assert "abcd1234:7" in forms
    assert "abcd1234" in forms
    assert "7" not in forms


def test_surfaces_decode_blob_and_uri() -> None:
    result = CallToolResult(
        content=[
            EmbeddedResource(
                type="resource",
                resource=BlobResourceContents(
                    uri="nextcloud://files/dir%20x/canary%2Dname.bin",
                    blob=base64.b64encode(b"inside markerzq9 body").decode(),
                ),
            )
        ],
        structured_content={"title": "plain"},
    )
    found = surfaces(result)
    assert '{"title": "plain"}' in found
    assert "nextcloud://files/dir x/canary-name.bin" in found
    assert "inside markerzq9 body" in found


def test_leaks_find_the_marker_only_where_it_stands() -> None:
    result = CallToolResult(
        content=[
            TextContent(type="text", text="clean answer"),
            TextContent(type="text", text="x" * 300 + "markerzq9"),
        ],
        structured_content={"name": "markerzq9.txt"},
    )
    found = leaks(result, "markerzq9")
    assert len(found) == 2
    assert all(len(surface) <= 200 for surface in found)
    assert leaks(_text("clean answer"), "markerzq9") == []
