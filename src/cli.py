"""
Simple CLI runner for the QuickScope interview bot.

Runs the LangGraph interview graph in a terminal (stdin/stdout), without LangSmith.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src.graphs.interview_graph import create_interview_graph
from src.state.interview_state import InterviewState, create_initial_state
from src.simulations.simulated_user import SimulatedUser


def _message_to_dict(msg: Any) -> dict[str, Any]:
    msg_type = getattr(msg, "type", None)
    content = getattr(msg, "content", None)
    return {"type": msg_type, "content": content}


def _dict_to_message(d: dict[str, Any]) -> Any:
    t = d.get("type")
    c = d.get("content", "")
    if t in ("human", "user"):
        return HumanMessage(content=c)
    if t in ("ai", "assistant"):
        return AIMessage(content=c)
    if t == "system":
        return SystemMessage(content=c)
    # Unknown message type; keep as a system message so we don't crash
    return SystemMessage(content=f"[{t}] {c}")


def _load_state(path: Path) -> InterviewState:
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw_messages = raw.get("messages", [])
    raw["messages"] = [_dict_to_message(m) for m in raw_messages]
    raw.setdefault("events", [])
    # best-effort typing: return as InterviewState-shaped dict
    return raw  # type: ignore[return-value]


def _save_state(path: Path, state: InterviewState) -> None:
    serializable = dict(state)
    serializable["messages"] = [_message_to_dict(m) for m in state.get("messages", [])]
    path.write_text(json.dumps(serializable, indent=2), encoding="utf-8")


def _print_new_ai_messages(state: InterviewState, printed_upto: int) -> int:
    messages = state.get("messages", [])
    for msg in messages[printed_upto:]:
        if isinstance(msg, AIMessage):
            print()
            print(msg.content)
            print()
    return len(messages)


def _print_new_events(state: InterviewState, printed_upto: int) -> int:
    events = state.get("events", []) or []
    for evt in events[printed_upto:]:
        kind = evt.get("kind", "event")
        # Keep watch output short; include most useful fields.
        stage_id = evt.get("stage_id")
        stage_type = evt.get("stage_type")
        action = evt.get("action")
        next_stage = evt.get("next_stage_id")
        parts = [f"kind={kind}"]
        if stage_id is not None:
            parts.append(f"stage={stage_id}")
        if stage_type is not None:
            parts.append(f"type={stage_type}")
        if action is not None:
            parts.append(f"action={action}")
        if next_stage is not None:
            parts.append(f"next={next_stage}")
        print("[TRACE] " + " ".join(parts))
    return len(events)


def _run_interactive(graph, state: InterviewState, *, watch: bool, state_file: Path | None) -> int:
    printed_msgs_upto = 0
    printed_evts_upto = 0

    # Main loop: invoke once to get bot prompt, then read user input, repeat.
    while True:
        state = graph.invoke(state)  # type: ignore[assignment]

        if watch:
            printed_evts_upto = _print_new_events(state, printed_evts_upto)
        printed_msgs_upto = _print_new_ai_messages(state, printed_msgs_upto)

        if state.get("error"):
            print(f"ERROR: {state['error']}")
            break

        if state.get("active_stage_id") == "end" and state.get("pending") is None:
            break

        user_text = input("> ").strip()
        if user_text.lower() in ("/quit", "/exit"):
            break

        state["messages"] = state.get("messages", []) + [HumanMessage(content=user_text)]

        if state_file:
            _save_state(state_file, state)

    if state_file:
        _save_state(state_file, state)

    return 0


def _run_simulation(
    graph,
    state: InterviewState,
    *,
    persona: str,
    model: str,
    temperature: float,
    max_turns: int,
    watch: bool,
    state_file: Path | None,
) -> int:
    sim = SimulatedUser(persona_id=persona, model=model, temperature=temperature)

    printed_msgs_upto = 0
    printed_evts_upto = 0
    turns = 0

    while turns < max_turns:
        state = graph.invoke(state)  # type: ignore[assignment]

        if watch:
            printed_evts_upto = _print_new_events(state, printed_evts_upto)
        printed_msgs_upto = _print_new_ai_messages(state, printed_msgs_upto)

        if state.get("error"):
            print(f"ERROR: {state['error']}")
            break

        if state.get("active_stage_id") == "end" and state.get("pending") is None:
            break

        # Find the latest bot prompt (most recent AIMessage)
        messages = state.get("messages", [])
        last_ai = next((m for m in reversed(messages) if isinstance(m, AIMessage)), None)
        bot_prompt = last_ai.content if last_ai else ""

        user_text = sim.respond(bot_prompt, state)
        print(f"> {user_text}")
        state["messages"] = state.get("messages", []) + [HumanMessage(content=user_text)]

        turns += 1

        if state_file:
            _save_state(state_file, state)

    if state_file:
        _save_state(state_file, state)

    return 0


def main(argv: list[str] | None = None) -> int:
    load_dotenv()

    parser = argparse.ArgumentParser(
        prog="quickscope",
        description="Run QuickScope interview bot (interactive) or simulate a realistic user persona.",
    )
    subparsers = parser.add_subparsers(dest="command")

    parser.add_argument("--flow-id", default="intake_sipoc_v1", help="Which flow to start with.")
    parser.add_argument(
        "--max-auto-advance-steps",
        type=int,
        default=50,
        help="Hard cycle limit for auto-advance.",
    )
    parser.add_argument(
        "--state-file",
        type=Path,
        default=None,
        help="Optional JSON file to persist/resume state.",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Print internal trace events so you can watch what the intake bot does.",
    )

    sim_parser = subparsers.add_parser("simulate", help="Run the interview against an LLM persona (LLM-as-user).")
    sim_parser.add_argument("--persona", default="1031_exchange_ops", help="Persona id to simulate.")
    sim_parser.add_argument("--model", default="gpt-4o-mini", help="OpenAI model for simulated user.")
    sim_parser.add_argument("--temperature", type=float, default=0.7, help="Simulated user temperature.")
    sim_parser.add_argument("--max-turns", type=int, default=200, help="Max simulated user turns.")

    args = parser.parse_args(argv)

    graph = create_interview_graph()

    if args.state_file and args.state_file.exists():
        state = _load_state(args.state_file)
    else:
        state = create_initial_state(flow_id=args.flow_id, max_auto_advance_steps=args.max_auto_advance_steps)

    if args.command == "simulate":
        return _run_simulation(
            graph,
            state,
            persona=args.persona,
            model=args.model,
            temperature=args.temperature,
            max_turns=args.max_turns,
            watch=args.watch,
            state_file=args.state_file,
        )

    # Default: interactive run (backwards compatible with prior CLI usage)
    return _run_interactive(graph, state, watch=args.watch, state_file=args.state_file)


if __name__ == "__main__":
    raise SystemExit(main())

