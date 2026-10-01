"""The output cap that all four converters share.

A small file can expand into a very long text. The converters write through :class:`Output`,
which stops at :data:`MAX_OUTPUT_CHARS` and ends the text with one note. Four slices of the
largest size ``files_read_as_markdown`` answers fit below the cap.
"""

__all__ = ["MAX_OUTPUT_CHARS", "Output"]

MAX_OUTPUT_CHARS = 4 * 2097152


class Output:
    """Markdown lines up to the cap. After the cap, ``full`` is set and lines are ignored."""

    def __init__(self) -> None:
        self._lines: list[str] = []
        self._length = 0
        self.full = False

    def add(self, line: str) -> None:
        if self.full:
            return
        room = max(MAX_OUTPUT_CHARS - self._length, 0)
        if len(line) > room:
            if room:
                self._lines.append(line[:room])
            self._lines.extend(["", f"(output truncated at {MAX_OUTPUT_CHARS} characters)"])
            self.full = True
            return
        self._lines.append(line)
        self._length += len(line) + 1

    def extend(self, lines: list[str]) -> None:
        for line in lines:
            self.add(line)

    def text(self) -> str:
        return "\n".join(self._lines).strip() + "\n"
