from dotenv import load_dotenv
load_dotenv()

from tools import create_event, list_events_for_day, list_events_between, find_events, delete_event, update_event
from langchain.chat_models import init_chat_model
from langchain.agents import create_agent

model = init_chat_model("gpt-4o-mini", temperature=0)

agent = create_agent(
    model=model,
    tools=[create_event, list_events_for_day, list_events_between, find_events, delete_event, update_event],
    system_prompt=(
        "You are a helpful assistant that manages my Google Calendar. "
        "When asked to create an event, you MUST call the create_event tool. "
        "Use any of the tools available to you to complete the task. If you need more tools, let me know"
        "Do not claim an event was created unless the tool returns success."
    ),
)
