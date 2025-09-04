import asyncio
from typing import TypedDict
from langchain_openai import ChatOpenAI
from langgraph_supervisor import create_supervisor
from langgraph.prebuilt import create_react_agent

from langchain.tools import tool

from core.agents.file_creator import build_agent

    

@tool
def dummy_tool():
    """must be called"""
    print("dummy tool!!!!")

EMBEDDED_PROMPT = """You are an embedded agent.
You will be called by a supervisor agent to handle user requests.
First!! you must call dummy_tool(). it must be call once.
You must ALWAYS produce a final answer to the user request, even if you have to make up an answer.
"""

def build_embedded_agent(model: str):
    llm = ChatOpenAI(model=model, temperature=0)
    
    agent = create_react_agent(
        llm,
        tools=[dummy_tool],
        prompt=EMBEDDED_PROMPT,
        name="embedded_agent"
    )
    
    
    return agent


SUPERVISOR_PROMPT = """You are a planner.

FOR EVERY USER REQUEST, RUN THIS SEQUENCE:
1) Transfer to `creator agent` exactly once. Wait until it transfers back.

Do NOT generate code yourself. Do NOT call any tools yourself.
Do NOT skip step 2 even if step 1 already produced output.
"""

from dotenv import load_dotenv
load_dotenv()

def build_supervisor(agents: list[any], model: str):
    llm = ChatOpenAI(model=model, streaming=True)
    
    workflow = create_supervisor(
        agents,
        model=llm,
        prompt=SUPERVISOR_PROMPT
    )

    return workflow.compile()

def build():
    # embedded_agent = build_embedded_agent("gpt-4")
    # supervisor = build_supervisor([embedded_agent], "gpt-4")
    creator_agent = build_agent('gpt-4')
    supervisor = build_supervisor([creator_agent], "gpt-4")
    return supervisor

class Orchestrator:
    def __init__(self, events_q):
        self.events_q = events_q
        self.agent = build()

    async def run(self, user_input: str):
        payload = {"messages": [{"role": "user", "content": user_input}],}
        async for ev in self.agent.astream_events(payload, version="v2"):
            typ = ev.get("event")
            data = ev.get("data") or {}
            if typ == "on_chat_model_stream":
                token = data.get("chunk") or data.get("token") or ""
                if token:
                    await self.events_q.put({"type": "token", "text": token})

        #     elif typ == "on_tool_start":
        #         await self.events_q.put({"type": "tool_start",
        #                                  "name": ev.get("name") or "tool",
        #                                  "args": data.get("input")})
        #     elif typ == "on_tool_end":
        #         await self.events_q.put({"type": "tool_end",
        #                                  "name": ev.get("name") or "tool",
        #                                  "output": data.get("output")})
        #     elif typ == "on_chain_error":
        #         await self.events_q.put({"type": "error", "message": str(data.get("error"))})
        # await self.events_q.put({"type": "final", "text": "something"})
        await self.events_q.put({'type: tool_start'})
        
        await self.events_q.put({'type': 'done'})
        
        
if __name__ == "__main__":
    agent = build()
    user_input = "create a file named hello.txt with the content 'Hello, World!'"
    payload = {
        "messages": {
            "role": "user",
            "content": user_input,
        }
    }
    
    events_q = asyncio.Queue()
    orch = Orchestrator(events_q)
    asyncio.run(orch.run(user_input))
    
    temp_items = []
    while not events_q.empty():
        item = events_q.get_nowait()
        temp_items.append(item)
        print(f'ev: {item}')

    
    # res = agent.invoke(payload)
    # print(f'res: {res}')
    