"""
LangGraph node implementations for the interview bot.

Follows .cursor/langgraph-core.mdc:
- Single responsibility per node
- Async for I/O, sync for CPU-bound
- Type hints
- Error handling
"""

from typing import Any

from langchain_core.messages import AIMessage, HumanMessage

from src.state.interview_state import InterviewState
from src.engine.flow_runner import FlowLoader, TemplateRenderer, SlotWriter, StageAdvancer
from src.actions.workflow_actions import execute_action


# Global flow loader instance (cached)
_flow_loader = FlowLoader()


def _evt(kind: str, **fields: Any) -> dict[str, Any]:
    """Create a structured trace event for observability/watch mode."""
    evt: dict[str, Any] = {"kind": kind}
    evt.update(fields)
    return evt


def _should_clarify(user_text: str, condition: str) -> bool:
    """
    Check if a clarify_if condition is met.
    
    Args:
        user_text: User's answer
        condition: Condition type (empty_or_too_short, vague, unclear_yes_no)
        
    Returns:
        True if clarification is needed
    """
    if not user_text:
        return True
    
    text = user_text.strip()
    
    if condition == "empty_or_too_short":
        # Empty or less than 5 characters
        return len(text) < 5
    
    elif condition == "vague":
        # Common vague responses
        vague_words = {"maybe", "sort of", "kind of", "i think", "not sure", "dunno", "idk", "probably"}
        lower_text = text.lower()
        
        # Don't treat clear "No" or "Yes" responses as vague
        # Include variations and common phrases that indicate "no decision"
        clear_responses = {
            "no", "yes", "y", "n", "nope", "yep", "yeah", "nah",
            "no.", "yes.", "no decision", "none", "n/a", "na", 
            "not applicable", "there is no", "there's no"
        }
        # Check for exact match or if any clear response is in the text
        if lower_text in clear_responses or any(resp in lower_text for resp in clear_responses):
            return False
        
        # Short answer with vague words only (don't penalize short but clear answers)
        return any(word in lower_text for word in vague_words)
    
    elif condition == "unclear_yes_no":
        # Not clearly yes or no
        from src.engine.flow_runner import StageAdvancer
        parsed = StageAdvancer._parse_yes_no(text)
        return parsed is None
    
    return False


def load_flow_node(state: InterviewState) -> dict[str, Any]:
    """
    Load flow definition and initialize slots if new session.
    
    Args:
        state: Current interview state
        
    Returns:
        Updates to state
    """
    try:
        flow_id = state["flow_id"]
        
        # If slots are empty, initialize from flow context
        if not state.get("slots"):
            initial_slots = _flow_loader.get_initial_slots(flow_id)
            return {"slots": initial_slots}
        
        return {}
    
    except Exception as e:
        return {
            "error": f"Failed to load flow: {str(e)}",
            "retry_count": state.get("retry_count", 0) + 1
        }


