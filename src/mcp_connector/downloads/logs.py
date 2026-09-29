"""Keep download tokens out of the uvicorn access log (same shape as entry_oauth's filter)."""

import logging

_PREFIX = "/dl/"


class RedactDownloadToken(logging.Filter):
    """Mask download tokens in uvicorn access logs.

    uvicorn logs every request with its full path. The download token is a single-use secret
    carried in the path `/dl/<token>`, so this filter keeps the path and replaces the token
    with its first 4 characters and an ellipsis. Other paths are left as they are.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if isinstance(args, tuple) and len(args) >= 3 and isinstance(args[2], str):
            path = args[2]
            if path.startswith(_PREFIX):
                token = path[len(_PREFIX) :].split("?", 1)[0]
                record.args = (*args[:2], f"{_PREFIX}{token[:4]}…", *args[3:])
        return True


def redact_download_tokens() -> None:
    """Install :class:`RedactDownloadToken` on uvicorn's access logger, once."""
    access = logging.getLogger("uvicorn.access")
    if not any(isinstance(item, RedactDownloadToken) for item in access.filters):
        access.addFilter(RedactDownloadToken())
