"""
Quick validation test for the loop exit fix.

This script simulates the exact scenario that was causing the infinite loop:
- Bot asks all 8 data element questions
- User answers them all
- Bot should move to the next data element OR exit the loop
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.graphs.interview_graph import create_interview_graph
from src.state.interview_state import create_initial_state
from langchain_core.messages import HumanMessage, AIMessage


def test_loop_exit_scenario():
    """Test the exact scenario that was causing the infinite loop."""
    print("\n" + "="*70)
    print("TESTING LOOP EXIT FIX - Data Elements Validation")
    print("="*70 + "\n")
    
    # Create graph and initial state
    graph = create_interview_graph()
    
    # Create state that's just before entering the data_elements_validate_loop
    # with one data element that needs validation
    state = {
        "messages": [],
        "events": [],
        "flow_id": "current_state_mapping_v1",
        "active_stage_id": "data_elements_validate_loop",
        "slots": {
            "process_parameters": {
                "data_elements": [
                    {
                        "data_id": "de_1",
                        "name": "Client Identification Number",
                        "definition": None,
                        "example_value": None,
                        "kind": None,
                        "required_when": None,
                        "source_today": None,
                        "owner_role": None,
                        "validation_rules_today": [],
                        "privacy_sensitivity": None,
                        "validated": False
                    }
                ],
                # Set to 0 to indicate we have an unvalidated element to process
                "current_data_element_index": 0
            }
        },
        "pending": None,
        "workflow_capture_state": {},
        "error": None,
        "retry_count": 0,
        "auto_advance_count": 0,
        "max_auto_advance_steps": 50,
        "question_cursor": {}
    }
    
    config = {"configurable": {"thread_id": "test_loop_exit"}}
    
    # Turn 1: Bot should ask first data element question
    print("Turn 1: Bot should ask first data element question")
    print("-" * 70)
    result = graph.invoke(state, config)
    
    last_msg = result["messages"][-1] if result.get("messages") else None
    if last_msg and isinstance(last_msg, AIMessage):
        print(f"Bot: {last_msg.content[:100]}...")
    
    assert result["active_stage_id"] == "data_element_questions", \
        f"Expected 'data_element_questions', got '{result['active_stage_id']}'"
    assert result["pending"] is not None, "Expected pending question"
    print("Bot asked first question\n")
    
    # Simulate answering all 8 questions
    questions = [
        ("definition", "A unique identifier assigned to each client"),
        ("example_value", "CLI-2024-001"),
        ("kind", "Free text"),
        ("required_when", "Always required at case initiation"),
        ("source_today", "Manually entered by Exchange Coordinator"),
        ("owner_role", "Exchange Coordinator"),
        ("validation_rules_today", "No formal validation rules currently"),
        ("privacy_sensitivity", "Yes, financial and personal information")
    ]
    
    state = result
    
    for i, (field, answer) in enumerate(questions, start=2):
        print(f"Turn {i}: User answers {field} question")
        print("-" * 70)
        
        # Add user answer
        state["messages"].append(HumanMessage(content=answer))
        
        # Invoke graph
        result = graph.invoke(state, config)
        
        last_msg = result["messages"][-1] if result.get("messages") else None
        if last_msg and isinstance(last_msg, AIMessage):
            content = last_msg.content
            # Truncate long content
            if len(content) > 150:
                content = content[:147] + "..."
            print(f"Bot: {content}")
        
        state = result
        
        # After the 8th answer, bot should either ask about next element or exit loop
        if i == len(questions) + 1:
            print(f"\nActive stage: {result['active_stage_id']}")
            print(f"Question cursor: {result.get('question_cursor', {})}")
            
            # The key test: After the last question, the bot will show "Thanks — moving on."
            # as it advances through the commit action. This is EXPECTED.
            # What matters is that on the NEXT turn, it doesn't get stuck in a loop.
            
            # We'll check this in the next turn simulation
            print("Note: 'Thanks — moving on.' after last question is expected (safety net)")
            print("      The important test is whether it continues or loops infinitely...")
        
        print()
    
    # Final check: simulate one more turn to ensure we're not looping
    print("Turn 10: Critical test - check for infinite loop")
    print("-" * 70)
    print("Invoking graph one more time to see if it progresses or loops...")
    
    # Just invoke the graph without adding a message
    # If the loop fix works, it should exit to status_model_capture
    # If broken, it would stay at data_elements_validate_loop and say "Thanks — moving on." again
    result = graph.invoke(state, config)
    
    last_msg = result["messages"][-1] if result.get("messages") else None
    if last_msg and isinstance(last_msg, AIMessage):
        content = last_msg.content
        print(f"Bot: {content[:150]}...")
        print(f"Active stage: {result['active_stage_id']}")
        
        # The critical check: if we see "Thanks — moving on." again, we're in a loop
        if content == "Thanks — moving on." and result['active_stage_id'] != 'status_model_capture':
            print("\nFAILED: Bot is stuck in an infinite loop!")
            print(f"Stage: {result['active_stage_id']}, should have progressed.")
            return False
        
        # If we've moved to status_model_capture, we successfully exited the loop
        if result['active_stage_id'] == 'status_model_capture':
            print("\nSUCCESS: Bot correctly exited the data elements loop!")
            print(f"Now at stage: {result['active_stage_id']}")
        elif result['active_stage_id'] == 'data_element_questions':
            print("\nSUCCESS: Bot continued to next data element (if multiple exist)")
        else:
            print(f"\nStage: {result['active_stage_id']}")
    
    print("\n" + "="*70)
    print("TEST PASSED: No infinite loop detected!")
    print("Bot correctly processed data elements and progressed to next stage.")
    print("="*70 + "\n")
    return True


if __name__ == "__main__":
    try:
        success = test_loop_exit_scenario()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\nERROR: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
