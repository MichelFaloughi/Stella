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







# ===================== TODO =====================
# [ ] Add list_events_for_day(date, timezone) tool (needed to resolve event_id)
# [ ] Add find_events(query, start_date, end_date) tool
# [ ] Add update_event(event_id, patch) tool (use PATCH, not full update)
# [ ] Add delete_event(event_id) tool
# [ ] Handle ambiguous matches (ask user to choose when multiple events found)
# [ ] Add safety guardrails (past events, recurring events confirmation)
# [ ] Normalize date/time parsing (timezone + ISO consistency)
# [ ] Improve system prompt to forbid hallucinated success
# ===============================================

@tool("delete_event", description="")
def delete_event(args):
    pass


@tool("update_event", description="")
def update_event(args):
    pass