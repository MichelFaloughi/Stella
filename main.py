from agent import agent

from datetime import datetime
from zoneinfo import ZoneInfo
def current_datetime_str():
    return datetime.now(ZoneInfo("America/New_York")).strftime(
        "%A, %Y-%m-%d %H:%M (%Z)"
    )


SYSTEM_HINT = (
    "You are Stella, a terminal calendar assistant. "
    "Be brief. Ask one clarifying question if required fields are missing. "
    "Never invent event titles unless the user explicitly says to block time."
    f"Current datetime: {current_datetime_str()}"
)

def main():
    messages = [{"role": "system", "content": SYSTEM_HINT}]

    print("Stella (Calendar) — type a request, or 'help', or 'exit'.")
    print("Examples: 'Create an event tomorrow 3-4pm called Gym' | 'List events next week'")

    while True:
        try:
            user = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nbye")
            break

        if not user:
            continue
        if user.lower() in {"exit", "quit", "q"}:
            print("bye")
            break
        if user.lower() == "help":
            print("Try: create / rename / delete / list. Include dates/times/timezone when possible.")
            continue

        messages.append({"role": "user", "content": user})

        res = agent.invoke({"messages": messages})
        reply = res["messages"][-1].content
        print(reply)

        # keep state exactly as returned
        messages = res["messages"]

if __name__ == "__main__":
    main()
