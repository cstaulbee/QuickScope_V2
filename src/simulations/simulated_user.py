"""
LLM-as-user simulator for running the interview bot against a realistic persona.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from src.state.interview_state import InterviewState
from src.simulations.personas import get_persona


class SimulatedUser:
    def __init__(
        self,
        persona_id: str = "1031_exchange_ops",
        *,
        model: str = "gpt-4o-mini",
        temperature: float = 0.7,
        llm: Optional[Any] = None,
    ) -> None:
        self.persona_id = persona_id
        self.persona = get_persona(persona_id)
        self.model = model
        self.temperature = temperature
        self.llm = llm or ChatOpenAI(model=model, temperature=temperature)

    def respond(self, bot_prompt: str, state: InterviewState) -> str:
        """
        Produce the next "human" response as the persona.
        """
        # CRITICAL: Detect loops before processing
        messages = state.get("messages", [])
        if len(messages) >= 8:
            # Check if bot is repeating the same question
            recent_bot_msgs = []
            for msg in reversed(messages[-12:]):
                if hasattr(msg, "content") and not isinstance(msg, type(messages[-1])):  # AI messages
                    recent_bot_msgs.append(msg.content.strip())
                    if len(recent_bot_msgs) >= 6:
                        break
            
            # Count repetitions
            from collections import Counter
            if recent_bot_msgs:
                msg_counts = Counter(recent_bot_msgs)
                for msg, count in msg_counts.items():
                    if count >= 3 and len(msg) > 20:
                        print(f"[SIM_USER_LOOP_BREAKER] Detected bot loop ({count}x): '{msg[:60]}...'")
                        # Force a different response to break the loop
                        return "Let's move on to the next part of the process."
        
        # Handle transition messages with minimal response to avoid loops
        # BUT only if there's no actual question pending
        pending = state.get("pending") or {}
        has_actual_question = "save_to" in pending or "confirm_id" in pending
        active_stage = state.get("active_stage_id", "unknown")
        
        # Debug logging - sanitize for Windows console
        safe_prompt = bot_prompt[:80].encode('ascii', errors='replace').decode('ascii')
        print(f"[SIM_USER_DEBUG] active_stage={active_stage}, has_question={has_actual_question}, bot_prompt='{safe_prompt}...'")
        
        if not has_actual_question:
            bot_prompt_stripped = bot_prompt.strip().rstrip('.!').lower()
            transition_phrases = [
                "thanks — moving on",
                "thanks - moving on", 
                "thanks moving on",
                "step captured",
                "live diagram updated",
            ]
            
            if any(phrase in bot_prompt_stripped for phrase in transition_phrases):
                print(f"[SIM_USER_DEBUG] Detected transition phrase, returning 'ok'")
                return "ok"
        
        # For confirmation questions, be more cooperative after initial feedback
        if "confirm_id" in pending:
            messages = state.get("messages", [])
            confirm_count = sum(1 for msg in messages if "Is this step captured correctly?" in str(getattr(msg, "content", "")))
            
            # After first rejection, accept to move forward
            if confirm_count >= 2:
                print(f"[SIM_USER_DEBUG] Multiple confirmations detected ({confirm_count}), accepting to progress")
                return "Yes, that captures it well enough. Let's move on to the next step."
        
        pending_type = "confirm" if "confirm_id" in pending else ("question" if "save_to" in pending else None)
        slots = state.get("slots", {})

        # Keep slot context small to avoid huge prompts. Include a few top-level keys.
        # Also include workflow info so the persona can see what steps have been captured
        workflows = slots.get("workflows", {})
        active_wf_id = slots.get("workflow_capture_state", {}).get("active_workflow_id")
        captured_steps = []
        if active_wf_id and "maps" in workflows:
            # workflows["maps"] is a list, find the matching workflow
            for wf in workflows["maps"]:
                if wf.get("workflow_id") == active_wf_id:
                    captured_steps = [
                        step.get("description", "")[:80] + ("..." if len(step.get("description", "")) > 80 else "")
                        for step in wf.get("steps", [])
                    ]
                    break
        
        slot_hint = {
            "engagement": slots.get("engagement", {}),
            "process_profile": slots.get("process_profile", {}),
            "scope": slots.get("scope", {}),
            "sipoc": slots.get("sipoc", {}),
            "workflows_selected": slots.get("workflows", {}).get("selected_workflows", []),
            "steps_captured_so_far": captured_steps,  # Show what's been captured to avoid repetition
        }

        system = self._build_system_prompt()
        user = self._build_user_prompt(
            bot_prompt=bot_prompt,
            pending_type=pending_type,
            save_to=pending.get("save_to"),
            question_id=pending.get("question_id"),
            confirm_id=pending.get("confirm_id"),
            slot_hint=slot_hint,
        )

        resp = self.llm.invoke([SystemMessage(content=system), HumanMessage(content=user)])
        text = getattr(resp, "content", "")
        return self._clean(text)

    def _build_system_prompt(self) -> str:
        p = self.persona
        return (
            "You are roleplaying a real business user being interviewed by a process-discovery bot.\n"
            "Stay in character. Do not provide consulting advice; only answer as the user.\n\n"
            f"Persona: {p.get('name')}\n"
            f"Company: {json.dumps(p.get('company', {}), ensure_ascii=False)}\n"
            f"Process focus: {json.dumps(p.get('process_focus', {}), ensure_ascii=False)}\n"
            f"Pain points: {json.dumps(p.get('pain_points', []), ensure_ascii=False)}\n"
            f"Success criteria: {json.dumps(p.get('success_criteria', []), ensure_ascii=False)}\n"
            f"Tone/style: {json.dumps(p.get('tone_and_style', {}), ensure_ascii=False)}\n"
            f"Domain notes: {json.dumps(p.get('domain_notes', []), ensure_ascii=False)}\n"
            f"Constraints: {json.dumps(p.get('constraints', []), ensure_ascii=False)}\n\n"
            "Output rules:\n"
            "- Return ONLY the user's answer content.\n"
            "- Keep answers concise unless the question explicitly asks for detail or lists.\n"
            "- If asked yes/no, answer clearly with 'Yes' or 'No' plus short context.\n"
            "- Respond as if you were a human, not an AI or robot. Use contractions and casual language.\n"
        )

    @staticmethod
    def _build_user_prompt(
        *,
        bot_prompt: str,
        pending_type: Optional[str],
        save_to: Optional[str],
        question_id: Optional[str],
        confirm_id: Optional[str],
        slot_hint: dict[str, Any],
    ) -> str:
        # Add reminder about steps if asking for next step
        steps_reminder = ""
        if "steps_captured_so_far" in slot_hint and slot_hint["steps_captured_so_far"]:
            steps_reminder = (
                "\n=== STEPS YOU HAVE ALREADY DESCRIBED ===\n"
                f"{chr(10).join(f'{i+1}. {step}' for i, step in enumerate(slot_hint['steps_captured_so_far']))}\n"
                "\n>>> CRITICAL: When asked 'What happens next?', describe the NEXT step that comes AFTER all the steps above in the CHRONOLOGICAL flow of the 1031 Exchange process. <<<\n"
                ">>> DO NOT REPEAT any step you've already described. Move forward in the timeline. <<<\n"
                ">>> Think: intake → agreement → relinquished sale closes → funds received → 45-day ID starts → client identifies properties → ID letter submitted → ID reviewed → upleg purchase contract → upleg purchase closes → funds disbursed → 180-day completion <<<\n"
            )
        
        return (
            "You are being interviewed. Here is the bot's latest prompt:\n"
            f"{bot_prompt}\n\n"
            "Context (for consistency; do not restate unless asked):\n"
            f"{json.dumps({k: v for k, v in slot_hint.items() if k != 'steps_captured_so_far'}, indent=2, ensure_ascii=False)}\n"
            f"{steps_reminder}\n"
            "Metadata:\n"
            f"- pending_type: {pending_type}\n"
            f"- question_id: {question_id}\n"
            f"- confirm_id: {confirm_id}\n"
            f"- save_to: {save_to}\n\n"
            "Now respond as the user."
        )

    @staticmethod
    def _clean(text: str) -> str:
        t = (text or "").strip()
        # Strip common markdown fences if the model adds them
        if t.startswith("```") and t.endswith("```"):
            t = t.strip("`").strip()
        return t.strip()

