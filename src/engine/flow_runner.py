"""
Flow runner engine: loads flows, advances stages, renders templates, writes to slots.

Follows .cursor/langgraph-core.mdc:
- Pure functions where possible
- Clear error handling
- No LLM calls in this module (deterministic only)
"""

import json
import re
from pathlib import Path
from typing import Any, Optional


class FlowRunnerError(Exception):
    """Base exception for flow runner errors."""
    pass


class FlowLoader:
    """Load and cache flow definitions from JSON files."""
    
    def __init__(self, flows_dir: str = "flows"):
        self.flows_dir = Path(flows_dir)
        self._cache: dict[str, dict] = {}
    
    def load_flow(self, flow_id: str) -> dict[str, Any]:
        """
        Load a flow definition by ID.
        
        Args:
            flow_id: Flow identifier (e.g., "intake_sipoc_v1")
            
        Returns:
            Flow definition dict
            
        Raises:
            FlowRunnerError: If flow not found or invalid JSON
        """
        if flow_id in self._cache:
            return self._cache[flow_id]
        
        # Try direct file mapping
        flow_files = {
            "intake_sipoc_v1": "Flow_A_intake_sipoc_v1.json",
            "current_state_mapping_v1": "Flow_B_current_state_mapping_v1.json",
            "outputs_v1": "Flow_C_outputs_v1.json",
            "current_state_discovery_complete_v1": "composed_master_flow.json"
        }
        
        filename = flow_files.get(flow_id)
        if not filename:
            raise FlowRunnerError(f"Unknown flow_id: {flow_id}")
        
        flow_path = self.flows_dir / filename
        if not flow_path.exists():
            raise FlowRunnerError(f"Flow file not found: {flow_path}")
        
        try:
            with open(flow_path, "r", encoding="utf-8") as f:
                flow_def = json.load(f)
            self._cache[flow_id] = flow_def
            return flow_def
        except json.JSONDecodeError as e:
            raise FlowRunnerError(f"Invalid JSON in {flow_path}: {e}")
    
    def get_stage(self, flow_id: str, stage_id: str) -> dict[str, Any]:
        """
        Get a specific stage from a flow.
        
        Args:
            flow_id: Flow identifier
            stage_id: Stage identifier
            
        Returns:
            Stage definition dict
            
        Raises:
            FlowRunnerError: If stage not found
        """
        flow = self.load_flow(flow_id)
        stages = flow.get("stages", [])
        
        for stage in stages:
            if stage.get("id") == stage_id:
                return stage
        
        raise FlowRunnerError(f"Stage '{stage_id}' not found in flow '{flow_id}'")
    
    def get_initial_slots(self, flow_id: str) -> dict[str, Any]:
        """
        Get the initial slots template from a flow's context.
        
        Args:
            flow_id: Flow identifier
            
        Returns:
            Initial slots dict (deep copy of context.slots)
        """
        flow = self.load_flow(flow_id)
        context = flow.get("context", {})
        slots = context.get("slots", {})
        
        # Deep copy to avoid mutation
        import copy
        return copy.deepcopy(slots)


