# Loop Stuck Bug - Quick Summary

## Problem
Bot repeatedly responds "Thanks — moving on." and doesn't progress.

## Root Cause
The `loop` stage type (`data_elements_validate_loop`) was not properly implemented - it never checked exit conditions.

## The Fix

### 1. Enhanced `auto_advance_node()` in `src/nodes/interview_nodes.py`
Added logic to check loop stop conditions and exit via `on_stop` when done:

```python
elif stage_type == "loop":
    # Check loop stop condition
    stop_condition = stage.get("stop_condition", {})
    signal_slot = stop_condition.get("signal_slot")
    
    should_exit_loop = False
    
    # Check if loop should exit based on signal slot
    if signal_slot and "data_elements" in signal_slot:
        current_idx = slots.get("process_parameters", {}).get("current_data_element_index")
        if current_idx is None:
            should_exit_loop = True
    
    if should_exit_loop:
        next_stage = stage.get("on_stop", "end")  # Exit
    else:
        next_stage = stage.get("next", "end")      # Continue
```

### 2. Updated `select_next_data_element_for_validation()` in `src/actions/workflow_actions.py`
Changed return type from `dict` to `tuple[dict, str]` to signal loop status:

```python
def select_next_data_element_for_validation(slots: dict[str, Any]) -> tuple[dict[str, Any], str]:
    # ... validation logic ...
    
    if unvalidated_element_found:
        return result, "element_selected"
    else:
        return result, "all_validated"
```

## Test Results
✅ All 80 tests pass (76 existing + 4 new)

## Files Changed
- `src/nodes/interview_nodes.py` (lines 416-457)
- `src/actions/workflow_actions.py` (lines 319-340)

## Detailed Documentation
See `BUG_FIX_LOOP_STUCK.md` for complete analysis and implementation details.
