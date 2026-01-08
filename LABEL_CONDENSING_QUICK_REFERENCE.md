# Quick Reference: Label Condensing System

## Overview

The label condensing system intelligently summarizes verbose descriptions into succinct, meaningful labels for BPMN diagrams.

**Key Principle:** Labels are SUMMARIZED (not truncated) to produce complete, meaningful phrases.

## How It Works

### 1. Main Entry Point: `condense_label()`

```python
from src.actions.diagram_generation import condense_label

# Basic usage
label = condense_label(
    text="The first step is to gather all client information and documents",
    max_length=35,
    context="step",
    use_llm=True
)
# Returns: "Gather client information"
```

### 2. Context Types

| Context | Max Length | Output Format | Example |
|---------|------------|---------------|---------|
| `step` | 35 chars | Verb+noun | "Gather client information" |
| `trigger` | 35 chars | Event phrase | "Customer places order" |
| `decision` | 35 chars | Yes/no question | "Meets approval criteria?" |
| `outcome` | 20 chars | Condition | "Item damaged" |
| `end` | 30 chars | Completion phrase | "Order shipped" |

### 3. Processing Flow

```
Input Text
    ↓
┌───────────────────────────────┐
│ Step 1: Try Verb+Noun Extract │
│ (_extract_verb_noun)           │
└───────────────────────────────┘
    ↓ (if fails or incomplete)
┌───────────────────────────────┐
│ Step 2: Use LLM Summarization │
│ (GPT-4o-mini)                  │
└───────────────────────────────┘
    ↓ (if fails or no API key)
┌───────────────────────────────┐
│ Step 3: Deterministic Fallback│
│ - Extract complete phrases     │
│ - Remove filler words          │
│ - Break at sentence boundaries │
└───────────────────────────────┘
    ↓
┌───────────────────────────────┐
│ Step 4: Validate Completeness │
│ - Check incomplete endings     │
│ - Verify length constraints    │
└───────────────────────────────┘
    ↓
Complete, Meaningful Label ✓
```

## Usage Examples

### Example 1: Workflow Step
```python
text = "The next step involves reviewing the identification letter for accuracy and ensuring all IRS requirements are met"

label = condense_label(text, max_length=35, context="step", use_llm=True)
# Returns: "Review identification letter"
```

### Example 2: Process Trigger
```python
text = "The process begins when a customer completes the online order form and submits payment"

label = condense_label(text, max_length=35, context="trigger", use_llm=True)
# Returns: "Customer completes order form"
```

### Example 3: Decision Point
```python
text = "At this stage, the manager needs to determine whether the request meets all approval criteria and budget constraints"

label = condense_label(text, max_length=35, context="decision", use_llm=True)
# Returns: "Meets approval criteria?"
```

## Configuration

### Environment Variables
```bash
# Required for LLM-powered summarization
OPENAI_API_KEY=sk-...

# Optional: Fallback will use deterministic extraction
```

### Programmatic Configuration
```python
from src.actions.diagram_generation import build_bpmn_lite_mermaid

# Enable LLM condensing (default)
diagram = build_bpmn_lite_mermaid(workflow_map, use_llm_condense=True)

# Disable LLM condensing (uses only deterministic extraction)
diagram = build_bpmn_lite_mermaid(workflow_map, use_llm_condense=False)
```

## Common Patterns Recognized

### Verb+Noun Extraction

The system recognizes 45+ common action verbs:

**Document Handling:**
- Gather, Collect, Review, Validate
- Draft, Prepare, Generate, Create
- Submit, Send, Distribute, Share

**Process Actions:**
- Process, Execute, Complete, Finalize
- Approve, Reject, Sign, Authorize
- Update, Modify, Change, Revise

**Financial:**
- Receive, Disburse, Fund, Transfer
- Calculate, Assess, Evaluate, Analyze

**Real Estate/Legal:**
- Purchase, Sell, Exchange, Close
- Identify, Track, Monitor, Coordinate

**Communication:**
- Notify, Contact, Inform, Alert
- Confirm, Verify, Check, Ensure

## Troubleshooting

### Problem: Labels still too long

**Solution:** Reduce max_length parameter
```python
label = condense_label(text, max_length=25, context="step")
```