class TemplateRenderer:
    """Render Jinja2-style templates with slot data."""
    
    @staticmethod
    def render(template: str, slots: dict[str, Any]) -> str:
        """
        Render a template string with slot values.
        
        Supports:
        - {{slot.path.to.value}}
        - Basic array access: {{workflows.maps[0].trigger}}
        
        Args:
            template: Template string
            slots: Slot data
            
        Returns:
            Rendered string
        """
        if not template:
            return ""
        
        # Find all {{...}} patterns
        pattern = r'\{\{([^}]+)\}\}'
        
        def replacer(match):
            path = match.group(1).strip()
            value = TemplateRenderer._get_nested_value(slots, path)
            if value is None:
                return f"[{path}]"  # Placeholder for missing values
            if isinstance(value, (list, dict)):
                return json.dumps(value)
            return str(value)
        
        return re.sub(pattern, replacer, template)
    
    @staticmethod
    def _get_nested_value(data: dict, path: str) -> Any:
        """
        Get nested value from data using dot notation.
        
        Supports:
        - engagement.process_name
        - workflows.maps[0].trigger
        - process_parameters.data_elements[current].name (dynamic index lookup)
        
        Args:
            data: Data dict
            path: Dot-notation path
            
        Returns:
            Value at path or None if not found
        """
        parts = path.split(".")
        current = data
        
        for part in parts:
            if current is None:
                return None
            
            # Handle array indexing: maps[0] or data_elements[current]
            if "[" in part and "]" in part:
                key, idx_str = part.split("[")
                idx_str = idx_str.rstrip("]")
                
                # Handle dynamic index lookup like [current]
                if idx_str == "current":
                    # Look for {key}_current_index or current_{key}_index
                    # Common patterns: current_data_element_index, current_workflow_index
                    idx = None
                    
                    # Try to find the current index in the parent context
                    if isinstance(current, dict):
                        # Try pattern: current_{key}_index
                        idx_key = f"current_{key.rstrip('s')}_index"
                        if idx_key in current:
                            idx = current.get(idx_key)
                        # Try pattern: {key}_current_index  
                        elif f"{key}_current_index" in current:
                            idx = current.get(f"{key}_current_index")
                    
                    if idx is None:
                        return None
                else:
                    # Numeric index
                    try:
                        idx = int(idx_str)
                    except ValueError:
                        return None
                
                if isinstance(current, dict):
                    current = current.get(key)
                
                if isinstance(current, list) and isinstance(idx, int) and 0 <= idx < len(current):
                    current = current[idx]
                else:
                    return None
            else:
                if isinstance(current, dict):
                    current = current.get(part)
                else:
                    return None
        
        return current


class SlotWriter:
    """Write values to slots using save_to paths."""
    
    @staticmethod
    def write(slots: dict[str, Any], save_to: str, value: Any) -> dict[str, Any]:
        """
        Write a value to a slot path.
        
        Supports:
        - engagement.process_name
        - workflows.maps[0].trigger
        - workflows.selected_workflows (append to list)
        - process_parameters.data_elements[current].name (dynamic index)
        
        Args:
            slots: Existing slots
            save_to: Dot-notation path
            value: Value to write
            
        Returns:
            Updated slots (mutates in place but also returns for clarity)
        """
        if not save_to:
            return slots
        
        parts = save_to.split(".")
        current = slots
        
        # Helper to resolve index
        def resolve_index(idx_str: str, key: str, context: dict) -> int:
            """Resolve an index string to an integer."""
            if idx_str == "current":
                # Look for current index in context
                idx_key = f"current_{key.rstrip('s')}_index"
                if idx_key in context:
                    return context[idx_key]
                idx_key2 = f"{key}_current_index"
                if idx_key2 in context:
                    return context[idx_key2]
                raise ValueError(f"Cannot resolve [current] for {key} - no index found")
            return int(idx_str)
        
        # Navigate to parent
        for i, part in enumerate(parts[:-1]):
            # Handle array indexing
            if "[" in part and "]" in part:
                key, idx_str = part.split("[")
                idx_str = idx_str.rstrip("]")
                
                try:
                    idx = resolve_index(idx_str, key, current)
                except ValueError:
                    # Can't resolve, skip
                    return slots
                
                if key not in current:
                    current[key] = []
                
                # Extend list if needed
                while len(current[key]) <= idx:
                    current[key].append({})
                
                current = current[key][idx]
            else:
                if part not in current:
                    # Decide if next part is array or dict
                    next_part = parts[i + 1] if i + 1 < len(parts) else None
                    if next_part and "[" in next_part:
                        current[part] = []
                    else:
                        current[part] = {}
                
                current = current[part]
        
        # Write final value
        final_key = parts[-1]
        
        # Handle array indexing in final key
        if "[" in final_key and "]" in final_key:
            key, idx_str = final_key.split("[")
            idx_str = idx_str.rstrip("]")
            
            try:
                idx = resolve_index(idx_str, key, current)
            except ValueError:
                # Can't resolve, skip
                return slots
            
            if key not in current:
                current[key] = []
            
            while len(current[key]) <= idx:
                current[key].append(None)
            
            current[key][idx] = value
        else:
            # If target is a list, append; otherwise set
            if final_key in current and isinstance(current[final_key], list) and not isinstance(value, list):
                current[final_key].append(value)
            else:
                current[final_key] = value
        
        return slots


