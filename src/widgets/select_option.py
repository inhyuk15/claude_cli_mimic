from textual import on
from textual.widgets import OptionList
from textual.widgets.option_list import Option
from textual.message import Message



class SelectionMade(Message):
    def __init__(self, label: str, value: str) -> None:
        super().__init__()
        self.label = label
        self.value = value


class SelectOption(OptionList):
    def __init__(self, id: str, labels: list[any] = []) -> None:
        super().__init__(id=id)
        if labels:
            self.add_options(Option(label) for label in labels)
        
    def set_selection_options(self, labels: list[str], ids: list[str] | None = None):
        self.clear_options()
        if ids:
            self.add_options(Option(label) for label in labels)
        else:
            self.add_options(Option(label, id) for label, id in zip(labels, ids))
        self.index = 0
        
    @on(OptionList.OptionSelected)
    def on_option_selected(self, event: OptionList.OptionSelected) -> None:
        """ WARNING: selectino이 여러개 쓰일때 과연 괜찮은지 모르겠음"""
        opt = event.option
        label = opt.prompt
        value = opt.id or label
        
        self.post_message(SelectionMade(label, value))
        event.stop()
        
