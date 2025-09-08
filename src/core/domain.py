"""
langgraph agent에서 발생하는 event들, orchestrator 전용 데이터 도메인
"""

from dataclasses import dataclass
from typing import Any, Literal, TypedDict, Union

class TokenEvent(TypedDict, total=False):
    type: Literal['token']
    text: str


class ToolStartEvent(TypedDict, total=False):
    type: Literal['tool_start']
    tool: str
    args: dict[str, Any]


class ToolEndEvent(TypedDict, total=False):
    type: Literal['tool_end']
    tool: str
    output_preview: Any


class InterruptEvent(TypedDict, total=False):
    type: Literal['interrupt']
    payload = dict


class DoneEvent(TypedDict, total=False):
    type: Literal['done']


class ErrorEvent(TypedDict, total=False):
    type: Literal['error']
    message: str
    
    
DomainEvent = Union[
    TokenEvent, ToolStartEvent, ToolEndEvent, InterruptEvent, DoneEvent, ErrorEvent,
]
    