### Problem: Labels are truncated/incomplete

**Check:**
1. Is OpenAI API key set?
2. Is `use_llm=True`?
3. Check console for `[WARN] LLM condensing failed` messages

**Fix:**
```python
# Ensure LLM is enabled
label = condense_label(text, max_length=35, context="step", use_llm=True)

# Check environment
import os
print(os.getenv("OPENAI_API_KEY"))  # Should not be None
```

### Problem: LLM calls are slow/expensive

**Solution:** Use caching or disable LLM
```python
# Labels are cached automatically
from src.actions.diagram_generation import clear_condense_cache

# Clear cache if needed (e.g., between test runs)
clear_condense_cache()

# Or disable LLM for faster (but lower quality) processing
label = condense_label(text, max_length=35, context="step", use_llm=False)
```

## Testing

### Manual Testing
```python
from src.actions.diagram_generation import condense_label

test_cases = [
    "Confirm that funds have been received",
    "Review identification letter for completeness",
    "Close purchase transaction at title company",
]

for text in test_cases:
    result = condense_label(text, max_length=35, context="step", use_llm=True)
    print(f"'{text}' → '{result}' ({len(result)} chars)")
```

### Automated Testing
```python
from src.actions.diagram_generation import _extract_verb_noun

def test_completeness():
    """Ensure labels don't end with incomplete markers"""
    text = "Confirm that funds have been received and deposited"
    result = _extract_verb_noun(text)
    
    incomplete = ('the', 'a', 'to', 'of', 'for', 'and', 'or', 'that', 'is')
    assert not result.lower().endswith(incomplete), f"Incomplete: {result}"
    assert len(result) <= 35, f"Too long: {result}"
```

## Best Practices

### 1. Always Use Context
```python
# Good - provides context
label = condense_label(text, max_length=35, context="step")

# Bad - loses context-aware processing
label = condense_label(text, max_length=35)
```

### 2. Enable LLM for Production
```python
# Good - intelligent summarization
build_bpmn_lite_mermaid(workflow, use_llm_condense=True)

# Only disable for testing/development
build_bpmn_lite_mermaid(workflow, use_llm_condense=False)
```

### 3. Validate Output
```python
label = condense_label(text, max_length=35, context="step")

# Check completeness
incomplete_markers = ('the', 'a', 'to', 'of', 'for', 'and', 'or')
if label.lower().endswith(incomplete_markers):
    print(f"WARNING: Incomplete label: {label}")
```

### 4. Monitor LLM Usage
```python
import logging

logging.basicConfig(level=logging.INFO)

# Will log warnings if LLM fails
label = condense_label(text, max_length=35, context="step", use_llm=True)
# Look for: [WARN] LLM condensing failed: ...
```

## Performance Considerations

### Caching
- Labels are automatically cached by (context, max_length, text)
- Cache persists for the session
- Clear cache between test runs to avoid stale results

### LLM Costs
- GPT-4o-mini: ~$0.00015 per label (typical)
- Consider batching for large workflows
- Use deterministic mode for testing to save costs

### Speed
- LLM mode: ~500-1000ms per label (network dependent)
- Deterministic mode: ~1-5ms per label
- Cache hit: <1ms

## Integration Points

### Workflow Capture (Flow B)
```python
# In workflow_actions.py
def update_live_bpmn_artifact(slots: dict[str, Any]) -> dict[str, Any]:
    mermaid_content = build_bpmn_lite_mermaid(
        active_workflow,
        use_llm_condense=True  # ← Labels are intelligently summarized
    )
```

### Diagram Generation
```python
# In diagram_generation.py
def build_bpmn_lite_mermaid(workflow_map, use_llm_condense=True):
    # For each step
    node_label = condense_label(
        step_name, 
        max_length=35, 
        context="step", 
        use_llm=use_llm_condense  # ← Controlled by parameter
    )
```

## Summary

**Key Points:**
- ✅ Always produces complete, meaningful phrases
- ✅ Never truncates mid-sentence or mid-word
- ✅ Context-aware summarization
- ✅ Multiple fallback levels for robustness
- ✅ Automatic caching for performance
- ✅ LLM-powered with deterministic fallback

**Remember:**
> "Labels should be succinct AND meaningful - never truncated, always complete."
