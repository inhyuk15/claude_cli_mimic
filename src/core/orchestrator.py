import asyncio
from typing import Any, AsyncIterator, Dict, TypedDict
from langchain_openai import ChatOpenAI
from langgraph_supervisor import create_supervisor
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage
from langgraph.types import Command

from langchain.tools import tool

from core.agents.file_creator import build_agent


def _tool_start_payload(ev: dict) -> dict:
    # ev: {'event','data','name','run_id','metadata',...}
    data = ev.get("data", {})
    meta = ev.get("metadata", {})
    tool_input = data.get("input", {})

    args = {}
    path = tool_input.get("path")
    if path is not None:
        args["path"] = path

    content_val = tool_input.get("content")
    if isinstance(content_val, str):
        args["content_len"] = len(content_val)
        args["content_preview"] = content_val if len(content_val) <= 80 else content_val[:77] + "..."

    return {
        "tool": ev.get("name", "unknown_tool"),
        "args": args,
        "run_id": ev.get("run_id"),
        "step": meta.get("langgraph_step"),
        "node": meta.get("langgraph_node"),
        "thread_id": meta.get("thread_id"),
        "tags": ev.get("tags") or [],
        "parent_ids": ev.get("parent_ids") or [],
    }


def _tool_end_payload(ev: dict) -> dict:
    # 로그 기준: 결과는 항상 data["output"]로 온다고 가정
    data = ev.get("data", {})
    meta = ev.get("metadata", {})
    out = data.get("output")

    out_preview = out
    if isinstance(out_preview, str) and len(out_preview) > 120:
        out_preview = out_preview[:117] + "..."

    return {
        "tool": ev.get("name", "unknown_tool"),
        "output_preview": out_preview,
        "run_id": ev.get("run_id"),
        "step": meta.get("langgraph_step"),
        "node": meta.get("langgraph_node"),
        "thread_id": meta.get("thread_id"),
    }

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
    def __init__(self, events_q, cmd_q):
        self.events_q = events_q
        self.cmd_q = cmd_q
        self.agent = build()
        self._approval_future = None
        self.config = {'configurable': {'thread_id': 'conv-1'}}
        
        
    async def run(self, user_input: str):
        payload = {"messages": [HumanMessage(content=user_input)]}
        
        max_rounds, round = 10, 0
        
        while True:
            round += 1
            if round > max_rounds:
                await self._emit(etype='error', message='Too many interrupt rounds')
                break
                
            stream = self.agent.astream_events(payload, config=self.config, version='v2')
            intr = await self._process_events(stream)
            
            if not intr:
                break
            
            await self._emit(etype='interrupt', payload=intr)
            resume = await self.cmd_q.get()
            payload = Command(resume=resume)
        
        await self.events_q.put({"type": "done"})

    
    async def _process_events(self, stream: AsyncIterator[Dict[str, Any]]):
        async for ev in stream:
            event = ev.get('event')
            data = ev.get('data') or {}
            
            if event =='on_chat_model_stream':
                chunk = data.get('chunk') or data.get('token')
                text = getattr(chunk, 'content') if chunk is not None else ''
                if text:
                    await self._emit(etype='token', content=text)
                    
            elif event == 'on_tool_start':
                await self._emit(etype='on_tool_start', content=_tool_start_payload(ev))
                
            elif event =='on_tool_end':
                await self._emit(etype='on_tool_end', content=_tool_end_payload(ev))
                
            elif event == 'on_chain_stream':
                chunk = data.get('chunk')
                intr = chunk.get('__interrupt__')
                if intr:
                    return intr
                
        return None
 
    
    async def _emit(self, etype: str, **kwargs):
        await self.events_q.put({'type': etype, **kwargs})
    
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
    cmd_q = asyncio.Queue()
    orch = Orchestrator(events_q, cmd_q)
    user_input = "create a file named hello.txt with the content 'Hello, World!'"
    # user_input = "hi"
    consumer = asyncio.create_task(consume_and_auto_approve(events_q, orch))
    await orch.run(user_input)
    await consumer

if __name__ == "__main__":
    asyncio.run(main())
    