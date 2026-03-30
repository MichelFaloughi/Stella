TODO: Make a requirements.txt file

# Stella

Personal AI agent for Google Calendar and Gmail. Natural language in, real API calls out.

## Tools

**Calendar (7):** create, list by day, list by range, find, delete, update, get current datetime

**Gmail (11):** list messages, get message, trash, delete permanently, batch modify labels, mark as read, mark as unread, create draft, update draft, send draft, create reply draft

## Tech stack

- Python 3.12, FastAPI, LangChain, OpenAI `gpt-4o-mini`
- Google Calendar + Gmail APIs (unified OAuth2, shared `token.json`)
- Next.js 15 / React 19 frontend with EventCard + EmailCard components

## Setup

1. Create a Google Cloud project, enable Calendar and Gmail APIs
2. Add `credentials.json` to the repo root
3. Set `OPENAI_API_KEY` in your environment
4. Run and authorize once in the browser

```bash
python main.py              # terminal CLI
uvicorn server:app --reload # backend
cd web && npm run dev       # frontend
pytest tests/               # tests
```

## Status

Work in progress — personal automation/agent playground.

### Recent changes
- Fixed stale event cards bleeding across turns (`_extract_events_from_messages` now stops at the current turn boundary, matching email extraction behavior)
- Fixed unsafe `messages[-1].content` access in the chat endpoint — now guarded against non-AIMessage types
- Added `mark_as_read` and `mark_as_unread` Gmail tools
