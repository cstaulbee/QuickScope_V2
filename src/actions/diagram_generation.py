"""
Deterministic diagram generation for live process visualization.

Generates Mermaid BPMN-lite diagrams from workflow maps.
"""

import json
from pathlib import Path
from typing import Any, Optional
from functools import lru_cache


# Simple in-memory cache for LLM condensing
_condense_cache: dict[str, str] = {}


def _extract_verb_noun(text: str) -> str:
    """
    Extract a concise verb+noun phrase from a longer text.
    
    This is designed to extract the core action from verbose descriptions
    for diagram labeling purposes (ideally just verb+noun).
    
    Args:
        text: Original text (possibly verbose)
        
    Returns:
        Concise verb+noun phrase (complete, not truncated)
    """
    import re
    
    if not text:
        return ""
    
    # Clean common verbose prefixes first
    text = re.sub(r'^(?:the\s+)?(?:first|next|immediate|main)\s+(?:action|step|task)\s+(?:is|is to|after|involves?|would be)\s+', '', text, flags=re.IGNORECASE)
    text = re.sub(r'^\s*(?:typically|usually|generally|we|this|it)\s+', '', text, flags=re.IGNORECASE)
    text = re.sub(r'^(?:to\s+)?', '', text, flags=re.IGNORECASE)
    
    # List of common action verbs to look for (expanded list)
    action_verbs = [
        r'\b(intake|intaking)\b',
        r'\b(receiv(?:e|ing))\b',
        r'\b(gather(?:ing)?)\b',
        r'\b(collect(?:ing)?)\b',
        r'\b(review(?:ing)?)\b',
        r'\b(validat(?:e|ing))\b',
        r'\b(confirm(?:ing)?)\b',
        r'\b(draft(?:ing)?)\b',
        r'\b(prepar(?:e|ing))\b',
        r'\b(send(?:ing)?)\b',
        r'\b(generat(?:e|ing))\b',
        r'\b(creat(?:e|ing))\b',
        r'\b(updat(?:e|ing))\b',
        r'\b(process(?:ing)?)\b',
        r'\b(submit(?:ting)?)\b',
        r'\b(approv(?:e|ing))\b',
        r'\b(reject(?:ing)?)\b',
        r'\b(transfer(?:ring)?)\b',
        r'\b(close|closing|clos(?:ing)?)\b',
        r'\b(open(?:ing)?)\b',
        r'\b(set(?:ting)?(?:\s+up)?)\b',
        r'\b(identif(?:y|ying))\b',
        r'\b(track(?:ing)?)\b',
        r'\b(monitor(?:ing)?)\b',
        r'\b(check(?:ing)?)\b',
        r'\b(verif(?:y|ying))\b',
        r'\b(disburs(?:e|ing))\b',
        r'\b(fund(?:ing)?)\b',
        r'\b(finaliz(?:e|ing))\b',
        r'\b(complet(?:e|ing))\b',
        r'\b(ensur(?:e|ing))\b',
        r'\b(coordinat(?:e|ing))\b',
        r'\b(manag(?:e|ing))\b',
        r'\b(purchas(?:e|ing))\b',
        r'\b(sell(?:ing)?)\b',
        r'\b(exchang(?:e|ing))\b',
        r'\b(sign(?:ing)?)\b',
        r'\b(execut(?:e|ing))\b',
        r'\b(notif(?:y|ying))\b',
        r'\b(contact(?:ing)?)\b',
        r'\b(calculat(?:e|ing))\b',
        r'\b(determin(?:e|ing))\b',
        r'\b(assess(?:ing)?)\b',
        r'\b(evaluat(?:e|ing))\b',
        r'\b(analyz(?:e|ing))\b',
    ]
    
    # Look for verb patterns followed by an object (be more generous with object capture)
    for verb_pattern in action_verbs:
        # Match verb + optional articles/prepositions + object (up to next punctuation or conjunction)
        pattern = verb_pattern + r'\s+(?:the\s+|a\s+|an\s+|all\s+|that\s+|of\s+(?:the\s+|all\s+)?)?([^,.;]+?)(?:\s+(?:and|or|with|for|to|from|during|after|before|at|in|on|is|are|that)|[,.;]|$)'
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            verb = match.group(1).lower()
            obj = match.group(2).strip()
            
            # Clean up the object (remove trailing articles/prepositions/location markers)
            obj = re.sub(r'\s+(?:a|an|the|of|for|to|from|with|at|in|on|during|is|are)(?:\s+the)?$', '', obj, flags=re.IGNORECASE).strip()
            
            # If object is still too long, take key words (up to 3-4 words)
            obj_words = obj.split()
            if len(obj_words) > 4:
                # Try to keep the most meaningful words
                obj_words = obj_words[:4]
            elif len(obj_words) > 2:
                # For 3-4 word objects, check if we can trim
                # Remove trailing location/context words
                while obj_words and obj_words[-1].lower() in ('at', 'in', 'on', 'the', 'a', 'an', 'to', 'from', 'with', 'for'):
                    obj_words.pop()
            
            obj = ' '.join(obj_words)
            
            # Capitalize first letter of verb and make it present tense if possible
            if verb.endswith('ing'):
                # Convert gerund to base form
                verb_base = verb[:-3] if len(verb) > 4 else verb
                # Handle special cases
                if verb_base.endswith('t'):
                    verb_base = verb_base  # submit -> submit
                verb = verb_base.capitalize()
            else:
                verb = verb.capitalize()
            
            result = f"{verb} {obj}".strip()
            
            # Final cleanup: remove incomplete trailing words
            result_words = result.split()
            while result_words and result_words[-1].lower() in ('and', 'or', 'the', 'a', 'to', 'of', 'for', 'that', 'is', 'all', 'at', 'in', 'on', 'with'):
                result_words.pop()
            result = ' '.join(result_words)
            
            # Only return if it's under max length AND not empty
            if result and len(result) <= 35:
                return result
            elif result and len(result) <= 40:  # Allow slightly longer if meaningful
                return result
    
    # Fallback: look for "is to", "involves", etc. patterns
    fallback_patterns = [
        r'is to\s+([^,.;]{5,40}?)(?:\.|,|;|and|or|with|for|$)',
        r'is the\s+([^,.;]{5,40}?)(?:\.|,|;|and|or|with|for|$)',
        r'involves?\s+([^,.;]{5,40}?)(?:\.|,|;|and|or|with|for|$)',
        r'(?:will|would)\s+([^,.;]{5,40}?)(?:\.|,|;|and|or|with|for|$)',
    ]
    
    for pattern in fallback_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            result = match.group(1).strip()
            # Clean trailing incomplete words
            result = re.sub(r'\s+(?:the|a|an|to|of|for|that|is|are|all)$', '', result, flags=re.IGNORECASE).strip()
            # Capitalize
            result = result[0].upper() + result[1:] if result else result
            if len(result) <= 35 and not result.endswith(('and', 'or', 'the', 'a', 'to', 'of', 'for', 'that')):
                return result
    
    # Last resort: take first meaningful phrase/sentence
    first_sentence = re.split(r'[.!?;]', text)[0]
    # Remove leading phrases
    first_sentence = re.sub(r'^(?:the|a|an|typically|usually|we|this|it|to)\s+', '', first_sentence, flags=re.IGNORECASE)
    first_sentence = first_sentence.strip()
    
    # If it's short enough and complete, return it
    if len(first_sentence) <= 35:
        return first_sentence
    
    # Try to get a complete phrase within limits
    words = first_sentence.split()
    result = ""
    for i, word in enumerate(words):
        test_result = result + (" " if result else "") + word
        if len(test_result) <= 35:
            result = test_result
        else:
            break
    
    # Check if result is complete (doesn't end with incomplete phrase markers)
    if result and not result.endswith(('and', 'or', 'the', 'a', 'to', 'of', 'for', 'with', 'that', 'is', 'all')):
        return result
    
    # Remove trailing incomplete words
    result_words = result.split()
    while result_words and result_words[-1].lower() in ('and', 'or', 'the', 'a', 'to', 'of', 'for', 'with', 'that', 'is', 'all'):
        result_words.pop()
    
    return ' '.join(result_words) if result_words else text[:35]


