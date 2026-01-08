"""
Action function stubs for workflow processing.

These will be fully implemented in the next step.
All actions are deterministic (no LLM calls).
"""

from typing import Any, Optional
import copy


def _deep_copy_slots(slots: dict[str, Any]) -> dict[str, Any]:
    """Helper to create a deep copy of slots to avoid mutation issues."""
    return copy.deepcopy(slots)



class ActionResult:
    """Result from an action execution."""
    
    def __init__(self, success: bool, value: Any = None, error: Optional[str] = None):
        self.success = success
        self.value = value
        self.error = error


def initialize_workflow_maps_from_selection(slots: dict[str, Any]) -> dict[str, Any]:
    """
    Create workflow map skeletons from workflows.selected_workflows.
    
    Sets active_workflow_id to the first workflow.
    """
    # Stub implementation
    selected = slots.get("workflows", {}).get("selected_workflows", [])
    
    maps = []
    for i, workflow_name in enumerate(selected):
        maps.append({
            "workflow_id": f"wf_{i+1}",
            "workflow_name": workflow_name,
            "trigger": None,
            "start_condition": None,
            "end_condition": None,
            "lanes": [],
            "steps": [],
            "decisions": [],
            "exceptions": [],
            "wait_states": [],
            "artifacts_touched": [],
            "notes": []
        })
    
    result = slots.copy()
    result.setdefault("workflows", {})["maps"] = maps
    result.setdefault("workflow_capture_state", {})["active_workflow_id"] = maps[0]["workflow_id"] if maps else None
    
    return result


def write_trigger_to_active_workflow(slots: dict[str, Any]) -> dict[str, Any]:
    """
    Write workflow trigger and start/end conditions from capture state to active workflow.
    """
    result = slots.copy()
    active_wf_id = result.get("workflow_capture_state", {}).get("active_workflow_id")
    
    if not active_wf_id:
        return result
    
    # Get trigger from buffer
    trigger = result.get("workflow_capture_state", {}).get("workflow_level_buffer", {}).get("trigger")
    start_condition = result.get("workflow_capture_state", {}).get("workflow_level_buffer", {}).get("start_condition")
    end_condition = result.get("workflow_capture_state", {}).get("workflow_level_buffer", {}).get("end_condition")
    
    # Find active workflow and update
    for wf in result.get("workflows", {}).get("maps", []):
        if wf.get("workflow_id") == active_wf_id:
            if trigger:
                wf["trigger"] = trigger
            if start_condition:
                wf["start_condition"] = start_condition
            if end_condition:
                wf["end_condition"] = end_condition
            break
    
    # Clear buffer
    if "workflow_level_buffer" in result.get("workflow_capture_state", {}):
        result["workflow_capture_state"]["workflow_level_buffer"] = {}
    
    return result


def parse_enumerated_steps_into_skeleton(slots: dict[str, Any]) -> dict[str, Any]:
    """
    Parse enumerated steps list into step queue skeleton.
    
    Takes the user's numbered list and creates a step_queue array with step placeholders.
    Sets current_step_index to 0 and prepares for step-by-step capture.
    """
    import re
    
    result = _deep_copy_slots(slots)
    enumerated_steps = result.get("workflow_capture_state", {}).get("enumerated_steps", "")
    
    if not enumerated_steps:
        # No steps provided, create empty queue
        result.setdefault("workflow_capture_state", {})["step_queue"] = []
        result["workflow_capture_state"]["current_step_index"] = 0
        result["workflow_capture_state"]["current_step_display"] = 1
        result["workflow_capture_state"]["step_count"] = 0
        result["workflow_capture_state"]["step_list_summary"] = "No steps provided"
        return result
    
    # Parse numbered list (handles various formats)
    # Examples:
    # 1. Intake
    # 1) Exchange Agreement
    # - Intake
    # * Exchange Agreement
    lines = enumerated_steps.strip().split("\n")
    steps = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Remove various numbering patterns
        # Match: "1.", "1)", "- ", "* ", "• ", etc.
        clean_line = re.sub(r"^(\d+[\.\)]?|\-|\*|\•)\s*", "", line)
        
        if clean_line:
            steps.append({
                "step_name": clean_line,
                "description": None,
                "owner_role": None,
                "inputs": None,
                "outputs": None,
                "systems_tools_used": None,
                "decision": None,
                "decision_outcomes": None,
                "wait_or_delay": None,
                "common_exception": None
            })
    
    # Build summary for confirmation
    step_list_summary = "\n".join([f"{i+1}. {s['step_name']}" for i, s in enumerate(steps)])
    
    # Update workflow_capture_state
    result.setdefault("workflow_capture_state", {})["step_queue"] = steps
    result["workflow_capture_state"]["current_step_index"] = 0
    result["workflow_capture_state"]["current_step_display"] = 1  # Human-readable (1-based)
    result["workflow_capture_state"]["step_count"] = len(steps)
    result["workflow_capture_state"]["step_list_summary"] = step_list_summary
    
    # Set current step name for first step
    if steps:
        result["workflow_capture_state"]["current_step_name"] = steps[0]["step_name"]
    
    return result


