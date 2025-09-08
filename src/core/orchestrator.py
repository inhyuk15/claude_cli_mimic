import asyncio
from typing import Any, Dict

from core.agents.file_creator import build_agent
from core.domain import DomainEvent, DoneEvent, InterruptEvent, TokenEvent, ToolEndEvent, ToolStartEvent
from langchain_core.messages import HumanMessage

from langgraph.types import Command

from core.langgraph_adapter import adapt_events
from dotenv import load_dotenv

load_dotenv()


class Orchestrator:
    def __init__(self, events_q: asyncio.Queue, cmd_q: asyncio.Queue):
        self.agent = build_agent('gpt-4o')
        self.config = {'configurable': {'thread_id': 'conv-1'}} # TODO: thread id 조정 필요
        self.events_q = events_q
        self.cmd_q = cmd_q
        
    async def _emit(self, ev: Dict[str, Any]):
        await self.events_q.put(ev)
    
    async def run(self, user_input: str):
        payload = {"messages": [HumanMessage(content=user_input)]}
        
        while True:
            intr = False
            stream = self.agent.astream_events(payload, config=self.config, version='v2')
            
            async for ev in adapt_events(stream):    
                await self._emit(ev)
                
                if ev.get('type') == 'interrupt':
                    intr = True
                    await self.cmd_q.put(True)
                    resume = await self.cmd_q.get()
                    payload = Command(resume = resume)
                    break
                    
            if not intr:
                break
            
        await self._emit({'type': 'done'})


#--------------- test 용
async def consume(q: asyncio.Queue, orch: Orchestrator):
    while True:
        ev = await q.get()
        
        etype = ev.get("type")
        if etype == "token":
            print(ev.get("text", ""), end="", flush=True)
        elif etype == "tool_start":
            print(f"\n[tool start] {ev.get('tool')} {dict(ev.get('args') or {})}")
        elif etype == "tool_end":
            print(f"[tool end] {ev.get('tool')} -> {ev.get('output_preview')!r}")
        elif etype == "interrupt":
            print(f"\n[interrupt] {dict(ev.get('payload') or {})}")
        elif etype == "error":
            print(f"\n[error] {ev.get('message')}")
        elif etype == "done":
            break

        
async def main():
    events_q = asyncio.Queue()
    cmd_q = asyncio.Queue()
    orch = Orchestrator(events_q, cmd_q)
    user_input = "create a file named hello.txt with the content 'Hello, World!'"
    # user_input = "hi"
    consumer = asyncio.create_task(consume(events_q, orch))
    await orch.run(user_input)
    await consumer

if __name__ == "__main__":
    asyncio.run(main())
    