def _call_llm_for_condensing(text: str, max_length: int, context: str) -> str:
    """
    Call LLM to condense text to a diagram-friendly label.
    
    Uses actual LLM for intelligent summarization to produce succinct, meaningful labels.
    
    Args:
        text: Original text to condense
        max_length: Target maximum length
        context: Context for condensing (e.g., 'trigger', 'step', 'decision', 'outcome')
        
    Returns:
        Condensed text that is succinct and meaningful (not truncated)
    """
    import re
    
    # For step context, ALWAYS use LLM to ensure proper summarization
    # Don't rely on verb+noun extraction alone as it can produce incomplete phrases
    # Skip the early return logic for steps - always call LLM
    
    # For non-step contexts, if text is already short enough, return as-is
    if context != "step" and (not text or len(text) <= max_length):
        return text
    
    # Use LLM to intelligently condense the text
    try:
        # Import and load environment variables
        import os
        from dotenv import load_dotenv
        load_dotenv()
        
        from langchain_openai import ChatOpenAI
        
        llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0,
            api_key=os.getenv("OPENAI_API_KEY")
        )
        
        # Create context-specific prompt
        if context == "step":
            system_msg = f"You are a process mapping expert. Condense the following step description into a succinct, meaningful verb-noun phrase (max {max_length} chars). Return ONLY the condensed phrase with no explanation, quotes, or extra text."
            example = "Example: 'The first step involves gathering all the client information and documents' -> 'Gather client information'"
        elif context == "trigger":
            system_msg = f"You are a process mapping expert. Condense the following trigger description into a succinct, meaningful phrase (max {max_length} chars). Return ONLY the condensed phrase with no explanation, quotes, or extra text."
            example = "Example: 'The process starts when a customer places an order through the website' -> 'Customer places order'"
        elif context == "decision":
            system_msg = f"You are a process mapping expert. Condense the following decision into a succinct yes/no question (max {max_length} chars). Return ONLY the question with no explanation, quotes, or extra text."
            example = "Example: 'The manager needs to determine whether the request meets all the approval criteria' -> 'Meets approval criteria?'"
        elif context == "outcome":
            system_msg = f"You are a process mapping expert. Condense the following outcome into a succinct label (max {max_length} chars). Return ONLY the label with no explanation, quotes, or extra text."
            example = "Example: 'If the item is found to be damaged or defective' -> 'Item damaged'"
        else:
            system_msg = f"You are a process mapping expert. Condense the following text into a succinct, meaningful phrase (max {max_length} chars). Return ONLY the condensed phrase with no explanation, quotes, or extra text."
            example = ""
        
        prompt = f"{system_msg}\n\n{example}\n\nText to condense: {text}"
        
        response = llm.invoke(prompt)
        condensed = response.content.strip()
        
        # Clean up any quotes that might have been added
        condensed = condensed.strip('"').strip("'")
        
        # Ensure it's not longer than max_length
        if len(condensed) > max_length:
            # If LLM failed to respect length, truncate at word boundary
            words = condensed.split()
            condensed = ""
            for word in words:
                if len(condensed) + len(word) + (1 if condensed else 0) <= max_length:
                    condensed += (" " if condensed else "") + word
                else:
                    break
            
            # Remove trailing incomplete words after truncation
            while condensed:
                condensed_words = condensed.split()
                if condensed_words and condensed_words[-1].lower() in ('and', 'or', 'the', 'a', 'to', 'of', 'for', 'with', 'that', 'is', 'all'):
                    condensed_words.pop()
                    condensed = ' '.join(condensed_words)
                else:
                    break
        
        # Validate that result is meaningful and complete
        if condensed and not condensed.endswith(('and', 'or', 'the', 'a', 'to', 'of', 'for', 'with', 'that', 'is')):
            return condensed
        
    except Exception as e:
        print(f"[WARN] LLM condensing failed: {e}")
    
    # Fallback: For step context, try verb+noun extraction first
    if context == "step":
        extracted = _extract_verb_noun(text)
        # Validate that extracted phrase is complete and meaningful
        if extracted and len(extracted) <= max_length:
            # Check that it doesn't end with incomplete words
            if not extracted.endswith(('and', 'or', 'the', 'a', 'to', 'of', 'for', 'with', 'that', 'is', 'all')):
                return extracted
    
    # Fallback: Use deterministic condensing with better logic
    # Remove common filler phrases
    fillers = [
        r'\bThe\s+',
        r'\bA\s+',
        r'\bAn\s+',
        r'\btypically\b',
        r'\busually\b',
        r'\bgenerally\b',
        r'\boften\b',
        r'\bbasically\b',
        r'\bessentially\b',
        r'\bin order to\b',
        r'\bfor the purpose of\b',
        r'\bat this point\b',
        r'\bat this stage\b',
    ]
    
    condensed = text
    for filler in fillers:
        condensed = re.sub(filler, '', condensed, flags=re.IGNORECASE)
    
    # Collapse multiple spaces
    condensed = re.sub(r'\s+', ' ', condensed).strip()
    
    # If still too long, take complete sentences or phrases
    if len(condensed) > max_length:
        # Try to extract a complete meaningful phrase
        sentences = re.split(r'[.!?;]', condensed)
        if sentences and len(sentences[0]) <= max_length:
            return sentences[0].strip()
        
        # Try to break at natural phrase boundaries (commas, conjunctions)
        phrase_breaks = re.split(r'(?:,|\band\b|\bor\b|\bbut\b)', condensed)
        for phrase in phrase_breaks:
            phrase = phrase.strip()
            if phrase and len(phrase) <= max_length:
                # Validate this phrase is complete
                if not phrase.endswith(('and', 'or', 'the', 'a', 'to', 'of', 'for', 'with', 'that', 'is', 'all')):
                    return phrase
        
        # Last resort: truncate at word boundary but try to keep meaningful
        words = condensed.split()
        result = ""
        for word in words:
            if len(result) + len(word) + (1 if result else 0) <= max_length:
                result += (" " if result else "") + word
            else:
                break
        
        # Remove trailing incomplete words
        while result:
            result_words = result.split()
            if result_words and result_words[-1].lower() in ('and', 'or', 'the', 'a', 'to', 'of', 'for', 'with', 'that', 'is', 'all'):
                result_words.pop()
                result = ' '.join(result_words)
            else:
                break
        
        return result if result else condensed[:max_length]
    
    return condensed


