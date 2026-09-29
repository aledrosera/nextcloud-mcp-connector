"""Task 10: an event carries its description and its calendar's display name, and a mail
links directly to its message in the Nextcloud Mail app instead of the app's front page."""

import datetime as dt

import pytest

from mcp_connector.nextcloud.clients import caldav
from mcp_connector.tools import chatgpt

pytestmark = pytest.mark.anyio

ICS = (
    "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\nUID:u1\r\nSUMMARY:Visita\r\n"
    "DTSTART:20260930T070000Z\r\nDTEND:20260930T071500Z\r\nLOCATION:Studio\r\n"
    "DESCRIPTION:Portare i referti\\, grazie\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"
)


def test_parse_ics_reads_the_description():
    events = caldav.parse_ics(ICS, calendar_uri="personal", object_name="x.ics")
    assert events[0]["description"] == "Portare i referti, grazie"


async def test_fetch_event_shows_description_location_and_calendar_name(monkeypatch):
    async def fake_discover(client, creds):
        return [caldav.CalendarRef("personal", "Personale")]

    async def fake_get_event(client, creds, calendar_uri, object_name, calendar=None):
        return [
            {
                "id": "x",
                "uid": "u1",
                "summary": "Visita",
                "all_day": False,
                "start": dt.datetime(2026, 9, 30, 7, tzinfo=dt.UTC),
                "end": dt.datetime(2026, 9, 30, 7, 15, tzinfo=dt.UTC),
                "location": "Studio",
                "description": "Portare i referti, grazie",
                "calendar": calendar or calendar_uri,
            }
        ]

    monkeypatch.setattr(chatgpt.caldav, "discover_calendars", fake_discover)
    monkeypatch.setattr(chatgpt.caldav, "get_event", fake_get_event)
    clients = type(
        "C", (), {"client": None, "creds": type("K", (), {"base_url": "https://cloud.example"})()}
    )()
    result = await chatgpt._fetch_event(clients, "personal", "x.ics")  # pyright: ignore[reportArgumentType]
    assert "Calendar: Personale" in result["text"]
    assert "Location: Studio" in result["text"]
    assert "Description: Portare i referti, grazie" in result["text"]


async def test_fetch_mail_links_the_message(monkeypatch):
    async def fake_require(clients, app):
        return None

    async def fake_get_message(client, creds, message_id):
        return {
            "subject": "Ciao",
            "body": "<p>testo</p>",
            "mailboxId": 6,
            "databaseId": 21,
            "dateInt": 1790000000,
        }, False

    monkeypatch.setattr(chatgpt.capabilities, "require_app", fake_require)
    monkeypatch.setattr(chatgpt.mail_client, "get_message", fake_get_message)
    clients = type(
        "C", (), {"client": None, "creds": type("K", (), {"base_url": "https://cloud.example"})()}
    )()
    result = await chatgpt._fetch_mail(clients, "21")  # pyright: ignore[reportArgumentType]
    assert result["url"] == "https://cloud.example/index.php/apps/mail/box/6/thread/21"


async def test_fetch_event_survives_discover_calendars_tool_error(monkeypatch):
    from mcp_connector.errors import ToolError as McpToolError

    async def fake_discover(client, creds):
        raise McpToolError(message="Network error", hint="Retry later")

    async def fake_get_event(client, creds, calendar_uri, object_name, calendar=None):
        return [
            {
                "id": "x",
                "uid": "u1",
                "summary": "Visita",
                "all_day": False,
                "start": dt.datetime(2026, 9, 30, 7, tzinfo=dt.UTC),
                "end": dt.datetime(2026, 9, 30, 7, 15, tzinfo=dt.UTC),
                "location": "Studio",
                "description": "Short desc",
                "calendar": calendar or calendar_uri,
            }
        ]

    monkeypatch.setattr(chatgpt.caldav, "discover_calendars", fake_discover)
    monkeypatch.setattr(chatgpt.caldav, "get_event", fake_get_event)
    clients = type(
        "C", (), {"client": None, "creds": type("K", (), {"base_url": "https://cloud.example"})()}
    )()
    result = await chatgpt._fetch_event(clients, "personal", "x.ics")  # pyright: ignore[reportArgumentType]
    assert "Calendar: personal" in result["text"]


