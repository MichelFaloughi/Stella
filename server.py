# server.py
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
from pydantic import BaseModel

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

    return {"reply": reply}
