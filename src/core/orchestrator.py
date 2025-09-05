import asyncio
from typing import TypedDict
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
        
        
    async def run(self, user_input: str):
        config = {"configurable": {"thread_id": "conv-1"}}
        payload = {"messages": [HumanMessage(content=user_input)]}

        async for ev in self.agent.astream_events(payload, config=config, version='v2'):
            event = ev.get("event"); data = ev.get("data") or {}
            print(ev)
            if event == 'on_chat_model_stream':
                token = data.get('chunk') or data.get('token') or ''
                content = getattr(token, 'content')
                if content:
                    await self.events_q.put({'type': 'token', 'content': content})
            elif event == 'on_chain_stream':
                chunk = data.get('chunk') or {}
                intr = chunk.get('__interrupt__')
                if intr:
                    await self.events_q.put({"type": "interrupt", "payload": intr})
                    # await self.cmd_q.put(True)
                    resume = await self.cmd_q.get()

                    cmd = Command(resume=resume)
                    async for ev2 in self.agent.astream_events(cmd, config=config, version="v2"):
                        e2 = ev2.get("event"); d2 = ev2.get("data") or {}
                        if e2 == "on_tool_start":
                            await self.events_q.put({"type": "on_tool_start",
                                                    "content": _tool_start_payload(ev2)})
                        elif e2 == "on_tool_end":
                            await self.events_q.put({"type": "on_tool_end",
                                                    "content": _tool_end_payload(ev2)})
                        elif e2 == "on_chat_model_stream":
                            # 재개 후 자연어가 오면 토큰으로 밀기
                            ch2 = d2.get("chunk") or d2.get("token")
                            t2 = getattr(ch2, "content", "") if ch2 is not None else ""
                            if t2:
                                await self.events_q.put({"type": "token", "content": t2})
            elif event == "on_tool_start":
                await self.events_q.put({"type": "on_tool_start",
                                        "content": _tool_start_payload(ev)})
            elif event == "on_tool_end":
                await self.events_q.put({"type": "on_tool_end",
                                        "content": _tool_end_payload(ev)})
                
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
    cmd_q = asyncio.Queue()
    orch = Orchestrator(events_q, cmd_q)
    user_input = "create a file named hello.txt with the content 'Hello, World!'"
    # user_input = "hi"
    consumer = asyncio.create_task(consume_and_auto_approve(events_q, orch))
    await orch.run(user_input)
    await consumer

if __name__ == "__main__":
    asyncio.run(main())
    