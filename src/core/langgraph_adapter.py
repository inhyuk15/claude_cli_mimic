
from typing import Any, AsyncIterator, Dict, Mapping, Optional
from core.domain import InterruptEvent, TokenEvent, ToolEndEvent, ToolStartEvent

def _extract_text(data: Mapping[str, Any]) -> Optional[str]:
    ch = data.get('chunk')
    if isinstance(ch, str):
        return ch or None
    
    text = getattr(ch, 'content', None)
    return text if isinstance(text, str) and text else None

def _start_payload(ev: dict[str, Any]) -> dict[str, Any]:
    data = ev.get('data') or {}
    meta = ev.get('metadata') or {}
    tool_input = data.get('input') or {}
    
    args: dict[str, Any] = {}
    if isinstance(tool_input, dict):
        if (p := tool_input.get('path')) is not None:
            args['path'] = p
            
        content_val = tool_input.get('content')    
        if isinstance(content_val, str):
            args['content_len'] = len(content_val)
            args['content_preview'] = content_val if len(content_val) <= 80 else content_val[:77] + '...'
    
    return {
        'type': 'tool_start',
        'tool': ev.get('name'),
        'args': args,
        'step': meta.get('langgraph_step'),
        'node': meta.get('langgraph_node'),
        'tags': ev.get('tags')
    }
    

def _end_payload(ev: dict[str, Any]) -> dict[str, Any]:
    data = ev.get('data') or {}
    out = data.get('output')
    
    out_preview = out
    if isinstance(out_preview, str) and len(out_preview) > 120:
        out_preview = out_preview[:117] + '...'
    
    return {
        'type': 'tool_end',
        'tool': ev.get('name'),
        'out_preview': out_preview,
    }

def _extract_interrupt(data: Mapping[str, Any]) -> Optional[InterruptEvent]:
    ch = data.get('chunk')
    if isinstance(ch, dict):
        intr = ch.get('__interrupt__')
        if intr:
            return {'type': 'interrupt', 'payload': intr}
    
    return None
    


async def adapt_events(stream: AsyncIterator[Dict[str, Any]]):
    """
    langchain의 astream_events를 orchestrator가 소비할 DomainEvent로 변환
    """
    async for ev in stream:
        event = ev.get('event')
        data = ev.get('data') or {}
        
        intr = _extract_interrupt(data)
        if intr:
            yield {'type': 'interrupt', 'payload': intr}
            continue
        
        if event == 'on_chat_model_stream':
            text = _extract_text(data)
            if text:
                yield {'type': 'token', 'text': text}
            continue

        elif event == 'on_tool_start':
            # TODO: interrupt 전후로 tool의 사용을 구분하기 위해 tag 도입을 고려해봐야함.
            yield _start_payload(ev)
            
        elif event == 'on_tool_end':
            yield _end_payload(ev)
        
                