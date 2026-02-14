# server.py
import ast
import json
from datetime import datetime
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
from pydantic import BaseModel
from langchain_core.messages import ToolMessage

from agent import agent
from main import SYSTEM_HINT

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Tool names that return a list of calendar events (we use the last one in the turn)
EVENT_LIST_TOOLS = {"list_events_for_day", "list_events_between", "find_events"}
# Tools that return a single event (create/update) — we show it as one event card
EVENT_SINGLE_TOOLS = {"create_event", "update_event"}


def _format_event_time(d: dict) -> str:
    """Format Google Calendar start/end dict to a short time string."""
    if not d:
        return ""
    if d.get("dateTime"):
        try:
            dt = datetime.fromisoformat(d["dateTime"].replace("Z", "+00:00"))
            hour = dt.hour % 12 or 12
            return f"{hour}:{dt.minute:02d} {dt.strftime('%p')}"
        except (ValueError, TypeError):
            return d["dateTime"]
    if d.get("date"):
        return "All day"
    return ""


def _tool_events_to_frontend(events: list) -> list:
    """Convert calendar tool event list to EventCard shape."""
    out = []
    for ev in events or []:
        start = ev.get("start") or {}
        end = ev.get("end") or {}
        start_time = _format_event_time(start)
        end_time = _format_event_time(end)
        if start.get("date") and not end_time:
            end_time = ""
        out.append({
            "title": ev.get("summary") or "(No title)",
            "startTime": start_time,
            "endTime": end_time,
            "location": ev.get("location"),
            "calendarUrl": ev.get("htmlLink") or "",
        })
    return out


def _get_tool_message_name(m):
    """Get tool name from a tool message (object or dict)."""
    return getattr(m, "name", None) or (m.get("name") if isinstance(m, dict) else None)


def _is_event_list_tool_message(m) -> bool:
    """True if this message is a tool result from an event-listing tool."""
    return _get_tool_message_name(m) in EVENT_LIST_TOOLS


def _is_event_single_tool_message(m) -> bool:
    """True if this message is a tool result from create_event or update_event."""
    return _get_tool_message_name(m) in EVENT_SINGLE_TOOLS


def _get_tool_message_content(m):
    """Get content from a tool message (object or dict)."""
    if hasattr(m, "content"):
        return m.content
    if isinstance(m, dict):
        return m.get("content")
    return None


def _parse_tool_content(raw) -> dict | None:
    """Parse tool message content (str or dict) to a dict. Returns None on failure."""
    try:
        if isinstance(raw, str):
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return ast.literal_eval(raw)
        if isinstance(raw, dict):
            return raw
        return None
    except (json.JSONDecodeError, TypeError, ValueError, SyntaxError):
        return None


def _extract_events_from_messages(messages: list) -> list:
    """Find the last event-producing tool result (list or single) and return frontend events."""
    for m in reversed(messages):
        name = _get_tool_message_name(m)
        content = _get_tool_message_content(m)
        if content is None:
            continue

        if name in EVENT_LIST_TOOLS:
            data = _parse_tool_content(content)
            if data is not None:
                raw_events = data.get("events") if isinstance(data, dict) else []
                return _tool_events_to_frontend(raw_events)

        if name in EVENT_SINGLE_TOOLS:
            data = _parse_tool_content(content)
            if not isinstance(data, dict):
                continue
            if data.get("error") or data.get("updated") is False:
                continue
            # create_event returns event_id, summary, start, end, htmlLink
            # update_event returns updated, event_id, summary, start, end, location, htmlLink
            if data.get("event_id") or data.get("summary") is not None:
                return _tool_events_to_frontend([data])

    return []


# keep chat state in memory (single-user, simple)
messages = [{"role": "system", "content": SYSTEM_HINT}]

class ChatRequest(BaseModel):
    message: str

@app.post("/chat")
def chat(req: ChatRequest):
    global messages

    messages.append({"role": "user", "content": req.message})
    res = agent.invoke({"messages": messages})

    messages = res["messages"]
    reply = messages[-1].content
    events = _extract_events_from_messages(messages)

    # When we have structured events, show only a short intro (avoid duplicating with markdown list)
    if events and reply:
        first_line = reply.split("\n")[0].strip()
        if first_line:
            reply = first_line

    return {"reply": reply, "events": events}
