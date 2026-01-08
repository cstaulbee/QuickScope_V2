"""
QuickScope Flow B Quick-Start
==============================
Skip SIPOC intake and go straight to detailed step-by-step workflow mapping
with live diagram generation.

Usage:
    python quickstart_flow_b.py                    # Interactive mode
    python quickstart_flow_b.py --simulate         # LLM persona mode
    python quickstart_flow_b.py --simulate --persona 1031_exchange_ops

Features:
    - Minimal setup (2 questions)
    - Live BPMN-lite diagram generation
    - Progressive disclosure for step details
    - Automatic clarification follow-ups
    - LLM-as-user simulation for testing
"""

from __future__ import annotations

import argparse
import sys
from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage

from src.graphs.interview_graph import create_interview_graph
from src.state.interview_state import create_initial_state
from src.simulations.simulated_user import SimulatedUser


def run_interactive(graph, state, config):
    """Run in interactive mode (human user)."""
    print("Starting interview... (type 'quit' or 'exit' to stop)")
    print()
    
    while True:
        # Invoke graph with current state
        result = graph.invoke(state, config)
        
        # Get last message
        messages = result.get("messages", [])
        if messages:
            last_msg = messages[-1]
            if isinstance(last_msg, AIMessage):
                print(f"Bot: {last_msg.content}")
                print()
        
        # Check if we're done
        if result.get("active_stage_id") == "end":
            print("=" * 60)
            print("Interview complete! Check artifacts/ folder for diagrams.")
            break
        
        # Check for error
        if result.get("error"):
            print(f"Error: {result.get('error')}")
            break
        
        # Get user input
        user_input = input("You: ").strip()
        print()
        
        if user_input.lower() in ("quit", "exit", "q"):
            print("Exiting interview.")
            break
        
        if not user_input:
            print("Please enter a response.")
            print()
            continue
        
        # Add user message and update state
        result["messages"].append(HumanMessage(content=user_input))
        state = result


def run_simulated(graph, state, config, persona_id, model, temperature, max_turns):
    """Run in simulated mode (LLM persona)."""
    sim = SimulatedUser(persona_id=persona_id, model=model, temperature=temperature)
    
    print(f"Starting SIMULATED interview with persona: {persona_id}")
    print(f"Model: {model}, Temperature: {temperature}, Max turns: {max_turns}")
    print("=" * 60)
    print()
    
    turns = 0
    
    def safe_print(text):
        """Print text, handling Unicode encoding errors."""
        try:
            print(text)
        except UnicodeEncodeError:
            # Replace problematic characters with ASCII equivalents
            print(text.encode('ascii', errors='replace').decode('ascii'))
    
    while turns < max_turns:
        # Invoke graph
        result = graph.invoke(state, config)
        
        # Get last message
        messages = result.get("messages", [])
        if messages:
            last_msg = messages[-1]
            if isinstance(last_msg, AIMessage):
                safe_print(f"Bot: {last_msg.content}")
                print()
        
        # Check if done
        if result.get("active_stage_id") == "end":
            print("=" * 60)
            print(f"Interview complete! Turns: {turns}")
            print("Check artifacts/ folder for diagrams.")
            break
        
        # Check for error
        if result.get("error"):
            safe_print(f"Error: {result.get('error')}")
            break
        
        # Get simulated user response
        pending = result.get("pending", {})
        if pending and pending.get("ask"):
            bot_prompt = pending["ask"]
        else:
            bot_prompt = "Continue"
        
        sim_response = sim.respond(bot_prompt, result)
        safe_print(f"User ({persona_id}): {sim_response}")
        print()
        
        # Add simulated response
        result["messages"].append(HumanMessage(content=sim_response))
        state = result
        turns += 1


def main():
    """Run Flow B quick-start interview."""
    load_dotenv()
    
    parser = argparse.ArgumentParser(
        description="QuickScope Flow B Quick-Start - Skip SIPOC, start mapping"
    )
    parser.add_argument(
        "--simulate",
        action="store_true",
        help="Run with LLM persona instead of human input"
    )
    parser.add_argument(
        "--persona",
        default="1031_exchange_ops",
        help="Persona ID for simulation (default: 1031_exchange_ops)"
    )
    parser.add_argument(
        "--model",
        default="gpt-4o-mini",
        help="OpenAI model for simulated user (default: gpt-4o-mini)"
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.7,
        help="Temperature for simulated user (default: 0.7)"
    )
    parser.add_argument(
        "--max-turns",
        type=int,
        default=200,
        help="Max turns for simulation (default: 200)"
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("  QuickScope Flow B: Process Mapping (Skip SIPOC)")
    print("=" * 60)
    print()
    print("This will map your process step-by-step with:")
    print("  * Live BPMN diagram generation (artifacts/live_bpmn_*.mmd)")
    print("  * Decision outcomes capture")
    print("  * Automatic clarification follow-ups")
    print()
    
    # Minimal intake (skip if simulating)
    if args.simulate:
        # Use default values for simulation
        process_name = "Business Process"
    else:
        process_name = input("Process name (e.g., 'Order Fulfillment'): ").strip()
        if not process_name:
            process_name = "Business Process"
    
    print()
    print("OK, we'll map the process: {0}".format(process_name))
    print()
    print("=" * 60)
    print()
    
    # Create initial state for Flow B
    state = create_initial_state(flow_id="current_state_mapping_v1")
    
    # Pre-populate slots to skip Flow A
    state["slots"] = {
        "engagement": {
            "process_name": process_name,
            "organization_type": "Unknown",
            "intended_audience": "Process improvement team"
        },
        "workflows": {
            "selected_workflows": [process_name]  # Single workflow
        }
    }
    
    # Start at the workflow selection stage
    state["active_stage_id"] = "workflow_selection"
    state["messages"] = []
    
    # Create graph
    graph = create_interview_graph()
    config = {"configurable": {"thread_id": "quickstart_flow_b"}}
    
    # Run in appropriate mode
    if args.simulate:
        run_simulated(
            graph, state, config,
            persona_id=args.persona,
            model=args.model,
            temperature=args.temperature,
            max_turns=args.max_turns
        )
    else:
        run_interactive(graph, state, config)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted. Goodbye!")
        sys.exit(0)
    except Exception as e:
        print(f"\n\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
