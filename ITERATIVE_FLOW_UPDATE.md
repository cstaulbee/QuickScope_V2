# Iterative Step Discovery - Flow Update

## Problem Identified

The previous flow asked users to **list all process steps upfront**:

```
Bot: "List all the steps in this process from start to finish. Just give me a 
     numbered list with short step names (e.g., 1. Receive request, 
     2. Verify info, 3. Process order)."

User: 1. Intake request
      2. Draft exchange agreement
      3. Execute exchange agreement
      ... (and so on)
```

**This defeats the entire purpose of process discovery!** The tool should help users **figure out** their process, not require them to already know it.

---

## Solution: True Iterative Discovery

### New Flow Pattern

Instead of pre-listing steps, the bot now guides users through the process **one step at a time**:

```
1. Bot: "What's the first action that happens after the trigger?"
   User: "Coordinator receives intake form"
   
2. Bot captures details (owner, inputs, outputs, etc.)

3. Bot: "What happens next?" (or type 'done')
   User: "Review documents for completeness"
   
4. Bot captures details for that step

5. Repeat until user says 'done'
```

### Benefits

✅ **No need to know all steps upfront** - discover as you go  
✅ **More natural conversation** - follows how people actually think  
✅ **Less intimidating** - one step at a time vs. entire process  
✅ **Better for complex processes** - can branch and explore  
✅ **Handles uncertainty** - users can say "done" when they're ready

---

## Technical Changes

### 1. Flow Structure (`Flow_B_current_state_mapping_v1.json`)

**REMOVED:**
- `workflow_step_enumeration` - Asked for numbered list
- `workflow_step_enumeration_parse` - Parsed list into queue
- `workflow_step_enumeration_confirm` - Confirmed the list
- `workflow_advance_to_next_step` - Moved through pre-populated queue
- Template variable references to `{{workflow_capture_state.current_step_name}}`

**ADDED:**
- `workflow_first_step_intro` - Sets context for first step
- `workflow_ask_next_step` - Asks "What happens next?"
- `workflow_check_if_done` - Detects when user says "done"
- `workflow_copy_description_to_buffer` - Moves next step description to buffer

**MODIFIED:**
- All step capture questions now ask directly (no "For step 'X':..." prefix)
- First step asks: "What's the first action that happens after the trigger?"
- Subsequent steps ask: "What happens next?"
- Step confirmation shows description instead of step name/number

### 2. Action Functions (`workflow_actions.py`)

**NEW FUNCTIONS:**

```python
def check_if_user_said_done(slots: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """
    Check if user indicated they're done adding steps.
    Returns: "done" or "continue"
    """
    
def copy_next_step_to_buffer(slots: dict[str, Any]) -> dict[str, Any]:
    """
    Copy user's next step description into active_step_buffer.
    Allows normal step capture flow to continue.
    """
```

**DEPRECATED:**
- `advance_to_next_step_or_finish()` - No longer used (kept for backward compatibility)
- `parse_enumerated_steps_into_skeleton()` - No longer used

### 3. Documentation Updates

**Updated:** `CHEATSHEET_FLOW_B.md`
- Clarified new flow structure
- Added note: "You DON'T need to list all steps upfront"

---

## Flow Diagram: Before vs. After

### BEFORE (Pre-enumeration)
```
Trigger captured
    ↓
"List ALL steps from start to finish" ❌
    ↓
Parse into step queue
    ↓
Confirm list
    ↓
Loop through queue asking details
```

### AFTER (True Iterative)
```
Trigger captured
    ↓
"What's the first action?" ✅
    ↓
Capture step details
    ↓
"What happens next?" (or 'done') ✅
    ↓
If continue: capture next step
If done: capture end condition
```

---

## Example Conversation: New Flow

```
Bot: What event triggers this process to start?
User: Client submits a 1031 exchange request form

Bot: Great! Now let's walk through this process step-by-step.

Bot: What's the first action that happens after the trigger?
User: Coordinator reviews the intake form for completeness

Bot: Who performs this specific step?
User: Exchange Coordinator

Bot: What do they need to perform this step?
User: Intake form, client contact info, property details

Bot: What gets produced or changed by this step?
User: Initial case record created in tracker

Bot: What tools/systems are used during this step?
User: Excel tracker

Bot: Is there a decision here that changes what happens next?
User: Yes - is the form complete?

Bot: What are the 2-3 common outcomes of that decision?
User: Complete → proceed to draft agreement
       Incomplete → contact client for missing info

Bot: Does it wait after this step?
User: Sometimes waits 1-2 days for client response

Bot: What's the most common thing that goes wrong at this step?
User: Missing property identification details

Bot: Step captured! Live diagram updated.

Bot: What happens next in the process? (Or type 'done')
User: Draft the exchange agreement

Bot: Who performs this specific step?
User: Senior Coordinator

[... continues until user says 'done' ...]
```

---

## Migration Notes

### Existing Sessions
- Old sessions with pre-enumerated steps will continue to work
- `advance_to_next_step_or_finish()` still exists for backward compatibility

### Testing
- Simulation mode (`--simulate`) should work with new flow
- Persona responses will need to describe steps one at a time
- No changes needed to diagram generation or output flows

---

## Files Modified

1. `flows/Flow_B_current_state_mapping_v1.json` - Main flow definition
2. `src/actions/workflow_actions.py` - Added new action functions
3. `CHEATSHEET_FLOW_B.md` - Updated documentation

---

## Summary

This update transforms QuickScope from a "tell me everything you know" tool into a **guided discovery partner** that helps users map their processes through natural conversation. Users no longer need to know all the steps upfront - they can explore and document as they go.
