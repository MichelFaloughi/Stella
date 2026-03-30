# CLAUDE.md — Stella Project Instructions

## Project Overview

Stella is a personal AI calendar and email agent built with:
- **Backend**: Python + LangChain + FastAPI + Google APIs (Calendar, Gmail)
- **Frontend**: Next.js 15 + React 19 + TypeScript + Tailwind CSS 4
- **LLM**: OpenAI `gpt-4o-mini` (temperature=0)
- **Auth**: Unified Google OAuth2 (`token.json` shared across Calendar + Gmail)

Users interact via natural language (terminal CLI or web UI), and the LangChain agent executes actions through 16 tools (7 calendar, 9 Gmail).

## Architecture Patterns

### Tool-Calling Agent (LangChain)
- All tools registered in `agent.py` via `create_agent()`
- System prompt enforces safety: no hallucinations, no email sending without explicit user request
- Agent must receive tool confirmation before claiming success

### Unified OAuth (`tools/auth.py`)
- Single `token.json` and `credentials.json` for both Calendar and Gmail
- Combined scopes: `calendar.events`, `gmail.modify`, `gmail.compose`
- Service caching: `_SERVICE_CACHE` dict prevents rebuilding API clients on each call
- Scopes-aware invalidation

### Frontend-Backend Contract (`server.py`)
- Response format: `{ reply: str, events: list, emails: list }`
- Server parses LangChain tool messages (walks backwards to find last event/email result)
- Frontend renders `EventCard` / `EmailCard` for structured data, plain text otherwise

### Timezone Handling
- Default: `America/New_York`
- Auto-injection into datetime objects missing timezone info
- Uses Python's `zoneinfo` (not `pytz`)

## Coding Conventions

### Python
- Use type hints for function signatures
- Tools should return dicts with clear success/error messages
- Error handling: return descriptive error messages, don't raise exceptions in tools
- Ambiguity resolution: when multiple matches found, return list and ask user to clarify (safe default)
- Service caching: always check `_SERVICE_CACHE` before building new API clients

### TypeScript / React
- Functional components with TypeScript
- Tailwind CSS for all styling (no CSS modules)
- Component props should be typed interfaces
- Keep components simple and focused

### Testing
- Use pytest for all Python tests
- Mock Google API services entirely (no real calls in tests)
- Test tools via `.func()` to bypass LangChain wrapper
- Cover both success and error cases
- Fixtures in `conftest.py` for reusable mocks

## File Structure

```
agent.py              # LangChain agent setup, tool registration
server.py             # FastAPI endpoint, message history, response parsing
main.py               # Terminal CLI interface
tools/
  auth.py             # OAuth2 flow, token management, service caching
  calendar.py         # 7 calendar tools
  gmail.py            # 9 Gmail tools
web/
  app/page.tsx        # Chat UI
  app/components/     # EventCard, EmailCard
tests/                # pytest test suite
```

## Important Implementation Details

### Ambiguous Event Matching
When deleting/updating events without `event_id`:
1. Search by query + date range
2. If multiple matches, return them with error message
3. Never guess which event the user meant

### MIME Message Construction (`gmail.py`)
- Use `email.mime` to build RFC 2822 messages
- Support plain text and HTML alternatives
- Threading headers: `In-Reply-To`, `References` for email chains
- Base64url encoding for Gmail's raw format

### Response Parsing (`server.py`)
- Walk backwards through message history to find last tool result
- Handle formats: string JSON, dict, Python AST literals
- Stop at first human message to avoid cross-turn pollution
- Extract events/emails from tool results for frontend cards

### Recurring Events
- Always use `singleEvents=True` in Calendar API calls
- This expands recurring events into individual instances
- Allows targeting specific occurrences

## Common Commands

### Development
```bash
# Terminal CLI
python main.py

# Backend server
uvicorn server:app --reload

# Frontend
cd web && npm run dev

# Tests
pytest tests/
pytest tests/test_calendar_tools.py -v
```

### OAuth Setup
On first run, user is sent to browser for Google OAuth consent. Token stored in `token.json`, auto-refreshed when expired.

## Safety Guidelines

### Destructive Actions
- Calendar: deletion requires confirmation (ambiguity check)
- Gmail: trash is reversible, permanent delete is not
- System prompt forbids sending emails without explicit user request

### Error Handling
- Tools should return error dicts, not raise exceptions
- Ambiguous queries return matches and ask for clarification
- API errors should be caught and returned as descriptive messages

## TODOs / Planned Features
- Daily calendar summaries
- Improved timezone normalization
- Ambiguous match selection UI (frontend)
- Safety guardrails for destructive actions
- Multi-user support (persistence, auth on web endpoint)

## Environment Variables
```
OPENAI_API_KEY=sk-proj-...
FRONTEND_ORIGIN=http://localhost:3000
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Notes for Claude
- Always read files before editing (never edit blind)
- Use type hints in Python code
- Test new tools with pytest before committing
- Maintain the tool-calling pattern (no direct API calls outside tools)
- Follow timezone injection pattern for consistency
- When adding new tools, register in `agent.py` and add tests
- Frontend components should handle missing/malformed data gracefully