def normalize_decision_text(decision_text: str) -> str:
    """
    Normalize decision text by removing boilerplate phrases.
    
    Strips leading "Yes/No" preambles and common filler phrases.
    """
    if not decision_text:
        return ""
    
    text = decision_text.strip()
    
    # Remove leading "Yes, " or "Yes. " patterns with optional "the decision is/here is" phrases
    import re
    text = re.sub(r'^(?:Yes|No)[,\.\s]+(?:the\s+)?(?:decision\s+(?:is|here)\s*:?\s*)?', '', text, flags=re.IGNORECASE)
    
    # Remove trailing question marks if multiple exist (keep single ?)
    while text.endswith('??'):
        text = text[:-1]
    
    # Ensure it ends with a question mark if it's a question
    if text and not text.endswith('?') and any(word in text.lower() for word in ['is ', 'does ', 'can ', 'will ', 'should ', 'are ']):
        text += '?'
    
    return text.strip()


def parse_decision_outcomes(outcomes_text: str) -> list[dict[str, Any]]:
    """
    Parse decision outcomes from text into structured format.
    
    Expected format:
        OutcomeName -> Next: StepName
        OutcomeName -> End: Reason
    
    Returns list of dicts with keys: label, next_ref, target_type
    """
    if not outcomes_text:
        return []
    
    import re
    outcomes = []
    
    # Split by newlines and process each line
    lines = outcomes_text.strip().split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Match pattern: "Label -> Next: StepName" or "Label -> End: Reason"
        # Also support: "Label → Next: StepName" (unicode arrow)
        match = re.match(r'^(.+?)\s*[-→]+>\s*(Next|End)\s*:\s*(.+)$', line, re.IGNORECASE)
        
        if match:
            label = match.group(1).strip()
            target_type = match.group(2).lower()
            next_ref = match.group(3).strip()
            
            outcomes.append({
                "label": label,
                "next_ref": next_ref,
                "target_type": target_type  # 'next' or 'end'
            })
        else:
            # Try to parse freeform text like "Approved → moves to shipping"
            # Look for arrow-like separators
            arrow_match = re.match(r'^(.+?)\s*[→\-]+\s*(.+)$', line)
            if arrow_match:
                label = arrow_match.group(1).strip()
                next_ref = arrow_match.group(2).strip()
                
                # Guess target type based on keywords
                next_ref_lower = next_ref.lower()
                if any(word in next_ref_lower for word in ['end', 'stop', 'cancel', 'close', 'terminate']):
                    target_type = 'end'
                else:
                    target_type = 'next'
                    # Clean up common prefixes
                    next_ref = re.sub(r'^(?:moves to|goes to|proceeds to|returns to|pauses for)\s+', '', next_ref, flags=re.IGNORECASE)
                
                outcomes.append({
                    "label": label,
                    "next_ref": next_ref,
                    "target_type": target_type
                })
    
    return outcomes


