"""
Modal screens for the Claude CLI Mimic application.
"""

from textual import on
from textual.widgets import Static, OptionList
from textual.widgets.option_list import Option
from textual.containers import Center, Vertical
from textual.screen import ModalScreen


class WorkspaceConfirmScreen(ModalScreen[bool]):
    """워크스페이스 접근 권한을 확인하는 모달 화면"""
    CSS = """
#panel {
    width: 80%;
    max-width: 100;
    border: round $secondary;     /* 둥근 테두리 */
    padding: 1 2;                 /* 패딩 */
}
#ws_options {
    margin-top: 1;
}
#panel OptionList {
    border: none;
    background: transparent;
}
    """
    BINDINGS = [
        ('1', 'choose_yes', 'yes'),
        ('2', 'choose_no', 'no'),
    ]
    
    def __init__(self, cwd: str) -> None:
        """
        Initialize the workspace confirmation screen.
        
        Args:
            cwd (str): The current working directory path to display to the user
        """
        super().__init__()
        self.cwd = cwd
        
    def compose(self):
        """
        Create the UI layout for the confirmation dialog.
        
        Returns:
            The composed UI elements including title, warning text, and options
        """
        yield Center(
                Vertical(
                    Static("[bold orange]Do you trust the files in this folder?[/bold orange]\n", markup=True, classes="title"),
                    Static(f"[bold]{self.cwd}[/bold]\n", markup=True),
                    Static(
                        "Claude Code may read files in this folder. Reading untrusted files may lead Claude Code to behave in unexpected ways.\n"
                        "With your permission Claude Code may execute files in this folder. Executing untrusted code is unsafe.\n",
                        markup=True,
                    ),
                    OptionList(
                        Option("1. Yes, proceed", id="yes"),
                        Option("2. No, exit",     id="no"),
                        id="ws_options",
                    ),
                ),
                id="panel",
            
        )
        
    async def _on_mount(self):
        """
        Set up the screen after it's mounted.
        
        This method focuses the option list and selects the first option
        by default for better keyboard navigation.
        """
        ol = self.query_one(OptionList)
        ol.focus()
        ol.index = 0
        
    @on(OptionList.OptionSelected)
    def on_option_selected(self, event: OptionList.OptionSelected) -> None:
        """
        Handle option selection from the list.
        
        Args:
            event: The option selection event containing the selected option ID
        """
        self.dismiss(event.option_id == 'yes')
        
    def action_choose_yes(self) -> None:
        """Handle the keyboard shortcut for choosing 'Yes, proceed'."""
        self.dismiss(True)
    
    def action_choose_no(self) -> None:
        """Handle the keyboard shortcut for choosing 'No, exit'."""
        self.dismiss(False)
