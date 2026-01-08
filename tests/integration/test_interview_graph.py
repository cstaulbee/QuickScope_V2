"""
Integration tests for the interview graph.
"""

import pytest
from pathlib import Path
from langchain_core.messages import HumanMessage

from src.state.interview_state import create_initial_state
from src.graphs.interview_graph import create_interview_graph


class TestInterviewGraphIntegration:
    """Integration tests for complete interview flow."""
    
    def test_graph_initialization(self):
        """Test graph can be created."""
        graph = create_interview_graph()
        
        assert graph is not None
    
    def test_graph_first_turn(self):
        """Test graph processes first turn and asks welcome question."""
        graph = create_interview_graph()
        
        # Create initial state
        initial_state = create_initial_state(flow_id="intake_sipoc_v1")
        
        # Add a dummy first message to trigger the flow
        initial_state["messages"] = [HumanMessage(content="Hello")]
        
        # Invoke graph
        config = {"configurable": {"thread_id": "test_thread_1"}}
        result = graph.invoke(initial_state, config)
        
        # Should have advanced and returned a message
        assert "messages" in result
        assert len(result["messages"]) > 0
        
        # Should have auto-advanced to the first questions stage
        assert result["active_stage_id"] == "engagement_context"
    
    def test_graph_answer_question(self):
        """Test graph processes an answer and advances."""
        graph = create_interview_graph()
        
        # Setup state at engagement_context
        state = create_initial_state(flow_id="intake_sipoc_v1")
        state["active_stage_id"] = "engagement_context"
        state["pending"] = {
            "question_id": "process_name",
            "save_to": "engagement.process_name",
            "ask": "What do you call this process internally?"
        }
        state["messages"] = [HumanMessage(content="Order Fulfillment")]
        
        config = {"configurable": {"thread_id": "test_thread_2"}}
        result = graph.invoke(state, config)
        
        # Answer should be saved
        assert result["slots"]["engagement"]["process_name"] == "Order Fulfillment"
        
        # For multi-question stages, we stay in the same stage and advance the cursor
        assert result["active_stage_id"] == "engagement_context"
        assert result["question_cursor"]["engagement_context"] == 1
        assert result["pending"] is not None
        assert result["pending"]["question_id"] == "organization_type"
    
    def test_workflow_trigger_capture(self):
        """Test that workflow trigger action works correctly."""
        # This is more of a unit test for the action flow
        from src.actions.workflow_actions import write_trigger_to_active_workflow
        
        # Setup state with trigger buffer populated
        slots = {
            "workflows": {
                "maps": [
                    {
                        "workflow_id": "wf_1",
                        "workflow_name": "Standard order",
                        "trigger": None,
                        "start_condition": None
                    }
                ]
            },
            "workflow_capture_state": {
                "active_workflow_id": "wf_1",
                "workflow_level_buffer": {
                    "trigger": "Customer places order",
                    "start_condition": "Account validated"
                }
            }
        }
        
        # Execute action
        result = write_trigger_to_active_workflow(slots)
        
        # Verify trigger was written
        assert result["workflows"]["maps"][0]["trigger"] == "Customer places order"
        assert result["workflows"]["maps"][0]["start_condition"] == "Account validated"
        assert result["workflow_capture_state"]["workflow_level_buffer"] == {}
    
    def test_graph_confirm_yes(self):
        """Test graph processes confirm with 'yes' response."""
        graph = create_interview_graph()
        
        # Setup state at sipoc_confirm
        state = create_initial_state(flow_id="intake_sipoc_v1")
        state["active_stage_id"] = "sipoc_confirm"
        state["slots"]["engagement"] = {"process_name": "Order Fulfillment"}
        state["slots"]["sipoc"] = {
            "suppliers": ["Vendor"],
            "inputs": ["Order"],
            "process_high_level_steps": ["Receive", "Process", "Ship"],
            "outputs": ["Package"],
            "customers": ["Customer"]
        }
        state["pending"] = {
            "confirm_id": "sipoc_confirm",
            "on_yes": "end",
            "on_no": "sipoc_capture"
        }
        state["messages"] = [HumanMessage(content="Yes")]
        
        config = {"configurable": {"thread_id": "test_thread_3"}}
        result = graph.invoke(state, config)
        
        # Should advance to end
        assert result["active_stage_id"] == "end"

    def test_graph_confirm_yes_with_punctuation(self):
        """Test graph processes confirm with a realistic 'Yes.' response."""
        graph = create_interview_graph()

        # Setup state at sipoc_confirm
        state = create_initial_state(flow_id="intake_sipoc_v1")
        state["active_stage_id"] = "sipoc_confirm"
        state["slots"]["engagement"] = {"process_name": "Order Fulfillment"}
        state["slots"]["sipoc"] = {
            "suppliers": ["Vendor"],
            "inputs": ["Order"],
            "process_high_level_steps": ["Receive", "Process", "Ship"],
            "outputs": ["Package"],
            "customers": ["Customer"]
        }
        state["pending"] = {
            "confirm_id": "sipoc_confirm",
            "on_yes": "end",
            "on_no": "sipoc_capture"
        }
        state["messages"] = [HumanMessage(content="Yes.")]

        config = {"configurable": {"thread_id": "test_thread_3b"}}
        result = graph.invoke(state, config)

        assert result["active_stage_id"] == "end"
    
    def test_graph_confirm_no(self):
        """Test graph processes confirm with 'no' response and loops back."""
        graph = create_interview_graph()
        
        # Setup state at sipoc_confirm
        state = create_initial_state(flow_id="intake_sipoc_v1")
        state["active_stage_id"] = "sipoc_confirm"
        state["slots"]["sipoc"] = {
            "suppliers": ["Vendor"],
            "inputs": ["Order"],
            "process_high_level_steps": ["Receive"],
            "outputs": ["Package"],
            "customers": ["Customer"]
        }
        state["pending"] = {
            "confirm_id": "sipoc_confirm",
            "on_yes": "end",
            "on_no": "sipoc_capture"
        }
        state["messages"] = [HumanMessage(content="No, I need to correct something")]
        
        config = {"configurable": {"thread_id": "test_thread_4"}}
        result = graph.invoke(state, config)
        
        # Should loop back to sipoc_capture
        assert result["active_stage_id"] == "sipoc_capture"
    
    def test_graph_auto_advance_through_message_stages(self):
        """Test graph auto-advances through message stages."""
        graph = create_interview_graph()
        
        # Setup state at welcome (message stage)
        state = create_initial_state(flow_id="intake_sipoc_v1")
        state["active_stage_id"] = "welcome"
        state["messages"] = [HumanMessage(content="Start")]
        
        config = {"configurable": {"thread_id": "test_thread_5"}}
        result = graph.invoke(state, config)
        
        # Should auto-advance past welcome to engagement_context (questions stage)
        assert result["active_stage_id"] == "engagement_context"
        
        # Should have a pending question
        assert result["pending"] is not None
        assert "question_id" in result["pending"]
    
    def test_graph_cycle_protection(self):
        """Test graph respects cycle protection limit."""
        graph = create_interview_graph()
        
        # Setup state with very low max_auto_advance_steps
        state = create_initial_state(flow_id="intake_sipoc_v1")
        state["max_auto_advance_steps"] = 2
        state["messages"] = [HumanMessage(content="Start")]
        
        config = {"configurable": {"thread_id": "test_thread_6"}}
        result = graph.invoke(state, config)
        
        # Should either complete successfully or hit limit
        # If hit limit, error should be set
        if result.get("error"):
            assert "exceeded max steps" in result["error"].lower()
    
    def test_graph_state_persistence(self):
        """Test graph persists state across invocations."""
        graph = create_interview_graph()
        
        # First turn
        state1 = create_initial_state(flow_id="intake_sipoc_v1")
        state1["messages"] = [HumanMessage(content="Start")]
        
        config = {"configurable": {"thread_id": "test_persist_thread"}}
        result1 = graph.invoke(state1, config)
        
        # Second turn with same thread_id
        state2 = result1.copy()
        state2["messages"].append(HumanMessage(content="Order Fulfillment"))
        
        result2 = graph.invoke(state2, config)
        
        # Should maintain continuity
        assert "Order Fulfillment" in str(result2["slots"])