def ingest_user_answer_node(state: InterviewState) -> dict[str, Any]:
    """
    Write user answer into the pending question/confirm slot.
    
    Checks clarify_if conditions and asks follow-up if needed.
    
    Args:
        state: Current interview state
        
    Returns:
        Updates to state
    """
    try:
        messages = state.get("messages", [])
        if not messages:
            return {}
        
        # Get last user message
        last_msg = messages[-1]
        if not isinstance(last_msg, HumanMessage):
            return {}
        
        user_text = last_msg.content
        pending = state.get("pending")
        
        if not pending:
            return {}
        
        slots = state["slots"].copy()
        flow_id = state["flow_id"]
        active_stage_id = state["active_stage_id"]
        question_cursor = state.get("question_cursor", {}).copy()
        
        stage = _flow_loader.get_stage(flow_id, active_stage_id)
        stage_type = stage.get("type")

        # Pending question: write answer, check clarify_if, advance within stage or to next stage
        if "save_to" in pending:
            save_to = pending["save_to"]
            print(f"[DEBUG_INGEST] Processing save_to: {save_to}, stage: {active_stage_id}, stage_type: {stage_type}")
            
            # Check if we're in a clarification loop
            is_clarifying = pending.get("is_clarifying", False)
            
            if is_clarifying:
                # We just got the clarification answer; combine with original if present
                original_answer = pending.get("original_answer", "")
                combined_answer = f"{original_answer}\n{user_text}" if original_answer else user_text
                SlotWriter.write(slots, save_to, combined_answer)
                # Clear clarification state and advance normally
                pending_copy = pending.copy()
                pending_copy["is_clarifying"] = False
                pending_copy.pop("original_answer", None)
            else:
                # Check clarify_if conditions
                clarify_if = pending.get("clarify_if", [])
                needs_clarification = False
                follow_up = None
                
                for clarify_rule in clarify_if:
                    condition = clarify_rule.get("condition", "")
                    if _should_clarify(user_text, condition):
                        needs_clarification = True
                        follow_up = clarify_rule.get("follow_up", "Can you provide more detail?")
                        break
                
                if needs_clarification and follow_up:
                    # Set clarification state and return follow-up question
                    pending_copy = pending.copy()
                    pending_copy["is_clarifying"] = True
                    pending_copy["original_answer"] = user_text
                    
                    return {
                        "messages": [AIMessage(content=follow_up)],
                        "events": [
                            _evt(
                                "clarify_requested",
                                stage_id=active_stage_id,
                                save_to=save_to,
                                condition=condition,
                                follow_up=follow_up,
                            )
                        ],
                        "pending": pending_copy,
                        "slots": slots,
                        "question_cursor": question_cursor,
                    }
                
                # No clarification needed; write answer
                SlotWriter.write(slots, save_to, user_text)

            # Advance question index within this "questions" stage
            if stage_type == "questions":
                idx = int(pending.get("question_index", question_cursor.get(active_stage_id, 0)))
                next_idx = idx + 1
                questions = stage.get("questions", [])
                
                print(f"[DEBUG_INGEST] stage={active_stage_id}, current_idx={idx}, next_idx={next_idx}, total_questions={len(questions)}")

                if next_idx < len(questions):
                    question_cursor[active_stage_id] = next_idx
                    print(f"[DEBUG_INGEST] Advancing within stage to question {next_idx}")
                    return {
                        "slots": slots,
                        "pending": None,
                        "events": [
                            _evt(
                                "answer_ingested",
                                stage_id=active_stage_id,
                                stage_type=stage_type,
                                save_to=save_to,
                                advanced_within_stage=True,
                                next_question_index=next_idx,
                            )
                        ],
                        "question_cursor": question_cursor,
                    }

                # Finished all questions in this stage; advance to next stage
                next_stage = stage.get("next", "end")
                question_cursor[active_stage_id] = next_idx
                print(f"[DEBUG_INGEST] Finished all questions in stage, advancing to next stage: {next_stage}")
                return {
                    "slots": slots,
                    "pending": None,
                    "active_stage_id": next_stage,
                    "events": [
                        _evt(
                            "answer_ingested",
                            stage_id=active_stage_id,
                            stage_type=stage_type,
                            save_to=save_to,
                            advanced_within_stage=False,
                            next_stage_id=next_stage,
                        )
                    ],
                    "question_cursor": question_cursor,
                }

            # Not a questions stage; just clear pending
            return {
                "slots": slots,
                "pending": None,
                "events": [
                    _evt(
                        "answer_ingested",
                        stage_id=active_stage_id,
                        stage_type=stage_type,
                        save_to=save_to,
                        advanced_within_stage=False,
                    )
                ],
                "question_cursor": question_cursor,
            }

        # Pending confirm: route based on user's response
        if stage_type == "confirm":
            next_stage = StageAdvancer.get_next_stage(stage, slots, user_response=user_text)
            return {
                "slots": slots,
                "pending": None,
                "active_stage_id": next_stage,
                "events": [
                    _evt(
                        "confirm_ingested",
                        stage_id=active_stage_id,
                        user_text=user_text,
                        next_stage_id=next_stage,
                    )
                ],
                "question_cursor": question_cursor,
            }

        # Fallback: clear pending
        return {
            "slots": slots,
            "pending": None,
            "question_cursor": question_cursor,
            "events": [_evt("answer_ignored", stage_id=active_stage_id, reason="no_save_to_or_non_confirm")],
        }
    
    except Exception as e:
        return {
            "error": f"Failed to ingest answer: {str(e)}",
            "retry_count": state.get("retry_count", 0) + 1
        }


