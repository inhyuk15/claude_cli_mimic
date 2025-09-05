"""
langgraph agent에서 발생하는 event들, orchestrator 전용 데이터 도메인
"""

from typing import Any, Literal, TypedDict, Union


class TokenEvent(TypedDict):
    type: Literal['token']
    tool: str
    args: dict
    
class ToolStartEvent(TypedDict):
    type: Literal['tool_start']
    tool: str
    args: list[str]
    run_id: str
    step: str
    node: str
    thread_id: str
    tags: str
    parent_ids: list[str] #... 이게 근데 굳이 필요한가?
    
class ToolEndEvent(TypedDict):
    type: Literal['tool_end']
    tool: str
    output_preview: Any

class InterruptEvent(TypedDict):
    type: Literal['interrupt']
    payload = dict

class DoneEvent(TypedDict):
    type: Literal['done']
    
class ErrorEvent(TypedDict):
    type: Literal['error']
    message: str
    
DomainEvent = Union[
    TokenEvent, ToolStartEvent, ToolEndEvent, InterruptEvent, DoneEvent, ErrorEvent,
]
    