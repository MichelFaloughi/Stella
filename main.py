from agent import agent

if __name__ == "__main__":
    # 1) Create a disposable event
    res = agent.invoke({
        "messages": [{
            "role": "user",
            "content": "Create an event on 2026-01-13 from 10:00 AM to 10:15 AM America/New_York called __UPDATE_ME_CANARY__"
        }]
    })
    print(res["messages"][-1].content)

    # 2) Update its title (agent should resolve via query+range and patch)
    res = agent.invoke({
        "messages": [{
            "role": "user",
            "content": "Rename '__UPDATE_ME_CANARY__' to '__UPDATED_CANARY__' between 2026-01-12 and 2026-01-14"
        }]
    })
    print(res["messages"][-1].content)

    # 3) Confirm
    res = agent.invoke({
        "messages": [{
            "role": "user",
            "content": "Find events matching '__UPDATED_CANARY__' between 2026-01-12 and 2026-01-14"
        }]
    })
    print(res["messages"][-1].content)

    # 4) Cleanup (delete)
    res = agent.invoke({
        "messages": [{
            "role": "user",
            "content": "Delete '__UPDATED_CANARY__' between 2026-01-12 and 2026-01-14"
        }]
    })
    print(res["messages"][-1].content)





