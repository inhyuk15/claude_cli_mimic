
from core.domain import ToolStartEvent


def _start_payload(ev: dict) -> ToolStartEvent:
    data = ev.get('data', {}) or {}
    meta = ev.get('metadata', {}) or {}
    tin = data.get('input', {}) or {}
    
    args: dict = {}
    if 'path' in tin:
        args['path'] = tin['path']
    cv = tin.get('content')
    if isinstance(cv, str):
        args['content_len'] = len(cv)
        #... 진짜 모르겟다