def normalize_and_parse_decision_data(slots: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize decision text and parse outcomes into structured format.
    
    Updates active_step_buffer with:
    - decision_normalized: cleaned decision text
    - decision_outcomes_parsed: structured list of outcomes
    """
    result = _deep_copy_slots(slots)
    
    buffer = result.get("workflow_capture_state", {}).get("active_step_buffer", {})
    
    # Normalize decision text
    decision_raw = buffer.get("decision", "")
    decision_normalized = normalize_decision_text(decision_raw)
    
    # Parse outcomes
    outcomes_raw = buffer.get("decision_outcomes", "")
    outcomes_parsed = parse_decision_outcomes(outcomes_raw)
    
    # Store structured data back in buffer
    buffer["decision_normalized"] = decision_normalized
    buffer["decision_outcomes_parsed"] = outcomes_parsed
    
    print(f"[DEBUG] normalize_and_parse_decision_data:")
    print(f"  Raw decision: {decision_raw}")
    print(f"  Normalized: {decision_normalized}")
    print(f"  Parsed {len(outcomes_parsed)} outcomes: {outcomes_parsed}")
    
    return result


def check_step_has_decision(slots: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """
    Check if active_step_buffer has a non-empty decision field.
    
    If there's no decision, clears the decision field so it doesn't appear in diagrams.
    
    Returns (updated_slots, action_result_code)
    """
    result = slots.copy()
    decision = result.get("workflow_capture_state", {}).get("active_step_buffer", {}).get("decision")
    
    # Check if decision is non-empty (not None, not empty string, not "no", not "none")
    has_decision = False
    if decision:
        decision_lower = str(decision).strip().lower()
        # Check for explicit "no decision" phrases
        no_decision_phrases = [
            "no", "none", "n/a", "na", "not applicable",
            "no decision", "there's no decision", "there is no decision",
            "no, there", "not a decision", "no branch", "no branching"
        ]
        
        if decision_lower and not any(phrase in decision_lower for phrase in no_decision_phrases):
            has_decision = True
        else:
            # User said there's no decision, so clear the decision field
            # This prevents "No" from appearing as a decision node in diagrams
            result.setdefault("workflow_capture_state", {}).setdefault("active_step_buffer", {})["decision"] = ""
    
    # Set flag
    result.setdefault("workflow_capture_state", {}).setdefault("active_step_flags", {})["has_decision"] = has_decision
    
    print(f"[DEBUG] check_step_has_decision: decision='{decision}' -> {has_decision}")
    
    return result, "has_decision" if has_decision else "no_decision"


def update_live_bpmn_artifact(slots: dict[str, Any]) -> dict[str, Any]:
    """
    Generate and write live BPMN-lite Mermaid diagram for the active workflow.
    
    Writes to artifacts/live_bpmn_<workflow_id>.mmd
    """
    from src.actions.diagram_generation import build_bpmn_lite_mermaid, write_mermaid_artifact, clear_condense_cache
    
    result = slots.copy()
    active_wf_id = result.get("workflow_capture_state", {}).get("active_workflow_id")
    
    print(f"[DEBUG] update_live_bpmn_artifact called - active_wf_id: {active_wf_id}")
    
    if not active_wf_id:
        print("[DEBUG] No active workflow ID found")
        return result
    
    # Find active workflow
    active_workflow = None
    for wf in result.get("workflows", {}).get("maps", []):
        if wf.get("workflow_id") == active_wf_id:
            active_workflow = wf
            break
    
    if not active_workflow:
        print(f"[DEBUG] Could not find workflow with ID: {active_wf_id}")
        return result
    
    print(f"[DEBUG] Found workflow: {active_workflow.get('workflow_name')} with {len(active_workflow.get('steps', []))} steps")
    
    # Clear cache to ensure fresh condensing (important after code updates)
    clear_condense_cache()
    
    # Generate Mermaid diagram
    mermaid_content = build_bpmn_lite_mermaid(active_workflow)
    
    # Write to artifact file
    artifact_path = f"artifacts/live_bpmn_{active_wf_id}.mmd"
    write_mermaid_artifact(artifact_path, mermaid_content)
    
    print(f"[DEBUG] Diagram written to: {artifact_path}")
    
    # Store artifact path in slots for reference
    result.setdefault("workflow_capture_state", {})["live_diagram_path"] = artifact_path
    
    return result


def commit_step_to_active_workflow(slots: dict[str, Any]) -> dict[str, Any]:
    """
    Append active_step_buffer as a new step in the active workflow.
    
    Now also adds step_name from the current step in the queue.
    Includes duplicate detection to prevent same step from being added multiple times.
    """
    result = _deep_copy_slots(slots)
    buffer = result.get("workflow_capture_state", {}).get("active_step_buffer", {})
    active_wf_id = result.get("workflow_capture_state", {}).get("active_workflow_id")
    current_step_name = result.get("workflow_capture_state", {}).get("current_step_name")
    current_index = result.get("workflow_capture_state", {}).get("current_step_index", 0)
    
    print(f"[DEBUG] commit_step_to_active_workflow called:")
    print(f"  current_step_name: {current_step_name}")
    print(f"  current_index: {current_index}")
    print(f"  buffer keys: {list(buffer.keys()) if buffer else 'empty'}")
    print(f"  active_wf_id: {active_wf_id}")
    
    if not buffer or not active_wf_id:
        print("[DEBUG] Skipping commit - buffer or active_wf_id is empty")
        return result
    
    # Check for duplicate descriptions (case-insensitive, normalized)
    new_description = buffer.get("description", "").strip().lower()
    if not new_description:
        print("[DEBUG] Skipping commit - empty description")
        return result
    
    # Find active workflow
    target_workflow = None
    for wf in result.get("workflows", {}).get("maps", []):
        if wf.get("workflow_id") == active_wf_id:
            target_workflow = wf
            break
    
    if not target_workflow:
        print(f"[DEBUG] Warning: active workflow {active_wf_id} not found")
        return result
    
    # Check for duplicate in existing steps
    existing_steps = target_workflow.get("steps", [])
    for existing_step in existing_steps:
        existing_desc = existing_step.get("description", "").strip().lower()
        # Use fuzzy matching - check if descriptions are very similar (80%+ match)
        if existing_desc == new_description:
            print(f"[DEBUG] Skipping duplicate step: '{buffer.get('description', '')[:60]}...'")
            # Reset buffer without committing
            result["workflow_capture_state"]["active_step_buffer"] = {}
            return result
    
    # Add step_name to buffer if present
    step_to_commit = buffer.copy()
    if current_step_name:
        step_to_commit["step_name"] = current_step_name
    
    # Append step to workflow
    target_workflow.setdefault("steps", []).append(step_to_commit)
    print(f"[DEBUG] Committed step. Total steps now: {len(target_workflow.get('steps', []))}")
    
    # Extract lane from owner
    owner = buffer.get("owner_role")
    if owner and owner not in target_workflow.get("lanes", []):
        target_workflow.setdefault("lanes", []).append(owner)
    
    # Reset buffer (don't increment index here, that's done in advance_to_next_step)
    result["workflow_capture_state"]["active_step_buffer"] = {}
    
    return result


def advance_to_next_step_or_finish(slots: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """
    DEPRECATED: This function is no longer used in the new iterative flow.
    Kept for backward compatibility only.
    
    Advance to the next step in the step queue or signal completion.
    
    Returns (updated_slots, action_result_code):
    - "continue_next_step" if there are more steps to process
    - "all_steps_complete" if we've processed all steps
    """
    result = _deep_copy_slots(slots)
    
    step_queue = result.get("workflow_capture_state", {}).get("step_queue", [])
    current_index = result.get("workflow_capture_state", {}).get("current_step_index", 0)
    
    print(f"[DEBUG] advance_to_next_step_or_finish called:")
    print(f"  current_index: {current_index}")
    print(f"  total steps in queue: {len(step_queue)}")
    
    # Move to next step
    next_index = current_index + 1
    
    if next_index < len(step_queue):
        # There are more steps
        result["workflow_capture_state"]["current_step_index"] = next_index
        result["workflow_capture_state"]["current_step_display"] = next_index + 1  # Human-readable
        result["workflow_capture_state"]["current_step_name"] = step_queue[next_index]["step_name"]
        
        print(f"[DEBUG] Advancing to step {next_index + 1}: {step_queue[next_index]['step_name']}")
        
        # Clear the buffer for the next step
        result["workflow_capture_state"]["active_step_buffer"] = {}
        
        return result, "continue_next_step"
    else:
        # All steps complete
        result["workflow_capture_state"]["current_step_index"] = next_index
        result["workflow_capture_state"]["current_step_display"] = next_index + 1
        result["workflow_capture_state"]["current_step_name"] = None
        
        print(f"[DEBUG] All steps complete!")
        
        return result, "all_steps_complete"


def check_if_user_said_done(slots: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """
    Check if the user indicated they're done adding steps.
    
    Returns (updated_slots, action_result_code):
    - "done" if user said done/complete/finished
    - "continue" if they described another step
    """
    result = _deep_copy_slots(slots)
    
    next_step_response = result.get("workflow_capture_state", {}).get("next_step_response", "").lower().strip()
    
    # Check for completion signals - must be standalone or at start of response
    # Not just contained within longer descriptions
    done_signals = [
        (r'\bdone\b', "done"),
        (r'\bcomplete\b', "complete"),
        (r'\bfinished\b', "finished"),
        (r"that\'?s it", "that's it"),
        (r'\bno more\b', "no more"),
        (r'\bnothing\b', "nothing"),
        (r'\bend\b', "end"),
    ]
    
    import re
    
    # Only match if response is very short OR starts with done signal
    is_short = len(next_step_response.split()) <= 3
    
    for pattern, signal in done_signals:
        if re.search(pattern, next_step_response):
            # Check if it's at the start or the response is very short
            match = re.search(pattern, next_step_response)
            if match and (match.start() < 15 or is_short):
                print(f"[DEBUG] User indicated done: '{next_step_response}' (matched: {signal})")
                return result, "done"
    
    print(f"[DEBUG] User provided next step: '{next_step_response}'")
    return result, "continue"


def copy_next_step_to_buffer(slots: dict[str, Any]) -> dict[str, Any]:
    """
    Copy the user's description of the next step into the active_step_buffer.
    This allows us to continue with the normal step capture flow.
    
    Note: Question cursor reset is handled in auto_advance_node, not here,
    because actions can only update slots, not other state fields.
    """
    result = _deep_copy_slots(slots)
    
    next_step_response = result.get("workflow_capture_state", {}).get("next_step_response", "")
    
    # Initialize buffer with the description and empty strings for fields to be filled
    # Use empty strings instead of None so template rendering doesn't show placeholders
    result.setdefault("workflow_capture_state", {})["active_step_buffer"] = {
        "description": next_step_response,
        "owner_role": "",
        "inputs": "",
        "outputs": "",
        "systems_tools_used": "",
        "decision": "",
        "decision_outcomes": [],
        "wait_or_delay": "",
        "common_exception": ""
    }
    
    print(f"[DEBUG] Copied next step to buffer: {next_step_response}")
    
    return result


def advance_or_close_workflow_based_on_response(slots: dict[str, Any], user_response: str) -> tuple[dict[str, Any], str]:
    """
    If user indicates 'done', mark workflow closed; otherwise continue.
    
    Returns (updated_slots, action_result_code)
    """
    # Stub implementation
    result = slots.copy()
    normalized = user_response.lower().strip()
    
    if "done" in normalized or "complete" in normalized or "finished" in normalized:
        active_wf_id = result.get("workflow_capture_state", {}).get("active_workflow_id")
        
        for wf in result.get("workflows", {}).get("maps", []):
            if wf.get("workflow_id") == active_wf_id:
                wf["end_condition"] = user_response
                break
        
        return result, "workflow_closed"
    
    return result, "continue_same_workflow"


def apply_workflow_corrections(slots: dict[str, Any], corrections: str) -> dict[str, Any]:
    """
    Apply corrections to the active workflow based on user feedback.
    """
    import copy
    
    # Deep copy to avoid mutation issues
    result = copy.deepcopy(slots)
    
    # Ensure validation dict exists
    if "validation" not in result:
        result["validation"] = {}
    
    # Ensure gaps is a list
    if "gaps" not in result["validation"]:
        result["validation"]["gaps"] = []
    elif not isinstance(result["validation"]["gaps"], list):
        # If it's not a list (e.g., accidentally set to a string), reset it
        result["validation"]["gaps"] = []
    
    # Append the correction
    result["validation"]["gaps"].append(corrections)
    
    return result


def activate_next_workflow_variant_or_finish(slots: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """
    Legacy function for backward compatibility - now just returns all_variants_done.
    
    Since we only support single workflows, this always signals completion.
    
    Returns (updated_slots, action_result_code)
    """
    return slots.copy(), "all_variants_done"


def normalize_and_expand_decision_rules(slots: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize decisions into structured rule candidates.
    """
    # Stub implementation
    result = slots.copy()
    raw_rules = result.get("process_parameters", {}).get("decision_rules", [])
    
    if isinstance(raw_rules, str):
        # Parse from string
        raw_rules = [r.strip() for r in raw_rules.split("\n") if r.strip()]
    
    normalized = []
    for i, rule_text in enumerate(raw_rules):
        if isinstance(rule_text, dict):
            normalized.append(rule_text)
        else:
            normalized.append({
                "rule_id": f"rule_{i+1}",
                "decision_point": rule_text,
                "rule_statement": None,
                "who_decides": [],
                "inputs_needed": [],
                "examples": []
            })
    
    result.setdefault("process_parameters", {})["decision_rules"] = normalized
    return result


def derive_candidate_data_elements_from_workflows_and_artifacts(slots: dict[str, Any]) -> dict[str, Any]:
    """
    Extract candidate data elements from workflows and artifacts.
    """
    # Stub implementation
    result = slots.copy()
    
    candidates = []
    
    # Extract from workflow steps
    for wf in result.get("workflows", {}).get("maps", []):
        for step in wf.get("steps", []):
            for inp in step.get("inputs", []):
                if isinstance(inp, str) and inp:
                    candidates.append({
                        "data_id": f"de_{len(candidates)+1}",
                        "name": inp,
                        "definition": None,
                        "example_value": None,
                        "kind": None,
                        "required_when": None,
                        "source_today": None,
                        "owner_role": step.get("owner_role"),
                        "validation_rules_today": [],
                        "privacy_sensitivity": None
                    })
    
    # Deduplicate by name
    seen = set()
    unique = []
    for c in candidates:
        name = c.get("name", "").lower()
        if name not in seen:
            seen.add(name)
            unique.append(c)
    
    result.setdefault("process_parameters", {})["data_elements"] = unique[:20]  # Limit to 20
    return result


def select_next_data_element_for_validation(slots: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """
    Select next unvalidated data element and set current pointer.
    
    Returns (updated_slots, action_result_code)
    - "element_selected" if there's an unvalidated element
    - "all_validated" if all elements are validated
    """
    # Stub implementation
    result = slots.copy()
    elements = result.get("process_parameters", {}).get("data_elements", [])
    
    for i, elem in enumerate(elements):
        # Check if element needs validation (definition is None or validated flag is not True)
        if not elem.get("validated", False) or elem.get("definition") is None:
            result.setdefault("process_parameters", {})["current_data_element_index"] = i
            return result, "element_selected"
    
    # All validated
    result.setdefault("process_parameters", {})["current_data_element_index"] = None
    return result, "all_validated"


def commit_validated_data_element(slots: dict[str, Any]) -> dict[str, Any]:
    """
    Mark current data element as validated.
    """
    # Stub implementation
    result = slots.copy()
    idx = result.get("process_parameters", {}).get("current_data_element_index")
    
    if idx is not None:
        elements = result.get("process_parameters", {}).get("data_elements", [])
        if 0 <= idx < len(elements):
            elements[idx]["validated"] = True
    
    return result


def detect_gaps_and_contradictions(slots: dict[str, Any]) -> dict[str, Any]:
    """
    Detect missing essentials and contradictions in captured data.
    """
    # Stub implementation
    result = slots.copy()
    
    gaps = []
    contradictions = []
    
    # Check for missing end_condition
    for wf in result.get("workflows", {}).get("maps", []):
        if not wf.get("end_condition"):
            gaps.append(f"Workflow '{wf.get('workflow_name')}' missing end_condition")
    
    # Check SLA contradiction
    if result.get("reality_checks", {}).get("service_levels", {}).get("slas_exist"):
        if not result.get("reality_checks", {}).get("service_levels", {}).get("sla_definitions"):
            contradictions.append("SLAs exist but no definitions provided")
    
    result.setdefault("validation", {})["gaps"] = gaps
    result.setdefault("validation", {})["contradictions"] = contradictions
    
    return result


def score_automation_and_select_digitization_candidates(slots: dict[str, Any]) -> dict[str, Any]:
    """
    Score workflows for automation fit and select digitization candidates.
    """
    # Stub implementation
    result = slots.copy()
    
    result.setdefault("automation_fit", {}).setdefault("digitization_candidates", {})["workflows_to_digitize"] = []
    result["automation_fit"]["digitization_candidates"]["highest_value_steps"] = []
    result["automation_fit"]["digitization_candidates"]["automation_opportunities"] = []
    
    return result


def generate_recommended_next_step(slots: dict[str, Any]) -> dict[str, Any]:
    """
    Generate recommended next step for automation journey.
    """
    # Stub implementation
    result = slots.copy()
    
    candidate = result.get("automation_fit", {}).get("candidate_for_app")
    
    if candidate:
        result.setdefault("automation_fit", {})["recommended_next_step"] = "proceed_to_app_requirements_flow"
    else:
        result.setdefault("automation_fit", {})["recommended_next_step"] = "improve_process_first"
    
    return result


# Import output generation
try:
    from src.actions.output_generation import generate_human_and_ai_outputs as _gen_outputs
except ImportError:
    _gen_outputs = None


# Action registry for dynamic lookup
ACTIONS = {
    "initialize_workflow_maps_from_selection": initialize_workflow_maps_from_selection,
    "write_trigger_to_active_workflow": write_trigger_to_active_workflow,
    "parse_enumerated_steps_into_skeleton": parse_enumerated_steps_into_skeleton,
    "normalize_and_parse_decision_data": normalize_and_parse_decision_data,
    "check_step_has_decision": check_step_has_decision,
    "update_live_bpmn_artifact": update_live_bpmn_artifact,
    "commit_step_to_active_workflow": commit_step_to_active_workflow,
    "advance_to_next_step_or_finish": advance_to_next_step_or_finish,
    "check_if_user_said_done": check_if_user_said_done,
    "copy_next_step_to_buffer": copy_next_step_to_buffer,
    "advance_or_close_workflow_based_on_response": advance_or_close_workflow_based_on_response,
    "apply_workflow_corrections": apply_workflow_corrections,
    "activate_next_workflow_variant_or_finish": activate_next_workflow_variant_or_finish,
    "normalize_and_expand_decision_rules": normalize_and_expand_decision_rules,
    "derive_candidate_data_elements_from_workflows_and_artifacts": derive_candidate_data_elements_from_workflows_and_artifacts,
    "select_next_data_element_for_validation": select_next_data_element_for_validation,
    "commit_validated_data_element": commit_validated_data_element,
    "detect_gaps_and_contradictions": detect_gaps_and_contradictions,
    "score_automation_and_select_digitization_candidates": score_automation_and_select_digitization_candidates,
    "generate_recommended_next_step": generate_recommended_next_step,
}

if _gen_outputs:
    ACTIONS["generate_human_and_ai_outputs"] = _gen_outputs


def execute_action(action_name: str, slots: dict[str, Any], **kwargs) -> tuple[dict[str, Any], str]:
    """
    Execute an action by name.
    
    Args:
        action_name: Name of action function
        slots: Current slots
        **kwargs: Additional arguments for action (e.g., user_response)
        
    Returns:
        (updated_slots, action_result_code)
    """
    import inspect
    
    action_fn = ACTIONS.get(action_name)
    
    if not action_fn:
        raise ValueError(f"Unknown action: {action_name}")
    
    # Inspect function signature to filter kwargs
    sig = inspect.signature(action_fn)
    accepted_params = set(sig.parameters.keys()) - {'slots'}  # Exclude 'slots'
    
    # If user_response is provided and the function has a non-slots parameter,
    # try to map user_response to that parameter name
    if 'user_response' in kwargs and 'user_response' not in accepted_params:
        user_response_value = kwargs.pop('user_response')
        
        # Find the first non-slots parameter that isn't already in kwargs
        for param_name in sig.parameters.keys():
            if param_name != 'slots' and param_name not in kwargs:
                # Map user_response to this parameter
                kwargs[param_name] = user_response_value
                break
    
    # Filter kwargs to only those accepted by the function
    filtered_kwargs = {k: v for k, v in kwargs.items() if k in accepted_params}
    
    # Some actions return (slots, result_code), others just slots
    result = action_fn(slots, **filtered_kwargs) if filtered_kwargs else action_fn(slots)
    
    if isinstance(result, tuple):
        return result
    else:
        return result, "success"
