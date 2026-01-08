from agent import agent

if __name__ == "__main__":
    res = agent.invoke(
        {"messages": [
            {"role": "user", 
            "content": "Create an event on January 8, 2026 from 1pm to 3pm America/New_York called 'Meeting with Michel'."}
        ]}
    )
    print(res)
