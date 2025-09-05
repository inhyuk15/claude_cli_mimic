import asyncio
from typing import TypedDict
from langchain_openai import ChatOpenAI
from langgraph_supervisor import create_supervisor
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage
from langgraph.types import Command

from langchain.tools import tool

from core.agents.file_creator import build_agent

def _to_text_from_stream_data(data) -> str:
    chunk = data.get("chunk") or data.get("token")
    if chunk is None:
        return ""
    content = getattr(chunk, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(chunk, str):
        return chunk
    return ""

def _is_tool_call_stream(data) -> bool:
    chunk = data.get("chunk")
    if getattr(chunk, "tool_calls", None):
        return True
    if data.get("tool_call_chunks") or data.get("invalid_tool_calls"):
        return True
    add = getattr(chunk, "additional_kwargs", {}) if chunk is not None else {}
    return bool(add.get("tool_calls"))

SUPERVISOR_PROMPT = """You are a planner.

FOR EVERY USER REQUEST, RUN THIS SEQUENCE:
1) Transfer to `creator agent` exactly once. Wait until it transfers back.

Do NOT generate code yourself. Do NOT call any tools yourself.
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
    creator_agent = build_agent('gpt-4o')
    return creator_agent
    # supervisor = build_supervisor([creator_agent], "gpt-4o")
    # return supervisor

class Orchestrator:
    def __init__(self, events_q):
        self.events_q = events_q
        self.agent = build()
        self._approval_future = None
        
        
    async def run(self, user_input: str):
        config = {"configurable": {"thread_id": "conv-1"}}
        payload = {"messages": [HumanMessage(content=user_input)]}

        async for ev in self.agent.astream_events(payload, config=config, version='v2'):
            event = ev.get("event"); data = ev.get("data") or {}
            if event == 'on_chain_stream':
                chunk = data.get('chunk') or {}
                if '__interrupt__' in chunk:
                    await self.events_q.put({'type': 'interrupt'})
                    cmd = Command(resume=True)
                    
                    async for ev2 in self.agent.astream_events(
                        cmd, config=config, version='v2'
                    ):
                        event = ev2.get('event')
                        if event == 'on_tool_start':
                            await self.events_q.put({'type': 'on_tool_start', 'content': ev2})
                        elif event == 'on_tool_end':
                            await self.events_q.put({'type': 'on_tool_end', 'content': ev2})
                    
        await self.events_q.put({"type": "done"})
    
    # UI가 호출해주는 승인 setter
    def set_approval(self, value: bool):
        if self._approval_future and not self._approval_future.done():
            self._approval_future.set_result(bool(value))

    async def _wait_for_approval(self) -> bool:
        import asyncio
        self._approval_future = asyncio.get_running_loop().create_future()
        return await self._approval_future
    
async def consume_and_auto_approve(q: asyncio.Queue, orch: Orchestrator):
    while True:
        ev = await q.get()
        print("ev:", ev)
        if ev.get("type") == "approval_request":
            # ask user on console (non-blocking via executor)
            prompt = f"Approval requested: {ev.get('plan')}. Approve? (y/n): "
            loop = asyncio.get_running_loop()
            answer = await loop.run_in_executor(None, input, prompt)
            orch.set_approval(answer.strip().lower().startswith("y"))
        if ev.get("type") == "done":
            break
    
    
async def main():
    events_q = asyncio.Queue()
    orch = Orchestrator(events_q)
    user_input = "create a file named hello.txt with the content 'Hello, World!'"

    consumer = asyncio.create_task(consume_and_auto_approve(events_q, orch))
    await orch.run(user_input)
    await consumer

if __name__ == "__main__":
    asyncio.run(main())
    