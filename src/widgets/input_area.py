"""
Custom input widgets for the Claude CLI Mimic application.
"""
from textual.widgets import Input
from textual.message import Message


class InputArea(Input):
    class Submit(Message, bubble=True):
        def __init__(self, value: str) -> None:
            super().__init__()
            self.value = value
            
    async def on_key(self, event) -> None:
        if event.key == "enter":
            self.post_message(self.Submit(self.value))
            self.value = ""
