# Auth/service setup is plumbing; the agent shouldn’t call it directly. Your tools should call get_service() internally. ie don't make it a tool
from langchain.tools import tool

import datetime
import os.path
import os
from typing import Optional, Sequence, Tuple, List, Dict, Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

DEFAULT_SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
DEFAULT_TZ = "America/New_York"

# ---- simple in-process cache so we don't rebuild every tool call ----
_SERVICE_CACHE = {
    "scopes": None,      # type: Optional[Tuple[str, ...]]
    "service": None      # type: Optional[object]
}


def get_creds(scopes: Optional[Sequence[str]] = None) -> Credentials:
    """
    Return valid OAuth Credentials for the given scopes.
    - Loads token.json if present
    - Refreshes if expired (and refresh_token exists)
    - Otherwise runs local-server OAuth flow using credentials.json
    - Writes token.json back to disk
    """
    scopes = list(scopes or DEFAULT_SCOPES)

    creds: Optional[Credentials] = None

    # Load cached tokens if present
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", scopes)

    # If no valid creds, refresh or run OAuth
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", scopes)
            creds = flow.run_local_server(port=0)

        # Persist for next run
        with open("token.json", "w") as f:
            f.write(creds.to_json())

    return creds

def get_service(scopes: Optional[Sequence[str]] = None):
    """
    Return a Google Calendar API 'service' object:
      service = build("calendar", "v3", credentials=creds)

    Caches the service in-process so repeated tool calls are fast.
    If scopes differ from the cached scopes, rebuilds the service.
    """
    scopes_tuple = tuple(scopes or DEFAULT_SCOPES)

    cached_scopes = _SERVICE_CACHE["scopes"]
    cached_service = _SERVICE_CACHE["service"]

    if cached_service is not None and cached_scopes == scopes_tuple:
        return cached_service

    creds = get_creds(scopes_tuple)
    service = build("calendar", "v3", credentials=creds)

    _SERVICE_CACHE["scopes"] = scopes_tuple
    _SERVICE_CACHE["service"] = service
    return service


###########
## TOOLS ##
###########

@tool("create_event", description="Create a calendar event. start/end must be dicts like {'dateTime': ISO, 'timeZone': TZ} or {'date': 'yyyy-mm-dd'} (for full day events). ")
def create_event(
    event_name: str,
    start: Dict[str, str],
    end: Dict[str, str],
    calendar_id: str = "primary",
    location: Optional[str] = None,
    description: Optional[str] = None,
    attendees: Optional[List[str]] = None,   # list of emails
    timezone: str = DEFAULT_TZ,
) -> Dict[str, Any]:
    """
    Creates an event in Google Calendar. Returns key fields so the agent can reference it later.
    """
    service = get_service()  # helper from above that returns build("calendar","v3", creds)

    # Normalize timezone if caller didn't include it
    start_norm = dict(start)
    end_norm = dict(end)
    if "dateTime" in start_norm and "timeZone" not in start_norm:
        start_norm["timeZone"] = timezone
    if "dateTime" in end_norm and "timeZone" not in end_norm:
        end_norm["timeZone"] = timezone

    # Required fields
    event: Dict[str, Any] = {
        "summary": event_name,
        "start": start_norm,
        "end": end_norm,
    }

    # Optional fields: only include if provided
    if location:
        event["location"] = location
    if description:
        event["description"] = description
    if attendees:
        event["attendees"] = [{"email": e} for e in attendees]

    created = service.events().insert(calendarId=calendar_id, body=event).execute()

    return {
        "event_id": created.get("id"),
        "summary": created.get("summary"),
        "start": created.get("start"),
        "end": created.get("end"),
        "htmlLink": created.get("htmlLink"),
    }




from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo

@tool(
    "list_events_for_day",
    description="List events for a given day. date_str must be 'YYYY-MM-DD'. Returns events with ids."
)
def list_events_for_day(
    date_str: str,
    calendar_id: str = "primary",
    timezone: str = DEFAULT_TZ,
    max_results: int = 50,
) -> Dict[str, Any]:
    service = get_service()

    tz = ZoneInfo(timezone)
    d = date.fromisoformat(date_str)

    start_dt = datetime.combine(d, time.min).replace(tzinfo=tz)
    end_dt = (start_dt + timedelta(days=1))

    events_result = (
        service.events()
        .list(
            calendarId=calendar_id,
            timeMin=start_dt.isoformat(),
            timeMax=end_dt.isoformat(),
            singleEvents=True,
            orderBy="startTime",
            maxResults=max_results,
        )
        .execute()
    )

    items = events_result.get("items", [])

    def _extract(ev):
        return {
            "event_id": ev.get("id"),
            "summary": ev.get("summary"),
            "start": ev.get("start"),
            "end": ev.get("end"),
            "htmlLink": ev.get("htmlLink"),
            "location": ev.get("location"),
        }

    return {
        "date": date_str,
        "timezone": timezone,
        "count": len(items),
        "events": [_extract(ev) for ev in items],
    }