def auto_advance_node(state: InterviewState) -> dict[str, Any]:
    """
    Auto-advance through message/action/gate stages until reaching a question/confirm.
    
    Bounded loop with hard cycle limit.
    
    Args:
        state: Current interview state
        
    Returns:
        Updates to state
    """
    try:
        flow_id = state["flow_id"]
        active_stage_id = state["active_stage_id"]
        slots = state["slots"].copy()
        auto_advance_count = state.get("auto_advance_count", 0)
        max_steps = state.get("max_auto_advance_steps", 50)
        
        # Cycle protection
        steps = 0
        events: list[dict[str, Any]] = []
        
        while steps < max_steps:
            stage = _flow_loader.get_stage(flow_id, active_stage_id)
            stage_type = stage.get("type")
            
            # Stop at question or confirm (requires user input)
            if stage_type in ("questions", "confirm"):
                events.append(_evt("auto_advance_stop", stage_id=active_stage_id, stage_type=stage_type))
                break
            
            # Stop at end
            if active_stage_id == "end":
                events.append(_evt("auto_advance_stop", stage_id="end", stage_type="end"))
                break
            
            # Process automatic stages
            if stage_type == "message":
                # Just advance
                next_stage = stage.get("next", "end")
                events.append(
                    _evt(
                        "stage_advanced",
                        stage_id=active_stage_id,
                        stage_type=stage_type,
                        next_stage_id=next_stage,
                    )
                )
                active_stage_id = next_stage
            
            elif stage_type == "action":
                # Execute action
                action_name = stage.get("action")
                save_to = stage.get("save_to")
                
                # Get last user message if needed for action
                messages = state.get("messages", [])
                user_response = ""
                if messages and isinstance(messages[-1], HumanMessage):
                    user_response = messages[-1].content
                
                if action_name:
                    updated_slots, action_result = execute_action(
                        action_name,
                        slots,
                        user_response=user_response
                    )
                    slots = updated_slots
                    
                    # Store action result for branching
                    slots["_last_action_result"] = action_result

                    events.append(
                        _evt(
                            "action_executed",
                            stage_id=active_stage_id,
                            action=action_name,
                            action_result=action_result,
                            save_to=save_to,
                        )
                    )
                    
                    # Special handling for copy_next_step_to_buffer action:
                    # Reset question cursors for step capture stages and workflow_ask_next_step so questions are asked properly
                    if action_name == "copy_next_step_to_buffer":
                        stages_to_reset = [
                            "workflow_ask_next_step",  # Reset this too so "What happens next?" is asked again
                            "workflow_step_capture__step_description",
                            "workflow_step_capture__owner",
                            "workflow_step_capture__inputs",
                            "workflow_step_capture__outputs",
                            "workflow_step_capture__systems",
                            "workflow_step_capture__decision_wait_exception",
                            "workflow_step_capture__wait_exception",
                            "workflow_step_capture__decision_outcomes",
                        ]
                        
                        # Get current question_cursor from state
                        question_cursor = state.get("question_cursor", {}).copy()
                        
                        # Remove stages from cursor so they'll start from question 0 again
                        for stage_id in stages_to_reset:
                            question_cursor.pop(stage_id, None)
                        
                        # Store updated cursor to be returned
                        # We'll return this in the final result
                        events.append(
                            _evt(
                                "question_cursors_reset",
                                stage_id=active_stage_id,
                                reset_stages=stages_to_reset,
                            )
                        )
                
                next_stage = stage.get("next", "end")
                events.append(
                    _evt(
                        "stage_advanced",
                        stage_id=active_stage_id,
                        stage_type=stage_type,
                        next_stage_id=next_stage,
                    )
                )
                active_stage_id = next_stage
            
            elif stage_type == "gate":
                # Check gate and route
                next_stage = StageAdvancer.get_next_stage(stage, slots)
                events.append(
                    _evt(
                        "gate_routed",
                        stage_id=active_stage_id,
                        criteria=stage.get("criteria", []),
                        next_stage_id=next_stage,
                    )
                )
                active_stage_id = next_stage
            
            elif stage_type == "branch":
                # Use last action result to route
                last_action_result = slots.get("_last_action_result")
                
                branches = stage.get("branches", [])
                routed = False
                
                for branch in branches:
                    when = branch.get("when", {})
                    if "action_result_equals" in when:
                        expected = when["action_result_equals"].get("value")
                        if expected == last_action_result:
                            active_stage_id = branch.get("next", "end")
                            routed = True
                            break
                
                if not routed:
                    # Default to first branch
                    if branches:
                        active_stage_id = branches[0].get("next", "end")
                    else:
                        active_stage_id = "end"

                events.append(
                    _evt(
                        "branch_routed",
                        stage_id=stage.get("id", active_stage_id),
                        last_action_result=last_action_result,
                        next_stage_id=active_stage_id,
                    )
                )
            
            elif stage_type == "loop":
                # Check loop stop condition
                stop_condition = stage.get("stop_condition", {})
                signal_slot = stop_condition.get("signal_slot")
                
                should_exit_loop = False
                
                # Check if loop should exit based on signal slot
                if signal_slot:
                    # For data_elements loop, check if current_data_element_index is None
                    if "data_elements" in signal_slot:
                        current_idx = slots.get("process_parameters", {}).get("current_data_element_index")
                        if current_idx is None:
                            should_exit_loop = True
                            events.append(
                                _evt(
                                    "loop_exit",
                                    stage_id=active_stage_id,
                                    reason="all_data_elements_validated",
                                )
                            )
                
                if should_exit_loop:
                    # Exit loop via on_stop
                    next_stage = stage.get("on_stop", "end")
                    events.append(
                        _evt(
                            "stage_advanced",
                            stage_id=active_stage_id,
                            stage_type=stage_type,
                            next_stage_id=next_stage,
                            note="loop_exited",
                        )
                    )
                    active_stage_id = next_stage
                else:
                    # Continue loop - advance to next stage within loop
                    next_stage = stage.get("next", "end")
                    events.append(
                        _evt(
                            "stage_advanced",
                            stage_id=active_stage_id,
                            stage_type=stage_type,
                            next_stage_id=next_stage,
                            note="loop_continue",
                        )
                    )
                    active_stage_id = next_stage
            
            elif stage_type == "output":
                # Output stage - just advance
                next_stage = stage.get("next", "end")
                events.append(
                    _evt(
                        "stage_advanced",
                        stage_id=active_stage_id,
                        stage_type=stage_type,
                        next_stage_id=next_stage,
                    )
                )
                active_stage_id = next_stage
            
            else:
                # Unknown stage type, stop
                events.append(_evt("auto_advance_stop", stage_id=active_stage_id, stage_type=stage_type))
                break
            
            steps += 1
        
        # Check cycle limit
        if steps >= max_steps:
            return {
                "error": f"Auto-advance exceeded max steps ({max_steps})",
                "retry_count": state.get("retry_count", 0) + 1
            }
        
        # Check if we reset question_cursor during this auto-advance
        # Look for question_cursors_reset event
        reset_done = any(evt.get("kind") == "question_cursors_reset" for evt in events)
        
        result = {
            "active_stage_id": active_stage_id,
            "slots": slots,
            "auto_advance_count": auto_advance_count + steps,
            "events": events + [_evt("auto_advance_summary", steps=steps, max_steps=max_steps)],
        }
        
        # If we reset cursors, include the updated question_cursor in the result
        if reset_done:
            question_cursor = state.get("question_cursor", {}).copy()
            stages_to_reset = [
                "workflow_ask_next_step",  # Reset this too so "What happens next?" is asked again
                "workflow_step_capture__step_description",
                "workflow_step_capture__owner",
                "workflow_step_capture__inputs",
                "workflow_step_capture__outputs",
                "workflow_step_capture__systems",
                "workflow_step_capture__decision_wait_exception",
                "workflow_step_capture__wait_exception",
                "workflow_step_capture__decision_outcomes",
            ]
            for stage_id in stages_to_reset:
                question_cursor.pop(stage_id, None)
            result["question_cursor"] = question_cursor
        
        return result
    
    except Exception as e:
        return {
            "error": f"Auto-advance failed: {str(e)}",
            "retry_count": state.get("retry_count", 0) + 1
        }


