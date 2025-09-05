import asyncio

from core.agents.file_creator import build_agent
from core.domain import DomainEvent


class Emitter:
    def __init__(self, q: asyncio.Queue):
        self.q = q
        
    async def emit(self, event: DomainEvent):
        await self.q.put(event)
    

class ResumeDecider:
    """ interrupt 대응, 지금은 yes/no만 처리 """
    def __init__(self, q: asyncio.Queue):
        self.q = q
    
    async def decide(self, payload: dict) -> bool:
        return await self.q.get()
    

class Orchestrator:
    def __init__(self, events_q: asyncio.Queue, cmd_q: asyncio.Queue):
        self.agent = build_agent('gpt-4o')
        self.config = {'configurable': {'thread_id': 'conv-1'}} # TODO: thread id 조정 필요
        self.emitter = Emitter(events_q)
        self.decider = ResumeDecider(cmd_q)