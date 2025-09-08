"""
Data models for the Claude CLI Mimic application.
"""
from dataclasses import dataclass, field


@dataclass
class Turn:
    """
    Represents a single conversation turn between user and assistant.
    """
    turn_id: int
    user_text: str = ""
    assistant_buffer: str = ""
    status: str = 'idle'
    tool_logs: list[str] = field(default_factory=list)
