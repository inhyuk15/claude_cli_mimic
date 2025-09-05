from typing import Annotated, Optional, TypedDict
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.types import interrupt
from langchain.tools import tool
from langgraph.graph.message import add_messages
from langchain_core.messages import SystemMessage, HumanMessage, BaseMessage
from langgraph.checkpoint.memory import MemorySaver


SYSTEM_PROMPT = """You are a file creation assistant. 
When asked to create a file, you MUST use the write_file tool.
The system will ask for human approval before executing tools - just proceed with your plan.

Example: If user asks to create hello.txt with "Hello World", call write_file(path="hello.txt", content="Hello World").
"""
@tool("write_file")
def file_write_tool(path:str, content: str) -> str:
    """write content to a file at the given path"""
    preview = (content[:80] + '_') if len(content) > 80 else content
    approved = interrupt({
        'type': 'approval_request',
        'plan':[{'tool': 'write_file',
                 'args': {'path': path, 'content_preview': preview}}]
    })
    if not approved:
        return '[cancelled] user denied'
    
    return f'[mock] write to {path} len={len(content)}'

class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    approved: Optional[bool]


def build_llm(model, tools:list[any], temperature = 0):
    return ChatOpenAI(
        model=model,
        temperature=temperature,
        streaming=True,
        model_kwargs={'tool_choice': 'required'},
    ).bind_tools(tools)

    
def has_tool_calls(state):
    last = state["messages"][-1]
    return bool(getattr(last, "tool_calls", None))

def chatbot_factory(llm_with_tools):
    async def chatbot(state: AgentState):
        msgs = [SystemMessage(SYSTEM_PROMPT), *state["messages"]]
        ai_msg = await llm_with_tools.ainvoke(msgs)
        return {'messages': [ai_msg]}
    return chatbot


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
    
    
    graph_builder.add_edge(START, 'chatbot')
    graph_builder.add_conditional_edges('chatbot', tools_condition)
    graph_builder.add_edge('tools', 'chatbot')
    
    return graph_builder.compile(name="file_creator_agent", checkpointer=MemorySaver())
    