def condense_label(text: str, max_length: int = 60, context: str = "general", use_llm: bool = False) -> str:
    """
    Condense a label to be diagram-friendly.
    
    Uses caching to avoid repeated work.
    
    Args:
        text: Original text
        max_length: Maximum length for label
        context: Context hint ('trigger', 'step', 'decision', 'outcome', etc.)
        use_llm: If True, use LLM assistance (when available)
        
    Returns:
        Condensed label
    """
    if not text:
        return ""
    
    # Check cache
    cache_key = f"{context}:{max_length}:{text}"
    if cache_key in _condense_cache:
        return _condense_cache[cache_key]
    
    # Always use smart condensing for steps
    if context == "step":
        result = _call_llm_for_condensing(text, max_length, context)
    elif use_llm:
        result = _call_llm_for_condensing(text, max_length, context)
    else:
        # Simple deterministic condensing - truncate at word boundary
        if len(text) <= max_length:
            result = text
        else:
            # Truncate at word boundary
            words = text.split()
            result = ""
            for word in words:
                if len(result) + len(word) + 1 <= max_length:
                    result += (" " if result else "") + word
                else:
                    break
            # Fallback to character truncate if no words fit
            if not result:
                result = text[:max_length]
    
    # Cache and return
    _condense_cache[cache_key] = result
    return result


