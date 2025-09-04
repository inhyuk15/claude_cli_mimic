from typing import Annotated, Optional, TypedDict
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.types import interrupt
from langchain.tools import tool
from langgraph.graph.message import add_messages
from langchain_core.messages import SystemMessage, HumanMessage, BaseMessage


SYSTEM_PROMPT = """You MUST get human approval before executing any tool.
However, approval is enforced by the graph. Provide a concise plan if you intend to call tools.
"""

@tool("write_file")
def file_write_tool(path:str, content: str) -> str:
    """write content to a file at the given path"""
    return f'[mock] write to {path} len={len(content)}'

class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    approved: Optional[bool]


def build_llm(model, tools:list[any], temperature = 0):
    return ChatOpenAI(
        model=model,
        temperature=temperature
    ).bind_tools(tools)

    
def has_tool_calls(state):
    last = state["messages"][-1]
    return bool(getattr(last, "tool_calls", None))

def chatbot_factory(llm_with_tools):
    async def chatbot(state: AgentState):
        msgs = [SystemMessage(SYSTEM_PROMPT), *state["messages"]]
        ai_msg = await llm_with_tools.ainvoke(msgs)
        return ai_msg
    return chatbot
    

async def approval_gate(state: AgentState):
    """
    strict approval gate. (must be passed)
    
    TODO:
    *if all system do well, it would be better to delegate llm to get human approval
    """
    last = state['messages'][-1]
    plan = [{'tool': c['name'], 'args': c['args']} for c in getattr(last, 'tool_calls', [])]
    resp = interrupt({'type': 'approval_request', 'plan': plan})
    return {'approved': resp['data'].get('approved', False)}


def route_from_chatbot(state: AgentState):
    return 'approval_gate' if has_tool_calls(state) else END


def route_from_gate(state: AgentState):
    return END if not state.get('approved') else 'tools'


def build_agent(model: str, tools: list[any] = [file_write_tool]):
    """
    tool 따로 빼야됨
    """
    
    llm_with_tools = build_llm(model, tools)
    chatbot = chatbot_factory(llm_with_tools)
    tool_node = ToolNode(tools)
    
    graph_builder = StateGraph(AgentState)
    graph_builder.add_node('chatbot', chatbot)
    graph_builder.add_node('tools', tool_node)
    graph_builder.add_node('approval_gate', approval_gate)
    
    graph_builder.add_edge(START, 'chatbot')
    graph_builder.add_conditional_edges(
        'chatbot',
        route_from_chatbot
    )
    graph_builder.add_conditional_edges(
        'chatbot',
        route_from_gate
    )
    graph_builder.add_edge('tools', 'chatbot')
    
    
    return graph_builder.compile(name="file_creator_agent")
    
