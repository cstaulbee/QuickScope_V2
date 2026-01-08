# Bug Fix: Bot Getting Stuck in "Thanks — moving on." Loop

## Problem Summary

The interview bot was getting stuck in an infinite loop, repeatedly responding with "Thanks — moving on." after the user completed answering questions about data elements. The bot would not progress to the next stage of the interview.

## Root Cause Analysis

The issue was caused by **incomplete implementation of the `loop` stage type** in the flow execution logic. Specifically:

### 1. Loop Stage Not Properly Handled
In `src/nodes/interview_nodes.py`, the `auto_advance_node` function had a simplified implementation for `loop` type stages (lines 416-428):

```python
elif stage_type == "loop":
    # For now, just advance to next (loop logic needs more state)
    next_stage = stage.get("next", "end")
    # ... just advances without checking exit conditions
```

This meant that when the bot reached the `data_elements_validate_loop` stage (line 680 in `Flow_B_current_state_mapping_v1.json`), it would:
1. Advance to `data_element_one_by_one` (action)
2. Execute `select_next_data_element_for_validation` action
3. Advance to `data_element_questions` (questions stage)
4. Ask all 8 questions about a data element
5. After the last question, hit the "safety net" in `render_prompt_node` (lines 508-522)
6. Send "Thanks — moving on." and advance to `data_element_commit`
7. Loop back to `data_elements_validate_loop`
8. **Repeat steps 1-7 infinitely** because the loop exit condition was never checked

### 2. Action Not Returning Loop Exit Signal
The `select_next_data_element_for_validation` action in `src/actions/workflow_actions.py` (lines 319-334) would set `current_data_element_index` to `None` when all elements were validated, but:
- It only returned the updated slots, not an action result code
- There was no logic to check this condition and exit the loop

### 3. Questions Stage Safety Net
After the last question in a multi-question stage, the `render_prompt_node` has a "safety net" (lines 508-522) that sends "Thanks — moving on." This is meant to gracefully handle edge cases, but it became the symptom of the deeper loop issue.

## The Fix

### Change 1: Enhanced Loop Stage Handling

Updated `auto_advance_node` in `src/nodes/interview_nodes.py` (lines 416-457) to:

1. **Check loop stop conditions** before continuing
2. **Examine the signal slot** specified in the flow definition
3. **Exit the loop** via `on_stop` when conditions are met
4. **Continue the loop** via `next` when more iterations needed

```python
elif stage_type == "loop":
    # Check loop stop condition
    stop_condition = stage.get("stop_condition", {})
    signal_slot = stop_condition.get("signal_slot")
    
    should_exit_loop = False
    
    # Check if loop should exit based on signal slot
    if signal_slot:
        # For data_elements loop, check if current_data_element_index is None
        if "data_elements" in signal_slot:
            current_idx = slots.get("process_parameters", {}).get("current_data_element_index")
            if current_idx is None:
                should_exit_loop = True
    
    if should_exit_loop:
        # Exit loop via on_stop
        next_stage = stage.get("on_stop", "end")
        active_stage_id = next_stage
    else:
        # Continue loop - advance to next stage within loop
        next_stage = stage.get("next", "end")
        active_stage_id = next_stage
```

### Change 2: Action Returns Exit Signal

Updated `select_next_data_element_for_validation` in `src/actions/workflow_actions.py` (lines 319-340) to:

1. **Return a tuple** `(updated_slots, action_result_code)`
2. **Return "element_selected"** when there's an unvalidated element
3. **Return "all_validated"** when all elements are complete

```python
def select_next_data_element_for_validation(slots: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """
    Select next unvalidated data element and set current pointer.
    
    Returns (updated_slots, action_result_code)
    - "element_selected" if there's an unvalidated element
    - "all_validated" if all elements are validated
    """
    result = slots.copy()
    elements = result.get("process_parameters", {}).get("data_elements", [])
    
    for i, elem in enumerate(elements):
        if not elem.get("validated", False) or elem.get("definition") is None:
            result.setdefault("process_parameters", {})["current_data_element_index"] = i
            return result, "element_selected"
    
    # All validated
    result.setdefault("process_parameters", {})["current_data_element_index"] = None
    return result, "all_validated"
```

## Flow Definition Reference

The relevant loop definition in `flows/Flow_B_current_state_mapping_v1.json` (lines 680-690):

```json
{
  "id": "data_elements_validate_loop",
  "type": "loop",
  "loop_purpose": "Validate each data element so it's unambiguous and build-informative, without technical jargon.",
  "prompt": "We'll confirm the key pieces of information one by one so the model is unambiguous.",
  "stop_condition": {
    "description": "All candidate data elements are validated or intentionally discarded.",
    "signal_slot": "process_parameters.data_elements"
  },
  "on_stop": "status_model_capture",
  "next": "data_element_one_by_one"
}
```

## Testing

To verify the fix:

1. Run the interview simulation with the `1031_exchange_ops` persona
2. Progress through the data elements validation section
3. Confirm the bot:
   - Asks all 8 questions for each data element
   - Moves to the next data element after committing
   - **Exits the loop** and proceeds to `status_model_capture` when all elements are validated

## Impact

This fix resolves:
- ✅ Infinite "Thanks — moving on." loop
- ✅ Proper loop exit conditions for data element validation
- ✅ Correct progression through the entire Flow B interview

## Related Code

- `src/nodes/interview_nodes.py`: `auto_advance_node` function (lines 277-468)
- `src/actions/workflow_actions.py`: `select_next_data_element_for_validation` function (lines 319-340)
- `flows/Flow_B_current_state_mapping_v1.json`: Loop stage definition (lines 680-690)

## Notes

The fix is **generalized** to handle any loop stage that uses a `signal_slot` condition. The specific check for `data_elements` can be extended to support other loop types in the future by:

1. Adding more signal slot patterns
2. Supporting different exit condition checks
3. Implementing custom loop validators

## Future Enhancements

Consider adding:
1. **Loop iteration counter** to prevent infinite loops (fail-safe)
2. **More sophisticated exit conditions** (e.g., min/max items, time limits)
3. **Branch support within loops** for complex iteration patterns
4. **Loop state tracking** for better observability and debugging
