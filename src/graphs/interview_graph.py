"""
LangGraph graph definition for the interview bot.

Follows .cursor/langgraph-core.mdc:
- Explicit routing (no implicit cycles)
- Checkpointer handled by LangGraph platform
- Clear node definitions
"""

from langgraph.graph import StateGraph, END

from src.state.interview_state import InterviewState
from src.nodes.interview_nodes import (
    load_flow_node,
    ingest_user_answer_node,
    auto_advance_node,
    render_prompt_node,
    should_continue
)


def create_interview_graph():
    """
    Create the interview graph.
    
    Flow:
    1. load_flow: Initialize slots if new session
    2. ingest_user_answer: Write user's answer to slots
    3. auto_advance: Process automatic stages (message/action/gate/branch)
    4. render_prompt: Generate next question/confirm
    5. Route: Continue or end
    
    Returns:
        Compiled graph (checkpointer handled by LangGraph platform)
    """
    # Create graph builder
    builder = StateGraph(InterviewState)
    
    # Add nodes
    builder.add_node("load_flow", load_flow_node)
    builder.add_node("ingest_user_answer", ingest_user_answer_node)
    builder.add_node("auto_advance", auto_advance_node)
    builder.add_node("render_prompt", render_prompt_node)
    
    # Entry point
    builder.set_entry_point("load_flow")
    
    # Flow
    builder.add_edge("load_flow", "ingest_user_answer")
    builder.add_edge("ingest_user_answer", "auto_advance")
    builder.add_edge("auto_advance", "render_prompt")
    
    # Conditional routing from render_prompt
    builder.add_conditional_edges(
        "render_prompt",
        should_continue,
        {
            "continue": END,  # Stop and wait for user input
            "end": END  # Interview complete
        }
    )
    
    # Compile graph without checkpointer
    # LangGraph platform handles persistence automatically
    graph = builder.compile()
    
    return graph


# Export graph for langgraph.json
graph = create_interview_graph()
