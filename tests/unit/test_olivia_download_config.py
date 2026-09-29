"""Task 1 (olivia): the configurable lifetime of a download link.

``config.download_ttl_minutes`` reuses ``config._bounded_number`` for the floor and adds its
own ceiling, because a link that never expires is not what AUDIT-06-style bounds exist to
prevent (a link is meant to live minutes, not indefinitely). The admin form field is one more
entry in ``CONFIG_KEYS``/``KEY_TO_ENV``, following the pattern every other admin value here
already uses.
"""

import pytest

from mcp_connector import config
from mcp_connector.exapp import admin_settings, config_values


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(None, 10), ("15", 15), ("1", 1), ("60", 60), ("0", 10), ("61", 10), ("abc", 10), (" 5 ", 5)],
)
def test_download_ttl_minutes_reads_a_bounded_number(raw, expected):
    env = {} if raw is None else {config.ENV_DOWNLOAD_TTL_MINUTES: raw}
    assert config.download_ttl_minutes(env) == expected


def test_admin_form_carries_the_download_ttl_field():
    assert "download_ttl_minutes" in config_values.CONFIG_KEYS
    assert config_values.KEY_TO_ENV["download_ttl_minutes"] == config.ENV_DOWNLOAD_TTL_MINUTES
    scheme = admin_settings.form_scheme({})
    field = next(f for f in scheme["fields"] if f["id"] == "download_ttl_minutes")
    assert field["type"] == "number"
    assert field["default"] == ""
