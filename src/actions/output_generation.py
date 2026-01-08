"""
LLM-driven output generation: Mermaid diagrams and markdown summaries.

Follows .cursor/langgraph-error-handling.mdc:
- Retry with exponential backoff
- Validation and error recovery
- Structured prompts
"""

import json
import re
from typing import Any, Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage


class OutputGenerationError(Exception):
    """Error during output generation."""
    pass


class MermaidValidator:
    """Basic Mermaid syntax validation."""
    
    @staticmethod
    def validate_sipoc(mermaid: str) -> tuple[bool, Optional[str]]:
        """
        Validate Mermaid SIPOC diagram.
        
        Returns:
            (is_valid, error_message)
        """
        if not mermaid or not mermaid.strip():
            return False, "Empty Mermaid diagram"
        
        # Check for graph declaration
        if "graph" not in mermaid.lower():
            return False, "Missing 'graph' declaration"
        
        # Check for basic SIPOC components
        required = ["supplier", "input", "process", "output", "customer"]
        missing = [comp for comp in required if comp.lower() not in mermaid.lower()]
        
        if missing:
            return False, f"Missing SIPOC components: {', '.join(missing)}"
        
        return True, None
    
    @staticmethod
    def validate_swimlane(mermaid: str) -> tuple[bool, Optional[str]]:
        """
        Validate Mermaid swimlane diagram.
        
        Returns:
            (is_valid, error_message)
        """
        if not mermaid or not mermaid.strip():
            return False, "Empty Mermaid diagram"
        
        # Check for graph or flowchart
        if not any(keyword in mermaid.lower() for keyword in ["graph", "flowchart"]):
            return False, "Missing 'graph' or 'flowchart' declaration"
        
        # Check for subgraph (lanes)
        if "subgraph" not in mermaid.lower():
            return False, "Missing 'subgraph' for swimlanes"
        
        return True, None


def generate_sipoc_mermaid(slots: dict[str, Any], llm: Optional[ChatOpenAI] = None) -> str:
    """
    Generate Mermaid SIPOC diagram from captured data.
    
    Args:
        slots: Interview data slots
        llm: OpenAI chat model (optional, will create if not provided)
        
    Returns:
        Mermaid diagram string
        
    Raises:
        OutputGenerationError: If generation fails after retries
    """
    if llm is None:
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.3)
    
    sipoc = slots.get("sipoc", {})
    
    system_prompt = """You are an expert at generating Mermaid diagrams for process documentation.

Generate a Mermaid SIPOC diagram (Suppliers, Inputs, Process, Outputs, Customers) in graph format.

Requirements:
- Use 'graph LR' for left-to-right flow
- Create clear nodes for each component
- Use descriptive labels
- Connect components logically
- Keep it readable and professional

Return ONLY the Mermaid code, no explanations."""
    
    user_prompt = f"""Generate a Mermaid SIPOC diagram from this data:

Suppliers: {json.dumps(sipoc.get('suppliers', []))}
Inputs: {json.dumps(sipoc.get('inputs', []))}
Process Steps: {json.dumps(sipoc.get('process_high_level_steps', []))}
Outputs: {json.dumps(sipoc.get('outputs', []))}
Customers: {json.dumps(sipoc.get('customers', []))}

Generate the Mermaid code now."""
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = llm.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ])
            
            mermaid = response.content.strip()
            
            # Extract mermaid code if wrapped in ```
            if "```mermaid" in mermaid:
                mermaid = re.search(r"```mermaid\n(.*?)```", mermaid, re.DOTALL)
                if mermaid:
                    mermaid = mermaid.group(1).strip()
            elif "```" in mermaid:
                mermaid = re.search(r"```\n(.*?)```", mermaid, re.DOTALL)
                if mermaid:
                    mermaid = mermaid.group(1).strip()
            
            # Validate
            is_valid, error = MermaidValidator.validate_sipoc(mermaid)
            if is_valid:
                return mermaid
            else:
                if attempt < max_retries - 1:
                    user_prompt += f"\n\nPrevious attempt had error: {error}. Please fix and regenerate."
                    continue
                else:
                    raise OutputGenerationError(f"SIPOC validation failed: {error}")
        
        except Exception as e:
            if attempt == max_retries - 1:
                raise OutputGenerationError(f"Failed to generate SIPOC after {max_retries} attempts: {e}")
    
    raise OutputGenerationError("Failed to generate valid SIPOC diagram")


