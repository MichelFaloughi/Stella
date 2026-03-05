# tools.gmail.py
# Auth/service setup is plumbing; the agent shouldn't call it directly.
# Tools call get_service() internally.

from langchain.tools import tool

import base64
from typing import Optional, Tuple, List, Dict, Any

from googleapiclient.discovery import build

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from tools.auth import get_creds, SCOPES


# -----------------------
# Config
# -----------------------
DEFAULT_USER_ID = "me"

_SERVICE_CACHE = {
    "scopes": None,      # type: Optional[Tuple[str, ...]]
    "service": None      # type: Optional[object]
}


def get_service():
    """
    Return a Gmail API service:
      service = build("gmail", "v1", credentials=creds)

    Cached in-process. Uses shared OAuth credentials from tools.auth (same token as Calendar).
    """
    scopes_tuple = tuple(SCOPES)

    if _SERVICE_CACHE["service"] is not None and _SERVICE_CACHE["scopes"] == scopes_tuple:
        return _SERVICE_CACHE["service"]

    creds = get_creds()
    service = build("gmail", "v1", credentials=creds)

    _SERVICE_CACHE["scopes"] = scopes_tuple
    _SERVICE_CACHE["service"] = service
    return service


# -----------------------
# Helpers
# -----------------------
def _b64url_encode(raw_bytes: bytes) -> str:
    return base64.urlsafe_b64encode(raw_bytes).decode("utf-8")


def build_mime_message(
    to: List[str],
    subject: str,
    body_text: str,
    cc: Optional[List[str]] = None,
    bcc: Optional[List[str]] = None,
    body_html: Optional[str] = None,
    from_email: Optional[str] = None,
    in_reply_to: Optional[str] = None,
    references: Optional[str] = None,
) -> str:
    """
    Build a MIME message and return base64url "raw" string for Gmail API.
    If body_html is provided, sends multipart/alternative.
    """
    if body_html:
        msg = MIMEMultipart("alternative")
        msg.attach(MIMEText(body_text or "", "plain", "utf-8"))
        msg.attach(MIMEText(body_html, "html", "utf-8"))
    else:
        msg = MIMEText(body_text or "", "plain", "utf-8")

    msg["To"] = ", ".join(to)
    msg["Subject"] = subject
    if cc:
        msg["Cc"] = ", ".join(cc)
    if bcc:
        # Gmail supports Bcc header; keep it if you need it.
        msg["Bcc"] = ", ".join(bcc)
    if from_email:
        msg["From"] = from_email
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
    if references:
        msg["References"] = references

    raw = _b64url_encode(msg.as_bytes())
    return raw


def _extract_headers(payload: Dict[str, Any]) -> Dict[str, str]:
    headers = payload.get("headers", []) if payload else []
    out = {}
    for h in headers:
        name = (h.get("name") or "").lower()
        value = h.get("value") or ""
        if name:
            out[name] = value
    return out


# -----------------------
# TOOLS
# -----------------------

@tool(
    "list_messages",
    description=(
        "List Gmail messages. query uses Gmail search syntax (same as Gmail search box). "
        "Optionally filter by label_ids (e.g. ['INBOX','UNREAD']). Returns message ids + thread ids."
    ),
)
def list_messages(
    query: Optional[str] = None,
    label_ids: Optional[List[str]] = None,
    max_results: int = 20,
    user_id: str = DEFAULT_USER_ID,
) -> Dict[str, Any]:
    service = get_service()

    resp = (
        service.users()
        .messages()
        .list(userId=user_id, q=query or None, labelIds=label_ids or None, maxResults=max_results)
        .execute()
    )

    msgs = resp.get("messages", []) or []
    return {
        "query": query,
        "label_ids": label_ids,
        "count": len(msgs),
        "messages": [{"message_id": m.get("id"), "thread_id": m.get("threadId")} for m in msgs],
        "nextPageToken": resp.get("nextPageToken"),
    }


@tool(
    "get_message",
    description=(
        "Get a Gmail message by id. format can be 'metadata' (fast) or 'full' (includes body structure). "
        "Returns key headers + snippet."
    ),
)
def get_message(
    message_id: str,
    format: str = "metadata",
    user_id: str = DEFAULT_USER_ID,
) -> Dict[str, Any]:
    service = get_service()

    resp = (
        service.users()
        .messages()
        .get(
            userId=user_id,
            id=message_id,
            format=format,
            metadataHeaders=["From", "To", "Cc", "Subject", "Date", "Message-Id", "Reply-To"],
        )
        .execute()
    )

    payload = resp.get("payload", {})
    headers = _extract_headers(payload)

    return {
        "message_id": resp.get("id"),
        "thread_id": resp.get("threadId"),
        "label_ids": resp.get("labelIds", []),
        "snippet": resp.get("snippet"),
        "internalDate": resp.get("internalDate"),
        "headers": {
            "from": headers.get("from"),
            "to": headers.get("to"),
            "cc": headers.get("cc"),
            "subject": headers.get("subject"),
            "date": headers.get("date"),
            "message_id": headers.get("message-id"),
            "reply_to": headers.get("reply-to"),
        },
    }


@tool(
    "trash_message",
    description="Move a message to TRASH (safe, reversible). Prefer this over permanent delete.",
)
def trash_message(
    message_id: str,
    user_id: str = DEFAULT_USER_ID,
) -> Dict[str, Any]:
    service = get_service()
    resp = service.users().messages().trash(userId=user_id, id=message_id).execute()
    return {
        "trashed": True,
        "message_id": resp.get("id"),
        "thread_id": resp.get("threadId"),
        "label_ids": resp.get("labelIds", []),
    }


