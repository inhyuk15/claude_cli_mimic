"""
Claude CLI Mimic
"""

import os
from typing import Dict, Optional
from textual import work
from textual.app import App, ComposeResult
import asyncio

from core.orchestrator import Orchestrator
from models import Turn
from widgets import InputArea, ChatLog
from screens import WorkspaceConfirmScreen

from dotenv import load_dotenv

from widgets.select_option import SelectOption, SelectionMade
load_dotenv()


class ChatApp(App):
    def __init__(self):
        """Initialize the chat application with default state."""
        super().__init__()
        self.event_q = asyncio.Queue()
        self.cmd_q = asyncio.Queue()
        self.orchestrator = Orchestrator(self.event_q, self.cmd_q)
        
        self.workspace_root = None
        
        self.next_turn_id = 1
        self.turns: Dict[int, Turn] = {}
        self.turn_order: list[int] = []
        
        self.active_turn_id: Optional[int] = None
        self._current_answer_buffer: str = ""
        
        self._pump_worker = None
        
    def compose(self) -> ComposeResult:
        """
        Create the main UI layout.
        """
        yield ChatLog(id="chat_log", markup=True)
        yield InputArea(id="input_text", placeholder="how can i help you")
        yield SelectOption(id="input_selection")
        
    async def on_mount(self) -> None:
        """Initialize the application after the UI is mounted."""
        sel = self.query_one('#input_selection', SelectOption)
        txt = self.query_one('#input_text', InputArea)
        sel.visible = False
        txt.visible = True
        
        self._startup_flow()
        
        
    @work(exclusive=True, group="startup")
    async def _startup_flow(self) -> None:
        """
        Handle the application startup sequence.
        
        This method:
        1. Shows workspace confirmation dialog
        2. Sets up the workspace if confirmed
        3. Displays welcome message
        4. Starts the event processing pump
        """
        
        result = await self.push_screen_wait(WorkspaceConfirmScreen(os.getcwd()))
        self.workspace_root = os.getcwd() if result else None
        chat_log = self.query_one("#chat_log", ChatLog)
        chat_log.write("[bold green]Welcome to Claude CLI Mimic![/bold green]")
        if self.workspace_root:
            chat_log.write(f"[dim]cwd: {self.workspace_root}[/dim]")
        else:
            chat_log.write("[dim]No workspace selected. You can still chat.[/dim]")
        
        def apply_mode():
            self._change_input_mode(is_selection=False)
            self.set_focus(self.query_one('#input_text', InputArea))
            
        self.call_after_refresh(apply_mode)
        
        self._pump()

        
    async def on_input_area_submit(self, message: InputArea.Submit) -> None:
        """
        1. Creates a new conversation turn
        2. Displays the user message
        3. Initiates AI response generation
        """
        text = message.value.strip()
        
        turn_id = self.next_turn_id
        self.next_turn_id += 1
        
        turn = Turn(turn_id=turn_id, user_text=text, status="thinking")
        self.turns[turn_id] = turn
        self.turn_order.append(turn_id)
        self.active_turn_id = turn_id
        
        chat_log = self.query_one("#chat_log", ChatLog)
        chat_log.write(f"[dim] user: {text} [/dim]")
        
        self._start_thinking()
        self.run_infer(text)
        
    async def on_selection_made(self, message: SelectionMade) -> None:
        """
        file_creator의 요청을 반환.
        
        TODO: boolean만 고려해서 작성했지만 선택지가 나오는 경우도 고려해야됨.
        """
        approve = (message.value == 'yes') or message.label.startswith('1')
        await self.cmd_q.put(approve)
        self._change_input_mode(is_selection=False)
        

    def _start_thinking(self):
        """Start the thinking indicator (placeholder for future implementation)."""
        pass
        
    def _stop_thinking(self):
        """Stop the thinking indicator (placeholder for future implementation)."""
        pass
    
    def _change_input_mode(self, is_selection: bool):
        input_selection = self.query_one('#input_selection')
        input_text = self.query_one('#input_text')
        
        if is_selection:
            input_selection.visible, input_text.visible = True, False
            input_selection.focus()
        else:
            input_selection.visible, input_text.visible = False, True
            input_text.focus()


    @work(exclusive=True, group='infer')
    async def run_infer(self, user_input: str):
        """
        Run agent inference on user input.
        """
        await self.orchestrator.run(user_input)
    
    @work(exclusive=True, group='pump')
    async def _pump(self):
        """
        Event processing loop.
   
        Event types handled:
        - 'token': Streaming response tokens from the AI
        - 'done': Response completion indicator
        """
        chat_log = self.query_one("#chat_log", ChatLog)
        
        while True:
            ev = await self.event_q.get()
            type = ev.get("type", '')
            
            cur_turn: Optional[Turn] = (
                self.turns.get(self.active_turn_id) if self.active_turn_id else None
            )
            
            if type == "token":
                text = ev.get('text', '')
                if not text:
                    continue
                
                if cur_turn:
                    if cur_turn.status == "thinking":
                        cur_turn.status = "streaming"
                        self._stop_thinking()
                    cur_turn.assistant_buffer += text
            elif type == 'tool_start':
                """ draw tool calling state """
                tool_name = ev.get('tool')
                args = ev.get('args')
                log = f'toolname: {tool_name}, args: {args}'
                chat_log.write(f'tool calling start: {log}')
                
            elif type == 'tool_end':
                """ draw tool calling end, and draw result of tool calling """
                tool_name = ev.get('tool')
                output = ev.get('output_preview')
                log = f'toolname: {tool_name}, output: {output}'
                chat_log.write(f'tool calling end: {log}')
            elif type == 'interrupt':
                """ get user input whether to approve """
                self._change_input_mode(is_selection=True)
                selection = self.query_one(SelectOption)
                selection.set_selection_options(['1. yes', '2. no'], ['yes', 'no'])
                
            elif type == 'done':
                if cur_turn:
                    chat_log.write(f'assistant: {cur_turn.assistant_buffer}')
                    cur_turn.assistant_buffer = ''
                    cur_turn.status = 'final'
                    

def main():
    app = ChatApp()
    app.run()


if __name__ == "__main__":
    main()