# Stella 🗓️✨

**Stella** is a personal AI agent that manages my Google Calendar on my behalf.

It can understand natural language requests like:
> “Create a meeting tomorrow from 1–3pm”  
and safely turn them into real calendar actions using Google’s API.

---

## What it does (so far)

- ✅ Create calendar events via natural language
- 🔐 OAuth-based Google Calendar authentication
- 🧠 Tool-calling agent (no fake “I did it” responses)
- 🗂️ Clean separation between agent logic and calendar tools

---

## Planned features

- 🗑️ Delete events  
- ✏️ Update / reschedule events  
- 🔍 Find & list events (by day or query)  
- 🧾 Daily summaries  
- 🛡️ Safety guardrails for destructive actions  

---

## Tech stack

- Python 3.12  
- LangChain (tool-calling agents)  
- OpenAI (`gpt-4o-mini`)  
- Google Calendar API (OAuth2)  

---

## How it works (high level)

User → Agent (LLM)
↓
Tools (create / update / delete)
↓
Google Calendar API


The agent **can only act through explicit tools**, keeping behavior predictable and safe.

---

## Setup (minimal)

1. Create a Google Cloud project  
2. Enable Google Calendar API  
3. Add `credentials.json` to the repo  
4. Set `OPENAI_API_KEY` in your environment  
5. Run the agent and authorize once in the browser  

---

## Status

🚧 Work in progress — built as a personal automation / agent playground.

---

*Built for learning, safety, and control — not as a generic SaaS bot.*
