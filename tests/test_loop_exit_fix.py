"""
Test to verify the loop exit condition fix for data_elements_validate_loop.

This test simulates the scenario where:
1. Bot processes data element questions
2. All data elements are validated
3. Bot should exit the loop and proceed to next stage
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.state.interview_state import create_initial_state, InterviewState
from src.nodes.interview_nodes import auto_advance_node
from src.actions.workflow_actions import select_next_data_element_for_validation


def test_loop_exit_with_no_elements():
    """Test that loop exits when there are no data elements to validate."""
    print("\n=== Test 1: Loop exits when all elements validated (no elements) ===")
    
    # Create state at data_elements_validate_loop stage with no unvalidated elements
    state: InterviewState = {
        "messages": [],
        "events": [],
        "flow_id": "current_state_mapping_v1",
        "active_stage_id": "data_elements_validate_loop",
        "slots": {
            "process_parameters": {
                "data_elements": [],
                "current_data_element_index": None
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
    
    # Execute auto_advance
    result = auto_advance_node(state)
    
    print(f"Active stage after advance: {result.get('active_stage_id')}")
    print(f"Events: {[e.get('kind') for e in result.get('events', [])]}")
    
    # Verify that we exited the loop
    assert result.get('active_stage_id') == 'status_model_capture', \
        f"Expected 'status_model_capture', got '{result.get('active_stage_id')}'"
    
    print("✅ Test passed: Loop correctly exited to status_model_capture\n")


def test_loop_continues_with_unvalidated_element():
    """Test that loop continues when there are unvalidated elements."""
    print("\n=== Test 2: Loop continues when elements need validation ===")
    
    # Create state with one unvalidated element
    state: InterviewState = {
        "messages": [],
        "events": [],
        "flow_id": "current_state_mapping_v1",
        "active_stage_id": "data_elements_validate_loop",
        "slots": {
            "process_parameters": {
                "data_elements": [
                    {
                        "data_id": "de_1",
                        "name": "Client Name",
                        "definition": None,  # Not validated yet
                        "validated": False
                    }
                ],
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
    
    # Execute auto_advance
    result = auto_advance_node(state)
    
    print(f"Active stage after advance: {result.get('active_stage_id')}")
    print(f"Events: {[e.get('kind') for e in result.get('events', [])]}")
    
    # Verify that we continued the loop and advanced through automatic stages to questions
    # Flow: data_elements_validate_loop -> data_element_one_by_one (action) -> data_element_questions (questions)
    assert result.get('active_stage_id') == 'data_element_questions', \
        f"Expected 'data_element_questions', got '{result.get('active_stage_id')}'"
    
    print("✅ Test passed: Loop correctly continued through action to questions stage\n")


def test_select_action_returns_correct_signals():
    """Test that select_next_data_element_for_validation returns correct signals."""
    print("\n=== Test 3: Action returns correct signals ===")
    
    # Test with unvalidated element
    slots_with_unvalidated = {
        "process_parameters": {
            "data_elements": [
                {"name": "Client Name", "definition": None, "validated": False}
            ]
        }
    }
    
    result_slots, signal = select_next_data_element_for_validation(slots_with_unvalidated)
    print(f"With unvalidated element - Signal: {signal}")
    assert signal == "element_selected", f"Expected 'element_selected', got '{signal}'"
    print("✅ Correct signal for unvalidated element")
    
    # Test with all validated
    slots_all_validated = {
        "process_parameters": {
            "data_elements": [
                {"name": "Client Name", "definition": "The name of the client", "validated": True}
            ]
        }
    }
    
    result_slots, signal = select_next_data_element_for_validation(slots_all_validated)
    print(f"With all validated - Signal: {signal}")
    assert signal == "all_validated", f"Expected 'all_validated', got '{signal}'"
    print("✅ Correct signal for all validated")
    
    # Test with empty list
    slots_empty = {
        "process_parameters": {
            "data_elements": []
        }
    }
    
    result_slots, signal = select_next_data_element_for_validation(slots_empty)
    print(f"With empty list - Signal: {signal}")
    assert signal == "all_validated", f"Expected 'all_validated', got '{signal}'"
    print("✅ Correct signal for empty list\n")


def test_full_loop_cycle():
    """Test a complete loop cycle: select -> validate -> commit -> check exit."""
    print("\n=== Test 4: Full loop cycle ===")
    
    # Start with 2 elements, validate them, then exit
    state: InterviewState = {
        "messages": [],
        "events": [],
        "flow_id": "current_state_mapping_v1",
        "active_stage_id": "data_elements_validate_loop",
        "slots": {
            "process_parameters": {
                "data_elements": [
                    {"name": "Client Name", "definition": "Name of client", "validated": True},
                    {"name": "Property Address", "definition": None, "validated": False}
                ],
                "current_data_element_index": 1
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
    
    # First cycle - should continue (element 2 needs validation)
    result = auto_advance_node(state)
    print(f"Cycle 1 - Active stage: {result.get('active_stage_id')}")
    # Auto-advance should process loop -> action -> questions
    assert result.get('active_stage_id') == 'data_element_questions'
    
    # Simulate validating the second element
    state["slots"]["process_parameters"]["data_elements"][1]["validated"] = True
    state["slots"]["process_parameters"]["data_elements"][1]["definition"] = "Address of property"
    state["slots"]["process_parameters"]["current_data_element_index"] = None
    state["active_stage_id"] = "data_elements_validate_loop"
    
    # Second cycle - should exit (all validated)
    result = auto_advance_node(state)
    print(f"Cycle 2 - Active stage: {result.get('active_stage_id')}")
    assert result.get('active_stage_id') == 'status_model_capture'
    
    print("✅ Full loop cycle completed correctly\n")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("Testing Loop Exit Condition Fix")
    print("="*60)
    
    try:
        test_select_action_returns_correct_signals()
        test_loop_exit_with_no_elements()
        test_loop_continues_with_unvalidated_element()
        test_full_loop_cycle()
        
        print("\n" + "="*60)
        print("✅ ALL TESTS PASSED")
        print("="*60 + "\n")
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
