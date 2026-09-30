import logging
import logging.config

import uvicorn.config

from mcp_connector.downloads import logs


def record(path: str) -> logging.LogRecord:
    return logging.LogRecord(
        "uvicorn.access",
        logging.INFO,
        __file__,
        1,
        '%s - "%s %s HTTP/%s" %d',
        ("1.2.3.4:5", "GET", path, "1.1", 200),
        None,
    )


def test_token_is_masked():
    item = record("/dl/AbCdEfGhIjKlMnOpQrStUvWxYz0123456789_-abcd")
    assert logs.RedactDownloadToken().filter(item) is True
    assert isinstance(item.args, tuple)
    assert item.args[2] == "/dl/AbCd…"
    assert "AbCdEfGh" not in item.getMessage()


def test_other_paths_are_untouched():
    item = record("/mcp")
    logs.RedactDownloadToken().filter(item)
    assert isinstance(item.args, tuple)
    assert item.args[2] == "/mcp"


def test_install_is_idempotent():
    logs.redact_download_tokens()
    logs.redact_download_tokens()
    access = logging.getLogger("uvicorn.access")
    assert sum(isinstance(f, logs.RedactDownloadToken) for f in access.filters) == 1


def test_upload_token_is_masked():
    item = record("/ul/AbCdEfGhIjKlMnOpQrStUvWxYz0123456789_-abcd")
    logs.RedactDownloadToken().filter(item)
    assert isinstance(item.args, tuple)
    assert item.args[2] == "/ul/AbCd…"


def test_filter_survives_dictconfig():
    """The filter must survive uvicorn.run's logging config initialization."""
    logs.redact_download_tokens()
    logging.config.dictConfig(uvicorn.config.LOGGING_CONFIG)
    access = logging.getLogger("uvicorn.access")
    assert any(isinstance(f, logs.RedactDownloadToken) for f in access.filters)