def _detect_loop(state: InterviewState) -> bool:
    """
    Detect if we're in an infinite loop by checking recent messages.
    
    Returns True if we detect a loop (same question asked 3+ times recently).
    """
    messages = state.get("messages", [])
    if len(messages) < 6:
        return False
    
    # Get last 10 AI messages
    recent_ai_messages = []
    for msg in reversed(messages[-20:]):
        if isinstance(msg, AIMessage):
            recent_ai_messages.append(msg.content.strip())
            if len(recent_ai_messages) >= 10:
                break
    
    if len(recent_ai_messages) < 3:
        return False
    
    # Check if same question appears 3+ times in recent messages
    from collections import Counter
    msg_counts = Counter(recent_ai_messages)
    
    for msg, count in msg_counts.items():
        # Ignore very short transition messages
        if len(msg) > 20 and count >= 3:
            print(f"[LOOP DETECTED] Message repeated {count} times: '{msg[:60]}...'")
            return True
    
    return False


def render_prompt_node(state: InterviewState) -> dict[str, Any]:
    """
    Render the next question or confirm prompt and set pending.
    
    Args:
        state: Current interview state
        
    Returns:
        Updates to state
    """
    try:
        # CRITICAL: Detect infinite loops before rendering
        if _detect_loop(state):
            # Force advance to next stage to break the loop
            flow_id = state["flow_id"]
            active_stage_id = state["active_stage_id"]
            stage = _flow_loader.get_stage(flow_id, active_stage_id)
            next_stage = stage.get("next", "end")
            
            return {
                "messages": [AIMessage(content="Thanks — moving on.")],
                "pending": None,
                "active_stage_id": next_stage,
                "events": [
                    _evt(
                        "loop_detected_force_advance",
                        stage_id=active_stage_id,
                        next_stage_id=next_stage,
                        note="Detected infinite loop, forcing advance to next stage"
                    )
                ],
            }
        
        flow_id = state["flow_id"]
        active_stage_id = state["active_stage_id"]
        slots = state["slots"]
        question_cursor = state.get("question_cursor", {})
        
        # If at end, send completion message
        if active_stage_id == "end":
            stage = _flow_loader.get_stage(flow_id, active_stage_id)
            prompt = stage.get("prompt", "Interview complete. Thank you!")
            rendered = TemplateRenderer.render(prompt, slots)
            
            return {
                "messages": [AIMessage(content=rendered)],
                "pending": None,
                "events": [_evt("prompt_rendered", stage_id="end", pending_type=None)],
            }
        
        stage = _flow_loader.get_stage(flow_id, active_stage_id)
        stage_type = stage.get("type")
        
        if stage_type == "questions":
            questions = stage.get("questions", [])
            if questions:
                idx = question_cursor.get(active_stage_id, 0)
                
                print(f"[DEBUG_RENDER] stage={active_stage_id}, idx={idx}, total_questions={len(questions)}")

                # If we've exhausted the questions, advance to next stage and prompt generically.
                # (Normally, ingest_user_answer_node moves us forward; this is a safety net.)
                if idx >= len(questions):
                    print(f"[DEBUG_RENDER] Questions exhausted, advancing to next stage")
                    return {
                        "active_stage_id": stage.get("next", "end"),
                        "messages": [AIMessage(content="Thanks — moving on.")],
                        "pending": None,
                        "events": [
                            _evt(
                                "prompt_rendered",
                                stage_id=active_stage_id,
                                pending_type=None,
                                note="questions_exhausted_safety_net",
                            )
                        ],
                    }

                q = questions[idx]
                ask = q.get("ask", "")
                rendered = TemplateRenderer.render(ask, slots)
                
                print(f"[DEBUG_RENDER] Rendering question {idx}: {ask[:50]}...")
                
                pending = {
                    "question_id": q.get("id"),
                    "save_to": q.get("save_to"),
                    "ask": rendered,
                    "clarify_if": q.get("clarify_if", []),
                    "question_index": idx,
                }
                
                return {
                    "messages": [AIMessage(content=rendered)],
                    "pending": pending,
                    "events": [
                        _evt(
                            "prompt_rendered",
                            stage_id=active_stage_id,
                            pending_type="question",
                            question_id=pending.get("question_id"),
                            save_to=pending.get("save_to"),
                            question_index=idx,
                        )
                    ],
                }
        
        elif stage_type == "confirm":
            summary_template = stage.get("summary_template", "")
            ask = stage.get("ask", "Is this correct?")
            
            summary = TemplateRenderer.render(summary_template, slots)
            full_prompt = f"{summary}\n\n{ask}"
            
            pending = {
                "confirm_id": stage.get("id"),
                "summary_template": summary_template,
                "ask": ask,
                "on_yes": stage.get("on_yes"),
                "on_no": stage.get("on_no")
            }
            
            return {
                "messages": [AIMessage(content=full_prompt)],
                "pending": pending,
                "events": [
                    _evt(
                        "prompt_rendered",
                        stage_id=active_stage_id,
                        pending_type="confirm",
                        confirm_id=pending.get("confirm_id"),
                        on_yes=pending.get("on_yes"),
                        on_no=pending.get("on_no"),
                    )
                ],
            }
        
        # Shouldn't reach here if auto-advance worked correctly
        return {
            "messages": [AIMessage(content="Unexpected stage type. Please continue.")],
            "pending": None,
            "events": [_evt("prompt_rendered", stage_id=active_stage_id, pending_type=None, note="unexpected")],
        }
    
    except Exception as e:
        return {
            "error": f"Failed to render prompt: {str(e)}",
            "retry_count": state.get("retry_count", 0) + 1
        }


def should_continue(state: InterviewState) -> str:
    """
    Routing function: determine if interview should continue or end.
    
    Args:
        state: Current interview state
        
    Returns:
        "continue" or "end"
    """
    if state.get("error"):
        return "end"
    
    if state["active_stage_id"] == "end":
        return "end"
    
    return "continue"