@tool(
    "list_events_between",
    description="List calendar events between two dates (inclusive). Dates are YYYY-MM-DD."
)
def list_events_between(
    start_date: str,
    end_date: str,
    calendar_id: str = "primary",
    timezone: str = DEFAULT_TZ,
    max_results: int = 50,
) -> Dict[str, Any]:
    service = get_service()
    tz = ZoneInfo(timezone)

    start_dt = datetime.combine(
        date.fromisoformat(start_date),
        time.min
    ).replace(tzinfo=tz)

    # end_date inclusive → add 1 day
    end_dt = datetime.combine(
        date.fromisoformat(end_date),
        time.min
    ).replace(tzinfo=tz) + timedelta(days=1)

    events_result = (
        service.events()
        .list(
            calendarId=calendar_id,
            timeMin=start_dt.isoformat(),
            timeMax=end_dt.isoformat(),
            singleEvents=True,
            orderBy="startTime",
            maxResults=max_results,
        )
        .execute()
    )

    items = events_result.get("items", [])

    return {
        "range": {
            "start_date": start_date,
            "end_date": end_date,
            "timezone": timezone,
        },
        "count": len(items),
        "events": [
            {
                "event_id": ev.get("id"),
                "summary": ev.get("summary"),
                "start": ev.get("start"),
                "end": ev.get("end"),
                "location": ev.get("location"),
                "htmlLink": ev.get("htmlLink"),
            }
            for ev in items
        ],
    }


from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo
from typing import Optional, Dict, Any, List

@tool(
    "find_events",
    description=(
        "Find events by free-text query within a date range (inclusive). "
        "Dates are YYYY-MM-DD. Returns events with ids."
    ),
)
def find_events(
    query: str,
    start_date: str,
    end_date: str,
    calendar_id: str = "primary",
    timezone: str = DEFAULT_TZ,
    max_results: int = 25,
) -> Dict[str, Any]:
    service = get_service()
    tz = ZoneInfo(timezone)

    start_dt = datetime.combine(date.fromisoformat(start_date), time.min).replace(tzinfo=tz)
    end_dt = datetime.combine(date.fromisoformat(end_date), time.min).replace(tzinfo=tz) + timedelta(days=1)

    events_result = (
        service.events()
        .list(
            calendarId=calendar_id,
            q=query,
            timeMin=start_dt.isoformat(),
            timeMax=end_dt.isoformat(),
            singleEvents=True,     # expands recurring events into instances
            orderBy="startTime",
            maxResults=max_results,
        )
        .execute()
    )

    items = events_result.get("items", [])

    return {
        "query": query,
        "range": {"start_date": start_date, "end_date": end_date, "timezone": timezone},
        "count": len(items),
        "events": [
            {
                "event_id": ev.get("id"),
                "summary": ev.get("summary"),
                "start": ev.get("start"),
                "end": ev.get("end"),
                "location": ev.get("location"),
                "htmlLink": ev.get("htmlLink"),
            }
            for ev in items
        ],
    }


@tool(
    "delete_event",
    description=(
        "Delete a calendar event. Prefer event_id. "
        "If only a query is provided, it will search in the date range and delete ONLY if exactly one match is found."
    ),
)
def delete_event(
    event_id: Optional[str] = None,
    query: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    calendar_id: str = "primary",
    timezone: str = DEFAULT_TZ,
) -> Dict[str, Any]:
    service = get_service()

    # If event_id provided, delete directly
    if event_id:
        service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
        return {"deleted": True, "event_id": event_id, "calendar_id": calendar_id}

    # Otherwise resolve by search (must have query + window)
    if not query or not start_date or not end_date:
        return {
            "deleted": False,
            "error": "Must provide event_id, or (query + start_date + end_date)."
        }

    # Reuse find_events logic inline (or call a shared helper)
    tz = ZoneInfo(timezone)
    start_dt = datetime.combine(date.fromisoformat(start_date), time.min).replace(tzinfo=tz)
    end_dt = datetime.combine(date.fromisoformat(end_date), time.min).replace(tzinfo=tz) + timedelta(days=1)

    events_result = service.events().list(
        calendarId=calendar_id,
        q=query,
        timeMin=start_dt.isoformat(),
        timeMax=end_dt.isoformat(),
        singleEvents=True,
        orderBy="startTime",
        maxResults=10,
    ).execute()

    items = events_result.get("items", [])
    if len(items) == 0:
        return {"deleted": False, "error": "No matching events found."}
    if len(items) > 1:
        return {
            "deleted": False,
            "error": "Ambiguous query: multiple matches.",
            "matches": [
                {"event_id": ev.get("id"), "summary": ev.get("summary"), "start": ev.get("start"), "htmlLink": ev.get("htmlLink")}
                for ev in items
            ],
        }

    eid = items[0].get("id")
    service.events().delete(calendarId=calendar_id, eventId=eid).execute()
    return {"deleted": True, "event_id": eid, "calendar_id": calendar_id}