async def test_fetch_event_survives_discover_calendars_connect_error(monkeypatch):
    import httpx

    async def fake_discover(client, creds):
        raise httpx.ConnectError("Connection failed")

    async def fake_get_event(client, creds, calendar_uri, object_name, calendar=None):
        return [
            {
                "id": "x",
                "uid": "u1",
                "summary": "Visita",
                "all_day": False,
                "start": dt.datetime(2026, 9, 30, 7, tzinfo=dt.UTC),
                "end": dt.datetime(2026, 9, 30, 7, 15, tzinfo=dt.UTC),
                "location": "Studio",
                "description": "Short desc",
                "calendar": calendar or calendar_uri,
            }
        ]

    monkeypatch.setattr(chatgpt.caldav, "discover_calendars", fake_discover)
    monkeypatch.setattr(chatgpt.caldav, "get_event", fake_get_event)
    clients = type(
        "C", (), {"client": None, "creds": type("K", (), {"base_url": "https://cloud.example"})()}
    )()
    result = await chatgpt._fetch_event(clients, "personal", "x.ics")  # pyright: ignore[reportArgumentType]
    assert "Calendar: personal" in result["text"]


async def test_fetch_event_truncates_long_description(monkeypatch):
    async def fake_discover(client, creds):
        return [caldav.CalendarRef("personal", "Personale")]

    long_description = "x" * 20000

    async def fake_get_event(client, creds, calendar_uri, object_name, calendar=None):
        return [
            {
                "id": "x",
                "uid": "u1",
                "summary": "Visita",
                "all_day": False,
                "start": dt.datetime(2026, 9, 30, 7, tzinfo=dt.UTC),
                "end": dt.datetime(2026, 9, 30, 7, 15, tzinfo=dt.UTC),
                "location": "Studio",
                "description": long_description,
                "calendar": calendar or calendar_uri,
            }
        ]

    monkeypatch.setattr(chatgpt.caldav, "discover_calendars", fake_discover)
    monkeypatch.setattr(chatgpt.caldav, "get_event", fake_get_event)
    clients = type(
        "C", (), {"client": None, "creds": type("K", (), {"base_url": "https://cloud.example"})()}
    )()
    result = await chatgpt._fetch_event(clients, "personal", "x.ics")  # pyright: ignore[reportArgumentType]
    assert chatgpt.FINAL_TRUNCATION in result["text"]
    assert result["metadata"]["truncated"] == "true"
    # Verify the Description line doesn't exceed 8 KiB
    text_lines = result["text"].split("\n")
    desc_lines = [line for line in text_lines if line.startswith("Description:")]
    assert desc_lines
    assert len(desc_lines[0].encode("utf-8")) <= 8 * 1024 + 100  # 100 bytes for marker


async def test_fetch_event_short_description_no_truncated_key(monkeypatch):
    async def fake_discover(client, creds):
        return [caldav.CalendarRef("personal", "Personale")]

    async def fake_get_event(client, creds, calendar_uri, object_name, calendar=None):
        return [
            {
                "id": "x",
                "uid": "u1",
                "summary": "Visita",
                "all_day": False,
                "start": dt.datetime(2026, 9, 30, 7, tzinfo=dt.UTC),
                "end": dt.datetime(2026, 9, 30, 7, 15, tzinfo=dt.UTC),
                "location": "Studio",
                "description": "Short description",
                "calendar": calendar or calendar_uri,
            }
        ]

    monkeypatch.setattr(chatgpt.caldav, "discover_calendars", fake_discover)
    monkeypatch.setattr(chatgpt.caldav, "get_event", fake_get_event)
    clients = type(
        "C", (), {"client": None, "creds": type("K", (), {"base_url": "https://cloud.example"})()}
    )()
    result = await chatgpt._fetch_event(clients, "personal", "x.ics")  # pyright: ignore[reportArgumentType]
    assert "truncated" not in result["metadata"]