def generate_swimlane_mermaid(slots: dict[str, Any], llm: Optional[ChatOpenAI] = None) -> str:
    """
    Generate Mermaid swimlane diagram from workflow data.
    
    Args:
        slots: Interview data slots
        llm: OpenAI chat model (optional, will create if not provided)
        
    Returns:
        Mermaid diagram string
        
    Raises:
        OutputGenerationError: If generation fails after retries
    """
    if llm is None:
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.3)
    
    workflows = slots.get("workflows", {}).get("maps", [])
    
    if not workflows:
        return "graph TD\n    A[No workflows captured yet]"
    
    # Use first workflow for now
    workflow = workflows[0]
    
    system_prompt = """You are an expert at generating Mermaid swimlane diagrams for process workflows.

Generate a Mermaid flowchart with subgraphs for swimlanes (roles/lanes).

Requirements:
- Use 'flowchart TD' for top-down flow
- Create subgraphs for each role/lane
- Show decision points with diamond shapes
- Include wait states and exceptions
- Use clear, descriptive labels
- Connect steps logically

Return ONLY the Mermaid code, no explanations."""
    
    user_prompt = f"""Generate a Mermaid swimlane diagram from this workflow:

Workflow: {workflow.get('workflow_name', 'Unnamed')}
Trigger: {workflow.get('trigger', 'N/A')}
Lanes (roles): {json.dumps(workflow.get('lanes', []))}
Steps: {json.dumps(workflow.get('steps', []), indent=2)}
Decisions: {json.dumps(workflow.get('decisions', []))}
Exceptions: {json.dumps(workflow.get('exceptions', []))}

Generate the Mermaid code now."""
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = llm.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ])
            
            mermaid = response.content.strip()
            
            # Extract mermaid code if wrapped in ```
            if "```mermaid" in mermaid:
                mermaid = re.search(r"```mermaid\n(.*?)```", mermaid, re.DOTALL)
                if mermaid:
                    mermaid = mermaid.group(1).strip()
            elif "```" in mermaid:
                mermaid = re.search(r"```\n(.*?)```", mermaid, re.DOTALL)
                if mermaid:
                    mermaid = mermaid.group(1).strip()
            
            # Validate
            is_valid, error = MermaidValidator.validate_swimlane(mermaid)
            if is_valid:
                return mermaid
            else:
                if attempt < max_retries - 1:
                    user_prompt += f"\n\nPrevious attempt had error: {error}. Please fix and regenerate."
                    continue
                else:
                    raise OutputGenerationError(f"Swimlane validation failed: {error}")
        
        except Exception as e:
            if attempt == max_retries - 1:
                raise OutputGenerationError(f"Failed to generate swimlane after {max_retries} attempts: {e}")
    
    raise OutputGenerationError("Failed to generate valid swimlane diagram")


def generate_markdown_summary(slots: dict[str, Any], llm: Optional[ChatOpenAI] = None) -> str:
    """
    Generate markdown summary of current state.
    
    Args:
        slots: Interview data slots
        llm: OpenAI chat model (optional, will create if not provided)
        
    Returns:
        Markdown summary string
        
    Raises:
        OutputGenerationError: If generation fails after retries
    """
    if llm is None:
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.3)
    
    system_prompt = """You are an expert business analyst creating current-state process documentation.

Generate a clear, professional markdown summary that:
- Uses proper markdown formatting
- Includes sections for: Overview, Scope, SIPOC, Workflow Details, Key Observations, Pain Points
- Is factual and based only on the captured data
- Uses business-friendly language
- Highlights important insights

Return ONLY the markdown, no preamble."""
    
    user_prompt = f"""Generate a current-state process summary from this captured data:

{json.dumps(slots, indent=2)}

Generate the markdown summary now."""
    
    max_retries = 2
    for attempt in range(max_retries):
        try:
            response = llm.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ])
            
            markdown = response.content.strip()
            
            # Basic validation
            if len(markdown) < 100:
                raise OutputGenerationError("Summary too short")
            
            if "# " not in markdown and "## " not in markdown:
                raise OutputGenerationError("Missing markdown headers")
            
            return markdown
        
        except Exception as e:
            if attempt == max_retries - 1:
                raise OutputGenerationError(f"Failed to generate summary after {max_retries} attempts: {e}")
    
    raise OutputGenerationError("Failed to generate markdown summary")


def generate_human_and_ai_outputs(slots: dict[str, Any], **kwargs) -> dict[str, Any]:
    """
    Generate all outputs: SIPOC mermaid, swimlane mermaid, and markdown summary.
    
    This is called as an action from the flow.
    
    Args:
        slots: Interview data slots
        **kwargs: Additional args (unused)
        
    Returns:
        Updated slots with outputs populated
    """
    try:
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.3)
        
        # Generate outputs
        sipoc_mermaid = generate_sipoc_mermaid(slots, llm)
        swimlane_mermaid = generate_swimlane_mermaid(slots, llm)
        markdown_summary = generate_markdown_summary(slots, llm)
        
        # Update slots
        result = slots.copy()
        result.setdefault("outputs", {}).setdefault("human_readable", {})
        result["outputs"]["human_readable"]["sipoc_mermaid"] = sipoc_mermaid
        result["outputs"]["human_readable"]["swimlane_mermaid"] = swimlane_mermaid
        result["outputs"]["human_readable"]["current_state_summary_markdown"] = markdown_summary
        
        # Also store AI handoff (just copy the full model for now)
        result["outputs"].setdefault("ai_handoff", {})
        result["outputs"]["ai_handoff"]["process_model"] = result.copy()
        
        return result
    
    except Exception as e:
        raise OutputGenerationError(f"Output generation failed: {e}")