def clear_condense_cache():
    """Clear the condensing cache. Useful for testing."""
    global _condense_cache
    _condense_cache.clear()


def normalize_step_label(step_name: str) -> str:
    """
    Normalize step label for matching.
    
    Converts to lowercase, removes punctuation, collapses spaces.
    """
    import re
    normalized = step_name.lower()
    normalized = re.sub(r'[^\w\s]', '', normalized)
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    return normalized


def find_step_by_name(step_name: str, steps: list[dict[str, Any]]) -> Optional[str]:
    """
    Find a step ID by matching step name (fuzzy match).
    
    Args:
        step_name: Name to search for
        steps: List of steps to search in
        
    Returns:
        Step ID if found, None otherwise
    """
    if not step_name or not steps:
        return None
    
    normalized_target = normalize_step_label(step_name)
    target_words = set(normalized_target.split())
    
    # First pass: exact match on normalized
    for i, step in enumerate(steps):
        candidate_name = step.get("step_name") or step.get("description", "")
        normalized_candidate = normalize_step_label(candidate_name)
        
        if normalized_candidate == normalized_target:
            return f"step{i+1}"
    
    # Second pass: partial match (target is substring of candidate or vice versa)
    for i, step in enumerate(steps):
        candidate_name = step.get("step_name") or step.get("description", "")
        normalized_candidate = normalize_step_label(candidate_name)
        
        if normalized_target in normalized_candidate or normalized_candidate in normalized_target:
            return f"step{i+1}"
    
    # Third pass: word overlap (at least 50% of target words in candidate)
    for i, step in enumerate(steps):
        candidate_name = step.get("step_name") or step.get("description", "")
        normalized_candidate = normalize_step_label(candidate_name)
        candidate_words = set(normalized_candidate.split())
        
        # Calculate overlap
        overlap = len(target_words & candidate_words)
        if overlap > 0 and overlap >= len(target_words) * 0.5:
            return f"step{i+1}"
    
    return None


