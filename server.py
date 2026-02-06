# server.py
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
from pydantic import BaseModel

from agent import agent
from main import SYSTEM_HINT

from dotenv import load_dotenv
import os

load_dotenv()
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN")



app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN],
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


@app.get("/")
def root():
    return {"status": "ok"}


from fastapi.responses import StreamingResponse
import json
import time

@app.get("/chat/stream")
def chat_stream(message: str):
    def event_generator():
        global messages
        messages.append({"role": "user", "content": message})

        for chunk in agent.stream({"messages": messages}):
            if "output" in chunk:
                yield f"data: {chunk['output']}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )

