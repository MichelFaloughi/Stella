# tools/auth.py
# Shared Google OAuth configuration for Calendar and Gmail tools.
# Both tools use the same token.json and the same scope set.

import os
from typing import Optional, Sequence

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow


# Paths (relative to process cwd, typically project root)
TOKEN_PATH = "token.json"
CREDENTIALS_PATH = "credentials.json"

# Unified scopes for Calendar and Gmail so a single token covers both.
SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.compose",
]


def get_creds(scopes: Optional[Sequence[str]] = None) -> Credentials:
    """
    Return valid OAuth Credentials for the given scopes.
    - Loads token from TOKEN_PATH if present
    - Refreshes if expired (and refresh_token exists)
    - Otherwise runs local-server OAuth flow using CREDENTIALS_PATH
    - Writes token back to TOKEN_PATH
    Uses the unified SCOPES by default so Calendar and Gmail share one token.
    """
    scopes_list = list(scopes if scopes is not None else SCOPES)

    creds: Optional[Credentials] = None

    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, scopes_list)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_PATH, scopes_list
            )
            creds = flow.run_local_server(port=0)

        with open(TOKEN_PATH, "w") as f:
            f.write(creds.to_json())

    return creds