def validate_live_flowchart(mermaid: str) -> tuple[bool, Optional[str]]:
    """
    Validate a live BPMN-lite flowchart.
    
    Checks:
    - Must start with 'flowchart'
    - No decision gateways with <2 outgoing edges
    
    Returns:
        (is_valid, error_message)
    """
    import re
    
    if not mermaid or not mermaid.strip():
        return False, "Empty Mermaid diagram"
    
    lines = mermaid.strip().split('\n')
    
    # Check first line
    if not lines[0].strip().lower().startswith('flowchart'):
        return False, "Must start with 'flowchart'"
    
    # Check decision gateways have 2+ outgoing edges
    decision_nodes = {}
    for line in lines:
        # Find decision node definitions: node_id{text}
        match = re.search(r'(\w+)\{([^}]+)\}', line)
        if match:
            node_id = match.group(1)
            decision_nodes[node_id] = 0
    
    # Count outgoing edges from decision nodes
    for line in lines:
        # Find edges: from_id --> to_id or from_id -->|label| to_id
        match = re.search(r'(\w+)\s+-->', line)
        if match:
            from_id = match.group(1)
            if from_id in decision_nodes:
                decision_nodes[from_id] += 1
    
    # Check each decision has 2+ edges
    for node_id, count in decision_nodes.items():
        if count < 2:
            return False, f"Decision node '{node_id}' has fewer than 2 outgoing edges"
    
    return True, None


def build_fallback_linear_diagram(workflow_map: dict[str, Any]) -> str:
    """
    Build a simple linear diagram as fallback when validation fails.
    
    Only includes tasks in sequence, with decisions/outcomes as note annotations.
    
    Args:
        workflow_map: Workflow map
        
    Returns:
        Simple Mermaid flowchart
    """
    lines = ["flowchart TD"]
    
    workflow_id = workflow_map.get("workflow_id", "wf")
    trigger = workflow_map.get("trigger") or "Start"
    end_condition = workflow_map.get("end_condition") or "Complete"
    steps = workflow_map.get("steps", [])
    
    # Start
    start_id = f"{workflow_id}_start"
    trigger_label = condense_label(trigger, max_length=35, context="trigger", use_llm=False)
    trigger_label_escaped = trigger_label.replace('"', "'")
    lines.append(f'    {start_id}(["{trigger_label_escaped}"])')
    
    prev_id = start_id
    
    # Steps (linear only)
    for i, step in enumerate(steps):
        step_id = f"{workflow_id}_step{i+1}"
        
        # Prefer description over step_name (same logic as main function)
        description = step.get("description")
        step_name = step.get("step_name")
        source_text = description if description else (step_name if step_name else f"Step {i+1}")
        
        owner = step.get("owner_role", "")
        
        if owner:
            label = condense_label(f"{owner}: {source_text}", max_length=35, context="step", use_llm=False)
        else:
            label = condense_label(source_text, max_length=35, context="step", use_llm=False)
        
        label_escaped = label.replace('"', "'")
        lines.append(f'    {step_id}["{label_escaped}"]')
        lines.append(f'    {prev_id} --> {step_id}')
        
        # Add decision/outcome as note if present
        decision = step.get("decision_normalized") or step.get("decision")
        if decision and str(decision).lower() not in ("no", "none", "n/a"):
            note_id = f"{step_id}_note"
            decision_label = condense_label(f"Decision: {decision}", max_length=30, context="decision", use_llm=False)
            decision_label_escaped = decision_label.replace('"', "'")
            lines.append(f'    {note_id}["{decision_label_escaped}"]')
            lines.append(f'    {step_id} -.- {note_id}')
        
        prev_id = step_id
    
    # End
    end_id = f"{workflow_id}_end"
    end_label = condense_label(end_condition, max_length=30, context="end", use_llm=False)
    end_label_escaped = end_label.replace('"', "'")
    lines.append(f'    {end_id}(["{end_label_escaped}"])')
    lines.append(f'    {prev_id} --> {end_id}')
    
    return "\n".join(lines)