@tool(
    "delete_message_permanently",
    description=(
        "Permanently delete a message immediately (NOT reversible). "
        "Use only if user explicitly requests permanent deletion."
    ),
)
def delete_message_permanently(
    message_id: str,
    user_id: str = DEFAULT_USER_ID,
) -> Dict[str, Any]:
    service = get_service()
    service.users().messages().delete(userId=user_id, id=message_id).execute()
    return {"deleted_permanently": True, "message_id": message_id}


@tool(
    "batch_modify_labels",
    description=(
        "Modify labels for many messages at once using batchModify. "
        "Example: remove INBOX, add ARCHIVE label, etc."
    ),
)
def batch_modify_labels(
    message_ids: List[str],
    add_label_ids: Optional[List[str]] = None,
    remove_label_ids: Optional[List[str]] = None,
    user_id: str = DEFAULT_USER_ID,
) -> Dict[str, Any]:
    service = get_service()
    body = {
        "ids": message_ids,
        "addLabelIds": add_label_ids or [],
        "removeLabelIds": remove_label_ids or [],
    }
    service.users().messages().batchModify(userId=user_id, body=body).execute()
    return {
        "updated": True,
        "count": len(message_ids),
        "add_label_ids": add_label_ids or [],
        "remove_label_ids": remove_label_ids or [],
    }


@tool(
    "create_draft",
    description="Create a Gmail draft. Provide to/subject/body. Returns draft_id and message_id.",
)
def create_draft(
    to: List[str],
    subject: str,
    body_text: str,
    cc: Optional[List[str]] = None,
    bcc: Optional[List[str]] = None,
    body_html: Optional[str] = None,
    user_id: str = DEFAULT_USER_ID,
) -> Dict[str, Any]:
    service = get_service()

    raw = build_mime_message(
        to=to,
        subject=subject,
        body_text=body_text,
        cc=cc,
        bcc=bcc,
        body_html=body_html,
    )

    draft_body = {"message": {"raw": raw}}
    created = service.users().drafts().create(userId=user_id, body=draft_body).execute()

    msg = created.get("message", {}) or {}
    return {
        "draft_id": created.get("id"),
        "message_id": msg.get("id"),
        "thread_id": msg.get("threadId"),
    }


@tool(
    "update_draft",
    description="Update an existing draft (replaces the draft content). Returns updated draft_id/message_id.",
)
def update_draft(
    draft_id: str,
    to: List[str],
    subject: str,
    body_text: str,
    cc: Optional[List[str]] = None,
    bcc: Optional[List[str]] = None,
    body_html: Optional[str] = None,
    user_id: str = DEFAULT_USER_ID,
) -> Dict[str, Any]:
    service = get_service()

    raw = build_mime_message(
        to=to,
        subject=subject,
        body_text=body_text,
        cc=cc,
        bcc=bcc,
        body_html=body_html,
    )

    body = {"id": draft_id, "message": {"raw": raw}}
    updated = service.users().drafts().update(userId=user_id, id=draft_id, body=body).execute()

    msg = updated.get("message", {}) or {}
    return {
        "draft_id": updated.get("id"),
        "message_id": msg.get("id"),
        "thread_id": msg.get("threadId"),
    }


@tool(
    "send_draft",
    description="Send an existing draft by draft_id. Returns sent message_id + thread_id.",
)
def send_draft(
    draft_id: str,
    user_id: str = DEFAULT_USER_ID,
) -> Dict[str, Any]:
    service = get_service()
    sent = service.users().drafts().send(userId=user_id, body={"id": draft_id}).execute()
    return {
        "sent": True,
        "message_id": sent.get("id"),
        "thread_id": sent.get("threadId"),
        "label_ids": sent.get("labelIds", []),
    }


@tool(
    "create_reply_draft",
    description=(
        "Create a reply draft to an existing message_id. "
        "Auto-sets Subject to 'Re: ...', and sets threadId + In-Reply-To/References for proper threading."
    ),
)
def create_reply_draft(
    original_message_id: str,
    reply_body_text: str,
    user_id: str = DEFAULT_USER_ID,
) -> Dict[str, Any]:
    service = get_service()

    original = service.users().messages().get(
        userId=user_id,
        id=original_message_id,
        format="metadata",
        metadataHeaders=["From", "Reply-To", "To", "Cc", "Subject", "Message-Id", "References"],
    ).execute()

    payload = original.get("payload", {})
    headers = _extract_headers(payload)

    # Prefer Reply-To, else From
    reply_to = headers.get("reply-to") or headers.get("from") or ""
    subject = headers.get("subject") or ""
    if not subject.lower().startswith("re:"):
        subject = f"Re: {subject}".strip()

    in_reply_to = headers.get("message-id")
    references = headers.get("references")
    if references and in_reply_to:
        references = f"{references} {in_reply_to}"
    elif in_reply_to:
        references = in_reply_to

    raw = build_mime_message(
        to=[reply_to],
        subject=subject,
        body_text=reply_body_text,
        in_reply_to=in_reply_to,
        references=references,
    )

    draft_body = {
        "message": {
            "raw": raw,
            "threadId": original.get("threadId"),
        }
    }

    created = service.users().drafts().create(userId=user_id, body=draft_body).execute()
    msg = created.get("message", {}) or {}

    return {
        "draft_id": created.get("id"),
        "message_id": msg.get("id"),
        "thread_id": msg.get("threadId"),
        "replied_to_message_id": original_message_id,
    }
