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
load_dotenv()

class ChatApp(App):
    def __init__(self):
        super().__init__()
        self.event_q = asyncio.Queue()
        self.orchestrator = Orchestrator(self.event_q)
        
        self.workspace_root =None
        
        self.next_turn_id = 1
        self.turns: Dict[int, Turn] = {}
        self.turn_order: list[int] = []
        
        self.active_turn_id: Optional[int] = None
        self._current_answer_buffer: str = ""
        
        self._pump_worker = None
        
    def compose(self) -> ComposeResult:
        yield ChatLog(id="chat_log", markup=True)
        yield InputArea(placeholder="how can i help you")
        
    async def on_mount(self) -> None:
        self._startup_flow()      
        
    @work(exclusive=True, group="startup")
    async def _startup_flow(self) -> None:
        result = await self.push_screen_wait(WorkspaceConfirmScreen(os.getcwd()))
        self.workspace_root = os.getcwd() if result else None
        chat_log = self.query_one("#chat_log", ChatLog)
        chat_log.write("[bold green]Welcome to Claude CLI Mimic![/bold green]")
        if self.workspace_root:
            chat_log.write(f"[dim]cwd: {self.workspace_root}[/dim]")
        else:
            chat_log.write("[dim]No workspace selected. You can still chat.[/dim]")

        self.query_one(InputArea).focus()
        self._pump()

    
        
        
    async def on_input_area_submit(self, message: InputArea.Submit) -> None:
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
        
        

    def _start_thinking(self):
        pass
        
    def _stop_thinking(self):
        pass
    

    @work(exclusive=True, group='infer')
    async def run_infer(self, user_input: str):
        await self.orchestrator.run(user_input)
    
    @work(exclusive=True, group='pump')
    async def _pump(self):
        chat_log = self.query_one("#chat_log", ChatLog)
        
        while True:
            ev = await self.event_q.get()
            typ = ev.get("type")
            
            cur_turn:Optional[Turn] = (
                self.turns.get(self.active_turn_id) if self.active_turn_id else None
            )
            
            if typ == "token":
                text_content = ev.get('text', '')
                if hasattr(text_content, 'content'):
                    chunk = text_content.content
                    
                if not chunk:
                    continue
                
                if cur_turn:
                    if cur_turn.status =="thinking":
                        cur_turn.status = "streaming"
                        self._stop_thinking()
                    cur_turn.assistant_buffer += chunk

            elif typ == 'done':
                    chat_log.write(f'assistant: {cur_turn.assistant_buffer}')
                    cur_turn.assistant_buffer = ''
                    cur_turn.status='final'
                    
        

def main():
    app = ChatApp()
    app.run()

if __name__ == "__main__":
    main()