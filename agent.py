from dotenv import load_dotenv
load_dotenv()

from tools import create_event
from langchain.chat_models import init_chat_model
from langchain.agents import create_agent

model = init_chat_model("gpt-4o-mini", temperature=0)

agent = create_agent(
    model=model,
    tools=[create_event],
    system_prompt=(
        "You are a helpful assistant that manages my Google Calendar. "
        "When asked to create an event, you MUST call the create_event tool. "
        "Do not claim an event was created unless the tool returns success."
    ),
)

if __name__ == "__main__":
    res = agent.invoke(
        {"messages": [
            {"role": "user", 
            "content": "Create an event on January 8, 2026 from 1pm to 3pm America/New_York called 'Meeting with Michel'."}
        ]}
    )
    print(res)
    print(res)
