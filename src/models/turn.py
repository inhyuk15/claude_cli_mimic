from dataclasses import dataclass, field


@dataclass
class Turn:
    turn_id: int
    user_text: str = ""
    assistant_buffer: str = ""
    status: str = 'idle'
    tool_logs: list[str] = field(default_factory=list)
