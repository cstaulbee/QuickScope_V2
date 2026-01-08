# Why Some Steps Weren't Being Summarized

## The Problem You Observed

When you ran the workflow capture again, **some steps got properly summarized** while **others remained truncated**. This inconsistent behavior was confusing because the fix appeared to work sometimes but not always.

## Root Cause Analysis

The issue was a **data priority problem** in the diagram generation logic. Let me explain:

### Step Data Structure

Each workflow step has TWO text fields:

```python
{
    "step_name": "Intake client's",              # ← From initial enumeration (SHORT)
    "description": "The first step involves...", # ← From detailed interview (FULL)
    "owner_role": "Coordinator",
    # ... other fields
}
```

- **`step_name`**: Created during initial step enumeration, might already be **truncated** by the user
- **`description`**: Created during detailed interview, the **full verbose description**

### The Bug in Original Code

In `src/actions/diagram_generation.py` (lines 611-614), the code was:

```python
# Use step_name if available, otherwise fall back to description
step_name = step.get("step_name")
if not step_name:
    description = step.get("description", f"Step {step_num}")
    step_name = description

# Then condense step_name
node_label = condense_label(step_name, ...)
```

**The Problem:**
1. If `step_name` exists (even if it's already truncated like "Intake client's"), it uses that
2. The already-truncated `step_name` gets passed to `condense_label()`
3. Since it's already short, it might just get returned as-is
4. Result: Truncated label appears in the diagram!

### Why It Was Inconsistent

- **Steps that got summarized**: Had verbose `step_name` values that needed condensing
- **Steps that stayed truncated**: Had `step_name` values that were already truncated (< 35 chars)

The LLM-based condenser would sometimes try to improve these, but often the cache would return the old truncated version, or the deterministic fallback would keep short text as-is.

## The Fix

### Change 1: Prioritize `description` Over `step_name`

**New logic in `build_bpmn_lite_mermaid()`** (lines 605-633):

```python
# Prefer description (full detail) over step_name (which might already be truncated)
description = step.get("description")
step_name = step.get("step_name")

# Use description if available (it's the full detailed version)
if description:
    source_text = description
elif step_name:
    source_text = step_name
else:
    source_text = f"Step {step_num}"

# ALWAYS condense the source text
node_label = condense_label(source_text, max_length=35, context="step", use_llm=use_llm_condense)
```

**Why this works:**
- ✅ Always starts with the **full, detailed description** when available
- ✅ Falls back to `step_name` only if no description exists
- ✅ **Always runs condensing**, even on short text (ensures consistency)
- ✅ LLM can intelligently summarize from the full context

### Change 2: Same Fix in Fallback Diagram

Applied the same logic to `build_fallback_linear_diagram()` (lines 520-528):

```python
# Prefer description over step_name (same logic as main function)
description = step.get("description")
step_name = step.get("step_name")
source_text = description if description else (step_name if step_name else f"Step {i+1}")

label = condense_label(source_text, max_length=35, context="step", use_llm=False)
```

### Change 3: Clear Cache on Each Generation

**In `workflow_actions.py`** (line 353):

```python
def update_live_bpmn_artifact(slots: dict[str, Any]) -> dict[str, Any]:
    from src.actions.diagram_generation import (..., clear_condense_cache)
    
    # ... find workflow ...
    
    # Clear cache to ensure fresh condensing (important after code updates)
    clear_condense_cache()
    
    # Generate diagram
    mermaid_content = build_bpmn_lite_mermaid(active_workflow)
```

**Why this is important:**
- ✅ Prevents old truncated labels from being served from cache
- ✅ Ensures each diagram generation uses the latest logic
- ✅ Critical after code updates or when debugging

## Example: Before and After

### Before the Fix

Given step data:
```python
{
    "step_name": "Review identification submitted by",  # ← Truncated!
    "description": "Review the identification letter submitted by the client to ensure it meets all IRS requirements and lists valid replacement properties within the 45-day window"
}
```

**Old behavior:**
1. Code checks: "Does `step_name` exist?" → Yes
2. Uses `step_name` = "Review identification submitted by"
3. Condenses it → Still truncated because cache or it's "close enough" to limit
4. **Result:** "Review identification submitted by" ❌

### After the Fix

Same step data as above.

**New behavior:**
1. Code checks: "Does `description` exist?" → Yes!
2. Uses `description` = "Review the identification letter submitted by..."
3. **LLM condenses** the full description → "Review identification letter"
4. **Result:** "Review identification letter" ✓

## Why You Need to Restart/Reload

### Python Module Caching

Python caches imported modules. If you're running the workflow capture in a long-running process (like a Jupyter notebook, Flask server, or interactive script), the **old code is still in memory**.

**What you need to do:**

1. **Restart the Python process** (close terminal/notebook and reopen)
2. **OR** Force reload the module:
   ```python
   import importlib
   import src.actions.diagram_generation
   import src.actions.workflow_actions
   
   importlib.reload(src.actions.diagram_generation)
   importlib.reload(src.actions.workflow_actions)
   ```

3. **For simulations:** Restart `quickstart_flow_b.py` or whatever script you're running

### Label Cache

Even with the new code loaded, old labels might be cached. The `clear_condense_cache()` call in `update_live_bpmn_artifact()` handles this automatically now.

## Testing the Fix

### Manual Test

Run this in a fresh Python session:

```python
from src.actions.diagram_generation import condense_label, clear_condense_cache

# Clear any cached labels
clear_condense_cache()

# Test with a verbose description (like what's stored in step.description)
verbose = "Review the identification letter submitted by the client to ensure it meets all IRS requirements"

result = condense_label(verbose, max_length=35, context="step", use_llm=True)
print(f"Result: '{result}' ({len(result)} chars)")
# Should print something like: "Review identification letter (28 chars)"
```

### Check Your Workflow Data

You can inspect what's actually in your workflow data:

```python
# After running workflow capture
import json

with open("state.json", "r") as f:
    slots = json.load(f)

for wf in slots.get("workflows", {}).get("maps", []):
    print(f"\nWorkflow: {wf.get('workflow_name')}")
    for i, step in enumerate(wf.get("steps", []), 1):
        print(f"  Step {i}:")
        print(f"    step_name: {step.get('step_name')}")
        print(f"    description: {step.get('description', 'None')[:80]}...")
```

This will show you which field has the full text vs truncated text.

## Summary

**The Real Issue:**
- ❌ Code was using `step_name` (potentially already truncated) instead of `description` (full text)
- ❌ Short `step_name` values would bypass intelligent condensing
- ❌ Cache was serving old truncated labels

**The Fix:**
- ✅ Now prioritizes `description` (full text) over `step_name`
- ✅ Always condenses from the full source text
- ✅ Clears cache on each diagram generation
- ✅ Consistent behavior across all steps

**To Apply the Fix:**
1. Restart your Python process to reload the modules
2. Re-run the workflow capture or regenerate the diagram
3. All steps should now be properly summarized from their full descriptions

The fix ensures that **every step is intelligently summarized from its full description**, not from potentially truncated initial names!