from typing import Optional, Dict, Any, List
from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo

@tool(
    "update_event",
    description=(
        "Patch-update a calendar event. Prefer event_id. "
        "If event_id is not provided, provide (query + start_date + end_date) to resolve a single event. "
        "patch is a partial Google Calendar event resource (e.g. {'summary': 'New title'} or {'start': {...}, 'end': {...}})."
    ),
)
def update_event(
    patch: Dict[str, Any],
    event_id: Optional[str] = None,
    query: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    calendar_id: str = "primary",
    timezone: str = DEFAULT_TZ,
) -> Dict[str, Any]:
    service = get_service()

    def _resolve_single_event_id() -> Dict[str, Any]:
        """Return {'ok': True, 'event_id': ...} or {'ok': False, 'error': ..., 'matches': [...]?}"""
        if event_id:
            return {"ok": True, "event_id": event_id}

        if not query or not start_date or not end_date:
            return {
                "ok": False,
                "error": "Must provide event_id, or (query + start_date + end_date).",
            }

        tz = ZoneInfo(timezone)
        start_dt = datetime.combine(date.fromisoformat(start_date), time.min).replace(tzinfo=tz)
        end_dt = datetime.combine(date.fromisoformat(end_date), time.min).replace(tzinfo=tz) + timedelta(days=1)

        events_result = service.events().list(
            calendarId=calendar_id,
            q=query,
            timeMin=start_dt.isoformat(),
            timeMax=end_dt.isoformat(),
            singleEvents=True,
            orderBy="startTime",
            maxResults=10,
        ).execute()

        items = events_result.get("items", [])
        if len(items) == 0:
            return {"ok": False, "error": "No matching events found."}
        if len(items) > 1:
            return {
                "ok": False,
                "error": "Ambiguous query: multiple matches.",
                "matches": [
                    {
                        "event_id": ev.get("id"),
                        "summary": ev.get("summary"),
                        "start": ev.get("start"),
                        "htmlLink": ev.get("htmlLink"),
                    }
                    for ev in items
                ],
            }

        return {"ok": True, "event_id": items[0].get("id")}

    # --- resolve target event id ---
    resolved = _resolve_single_event_id()
    if not resolved.get("ok"):
        return {"updated": False, **resolved}

    target_id = resolved["event_id"]

    # --- apply PATCH ---
    updated = service.events().patch(
        calendarId=calendar_id,
        eventId=target_id,
        body=patch,
    ).execute()

    return {
        "updated": True,
        "event_id": updated.get("id"),
        "summary": updated.get("summary"),
        "start": updated.get("start"),
        "end": updated.get("end"),
        "location": updated.get("location"),
        "htmlLink": updated.get("htmlLink"),
    }



@tool(
    "get_current_datetime",
    description="Return the current datetime in ISO-8601 format for a given timezone."
)
def get_current_datetime(tz: str = "America/New_York") -> str:
    return datetime.now(ZoneInfo(tz)).isoformat()






# ===================== TODO =====================
# [ ] Add list_events_for_day(date, timezone) tool (needed to resolve event_id) - DONE
# [ ] Add find_events(query, start_date, end_date) tool                         - DONE
# [ ] Add update_event(event_id, patch) tool (use PATCH, not full update)       - DONE 
# [ ] Add delete_event(event_id) tool                                           - DONE (added non-id arg)
# [ ] Handle ambiguous matches (ask user to choose when multiple events found)
# [ ] Add safety guardrails (past events, recurring events confirmation)
# [ ] Normalize date/time parsing (timezone + ISO consistency)
# [ ] Improve system prompt to forbid hallucinated success
# ===============================================