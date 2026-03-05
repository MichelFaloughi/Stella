"""
Tests for tools/calendar.py.

All Google Calendar API calls are intercepted by patching get_service().
The underlying tool functions are called via tool.func() to bypass the
LangChain tool wrapper and test the logic directly.
"""
from unittest.mock import MagicMock, call, patch

import pytest

from tools.calendar import (
    create_event,
    delete_event,
    find_events,
    get_current_datetime,
    list_events_between,
    list_events_for_day,
    update_event,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_event(
    event_id="evt1",
    summary="Team Meeting",
    start=None,
    end=None,
    html_link="https://calendar.google.com/event/evt1",
    location=None,
):
    return {
        "id": event_id,
        "summary": summary,
        "start": start or {"dateTime": "2026-03-05T14:00:00-05:00", "timeZone": "America/New_York"},
        "end": end or {"dateTime": "2026-03-05T15:00:00-05:00", "timeZone": "America/New_York"},
        "htmlLink": html_link,
        "location": location,
    }


# ---------------------------------------------------------------------------
# create_event
# ---------------------------------------------------------------------------

class TestCreateEvent:
    def test_basic_creation_returns_key_fields(self, mock_calendar_service):
        created = _make_event()
        mock_calendar_service.events.return_value.insert.return_value.execute.return_value = created

        result = create_event.func(
            event_name="Team Meeting",
            start={"dateTime": "2026-03-05T14:00:00", "timeZone": "America/New_York"},
            end={"dateTime": "2026-03-05T15:00:00", "timeZone": "America/New_York"},
        )

        assert result["event_id"] == "evt1"
        assert result["summary"] == "Team Meeting"
        assert result["htmlLink"] == "https://calendar.google.com/event/evt1"

    def test_timezone_added_when_missing_from_datetime(self, mock_calendar_service):
        """If caller omits timeZone on a dateTime, the default tz is injected."""
        mock_calendar_service.events.return_value.insert.return_value.execute.return_value = _make_event()

        create_event.func(
            event_name="Standup",
            start={"dateTime": "2026-03-05T09:00:00"},
            end={"dateTime": "2026-03-05T09:30:00"},
        )

        insert_call = mock_calendar_service.events.return_value.insert.call_args
        body = insert_call.kwargs["body"]
        assert body["start"]["timeZone"] == "America/New_York"
        assert body["end"]["timeZone"] == "America/New_York"

    def test_timezone_not_overwritten_when_already_present(self, mock_calendar_service):
        mock_calendar_service.events.return_value.insert.return_value.execute.return_value = _make_event()

        create_event.func(
            event_name="Standup",
            start={"dateTime": "2026-03-05T09:00:00", "timeZone": "Europe/London"},
            end={"dateTime": "2026-03-05T09:30:00", "timeZone": "Europe/London"},
        )

        body = mock_calendar_service.events.return_value.insert.call_args.kwargs["body"]
        assert body["start"]["timeZone"] == "Europe/London"

    def test_optional_fields_included_when_provided(self, mock_calendar_service):
        mock_calendar_service.events.return_value.insert.return_value.execute.return_value = _make_event()

        create_event.func(
            event_name="All Hands",
            start={"dateTime": "2026-03-05T10:00:00", "timeZone": "America/New_York"},
            end={"dateTime": "2026-03-05T11:00:00", "timeZone": "America/New_York"},
            location="Conference Room A",
            description="Q1 review",
            attendees=["alice@example.com", "bob@example.com"],
        )

        body = mock_calendar_service.events.return_value.insert.call_args.kwargs["body"]
        assert body["location"] == "Conference Room A"
        assert body["description"] == "Q1 review"
        assert body["attendees"] == [
            {"email": "alice@example.com"},
            {"email": "bob@example.com"},
        ]

    def test_optional_fields_absent_when_not_provided(self, mock_calendar_service):
        mock_calendar_service.events.return_value.insert.return_value.execute.return_value = _make_event()

        create_event.func(
            event_name="Solo work",
            start={"dateTime": "2026-03-05T10:00:00", "timeZone": "America/New_York"},
            end={"dateTime": "2026-03-05T11:00:00", "timeZone": "America/New_York"},
        )

        body = mock_calendar_service.events.return_value.insert.call_args.kwargs["body"]
        assert "location" not in body
        assert "description" not in body
        assert "attendees" not in body

    def test_all_day_event_no_timezone_injection(self, mock_calendar_service):
        """date-based (all day) events should not get a timeZone injected."""
        mock_calendar_service.events.return_value.insert.return_value.execute.return_value = _make_event()

        create_event.func(
            event_name="Holiday",
            start={"date": "2026-03-05"},
            end={"date": "2026-03-06"},
        )

        body = mock_calendar_service.events.return_value.insert.call_args.kwargs["body"]
        assert "timeZone" not in body["start"]
        assert "timeZone" not in body["end"]


# ---------------------------------------------------------------------------
# list_events_for_day
# ---------------------------------------------------------------------------

class TestListEventsForDay:
    def test_returns_events_with_correct_shape(self, mock_calendar_service):
        raw = [_make_event()]
        mock_calendar_service.events.return_value.list.return_value.execute.return_value = {
            "items": raw
        }

        result = list_events_for_day.func(date_str="2026-03-05")

        assert result["date"] == "2026-03-05"
        assert result["count"] == 1
        assert result["events"][0]["event_id"] == "evt1"
        assert result["events"][0]["summary"] == "Team Meeting"

    def test_returns_empty_when_no_events(self, mock_calendar_service):
        mock_calendar_service.events.return_value.list.return_value.execute.return_value = {
            "items": []
        }

        result = list_events_for_day.func(date_str="2026-03-05")

        assert result["count"] == 0
        assert result["events"] == []

    def test_timezone_used_in_query(self, mock_calendar_service):
        mock_calendar_service.events.return_value.list.return_value.execute.return_value = {"items": []}

        list_events_for_day.func(date_str="2026-03-05", timezone="Europe/London")

        list_call = mock_calendar_service.events.return_value.list.call_args
        assert "2026-03-05T00:00:00" in list_call.kwargs["timeMin"]


# ---------------------------------------------------------------------------
# list_events_between
# ---------------------------------------------------------------------------

class TestListEventsBetween:
    def test_returns_events_in_range(self, mock_calendar_service):
        raw = [_make_event("evt1"), _make_event("evt2", summary="Lunch")]
        mock_calendar_service.events.return_value.list.return_value.execute.return_value = {
            "items": raw
        }

        result = list_events_between.func(start_date="2026-03-01", end_date="2026-03-07")

        assert result["count"] == 2
        assert result["range"]["start_date"] == "2026-03-01"
        assert result["range"]["end_date"] == "2026-03-07"

    def test_empty_range(self, mock_calendar_service):
        mock_calendar_service.events.return_value.list.return_value.execute.return_value = {"items": []}

        result = list_events_between.func(start_date="2026-03-01", end_date="2026-03-07")

        assert result["count"] == 0
        assert result["events"] == []

    def test_end_date_is_inclusive(self, mock_calendar_service):
        """end_date adds one day so the range is inclusive."""
        mock_calendar_service.events.return_value.list.return_value.execute.return_value = {"items": []}

        list_events_between.func(start_date="2026-03-05", end_date="2026-03-05")

        list_call = mock_calendar_service.events.return_value.list.call_args
        # timeMax must be on March 6 to include all of March 5
        assert "2026-03-06" in list_call.kwargs["timeMax"]


# ---------------------------------------------------------------------------
# find_events
# ---------------------------------------------------------------------------

class TestFindEvents:
    def test_returns_matching_events(self, mock_calendar_service):
        mock_calendar_service.events.return_value.list.return_value.execute.return_value = {
            "items": [_make_event(summary="Gym")]
        }

        result = find_events.func(query="Gym", start_date="2026-03-01", end_date="2026-03-31")

        assert result["query"] == "Gym"
        assert result["count"] == 1
        assert result["events"][0]["summary"] == "Gym"

    def test_no_matches_returns_empty_list(self, mock_calendar_service):
        mock_calendar_service.events.return_value.list.return_value.execute.return_value = {"items": []}

        result = find_events.func(query="Dentist", start_date="2026-03-01", end_date="2026-03-31")

        assert result["count"] == 0
        assert result["events"] == []

    def test_query_forwarded_to_api(self, mock_calendar_service):
        mock_calendar_service.events.return_value.list.return_value.execute.return_value = {"items": []}

        find_events.func(query="Board meeting", start_date="2026-03-01", end_date="2026-03-31")

        list_call = mock_calendar_service.events.return_value.list.call_args
        assert list_call.kwargs["q"] == "Board meeting"


# ---------------------------------------------------------------------------
# delete_event
# ---------------------------------------------------------------------------

class TestDeleteEvent:
    def test_delete_by_event_id(self, mock_calendar_service):
        mock_calendar_service.events.return_value.delete.return_value.execute.return_value = None

        result = delete_event.func(event_id="evt1")

        assert result["deleted"] is True
        assert result["event_id"] == "evt1"
        mock_calendar_service.events.return_value.delete.assert_called_once()

    def test_delete_by_query_single_match(self, mock_calendar_service):
        events_resource = mock_calendar_service.events.return_value
        events_resource.list.return_value.execute.return_value = {"items": [_make_event()]}
        events_resource.delete.return_value.execute.return_value = None

        result = delete_event.func(
            query="Team Meeting",
            start_date="2026-03-05",
            end_date="2026-03-05",
        )

        assert result["deleted"] is True
        assert result["event_id"] == "evt1"

    def test_delete_by_query_no_match(self, mock_calendar_service):
        mock_calendar_service.events.return_value.list.return_value.execute.return_value = {"items": []}

        result = delete_event.func(
            query="Nonexistent",
            start_date="2026-03-05",
            end_date="2026-03-05",
        )

        assert result["deleted"] is False
        assert "No matching" in result["error"]

    def test_delete_by_query_multiple_matches_is_refused(self, mock_calendar_service):
        mock_calendar_service.events.return_value.list.return_value.execute.return_value = {
            "items": [_make_event("evt1"), _make_event("evt2", summary="Team Meeting 2")]
        }

        result = delete_event.func(
            query="Team Meeting",
            start_date="2026-03-05",
            end_date="2026-03-31",
        )

        assert result["deleted"] is False
        assert "Ambiguous" in result["error"]
        assert len(result["matches"]) == 2

    def test_missing_all_params_returns_error(self, mock_calendar_service):
        result = delete_event.func()

        assert result["deleted"] is False
        assert "error" in result

    def test_query_without_dates_returns_error(self, mock_calendar_service):
        result = delete_event.func(query="Gym")

        assert result["deleted"] is False
        assert "error" in result


# ---------------------------------------------------------------------------
# update_event
# ---------------------------------------------------------------------------

class TestUpdateEvent:
    def test_update_by_event_id(self, mock_calendar_service):
        updated = _make_event(summary="Renamed")
        mock_calendar_service.events.return_value.patch.return_value.execute.return_value = updated

        result = update_event.func(
            patch={"summary": "Renamed"},
            event_id="evt1",
        )

        assert result["updated"] is True
        assert result["summary"] == "Renamed"
        mock_calendar_service.events.return_value.patch.assert_called_once()

    def test_update_by_query_single_match(self, mock_calendar_service):
        events_resource = mock_calendar_service.events.return_value
        events_resource.list.return_value.execute.return_value = {"items": [_make_event()]}
        events_resource.patch.return_value.execute.return_value = _make_event(summary="Updated")

        result = update_event.func(
            patch={"summary": "Updated"},
            query="Team Meeting",
            start_date="2026-03-05",
            end_date="2026-03-05",
        )

        assert result["updated"] is True

    def test_update_by_query_no_match(self, mock_calendar_service):
        mock_calendar_service.events.return_value.list.return_value.execute.return_value = {"items": []}

        result = update_event.func(
            patch={"summary": "New"},
            query="Ghost",
            start_date="2026-03-05",
            end_date="2026-03-05",
        )

        assert result["updated"] is False
        assert "No matching" in result["error"]

    def test_update_by_query_multiple_matches_is_refused(self, mock_calendar_service):
        mock_calendar_service.events.return_value.list.return_value.execute.return_value = {
            "items": [_make_event("e1"), _make_event("e2", summary="Meeting 2")]
        }

        result = update_event.func(
            patch={"summary": "New"},
            query="Meeting",
            start_date="2026-03-05",
            end_date="2026-03-31",
        )

        assert result["updated"] is False
        assert "Ambiguous" in result["error"]

    def test_missing_all_params_returns_error(self, mock_calendar_service):
        result = update_event.func(patch={"summary": "New"})

        assert result["updated"] is False
        assert "error" in result

    def test_patch_body_forwarded_to_api(self, mock_calendar_service):
        updated = _make_event()
        mock_calendar_service.events.return_value.patch.return_value.execute.return_value = updated

        patch_body = {"summary": "New Name", "location": "Room 42"}
        update_event.func(patch=patch_body, event_id="evt1")

        patch_call = mock_calendar_service.events.return_value.patch.call_args
        assert patch_call.kwargs["body"] == patch_body
        assert patch_call.kwargs["eventId"] == "evt1"


# ---------------------------------------------------------------------------
# get_current_datetime
# ---------------------------------------------------------------------------

class TestGetCurrentDatetime:
    def test_returns_iso_string(self):
        result = get_current_datetime.func()
        # Should be parseable as an ISO datetime
        from datetime import datetime
        parsed = datetime.fromisoformat(result)
        assert parsed.year >= 2026

    def test_uses_specified_timezone(self):
        result_ny = get_current_datetime.func(tz="America/New_York")
        result_utc = get_current_datetime.func(tz="UTC")
        # Both should be valid ISO strings; offsets will differ
        assert "T" in result_ny
        assert "T" in result_utc
