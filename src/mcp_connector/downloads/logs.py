"""Keep download and upload tokens out of the uvicorn access log.

Same shape as entry_oauth's filter.
"""

import logging

_PREFIXES = ("/dl/", "/ul/")


class RedactDownloadToken(logging.Filter):
    """Mask download and upload tokens in uvicorn access logs.

    uvicorn logs every request with its full path. The download and upload tokens are
    single-use secrets carried in the paths `/dl/<token>` and `/ul/<token>`, so this filter
    keeps the path and replaces the token with its first 4 characters and an ellipsis. Other
    paths are left as they are.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if isinstance(args, tuple) and len(args) >= 3 and isinstance(args[2], str):
            path = args[2]
            for prefix in _PREFIXES:
                if path.startswith(prefix):
                    token = path[len(prefix) :].split("?", 1)[0]
                    record.args = (*args[:2], f"{prefix}{token[:4]}…", *args[3:])
                    break
        return True


def redact_download_tokens() -> None:
    """Install :class:`RedactDownloadToken` on uvicorn's access logger, once."""
    access = logging.getLogger("uvicorn.access")
    if not any(isinstance(item, RedactDownloadToken) for item in access.filters):
        access.addFilter(RedactDownloadToken())