def build_bpmn_lite_mermaid(workflow_map: dict[str, Any], use_llm_condense: bool = True) -> str:
    """
    Generate Mermaid flowchart (BPMN-lite) from a workflow map.
    
    Supports real branching with placeholders for unresolved next steps.
    
    Uses:
    - ([Start]) for start event
    - [Task] for tasks
    - {Decision} for gateways
    - ([End]) for end event
    - [Pending: ...] for placeholder nodes
    
    Args:
        workflow_map: Workflow map with steps, trigger, end_condition
        use_llm_condense: If True, use LLM-assisted label condensing
        
    Returns:
        Mermaid flowchart string
    """
    lines = ["flowchart TD"]
    
    workflow_name = workflow_map.get("workflow_name", "Process")
    workflow_id = workflow_map.get("workflow_id", "wf")
    trigger = workflow_map.get("trigger") or "Start"
    end_condition = workflow_map.get("end_condition") or "Complete"
    steps = workflow_map.get("steps", [])
    
    # Sanitize node IDs (no spaces, special chars)
    def sanitize_id(text: str) -> str:
        if not text:
            return "node"
        # Replace spaces and special chars with underscore
        sanitized = "".join(c if c.isalnum() or c == "_" else "_" for c in str(text))
        return sanitized[:50]  # Limit length
    
    # Start event - use condensing instead of truncation - reduce to 35 chars
    start_id = f"{workflow_id}_start"
    trigger_condensed = condense_label(trigger, max_length=35, context="trigger", use_llm=use_llm_condense)
    trigger_condensed = trigger_condensed.replace('"', "'")
    lines.append(f'    {start_id}(["{trigger_condensed}"])')
    
    # Track which nodes we've created
    created_nodes = {start_id}
    # Track edges to add
    edges = []
    
    # Track previous node for linear linking (fallback)
    prev_node_id = start_id
    
    # Generate nodes for each step
    for i, step in enumerate(steps):
        step_num = i + 1
        step_id = f"{workflow_id}_step{step_num}"
        
        # Prefer description (full detail) over step_name (which might already be truncated)
        # This ensures we always condense from the full text, not from already-truncated text
        description = step.get("description")
        step_name = step.get("step_name")
        
        # Use description if available (it's the full detailed version)
        # Fall back to step_name if no description
        # Finally fall back to generic label
        if description:
            source_text = description
        elif step_name:
            source_text = step_name
        else:
            source_text = f"Step {step_num}"
        
        owner = step.get("owner_role", "")
        decision_normalized = step.get("decision_normalized") or step.get("decision")
        decision_outcomes_parsed = step.get("decision_outcomes_parsed", [])
        
        # ALWAYS condense the source text (whether it's description or step_name)
        # This ensures even if step_name is truncated, we get a proper condensed version
        if owner:
            node_label = condense_label(f"{owner}: {source_text}", max_length=35, context="step", use_llm=use_llm_condense)
        else:
            node_label = condense_label(source_text, max_length=35, context="step", use_llm=use_llm_condense)
        
        # Escape quotes
        node_label = node_label.replace('"', "'")
        
        # Task node
        lines.append(f'    {step_id}["{node_label}"]')
        created_nodes.add(step_id)
        
        # Link from previous (if no branching handled yet)
        if prev_node_id and prev_node_id not in [e[0] for e in edges]:
            edges.append((prev_node_id, step_id, None))
        
        # Check if we have a real decision with 2+ outcomes
        if decision_normalized and decision_outcomes_parsed and len(decision_outcomes_parsed) >= 2:
            decision_id = f"{step_id}_decision"
            decision_text = condense_label(decision_normalized, max_length=35, context="decision", use_llm=use_llm_condense)
            
            # Ensure it ends with ?
            if not decision_text.endswith('?'):
                decision_text += '?'
            decision_text = decision_text.replace('"', "'")
            
            lines.append(f'    {decision_id}{{{decision_text}}}')
            created_nodes.add(decision_id)
            edges.append((step_id, decision_id, None))
            
            # Add outcome branches
            for j, outcome_data in enumerate(decision_outcomes_parsed[:3]):  # Max 3
                outcome_label = outcome_data.get("label", f"Outcome {j+1}")
                next_ref = outcome_data.get("next_ref", "")
                target_type = outcome_data.get("target_type", "next")
                
                outcome_label_condensed = condense_label(outcome_label, max_length=20, context="outcome", use_llm=use_llm_condense)
                outcome_label_condensed = outcome_label_condensed.replace('"', "'")
                
                if target_type == "end":
                    # Link to end node
                    target_id = f"{workflow_id}_end"
                    edges.append((decision_id, target_id, outcome_label_condensed))
                else:
                    # Try to resolve next_ref to a known step
                    target_step_id = find_step_by_name(next_ref, steps[i+1:])  # Only look forward
                    
                    if target_step_id:
                        # Found a matching step
                        full_target_id = f"{workflow_id}_{target_step_id}"
                        edges.append((decision_id, full_target_id, outcome_label_condensed))
                    else:
                        # Create a placeholder node
                        placeholder_id = f"{step_id}_pending{j+1}"
                        placeholder_label = condense_label(f"Pending: {next_ref}", max_length=50, context="pending", use_llm=use_llm_condense)
                        placeholder_label = placeholder_label.replace('"', "'")
                        
                        lines.append(f'    {placeholder_id}["{placeholder_label}"]')
                        created_nodes.add(placeholder_id)
                        edges.append((decision_id, placeholder_id, outcome_label_condensed))
            
            # Don't set prev_node_id - branches handle their own connections
            prev_node_id = None
        else:
            # No branching decision
            prev_node_id = step_id
    
    # End event
    end_id = f"{workflow_id}_end"
    end_text = condense_label(end_condition, max_length=30, context="end", use_llm=use_llm_condense)
    end_text = end_text.replace('"', "'")
    lines.append(f'    {end_id}(["{end_text}"])')
    created_nodes.add(end_id)
    
    # Link to end if we have a prev_node_id (linear flow case)
    if prev_node_id:
        edges.append((prev_node_id, end_id, None))
    elif not steps:
        edges.append((start_id, end_id, None))
    
    # Add all edges
    for from_id, to_id, label in edges:
        if label:
            lines.append(f'    {from_id} -->|"{label}"| {to_id}')
        else:
            lines.append(f'    {from_id} --> {to_id}')
    
    diagram = "\n".join(lines)
    
    # Validate the diagram
    is_valid, error_msg = validate_live_flowchart(diagram)
    
    if not is_valid:
        print(f"[WARN] Live diagram validation failed: {error_msg}")
        print(f"[WARN] Falling back to simple linear diagram")
        # Fall back to simple linear diagram
        diagram = build_fallback_linear_diagram(workflow_map)
    
    return diagram



def write_mermaid_artifact(file_path: str, content: str) -> None:
    """
    Write Mermaid content to a file, creating directories if needed.
    
    Args:
        file_path: Path to write to (e.g., "artifacts/live_bpmn_wf_1.mmd")
        content: Mermaid diagram content
    """
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
