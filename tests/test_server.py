"""
Tests for server.py.

The LangChain agent is fully mocked so no LLM or Google API calls are made.
Tests cover:
  - Helper functions (_format_event_time, _tool_events_to_frontend,
    _extract_events_from_messages, _extract_emails_from_messages,
    _tool_message_to_email)
  - POST /chat endpoint behaviour
"""
import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Import the app (agent module will initialize with the fake key from conftest)
# ---------------------------------------------------------------------------
import server
from server import (
    _extract_emails_from_messages,
    _extract_events_from_messages,
    _format_event_time,
    _tool_events_to_frontend,
    _tool_message_to_email,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_server_state():
    """
    Reset the in-memory message list between tests so tests don't bleed state.
    """
    original = server.messages[:]
    yield
    server.messages = original[:]


@pytest.fixture
def client():
    return TestClient(server.app)


# ---------------------------------------------------------------------------
# Fake message objects (stand-ins for LangChain message objects)
# ---------------------------------------------------------------------------

class FakeHumanMessage:
    type = "human"
    def __init__(self, content="hi"):
        self.content = content


class FakeAIMessage:
    type = "ai"
    def __init__(self, content="ok"):
        self.content = content


class FakeToolMessage:
    type = "tool"
    def __init__(self, name, content):
        self.name = name
        self.content = content


# ---------------------------------------------------------------------------
# _format_event_time
# ---------------------------------------------------------------------------

class TestFormatEventTime:
    def test_formats_datetime(self):
        result = _format_event_time({"dateTime": "2026-03-05T14:30:00-05:00"})
        assert "2" in result  # hour
        assert "30" in result  # minute
        assert "PM" in result or "AM" in result

    def test_all_day_event_returns_all_day(self):
        result = _format_event_time({"date": "2026-03-05"})
        assert result == "All day"

    def test_empty_dict_returns_empty_string(self):
        assert _format_event_time({}) == ""

    def test_none_returns_empty_string(self):
        assert _format_event_time(None) == ""

    def test_malformed_datetime_falls_back_to_raw(self):
        result = _format_event_time({"dateTime": "not-a-date"})
        assert result == "not-a-date"


# ---------------------------------------------------------------------------
# _tool_events_to_frontend
# ---------------------------------------------------------------------------

class TestToolEventsToFrontend:
    def _make_raw_event(self, summary="Meeting", start_dt="2026-03-05T14:00:00-05:00"):
        return {
            "summary": summary,
            "start": {"dateTime": start_dt},
            "end": {"dateTime": "2026-03-05T15:00:00-05:00"},
            "location": "Room A",
            "htmlLink": "https://calendar.google.com/event/1",
        }

    def test_converts_event_to_frontend_shape(self):
        events = _tool_events_to_frontend([self._make_raw_event()])
        assert len(events) == 1
        ev = events[0]
        assert ev["title"] == "Meeting"
        assert ev["location"] == "Room A"
        assert ev["calendarUrl"] == "https://calendar.google.com/event/1"

    def test_missing_summary_uses_default(self):
        raw = self._make_raw_event()
        raw.pop("summary")
        events = _tool_events_to_frontend([raw])
        assert events[0]["title"] == "(No title)"

    def test_empty_list_returns_empty(self):
        assert _tool_events_to_frontend([]) == []

    def test_none_returns_empty(self):
        assert _tool_events_to_frontend(None) == []

    def test_multiple_events_all_converted(self):
        raw = [self._make_raw_event("A"), self._make_raw_event("B")]
        events = _tool_events_to_frontend(raw)
        assert len(events) == 2
        assert {e["title"] for e in events} == {"A", "B"}


# ---------------------------------------------------------------------------
# _extract_events_from_messages
# ---------------------------------------------------------------------------

class TestExtractEventsFromMessages:
    def _event_payload(self, count=1):
        events = [
            {
                "summary": f"Event {i}",
                "start": {"dateTime": "2026-03-05T10:00:00-05:00"},
                "end": {"dateTime": "2026-03-05T11:00:00-05:00"},
                "htmlLink": f"https://cal.google.com/{i}",
            }
            for i in range(count)
        ]
        return json.dumps({"events": events})

    def test_finds_event_list_tool_result(self):
        messages = [
            FakeHumanMessage("what's on today?"),
            FakeToolMessage("list_events_for_day", self._event_payload(2)),
            FakeAIMessage("Here are your events."),
        ]
        result = _extract_events_from_messages(messages)
        assert len(result) == 2

    def test_uses_last_event_list_result(self):
        """If two event-listing tool messages exist, the last one wins."""
        messages = [
            FakeHumanMessage("show me"),
            FakeToolMessage("list_events_for_day", self._event_payload(1)),
            FakeToolMessage("list_events_between", self._event_payload(3)),
            FakeAIMessage("Done"),
        ]
        result = _extract_events_from_messages(messages)
        assert len(result) == 3

    def test_returns_empty_when_no_tool_messages(self):
        messages = [FakeHumanMessage("hello"), FakeAIMessage("hi")]
        assert _extract_events_from_messages(messages) == []

    def test_handles_dict_format_messages(self):
        """Server initialises messages as dicts; should still work."""
        raw_payload = json.dumps({"events": [
            {
                "summary": "Dict event",
                "start": {"dateTime": "2026-03-05T10:00:00-05:00"},
                "end": {"dateTime": "2026-03-05T11:00:00-05:00"},
                "htmlLink": "https://cal.google.com/1",
            }
        ]})
        messages = [
            {"role": "user", "content": "show me"},
            {"name": "list_events_for_day", "content": raw_payload},
            FakeAIMessage("Here they are"),
        ]
        result = _extract_events_from_messages(messages)
        assert len(result) == 1

    def test_returns_empty_for_malformed_json(self):
        messages = [
            FakeToolMessage("list_events_for_day", "not valid json {{ "),
            FakeAIMessage("ok"),
        ]
        result = _extract_events_from_messages(messages)
        assert result == []


# ---------------------------------------------------------------------------
# _tool_message_to_email
# ---------------------------------------------------------------------------

class TestToolMessageToEmail:
    def _make_get_message_result(
        self,
        msg_id="msg1",
        subject="Hello",
        from_addr="Alice <alice@example.com>",
        date="Thu, 5 Mar 2026 10:00:00 +0000",
        snippet="Hey there",
        label_ids=None,
    ):
        data = {
            "message_id": msg_id,
            "thread_id": "t1",
            "label_ids": label_ids or ["INBOX", "UNREAD"],
            "snippet": snippet,
            "headers": {
                "from": from_addr,
                "to": "me@example.com",
                "subject": subject,
                "date": date,
                "cc": None,
                "reply_to": None,
                "message_id": f"<{msg_id}@mail.example.com>",
            },
        }
        msg = FakeToolMessage("get_message", json.dumps(data))
        return msg

    def test_converts_correctly(self):
        msg = self._make_get_message_result()
        result = _tool_message_to_email(msg)
        assert result is not None
        assert result["subject"] == "Hello"
        assert result["from"] == "Alice <alice@example.com>"
        assert result["snippet"] == "Hey there"
        assert result["messageId"] == "msg1"
        assert "UNREAD" in result["labels"]

    def test_missing_subject_uses_default(self):
        msg = self._make_get_message_result(subject=None)
        result = _tool_message_to_email(msg)
        assert result["subject"] == "(No subject)"

    def test_returns_none_when_no_message_id(self):
        data = {"message_id": "", "headers": {}, "label_ids": []}
        msg = FakeToolMessage("get_message", json.dumps(data))
        assert _tool_message_to_email(msg) is None

    def test_returns_none_for_invalid_json(self):
        msg = FakeToolMessage("get_message", "this is not json }{")
        assert _tool_message_to_email(msg) is None

    def test_returns_none_for_non_dict_content(self):
        msg = FakeToolMessage("get_message", json.dumps([1, 2, 3]))
        assert _tool_message_to_email(msg) is None


# ---------------------------------------------------------------------------
# _extract_emails_from_messages
# ---------------------------------------------------------------------------

class TestExtractEmailsFromMessages:
    def _make_email_msg(self, msg_id="msg1"):
        data = {
            "message_id": msg_id,
            "thread_id": "t1",
            "label_ids": ["INBOX"],
            "snippet": "snippet",
            "headers": {
                "from": "Alice <alice@example.com>",
                "subject": "Hi",
                "date": "Thu, 5 Mar 2026 10:00:00 +0000",
                "to": None, "cc": None, "reply_to": None, "message_id": None,
            },
        }
        return FakeToolMessage("get_message", json.dumps(data))

    def test_collects_all_get_message_results_from_turn(self):
        messages = [
            FakeHumanMessage("show my emails"),
            self._make_email_msg("msg1"),
            self._make_email_msg("msg2"),
            self._make_email_msg("msg3"),
            FakeAIMessage("Here are 3 emails."),
        ]
        result = _extract_emails_from_messages(messages)
        assert len(result) == 3
        ids = {e["messageId"] for e in result}
        assert ids == {"msg1", "msg2", "msg3"}

    def test_stops_at_human_message_boundary(self):
        """Emails from a previous turn should not bleed into the current one."""
        messages = [
            FakeHumanMessage("first question"),
            self._make_email_msg("old_msg"),
            FakeAIMessage("Old reply"),
            FakeHumanMessage("second question"),
            self._make_email_msg("new_msg"),
            FakeAIMessage("New reply"),
        ]
        result = _extract_emails_from_messages(messages)
        assert len(result) == 1
        assert result[0]["messageId"] == "new_msg"

    def test_returns_in_chronological_order(self):
        messages = [
            FakeHumanMessage("show"),
            self._make_email_msg("first"),
            self._make_email_msg("second"),
            FakeAIMessage("done"),
        ]
        result = _extract_emails_from_messages(messages)
        assert result[0]["messageId"] == "first"
        assert result[1]["messageId"] == "second"

    def test_returns_empty_when_no_email_messages(self):
        messages = [FakeHumanMessage("hi"), FakeAIMessage("hello")]
        assert _extract_emails_from_messages(messages) == []

    def test_handles_dict_human_message(self):
        """Dict-format user messages (as used at session start) act as boundary."""
        messages = [
            {"role": "user", "content": "show emails"},
            self._make_email_msg("msg1"),
            FakeAIMessage("here"),
        ]
        result = _extract_emails_from_messages(messages)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# POST /chat endpoint
# ---------------------------------------------------------------------------

class TestChatEndpoint:
    def _ai_msg(self, content):
        m = MagicMock()
        m.content = content
        m.type = "ai"
        return m

    def _make_agent_response(self, reply, extra_messages=None):
        messages = extra_messages or []
        return {"messages": [*messages, self._ai_msg(reply)]}

    def test_returns_reply(self, client):
        with patch("server.agent") as mock_agent:
            mock_agent.invoke.return_value = self._make_agent_response("Hello back!")
            resp = client.post("/chat", json={"message": "hi"})

        assert resp.status_code == 200
        assert resp.json()["reply"] == "Hello back!"

    def test_returns_empty_events_and_emails_by_default(self, client):
        with patch("server.agent") as mock_agent:
            mock_agent.invoke.return_value = self._make_agent_response("No events today.")
            resp = client.post("/chat", json={"message": "what's on today?"})

        data = resp.json()
        assert data["events"] == []
        assert data["emails"] == []

    def test_returns_calendar_events(self, client):
        event_payload = json.dumps({
            "events": [{
                "summary": "Standup",
                "start": {"dateTime": "2026-03-05T09:00:00-05:00"},
                "end": {"dateTime": "2026-03-05T09:30:00-05:00"},
                "htmlLink": "https://cal.google.com/1",
                "location": None,
            }]
        })
        tool_msg = FakeToolMessage("list_events_for_day", event_payload)

        with patch("server.agent") as mock_agent:
            mock_agent.invoke.return_value = {
                "messages": [
                    FakeHumanMessage("what's on today?"),
                    tool_msg,
                    self._ai_msg("Here is your schedule."),
                ]
            }
            resp = client.post("/chat", json={"message": "what's on today?"})

        data = resp.json()
        assert len(data["events"]) == 1
        assert data["events"][0]["title"] == "Standup"

    def test_returns_email_cards(self, client):
        email_data = {
            "message_id": "msg1",
            "thread_id": "t1",
            "label_ids": ["INBOX", "UNREAD"],
            "snippet": "Hey, quick question...",
            "headers": {
                "from": "Bob <bob@example.com>",
                "subject": "Quick question",
                "date": "Thu, 5 Mar 2026 10:00:00 +0000",
                "to": None, "cc": None, "reply_to": None, "message_id": None,
            },
        }
        tool_msg = FakeToolMessage("get_message", json.dumps(email_data))

        with patch("server.agent") as mock_agent:
            mock_agent.invoke.return_value = {
                "messages": [
                    FakeHumanMessage("show my emails"),
                    tool_msg,
                    self._ai_msg("Here is your email."),
                ]
            }
            resp = client.post("/chat", json={"message": "show my emails"})

        data = resp.json()
        assert len(data["emails"]) == 1
        assert data["emails"][0]["subject"] == "Quick question"
        assert data["emails"][0]["from"] == "Bob <bob@example.com>"
        assert data["emails"][0]["messageId"] == "msg1"

    def test_reply_truncated_to_first_line_when_events_present(self, client):
        """Server strips multi-line LLM reply to first line when cards are shown."""
        event_payload = json.dumps({
            "events": [{
                "summary": "Meeting",
                "start": {"dateTime": "2026-03-05T10:00:00-05:00"},
                "end": {"dateTime": "2026-03-05T11:00:00-05:00"},
                "htmlLink": "https://cal.google.com/1",
                "location": None,
            }]
        })
        tool_msg = FakeToolMessage("list_events_for_day", event_payload)

        with patch("server.agent") as mock_agent:
            mock_agent.invoke.return_value = {
                "messages": [
                    FakeHumanMessage("schedule?"),
                    tool_msg,
                    self._ai_msg("Here are your events:\n- Meeting at 10am\n- Another thing"),
                ]
            }
            resp = client.post("/chat", json={"message": "schedule?"})

        data = resp.json()
        assert "\n" not in data["reply"]
        assert data["reply"] == "Here are your events:"

    def test_message_history_is_updated_after_call(self, client):
        """Subsequent requests build on prior context."""
        with patch("server.agent") as mock_agent:
            mock_agent.invoke.return_value = self._make_agent_response("First reply")
            client.post("/chat", json={"message": "first"})

            mock_agent.invoke.return_value = self._make_agent_response("Second reply")
            resp = client.post("/chat", json={"message": "second"})

        assert resp.json()["reply"] == "Second reply"
        # agent.invoke should have been called twice total
        assert mock_agent.invoke.call_count == 2
