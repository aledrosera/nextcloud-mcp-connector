"""Conversion runs in a worker subprocess: memory limit, wall-clock timeout, kill, and slots.

A thread cannot be cancelled and shares the server's memory. The worker process can be
killed, and an address-space limit inside it turns a hostile document into a MemoryError
instead of an out-of-memory server. These tests hold both bounds and the slot count.
"""

import asyncio
import io
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from mcp_connector import documents
from mcp_connector.documents import docx as docx_conv
from mcp_connector.documents import worker
from mcp_connector.errors import REASON_GUARD_TRIPPED, ToolError

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "documents"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
LINUX_ONLY = pytest.mark.skipif(sys.platform != "linux", reason="RLIMIT_AS is enforced on Linux")


def _python(code: str) -> list[str]:
    return [sys.executable, "-c", code]


@pytest.mark.anyio
async def test_convert_answers_from_the_worker_what_convert_sync_answers_in_process() -> None:
    data = (FIXTURES / "sample.docx").read_bytes()
    result = await documents.convert(data, DOCX, "/Docs/sample.docx")
    assert result == documents.convert_sync(data, DOCX, "/Docs/sample.docx")


def test_the_worker_answers_a_refusal_as_json_and_exits_cleanly() -> None:
    header = json.dumps({"content_type": DOCX, "name": "/Docs/a.docx"}).encode() + b"\n"
    result = subprocess.run(  # noqa: S603 - fixed command
        [sys.executable, "-m", documents.WORKER_MODULE],
        input=header + b"not a zip at all",
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["error"]["message"] == "/Docs/a.docx is not a readable Office file."
    assert payload["error"]["guard"] is False


@pytest.mark.anyio
async def test_a_worker_that_does_not_finish_in_time_is_killed_and_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    pid_file = tmp_path / "pid"
    code = (
        "import os, pathlib, time\n"
        f"pathlib.Path({str(pid_file)!r}).write_text(str(os.getpid()))\n"
        "time.sleep(30)\n"
    )
    monkeypatch.setattr(documents, "TIMEOUT_SECONDS", 0.5)
    monkeypatch.setattr(documents, "_command", lambda: _python(code))

    with pytest.raises(ToolError) as info:
        await documents.convert(b"x", DOCX, "/Docs/a.docx")

    assert info.value.reason == REASON_GUARD_TRIPPED
    assert "longer than 0.5 seconds" in info.value.message
    assert "/Docs/a.docx" in info.value.message
    if sys.platform != "win32":
        # os.kill(pid, 0) is a liveness probe on POSIX only.
        pid = int(pid_file.read_text())
        with pytest.raises(ProcessLookupError):
            os.kill(pid, 0)


@pytest.mark.anyio
async def test_a_worker_that_dies_becomes_one_refusal_naming_file_and_format(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(documents, "_command", lambda: _python("import sys; sys.exit(3)"))
    with pytest.raises(ToolError) as info:
        await documents.convert(b"x", DOCX, "/Docs/a.docx")
    assert info.value.message == "/Docs/a.docx could not be read as docx."


@pytest.mark.anyio
async def test_a_worker_that_answers_garbage_becomes_the_same_refusal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(documents, "_command", lambda: _python("print('not json')"))
    with pytest.raises(ToolError) as info:
        await documents.convert(b"x", DOCX, "/Docs/a.docx")
    assert info.value.message == "/Docs/a.docx could not be read as docx."


@pytest.mark.anyio
async def test_the_worker_does_not_inherit_the_server_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_SECRET", "must-not-reach-the-parser")
    code = (
        "import json, os, sys\n"
        "sys.stdout.write(json.dumps({'markdown': ' '.join(sorted(os.environ)), "
        "'format': 'docx'}))\n"
    )
    monkeypatch.setattr(documents, "_command", lambda: _python(code))
    result = await documents.convert(b"", DOCX, "/Docs/a.docx")
    assert "APP_SECRET" not in result.markdown
    assert "PATH" in result.markdown


def test_a_memory_error_in_a_converter_is_a_guard_refusal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(_data: bytes) -> str:
        raise MemoryError

    monkeypatch.setattr(docx_conv, "to_markdown", boom)
    with pytest.raises(ToolError) as info:
        documents.convert_sync((FIXTURES / "sample.docx").read_bytes(), DOCX, "/Docs/a.docx")
    assert info.value.reason == REASON_GUARD_TRIPPED
    assert "memory" in info.value.message
    assert "/Docs/a.docx" in info.value.message


def test_the_debug_log_names_the_exception_class_and_not_the_file(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def boom(_data: bytes) -> str:
        raise ValueError("detail")

    monkeypatch.setattr(docx_conv, "to_markdown", boom)
    with caplog.at_level("DEBUG", logger="mcp_connector.documents"), pytest.raises(ToolError):
        documents.convert_sync((FIXTURES / "sample.docx").read_bytes(), DOCX, "/Docs/a.docx")
    assert "ValueError" in caplog.text
    assert "/Docs/a.docx" not in caplog.text
    assert "detail" not in caplog.text


def test_without_the_resource_module_the_limit_is_skipped_and_said_so(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Windows has no ``resource``; the worker must still run, bounded by the timeout alone.
    monkeypatch.setattr(worker, "resource", None)
    assert worker.apply_memory_limit() is False


def test_the_worker_module_imports_without_the_resource_module() -> None:
    code = (
        "import sys\n"
        "sys.modules['resource'] = None\n"
        "from mcp_connector.documents import worker\n"
        "assert worker.resource is None\n"
    )
    result = subprocess.run(  # noqa: S603 - fixed command
        _python(code), capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr


def test_the_worker_environment_passes_systemroot_through_when_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Python on Windows does not start without SYSTEMROOT (WinError 10106).
    monkeypatch.setenv("SYSTEMROOT", r"C:\Windows")
    monkeypatch.setenv("APP_SECRET", "must-not-reach-the-parser")
    env = documents._environment()
    assert env["SYSTEMROOT"] == r"C:\Windows"
    assert "APP_SECRET" not in env
    monkeypatch.delenv("SYSTEMROOT")
    assert "SYSTEMROOT" not in documents._environment()


@pytest.mark.anyio
async def test_killing_a_worker_that_just_exited_is_not_an_error() -> None:
    class Exited:
        returncode = 0

        def kill(self) -> None:
            raise ProcessLookupError

        async def wait(self) -> int:
            return 0

    class Running:
        returncode = None
        killed = False

        def kill(self) -> None:
            self.killed = True
            self.returncode = -9

        async def wait(self) -> int:
            return -9

    await documents._kill(Exited())
    running = Running()
    await documents._kill(running)
    assert running.killed


@LINUX_ONLY
def test_the_memory_limit_stops_an_allocation_above_it() -> None:
    code = (
        "from mcp_connector.documents import worker\n"
        "assert worker.apply_memory_limit(256 * 1024 * 1024)\n"
        "block = bytearray(400 * 1024 * 1024)\n"
    )
    result = subprocess.run(  # noqa: S603 - fixed command
        _python(code), capture_output=True, text=True, check=False
    )
    assert result.returncode != 0
    assert "MemoryError" in result.stderr


def _bloated_docx(part_bytes: int) -> bytes:
    """The reviewer's case: a ~100 KB file whose four parsed parts each inflate to part_bytes.

    Every part carries its real content type and is reached through the document's
    relationships, so python-docx parses all four with lxml at package open. Empty elements
    are the densest DOM per byte: 6 bytes of XML become one node of well over 100.
    """
    ns = b'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
    body = b"<w:p/>" * (part_bytes // 6)
    wp = b"application/vnd.openxmlformats-officedocument.wordprocessingml."
    rel = b"http://schemas.openxmlformats.org/officeDocument/2006/relationships/"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            b'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            b'<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.'
            b'relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>'
            b'<Override PartName="/word/document.xml" ContentType="' + wp + b'document.main+xml"/>'
            b'<Override PartName="/word/styles.xml" ContentType="' + wp + b'styles+xml"/>'
            b'<Override PartName="/word/numbering.xml" ContentType="' + wp + b'numbering+xml"/>'
            b'<Override PartName="/word/settings.xml" ContentType="' + wp + b'settings+xml"/>'
            b"</Types>",
        )
        archive.writestr(
            "_rels/.rels",
            b'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            b'<Relationship Id="rId1" Type="'
            + rel
            + b'officeDocument" Target="word/document.xml"/>'
            b"</Relationships>",
        )
        archive.writestr(
            "word/_rels/document.xml.rels",
            b'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            b'<Relationship Id="rId1" Type="' + rel + b'styles" Target="styles.xml"/>'
            b'<Relationship Id="rId2" Type="' + rel + b'numbering" Target="numbering.xml"/>'
            b'<Relationship Id="rId3" Type="' + rel + b'settings" Target="settings.xml"/>'
            b"</Relationships>",
        )
        archive.writestr(
            "word/document.xml",
            b"<w:document " + ns + b"><w:body>" + body + b"</w:body></w:document>",
        )
        for part in ("styles", "numbering", "settings"):
            tag = part.encode()
            archive.writestr(
                f"word/{part}.xml", b"<w:" + tag + b" " + ns + b">" + body + b"</w:" + tag + b">"
            )
    return buffer.getvalue()


@LINUX_ONLY
@pytest.mark.anyio
async def test_an_office_file_that_inflates_past_the_memory_limit_is_refused() -> None:
    # Measured in the Linux image: without the limit this file converts in 12.7 s at a peak
    # of 977 MB; with it, lxml's allocation fails in 0.4 s at 500 MB. lxml reports the failed
    # allocation as XMLSyntaxError and not as MemoryError, so the refusal is the one for an
    # unreadable file. The bound holds either way; only the audit reason is less precise.
    data = _bloated_docx(9 * 1024 * 1024)
    assert len(data) < 200 * 1024
    with pytest.raises(ToolError) as info:
        await documents.convert(data, DOCX, "/Docs/bloated.docx")
    assert info.value.message in {
        "/Docs/bloated.docx could not be read as docx.",
        "/Docs/bloated.docx needs more memory to convert than this server allows.",
    }


@pytest.mark.anyio
async def test_slots_admit_two_conversions_and_queue_the_third() -> None:
    entered: list[int] = []
    release = asyncio.Event()

    async def hold(number: int) -> None:
        async with documents.slot():
            entered.append(number)
            await release.wait()

    tasks = [asyncio.create_task(hold(n)) for n in range(3)]
    await asyncio.sleep(0.05)
    assert len(entered) == documents.MAX_CONCURRENT == 2
    release.set()
    await asyncio.gather(*tasks)
    assert sorted(entered) == [0, 1, 2]


def test_the_slot_count_and_the_bounds_are_the_documented_numbers() -> None:
    assert documents.MAX_CONCURRENT == 2
    assert documents.TIMEOUT_SECONDS == 30
    assert worker.MAX_MEMORY_BYTES == 512 * 1024 * 1024
