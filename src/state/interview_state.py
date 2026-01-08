"""
Interview state schema for LangGraph bot.

Follows .cursor/langgraph-core.mdc guidelines:
- Minimal typed state
- Reducers for accumulation (messages)
- Validation where needed
"""

from typing import Annotated, Any, Optional

from typing_extensions import TypedDict

from langgraph.graph import add_messages


def add_events(existing: list[dict[str, Any]] | None, new: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """
    Reducer for trace/event logs.

    LangGraph uses typing.Annotated reducers to merge state updates across nodes.
    """
    return (existing or []) + (new or [])


class PendingQuestion(TypedDict, total=False):
    """What we're waiting for from the user."""
    question_id: str
    save_to: str
    ask: str
    clarify_if: list[dict[str, Any]]


class PendingConfirm(TypedDict, total=False):
    """Pending confirmation from user."""
    confirm_id: str
    summary_template: str
    ask: str
    on_yes: str
    on_no: str


class InterviewState(TypedDict):
    """
    Minimal state for the interview bot.
    
    State persists per thread_id via checkpointer.
    
    Fields:
    - messages: Chat history (using add_messages reducer)
    - flow_id: Current flow identifier
    - active_stage_id: Current stage in the flow
    - slots: Captured interview data (nested dict matching flow context schema)
    - pending: What we're waiting for (question or confirm)
    - workflow_capture_state: Pointer for workflow mapping (active workflow, step index, buffer)
    - error: Last error (if any)
    - retry_count: Number of retries for current stage
    - auto_advance_count: Cycle protection counter
    - max_auto_advance_steps: Hard limit for auto-advance
    """
    
    # Chat history
    messages: Annotated[list, add_messages]

    # Trace / observability (append-only event log)
    events: Annotated[list[dict[str, Any]], add_events]
    
    # Flow navigation
    flow_id: str
    active_stage_id: str
    
    # Captured data
    slots: dict[str, Any]
    
    # What we're waiting for
    pending: Optional[PendingQuestion | PendingConfirm]
    
    # Workflow capture pointers
    workflow_capture_state: dict[str, Any]
    
    # Error handling
    error: Optional[str]
    retry_count: int
    
    # Cycle protection
    auto_advance_count: int
    max_auto_advance_steps: int

    # Per-stage cursor for multi-question "questions" stages
    question_cursor: dict[str, int]


class InterviewConfig(TypedDict, total=False):
    """Configuration for interview graph invocation."""
    configurable: dict[str, Any]


def create_initial_state(
    flow_id: str = "intake_sipoc_v1",
    max_auto_advance_steps: int = 50
) -> InterviewState:
    """
    Create initial state for a new interview session.
    
    Args:
        flow_id: Which flow to start with
        max_auto_advance_steps: Cycle protection limit
        
    Returns:
        Initial InterviewState
    """
    return {
        "messages": [],
        "events": [],
        "flow_id": flow_id,
        "active_stage_id": "welcome",
        "slots": {},
        "pending": None,
        "workflow_capture_state": {
            "active_workflow_id": None,
            "active_step_index": 0,
            "active_step_buffer": {}
        },
        "error": None,
        "retry_count": 0,
        "auto_advance_count": 0,
        "max_auto_advance_steps": max_auto_advance_steps,
        "question_cursor": {}
    }