class StageAdvancer:
    """Determine next stage based on stage type and conditions."""

    @staticmethod
    def _parse_yes_no(user_response: str) -> Optional[bool]:
        """
        Best-effort parsing of yes/no style confirmation responses.

        Returns:
            True for yes, False for no, None if unclear/ambiguous.
        """
        if not user_response:
            return None

        raw = user_response.strip().lower()
        # Normalize punctuation/whitespace while keeping words.
        cleaned = re.sub(r"[^a-z0-9]+", " ", raw).strip()
        if not cleaned:
            return None

        tokens = cleaned.split()
        token_set = set(tokens)

        yes_tokens = {
            "yes", "y", "yeah", "yep", "yup", "sure", "ok", "okay",
            "k", "great", "good", "fine", "alright", "right",
            "correct", "true", "accurate", "affirmative", "confirmed",
            "generally", "mostly",
        }
        no_tokens = {
            "no", "n", "nope", "nah", "negative", "incorrect", "false",
        }

        # Direct first-token signal is strongest.
        if tokens[0] in yes_tokens:
            return True
        if tokens[0] in no_tokens:
            return False

        # Common "soft yes" openers.
        if len(tokens) >= 2 and tokens[0] == "i" and tokens[1] in {"guess", "think"}:
            # e.g. "I guess generally", "I think so"
            return True
        if tokens[0] == "sounds" and "good" in token_set:
            return True
        if tokens[0] == "looks" and "good" in token_set:
            return True

        # Common negation patterns.
        if "not" in token_set and ("accurate" in token_set or "correct" in token_set or "true" in token_set):
            return False

        yes_hits = bool(token_set & yes_tokens)
        no_hits = bool(token_set & no_tokens)
        if yes_hits and not no_hits:
            return True
        if no_hits and not yes_hits:
            return False

        return None
    
    @staticmethod
    def get_next_stage(
        stage: dict[str, Any],
        slots: dict[str, Any],
        user_response: Optional[str] = None
    ) -> str:
        """
        Determine the next stage ID.
        
        Args:
            stage: Current stage definition
            slots: Current slots
            user_response: User's answer (if applicable)
            
        Returns:
            Next stage ID
            
        Raises:
            FlowRunnerError: If no valid next stage
        """
        stage_type = stage.get("type")
        
        if stage_type in ("message", "questions", "action", "output"):
            next_stage = stage.get("next")
            if not next_stage:
                raise FlowRunnerError(f"Stage {stage.get('id')} missing 'next' field")
            return next_stage
        
        elif stage_type == "confirm":
            parsed = StageAdvancer._parse_yes_no(user_response or "")
            if parsed is True:
                return stage.get("on_yes", "end")
            if parsed is False:
                return stage.get("on_no", "end")

            # Unclear response: keep user on the same confirm stage rather than defaulting to "no".
            # This avoids accidental loops when users type e.g. "Yes." or "Yes - looks right".
            return stage.get("id", "end")
        
        elif stage_type == "gate":
            passed = StageAdvancer._check_gate_criteria(stage.get("criteria", []), slots)
            if passed:
                return stage.get("on_pass", "end")
            else:
                return stage.get("on_fail", "end")
        
        elif stage_type == "branch":
            # Branch logic handled by action results (see actions module)
            # For now, take first branch's next
            branches = stage.get("branches", [])
            if branches:
                return branches[0].get("next", "end")
            return "end"
        
        elif stage_type == "loop":
            # Loop continues until stop_condition met
            # For now, advance to next (loop driver will handle re-entry)
            return stage.get("next", "end")
        
        return "end"
    
    @staticmethod
    def _check_gate_criteria(criteria: list[dict], slots: dict[str, Any]) -> bool:
        """
        Check if gate criteria are met.
        
        Args:
            criteria: List of criterion dicts
            slots: Current slots
            
        Returns:
            True if all criteria pass
        """
        for criterion in criteria:
            slot_path = criterion.get("slot")
            required = criterion.get("required", True)
            min_items = criterion.get("min_items")
            max_items = criterion.get("max_items")
            
            value = TemplateRenderer._get_nested_value(slots, slot_path)
            
            if required and value is None:
                return False
            
            if min_items is not None:
                if not isinstance(value, list) or len(value) < min_items:
                    return False
            
            if max_items is not None:
                if isinstance(value, list) and len(value) > max_items:
                    return False
        
        return True
