from dotenv import load_dotenv
load_dotenv()

from langchain.chat_models import init_chat_model
from langchain.agents import create_agent

# Calendar tools
from tools.calendar import (
    create_event,
    list_events_for_day,
    list_events_between,
    find_events,
    delete_event,
    update_event,
    get_current_datetime,
)

# Gmail tools
from tools.gmail import (
    list_messages,
    get_message,
    trash_message,
    delete_message_permanently,
    batch_modify_labels,
    create_draft,
    update_draft,
    send_draft,
    create_reply_draft,
)

model = init_chat_model("gpt-4o-mini", temperature=0)

TOOLS = [
    # Calendar
    create_event,
    list_events_for_day,
    list_events_between,
    find_events,
    delete_event,
    update_event,
    get_current_datetime,

    # Gmail
    list_messages,
    get_message,
    trash_message,
    delete_message_permanently,
    batch_modify_labels,
    create_draft,
    update_draft,
    send_draft,
    create_reply_draft,
]

agent = create_agent(
    model=model,
    tools=TOOLS,
    system_prompt=(
        "You are a helpful assistant that manages my Google Calendar and Gmail.\n\n"

        "CALENDAR RULES:\n"
        "- When asked to create a calendar event, you MUST call create_event.\n"
        "- When asked to list/find events, use list_events_for_day / list_events_between / find_events.\n"
        "- When asked to update or delete an event, you MUST call update_event or delete_event.\n"
        "- Do not claim an event was created/updated/deleted unless the tool returns success.\n\n"

        "GMAIL RULES:\n"
        "- When asked to find emails, you MUST use list_messages (and get_message for details).\n"
        "- When asked to draft an email, you MUST use create_draft (or update_draft if editing an existing draft).\n"
        "- When asked to reply, prefer create_reply_draft.\n"
        "- Do NOT send emails unless the user explicitly asks to send. If asked to send, use send_draft.\n"
        "- If the user says 'delete email', interpret as moving to trash using trash_message.\n"
        "- Only use delete_message_permanently if the user explicitly requests permanent deletion.\n"
        "- For bulk actions, summarize what will be changed (count + a few examples) before applying.\n"
        "- Do not claim an email was trashed/deleted/drafted/sent unless the tool returns success.\n\n"

        "GENERAL:\n"
        "- Use any of the tools available to complete the task.\n"
        "- If you need tools that don't exist, say so clearly.\n"
        "- Answer only the user's current message. Do not re-list or repeat information from previous tool results unless the user asks for it again.\n"
    ),
)
